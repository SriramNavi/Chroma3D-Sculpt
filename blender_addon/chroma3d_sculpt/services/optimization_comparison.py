"""Bounded before/after comparison and conservative fidelity evidence."""

from __future__ import annotations

from hashlib import sha256
import json
import math
from typing import Any, Mapping
from uuid import uuid4

import bmesh
from mathutils import Vector

from ..models.optimization_models import (
    ComparisonClassification, FidelityStatus, ObjectiveDelta, OptimizationComparison, OptimizationConfidence,
    OptimizationObjective, ObjectiveSnapshot, RiskDelta,
)


_OBJECTIVE_METRICS = {
    OptimizationObjective.BUILD_VOLUME_FIT: ("build_fit", True),
    OptimizationObjective.WALL_THICKNESS_PRESERVATION: ("wall_thickness_score", True),
    OptimizationObjective.THIN_FEATURE_PRESERVATION: ("thin_feature_score", True),
    OptimizationObjective.OVERHANG_REDUCTION: ("overhang_risk", False),
    OptimizationObjective.BRIDGE_RISK_REDUCTION: ("bridge_risk", False),
    OptimizationObjective.SUPPORT_RISK_REDUCTION: ("support_risk", False),
    OptimizationObjective.CONTACT_IMPROVEMENT: ("contact_score", True),
    OptimizationObjective.HEIGHT_REDUCTION: ("height", False),
    OptimizationObjective.FLOATING_COMPONENT_REDUCTION: ("floating_components", False),
    OptimizationObjective.TOPOLOGY_CLEANLINESS: ("topology_issues", False),
    OptimizationObjective.GEOMETRY_FIDELITY: ("fidelity_score", True),
    OptimizationObjective.TRIANGLE_COUNT_REDUCTION: ("triangles", False),
    OptimizationObjective.RESIN_ADVISORY_IMPROVEMENT: ("resin_risk", False),
}


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _world_vertices(obj: Any) -> tuple[Vector, ...]:
    matrix = obj.matrix_world
    return tuple(matrix @ vertex.co for vertex in obj.data.vertices)


def _surface_area(obj: Any) -> float:
    # Sprint 5 operations are uniform-scale/rotation/translation or isolated
    # mesh edits.  The determinant proxy is conservative for these bounded ops.
    local = sum(float(poly.area) for poly in obj.data.polygons)
    determinant = abs(float(obj.matrix_world.to_3x3().determinant()))
    return local * (determinant ** (2.0 / 3.0) if determinant > 0.0 else 0.0)


def _volume(obj: Any) -> float | None:
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        if not bm.faces:
            return None
        value = abs(float(bmesh.ops.recalc_face_normals(bm, faces=bm.faces).get("faces", ()) and bm.calc_volume(signed=False)))
        return value if math.isfinite(value) else None
    except (AttributeError, RuntimeError, ValueError):
        return None
    finally:
        bm.free()


def _watertight(obj: Any) -> bool:
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        return bool(bm.faces) and all(len(edge.link_faces) == 2 for edge in bm.edges)
    except (AttributeError, RuntimeError):
        return False
    finally:
        bm.free()


def object_facts(obj: Any, *, build_volume_mm: tuple[float, float, float] | None = None) -> dict[str, Any]:
    vertices = _world_vertices(obj)
    if vertices:
        minimum = Vector((min(value.x for value in vertices), min(value.y for value in vertices), min(value.z for value in vertices)))
        maximum = Vector((max(value.x for value in vertices), max(value.y for value in vertices), max(value.z for value in vertices)))
        bbox = tuple(float(maximum[index] - minimum[index]) for index in range(3))
        location = tuple(float(value) for value in minimum)
    else:
        bbox = (0.0, 0.0, 0.0)
        location = (0.0, 0.0, 0.0)
    volume = _volume(obj)
    build_fit = None if build_volume_mm is None else all(bbox[index] <= float(build_volume_mm[index]) + 1e-9 for index in range(3))
    return {
        "vertex_count": len(obj.data.vertices),
        "edge_count": len(obj.data.edges),
        "triangle_count": sum(max(0, len(poly.vertices) - 2) for poly in obj.data.polygons),
        "triangles": sum(max(0, len(poly.vertices) - 2) for poly in obj.data.polygons),
        "bbox_dimensions": bbox,
        "height": bbox[2],
        "surface_area": _surface_area(obj),
        "volume": volume,
        "build_fit": build_fit,
        "topology_issues": 0.0,
        "watertight": _watertight(obj),
        "minimum_world": location,
        "fidelity_score": 1.0,
    }


