#!/bin/bash
# Reentrant source preparation. Never deletes source, patches or build outputs.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_ROOT="${CEF_BUILD_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
mkdir -p "$BUILD_ROOT/state" "$BUILD_ROOT/logs" "$BUILD_ROOT/downloads"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"
DOWNLOAD_ARGS=(--directory "$BUILD_ROOT/downloads" --jobs "${CEF_DOWNLOAD_JOBS:-12}")
if [[ -n "${CEF_DOWNLOAD_PROXY:-}" ]]; then
  DOWNLOAD_ARGS+=(--proxy "$CEF_DOWNLOAD_PROXY")
fi
"$PYTHON_BIN" "$REPO_ROOT/scripts/download_chromium_104.py" "${DOWNLOAD_ARGS[@]}"
touch "$BUILD_ROOT/state/01-source-verified.done"
if [[ ! -f "$BUILD_ROOT/state/01b-archive-extracted.done" ]]; then
  mkdir -p "$BUILD_ROOT/source-staging"
  # Re-extract into an isolated staging tree on interruption, overwriting any
  # incomplete file. Never mix a partial extraction with patched build sources.
  tar -xf "$BUILD_ROOT/downloads/chromium-104.0.5112.102.tar.xz" \
    --strip-components=1 -C "$BUILD_ROOT/source-staging"
  touch "$BUILD_ROOT/state/01b-archive-extracted.done"
fi
if [[ ! -f "$BUILD_ROOT/state/02-source-extracted.done" ]]; then
  mkdir -p "$BUILD_ROOT/chromium/src"
  rsync -a --ignore-existing "$BUILD_ROOT/source-staging/" "$BUILD_ROOT/chromium/src/"
  touch "$BUILD_ROOT/state/02-source-extracted.done"
fi
printf 'Chromium sources ready: %s\n' "$BUILD_ROOT/chromium/src"
