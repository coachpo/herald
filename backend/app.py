"""One local process owns the HTTP interface and durable delivery loop."""
from __future__ import annotations

import asyncio
import fcntl
import logging
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .api import router
from .config import Settings, get_settings
from .middleware import BodyLimitMiddleware, SafeErrorMiddleware
from .store import Store, StoreError
from .worker import Worker
from .tasks import database_call

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, store: Store | None = None,
               start_worker: bool = True) -> FastAPI:
    settings = settings or get_settings()
    store = store or Store(settings.database_path, settings.encryption_key)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        lock = (settings.data_dir / '.lock').open('a')
        try:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('Herald is already running for this data directory') from None
            await database_call(store.initialize)
            worker = Worker(store, settings)
            app.state.worker = worker
            task = asyncio.create_task(worker.run()) if start_worker else None
            app.state.worker_task = task
            try:
                yield
            finally:
                if task:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    except Exception as exc:
                        logger.error('delivery worker stopped (%s); restart to recover', type(exc).__name__)
        finally:
            lock.close()

    version_path = Path(__file__).resolve().parent.parent / 'VERSION'
    app = FastAPI(title='Herald', version=version_path.read_text().strip(),
                  lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.store = store
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(SafeErrorMiddleware)

    @app.exception_handler(StoreError)
    async def domain_error(request: Request, exc):
        return JSONResponse({'detail': exc.code}, exc.status)

    @app.exception_handler(RequestValidationError)
    @app.exception_handler(ValidationError)
    async def validation_error(request: Request, exc):
        # Pydantic's default error response includes input, including passwords.
        return JSONResponse({'detail': 'validation_error', 'errors': [
            {'field': '.'.join(str(p) for p in e['loc']), 'code': e['type']}
            for e in exc.errors()
        ]}, 422)

    @app.exception_handler(ValueError)
    async def invalid_input(request: Request, exc):
        return JSONResponse({'detail': 'invalid_input'}, 422)

    @app.exception_handler(sqlite3.Error)
    @app.exception_handler(OSError)
    async def storage_error(request: Request, exc):
        logger.error('storage operation failed (%s)', type(exc).__name__)
        return JSONResponse({'detail': 'storage_unavailable'}, 503)

    @app.get('/health')
    async def health():
        try:
            def check():
                with sqlite3.connect(settings.database_path) as db:
                    db.execute('SELECT COUNT(*) FROM messages').fetchone()
            await database_call(check)
            task = getattr(app.state, 'worker_task', None)
            if task is not None and task.done():
                return JSONResponse({'status': 'degraded', 'database': 'connected', 'worker': 'stopped'}, 503)
        except (sqlite3.Error, OSError):
            return JSONResponse({'status': 'degraded', 'database': 'unavailable'}, 503)
        return {'status': 'ok', 'database': 'connected', 'version': app.version}

    app.include_router(router)
    # Production serves the built single-page UI from the same origin; Vite is dev-only.
    frontend = Path(__file__).resolve().parent.parent / 'frontend' / 'dist'
    if frontend.is_dir():
        app.mount('/', StaticFiles(directory=frontend, html=True), name='ui')
    return app
