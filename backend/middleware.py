"""Bound the existing 1 MiB JSON ingress size before parsing, including chunked bodies."""
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send
import logging


class SafeErrorMiddleware:
    """Contain unexpected exceptions before Uvicorn can log credential-bearing text."""
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        started = False

        async def track(message):
            nonlocal started
            if message['type'] == 'http.response.start':
                started = True
            await send(message)

        try:
            await self.app(scope, receive, track)
        except Exception as exc:
            logging.getLogger(__name__).error('request failed (%s)', type(exc).__name__)
            if started:
                raise RuntimeError('internal_error') from None
            await JSONResponse({'detail': 'internal_error'}, 500)(scope, receive, send)


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, limit: int = 1024 * 1024):
        self.app, self.limit = app, limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http' or scope['method'] not in {'POST', 'PUT'}:
            await self.app(scope, receive, send)
            return
        chunks = []
        size = 0
        while True:
            event = await receive()
            if event['type'] == 'http.disconnect':
                return
            size += len(event.get('body', b''))
            if size > self.limit:
                await JSONResponse({'detail': 'body_too_large'}, 413)(scope, receive, send)
                return
            chunks.append(event.get('body', b''))
            if not event.get('more_body', False):
                break
        delivered = False

        async def buffered_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
            return await receive()

        await self.app(scope, buffered_receive, send)
