"""Verify the canonical baseline's deterministic identity and record structure."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import re
import sys


HASH = re.compile(r"^[0-9a-f]{64}$")


def implementation_fingerprint(repository: Path) -> str:
    root = repository / "blender_addon" / "chroma3d_sculpt"
    digest = sha256()
    for source in sorted(root.rglob("*.py"), key=lambda item: item.relative_to(root).as_posix()):
        digest.update(source.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(source.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def main() -> int:
    path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).with_name("baseline_manifest.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    if payload.get("schema_version") != "1.0" or payload.get("baseline_version") != "1.0.0":
        errors.append("Unsupported baseline version")
    records = payload.get("records", [])
    ids = [item.get("model_id") for item in records]
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        errors.append("Record IDs are not sorted and unique")
    dataset = payload.get("dataset", {})
    software = payload.get("software", {})
    process = payload.get("process_context", {})
    flags = payload.get("feature_flags", {})
    if dataset.get("model_count") != len(records):
        errors.append("Dataset model count does not match baseline records")
    if not HASH.fullmatch(str(process.get("context_hash", ""))):
        errors.append("Malformed process-context hash")
    if not HASH.fullmatch(str(flags.get("flag_hash", ""))):
        errors.append("Malformed feature-flag hash")
    repository = Path(__file__).resolve().parents[2]
    if software.get("implementation_fingerprint") != implementation_fingerprint(repository):
        errors.append("Baseline implementation fingerprint is not current")
    for item in records:
        if not HASH.fullmatch(str(item.get("source_sha256", ""))) or not HASH.fullmatch(str(item.get("process_context_hash", ""))):
            errors.append(f"Malformed hash: {item.get('model_id')}")
        if item.get("process_context_hash") != process.get("context_hash"):
            errors.append(f"Mismatched process-context hash: {item.get('model_id')}")
        if item.get("feature_flags", {}).get("flag_hash") != flags.get("flag_hash"):
            errors.append(f"Mismatched feature-flag hash: {item.get('model_id')}")
        if not isinstance(item.get("per_check_states"), dict):
            errors.append(f"Missing check states: {item.get('model_id')}")
    if payload.get("physical_validation_status") != "READY_FOR_PHYSICAL_EXECUTION":
        errors.append("Physical status is not truthful")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Printability Baseline 1.0.0 verified: {len(records)} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
