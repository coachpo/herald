from __future__ import annotations

import asyncio
import os
import uuid
import warnings
from dataclasses import dataclass
from typing import Any

from sqlalchemy import MetaData, Table
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from .config import get_settings


@dataclass(frozen=True)
class ReflectedTables:
    users: Table
    ingest_endpoints: Table
    channels: Table
    rules: Table
    messages: Table
    deliveries: Table
    refresh_tokens: Table
    email_verification_tokens: Table
    password_reset_tokens: Table


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None
_tables: ReflectedTables | None = None
_tables_lock: asyncio.Lock | None = None


def _get_tables_lock() -> asyncio.Lock:
    global _tables_lock
    if _tables_lock is None:
        _tables_lock = asyncio.Lock()
    return _tables_lock


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        async_url = settings.async_database_url
        use_null_pool = os.environ.get("DB_POOL_CLASS", "").lower() == "null"
        engine_kwargs: dict[str, Any] = {
            "future": True,
            "pool_pre_ping": True,
        }
        if use_null_pool:
            engine_kwargs["poolclass"] = NullPool
            engine_kwargs.pop("pool_pre_ping", None)
        else:
            engine_kwargs["pool_size"] = settings.db_pool_size
            engine_kwargs["max_overflow"] = settings.db_max_overflow
            engine_kwargs["pool_recycle"] = settings.db_pool_recycle
        _engine = create_async_engine(async_url, **engine_kwargs)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def get_session():
    async with get_sessionmaker()() as session:
        yield session


async def get_tables() -> ReflectedTables:
    global _tables
    if _tables is not None:
        return _tables

    async with _get_tables_lock():
        if _tables is not None:
            return _tables

        metadata = MetaData()
        only_tables = [
            "accounts_user",
            "beacon_ingestendpoint",
            "beacon_channel",
            "beacon_forwardingrule",
            "beacon_message",
            "beacon_delivery",
            "accounts_refreshtoken",
            "accounts_emailverificationtoken",
            "accounts_passwordresettoken",
        ]

        async with get_engine().begin() as connection:
            with warnings.catch_warnings():
                from sqlalchemy.exc import SAWarning

                warnings.filterwarnings(
                    "ignore",
                    message="Skipped unsupported reflection of expression-based index.*",
                    category=SAWarning,
                )
                await connection.run_sync(
                    lambda sync_connection: metadata.reflect(
                        bind=sync_connection,
                        only=only_tables,
                    )
                )

        _tables = ReflectedTables(
            users=metadata.tables["accounts_user"],
            ingest_endpoints=metadata.tables["beacon_ingestendpoint"],
            channels=metadata.tables["beacon_channel"],
            rules=metadata.tables["beacon_forwardingrule"],
            messages=metadata.tables["beacon_message"],
            deliveries=metadata.tables["beacon_delivery"],
            refresh_tokens=metadata.tables["accounts_refreshtoken"],
            email_verification_tokens=metadata.tables[
                "accounts_emailverificationtoken"
            ],
            password_reset_tokens=metadata.tables["accounts_passwordresettoken"],
        )
        return _tables


def serialize_uuid(value: Any) -> str:
    if isinstance(value, uuid.UUID):
        return str(value)

    raw = str(value)
    if len(raw) == 32:
        return str(uuid.UUID(hex=raw))
    return str(uuid.UUID(raw))


def clear_database_state() -> None:
    global _engine, _sessionmaker, _tables, _tables_lock
    _engine = None
    _sessionmaker = None
    _tables = None
    _tables_lock = None


async def dispose_database_state() -> None:
    global _engine, _sessionmaker, _tables, _tables_lock
    engine = _engine
    _engine = None
    _sessionmaker = None
    _tables = None
    _tables_lock = None
    if engine is not None:
        await engine.dispose()
