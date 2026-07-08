from __future__ import annotations

import argparse
import os

import uvicorn

from .config import get_settings


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip()
    return value or default


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the Herald backend server")
    subparsers = parser.add_subparsers(dest="command")
    reset = subparsers.add_parser("reset-password", help="Reset a user's password")
    reset.add_argument("email")
    parser.add_argument(
        "--host",
        default=_env_str("BACKEND_HOST", "0.0.0.0"),
        help="Host interface to bind the server to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=_env_int("BACKEND_PORT", _env_int("PORT", 8000)),
        help="Port to bind the server to",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=max(_env_int("WEB_CONCURRENCY", 2), 1),
        help="Number of uvicorn worker processes",
    )
    return parser


def _reset_password(email: str) -> None:
    import asyncio
    import secrets

    import asyncpg

    from .auth.passwords import make_password
    from .config import get_settings

    new_password = secrets.token_urlsafe(12)

    async def _go() -> int:
        conn = await asyncpg.connect(get_settings().raw_database_url)
        try:
            result = await conn.execute(
                "UPDATE users SET password = $1 WHERE email = $2",
                make_password(new_password),
                email,
            )
            return int(result.split()[-1])
        finally:
            await conn.close()

    if asyncio.run(_go()) == 0:
        raise SystemExit(f"no user with email {email}")
    print(f"new password for {email}: {new_password}")


def main() -> None:
    args = _build_parser().parse_args()
    if args.command == "reset-password":
        _reset_password(args.email)
        return
    uvicorn.run(
        "backend.main:app",
        host=args.host,
        port=args.port,
        workers=max(args.workers, 1),
        proxy_headers=True,
        forwarded_allow_ips=get_settings().forwarded_allow_ips or None,
    )
