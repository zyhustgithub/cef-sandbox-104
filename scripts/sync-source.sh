#!/usr/bin/env bash
# After cloning this workspace, run: bash scripts/sync-source.sh
# For a new checkout: git clone --recurse-submodules <workspace-url>
# Dependencies follow commits recorded by their parents, never remote branch tips.
# depot_tools source is included; downloaded toolchain/runtime caches are not.
set -euo pipefail

workspace_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$workspace_dir"
if ! git lfs version >/dev/null 2>&1; then
  echo "Git LFS is required. Install Git LFS, then run this script again." >&2
  exit 1
fi

git submodule sync --recursive
git submodule update --init --recursive
git -C chromium/src lfs install --local
git -C chromium/src lfs pull

# These settings are local to this checkout; each new clone must run this script.
git config --local submodule.recurse true
git config --local fetch.recurseSubmodules on-demand
git config --local push.recurseSubmodules check

if [[ ! -e chromium/.gclient ]]; then
  cp chromium/src/gclient.cef104 chromium/.gclient
elif ! cmp -s chromium/src/gclient.cef104 chromium/.gclient; then
  echo "Existing chromium/.gclient was preserved; compare it with chromium/src/gclient.cef104."
fi

echo "Source dependencies are synchronized to the recorded commits."
echo "Future git pull operations in this checkout will update submodules recursively."
echo "depot_tools source is included; use DEPOT_TOOLS_UPDATE=0 when running it to retain the pinned revision."
echo "macOS SDK, Clang/GN, CIPD/Python caches and build outputs require separate setup."
