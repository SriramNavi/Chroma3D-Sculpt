"""Printability Baseline 1.0.0 records, verification, and regression comparison."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

from ..metadata import (
    DATASET_VERSION, DISPLAY_VERSION, GOLDEN_BENCHMARK_VERSION, PRINTABILITY_BASELINE_SCHEMA_VERSION,
    PRINTABILITY_BASELINE_VERSION,
)
from ..models.advanced_preparation_models import (
    AdvancedPreparationResult, ComposedProcessContext, FeatureFlagSet, PrintabilityBaselineRecord,
    RegressionComparison, RegressionState,
)
from ..utilities.blender_paths import extension_root


_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_FAILURE_STATES = {"FAILED", "CRITICAL"}
_SKIP_STATES = {"NOT_EVALUATED", "SKIPPED_LIMIT", "INDETERMINATE"}


def implementation_fingerprint() -> str:
    root = extension_root()
    digest = sha256()
    for path in sorted(root.rglob("*.py"), key=lambda item: item.relative_to(root).as_posix()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def baseline_record(model_id: str, source_sha256: str, result: AdvancedPreparationResult) -> PrintabilityBaselineRecord:
    if not isinstance(model_id, str) or not model_id:
        raise ValueError("Baseline model ID cannot be empty.")
    if not _HASH_RE.fullmatch(source_sha256):
        raise ValueError("Baseline source SHA-256 is malformed.")
    base_states = {item["check"]: item.get("status", "NOT_EVALUATED") for item in result.base_printability["check_results"]}
    base_states.update(
        {
            "bridge_risk": result.bridge_risk.status.value, "support_risk": result.support_risk.status.value,
            "resin_advisory": result.resin_advisory.status.value, "advanced_scale": result.scale_recommendation.status.value,
            "orientation_comparison": result.orientation_comparison.status.value,
        }
    )
    return PrintabilityBaselineRecord(
        model_id=model_id, source_sha256=source_sha256,
        process_context_hash=result.process_context_snapshot.context.context_hash,
        feature_flags=result.feature_flags.to_dict(), score=result.score, status=result.status.value,
        confidence=result.confidence.value, per_check_states=base_states,
        bridge_risks={"state": result.bridge_risk.status.value, "candidate_count": result.bridge_risk.candidate_region_count,
                      "spans_mm": [item.projected_unsupported_distance_mm for item in result.bridge_risk.regions]},
        support_risk_areas={"state": result.support_risk.status.value, "area_mm2": result.support_risk.total_risk_area_mm2,
                            "area_percent": result.support_risk.total_risk_area_percent, "region_count": result.support_risk.region_count},
        resin_advisory_states={name: item.get("state") for name, item in result.resin_advisory.checks.items()},
        scale_interval=result.scale_recommendation.recommended_interval.to_dict(),
        orientation_candidates=tuple(
            {"candidate_id": item["candidate_id"], "rank": item["deterministic_rank"], "status": item["resin_advisory_status"]}
            for item in result.orientation_comparison.candidates
        ),
        timings=dict(result.timings), limitations=result.limitations,
    )


def generate_baseline_manifest(
    records: list[PrintabilityBaselineRecord] | tuple[PrintabilityBaselineRecord, ...],
    process: ComposedProcessContext,
    flags: FeatureFlagSet,
    *,
    blender_version: str,
    dataset_manifest_sha256: str,
    golden_manifest_sha256: str,
    status: str = "VALIDATED",
    generated_at: str | None = None,
) -> dict[str, Any]:
    if status not in {"PROPOSED", "VALIDATED", "FROZEN"}:
        raise ValueError("Unsupported baseline status.")
    if not _HASH_RE.fullmatch(dataset_manifest_sha256) or not _HASH_RE.fullmatch(golden_manifest_sha256):
        raise ValueError("Dataset and Golden Benchmark manifest hashes must be SHA-256 values.")
    ordered = sorted(records, key=lambda item: item.model_id)
    if len({item.model_id for item in ordered}) != len(ordered):
        raise ValueError("Baseline model IDs must be unique.")
    payload = {
        "schema_version": PRINTABILITY_BASELINE_SCHEMA_VERSION, "baseline_version": PRINTABILITY_BASELINE_VERSION,
        "status": status, "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "software": {"extension_version": DISPLAY_VERSION, "implementation_fingerprint": implementation_fingerprint(), "blender_version": blender_version},
        "dataset": {"version": DATASET_VERSION, "manifest_sha256": dataset_manifest_sha256, "model_count": len(ordered)},
        "golden_benchmark": {"version": GOLDEN_BENCHMARK_VERSION, "manifest_sha256": golden_manifest_sha256},
        "process_context": process.to_dict(), "feature_flags": flags.to_dict(),
        "records": [item.to_dict() for item in ordered], "physical_validation_status": "READY_FOR_PHYSICAL_EXECUTION",
        "limitations": [
            "Printability Baseline 1.0.0 is software regression evidence and is not physically calibrated.",
            "Skipped, indeterminate, not-evaluated, and failed states remain explicit and are never normalized to pass.",
        ],
    }
    verify_baseline_manifest(payload)
    return payload


def verify_baseline_manifest(payload: dict[str, Any]) -> None:
    required = {"schema_version", "baseline_version", "status", "generated_at", "software", "dataset", "golden_benchmark", "process_context", "feature_flags", "records", "physical_validation_status", "limitations"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError("Baseline manifest keys do not match schema 1.0.")
    if payload["schema_version"] != PRINTABILITY_BASELINE_SCHEMA_VERSION or payload["baseline_version"] != PRINTABILITY_BASELINE_VERSION:
        raise ValueError("Unsupported baseline schema or version.")
    if payload["status"] not in {"PROPOSED", "VALIDATED", "FROZEN"}:
        raise ValueError("Unsupported baseline status.")
    if payload["physical_validation_status"] != "READY_FOR_PHYSICAL_EXECUTION":
        raise ValueError("Sprint 4 baseline cannot fabricate physical completion.")
    software = payload["software"]
    if not isinstance(software, dict) or set(software) != {"extension_version", "implementation_fingerprint", "blender_version"}:
        raise ValueError("Baseline software identity does not match schema 1.0.")
    if not _HASH_RE.fullmatch(str(software["implementation_fingerprint"])):
        raise ValueError("Baseline implementation fingerprint is malformed.")
    dataset = payload["dataset"]
    if not isinstance(dataset, dict) or set(dataset) != {"version", "manifest_sha256", "model_count"}:
        raise ValueError("Baseline dataset identity does not match schema 1.0.")
    golden = payload["golden_benchmark"]
    if not isinstance(golden, dict) or set(golden) != {"version", "manifest_sha256"}:
        raise ValueError("Baseline Golden Benchmark identity does not match schema 1.0.")
    if not _HASH_RE.fullmatch(str(dataset["manifest_sha256"])) or not _HASH_RE.fullmatch(str(golden["manifest_sha256"])):
        raise ValueError("Baseline dataset or Golden Benchmark hash is malformed.")
    process = payload["process_context"]
    flags = payload["feature_flags"]
    if not isinstance(process, dict) or not _HASH_RE.fullmatch(str(process.get("context_hash", ""))):
        raise ValueError("Baseline process-context identity is malformed.")
    if not isinstance(flags, dict) or not _HASH_RE.fullmatch(str(flags.get("flag_hash", ""))):
        raise ValueError("Baseline feature-flag identity is malformed.")
    records = payload["records"]
    if not isinstance(records, list) or len({item.get("model_id") for item in records}) != len(records):
        raise ValueError("Baseline records must be a unique model list.")
    if isinstance(dataset.get("model_count"), bool) or dataset.get("model_count") != len(records):
        raise ValueError("Baseline dataset model count does not match its records.")
    if records != sorted(records, key=lambda item: item["model_id"]):
        raise ValueError("Baseline records must use deterministic model ordering.")
    for item in records:
        if not _HASH_RE.fullmatch(str(item.get("source_sha256", ""))) or not _HASH_RE.fullmatch(str(item.get("process_context_hash", ""))):
            raise ValueError("Baseline record source/context hash is malformed.")
        if item["process_context_hash"] != process["context_hash"]:
            raise ValueError("Baseline record process-context hash does not match the manifest snapshot.")
        record_flags = item.get("feature_flags")
        if not isinstance(record_flags, dict) or record_flags.get("flag_hash") != flags["flag_hash"]:
            raise ValueError("Baseline record feature-flag hash does not match the manifest snapshot.")
        if not isinstance(item.get("per_check_states"), dict):
            raise ValueError("Baseline record check states are required.")


def write_baseline_manifest(payload: dict[str, Any], destination: Path) -> Path:
    verify_baseline_manifest(payload)
    path = destination.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)
    return path


def _change(kind: str, field: str, before: Any, after: Any, severity: RegressionState) -> dict[str, Any]:
    return {"mode": kind, "field": field, "baseline": before, "current": after, "state": severity.value}


def compare_records(
    baseline: dict[str, Any], current: dict[str, Any], *, score_tolerance: float = 1.0,
    numeric_relative_tolerance: float = 0.02, timing_relative_tolerance: float = 0.5,
) -> RegressionComparison:
    model_id = str(current.get("model_id") or baseline.get("model_id") or "unknown")
    changes: list[dict[str, Any]] = []
    for field in ("source_sha256", "process_context_hash"):
        if baseline.get(field) != current.get(field):
            changes.append(_change("exact_invariant", field, baseline.get(field), current.get(field), RegressionState.FAIL))
    before_states = baseline.get("per_check_states", {})
    after_states = current.get("per_check_states", {})
    for check in sorted(set(before_states) | set(after_states)):
        before, after = before_states.get(check), after_states.get(check)
        if before == after:
            continue
        if before not in _FAILURE_STATES and after in _FAILURE_STATES:
            kind, severity = "new_failure", RegressionState.FAIL
        elif before in _FAILURE_STATES and after not in _FAILURE_STATES:
            kind, severity = "removed_failure", RegressionState.REVIEW_REQUIRED
        elif (before in _SKIP_STATES) != (after in _SKIP_STATES):
            kind, severity = "skipped_state_change", RegressionState.FAIL if after in _SKIP_STATES else RegressionState.REVIEW_REQUIRED
        else:
            kind, severity = "classification_change", RegressionState.FAIL
        changes.append(_change(kind, f"per_check_states.{check}", before, after, severity))
    before_score, after_score = baseline.get("score"), current.get("score")
    if before_score is None or after_score is None:
        if before_score != after_score:
            changes.append(_change("score_drift", "score", before_score, after_score, RegressionState.FAIL))
    elif abs(float(after_score) - float(before_score)) > score_tolerance:
        changes.append(_change("score_drift", "score", before_score, after_score, RegressionState.FAIL if after_score < before_score else RegressionState.REVIEW_REQUIRED))
    for field in ("area_mm2", "area_percent"):
        before = baseline.get("support_risk_areas", {}).get(field)
        after = current.get("support_risk_areas", {}).get(field)
        if isinstance(before, (int, float)) and isinstance(after, (int, float)):
            tolerance = max(abs(float(before)) * numeric_relative_tolerance, 1e-6)
            if abs(float(after) - float(before)) > tolerance:
                changes.append(_change("allowed_numeric_drift", f"support_risk_areas.{field}", before, after, RegressionState.WARNING))
    before_rank = [item.get("candidate_id") for item in baseline.get("orientation_candidates", [])]
    after_rank = [item.get("candidate_id") for item in current.get("orientation_candidates", [])]
    if before_rank != after_rank:
        changes.append(_change("candidate_ranking_drift", "orientation_candidates", before_rank, after_rank, RegressionState.REVIEW_REQUIRED))
    for name in sorted(set(baseline.get("timings", {})) & set(current.get("timings", {}))):
        before, after = baseline["timings"][name], current["timings"][name]
        if isinstance(before, (int, float)) and isinstance(after, (int, float)) and after > before * (1.0 + timing_relative_tolerance) + 0.05:
            changes.append(_change("timing_drift", f"timings.{name}", before, after, RegressionState.WARNING))
    priorities = {RegressionState.PASS: 0, RegressionState.WARNING: 1, RegressionState.REVIEW_REQUIRED: 2, RegressionState.FAIL: 3}
    state = max((RegressionState(item["state"]) for item in changes), key=lambda item: priorities[item], default=RegressionState.PASS)
    return RegressionComparison(model_id, state, tuple(changes), "No regression detected." if not changes else f"{len(changes)} comparison change(s) require the recorded response.")


def compare_baseline_manifests(baseline: dict[str, Any], current: dict[str, Any]) -> tuple[RegressionComparison, ...]:
    verify_baseline_manifest(baseline)
    verify_baseline_manifest(current)
    before = {item["model_id"]: item for item in baseline["records"]}
    after = {item["model_id"]: item for item in current["records"]}
    comparisons: list[RegressionComparison] = []
    for model_id in sorted(set(before) | set(after)):
        if model_id not in before:
            comparisons.append(RegressionComparison(model_id, RegressionState.REVIEW_REQUIRED, ({"mode": "new_model", "state": "REVIEW_REQUIRED"},), "New model requires baseline review."))
        elif model_id not in after:
            comparisons.append(RegressionComparison(model_id, RegressionState.FAIL, ({"mode": "missing_model", "state": "FAIL"},), "Baseline model is missing from the current run."))
        else:
            comparisons.append(compare_records(before[model_id], after[model_id]))
    return tuple(comparisons)
