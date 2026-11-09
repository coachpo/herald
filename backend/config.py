"""Single-instance configuration; generated credentials never enter the database."""
from __future__ import annotations

import os
import secrets
import stat
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    admin_token: str = field(repr=False)
    ingest_token: str = field(repr=False)
    encryption_key: str = field(repr=False)
    delivery_timeout: float = 10
    max_attempts: int = 5
    backoff_base_seconds: float = 5
    backoff_max_seconds: float = 300
    concurrency: int = 4
    retention_days: int = 30
    poll_seconds: float = 1
    host: str = '127.0.0.1'
    port: int = 8000

    @property
    def database_path(self) -> Path:
        return self.data_dir / 'herald.sqlite3'

    def __post_init__(self) -> None:
        if len(self.admin_token) < 32 or len(self.ingest_token) < 32:
            raise ValueError('tokens must contain at least 32 characters')
        if secrets.compare_digest(self.admin_token, self.ingest_token):
            raise ValueError('management and ingest tokens must differ')
        Fernet(self.encryption_key.encode())
        if any(not math.isfinite(value) or value <= 0 for value in (self.delivery_timeout, self.max_attempts,
               self.backoff_base_seconds, self.backoff_max_seconds, self.concurrency,
               self.retention_days, self.poll_seconds)):
            raise ValueError('worker and retention settings must be positive')


def _credentials(data_dir: Path) -> dict[str, str]:
    names = ('HERALD_ADMIN_TOKEN', 'HERALD_INGEST_TOKEN', 'HERALD_ENCRYPTION_KEY')
    provided = {name: os.environ.get(name, '') for name in names}
    if any(provided.values()):
        if not all(provided.values()):
            raise ValueError('provide all three HERALD credential variables or use credentials.env')
        return provided
    path = data_dir / 'credentials.env'
    if not path.exists():
        if (data_dir / 'herald.sqlite3').exists():
            raise ValueError('existing database requires its original credentials.env or explicit credential variables')
        values = (secrets.token_urlsafe(32), secrets.token_urlsafe(32), Fernet.generate_key().decode())
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, 'w') as f:
                for name, value in zip(names, values):
                    f.write(f'{name}={value}\n')
                f.flush()
                os.fsync(f.fileno())
            directory_fd = os.open(data_dir, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode) or path.stat().st_mode & 0o077:
        raise ValueError('credentials.env must be a private regular file (chmod 600)')
    result = dict(line.split('=', 1) for line in path.read_text().splitlines() if '=' in line)
    if not all(result.get(name) for name in names):
        raise ValueError('credentials.env is incomplete; preserve the encryption key for existing data')
    return result


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data_dir = Path(os.environ.get('HERALD_DATA_DIR', 'data')).resolve()
    data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if data_dir.stat().st_mode & 0o077:
        raise ValueError('HERALD_DATA_DIR must be private (chmod 700)')
    values = _credentials(data_dir)
    return Settings(
        data_dir=data_dir,
        admin_token=values['HERALD_ADMIN_TOKEN'],
        ingest_token=values['HERALD_INGEST_TOKEN'],
        encryption_key=values['HERALD_ENCRYPTION_KEY'],
        delivery_timeout=float(os.environ.get('HERALD_DELIVERY_TIMEOUT', '10')),
        max_attempts=int(os.environ.get('HERALD_MAX_ATTEMPTS', '5')),
        backoff_base_seconds=float(os.environ.get('HERALD_BACKOFF_BASE', '5')),
        backoff_max_seconds=float(os.environ.get('HERALD_BACKOFF_MAX', '300')),
        concurrency=int(os.environ.get('HERALD_CONCURRENCY', '4')),
        retention_days=int(os.environ.get('HERALD_RETENTION_DAYS', '30')),
        host=os.environ.get('HERALD_HOST', '127.0.0.1'),
        port=int(os.environ.get('HERALD_PORT', '8000')),
    )
