#!/usr/bin/env python3
"""Resume the configured CEF framework build without clearing Ninja outputs."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(os.environ.get(
        'CEF_BUILD_ROOT', str(Path(__file__).resolve().parents[1]))))
    parser.add_argument('--jobs', type=int, default=8)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    root = args.root.resolve()
    state = root / 'state'
    if not (state / '06-configure.done').exists():
        parser.error('Configure stage must complete first')
    with (state / 'framework-build.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('Another build wrapper is already running')
        env = os.environ.copy()
        # Apple's /usr/bin/python3 launcher injects host search paths, including
        # /usr/local/lib even when that directory does not exist. Chromium uses
        # its configured SDK and must not inherit these launcher additions.
        for name in ('LIBRARY_PATH', 'CPATH', 'SDKROOT'):
            env.pop(name, None)
        env['PATH'] = str(root / 'depot_tools') + os.pathsep + env['PATH']
        env['DEPOT_TOOLS_UPDATE'] = '0'
        env['GCLIENT_PY3'] = '1'
        log_path = root / 'logs' / 'libcef-build.log'
        status_path = state / 'framework-build.json'
        status = {'state': 'running', 'started_at': time.time(),
                  'log': str(log_path), 'jobs': args.jobs}

        def save():
            tmp = status_path.with_suffix('.tmp')
            tmp.write_text(json.dumps(status, indent=2) + '\n')
            tmp.replace(status_path)

        save()
        print('Resuming framework build; log: ' + str(log_path), flush=True)
        try:
            with log_path.open('a') as log:
                log.write('\n=== Resumed build at ' + time.ctime() + ' ===\n')
                log.flush()
                code = subprocess.call([
                    str(root / 'depot_tools' / 'ninja'), '-C',
                    'out/Release_GN_arm64', 'cef_framework', '-j', str(args.jobs)
                ], cwd=root / 'chromium' / 'src', env=env,
                   stdout=log, stderr=subprocess.STDOUT)
        except BaseException:
            status.update(state='interrupted', finished_at=time.time())
            save()
            raise
        status.update(state='complete' if code == 0 else 'failed',
                      exit_code=code, finished_at=time.time())
        save()
        if code == 0:
            (state / '07-framework-build.done').touch()
        raise SystemExit(code)


if __name__ == '__main__':
    main()
