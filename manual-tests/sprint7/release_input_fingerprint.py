"""Deterministic identity for every Sprint 7 shipping and validation input."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "manual-tests" / "sprint7" / "reports" / "release_input_fingerprint.json"


def _files_under(folder: Path) -> Iterable[Path]:
    if not folder.is_dir():
        return ()
    return (
        path for path in folder.rglob("*")
        if path.is_file()
        and not {"__pycache__", "reports", "logs", "artifacts", "screenshots"}.intersection(path.parts)
        and path.suffix.lower() not in {".pyc", ".pyo"}
    )


def release_input_paths() -> tuple[Path, ...]:
    values: set[Path] = set()
    for folder in (
        ROOT / "blender_addon" / "chroma3d_sculpt",
        ROOT / "schemas",
        ROOT / "profiles",
    ):
        values.update(_files_under(folder))
    for relative in (
        "scripts/_project.py",
        "scripts/package_extension.py",
        "scripts/validate_package.py",
        "tests/blender/run_sprint7_tests.py",
        "tests/blender/test_sprint7_ai_recommendation.py",
    ):
        path = ROOT / relative
        if path.is_file():
            values.add(path)
    values.update(path for path in _files_under(ROOT / "manual-tests" / "sprint7") if path.suffix.lower() == ".py")
    values.update(path for path in _files_under(ROOT / "manual-tests" / "sprint7-final") if path.suffix.lower() == ".py")
    return tuple(sorted(values, key=lambda path: path.relative_to(ROOT).as_posix()))


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _aggregate(entries: Iterable[tuple[str, str]]) -> str:
    digest = hashlib.sha256()
    for relative, file_hash in entries:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "UNAVAILABLE"


def build_release_input_identity() -> dict[str, object]:
    paths = release_input_paths()
    entries = tuple((path.relative_to(ROOT).as_posix(), _digest(path)) for path in paths)
    dataset_manifest = ROOT / ".validation-assets" / "dataset" / "manifests" / "statue_dataset_manifest.json"
    golden_manifest = ROOT / ".validation-assets" / "benchmark" / "manifests" / "golden_manifest.json"
    profile_entries = tuple(
        (path.relative_to(ROOT).as_posix(), _digest(path))
        for path in sorted(_files_under(ROOT / "profiles"), key=lambda item: item.relative_to(ROOT).as_posix())
    )
    context_inputs = (
        ROOT / "blender_addon" / "chroma3d_sculpt" / "ai_assistance_settings.py",
        ROOT / "blender_addon" / "chroma3d_sculpt" / "performance_registry.py",
    )
    profile_context_entries = profile_entries + tuple(
        (path.relative_to(ROOT).as_posix(), _digest(path)) for path in context_inputs if path.is_file()
    )
    return {
        "schema_version": "1.0.0",
        "file_count": len(entries),
        "files": [{"path": relative, "sha256": file_hash} for relative, file_hash in entries],
        "aggregate_sha256": _aggregate(entries),
        "head": _git("rev-parse", "HEAD"),
        "base_main": _git("rev-parse", "main"),
        "origin_main": _git("rev-parse", "origin/main"),
        "dataset_manifest_sha256": _digest(dataset_manifest) if dataset_manifest.is_file() else "MISSING",
        "golden_manifest_sha256": _digest(golden_manifest) if golden_manifest.is_file() else "MISSING",
        "profile_context_sha256": _aggregate(profile_context_entries),
    }


def write_release_input_identity(path: Path = REPORT) -> dict[str, object]:
    identity = build_release_input_identity()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)
    return identity


if __name__ == "__main__":
    value = write_release_input_identity()
    print(json.dumps({key: value[key] for key in (
        "file_count", "aggregate_sha256", "dataset_manifest_sha256",
        "golden_manifest_sha256", "profile_context_sha256",
    )}, sort_keys=True))
