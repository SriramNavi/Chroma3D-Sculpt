"""Advisory support-risk region aggregation; this module never generates supports."""

from __future__ import annotations

from time import perf_counter

from ..models.advanced_preparation_models import (
    BridgeRiskResult, ComposedProcessContext, ResinAdvisoryResult, SupportRiskReason, SupportRiskRegion, SupportRiskResult,
)
from ..models.printability_models import (
    BuildPlateContactResult, FloatingComponentResult, OverhangResult, PrintabilityConfidence, PrintabilityMode,
    PrintabilityStatus, ThinFeatureResult,
)
from ..performance_registry import limit_for
from .geometry_facts import GeometryContext


NEUTRAL_SUPPORT_MESSAGE = "Region likely to require support, orientation adjustment, or user review under the selected process context."


def analyze_support_risk(
    context: GeometryContext,
    process: ComposedProcessContext,
    mode: PrintabilityMode,
    overhangs: OverhangResult,
    floating: FloatingComponentResult,
    contact: BuildPlateContactResult,
    thin_features: ThinFeatureResult,
    bridges: BridgeRiskResult,
    resin: ResinAdvisoryResult | None = None,
) -> SupportRiskResult:
    started = perf_counter()
    limit = limit_for(mode, context.facts.triangle_count, "support_risk")
    if context.facts.triangle_count > limit.hard_skip_limit:
        return SupportRiskResult(
            status=PrintabilityStatus.SKIPPED_LIMIT, confidence=PrintabilityConfidence.UNKNOWN, region_count=0,
            total_risk_area_mm2=0.0, total_risk_area_percent=0.0, regions=(), evidence_faces=(),
            duration_seconds=perf_counter() - started,
            limitations=(f"Support-risk analysis skipped at the centralized {limit.hard_skip_limit:,}-triangle hard limit; skipped is not pass.",),
        )
    raw: list[dict[str, object]] = []
    for item in overhangs.regions:
        raw.append({"severity": PrintabilityStatus(item.band), "reasons": {SupportRiskReason.OVERHANG}, "area": item.area_mm2, "faces": {item.representative_face}, "confidence": overhangs.confidence})
    for item in bridges.regions:
        raw.append({"severity": item.severity, "reasons": {SupportRiskReason.BRIDGE}, "area": item.surface_area_mm2, "faces": set(item.evidence_faces), "confidence": item.confidence})
    floating_ids = set(floating.floating_shell_ids)
    for item in floating.components:
        if item.shell_id in floating_ids:
            raw.append({"severity": PrintabilityStatus.CRITICAL, "reasons": {SupportRiskReason.FLOATING_COMPONENT}, "area": item.surface_area_mm2, "faces": set(item.evidence_faces), "confidence": floating.confidence})
    if contact.status != PrintabilityStatus.PASS:
        raw.append({"severity": PrintabilityStatus.WARNING, "reasons": {SupportRiskReason.LOW_CONTACT}, "area": contact.contact_area_mm2, "faces": set(contact.evidence_faces), "confidence": contact.confidence})
    if thin_features.status in {PrintabilityStatus.WARNING, PrintabilityStatus.CRITICAL}:
        raw.append({"severity": thin_features.status, "reasons": {SupportRiskReason.FRAGILE_FEATURE}, "area": 0.0, "faces": set(), "confidence": thin_features.confidence})
    if resin and resin.checks.get("disconnected_islands", {}).get("state") == PrintabilityStatus.WARNING.value:
        raw.append({"severity": PrintabilityStatus.WARNING, "reasons": {SupportRiskReason.RESIN_ISLAND}, "area": 0.0, "faces": set(resin.evidence_faces), "confidence": resin.confidence})
    merged: list[dict[str, object]] = []
    for item in raw:
        target = next((existing for existing in merged if item["faces"] and existing["faces"] and set(item["faces"]) & set(existing["faces"])), None)
        if target is None:
            merged.append(item)
            continue
        target["reasons"] = set(target["reasons"]) | set(item["reasons"])
        target["faces"] = set(target["faces"]) | set(item["faces"])
        target["area"] = max(float(target["area"]), float(item["area"]))
        if item["severity"] == PrintabilityStatus.CRITICAL:
            target["severity"] = PrintabilityStatus.CRITICAL
    surface = max(context.facts.surface_area_mm2, 1e-12)
    regions: list[SupportRiskRegion] = []
    for item in merged[:limit.maximum_candidate_count]:
        faces = tuple(sorted(set(item["faces"])))[:limit.maximum_region_evidence]
        area = float(item["area"])
        regions.append(
            SupportRiskRegion(
                region_id=f"support-risk-region-{len(regions):04d}", severity=item["severity"],
                reason_categories=tuple(sorted(set(item["reasons"]), key=lambda value: value.value)),
                surface_area_mm2=area, total_area_percent=area / surface * 100.0,
                confidence=item["confidence"], evidence_faces=faces, message=NEUTRAL_SUPPORT_MESSAGE,
                profile_material_influence={
                    "support_policy": process.support_policy, "material_profile_id": process.material_profile.profile_id,
                    "overhang_modifier": process.material_profile.overhang_risk_modifier,
                    "support_removal_risk": process.material_profile.support_removal_risk,
                },
                limitations=("This region is advisory evidence only; support necessity and removability require slicer and user review.",),
            )
        )
    unique_faces = {face for region in regions for face in region.evidence_faces}
    total_area = sum(context.face_areas_mm2[face] for face in unique_faces if 0 <= face < len(context.face_areas_mm2))
    if any(item.severity == PrintabilityStatus.CRITICAL for item in regions):
        status = PrintabilityStatus.CRITICAL
    elif regions:
        status = PrintabilityStatus.WARNING
    elif overhangs.status in {PrintabilityStatus.FAILED, PrintabilityStatus.INDETERMINATE}:
        status = PrintabilityStatus.INDETERMINATE
    else:
        status = PrintabilityStatus.PASS
    confidence = PrintabilityConfidence.LOW if regions else PrintabilityConfidence.MEDIUM
    evidence = tuple(sorted(unique_faces))[:limit.maximum_region_evidence]
    return SupportRiskResult(
        status=status, confidence=confidence, region_count=len(regions), total_risk_area_mm2=total_area,
        total_risk_area_percent=total_area / surface * 100.0, regions=tuple(regions), evidence_faces=evidence,
        duration_seconds=perf_counter() - started,
        limitations=(
            "Support risk combines bounded geometry indicators; it does not generate supports or state that supports are definitely required.",
            NEUTRAL_SUPPORT_MESSAGE,
        ),
    )
