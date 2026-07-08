#!/usr/bin/env python3
"""Sync edge relay config: pull from backend, push to each edge's /admin/config."""

import argparse
import json
import os
import sys
import urllib.request


def _request(url: str, token: str, data: bytes | None = None) -> bytes:
    req = urllib.request.Request(
        url,
        data=data,
        method="POST" if data is not None else "GET",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", required=True)
    parser.add_argument("--edges", required=True, help="comma-separated edge base URLs")
    args = parser.parse_args()

    sync_token = os.environ.get("EDGE_SYNC_TOKEN", "")
    admin_token = os.environ.get("RELAY_ADMIN_TOKEN", "")
    if not sync_token or not admin_token:
        sys.exit("EDGE_SYNC_TOKEN and RELAY_ADMIN_TOKEN env vars are required")

    config = _request(f"{args.backend.rstrip('/')}/api/edge-config", sync_token)
    parsed = json.loads(config)
    for edge in [e.strip().rstrip("/") for e in args.edges.split(",") if e.strip()]:
        _request(f"{edge}/admin/config", admin_token, data=config)
        print(f"pushed version {parsed['version']} -> {edge}")


if __name__ == "__main__":
    main()
