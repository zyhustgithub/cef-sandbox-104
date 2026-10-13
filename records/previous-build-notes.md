# niimbot_cef_bridge_example

Windows example application for `niimbot_cef_bridge`.

```bash
flutter pub get
flutter build windows --debug
```

## macOS App Sandbox example

From the repository root, run `scripts/build_macos_sandbox_example.sh`.
The default is Debug; pass `release` for an AOT build. Release requires a Flutter
SDK whose snapshot compiler can run on this Mac (older SDKs may need Rosetta).
Set `FLUTTER_BIN` to select a different SDK.

The example uses company team `YSP53GL6F6` and the separate bundle identifier
`com.niimbot.cefbridge.example`. A matching Apple Development certificate is
required. The current vendored CEF SDK supports arm64 only.

The host enables App Sandbox and hardened runtime. Embedded CEF helpers are
signed with the host identity and inherit its App Sandbox. Chromium's own
sandbox remains disabled by default; macOS V8 uses `--jitless`, matching the
observed WPS configuration. Jitless can affect JS performance and WebAssembly.
CEF data and logs use Foundation-resolved directories inside the app container.
The host permits JIT/unsigned executable memory, network client/server,
user-selected files, app-scoped bookmarks and printing. The application group `YSP53GL6F6.com.niimbot.cefbridge.example` also supplies
Chromium's `--base-bundle-id`. This requires a CEF build that implements the
switch (the installed WPS does; our stock CEF 104 does not).
Apple Events, login services and WPS filesystem exceptions are not copied.

Output: `build/macos/Build/Products/Debug/example.app` (or `Release/example.app`).
This is a local development build, not an App Store submission archive.

### Current verification result

On 2026-10-13 the patched Release framework was installed into both the SDK's
Debug and Release framework directories. Debug refers to the Flutter host build;
the CEF runtime in both configurations is the new Release build. The 625 existing
header/wrapper files were checked by SHA-256 and remain unchanged. Windows SDK
files were not modified.

The company-signed arm64 Debug example builds and passes nested signature
validation. Its main, GPU, utility and renderer processes were observed running, and
remote page JavaScript executes. The previous MachPortRendezvous failure is
resolved. The first run exposed a macOS App Sandbox process-role assertion;
Chromium commit `65bee5592d` fixes that check only on macOS without disabling the
App Sandbox. The incremental rebuild and subsequent startup pass. Cache and
unsupported-media warnings remain; UI automation could not bind the window, so
this is process/log verification, not a complete visual or JS API regression test.

Original frameworks are backed up at
`/Users/zengyong/work/cef-sandbox-104/backups/sdk-before-replacement-20261013-090058`.

The SDK in this repository contains headers/wrappers and prebuilt Chromium, not
the full source needed to rebuild Chromium. `build_cef_mac_official.sh` rebuilds
the SDK sample applications, not the CEF framework.

### Source patch application (2026-10-12)

The patch has now been applied to a separate local checkout at
`/Users/zengyong/work/cef-sandbox-104/cef`, pinned to
`4180781f5481a4f83a342dbf26e7dc6ce0a81ce3` (the exact version of the bundled SDK).
`git diff --check` passes. Both Alloy and Chrome startup call
`OnBeforeCommandLineProcessing` before `util_mac::BasicStartupComplete`, so the
host supplies the override before CEF reads the base bundle ID.

The matching Chromium source and build tools have now been downloaded through
the configured proxy. All 79 official CEF patches applied successfully and the
arm64 Release Ninja project was generated. Framework compilation succeeded on
2026-10-12: Ninja completed all 46,360 remaining steps with exit code 0. A second
Ninja check reports no work to do. All 70 declared framework outputs exist; the
main library and three bundled dylibs are arm64. On 2026-10-13 the macOS salt
assertion fix was incrementally rebuilt and installed; see verification above.

Built framework:
`/Users/zengyong/work/cef-sandbox-104/chromium/src/out/Release_GN_arm64/Chromium Embedded Framework.framework`
(390 MiB). Its custom branch version string is
`104.0.0-cef104-app-sandbox.2+gdea6f60+chromium-104.0.5112.102`.
The exported CEF API hashes match the existing prebuilt SDK. The main library
contains `base-bundle-id`; SHA-256:
`ff057679e5ad42a890fb7991f59a2b06b6d646ef2e35379c22f7f93d307b6887`.
Build status and output verification are recorded under the build root in
`state/framework-build.json` and `state/framework-verification.json`.

### Resumable source preparation

The source host is reachable using the system-configured HTTP proxy. Source
preparation now uses Google's official Chromium 104.0.5112.102 archive instead
of a large Git pack. It downloads independent 32 MiB ranges, resumes partial
ranges, validates Content-Range and the final official MD5, and keeps all parts.

From the repository root:

```bash
CEF_DOWNLOAD_PROXY=http://127.0.0.1:7897 scripts/prepare_chromium_104.sh
```

Override `CEF_BUILD_ROOT` to change the isolated build directory. The default is
`/Users/zengyong/work/cef-sandbox-104`. Stage markers live in `state/`, downloads
in `downloads/`, logs in `logs/`, and build outputs will remain in
`chromium/src/out/`. Do not delete these directories on a failed attempt.
The CEF and depot_tools revisions are recorded in `state/versions.json`.
Source preparation can be rerun after interruption; later compilation should
resume with Ninja in the same output directory rather than cleaning it.

### Source history for review

All source repositories use branch `codex/cef104-app-sandbox` under
`/Users/zengyong/work/cef-sandbox-104/chromium/src`.

| Repository | Commit | Purpose |
| --- | --- | --- |
| `cef` | `4180781` | Original CEF 104.4.26 upstream commit, tag `cef-104.4.26-upstream` |
| Chromium root | `e76c2de` | Pristine official source archive snapshot (not an upstream Git commit) |
| `v8` | `c84d9f3` | Pristine V8 archive snapshot |
| Chromium root | `24c1dc6` | Official CEF Chromium adaptation patches |
| `v8` | `74d856b` | Official CEF V8 adaptation patch |
| `cef` | `dea6f60` | Our `--base-bundle-id` implementation: one file, eight added lines |
| Chromium root | `95468c7` | Reference to our patched CEF commit |
| Chromium root | `c3b2095` | Our opt-in Clang 15 / newer macOS SDK compatibility adjustment |
| Chromium root | `749e171` | Official DEPS-pinned macOS Google Toolbox dependency |
| Chromium root | `357784a5ca` | Official DEPS-pinned macOS arm64 esbuild tool |
| Chromium root | `f26066b` | Our deployment-version macro compatibility fix for Clang 15 |
| Chromium root | `673aa33252` | Our explicit SDK library search paths for legacy LLD |
| Chromium root | `65bee5592d` | Our macOS App Sandbox browser-role check for pseudonymization salt |

Review our functionality change directly:

```bash
git -C /Users/zengyong/work/cef-sandbox-104/chromium/src/cef show dea6f60
git -C /Users/zengyong/work/cef-sandbox-104/chromium/src show c3b2095
```

Local source modifications are also exported as `git format-patch` files in
`niimbot_cef/patches/`. Downloaded platform dependencies are recorded separately
from local source modifications. Subsequent build fixes should follow the same
rule and must not be folded into the pristine or official-patch commits.

Resume compilation after a stopped attempt (do not start a second simultaneous
build in the same output directory):

```bash
python3 scripts/build_cef104_framework.py --jobs 8
```

The wrapper appends to `logs/libcef-build.log`, records success/failure in
`state/framework-build.json`, and only creates `07-framework-build.done` after
Ninja succeeds. Source/download stages and existing object files are retained.
