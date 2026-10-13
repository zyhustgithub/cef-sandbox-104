#!/bin/bash
# Source this file for the isolated Chromium 104 toolchain. No global Git changes.
export PATH="/Users/zengyong/work/cef-sandbox-104/depot_tools:$PATH"
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
