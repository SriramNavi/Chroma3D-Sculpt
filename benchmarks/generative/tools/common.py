"""Shared deterministic hashing, JSON, path, and cache helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


CGB_VERSION = "0.1.0"
GENERATIVE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = GENERATIVE_ROOT.parents[1]
VALIDATION_ROOT = PROJECT_ROOT / ".validation-assets" / "generative-benchmark"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path, chunk_size: int = 4 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def relative_to_project(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return "[EXTERNAL_PATH_REDACTED]"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def cache_identity(
    *, case_hash: str, backend_id: str, model_version: str, adapter_version: str,
    parameter_hash: str, attempt: int, seed: int | None, seed_semantics: str,
    quality_mode: str, evaluator_version: str, evaluation_settings_hash: str,
) -> tuple[str, dict[str, Any]]:
    identity = {
        "cgb_version": CGB_VERSION, "case_hash": case_hash, "backend_id": backend_id,
        "model_version": model_version, "adapter_version": adapter_version,
        "request_parameter_hash": parameter_hash, "attempt": attempt, "seed": seed,
        "seed_semantics": seed_semantics, "quality_mode": quality_mode,
        "evaluator_version": evaluator_version,
        "evaluation_settings_hash": evaluation_settings_hash,
    }
    return stable_hash(identity), identity


def evaluation_cache_identity(
    *, artifact_sha256: str, evaluator_version: str, evaluation_settings_hash: str,
) -> dict[str, str]:
    payload = {
        "artifact_sha256": artifact_sha256,
        "evaluator_version": evaluator_version,
        "evaluation_settings_hash": evaluation_settings_hash,
    }
    return {**payload, "evaluation_cache_key": stable_hash(payload)}


def reusable_record(record: Mapping[str, Any], identity: Mapping[str, Any], artifact_root: Path) -> bool:
    if record.get("status") != "PASS" or record.get("cache_identity") != identity:
        return False
    relative = record.get("raw_artifact_path")
    digest = record.get("raw_artifact_sha256")
    if not isinstance(relative, str) or not isinstance(digest, str):
        return False
    artifact = artifact_root / relative
    if not artifact.is_file() or sha256_file(artifact) != digest:
        return False
    expected_evaluation = evaluation_cache_identity(
        artifact_sha256=digest,
        evaluator_version=str(identity.get("evaluator_version", "")),
        evaluation_settings_hash=str(identity.get("evaluation_settings_hash", "")),
    )
    return record.get("evaluation_cache_identity") == expected_evaluation
