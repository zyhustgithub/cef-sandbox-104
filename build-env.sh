#!/bin/bash
# Source this file for the isolated Chromium 104 toolchain. No global Git changes.
# Resolve relative to this file, so sourcing it does not depend on the current directory.
if [ -n "${BASH_VERSION:-}" ]; then
  _cef_build_env_path="${BASH_SOURCE[0]}"
elif [ -n "${ZSH_VERSION:-}" ]; then
  _cef_build_env_path="${(%):-%x}"
else
  echo "Source build-env.sh from Bash or Zsh." >&2
  return 1
fi
_cef_workspace_dir="$(cd -- "$(dirname -- "$_cef_build_env_path")" && pwd)" || return 1
export PATH="$_cef_workspace_dir/depot_tools:$PATH"
unset _cef_build_env_path _cef_workspace_dir
export DEPOT_TOOLS_UPDATE=0
export GCLIENT_PY3=1
export http_proxy=http://127.0.0.1:7897
export https_proxy=http://127.0.0.1:7897
export HTTP_PROXY="$http_proxy"
export HTTPS_PROXY="$https_proxy"
export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0=http.proxy
export GIT_CONFIG_VALUE_0="$https_proxy"
export GN_DEFINES='is_official_build=false is_component_build=false symbol_level=0 use_thin_lto=false target_cpu="arm64" enable_nacl=false'
