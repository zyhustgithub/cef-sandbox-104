#!/usr/bin/env python3
"""Merge matching CEF builds without selecting one architecture's shared resources."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
NAME = 'Chromium Embedded Framework.framework'
MACH_FILES = {
    'Chromium Embedded Framework',
    'Libraries/libEGL.dylib',
    'Libraries/libGLESv2.dylib',
    'Libraries/libvk_swiftshader.dylib',
}
SNAPSHOTS = {
    'arm64': {'Resources/snapshot_blob.arm64.bin', 'Resources/v8_context_snapshot.arm64.bin'},
    'x86_64': {'Resources/snapshot_blob.x64.bin', 'Resources/v8_context_snapshot.x86_64.bin'},
}
# Ninja does not remove outputs from obsolete bundle rules.
OBSOLETE = {'Resources/snapshot_blob.bin'}


def inventory(path):
    return {p.relative_to(path).as_posix(): p for p in path.rglob('*') if p.is_file()}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm64', type=Path, default=ROOT / 'chromium/src/out/Release_GN_arm64' / NAME)
    parser.add_argument('--x64', type=Path, default=ROOT / 'chromium/src/out/Release_GN_x64_macos12' / NAME)
    parser.add_argument('--output', type=Path, default=ROOT / 'out/universal-macos12' / NAME)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; select a fresh staging directory')
    roots = {arch: path / 'Versions/A' if (path / 'Versions/A').is_dir() else path
             for arch, path in [('arm64', args.arm64), ('x86_64', args.x64)]}
    items = {arch: inventory(path) for arch, path in roots.items()}
    all_snapshots = set.union(*SNAPSHOTS.values())
    common = {}
    for arch, files in items.items():
        missing = (MACH_FILES | SNAPSHOTS[arch]) - files.keys()
        if missing:
            raise RuntimeError(f'{arch}: missing {sorted(missing)}')
        common[arch] = files.keys() - all_snapshots - MACH_FILES - OBSOLETE - {'Resources/Info.plist'}
    if common['arm64'] != common['x86_64']:
        raise RuntimeError('Shared file sets differ: ' + str(common['arm64'] ^ common['x86_64']))
    for name in common['arm64']:
        if sha(items['arm64'][name]) != sha(items['x86_64'][name]):
            raise RuntimeError('Shared resource differs: ' + name)
    plists = [plistlib.loads(items[arch]['Resources/Info.plist'].read_bytes()) for arch in roots]
    if plists[0] != plists[1]:
        raise RuntimeError('Framework Info.plist values differ')
    # Complete validation precedes any output. Produce the consumer's flat layout.
    args.output.mkdir(parents=True)
    for name in common['arm64'] | {'Resources/Info.plist'}:
        dest = args.output / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(items['arm64'][name], dest)
    for arch, names in SNAPSHOTS.items():
        for name in names:
            shutil.copy2(items[arch][name], args.output / name)
    for name in sorted(MACH_FILES):
        dest = args.output / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        for arch in roots:
            subprocess.run(['lipo', '-verify_arch', arch, str(items[arch][name])], check=True)
        subprocess.run(['lipo', '-create', *(str(items[a][name]) for a in roots), '-output', str(dest)], check=True)
        subprocess.run(['lipo', '-verify_arch', 'arm64', 'x86_64', str(dest)], check=True)
    record = {'sources': {a: str(p) for a, p in roots.items()}, 'output': str(args.output),
              'files': {n: sha(p) for n, p in sorted(inventory(args.output).items())}}
    (args.output.parent / 'merge-manifest.json').write_text(json.dumps(record, indent=2) + '\n')
    print(args.output)


if __name__ == '__main__':
    main()
