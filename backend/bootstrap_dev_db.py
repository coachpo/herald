from __future__ import annotations

import asyncio
import os

import asyncpg

DDL_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS accounts_user (
        id UUID PRIMARY KEY,
        email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        email_verified_at TIMESTAMPTZ NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        is_staff BOOLEAN NOT NULL DEFAULT FALSE,
        is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS accounts_emailverificationtoken (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
        token_hash TEXT NOT NULL UNIQUE,
        expires_at TIMESTAMPTZ NOT NULL,
        used_at TIMESTAMPTZ NULL,
        created_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS accounts_passwordresettoken (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
        token_hash TEXT NOT NULL UNIQUE,
        expires_at TIMESTAMPTZ NOT NULL,
        used_at TIMESTAMPTZ NULL,
        created_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS accounts_refreshtoken (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
        token_hash TEXT NOT NULL UNIQUE,
        family_id UUID NOT NULL,
        replaced_by_id UUID NULL,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL,
        last_used_at TIMESTAMPTZ NULL,
        expires_at TIMESTAMPTZ NOT NULL,
        revoked_at TIMESTAMPTZ NULL,
        revoked_reason TEXT NULL,
        ip TEXT NULL,
        user_agent TEXT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS beacon_ingestendpoint (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        created_at TIMESTAMPTZ NOT NULL,
        revoked_at TIMESTAMPTZ NULL,
        deleted_at TIMESTAMPTZ NULL,
        last_used_at TIMESTAMPTZ NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS beacon_channel (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
        type TEXT NOT NULL,
        name TEXT NOT NULL,
        config_json_encrypted TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        disabled_at TIMESTAMPTZ NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS beacon_forwardingrule (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        filter_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        channel_id UUID NOT NULL REFERENCES beacon_channel(id) ON DELETE CASCADE,
        payload_template_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS beacon_message (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
        ingest_endpoint_id UUID NOT NULL REFERENCES beacon_ingestendpoint(id) ON DELETE CASCADE,
        received_at TIMESTAMPTZ NOT NULL,
        title TEXT NULL,
        body TEXT NOT NULL,
        "group" TEXT NULL,
        priority INTEGER NOT NULL DEFAULT 3,
        tags_json JSONB NOT NULL DEFAULT '[]'::jsonb,
        url TEXT NULL,
        extras_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        content_type TEXT NULL,
        body_sha256 TEXT NOT NULL,
        headers_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        query_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        remote_ip TEXT NULL,
        user_agent TEXT NULL,
        deleted_at TIMESTAMPTZ NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS beacon_delivery (
        id UUID PRIMARY KEY,
        user_id UUID NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
        message_id UUID NOT NULL REFERENCES beacon_message(id) ON DELETE CASCADE,
        rule_id UUID NOT NULL REFERENCES beacon_forwardingrule(id) ON DELETE CASCADE,
        channel_id UUID NOT NULL REFERENCES beacon_channel(id) ON DELETE CASCADE,
        status TEXT NOT NULL,
        attempt_count INTEGER NOT NULL DEFAULT 0,
        next_attempt_at TIMESTAMPTZ NULL,
        sent_at TIMESTAMPTZ NULL,
        last_error TEXT NULL,
        provider_response_json JSONB NULL,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_accounts_emailverificationtoken_user ON accounts_emailverificationtoken (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_accounts_passwordresettoken_user ON accounts_passwordresettoken (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_accounts_refreshtoken_user ON accounts_refreshtoken (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_accounts_refreshtoken_family ON accounts_refreshtoken (family_id)",
    "CREATE INDEX IF NOT EXISTS idx_beacon_ingestendpoint_user_created ON beacon_ingestendpoint (user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_beacon_channel_user_created ON beacon_channel (user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_beacon_forwardingrule_user_created ON beacon_forwardingrule (user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_beacon_message_user_received ON beacon_message (user_id, received_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_beacon_message_endpoint ON beacon_message (ingest_endpoint_id)",
    "CREATE INDEX IF NOT EXISTS idx_beacon_delivery_message_status ON beacon_delivery (message_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_beacon_delivery_next_attempt ON beacon_delivery (status, next_attempt_at)",
)


async def main() -> None:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL is required")

    conn = await asyncpg.connect(database_url)
    try:
        for statement in DDL_STATEMENTS:
            await conn.execute(statement)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
