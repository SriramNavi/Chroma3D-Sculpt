"""Bounded resin-specific geometry advisories with no physical-force simulation."""

from __future__ import annotations

from time import perf_counter

from mathutils import Vector

from ..models.advanced_preparation_models import ComposedProcessContext, ResinAdvisoryResult
from ..models.printability_models import (
    BuildPlateContactResult, FloatingComponentResult, OverhangResult, PrintabilityConfidence, PrintabilityMode,
    PrintabilityStatus, ProcessType,
)
from ..performance_registry import limit_for
from .geometry_facts import GeometryContext


def _check(state: PrintabilityStatus, value: object, limitation: str) -> dict[str, object]:
    return {"state": state.value, "classification": "EXPERIMENTAL", "value": value, "limitation": limitation}


def analyze_resin_advisory(
    context: GeometryContext,
    process: ComposedProcessContext,
    mode: PrintabilityMode,
    overhangs: OverhangResult,
    floating: FloatingComponentResult,
    contact: BuildPlateContactResult,
    build_direction: tuple[float, float, float] = (0.0, 0.0, 1.0),
) -> ResinAdvisoryResult:
    started = perf_counter()
    if process.hardware_profile.process_type != ProcessType.RESIN:
        return ResinAdvisoryResult(
            status=PrintabilityStatus.NOT_APPLICABLE, confidence=PrintabilityConfidence.UNKNOWN, checks={}, evidence_faces=(),
            duration_seconds=perf_counter() - started,
            limitations=("Resin advisories are not active outside a composed resin process context.",),
        )
    limit = limit_for(mode, context.facts.triangle_count, "resin_advisory")
    if context.facts.triangle_count > limit.hard_skip_limit:
        return ResinAdvisoryResult(
            status=PrintabilityStatus.SKIPPED_LIMIT, confidence=PrintabilityConfidence.UNKNOWN, checks={}, evidence_faces=(),
            duration_seconds=perf_counter() - started,
            limitations=(f"Resin advisory skipped at the centralized {limit.hard_skip_limit:,}-triangle hard limit.",),
        )
    floating_count = len(floating.floating_shell_ids)
    hollow_indicator = context.facts.shell_count > 1 and context.facts.watertight
    topology_sufficient = context.facts.non_manifold_edges == 0
    boundary_open = context.facts.boundary_edges > 0
    direction = Vector(build_direction).normalized()
    layer = max(process.layer_height_mm, 1e-6)
    bins: dict[int, float] = {}
    for face_index, centroid in enumerate(context.face_centroids_mm):
        bin_index = int(float(centroid.dot(direction)) / layer)
        projected = context.face_areas_mm2[face_index] * abs(float(context.face_normals[face_index].dot(direction)))
        bins[bin_index] = bins.get(bin_index, 0.0) + projected
    maximum_section = max(bins.values(), default=0.0)
    plate_area = process.hardware_profile.build_volume_mm[0] * process.hardware_profile.build_volume_mm[1]
    large_section = maximum_section > plate_area * 0.25
    downward_cup = boundary_open and overhangs.warning_area_mm2 > 0.0
    checks = {
        "disconnected_islands": _check(PrintabilityStatus.WARNING if floating_count else PrintabilityStatus.PASS, floating_count, "Disconnected shells are an island proxy, not a layer-by-layer resin support solution."),
        "downward_cups": _check(PrintabilityStatus.WARNING if downward_cup else PrintabilityStatus.NOT_EVALUATED if not topology_sufficient else PrintabilityStatus.PASS, downward_cup, "Cup detection is a boundary/downward-surface indicator; drainage and suction are not simulated."),
        "enclosed_cavity_indicators": _check(PrintabilityStatus.WARNING if hollow_indicator else PrintabilityStatus.NOT_EVALUATED if not topology_sufficient else PrintabilityStatus.PASS, hollow_indicator, "Nested-shell geometry is only an enclosed-cavity indicator."),
        "hollow_shell_indicators": _check(PrintabilityStatus.WARNING if hollow_indicator else PrintabilityStatus.PASS, hollow_indicator, "Multiple closed shells are a hollow-shell proxy and do not prove intentional hollowing."),
        "trapped_volume_candidates": _check(PrintabilityStatus.WARNING if hollow_indicator and not boundary_open else PrintabilityStatus.NOT_EVALUATED if not topology_sufficient else PrintabilityStatus.PASS, hollow_indicator and not boundary_open, "Trapped volume is not calculated; only closed nested-shell evidence is reported."),
        "no_visible_drain_opening_candidate": _check(PrintabilityStatus.WARNING if hollow_indicator and not boundary_open else PrintabilityStatus.NOT_EVALUATED if not hollow_indicator else PrintabilityStatus.PASS, hollow_indicator and not boundary_open, "No drain hole is added and visibility of a viable drainage path is not guaranteed."),
        "large_cross_section_proxy": _check(PrintabilityStatus.WARNING if large_section else PrintabilityStatus.PASS, maximum_section, "Cross-sectional projected area is a geometric proxy, not peel-force or suction calculation."),
        "build_plate_contact": _check(PrintabilityStatus.PASS if contact.status == PrintabilityStatus.PASS else PrintabilityStatus.WARNING, contact.classification.value, "Contact geometry does not guarantee resin adhesion."),
        "orientation_sensitivity": _check(PrintabilityStatus.WARNING if floating_count or overhangs.warning_area_percent > 20.0 else PrintabilityStatus.PASS, {"floating_components": floating_count, "downward_area_percent": overhangs.warning_area_percent}, "Orientation sensitivity is bounded and does not identify a globally optimal orientation."),
    }
    states = {item["state"] for item in checks.values()}
    status = PrintabilityStatus.WARNING if PrintabilityStatus.WARNING.value in states else PrintabilityStatus.INDETERMINATE if PrintabilityStatus.NOT_EVALUATED.value in states else PrintabilityStatus.PASS
    evidence = tuple(sorted(set(overhangs.evidence_faces + tuple(face for item in floating.components for face in item.evidence_faces))))[:limit.maximum_region_evidence]
    return ResinAdvisoryResult(
        status=status, confidence=PrintabilityConfidence.LOW, checks=checks, evidence_faces=evidence,
        duration_seconds=perf_counter() - started,
        limitations=(
            "ADVISORY / EXPERIMENTAL geometry only; no hollowing, drain holes, supports, resin calibration, fluid simulation, suction simulation, or real peel-force calculation is performed.",
            "Insufficient topology or geometry returns NOT_EVALUATED rather than a successful zero finding.",
        ),
    )
