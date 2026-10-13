#!/usr/bin/env python3
"""Verify and install the staged universal framework; never commits the bridge."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
NAME = 'Chromium Embedded Framework.framework'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge', type=Path, default=ROOT.parent / 'niimbot_cef_bridge')
    parser.add_argument('--source', type=Path, default=ROOT / 'out/universal-macos12' / NAME)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    sdk = args.bridge / 'niimbot_cef/3rd/cef/macos-arm64'
    manifest = json.loads((args.source.parent / 'merge-manifest.json').read_text())
    for name, expected in manifest['files'].items():
        if sha(args.source / name) != expected:
            raise RuntimeError('Staging checksum mismatch: ' + name)
    actual = {p.relative_to(args.source).as_posix() for p in args.source.rglob('*') if p.is_file()}
    if actual != manifest['files'].keys():
        raise RuntimeError('Staged file inventory differs from merge manifest')
    versions = {}
    for name in ['Chromium Embedded Framework', 'Libraries/libEGL.dylib',
                 'Libraries/libGLESv2.dylib', 'Libraries/libvk_swiftshader.dylib']:
        p = args.source / name
        archs = subprocess.check_output(['lipo', '-archs', str(p)], text=True).split()
        if set(archs) != {'arm64', 'x86_64'}:
            raise RuntimeError('Unexpected architectures in ' + name)
        details = subprocess.check_output(['xcrun', 'vtool', '-show-build', str(p)], text=True)
        minimums = re.findall(r'\bminos\s+([\d.]+)', details)
        if len(minimums) != 2 or any(tuple(map(int, v.split('.'))) > (12, 0, 0) for v in minimums):
            raise RuntimeError('Unsupported deployment version in ' + name + ': ' + details)
        versions[name] = details
    protected = json.loads((ROOT / 'state/sdk-replacement.json').read_text())['protected_files']

    def verify_protected():
        for name, expected in protected.items():
            if sha(sdk / name) != expected:
                raise RuntimeError('Protected SDK file changed: ' + name)

    verify_protected()
    if not args.apply:
        print('Validated staged runtime and', len(protected), 'protected SDK files; use --apply to install.')
        return
    backup = ROOT / 'backups' / time.strftime('sdk-before-universal-%Y%m%d-%H%M%S')
    backup.mkdir(parents=True, exist_ok=False)
    result = {'source': str(args.source), 'backup': str(backup),
              'protected_files_verified': len(protected), 'build_versions': versions, 'configurations': {}}
    for config in ('Debug', 'Release'):
        target = sdk / config / NAME
        staging = target.with_name(NAME + '.universal-staging')
        if staging.exists():
            raise RuntimeError('Previous staging directory exists: ' + str(staging))
        shutil.copytree(args.source, staging)
        # Keep the original distribution policy: omit generated pseudolocales.
        for locale in ('ar_XB.lproj', 'en_XA.lproj'):
            p = staging / 'Resources' / locale
            if p.exists():
                shutil.rmtree(p)
        saved = backup / config / NAME
        saved.parent.mkdir(parents=True)
        shutil.copytree(target, saved, symlinks=True)
        old = target.with_name(NAME + '.previous-runtime')
        if old.exists():
            raise RuntimeError('Previous swap directory exists: ' + str(old))
        target.rename(old)
        try:
            staging.rename(target)
        except BaseException:
            old.rename(target)
            raise
        shutil.rmtree(old)
        result['configurations'][config] = {
            p.relative_to(target).as_posix(): sha(p) for p in target.rglob('*') if p.is_file()}
        (backup / 'replacement-progress.json').write_text(json.dumps(result, indent=2) + '\n')
    verify_protected()
    (ROOT / 'records/universal-sdk-replacement.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Replaced Debug and Release frameworks; originals:', backup)


if __name__ == '__main__':
    main()
