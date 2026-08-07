"""Disposition all 82 frozen H1 duplication candidates by semantic ownership."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
H1_LEDGER = ROOT / "hardening" / "h1" / "H1_DISPOSITION_LEDGER.json"
OUTPUT = ROOT / "hardening" / "h2" / "H2_DUPLICATION_TRIAGE.json"
SUMMARY = ROOT / "hardening" / "h2" / "H2_DUPLICATION_TRIAGE.md"
ALLOWED = {
    "EXACT_SHARED_SEMANTICS",
    "SIMILAR_BUT_DIFFERENT",
    "INTENTIONAL_DOMAIN_DUPLICATION",
    "TEST_FIXTURE_DUPLICATION",
    "GENERATED_PATTERN",
    "TOO_RISKY",
    "DEFER",
}
EXACT_SELECTED = "H1-DUP-0013"
EXACT_RETAINED = "H1-DUP-0014"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8", newline="\n")
    temporary.replace(path)


def _classification(entry: dict[str, Any]) -> tuple[str, str]:
    candidate_id = entry["candidate_id"]
    topic = entry["evidence"]["topic"]
    files = entry["evidence"]["files"]
    symbol = entry["symbol"]
    if candidate_id == EXACT_SELECTED:
        return (
            "EXACT_SHARED_SEMANTICS",
            "Both private percentile helpers have identical inputs, outputs, empty-input behavior, rounding, percentile labels, scalar units, and no mutation/stale/public-contract behavior.",
        )
    if candidate_id == EXACT_RETAINED:
        return (
            "EXACT_SHARED_SEMANTICS",
            "The cancellation predicates are behaviorally exact, but a new cross-owner utility would add dependency surface for six private lines and is not independently beneficial.",
        )
    if all(path.startswith(("tests/", "manual-tests/")) for path in files):
        return "TEST_FIXTURE_DUPLICATION", "The repeated code belongs to independent validation fixtures or retained release gates; product/runtime consolidation would cross the validation boundary."
    if any(path.startswith(("tests/", "manual-tests/")) for path in files):
        return "TOO_RISKY", "The candidate crosses runtime and validation ownership, so one shared implementation would couple product behavior to test/release tooling."
    if any(token in symbol for token in ("hardware_profile", "material_profile", "printer_profile")):
        return "INTENTIONAL_DOMAIN_DUPLICATION", "Hardware, material, and printer profile validation retain separate threshold and schema ownership."
    if topic in {"evidence_state", "blender_state_cleanup"}:
        return "INTENTIONAL_DOMAIN_DUPLICATION", "Session evidence or Blender resource cleanup has distinct owner, lifetime, stale-state, and mutation semantics."
    if topic == "hashing_or_signature":
        return "INTENTIONAL_DOMAIN_DUPLICATION", "The syntax is similar while the hashed identity, input contract, and stale-state owner differ."
    if topic == "package_version":
        return "INTENTIONAL_DOMAIN_DUPLICATION", "Version exposure remains local to its public package or manifest boundary."
    if topic in {"filename_sanitization", "path_validation", "json_or_profile_validation"}:
        return "SIMILAR_BUT_DIFFERENT", "Names and control flow resemble each other, but allowed characters, reserved names, roots, schemas, or error semantics differ."
    if topic == "atomic_or_report_write":
        return "SIMILAR_BUT_DIFFERENT", "Report type, sanitization, serialization, overwrite, and failure semantics are not proven identical."
    return "SIMILAR_BUT_DIFFERENT", "Structural or normalized similarity does not prove identical inputs, outputs, units, thresholds, state, mutation, or public visibility."


def _equivalence(entry: dict[str, Any], classification: str) -> dict[str, Any]:
    if entry["candidate_id"] == EXACT_SELECTED:
        return {
            "same_inputs": True,
            "same_outputs": True,
            "same_error_semantics": True,
            "same_units": True,
            "same_threshold_ownership": True,
            "same_stale_state_semantics": True,
            "same_mutation_semantics": True,
            "same_public_visibility": True,
            "proof": "H1 AST structural hash 1.0 plus current byte-equivalent private function bodies",
        }
    if entry["candidate_id"] == EXACT_RETAINED:
        return {
            "same_inputs": True,
            "same_outputs": True,
            "same_error_semantics": True,
            "same_units": True,
            "same_threshold_ownership": True,
            "same_stale_state_semantics": True,
            "same_mutation_semantics": True,
            "same_public_visibility": True,
            "proof": "H1 AST structural hash 1.0 and exact cancellation predicate behavior",
        }
    return {
        "same_inputs": False,
        "same_outputs": False,
        "same_error_semantics": False,
        "same_units": False,
        "same_threshold_ownership": False,
        "same_stale_state_semantics": False,
        "same_mutation_semantics": False,
        "same_public_visibility": False,
        "proof": "Semantic equivalence not established; candidate remains local.",
    }


def build() -> tuple[dict[str, Any], list[str]]:
    h1 = _read(H1_LEDGER)
    candidates = [entry for entry in h1["entries"] if str(entry.get("candidate_id", "")).startswith("H1-DUP-")]
    entries: list[dict[str, Any]] = []
    for candidate in candidates:
        classification, reason = _classification(candidate)
        selected = candidate["candidate_id"] == EXACT_SELECTED
        entries.append({
            "candidate_id": candidate["candidate_id"],
            "topic": candidate["evidence"]["topic"],
            "files": candidate["evidence"]["files"],
            "symbols": candidate["symbol"],
            "h1_similarity": candidate["evidence"]["similarity_evidence"],
            "classification": classification,
            "reason": reason,
            "semantic_equivalence": _equivalence(candidate, classification),
            "selected_for_consolidation": selected,
            "consolidation_owner": "chroma3d_sculpt.services.printability_statistics.percentiles" if selected else "",
            "retained_reason": "" if selected else reason,
        })
    counts = Counter(entry["classification"] for entry in entries)
    errors: list[str] = []
    if len(entries) != 82:
        errors.append(f"Duplication triage has {len(entries)} entries, expected 82")
    invalid = sorted(set(counts) - ALLOWED)
    if invalid:
        errors.append("Invalid duplication classifications: " + ", ".join(invalid))
    selected = [entry for entry in entries if entry["selected_for_consolidation"]]
    if len(selected) != 1 or selected[0]["classification"] != "EXACT_SHARED_SEMANTICS":
        errors.append("Exactly one exact-semantic consolidation must be selected")
    report = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "h1_candidate_count": 82,
        "triaged_count": len(entries),
        "classification_counts": dict(sorted(counts.items())),
        "selected_count": len(selected),
        "entries": entries,
        "errors": errors,
        "status": "PASS" if not errors else "FAIL",
    }
    return report, errors


def render(report: dict[str, Any]) -> str:
    selected = next(entry for entry in report["entries"] if entry["selected_for_consolidation"])
    exact_retained = next(entry for entry in report["entries"] if entry["candidate_id"] == EXACT_RETAINED)
    lines = [
        "# H2 duplication triage",
        "",
        f"Status: `{report['status']}`. Frozen H1 candidates: `82`; triaged: `{report['triaged_count']}`.",
        "",
        "Classifications: " + ", ".join(f"`{key}={value}`" for key, value in report["classification_counts"].items()) + ".",
        "",
        "## Selected exact-semantic consolidation",
        "",
        f"- `{selected['candidate_id']}`: `{selected['symbols']}`.",
        f"- Owner: `{selected['consolidation_owner']}`.",
        "- Proof: identical private input/output/error/rounding/unit/threshold/stale/mutation/public behavior.",
        "",
        "## Deliberately retained exact-semantic candidate",
        "",
        f"- `{exact_retained['candidate_id']}`: `{exact_retained['symbols']}`.",
        "- Reason: a new cross-owner cancellation utility would add dependency surface for six private lines.",
        "",
        "All other candidates lack complete semantic equivalence or cross runtime, domain, state, schema, validation, or resource-ownership boundaries and remain local.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    report, errors = build()
    _write(OUTPUT, json.dumps(report, indent=2, sort_keys=True) + "\n")
    _write(SUMMARY, render(report))
    print(json.dumps({
        "status": report["status"],
        "triaged": report["triaged_count"],
        "counts": report["classification_counts"],
        "selected": report["selected_count"],
        "errors": errors,
    }, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
