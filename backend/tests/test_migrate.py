import asyncio

import asyncpg

from backend.migrate import apply_migrations
from backend.tests.conftest import TEST_DATABASE_URL


async def _fetchval(query: str):
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        return await conn.fetchval(query)
    finally:
        await conn.close()


async def _drop_all():
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    finally:
        await conn.close()


def test_apply_migrations_from_scratch_then_idempotent():
    asyncio.run(_drop_all())
    first = asyncio.run(apply_migrations(TEST_DATABASE_URL))
    assert first == ["0001_initial"]
    n = asyncio.run(
        _fetchval(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name IN "
            "('users','refresh_tokens','ingest_endpoints','channels','rules','messages','deliveries')"
        )
    )
    assert n == 7
    second = asyncio.run(apply_migrations(TEST_DATABASE_URL))
    assert second == []
