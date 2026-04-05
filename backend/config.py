from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse


PACKAGE_DIR = Path(__file__).resolve().parent
ROOT_DIR = PACKAGE_DIR.parent
BACKEND_DIR = ROOT_DIR / "backend"


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_key = key.strip()
        normalized_value = value.strip().strip('"').strip("'")
        if normalized_key and normalized_key not in os.environ:
            os.environ[normalized_key] = normalized_value


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _env_str(key: str, default: str) -> str:
    raw = os.environ.get(key)
    if raw is None:
        return default
    value = raw.strip()
    return value or default


def _to_async_database_url(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    scheme = (parsed.scheme or "").split("+", 1)[0].lower()

    if scheme in {"postgres", "postgresql"}:
        return raw_url.replace(f"{parsed.scheme}://", "postgresql+asyncpg://", 1)

    raise ValueError(f"unsupported_database_scheme:{parsed.scheme}")


_load_env_file(BACKEND_DIR / ".env")


@dataclass
class Settings:
    root_dir: Path
    backend_dir: Path
    raw_database_url: str
    async_database_url: str
    secret_key: str
    jwt_signing_key: str
    jwt_access_ttl_seconds: int
    jwt_refresh_ttl_seconds: int
    channel_config_encryption_key: str
    cors_allowed_origins: list[str]
    worker_poll_seconds: float
    worker_batch_size: int
    delivery_max_attempts: int
    delivery_backoff_base_seconds: int
    delivery_backoff_max_seconds: int
    db_pool_size: int
    db_max_overflow: int
    db_pool_recycle: int
    log_level: str
    log_format: str
    sentry_dsn: str
    sentry_traces_sample_rate: float
    sentry_environment: str
    allow_user_signup: bool


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    raw_database_url = os.environ.get("DATABASE_URL", "")
    secret_key = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure")

    # Parse CORS origins
    cors_raw = os.environ.get("CORS_ALLOWED_ORIGINS", "")
    cors_origins = [o.strip() for o in cors_raw.split(",") if o.strip()]

    return Settings(
        root_dir=ROOT_DIR,
        backend_dir=BACKEND_DIR,
        raw_database_url=raw_database_url,
        async_database_url=_to_async_database_url(raw_database_url),
        secret_key=secret_key,
        jwt_signing_key=os.environ.get("JWT_SIGNING_KEY", secret_key),
        jwt_access_ttl_seconds=_env_int("JWT_ACCESS_TTL_SECONDS", 900),
        jwt_refresh_ttl_seconds=_env_int("JWT_REFRESH_TTL_SECONDS", 2592000),
        channel_config_encryption_key=os.environ.get(
            "CHANNEL_CONFIG_ENCRYPTION_KEY", ""
        ),
        cors_allowed_origins=cors_origins,
        worker_poll_seconds=float(os.environ.get("WORKER_POLL_SECONDS", "1.0")),
        worker_batch_size=_env_int("WORKER_BATCH_SIZE", 50),
        delivery_max_attempts=_env_int("DELIVERY_MAX_ATTEMPTS", 10),
        delivery_backoff_base_seconds=_env_int("DELIVERY_BACKOFF_BASE_SECONDS", 5),
        delivery_backoff_max_seconds=_env_int("DELIVERY_BACKOFF_MAX_SECONDS", 1800),
        db_pool_size=_env_int("DB_POOL_SIZE", 5),
        db_max_overflow=_env_int("DB_MAX_OVERFLOW", 10),
        db_pool_recycle=_env_int("DB_POOL_RECYCLE", 3600),
        log_level=_env_str("LOG_LEVEL", "INFO").upper(),
        log_format=_env_str("LOG_FORMAT", "json").lower(),
        sentry_dsn=os.environ.get("SENTRY_DSN", ""),
        sentry_traces_sample_rate=float(
            os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")
        ),
        sentry_environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        allow_user_signup=(
            os.environ.get("ALLOW_USER_SIGNUP", "true").lower() in {"true", "1", "yes"}
        ),
    )