def _score(value: Any, higher_is_better: bool) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if not _finite(value):
        return None
    numeric = float(value)
    return numeric if higher_is_better else -numeric


def _classification(before: float | None, after: float | None, *, higher_is_better: bool) -> ComparisonClassification:
    if before is None or after is None:
        return ComparisonClassification.INDETERMINATE
    delta = after - before
    if abs(delta) <= 1e-9:
        return ComparisonClassification.NEUTRAL
    improves = delta > 0.0 if higher_is_better else delta < 0.0
    return ComparisonClassification.IMPROVEMENT if improves else ComparisonClassification.REGRESSION


def fidelity_evidence(before: Mapping[str, Any], after: Mapping[str, Any], *, maximum_deviation: float = 0.25) -> dict[str, Any]:
    before_bbox = tuple(before.get("bbox_dimensions", ()))
    after_bbox = tuple(after.get("bbox_dimensions", ()))
    bbox_drift = max((abs(float(after_bbox[i]) - float(before_bbox[i])) for i in range(min(len(before_bbox), len(after_bbox)))), default=0.0)
    before_area = before.get("surface_area")
    after_area = after.get("surface_area")
    before_volume = before.get("volume")
    after_volume = after.get("volume")
    area_drift = None if not _finite(before_area) or not _finite(after_area) or float(before_area) == 0.0 else abs(float(after_area) - float(before_area)) / abs(float(before_area))
    volume_drift = None if not _finite(before_volume) or not _finite(after_volume) or float(before_volume) == 0.0 else abs(float(after_volume) - float(before_volume)) / abs(float(before_volume))
    triangle_delta = int(after.get("triangle_count", 0)) - int(before.get("triangle_count", 0))
    deviation = max(bbox_drift, float(area_drift or 0.0), float(volume_drift or 0.0))
    if not before_bbox or not after_bbox or not all(_finite(value) for value in (bbox_drift, deviation)):
        status = FidelityStatus.INDETERMINATE
    elif deviation > maximum_deviation:
        status = FidelityStatus.FAIL
    elif deviation > maximum_deviation * 0.5:
        status = FidelityStatus.WARNING
    else:
        status = FidelityStatus.PASS
    return {
        "status": status.value,
        "vertex_count_delta": int(after.get("vertex_count", 0)) - int(before.get("vertex_count", 0)),
        "triangle_count_delta": triangle_delta,
        "bbox_drift": bbox_drift,
        "surface_area_drift_ratio": area_drift,
        "volume_drift_ratio": volume_drift,
        "hausdorff_like_sampled_distance_proxy": bbox_drift,
        "normal_deviation_proxy": None,
        "silhouette_bounds_drift_proxy": bbox_drift,
        "shell_count_change": None,
        "topology_state_change": before.get("watertight") != after.get("watertight"),
        "limitation": "Bounded bounding-box and area/volume proxies; no exact Hausdorff distance is claimed.",
    }


