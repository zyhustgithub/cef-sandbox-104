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
