"""Resumable per-model Sprint 6 worker with real Blender strategy evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]


def atomic_write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--blender", type=Path)
    parser.add_argument("--mode", choices=("representative-mutation", "full-nondestructive"), default="full-nondestructive")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--blender-version", default="")
    parser.add_argument("--implementation-fingerprint", default="sprint6-intelligent-optimization-1.2-verification")
    args = parser.parse_args()
    source = args.source.resolve() if args.source else None
    if source is None or not source.is_file():
        atomic_write(args.output, {"schema_version": "1.0", "model_id": args.model_id, "status": "NOT_EVALUATED", "workflow_mode": args.mode, "reason": "Source asset is unavailable.", "recorded_at": datetime.now(timezone.utc).isoformat()})
        return 0
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if args.output.is_file():
        try:
            previous = json.loads(args.output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}
        required = (previous.get("source_sha256") == digest, previous.get("implementation_fingerprint") == args.implementation_fingerprint, previous.get("workflow_mode") == args.mode, previous.get("blender_version") == args.blender_version, previous.get("status") == "PASS", previous.get("source_immutability") is True)
        if all(required):
            return 0
    if args.blender is None or not args.blender.is_file():
        atomic_write(args.output, {"schema_version": "1.0", "model_id": args.model_id, "status": "NOT_EVALUATED", "workflow_mode": args.mode, "source_sha256": digest, "implementation_fingerprint": args.implementation_fingerprint, "reason": "Blender executable is unavailable for the real strategy worker.", "recorded_at": datetime.now(timezone.utc).isoformat()})
        return 0
    with tempfile.TemporaryDirectory(prefix=f"chroma3d-s6-worker-{args.model_id}-") as temporary:
        temporary_output = Path(temporary) / "result.json"
        runner = Path(__file__).with_name("dataset_blender_worker.py")
        command = [str(args.blender), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(runner), "--", "--model-id", args.model_id, "--source", str(source), "--output", str(temporary_output), "--mode", args.mode, "--implementation-fingerprint", args.implementation_fingerprint]
        try:
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=args.timeout_seconds, check=False)
        except subprocess.TimeoutExpired as exc:
            atomic_write(args.output, {"schema_version": "1.0", "model_id": args.model_id, "status": "TIMEOUT", "workflow_mode": args.mode, "source_sha256": digest, "implementation_fingerprint": args.implementation_fingerprint, "error": f"Exceeded per-model timeout of {args.timeout_seconds} seconds.", "stdout_tail": str(exc.stdout or "")[-2000:], "stderr_tail": str(exc.stderr or "")[-2000:], "recorded_at": datetime.now(timezone.utc).isoformat()})
            return 1
        if completed.returncode != 0 or not temporary_output.is_file():
            atomic_write(args.output, {"schema_version": "1.0", "model_id": args.model_id, "status": "FAIL", "workflow_mode": args.mode, "source_sha256": digest, "implementation_fingerprint": args.implementation_fingerprint, "error": f"Blender worker exited {completed.returncode} without a result.", "stdout_tail": completed.stdout[-2000:], "stderr_tail": completed.stderr[-2000:], "recorded_at": datetime.now(timezone.utc).isoformat()})
            return 1
        result = json.loads(temporary_output.read_text(encoding="utf-8"))
        result["source_sha256_file"] = digest
        result["implementation_fingerprint"] = args.implementation_fingerprint
        atomic_write(args.output, result)
        return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
