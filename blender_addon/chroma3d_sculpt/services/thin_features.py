"""Conservative experimental thin-feature diameter proxy."""

from __future__ import annotations

import math
from time import perf_counter

from ..models.printability_models import EvidenceState, PrintabilityConfidence, PrintabilityStatus, PrinterProfile, ThinFeatureResult
from ..printability_settings import PrintabilitySettings
from .geometry_facts import GeometryContext


def _percentiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    return {
        label: ordered[min(round((len(ordered) - 1) * fraction), len(ordered) - 1)]
        for label, fraction in (("p05", 0.05), ("p25", 0.25), ("p50", 0.5), ("p75", 0.75), ("p95", 0.95))
    }


def analyze_thin_features(
    context: GeometryContext,
    profile: PrinterProfile,
    settings: PrintabilitySettings,
) -> ThinFeatureResult:
    started = perf_counter()
    if context.facts.triangle_count > int(settings.triangle_limit or 0):
        return ThinFeatureResult(
            status=PrintabilityStatus.SKIPPED_LIMIT,
            confidence=PrintabilityConfidence.UNKNOWN,
            evidence_state=EvidenceState.UNAVAILABLE,
            duration_seconds=perf_counter() - started,
            limitations=("Thin-feature proxy was skipped at the configured triangle limit.",),
        )
    candidates: list[tuple[int, float, float]] = []
    for shell in context.shells.shells:
        positive = sorted(value for value in shell.dimensions_mm if value > 1e-9)
        if len(positive) < 3:
            continue
        aspect = positive[-1] / positive[0]
        cross_section_ratio = positive[1] / positive[0]
        if aspect >= 2.5 and cross_section_ratio <= 2.0:
            candidates.append((shell.shell_id, positive[0], positive[-1]))
    if not candidates:
        return ThinFeatureResult(
            status=PrintabilityStatus.NOT_EVALUATED,
            confidence=PrintabilityConfidence.UNKNOWN,
            evidence_state=EvidenceState.UNAVAILABLE,
            candidates_attempted=len(context.shells.shells),
            candidates_skipped=len(context.shells.shells),
            duration_seconds=perf_counter() - started,
            limitations=(
                "The Sprint 3 conservative proxy evaluates rod-like elongated connected shells only; flat plates, walls, and local features merged into a larger shell remain unsupported.",
                "Medial-axis, semantic feature recognition, strength, material, support, and slicer toolpaths are not evaluated.",
            ),
        )
    warning = profile.minimum_feature_warning_mm.value
    critical = profile.minimum_feature_critical_mm.value
    diameters = [item[1] for item in candidates]
    critical_items = [item for item in candidates if item[1] <= critical]
    warning_items = [item for item in candidates if critical < item[1] <= warning]
    status = PrintabilityStatus.CRITICAL if critical_items else PrintabilityStatus.WARNING if warning_items else PrintabilityStatus.PASS
    affected_ids = {item[0] for item in critical_items + warning_items}
    evidence_vertices = sorted(
        vertex
        for geometry in context.shells.geometries
        if geometry.shell_id in affected_ids
        for vertex in geometry.vertex_indices
    )
    centers = [
        context.shells.geometries[shell_id].centroid
        for shell_id, _diameter, _length in candidates
    ]
    cap = int(settings.evidence_cap or 1)
    return ThinFeatureResult(
        status=status,
        confidence=PrintabilityConfidence.LOW,
        evidence_state=EvidenceState.TRUNCATED if len(evidence_vertices) > cap else EvidenceState.BOUNDED,
        candidates_attempted=len(context.shells.shells),
        candidates_completed=len(candidates),
        candidates_skipped=len(context.shells.shells) - len(candidates),
        minimum_diameter_mm=min(diameters),
        percentile_diameters_mm=_percentiles(diameters),
        warning_feature_count=len(warning_items),
        critical_feature_count=len(critical_items),
        largest_affected_region_mm=max((item[2] for item in critical_items + warning_items), default=0.0),
        evidence_vertices=tuple(evidence_vertices[:cap]),
        feature_centers_mm=tuple(tuple(float(value) for value in center) for center in centers[:cap]),
        duration_seconds=perf_counter() - started,
        limitations=(
            "EXPERIMENTAL: local diameter is approximated by the minimum bounding dimension of rod-like elongated connected shells.",
            "Features merged into a larger shell, height-to-diameter effects, unsupported orientation, material, and post-processing are not modeled.",
        ),
    )
