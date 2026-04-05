from __future__ import annotations

import argparse
import os

import uvicorn


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


def main() -> None:
    args = _build_parser().parse_args()
    uvicorn.run(
        "backend.main:app",
        host=args.host,
        port=args.port,
        workers=max(args.workers, 1),
    )
