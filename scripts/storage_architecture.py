"""Shared, standard-library-only helpers for Sprint 2.7 storage tooling."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import shutil
import stat
import uuid
import zipfile
from typing import Any, Iterable, Mapping


ARCHIVE_INDEX_SCHEMA_VERSION = "1.0.0"
STORAGE_TOOL_VERSION = "1.0.0"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(payload))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_timestamp(value: str | None = None) -> str:
    if value:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_posix_name(name: str) -> str:
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or ":" in normalized.split("/", 1)[0]:
        raise ValueError(f"absolute archive path is not allowed: {name!r}")
    parts = normalized.split("/")
    if not normalized or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"unsafe archive path: {name!r}")
    candidate = PurePosixPath(*parts).as_posix()
    if candidate != normalized:
        raise ValueError(f"archive path is not normalized: {name!r}")
    return candidate


def archive_member_name(archive_root: str, relative_path: str) -> str:
    root = _safe_posix_name(archive_root)
    relative = _safe_posix_name(relative_path)
    return f"{root}/{relative}"


def _zip_datetime(timestamp: str) -> tuple[int, int, int, int, int, int]:
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    # ZIP timestamps cannot represent dates before 1980.
    return (
        max(1980, parsed.year),
        parsed.month,
        parsed.day,
        parsed.hour,
        parsed.minute,
        parsed.second,
    )


def _zip_info(name: str, timestamp: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=_zip_datetime(timestamp))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 0
    info.external_attr = (0o644 & 0xFFFF) << 16
    info.flag_bits = 0
    return info


def _is_special_zip_entry(info: zipfile.ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0xFFFF
    return bool(mode and (stat.S_ISLNK(mode) or stat.S_ISCHR(mode) or stat.S_ISBLK(mode) or stat.S_ISFIFO(mode)))


def build_deterministic_zip(
    output_path: Path,
    *,
    archive_root: str,
    index_relative_path: str,
    created_at_utc: str,
    entries: Iterable[tuple[str, bytes, Mapping[str, Any]]],
    index_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a stable ZIP and return its complete index payload.

    ``entries`` contains paths relative to ``archive_root``. The generated
    index is deliberately excluded from its own file list to avoid a circular
    self-hash.
    """
    normalized_entries: list[tuple[str, bytes, dict[str, Any]]] = []
    seen: set[str] = set()
    for relative_path, payload, metadata in entries:
        relative = _safe_posix_name(relative_path)
        if relative in seen or relative == index_relative_path:
            raise ValueError(f"duplicate or reserved archive path: {relative}")
        seen.add(relative)
        normalized_entries.append((relative, payload, dict(metadata)))
    normalized_entries.sort(key=lambda item: item[0])

    files = [
        {
            "path": relative,
            "size_bytes": len(payload),
            "sha256": sha256_bytes(payload),
            **metadata,
        }
        for relative, payload, metadata in normalized_entries
    ]
    complete_index = {
        "archive_index_schema_version": ARCHIVE_INDEX_SCHEMA_VERSION,
        **dict(index_payload),
        "archive_root": archive_root,
        "index_path": index_relative_path,
        "files": files,
    }
    index_bytes = canonical_json_bytes(complete_index)
    index_name = archive_member_name(archive_root, index_relative_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f".{output_path.name}.{uuid.uuid4().hex}.part")
    try:
        payloads = {
            archive_member_name(archive_root, relative): payload
            for relative, payload, _metadata in normalized_entries
        }
        payloads[index_name] = index_bytes
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name in sorted(payloads):
                archive.writestr(_zip_info(name, created_at_utc), payloads[name])
        os.replace(temporary_path, output_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    verify_archive(output_path)
    return complete_index


def write_sha256_sidecar(archive_path: Path, sidecar_path: Path) -> str:
    digest = sha256_file(archive_path)
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.write_text(f"{digest}  {archive_path.name}\n", encoding="utf-8")
    return digest


def _read_archive_index(archive: zipfile.ZipFile) -> tuple[dict[str, Any], str]:
    candidates = [
        info.filename
        for info in archive.infolist()
        if info.filename.endswith("/archive_index.json")
    ]
    if len(candidates) != 1:
        raise ValueError("archive must contain exactly one archive_index.json")
    index_name = _safe_posix_name(candidates[0])
    if _is_special_zip_entry(archive.getinfo(index_name)):
        raise ValueError("archive index is a special file")
    return json.loads(archive.read(index_name).decode("utf-8")), index_name


def verify_archive(archive_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(archive_path, "r") as archive:
        infos = archive.infolist()
        names = [_safe_posix_name(info.filename) for info in infos]
        if len(names) != len(set(names)):
            raise ValueError("archive contains duplicate paths")
        if any(_is_special_zip_entry(info) for info in infos):
            raise ValueError("archive contains a symlink or special file")
        index, index_name = _read_archive_index(archive)
        root = _safe_posix_name(str(index["archive_root"]))
        expected_index_name = archive_member_name(root, str(index["index_path"]))
        if index_name != expected_index_name:
            raise ValueError("archive index path does not match archive root")
        expected: dict[str, dict[str, Any]] = {}
        for record in index["files"]:
            relative = _safe_posix_name(str(record["path"]))
            if relative in expected or relative == str(index["index_path"]):
                raise ValueError(f"duplicate or reserved index path: {relative}")
            expected[relative] = record
            member = archive_member_name(root, relative)
            info = archive.getinfo(member)
            if info.is_dir():
                raise ValueError(f"indexed path is a directory: {relative}")
            payload = archive.read(member)
            if len(payload) != int(record["size_bytes"]):
                raise ValueError(f"archive size mismatch: {relative}")
            if sha256_bytes(payload) != record["sha256"]:
                raise ValueError(f"archive checksum mismatch: {relative}")
        expected_names = {archive_member_name(root, path) for path in expected}
        expected_names.add(expected_index_name)
        if set(names) != expected_names:
            unexpected = sorted(set(names) - expected_names)
            missing = sorted(expected_names - set(names))
            raise ValueError(f"archive index mismatch; unexpected={unexpected}, missing={missing}")
        return index


def _relative_to_install_root(path: str, archive_root: str) -> str:
    normalized = _safe_posix_name(path)
    prefix = f"{_safe_posix_name(archive_root)}/"
    if not normalized.startswith(prefix):
        raise ValueError(f"archive member is outside archive root: {path!r}")
    return _safe_posix_name(normalized[len(prefix) :])


def _verify_installed_index(install_root: Path) -> dict[str, Any]:
    index_candidates = sorted(install_root.rglob("archive_index.json"))
    if len(index_candidates) != 1:
        raise ValueError("installed asset must contain exactly one archive index")
    index_path = index_candidates[0]
    index = read_json(index_path)
    index_relative = str(index["index_path"])
    expected_paths = {PurePosixPath(record["path"]).as_posix() for record in index["files"]}
    actual_paths = {
        path.relative_to(install_root).as_posix()
        for path in install_root.rglob("*")
        if path.is_file()
    }
    actual_index_relative = index_path.relative_to(install_root).as_posix()
    if actual_index_relative != index_relative:
        raise ValueError("installed archive index is in the wrong location")
    if actual_paths != expected_paths | {index_relative}:
        raise ValueError("installed files do not match archive index")
    for record in index["files"]:
        path = install_root / record["path"]
        if path.stat().st_size != int(record["size_bytes"]):
            raise ValueError(f"installed size mismatch: {record['path']}")
        if sha256_file(path) != record["sha256"]:
            raise ValueError(f"installed checksum mismatch: {record['path']}")
    return index


def verify_installed(install_root: Path) -> dict[str, Any]:
    if not install_root.is_dir():
        raise FileNotFoundError(f"asset is not installed: {install_root}")
    return _verify_installed_index(install_root)


def extract_archive_atomically(
    archive_path: Path,
    *,
    cache_dir: Path,
    kind: str,
    force: bool = False,
) -> tuple[Path, dict[str, Any], bool]:
    """Securely extract an archive and atomically install its root contents."""
    index = verify_archive(archive_path)
    archive_root = _safe_posix_name(str(index["archive_root"]))
    final_root = cache_dir / kind
    if final_root.is_dir():
        try:
            existing_index = verify_installed(final_root)
        except (OSError, ValueError, json.JSONDecodeError):
            if not force:
                raise ValueError(
                    f"existing {kind} installation is modified or corrupt; use --force"
                )
        else:
            if existing_index == index:
                return final_root, existing_index, False
            if not force:
                raise ValueError(
                    f"existing {kind} installation is from another archive; use --force"
                )

    cache_dir.mkdir(parents=True, exist_ok=True)
    staging_root = cache_dir / f".staging-{kind}-{uuid.uuid4().hex}"
    staging_root.mkdir(parents=True, exist_ok=False)
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            for info in archive.infolist():
                member = _safe_posix_name(info.filename)
                if info.is_dir() or _is_special_zip_entry(info):
                    raise ValueError(f"archive contains an unsupported entry: {member}")
                relative = _relative_to_install_root(member, archive_root)
                target = staging_root / Path(*PurePosixPath(relative).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info, "r") as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination, length=4 * 1024 * 1024)
        verify_installed(staging_root)
        if final_root.exists():
            backup = cache_dir / f".backup-{kind}-{uuid.uuid4().hex}"
            os.replace(final_root, backup)
            try:
                os.replace(staging_root, final_root)
            except Exception:
                os.replace(backup, final_root)
                raise
            shutil.rmtree(backup)
        else:
            os.replace(staging_root, final_root)
        return final_root, verify_installed(final_root), True
    finally:
        if staging_root.exists():
            shutil.rmtree(staging_root)


def remove_cache(cache_dir: Path, *, force: bool = False) -> list[str]:
    if not cache_dir.exists():
        return []
    if not force:
        removed: list[str] = []
        for path in cache_dir.rglob("*.part"):
            path.unlink()
            removed.append(path.relative_to(cache_dir).as_posix())
        for path in sorted(cache_dir.rglob(".staging-*"), reverse=True):
            if not path.is_dir():
                continue
            shutil.rmtree(path)
            removed.append(path.name)
        return removed
    removed = [path.name for path in cache_dir.iterdir()]
    shutil.rmtree(cache_dir)
    return removed


def git_tracked_paths(repository_root: Path, *, staged_only: bool = False) -> list[str]:
    import subprocess

    command = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"] if staged_only else ["git", "ls-files"]
    completed = subprocess.run(
        command,
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]
