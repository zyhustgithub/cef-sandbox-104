#!/usr/bin/env python3
"""Download the pinned official Chromium source with resumable validated ranges."""
import argparse
import concurrent.futures
import hashlib
import fcntl
import json
from pathlib import Path
import time
import urllib.request

URL = 'https://commondatastorage.googleapis.com/chromium-browser-official/chromium-104.0.5112.102.tar.xz'
SIZE = 1510037412
MD5 = '37e0c3fecfcc0b92ffe1d617afea6b3d'
CHUNK = 32 * 1024 * 1024


def digest(path):
    h = hashlib.md5()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    global URL, SIZE, MD5, CHUNK
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--proxy')
    parser.add_argument('--jobs', type=int, default=6)
    parser.add_argument('--url', default=URL)
    parser.add_argument('--size', type=int, default=SIZE)
    parser.add_argument('--md5', default=MD5)
    parser.add_argument('--chunk-mib', type=int, default=32)
    args = parser.parse_args()
    URL, SIZE, MD5, CHUNK = args.url, args.size, args.md5, args.chunk_mib * 1024 * 1024
    args.directory.mkdir(parents=True, exist_ok=True)
    # Keep this handle alive until main returns; concurrent resumptions must not
    # append to the same partial files.
    lock = (args.directory / '.chromium104-download.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('Another Chromium source download is already active')
    archive = args.directory / URL.rsplit('/', 1)[1]
    if archive.exists() and archive.stat().st_size == SIZE and digest(archive) == MD5:
        print('Archive already verified:', archive, flush=True)
        return
    parts = args.directory / (archive.name + '.parts')
    parts.mkdir(exist_ok=True)
    manifest = {'url': URL, 'size': SIZE, 'md5': MD5, 'chunk_size': CHUNK}
    metadata = parts / 'manifest.json'
    if metadata.exists() and json.loads(metadata.read_text()) != manifest:
        raise RuntimeError('Existing download manifest does not match pinned source')
    metadata.write_text(json.dumps(manifest, indent=2) + '\n')

    def download(index):
        first = index * CHUNK
        last = min(first + CHUNK, SIZE) - 1
        length = last - first + 1
        part = parts / ('%04d.part' % index)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler(
            {'http': args.proxy, 'https': args.proxy}) if args.proxy
            else urllib.request.ProxyHandler())
        for attempt in range(12):
            offset = part.stat().st_size if part.exists() else 0
            if offset == length:
                return index
            if offset > length:
                raise RuntimeError('Oversized part: ' + str(part))
            try:
                req = urllib.request.Request(URL, headers={
                    'Range': 'bytes=%d-%d' % (first + offset, last),
                    'If-Match': '"' + MD5 + '"',
                })
                with opener.open(req, timeout=45) as response:
                    expected = 'bytes %d-%d/%d' % (first + offset, last, SIZE)
                    if response.status != 206 or response.headers.get('Content-Range') != expected:
                        raise RuntimeError('Server did not honor the requested range')
                    with part.open('ab') as output:
                        remaining = length - offset
                        while remaining:
                            data = response.read(min(1024 * 1024, remaining))
                            if not data:
                                raise OSError('Interrupted range transfer')
                            output.write(data)
                            output.flush()
                            remaining -= len(data)
                print('Completed part %d/%d' % (index + 1, (SIZE + CHUNK - 1) // CHUNK), flush=True)
                return index
            except Exception as exc:
                print('Retry part %d (%d/12): %s' % (index, attempt + 1, exc), flush=True)
                if attempt == 11:
                    raise
                time.sleep(min(2 ** attempt, 30))

    saved = sum(p.stat().st_size for p in parts.glob('*.part'))
    print('Resuming %d / %d bytes already saved' % (saved, SIZE), flush=True)
    count = (SIZE + CHUNK - 1) // CHUNK
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        list(pool.map(download, range(count)))
    assembled = archive.with_suffix(archive.suffix + '.assembling')
    with assembled.open('wb') as output:
        for index in range(count):
            with (parts / ('%04d.part' % index)).open('rb') as source:
                for block in iter(lambda: source.read(4 * 1024 * 1024), b''):
                    output.write(block)
    if assembled.stat().st_size != SIZE or digest(assembled) != MD5:
        raise RuntimeError('Source archive checksum mismatch; parts retained for diagnosis')
    assembled.replace(archive)
    print('Verified official archive:', archive, flush=True)


if __name__ == '__main__':
    main()
