"""Numbered SQL migration runner.

Usage: python -m backend.migrate
Files: backend/migrations/NNNN_name.sql, applied in filename order,
each inside one transaction, recorded in schema_migrations.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import asyncpg

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


async def apply_migrations(database_url: str) -> list[str]:
    conn = await asyncpg.connect(database_url)
    applied: list[str] = []
    try:
        await conn.execute("SELECT pg_advisory_lock(727001)")
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, "
            "applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        rows = await conn.fetch("SELECT version FROM schema_migrations")
        done = {row["version"] for row in rows}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = path.stem
            if version in done:
                continue
            async with conn.transaction():
                await conn.execute(path.read_text(encoding="utf-8"))
                await conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES ($1)", version
                )
            applied.append(version)
    finally:
        await conn.close()
    return applied


def main() -> None:
    # read env directly: get_settings() eagerly derives the async URL and would
    # raise a misleading unsupported_database_scheme error on an empty DATABASE_URL
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        sys.exit("DATABASE_URL is required")
    applied = asyncio.run(apply_migrations(url))
    print(f"migrations applied: {applied if applied else 'none (up to date)'}")


if __name__ == "__main__":
    main()
