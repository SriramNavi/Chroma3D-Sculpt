"""Deterministic bounded comparison of virtual orientation trade-offs."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from ..models.advanced_preparation_models import (
    BridgeRiskResult, ComposedProcessContext, OrientationComparison, ResinAdvisoryResult, SupportRiskResult,
)
from ..models.printability_models import OrientationResult, PrintabilityConfidence, PrintabilityMode, PrintabilityStatus, ProcessType
from ..performance_registry import limit_for


def _dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_values = (
        0.0 if left["build_fit"] else 1.0,
        float(left["support_risk_area_mm2"]), float(left["bridge_risk_count"]),
        float(left["height_mm"]), float(left["material_aware_risk"]), -float(left["contact_area_mm2"]),
    )
    right_values = (
        0.0 if right["build_fit"] else 1.0,
        float(right["support_risk_area_mm2"]), float(right["bridge_risk_count"]),
        float(right["height_mm"]), float(right["material_aware_risk"]), -float(right["contact_area_mm2"]),
    )
    return all(a <= b + 1e-9 for a, b in zip(left_values, right_values)) and any(a < b - 1e-9 for a, b in zip(left_values, right_values))


def compare_orientations(
    base: OrientationResult,
    process: ComposedProcessContext,
    mode: PrintabilityMode,
    triangle_count: int,
    bridges: BridgeRiskResult,
    supports: SupportRiskResult,
    resin: ResinAdvisoryResult,
) -> OrientationComparison:
    started = perf_counter()
    limit = limit_for(mode, triangle_count, "orientation_recommendations")
    if triangle_count > limit.hard_skip_limit or base.status == PrintabilityStatus.SKIPPED_LIMIT:
        return OrientationComparison(
            status=PrintabilityStatus.SKIPPED_LIMIT, confidence=PrintabilityConfidence.UNKNOWN, candidates=(),
            pareto_candidate_ids=(), deterministic_rank_ids=(), duration_seconds=perf_counter() - started,
            limitations=("Orientation comparison was skipped at the centralized performance limit; no candidate was treated as safe.",),
        )
    candidates: list[dict[str, Any]] = []
    current_overhang = 0.0
    if base.candidates:
        current = next((item for item in base.candidates if item.source.value == "CURRENT"), base.candidates[0])
        current_overhang = float(current.measurement_summary.get("warning_overhang_area_mm2", 0.0))
    for item in base.candidates[:limit.maximum_candidate_count]:
        metrics = item.measurement_summary
        overhang_area = float(metrics.get("warning_overhang_area_mm2", 0.0))
        ratio = overhang_area / current_overhang if current_overhang > 1e-9 else (1.0 if overhang_area > 0.0 else 0.0)
        bridge_count = min(bridges.candidate_region_count, max(0, round(bridges.candidate_region_count * ratio)))
        floating = int(metrics.get("floating_component_count", 0))
        contact_area = float(metrics.get("contact_area_mm2", 0.0))
        support_area = overhang_area + floating * max(overhang_area * 0.1, 1.0) + (0.0 if contact_area > 0.0 else 1.0)
        risk_modifier = (process.material_profile.overhang_risk_modifier + process.material_profile.bridge_risk_modifier) * 0.5
        material_risk = support_area * risk_modifier + bridge_count * process.material_profile.bridge_risk_modifier * 10.0
        resin_status = (
            PrintabilityStatus.WARNING.value
            if process.hardware_profile.process_type == ProcessType.RESIN and (floating or overhang_area > 0.0)
            else resin.status.value if process.hardware_profile.process_type == ProcessType.RESIN
            else PrintabilityStatus.NOT_APPLICABLE.value
        )
        candidates.append(
            {
                "candidate_id": item.candidate_id, "rotation_quaternion": item.rotation_quaternion,
                "source": item.source.value, "strategies": (), "build_fit": bool(metrics.get("fits_build_volume", False)),
                "contact_class": metrics.get("contact_classification", "INDETERMINATE"), "contact_area_mm2": contact_area,
                "overhang_risk_area_mm2": overhang_area, "support_risk_area_mm2": support_area,
                "bridge_risk_count": bridge_count, "floating_components": floating,
                "height_mm": float(metrics.get("height_mm", 0.0)), "scale_feasibility": "FEASIBLE" if metrics.get("fits_build_volume") else "REVIEW_REQUIRED",
                "material_aware_risk": material_risk, "resin_advisory_status": resin_status,
                "advantages": item.advantages, "trade_offs": item.trade_offs,
                "confidence": PrintabilityConfidence.LOW.value,
            }
        )
    if not candidates:
        return OrientationComparison(
            status=PrintabilityStatus.NOT_EVALUATED, confidence=PrintabilityConfidence.UNKNOWN, candidates=(),
            pareto_candidate_ids=(), deterministic_rank_ids=(), duration_seconds=perf_counter() - started,
            limitations=("No bounded virtual orientation candidate was available.",),
        )
    extrema = {
        "contact_maximizing": max(item["contact_area_mm2"] for item in candidates),
        "overhang_minimizing": min(item["overhang_risk_area_mm2"] for item in candidates),
        "bridge_risk_minimizing": min(item["bridge_risk_count"] for item in candidates),
        "support_risk_minimizing": min(item["support_risk_area_mm2"] for item in candidates),
        "height_minimizing": min(item["height_mm"] for item in candidates),
        "hardware_material_aware": min(item["material_aware_risk"] for item in candidates),
    }
    for item in candidates:
        strategies: list[str] = ["current_orientation"] if item["source"] == "CURRENT" else []
        for name, value in extrema.items():
            field = {
                "contact_maximizing": "contact_area_mm2", "overhang_minimizing": "overhang_risk_area_mm2",
                "bridge_risk_minimizing": "bridge_risk_count", "support_risk_minimizing": "support_risk_area_mm2",
                "height_minimizing": "height_mm", "hardware_material_aware": "material_aware_risk",
            }[name]
            if abs(float(item[field]) - float(value)) <= 1e-9:
                strategies.append(name)
        item["strategies"] = tuple(strategies)
    candidates.sort(
        key=lambda item: (
            not item["build_fit"], item["material_aware_risk"], item["support_risk_area_mm2"],
            item["bridge_risk_count"], item["height_mm"], -item["contact_area_mm2"], item["candidate_id"],
        )
    )
    for rank, item in enumerate(candidates, 1):
        item["deterministic_rank"] = rank
    pareto = tuple(item["candidate_id"] for item in candidates if not any(_dominates(other, item) for other in candidates if other is not item))
    return OrientationComparison(
        status=PrintabilityStatus.PASS, confidence=PrintabilityConfidence.LOW, candidates=tuple(candidates),
        pareto_candidate_ids=pareto, deterministic_rank_ids=tuple(item["candidate_id"] for item in candidates),
        duration_seconds=perf_counter() - started,
        limitations=(
            "All candidates are bounded mathematical what-if comparisons; they are not globally optimal and no Blender transform is applied.",
            "Per-candidate bridge and support values are conservative proxies derived from virtual downward exposure, not slicer support generation or physical simulation.",
        ),
    )
