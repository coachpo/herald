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
    failures: list[tuple[str, str]] = []
    for edge in [e.strip().rstrip("/") for e in args.edges.split(",") if e.strip()]:
        try:
            _request(f"{edge}/admin/config", admin_token, data=config)
            print(f"pushed version {parsed['version']} -> {edge}")
        except Exception as exc:  # noqa: BLE001
            failures.append((edge, str(exc)))
            print(f"FAILED -> {edge}: {exc}", file=sys.stderr)
    if failures:
        sys.exit(
            f"config push failed for {len(failures)} edge(s). "
            "Skewed edges 401 new endpoints (permanent dead-letter) - fix and re-run."
        )


if __name__ == "__main__":
    main()
