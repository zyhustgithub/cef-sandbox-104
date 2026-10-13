#!/usr/bin/env python3
"""Record pristine archive snapshots before applying CEF's official patches."""
import argparse
import json
from pathlib import Path
import subprocess


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build_root', type=Path)
    args = parser.parse_args()
    root = args.build_root.resolve()
    src = root / 'chromium/src'
    staged = root / 'source-staging'
    if not (root / 'state/02-source-extracted.done').exists():
        raise SystemExit('Verified source extraction must finish before baseline commits')
    version = json.loads((root / 'state/versions.json').read_text())
    for relative, label, tag in [
        ('v8', 'V8', 'v8-chromium104-official-source'),
        ('', 'Chromium', 'chromium104-official-source'),
    ]:
        repo = src / relative
        origin = staged / relative
        marker = root / 'state' / ('03-' + label.lower() + '-baseline.done')
        if marker.exists():
            continue
        if (repo / '.git').exists() and subprocess.run(
                ['git', '-C', str(repo), 'rev-parse', '--verify', 'refs/tags/' + tag],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            marker.touch()
            continue
        if not (repo / '.git').exists():
            git(repo, 'init', '-b', 'codex/cef104-app-sandbox')
        else:
            has_head = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--verify', 'HEAD'],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
            if has_head:
                raise SystemExit('Unexpected existing HEAD; inspect before creating baseline: ' + str(repo))
            git(repo, 'symbolic-ref', 'HEAD', 'refs/heads/codex/cef104-app-sandbox')
        names = []
        for path in origin.rglob('*'):
            if not path.is_file() and not path.is_symlink():
                continue
            name = path.relative_to(origin).as_posix()
            if not relative and (name.startswith('v8/') or name.startswith('cef/')):
                continue
            if '.git' in Path(name).parts:
                continue
            names.append(name)
        pathlist = root / 'state' / (label.lower() + '-baseline.paths')
        pathlist.write_bytes(b''.join(name.encode() + b'\0' for name in sorted(names)))
        if relative:
            git(repo, 'add', '-f', '--all')
        else:
            # A pathspec for every file is quadratic on a Chromium-sized tree.
            # Only these local toolchain/checkout paths are outside the archive.
            git(repo, 'add', '-f', '--all', '--', '.',
                ':(exclude)cef', ':(exclude)v8', ':(exclude)out',
                ':(exclude)third_party/llvm-build/Release+Asserts',
                ':(exclude)buildtools/mac/gn', ':(exclude)buildtools/mac/.cipd',
                ':(exclude)third_party/node/mac/node-darwin-arm64')
        if not relative:
            (repo / '.gitmodules').write_text(
                '[submodule "cef"]\n\tpath = cef\n\turl = https://github.com/chromiumembedded/cef.git\n'
                '[submodule "v8"]\n\tpath = v8\n\turl = https://chromium.googlesource.com/v8/v8.git\n')
            (repo / 'CEF_SOURCE_ORIGIN.json').write_text(json.dumps(version, indent=2) + '\n')
            git(repo, 'add', '-f', 'v8', 'cef', '.gitmodules', 'CEF_SOURCE_ORIGIN.json')
        message = (f'Import pristine {label} source from Chromium {version["chromium_version"]} official archive\n\n'
                   f'Source archive MD5: {version["source_archive_md5"]}\n'
                   f'Chromium upstream revision: {version["chromium_commit"]}\n'
                   'This is an archive snapshot, not a reconstructed upstream Git commit.\n'
                   'No CEF adaptation patches or local sandbox changes are included.\n')
        git(repo, 'commit', '--quiet', '-m', message)
        git(repo, 'tag', tag)
        marker.touch()


if __name__ == '__main__':
    main()
