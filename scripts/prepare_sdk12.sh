#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARCHIVE="${ROOT}/downloads/MacOSX12.3.sdk.tar.xz"
mkdir -p "${ROOT}/downloads" "${ROOT}/sdks"
EXPECTED=3abd261ceb483c44295a6623fdffe5d44fc4ac2c872526576ec5ab5ad0f6e26c
if [[ ! -f "$ARCHIVE" ]] || [[ "$(shasum -a 256 "$ARCHIVE" | cut -d ' ' -f 1)" != "$EXPECTED" ]]; then
  curl -fL --retry 5 --retry-delay 3 -C - -o "$ARCHIVE" \
    https://github.com/joseluisq/macosx-sdks/releases/download/12.3/MacOSX12.3.sdk.tar.xz
fi
[[ "$(shasum -a 256 "$ARCHIVE" | cut -d ' ' -f 1)" == "$EXPECTED" ]]
if [[ ! -f "${ROOT}/state/sdk12.3.done" ]]; then
  tar -xf "$ARCHIVE" -C "${ROOT}/sdks"
  touch "${ROOT}/state/sdk12.3.done"
fi
