"""Fetch, verify, and safely cache Dataset and Golden Benchmark release assets."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import urllib.error
import urllib.request

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from storage_architecture import (  # noqa: E402
    STORAGE_TOOL_VERSION,
    extract_archive_atomically,
    read_json,
    remove_cache,
    sha256_file,
    verify_archive,
    verify_installed,
    write_json,
)


LOCKS = {
    "dataset": SCRIPT_ROOT / "datasets" / "statues" / "DATASET_LOCK.json",
    "benchmark": SCRIPT_ROOT / "benchmarks" / "golden" / "BENCHMARK_LOCK.json",
}
EXPECTED_RELEASE_REPOSITORY = "https://github.com/SriramNavi/Chroma3D-Benchmark-Dataset/releases/download/"


def cache_root(argument: Path | None) -> Path:
    if argument:
        return argument.expanduser().resolve()
    import os

    configured = os.environ.get("CHROMA3D_VALIDATION_CACHE")
    return (Path(configured).expanduser() if configured else SCRIPT_ROOT / ".validation-assets").resolve()


def _lock(kind: str) -> dict[str, object]:
    lock = read_json(LOCKS[kind])
    required = {
        "schema_version",
        "asset_filename",
        "asset_sha256",
        "asset_size_bytes",
        "manifest_sha256",
        "release_url",
    }
    missing = sorted(required - set(lock))
    if missing:
        raise ValueError(f"{kind} lock is missing fields: {', '.join(missing)}")
    url = str(lock["release_url"])
    if not url.startswith(EXPECTED_RELEASE_REPOSITORY) or not url.startswith("https://"):
        raise ValueError(f"{kind} lock does not use the approved HTTPS GitHub release host")
    if Path(url.rsplit("/", 1)[-1]).name != str(lock["asset_filename"]):
        raise ValueError(f"{kind} lock URL filename does not match asset_filename")
    minimum_tool = lock.get("minimum_acquisition_tool_version")
    if minimum_tool:
        required_version = tuple(int(part) for part in str(minimum_tool).split("."))
        current_version = tuple(int(part) for part in STORAGE_TOOL_VERSION.split("."))
        if required_version > current_version:
            raise ValueError(f"{kind} lock requires a newer acquisition tool")
    return lock


def _paths(kind: str, root: Path, lock: dict[str, object]) -> dict[str, Path]:
    filename = str(lock["asset_filename"])
    return {
        "downloads": root / "downloads" / filename,
        "partial": root / "downloads" / f"{filename}.part",
        "install": root / kind,
        "status": root / f"{kind}-status.json",
    }


def _download(url: str, destination: Path, partial: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    offset = partial.stat().st_size if partial.exists() else 0
    request = urllib.request.Request(url, headers={"User-Agent": "Chroma3D-Sculpt-storage/1.0"})
    if offset:
        request.add_header("Range", f"bytes={offset}-")
    try:
        response = urllib.request.urlopen(request, timeout=60)
    except urllib.error.URLError as exc:
        raise RuntimeError(f"download failed: {exc}") from exc
    append = offset and getattr(response, "status", None) == 206
    if offset and not append:
        partial.unlink()
        offset = 0
    mode = "ab" if append else "wb"
    with response, partial.open(mode) as stream:
        shutil.copyfileobj(response, stream, length=4 * 1024 * 1024)
    partial.replace(destination)


def _verify_download(kind: str, lock: dict[str, object], paths: dict[str, Path]) -> dict[str, object]:
    archive = paths["downloads"]
    if not archive.is_file():
        raise FileNotFoundError(f"{kind} release asset is not cached: {archive}")
    if archive.stat().st_size != int(lock["asset_size_bytes"]):
        raise ValueError(f"{kind} archive size does not match lock")
    digest = sha256_file(archive)
    if digest != str(lock["asset_sha256"]):
        raise ValueError(f"{kind} archive SHA-256 does not match lock")
    index = verify_archive(archive)
    if index.get("source_manifest_sha256") != lock["manifest_sha256"]:
        raise ValueError(f"{kind} archive manifest SHA-256 does not match lock")
    return index


def _status_for(kind: str, root: Path) -> dict[str, object]:
    lock = _lock(kind)
    paths = _paths(kind, root, lock)
    result: dict[str, object] = {
        "kind": kind,
        "version": lock.get("dataset_version", lock.get("benchmark_version")),
        "cache_location": str(paths["install"]),
        "archive_location": str(paths["downloads"]),
        "installed_state": "NOT_INSTALLED",
        "file_count": 0,
        "size_bytes": 0,
        "verification_status": "NOT_VERIFIED",
    }
    if paths["install"].is_dir():
        try:
            index = verify_installed(paths["install"])
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            result.update(
                installed_state="INSTALLED_BUT_MODIFIED_OR_CORRUPT",
                verification_status=f"FAIL: {exc}",
            )
        else:
            result.update(
                installed_state="INSTALLED_AND_VALID",
                verification_status="PASS",
                file_count=len(index["files"]),
                size_bytes=sum(int(item["size_bytes"]) for item in index["files"]),
            )
    if paths["status"].is_file():
        saved = read_json(paths["status"])
        result["last_verification_time_utc"] = saved.get("verification_time_utc")
    return result


def _save_status(kind: str, root: Path, status: dict[str, object]) -> None:
    lock = _lock(kind)
    paths = _paths(kind, root, lock)
    status = dict(status)
    status["verification_time_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    write_json(paths["status"], status)


def acquire(kind: str, root: Path, *, offline: bool, force: bool) -> dict[str, object]:
    lock = _lock(kind)
    paths = _paths(kind, root, lock)
    archive = paths["downloads"]
    if not archive.is_file():
        if offline:
            raise FileNotFoundError(f"offline mode requires cached {kind} archive: {archive}")
        _download(str(lock["release_url"]), archive, paths["partial"])
    index = _verify_download(kind, lock, paths)
    install_root, installed_index, changed = extract_archive_atomically(
        archive,
        cache_dir=root,
        kind=kind,
        force=force,
    )
    result = _status_for(kind, root)
    result.update(
        archive_sha256=str(lock["asset_sha256"]),
        manifest_sha256=str(lock["manifest_sha256"]),
        install_changed=changed,
        archive_index_file_count=len(index["files"]),
        install_location=str(install_root),
        installed_index_file_count=len(installed_index["files"]),
    )
    _save_status(kind, root, result)
    return result


def verify(kind: str, root: Path) -> dict[str, object]:
    lock = _lock(kind)
    paths = _paths(kind, root, lock)
    archive_index = _verify_download(kind, lock, paths) if paths["downloads"].is_file() else None
    installed_index = verify_installed(paths["install"])
    if archive_index is not None and archive_index != installed_index:
        raise ValueError(f"installed {kind} index differs from cached archive index")
    result = _status_for(kind, root)
    result.update(
        archive_sha256=str(lock["asset_sha256"]) if archive_index is not None else None,
        manifest_sha256=str(lock["manifest_sha256"]),
        offline_verified=True,
    )
    _save_status(kind, root, result)
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("dataset", "benchmark", "all", "status", "verify", "clean-cache"))
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--offline", action="store_true", help="Do not access the network; require a cached archive.")
    parser.add_argument("--force", action="store_true", help="Replace a modified/corrupt installation or clear the full cache.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args()


def main() -> int:
    arguments = _parse_args()
    root = cache_root(arguments.cache_dir)
    try:
        if arguments.command == "clean-cache":
            removed = remove_cache(root, force=arguments.force)
            result: object = {"cache_location": str(root), "removed": removed, "force": arguments.force}
        elif arguments.command == "status":
            result = {kind: _status_for(kind, root) for kind in LOCKS}
        elif arguments.command == "verify":
            result = {kind: verify(kind, root) for kind in LOCKS}
        else:
            kinds = list(LOCKS) if arguments.command == "all" else [arguments.command]
            result = {
                kind: acquire(kind, root, offline=arguments.offline, force=arguments.force)
                for kind in kinds
            }
    except (FileNotFoundError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        if arguments.json:
            print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2, sort_keys=True))
        else:
            print(f"FAIL {exc}")
        return 1
    if arguments.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
