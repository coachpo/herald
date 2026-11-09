import argparse

import uvicorn

from .config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description='Run Herald API, UI and durable delivery worker')
    parser.add_argument('command', nargs='?', choices=['serve', 'init'], default='serve')
    args = parser.parse_args()
    settings = get_settings()
    if args.command == 'init':
        print(f'Configuration initialized in {settings.data_dir}; keep credentials.env private.')
        return
    uvicorn.run('backend.main:app', host=settings.host, port=settings.port, workers=1,
                proxy_headers=False, access_log=False)
