"""Compare validated Chroma3D predictions with physical observations by category."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(__file__).resolve().parent
RUNS_ROOT = ROOT / "runs"
REPORTS_ROOT = ROOT / "reports"
CATEGORY_TO_CHECK = {
    "wall_thickness": "wall_thickness", "thin_features": "thin_features", "overhang": "overhangs",
    "contact_stability": "build_plate_contact", "floating_components": "floating_components",
}
SEVERITY_RANK = {"NONE": 0, "MINOR": 1, "MAJOR": 2, "CRITICAL": 3}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def safe_ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def empty_matrix() -> dict[str, Any]:
    return {"true_positive": 0, "false_positive": 0, "false_negative": 0, "true_negative": 0, "precision": None, "recall": None, "severity_agreement": None, "evaluated": 0, "excluded": 0}


def main() -> int:
    matrices = {category: empty_matrix() for category in CATEGORY_TO_CHECK}
    confidence: dict[str, dict[str, int]] = {}
    proposals: list[dict[str, Any]] = []
    completed_runs = 0
    excluded_runs = 0
    for job_path in sorted(RUNS_ROOT.glob("*/job-card.json")):
        run = load_json(job_path)
        observation_ref = run.get("observation_file")
        if run.get("overall_disposition") in {"NOT_RUN", "INVALID_EXPERIMENT"} or not observation_ref:
            excluded_runs += 1
            continue
        observation = load_json(REPOSITORY_ROOT / str(observation_ref))
        completed_runs += 1
        check_states = dict(run["predictions"]["check_states"])
        confidence_name = str(run["predictions"].get("confidence", "UNKNOWN"))
        confidence.setdefault(confidence_name, {"evaluated": 0, "agreed": 0})
        for category, check in CATEGORY_TO_CHECK.items():
            observed = observation["category_observations"][category]
            matrix = matrices[category]
            if observed["state"] != "OBSERVED" or observed["severity"] not in SEVERITY_RANK:
                matrix["excluded"] += 1
                continue
            predicted_state = check_states.get(check, "NOT_EVALUATED")
            if predicted_state not in {"PASS", "WARNING", "CRITICAL"}:
                matrix["excluded"] += 1
                continue
            predicted_positive = predicted_state in {"WARNING", "CRITICAL"}
            actual_positive = SEVERITY_RANK[observed["severity"]] > 0
            key = "true_positive" if predicted_positive and actual_positive else "false_positive" if predicted_positive else "false_negative" if actual_positive else "true_negative"
            matrix[key] += 1
            matrix["evaluated"] += 1
            predicted_severity = 2 if predicted_state == "CRITICAL" else 1 if predicted_state == "WARNING" else 0
            matrix.setdefault("severity_matches", 0)
            matrix["severity_matches"] += int(predicted_severity == SEVERITY_RANK[observed["severity"]])
            agreement = observed.get("prediction_agreement")
            confidence[confidence_name]["evaluated"] += 1
            confidence[confidence_name]["agreed"] += int(agreement == "AGREES")
            if key in {"false_positive", "false_negative"}:
                proposals.append({"run_id": run["run_id"], "category": category, "classification": key.upper(), "prediction": predicted_state, "observed_severity": observed["severity"], "cause_classification": observation["cause_classification"], "automatic_threshold_change": False})
    for matrix in matrices.values():
        matrix["precision"] = safe_ratio(matrix["true_positive"], matrix["true_positive"] + matrix["false_positive"])
        matrix["recall"] = safe_ratio(matrix["true_positive"], matrix["true_positive"] + matrix["false_negative"])
        matrix["severity_agreement"] = safe_ratio(matrix.pop("severity_matches", 0), matrix["evaluated"])
    confidence_calibration = {
        name: {**values, "agreement_rate": safe_ratio(values["agreed"], values["evaluated"])}
        for name, values in confidence.items()
    }
    report = {
        "schema_version": "1.0.0", "generated_at": utcnow(),
        "status": "NO_PHYSICAL_OBSERVATIONS" if completed_runs == 0 else "PARTIAL",
        "completed_runs": completed_runs, "excluded_runs": excluded_runs, "categories": matrices,
        "confidence_calibration": confidence_calibration,
        "threshold_sensitivity": {"status": "NOT_AVAILABLE" if completed_runs == 0 else "REQUIRES_CONTROLLED_NUMERIC_COUPON_SERIES", "automatic_production_change": False},
        "proposed_calibration_observations": proposals,
        "limitations": [
            "Statistics exclude NOT_RUN, INVALID_EXPERIMENT, INCONCLUSIVE, NOT_APPLICABLE, and non-decisive engine states.",
            "Contact/stability observations are not treated as physical simulation ground truth.",
            "No packaged profile or production threshold is changed by this analysis.",
            "At least three comparable controlled observations are required before a threshold-change proposal.",
        ],
    }
    REPORTS_ROOT.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_ROOT / "physical_comparison.json"
    markdown_path = REPORTS_ROOT / "physical_comparison.md"
    proposals_path = REPORTS_ROOT / "proposed_calibration_observations.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    proposals_path.write_text(json.dumps({"schema_version": "1.0.0", "generated_at": report["generated_at"], "observations": proposals, "automatic_threshold_change": False}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    lines = ["# Sprint 3.5 Physical Comparison", "", f"**{report['status']}**", "", f"- Completed runs: {completed_runs}", f"- Excluded/not-run runs: {excluded_runs}", "- Automatic threshold changes: 0", "", "## Category matrices", ""]
    lines.extend(f"- {name}: TP {value['true_positive']}, FP {value['false_positive']}, FN {value['false_negative']}, TN {value['true_negative']}, precision {value['precision']}, recall {value['recall']}." for name, value in matrices.items())
    lines.extend(["", "## Limitations", "", *[f"- {item}" for item in report["limitations"]], ""])
    markdown_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(json.dumps({"status": report["status"], "completed_runs": completed_runs, "excluded_runs": excluded_runs, "proposals": len(proposals)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
