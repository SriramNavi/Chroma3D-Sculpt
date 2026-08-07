"""Build deterministic provider-hidden local human-review packets and reveal maps."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Iterable, Mapping

from common import CGB_VERSION, read_json, stable_hash, write_json


RATING_FIELDS = (
    "reference_resemblance", "fine_detail_quality", "artifact_severity",
    "visual_appeal", "model_completeness",
)


def anonymize(entries: Iterable[Mapping[str, Any]], *, salt: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if len(salt) < 8:
        raise ValueError("Blind-review salt must contain at least 8 characters.")
    packet_entries, reveal = [], {}
    for entry in entries:
        backend_id = str(entry["backend_id"])
        case_id = str(entry["case_id"])
        token = "B-" + hashlib.sha256(f"{salt}:{backend_id}".encode()).hexdigest()[:10].upper()
        reveal[token] = {"backend_id": backend_id, "provider": entry.get("provider"), "model_version": entry.get("model_version")}
        packet_entries.append({
            "case_id": case_id, "backend_token": token,
            "canonical_renders": list(entry.get("canonical_renders", [])),
            "ratings": {field: None for field in RATING_FIELDS}, "review_status": "NOT_RUN",
        })
    packet_entries.sort(key=lambda item: hashlib.sha256(f"{salt}:{item['case_id']}:{item['backend_token']}".encode()).hexdigest())
    packet = {
        "schema_version": "1.0.0", "cgb_version": CGB_VERSION,
        "human_evaluation": "NOT_RUN", "provider_hidden": True,
        "rating_scale": {"minimum": 1, "maximum": 5}, "rating_fields": list(RATING_FIELDS),
        "entries": packet_entries,
    }
    reveal_map = {"schema_version": "1.0.0", "reveal_only_after_scoring": True, "tokens": reveal}
    packet["packet_hash"] = stable_hash(packet)
    reveal_map["reveal_hash"] = stable_hash(reveal_map)
    return packet, reveal_map


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON array of backend/case/render entries")
    parser.add_argument("--salt", required=True)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--reveal-map", type=Path, required=True)
    args = parser.parse_args()
    entries = read_json(args.input)
    if not isinstance(entries, list):
        raise SystemExit("Input must be a JSON array.")
    packet, reveal = anonymize(entries, salt=args.salt)
    write_json(args.packet, packet)
    write_json(args.reveal_map, reveal)
    print(f"CGB blind packet PASS: entries={len(packet['entries'])} human_evaluation=NOT_RUN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
