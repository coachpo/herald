#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_PATH = REPO_ROOT / "VERSION"
BACKEND_PYPROJECT_PATH = REPO_ROOT / "backend/pyproject.toml"
FRONTEND_PACKAGE_PATH = REPO_ROOT / "frontend/package.json"
EDGE_PACKAGE_PATH = REPO_ROOT / "edge/package.json"
EDGE_LOCKFILE_PATH = REPO_ROOT / "edge/package-lock.json"

BACKEND_VERSION_RE = re.compile(r'(?m)^(version = )"([^"]+)"$')


def read_root_version() -> str:
    version = VERSION_PATH.read_text(encoding="utf-8").strip()
    if not version:
        raise SystemExit("VERSION is empty")
    return version


def relative_path(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def sync_backend_pyproject(version: str, check: bool) -> bool:
    text = BACKEND_PYPROJECT_PATH.read_text(encoding="utf-8")
    match = BACKEND_VERSION_RE.search(text)
    if match is None:
        raise SystemExit(
            f"Could not find project version in {relative_path(BACKEND_PYPROJECT_PATH)}"
        )

    current = match.group(2)
    if current == version:
        return False

    if check:
        print(
            f"Mismatch: {relative_path(BACKEND_PYPROJECT_PATH)} has {current}, expected {version}"
        )
        return True

    updated = BACKEND_VERSION_RE.sub(
        lambda m: f'{m.group(1)}"{version}"',
        text,
        count=1,
    )
    BACKEND_PYPROJECT_PATH.write_text(updated, encoding="utf-8")
    print(f"Updated {relative_path(BACKEND_PYPROJECT_PATH)}: {current} -> {version}")
    return True


def sync_package_json(path: Path, version: str, check: bool) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    current = data.get("version")
    if not isinstance(current, str):
        raise SystemExit(f"Missing string version in {relative_path(path)}")

    if current == version:
        return False

    if check:
        print(f"Mismatch: {relative_path(path)} has {current}, expected {version}")
        return True

    data["version"] = version
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {relative_path(path)}: {current} -> {version}")
    return True


def sync_edge_lockfile(version: str, check: bool) -> bool:
    data = json.loads(EDGE_LOCKFILE_PATH.read_text(encoding="utf-8"))
    package_info = data.get("packages")
    if not isinstance(package_info, dict):
        raise SystemExit(
            f"Missing packages object in {relative_path(EDGE_LOCKFILE_PATH)}"
        )

    root_package = package_info.get("")
    if not isinstance(root_package, dict):
        raise SystemExit(
            f"Missing root package entry in {relative_path(EDGE_LOCKFILE_PATH)}"
        )

    current_top_level = data.get("version")
    current_root_package = root_package.get("version")
    if not isinstance(current_top_level, str) or not isinstance(
        current_root_package, str
    ):
        raise SystemExit(
            f"Missing version fields in {relative_path(EDGE_LOCKFILE_PATH)}"
        )

    if current_top_level == version and current_root_package == version:
        return False

    if check:
        print(
            "Mismatch: "
            f"{relative_path(EDGE_LOCKFILE_PATH)} has top-level {current_top_level} "
            f"and packages[''] {current_root_package}, expected {version}"
        )
        return True

    data["version"] = version
    root_package["version"] = version
    EDGE_LOCKFILE_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(
        "Updated "
        f"{relative_path(EDGE_LOCKFILE_PATH)}: "
        f"top-level {current_top_level} -> {version}, "
        f"packages[''] {current_root_package} -> {version}"
    )
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sync package metadata versions from the repo root VERSION file."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero instead of rewriting files when versions are out of sync.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    version = read_root_version()

    changed = [
        sync_backend_pyproject(version, check=args.check),
        sync_package_json(FRONTEND_PACKAGE_PATH, version, check=args.check),
        sync_package_json(EDGE_PACKAGE_PATH, version, check=args.check),
        sync_edge_lockfile(version, check=args.check),
    ]

    if args.check:
        if any(changed):
            return 1
        print(f"Aligned version: {version}")
        return 0

    if any(changed):
        print(f"Synchronized version metadata to {version}")
    else:
        print(f"All managed version files already match {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
