#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
rm -rf edge-functions/_shared
mkdir -p edge-functions/_shared
cp ../shared/*.mjs edge-functions/_shared/
echo "shared modules copied"
