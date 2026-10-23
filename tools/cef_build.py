#!/usr/bin/env python3
"""Single entry point for the reproducible CEF 104 macOS build workspace."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config/build-profiles.json"
SOURCE = ROOT / "chromium/src"
SDK = ROOT / "sdks/MacOSX12.3.sdk"
FRAMEWORK_NAME = "Chromium Embedded Framework.framework"
MACH_FILES = (
    "Chromium Embedded Framework",
    "Libraries/libEGL.dylib",
    "Libraries/libGLESv2.dylib",
    "Libraries/libvk_swiftshader.dylib",
)
SNAPSHOTS = {
    "arm64": (
        "Resources/snapshot_blob.arm64.bin",
        "Resources/v8_context_snapshot.arm64.bin",
    ),
    "x64": (
        "Resources/snapshot_blob.x64.bin",
        "Resources/v8_context_snapshot.x86_64.bin",
    ),
}
OBSOLETE_BUNDLE_FILES = {"Resources/snapshot_blob.bin"}
HOST_ARCHES = {"arm64": "darwin-arm64", "x86_64": "darwin-x86_64"}
LEGACY_OUTPUTS = {
    ("macos11", "arm64"): "Release_GN_arm64_macos11",
    ("macos11", "x64"): "Release_GN_x64_macos11",
    ("macos12", "arm64"): "Release_GN_arm64",
    ("macos12", "x64"): "Release_GN_x64_macos12",
}


class BuildError(RuntimeError):
    pass


def load_config() -> dict:
    config = json.loads(CONFIG_PATH.read_text())
    if config.get("format_version") != 1:
        raise BuildError("Unsupported build profile format")
    if config.get("sdk_version") != "12.3":
        raise BuildError("CEF 104 profiles must use SDK 12.3")
    return config


def command_text(command: Sequence[str], cwd: Optional[Path] = None) -> str:
    try:
        return subprocess.check_output(
            list(command), cwd=str(cwd) if cwd else None, stderr=subprocess.STDOUT, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        output = getattr(exc, "output", "")
        raise BuildError((output or str(exc)).strip()) from exc


def run(command: Sequence[str], cwd: Optional[Path] = None, env: Optional[dict] = None,
        stdout=None) -> None:
    print("+ " + " ".join(str(item) for item in command), flush=True)
    try:
        subprocess.run(
            list(map(str, command)), cwd=str(cwd) if cwd else None, env=env,
            stdout=stdout, stderr=subprocess.STDOUT if stdout else None, check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise BuildError(f"Command failed: {' '.join(map(str, command))}") from exc


def host_key() -> str:
    if platform.system() != "Darwin":
        raise BuildError("CEF 104 build supports macOS hosts only")
    machine = platform.machine()
    if machine not in HOST_ARCHES:
        raise BuildError(f"Unsupported macOS host architecture: {machine}")
    return HOST_ARCHES[machine]


def binary_arches(path: Path) -> List[str]:
    if not path.is_file():
        return []
    try:
        output = command_text(["lipo", "-archs", str(path)])
    except BuildError:
        return []
    return output.split()


def expected_host_binary_arch() -> str:
    return "arm64" if host_key() == "darwin-arm64" else "x86_64"


def git_revision(path: Path) -> str:
    return command_text(["git", "rev-parse", "HEAD"], cwd=path)


def git_dirty(path: Path) -> bool:
    return bool(command_text(["git", "status", "--porcelain", "--untracked-files=no"], cwd=path))


def workspace_env() -> dict:
    env = os.environ.copy()
    env["PATH"] = str(ROOT / "depot_tools") + os.pathsep + env.get("PATH", "")
    env["DEPOT_TOOLS_UPDATE"] = "0"
    env["GCLIENT_PY3"] = "1"
    for name in ("LIBRARY_PATH", "CPATH", "SDKROOT"):
        env.pop(name, None)
    return env


def tool_paths() -> Dict[str, Path]:
    return {
        "clang": SOURCE / "third_party/llvm-build/Release+Asserts/bin/clang",
        "gn": SOURCE / "buildtools/mac/gn",
        "depot-runtime": ROOT / "depot_tools/.cipd_client",
    }


def inspect_requirements(config: dict) -> Tuple[List[str], List[str]]:
    ok: List[str] = []
    errors: List[str] = []

    def check(label: str, callback) -> None:
        try:
            detail = callback()
            ok.append(f"{label}: {detail}")
        except (BuildError, OSError, subprocess.CalledProcessError) as exc:
            errors.append(f"{label}: {exc}")

    check("host", lambda: host_key())
    check("Python", lambda: platform.python_version() if sys.version_info >= (3, 8)
          else (_ for _ in ()).throw(BuildError("Python 3.8+ is required")))
    check("Git LFS", lambda: command_text(["git", "lfs", "version"]))
    check("Xcode/CLT", lambda: command_text(["xcode-select", "-p"]))
    check("Xcode", lambda: command_text(["xcodebuild", "-version"]).replace("\n", "; "))

    for relative, expected in config["source_revisions"].items():
        path = ROOT / relative
        check(relative, lambda p=path, e=expected: _check_revision(p, e))

    expected_arch = None
    try:
        expected_arch = expected_host_binary_arch()
    except BuildError:
        pass
    if expected_arch:
        for name, path in tool_paths().items():
            check(name, lambda n=name, p=path, a=expected_arch: _check_tool_arch(n, p, a))
    check("SDK", lambda: _check_sdk(config))
    return ok, errors


def _check_revision(path: Path, expected: str) -> str:
    if not (path / ".git").exists() and not (path.parent / ".git/modules").exists():
        raise BuildError("not initialized")
    actual = git_revision(path)
    if actual != expected:
        raise BuildError(f"expected {expected[:12]}, got {actual[:12]}")
    return actual[:12] + ("; local changes present" if git_dirty(path) else "")


def _check_tool_arch(name: str, path: Path, expected: str) -> str:
    arches = binary_arches(path)
    if expected not in arches:
        detail = ",".join(arches) if arches else "missing or not Mach-O"
        raise BuildError(f"expected {expected}, got {detail}: {path}")
    if name == "clang":
        version = command_text([str(path), "--version"]).splitlines()[0]
    elif name == "gn":
        version = command_text([str(path), "--version"])
    else:
        version = command_text([str(path), "version"]).splitlines()[0]
    return f"{expected}; {version}"


def _check_sdk(config: dict) -> str:
    settings = SDK / "SDKSettings.plist"
    if not settings.is_file():
        raise BuildError(f"missing {SDK}")
    data = plistlib.loads(settings.read_bytes())
    version = str(data.get("Version", ""))
    if version != config["sdk_version"]:
        raise BuildError(f"expected {config['sdk_version']}, got {version or 'unknown'}")
    return str(SDK)


def cmd_setup(_args: argparse.Namespace) -> None:
    config = load_config()
    host = host_key()
    if sys.version_info < (3, 8):
        raise BuildError("Python 3.8+ is required")
    command_text(["git", "lfs", "version"])
    command_text(["xcode-select", "-p"])
    command_text(["xcodebuild", "-version"])
    run(["git", "submodule", "sync", "--recursive"], cwd=ROOT)
    run(["git", "submodule", "update", "--init", "--recursive"], cwd=ROOT)
    run(["git", "lfs", "install", "--local"], cwd=ROOT)
    run(["git", "lfs", "pull"], cwd=ROOT / "cef_build_tools")
    restore = ROOT / "cef_build_tools/restore.py"
    manifest = json.loads((ROOT / "cef_build_tools/manifest.json").read_text())
    if manifest.get("format_version") != 2 or host not in manifest.get("hosts", {}):
        raise BuildError(f"Tool archive does not support {host}")
    missing = []
    expected_arch = expected_host_binary_arch()
    for name, path in tool_paths().items():
        if expected_arch not in binary_arches(path):
            missing.append(name)
    try:
        _check_sdk(config)
    except BuildError:
        missing.append("sdk")
    if missing:
        run([sys.executable, str(restore), "--workspace", str(ROOT),
             "--replace-existing", "--only", *missing])
    else:
        run([sys.executable, str(restore), "--workspace", str(ROOT), "--verify-only"])
    ok, errors = inspect_requirements(config)
    for line in ok:
        print("[OK] " + line)
    if errors:
        raise BuildError("Setup verification failed:\n" + "\n".join("- " + item for item in errors))
    print("Setup complete. Run ./cef-build build or ./cef-build build macos11.")


def cmd_doctor(_args: argparse.Namespace) -> None:
    config = load_config()
    ok, errors = inspect_requirements(config)
    for line in ok:
        print("[OK] " + line)
    for line in errors:
        print("[FAIL] " + line)
    for profile in config["profiles"]:
        final = ROOT / "out" / profile / FRAMEWORK_NAME
        cache = [active_output_dir(profile, arch) for arch in config["architectures"]]
        state = "framework ready" if final.is_dir() else "no final framework"
        cache_state = ", ".join(f"{p.name}={'yes' if p.is_dir() else 'no'}" for p in cache)
        print(f"[STATE] {profile}: {state}; {cache_state}")
    if errors:
        raise BuildError(f"Doctor found {len(errors)} blocking problem(s)")


def gn_literal(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    raise BuildError(f"Unsupported GN value: {value!r}")


def gn_args(config: dict, profile: str, arch: str) -> Dict[str, object]:
    result = dict(config["common_gn_args"])
    deployment = config["profiles"][profile]["deployment_target"]
    result.update({
        "mac_deployment_target": deployment,
        "mac_min_system_version": deployment,
        "mac_sdk_path": str(SDK.resolve()),
        "target_cpu": arch,
    })
    return result


def render_gn_args(config: dict, profile: str, arch: str) -> str:
    return "".join(f"{key}={gn_literal(value)}\n" for key, value in sorted(
        gn_args(config, profile, arch).items()))


def output_dir(profile: str, arch: str) -> Path:
    return SOURCE / "out" / f"cef104-{profile}-{arch}"


def active_output_dir(profile: str, arch: str) -> Path:
    canonical = output_dir(profile, arch)
    legacy = SOURCE / "out" / LEGACY_OUTPUTS[(profile, arch)]
    return canonical if canonical.exists() or not legacy.exists() else legacy


@contextlib.contextmanager
def build_lock(profile: str):
    state = ROOT / ".cef-build" / profile
    state.mkdir(parents=True, exist_ok=True)
    with (state / "build.lock").open("w") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise BuildError(f"Another {profile} build is running") from exc
        yield state


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temp.replace(path)


def preflight_build(config: dict) -> None:
    _, errors = inspect_requirements(config)
    if errors:
        raise BuildError("Run ./cef-build setup and fix:\n" + "\n".join("- " + e for e in errors))


def cmd_build(args: argparse.Namespace) -> None:
    config = load_config()
    profile = args.profile or config["default_profile"]
    preflight_build(config)
    jobs = args.jobs or min(os.cpu_count() or 1, 8)
    env = workspace_env()
    gn = SOURCE / "buildtools/mac/gn"
    ninja = ROOT / "depot_tools/ninja"
    started = int(time.time())
    with build_lock(profile) as state:
        status_path = state / "status.json"
        log_path = state / "build.log"
        status = {"profile": profile, "state": "running", "jobs": jobs,
                  "started_at": started, "architectures": {}}
        save_json(status_path, status)
        try:
            with log_path.open("a") as log:
                log.write(f"\n=== {profile} build started {time.ctime()} ===\n")
                for arch in config["architectures"]:
                    out = active_output_dir(profile, arch)
                    out.mkdir(parents=True, exist_ok=True)
                    (out / "args.gn").write_text(render_gn_args(config, profile, arch))
                    status["architectures"][arch] = "configuring"
                    save_json(status_path, status)
                    run([str(gn), "gen", f"out/{out.name}"], cwd=SOURCE, env=env, stdout=log)
                    status["architectures"][arch] = "building"
                    save_json(status_path, status)
                    run([str(ninja), "-C", f"out/{out.name}", "cef_framework",
                         "-j", str(jobs)], cwd=SOURCE, env=env, stdout=log)
                    status["architectures"][arch] = "complete"
                    save_json(status_path, status)
            manifest = merge_and_verify(config, profile)
            status.update(state="complete", finished_at=int(time.time()),
                          output=manifest["output"], manifest=manifest["manifest"])
            save_json(status_path, status)
        except BaseException:
            status.update(state="failed", finished_at=int(time.time()))
            save_json(status_path, status)
            raise
    print(f"Build complete: {ROOT / 'out' / profile / FRAMEWORK_NAME}")


def framework_root(path: Path) -> Path:
    versioned = path / "Versions/A"
    return versioned if versioned.is_dir() else path


def inventory(path: Path) -> Dict[str, Path]:
    return {item.relative_to(path).as_posix(): item for item in path.rglob("*") if item.is_file()}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def merge_frameworks(arm64: Path, x64: Path, output: Path) -> None:
    roots = {"arm64": framework_root(arm64), "x64": framework_root(x64)}
    items = {arch: inventory(path) for arch, path in roots.items()}
    all_snapshots = set(SNAPSHOTS["arm64"]) | set(SNAPSHOTS["x64"])
    common = {}
    for arch in ("arm64", "x64"):
        required = set(MACH_FILES) | set(SNAPSHOTS[arch]) | {"Resources/Info.plist"}
        missing = required - set(items[arch])
        if missing:
            raise BuildError(f"{arch} framework is missing: {sorted(missing)}")
        common[arch] = (set(items[arch]) - all_snapshots - set(MACH_FILES)
                        - OBSOLETE_BUNDLE_FILES - {"Resources/Info.plist"})
    if common["arm64"] != common["x64"]:
        raise BuildError(f"Shared framework file sets differ: {sorted(common['arm64'] ^ common['x64'])}")
    for name in sorted(common["arm64"]):
        if sha256(items["arm64"][name]) != sha256(items["x64"][name]):
            raise BuildError(f"Shared framework resource differs: {name}")
    arm_plist = plistlib.loads(items["arm64"]["Resources/Info.plist"].read_bytes())
    x64_plist = plistlib.loads(items["x64"]["Resources/Info.plist"].read_bytes())
    if arm_plist != x64_plist:
        raise BuildError("Framework Info.plist differs between architectures")
    output.mkdir(parents=True)
    for name in sorted(common["arm64"] | {"Resources/Info.plist"}):
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(items["arm64"][name], destination)
    for arch in ("arm64", "x64"):
        for name in SNAPSHOTS[arch]:
            destination = output / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(items[arch][name], destination)
    for name in MACH_FILES:
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        run(["lipo", "-create", str(items["arm64"][name]), str(items["x64"][name]),
             "-output", str(destination)])


def build_versions(path: Path) -> Tuple[List[str], List[str]]:
    output = command_text(["vtool", "-show-build", str(path)])
    return re.findall(r"^\s*minos\s+(\S+)", output, re.MULTILINE), re.findall(
        r"^\s*sdk\s+(\S+)", output, re.MULTILINE)


def verify_framework(path: Path, deployment: str, sdk_version: str) -> dict:
    files = inventory(path)
    result = {"mach_o": {}, "snapshots": {}, "file_count": len(files)}
    for name in MACH_FILES:
        binary = path / name
        arches = binary_arches(binary)
        if set(arches) != {"arm64", "x86_64"}:
            raise BuildError(f"{name}: expected arm64+x86_64, got {arches}")
        minimums, sdks = build_versions(binary)
        if not minimums or set(minimums) != {deployment}:
            raise BuildError(f"{name}: expected minimum macOS {deployment}, got {minimums}")
        if not sdks or set(sdks) != {sdk_version}:
            raise BuildError(f"{name}: expected SDK {sdk_version}, got {sdks}")
        result["mach_o"][name] = {"architectures": arches, "minos": minimums, "sdk": sdks}
    for names in SNAPSHOTS.values():
        for name in names:
            item = path / name
            if not item.is_file() or item.stat().st_size == 0:
                raise BuildError(f"Missing V8 snapshot: {name}")
            result["snapshots"][name] = {"bytes": item.stat().st_size, "sha256": sha256(item)}
    return result


def tool_versions() -> dict:
    paths = tool_paths()
    return {
        "host": host_key(),
        "clang": command_text([str(paths["clang"]), "--version"]).splitlines()[0],
        "gn": command_text([str(paths["gn"]), "--version"]),
        "ninja": command_text([str(ROOT / "depot_tools/ninja"), "--version"], cwd=ROOT),
    }


def merge_and_verify(config: dict, profile: str) -> dict:
    state = ROOT / ".cef-build" / profile
    stage_parent = Path(tempfile.mkdtemp(prefix="merge-", dir=state))
    staged_framework = stage_parent / FRAMEWORK_NAME
    final_dir = ROOT / "out" / profile
    previous = state / "previous-output"
    try:
        merge_frameworks(
            active_output_dir(profile, "arm64") / FRAMEWORK_NAME,
            active_output_dir(profile, "x64") / FRAMEWORK_NAME,
            staged_framework,
        )
        verification = verify_framework(
            staged_framework, config["profiles"][profile]["deployment_target"], config["sdk_version"]
        )
        hashes = {name: sha256(path) for name, path in sorted(inventory(staged_framework).items())}
        manifest = {
            "format_version": 1,
            "profile": profile,
            "chromium_version": config["chromium_version"],
            "cef_version": config["cef_version"],
            "sdk_version": config["sdk_version"],
            "deployment_target": config["profiles"][profile]["deployment_target"],
            "architectures": ["arm64", "x86_64"],
            "source_revisions": {name: git_revision(ROOT / name)
                                 for name in config["source_revisions"]},
            "source_dirty": {name: git_dirty(ROOT / name)
                             for name in config["source_revisions"]},
            "tools": tool_versions(),
            "gn_args": {arch: gn_args(config, profile, arch)
                        for arch in config["architectures"]},
            "verification": verification,
            "files": hashes,
        }
        save_json(stage_parent / "build-manifest.json", manifest)
        if previous.exists():
            shutil.rmtree(previous)
        if final_dir.exists():
            final_dir.replace(previous)
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            stage_parent.replace(final_dir)
        except BaseException:
            if previous.exists() and not final_dir.exists():
                previous.replace(final_dir)
            raise
        if previous.exists():
            shutil.rmtree(previous)
        return {"output": str(final_dir / FRAMEWORK_NAME),
                "manifest": str(final_dir / "build-manifest.json")}
    finally:
        if stage_parent.exists():
            shutil.rmtree(stage_parent)


def managed_clean_paths(target: str) -> List[Path]:
    if target in ("macos11", "macos12"):
        return [output_dir(target, "arm64"), output_dir(target, "x64"),
                SOURCE / "out" / LEGACY_OUTPUTS[(target, "arm64")],
                SOURCE / "out" / LEGACY_OUTPUTS[(target, "x64")],
                ROOT / "out" / target, ROOT / ".cef-build" / target]
    if target == "obsolete":
        return [
            SOURCE / "out/Debug_GN_arm64",
            SOURCE / "out/Release_GN_x64_macos1013",
            ROOT / "source-staging",
            ROOT / "downloads",
            ROOT / "backups",
            ROOT / "logs",
            ROOT / "state",
            ROOT / "out/universal-macos11",
            ROOT / "out/universal-macos12",
        ]
    raise BuildError(f"Unknown clean target: {target}")


def cmd_clean(args: argparse.Namespace) -> None:
    existing = [path for path in managed_clean_paths(args.target) if path.exists()]
    if not existing:
        print("Nothing to clean.")
        return
    print("The following managed paths will move to Trash:")
    for path in existing:
        print("- " + str(path.relative_to(ROOT)))
    if not args.yes:
        answer = input("Continue? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Cancelled.")
            return
    trash_root = Path.home() / ".Trash" / ("cef-sandbox-104-" + time.strftime("%Y%m%d-%H%M%S"))
    trash_root.mkdir(parents=True, exist_ok=False)
    for source in existing:
        relative = source.relative_to(ROOT)
        destination = trash_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.replace(destination)
        print(f"Moved {relative} -> {destination}")


def parser() -> argparse.ArgumentParser:
    config = load_config()
    result = argparse.ArgumentParser(
        prog="cef-build", description="Build and verify CEF 104 Universal Frameworks on macOS."
    )
    commands = result.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("setup", help="sync sources and restore the pinned host tools")
    setup.set_defaults(handler=cmd_setup)
    doctor = commands.add_parser("doctor", help="inspect the workspace without changing it")
    doctor.set_defaults(handler=cmd_doctor)
    build = commands.add_parser("build", help="build arm64+x64 and merge a Universal Framework")
    build.add_argument("profile", nargs="?", choices=sorted(config["profiles"]),
                       help=f"build profile (default: {config['default_profile']})")
    build.add_argument("--jobs", type=int, help="Ninja jobs (default: min(CPU count, 8))")
    build.set_defaults(handler=cmd_build)
    clean = commands.add_parser("clean", help="move managed build data to the macOS Trash")
    clean.add_argument("target", choices=["macos11", "macos12", "obsolete"])
    clean.add_argument("--yes", action="store_true", help="skip the interactive confirmation")
    clean.set_defaults(handler=cmd_clean)
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        args = parser().parse_args(argv)
        if getattr(args, "jobs", 1) is not None and getattr(args, "jobs", 1) < 1:
            raise BuildError("--jobs must be positive")
        args.handler(args)
        return 0
    except BuildError as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
