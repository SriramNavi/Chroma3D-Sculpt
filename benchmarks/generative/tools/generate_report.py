"""Generate dimension-first CGB reports, explicit composites, and Pareto evidence."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

from common import CGB_VERSION, read_json, stable_hash, write_json


DIMENSION_DIRECTIONS = {
    "shape_fidelity": "MAX", "geometry_health": "MAX", "detail": "MAX",
    "topology": "MAX", "printability": "MAX", "texture_pbr": "MAX",
    "latency": "MIN", "cost": "MIN", "reliability": "MAX",
}
PROJECT_DEFAULT = {
    "shape_fidelity": 30.0, "geometry_health": 25.0, "detail": 15.0,
    "topology": 10.0, "printability": 10.0, "reliability": 5.0,
    "latency": 2.5, "cost": 2.5,
}


def validate_weights(weights: Mapping[str, float]) -> None:
    if set(weights) != set(PROJECT_DEFAULT):
        raise ValueError("Weight profile must contain the exact PROJECT_DEFAULT dimensions.")
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or value < 0
        for value in weights.values()
    ):
        raise ValueError("Weights must be finite non-negative numbers.")
    if abs(sum(float(value) for value in weights.values()) - 100.0) > 1e-9:
        raise ValueError("Weight profile must total 100.")


def dominates(left: Mapping[str, float], right: Mapping[str, float], directions: Mapping[str, str]) -> bool:
    comparable = tuple(key for key in directions if key in left and key in right)
    if not comparable:
        return False
    no_worse = all(left[key] >= right[key] if directions[key] == "MAX" else left[key] <= right[key] for key in comparable)
    better = any(left[key] > right[key] if directions[key] == "MAX" else left[key] < right[key] for key in comparable)
    return no_worse and better


def pareto_frontier(rows: Iterable[Mapping[str, Any]], directions: Mapping[str, str] = DIMENSION_DIRECTIONS) -> list[str]:
    values = list(rows)
    frontier = []
    for candidate in values:
        scores = candidate.get("dimensions", {})
        if not isinstance(scores, Mapping):
            continue
        if not any(dominates(other.get("dimensions", {}), scores, directions) for other in values if other is not candidate):
            frontier.append(str(candidate["result_id"]))
    return sorted(frontier)


def _scorecard(record: Mapping[str, Any]) -> dict[str, Any]:
    raw_metrics = record.get("raw_metrics", {})
    fidelity = raw_metrics.get("shape_fidelity", {}) if isinstance(raw_metrics, Mapping) else {}
    geometry = raw_metrics.get("raw_geometry", {}) if isinstance(raw_metrics, Mapping) else {}
    conditioning = record.get("conditioning", {})
    normalized_chamfer = fidelity.get("normalized_symmetric_chamfer") if isinstance(fidelity, Mapping) else None
    shape_score = None if not isinstance(normalized_chamfer, (int, float)) else max(0.0, 100.0 * (1.0 - min(1.0, normalized_chamfer * 10.0)))
    health_score = geometry.get("geometry_health_score") if isinstance(geometry, Mapping) else None
    silhouette = raw_metrics.get("silhouette", {}).get("mean_iou") if isinstance(raw_metrics, Mapping) else None
    dimensions = {
        "shape_fidelity": shape_score,
        "geometry_health": health_score,
        "detail": None,
        "topology": health_score,
        "printability": 100.0 if isinstance(conditioning, Mapping) and conditioning.get("conditioned_metrics", {}).get("printability_state") == "PASS_WITH_LIMITATIONS" else 50.0 if conditioning else None,
        "texture_pbr": None,
        "latency": record.get("latency", {}).get("end_to_end_seconds"),
        "cost": record.get("estimated_cost_usd"),
        "reliability": 100.0 if record.get("status") == "PASS" else 0.0,
    }
    return {
        "result_id": f"{record.get('backend_id')}:{record.get('case_id')}:{record.get('attempt')}",
        "backend_id": record.get("backend_id"), "case_id": record.get("case_id"),
        "status": record.get("status"), "dimensions": dimensions,
        "supporting": {"silhouette_mean_iou": silhouette, "detail_state": "EXPERIMENTAL_EXCLUDED", "pbr_state": "CAPABILITY_ONLY"},
    }


def generate(run: Mapping[str, Any]) -> dict[str, Any]:
    validate_weights(PROJECT_DEFAULT)
    scorecards = [_scorecard(record) for record in run.get("attempts", []) if record.get("status") == "PASS"]
    ranked = [row for row in scorecards if row["backend_id"] != "fake_generator"]
    result = {
        "schema_version": "1.0.0", "cgb_version": CGB_VERSION,
        "run_id": run.get("run_id"), "primary_truth": "RAW_DIMENSIONS_AND_STATUSES",
        "dimension_directions": DIMENSION_DIRECTIONS, "scorecards": scorecards,
        "pareto_frontier": pareto_frontier(ranked),
        "project_default_profile": {
            "name": "PROJECT_DEFAULT", "scientifically_validated": False,
            "weights": PROJECT_DEFAULT, "pbr_reported_separately": True,
        },
        "winner_declarations": {},
        "decision": "G0_FRAMEWORK_COMPLETE_READY_FOR_BACKEND_EXECUTION",
        "no_model_winner_declared": True,
        "limitations": [
            "Fake-generator evidence validates infrastructure and is excluded from model rankings.",
            "No winner may be declared without genuine Smoke3 and Core10 finalist evidence.",
        ],
    }
    result["result_hash"] = stable_hash(result)
    return result


def markdown(result: Mapping[str, Any]) -> str:
    rows = []
    for card in result["scorecards"]:
        dims = card["dimensions"]
        rows.append(
            f"| {card['backend_id']} | {card['case_id']} | {card['status']} | "
            f"{_display(dims['shape_fidelity'])} | {_display(dims['geometry_health'])} | "
            f"{_display(dims['latency'])} |"
        )
    return f"""# CGB v0.1 Result Summary

Decision: `{result['decision']}`

**NO MODEL WINNER HAS BEEN DECLARED.**

Primary truth is the dimension/status matrix; the provisional `PROJECT_DEFAULT` profile is secondary and not scientifically validated.

| Backend | Case | Status | Shape fidelity | Geometry health | Latency s |
|---|---|---:|---:|---:|---:|
{chr(10).join(rows) if rows else '| NOT_RUN | NOT_RUN | NOT_RUN | - | - | - |'}

Pareto frontier (real backends only): `{', '.join(result['pareto_frontier']) or 'NOT_RUN'}`

PBR for the untextured GT27 corpus is `CAPABILITY_ONLY`. Human evaluation is `NOT_RUN`.
"""


def _display(value: Any) -> str:
    return "NOT_APPLICABLE" if value is None else f"{float(value):.6g}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_manifest", type=Path)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    result = generate(read_json(args.run_manifest))
    write_json(args.output_directory / "result.json", result)
    (args.output_directory / "summary.md").write_text(markdown(result), encoding="utf-8", newline="\n")
    print(f"CGB report PASS: scorecards={len(result['scorecards'])} pareto={len(result['pareto_frontier'])} hash={result['result_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
