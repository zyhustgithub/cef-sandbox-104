# CEF 104 macOS build workspace

Owns CEF/Chromium download scripts, source baselines, official/local patch history,
macOS toolchain configuration and build verification records. The bridge repository
only consumes the built runtime and retains application integration code.

## Repositories

- This root repository tracks build tooling, patches and records only.
- `chromium/src`: Chromium archive baseline and official/local patch commits.
- `chromium/src/cef` (`cef` symlink): original CEF and local macOS IPC patch.
- `chromium/src/v8`: original V8 and official CEF adaptation patch.
- Source repositories remain independent; their histories were not rewritten.

`records/previous-build-notes.md` preserves the original detailed build history.
Paths mentioning the bridge repository's build scripts/patches in that historical
record refer to their old locations. Current copies are `scripts/` and `patches/` here.
`records/versions.json` pins the original inputs; `records/framework-verification.json`
records the compiled source revisions. Downloads, outputs and mutable state stay
local and ignored by Git. No remote has been configured for this root repository.

## Continue this configured checkout

```bash
CEF_DOWNLOAD_PROXY=http://127.0.0.1:7897 scripts/prepare_chromium_104.sh
source build-env.sh
python3 scripts/build_cef104_framework.py --jobs 8
```

These are continuation tools for the existing staged checkout, not a complete
one-command bootstrap for an empty machine. See the historical records for pinned
platform dependencies and prerequisites. `configure-local.py` retains the local
configuration helper; later source fixes are recorded as separate Git commits and
patch files, not all replayed by that helper.

The bridge SDK stores the runtime in its original flat distribution layout.
Only the app bundle is normalized into the macOS `Versions/A` structure.
The two pseudolocales `ar_XB` and `en_XA` are omitted from the distribution;
real locales, ICU, V8 snapshots, resource packs and GPU libraries are retained.

## Universal CEF for muses_flutter (2026-10-13)

The final scope preserves muses_flutter's current macOS 12.0 deployment target
and existing Flutter/business dependency versions. Earlier arm64 11.0 / Intel
10.13 configuration records are superseded; those experimental builds stopped.
The dependency audit is diagnostic only and does not change the host's requirements.

- arm64 reuses `out/Release_GN_arm64` (12.0).
- Intel uses `out/Release_GN_x64_macos12` (12.0).
- Both use the same CEF/Chromium/V8 revisions recorded in
  `records/universal-macos12.json`.
- Default V8 snapshots now have architecture-specific bundle names; unbundled
  snapshot generators retain V8's original filename.
- `scripts/prepare_sdk_overlay.py` creates a private SDK header mapping for old
  Clang's lack of Intel `_Float16`; it does not edit the installed SDK.

```bash
source build-env.sh
python3 scripts/prepare_sdk_overlay.py
# args.gn copies are recorded in records/; gn gen must precede each build.
python3 scripts/build_cef104_framework.py --out Release_GN_arm64 --jobs 8
python3 scripts/build_cef104_framework.py --out Release_GN_x64_macos12 --jobs 8
# After BOTH builds succeed:
python3 scripts/merge_universal_framework.py
```

Each output has its own lock, append-only log and state file, and Ninja resumes
completed objects without clearing the output directory. The default arm64 output
retains its historical log/state filenames. The merge script rejects conflicting
shared resources and keeps both architecture-specific snapshot sets. Merging is
staging only: bridge SDK replacement and host build/runtime verification follow
separately. CEF runtime replacements in the bridge remain for the user to commit.
