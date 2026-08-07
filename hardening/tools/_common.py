"""Shared deterministic helpers for the Version 1.0 hardening baseline."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPOSITORY_ROOT / "blender_addon" / "chroma3d_sculpt"
REPORT_ROOT = REPOSITORY_ROOT / "manual-tests" / "hardening" / "reports"
BASELINE_ROOT = REPOSITORY_ROOT / "hardening" / "baseline"
CHECKPOINT_TAG = "v0.8.0-pre-hardening-backup"
CHECKPOINT_COMMIT = "d06e1a05890fe23e77e66f95fc40e0200638a765"
PRODUCT_VERSION = "0.8.0-alpha.1"
HARDENING_EXCLUSIONS = (
    "hardening/",
    "manual-tests/hardening/",
    "dist/",
    ".validation-assets/",
    "release-staging/",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def relative(path: Path) -> str:
    return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()


def git_lines(*args: str) -> list[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout.splitlines()


def checkpoint_paths() -> list[str]:
    """Return the immutable product path set, excluding H0 additions."""

    paths = git_lines("ls-tree", "-r", "--name-only", CHECKPOINT_TAG)
    return sorted(path for path in paths if not path.startswith(HARDENING_EXCLUSIONS))


def checkpoint_python_paths() -> list[Path]:
    return [REPOSITORY_ROOT / path for path in checkpoint_paths() if path.endswith(".py")]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse_python(path: Path) -> ast.AST:
    return ast.parse(read_text(path), filename=relative(path))


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(canonical_bytes(value))
    temporary.replace(path)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value.rstrip() + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def module_name(path: Path) -> str:
    rel = relative(path)
    if rel.startswith("blender_addon/"):
        parts = Path(rel).with_suffix("").parts[1:]
    else:
        parts = Path(rel).with_suffix("").parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def line_count(text: str) -> int:
    return len(text.splitlines())


def iter_definitions(tree: ast.AST) -> Iterable[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef]:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node


def markdown_table(headers: tuple[str, ...], rows: Iterable[Iterable[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        values = [str(value).replace("|", "\\|").replace("\n", " ") for value in row]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)
