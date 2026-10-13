#!/bin/bash
set -euo pipefail
BUILD_ROOT="${CEF_BUILD_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
SRC="$BUILD_ROOT/chromium/src"
source "$BUILD_ROOT/build-env.sh"
[[ -f "$BUILD_ROOT/state/03-chromium-baseline.done" ]]
if [[ ! -f "$BUILD_ROOT/state/04-official-patches.done" ]]; then
  cd "$SRC/cef"
  python3 tools/patcher.py
  if ! git -C "$SRC/v8" diff --quiet; then
    git -C "$SRC/v8" add -u
    git -C "$SRC/v8" commit -m 'Apply official CEF 4180781 V8 adaptation patches'
  fi
  if ! git -C "$SRC" diff --quiet --ignore-submodules=dirty; then
    git -C "$SRC" add -u
    git -C "$SRC" commit -m 'Apply official CEF 4180781 Chromium adaptation patches'
  fi
  touch "$BUILD_ROOT/state/04-official-patches.done"
fi
if [[ ! -f "$BUILD_ROOT/state/05-local-sandbox-patch.done" ]]; then
  if ! git -C "$SRC/cef" diff --quiet -- libcef/common/util_mac.mm; then
    git -C "$SRC/cef" add libcef/common/util_mac.mm
    git -C "$SRC/cef" commit -m 'Support an application-group base bundle ID for macOS sandbox IPC'
  fi
  if ! git -C "$SRC" diff --quiet -- cef; then
    git -C "$SRC" add cef
    git -C "$SRC" commit -m 'Use CEF with the local application-group IPC patch'
  fi
  touch "$BUILD_ROOT/state/05-local-sandbox-patch.done"
fi