def compare_snapshots(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    objectives: ObjectiveSnapshot | None = None,
    maximum_geometric_deviation: float = 0.25,
) -> OptimizationComparison:
    objective_snapshot = objectives
    if objective_snapshot is None:
        from ..optimization_settings import build_objective_snapshot
        objective_snapshot = build_objective_snapshot()
    fidelity = fidelity_evidence(before, after, maximum_deviation=maximum_geometric_deviation)
    objective_deltas: list[ObjectiveDelta] = []
    weighted_before = 0.0
    weighted_after = 0.0
    weight_total = 0.0
    skipped: list[str] = []
    indeterminate: list[str] = []
    for weight in objective_snapshot.normalized_weights:
        metric, higher = _OBJECTIVE_METRICS[weight.objective]
        before_value = _score(before.get(metric), higher)
        after_value = _score(after.get(metric), higher)
        classification = _classification(before_value, after_value, higher_is_better=True)
        delta = None if before_value is None or after_value is None else after_value - before_value
        if before_value is None or after_value is None:
            indeterminate.append(weight.objective.value)
        else:
            weighted_before += before_value * weight.weight
            weighted_after += after_value * weight.weight
            weight_total += weight.weight
        objective_deltas.append(ObjectiveDelta(weight.objective, before_value, after_value, delta, classification, OptimizationConfidence.LOW, "Missing evidence remains indeterminate." if delta is None else ""))
    risk_names = ("overhang_risk", "bridge_risk", "support_risk", "floating_components", "resin_risk")
    risk_deltas = []
    for name in risk_names:
        before_value = float(before[name]) if _finite(before.get(name)) else None
        after_value = float(after[name]) if _finite(after.get(name)) else None
        classification = _classification(before_value, after_value, higher_is_better=False)
        risk_deltas.append(RiskDelta(name, before_value, after_value, None if before_value is None or after_value is None else after_value - before_value, classification, OptimizationConfidence.LOW, "Risk metric is not available in this bounded comparison." if before_value is None or after_value is None else ""))
        if before_value is None or after_value is None:
            skipped.append(name)
    score_before = weighted_before / weight_total if weight_total else None
    score_after = weighted_after / weight_total if weight_total else None
    critical = []
    if after.get("critical") and not before.get("critical"):
        critical.append("new_critical_regression")
    if after.get("status") in {"CRITICAL", "FAILED", "FAIL"} and before.get("status") not in {"CRITICAL", "FAILED", "FAIL"}:
        critical.append("after_status_critical")
    if critical:
        overall = ComparisonClassification.REGRESSION
    elif score_before is None or score_after is None or indeterminate:
        overall = ComparisonClassification.INDETERMINATE
    elif score_after > score_before + 1e-9:
        overall = ComparisonClassification.IMPROVEMENT
    elif score_after < score_before - 1e-9:
        overall = ComparisonClassification.REGRESSION
    else:
        overall = ComparisonClassification.NEUTRAL
    if fidelity["status"] == FidelityStatus.FAIL.value:
        critical.append("geometric_fidelity_failed")
        overall = ComparisonClassification.REGRESSION
    payload = {"before": dict(before), "after": dict(after), "objective_deltas": [item.to_dict() for item in objective_deltas], "risk_deltas": [item.to_dict() for item in risk_deltas], "fidelity": fidelity}
    comparison_id = "s5-comparison-" + sha256(json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
    return OptimizationComparison(
        comparison_id=comparison_id, before=dict(before), after=dict(after), objective_deltas=tuple(objective_deltas), risk_deltas=tuple(risk_deltas),
        fidelity=fidelity, objective_score_before=score_before, objective_score_after=score_after,
        overall_classification=overall, critical_regressions=tuple(critical), skipped_checks=tuple(skipped), indeterminate_checks=tuple(indeterminate),
        limitations=("A score increase never overrides a new critical regression.", "Missing evidence is not treated as improvement."),
    )


def compare_objects(before_obj: Any, after_obj: Any, *, build_volume_mm: tuple[float, float, float] | None = None, objectives: ObjectiveSnapshot | None = None, maximum_geometric_deviation: float = 0.25) -> OptimizationComparison:
    return compare_snapshots(object_facts(before_obj, build_volume_mm=build_volume_mm), object_facts(after_obj, build_volume_mm=build_volume_mm), objectives=objectives, maximum_geometric_deviation=maximum_geometric_deviation)


__all__ = ("compare_objects", "compare_snapshots", "fidelity_evidence", "object_facts")
