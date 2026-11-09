#!/usr/bin/env bash
# Consistent online SQLite backup; never copy a live database without its WAL.
set -euo pipefail
export HERALD_DATA_DIR="${HERALD_DATA_DIR:-./data}"
export BACKUP_DIR="${BACKUP_DIR:-./backups}"
python3 - <<'PYBACKUP'
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

source = Path(os.environ['HERALD_DATA_DIR']).resolve()
root = Path(os.environ['BACKUP_DIR']).resolve()
database = source / 'herald.sqlite3'
if not database.is_file():
    raise SystemExit('Source SQLite database does not exist')
os.umask(0o077)
root.mkdir(mode=0o700, parents=True, exist_ok=True)
if root.stat().st_mode & 0o077:
    raise SystemExit('Backup directory must have owner-only permissions (chmod 700)')
target = root / datetime.now(timezone.utc).strftime('herald-%Y%m%dT%H%M%S.%fZ')
target.mkdir(mode=0o700)
try:
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as src:
        with sqlite3.connect(target / 'herald.sqlite3') as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Backup integrity check failed')
    credentials = source / 'credentials.env'
    environment_credentials = any(os.environ.get(name) for name in (
        'HERALD_ADMIN_TOKEN', 'HERALD_INGEST_TOKEN', 'HERALD_ENCRYPTION_KEY'))
    if credentials.is_file() and not environment_credentials:
        if credentials.is_symlink() or credentials.stat().st_mode & 0o077:
            raise RuntimeError('Source credential file must be private')
        shutil.copyfile(credentials, target / 'credentials.env')
        (target / 'credentials.env').chmod(0o600)
    else:
        print('Environment credentials are not included; preserve them separately.')
except BaseException:
    shutil.rmtree(target)
    raise
print(f'Backup written: {target}')
PYBACKUP
