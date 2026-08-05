"""Read-only Sprint 4 orchestration above the unchanged Sprint 3 engine."""

from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from ..feature_flags import build_feature_flags
from ..metadata import (
    ADVANCED_PREPARATION_REPORT_SCHEMA_VERSION, DISPLAY_VERSION, PERFORMANCE_REGISTRY_VERSION,
)
from ..models.advanced_preparation_models import (
    AdvancedPreparationResult, AdvancedScaleRecommendation, BridgeRiskResult, ComposedProcessContext,
    FeatureFlagSet, HardwareProfile, MaterialProfile, OrientationComparison, ProcessContextSnapshot,
    ResinAdvisoryResult, ScaleInterval, SupportRiskResult,
)
from ..models.printability_models import PrintabilityConfidence, PrintabilityStatus
from ..printability_settings import PrintabilitySettings
from ..utilities.printability_signatures import printability_source_snapshot, source_is_unchanged
from .advanced_orientation import compare_orientations
from .advanced_scale import recommend_scale
from .bridge_risk import analyze_bridge_risk
from .geometry_facts import build_geometry_facts
from .printability_coordinator import analyze_printability
from .process_context import legacy_profile_for_context
from .resin_advisory import analyze_resin_advisory
from .support_risk import analyze_support_risk


_BASE_FLAG_CHECKS = {
    "wall_thickness": "wall_thickness",
    "thin_features": "thin_features",
    "overhangs": "overhangs",
    "floating_components": "floating_components",
    "build_plate_contact": "build_contact",
    "build_volume_and_scale": "scale_evaluation",
    "orientation": "orientation_recommendations",
}


def _disabled_bridge() -> BridgeRiskResult:
    return BridgeRiskResult(PrintabilityStatus.NOT_EVALUATED, PrintabilityConfidence.UNKNOWN, 0, (), (), 0.0, ("Bridge risk is disabled by the recorded feature-flag snapshot.",))


def _disabled_support() -> SupportRiskResult:
    return SupportRiskResult(PrintabilityStatus.NOT_EVALUATED, PrintabilityConfidence.UNKNOWN, 0, 0.0, 0.0, (), (), 0.0, ("Support risk is disabled by the recorded feature-flag snapshot.",))


def _disabled_resin() -> ResinAdvisoryResult:
    return ResinAdvisoryResult(PrintabilityStatus.NOT_EVALUATED, PrintabilityConfidence.UNKNOWN, {}, (), 0.0, ("Resin advisory is disabled by the recorded feature-flag snapshot.",))


def _disabled_scale() -> AdvancedScaleRecommendation:
    return AdvancedScaleRecommendation(
        PrintabilityStatus.NOT_EVALUATED, PrintabilityConfidence.UNKNOWN, 0.0, None, None,
        ScaleInterval(None, None, "NOT_EVALUATED"), None, (), (), ("Scale evaluation is disabled by the recorded feature-flag snapshot.",),
    )


def _disabled_orientation() -> OrientationComparison:
    return OrientationComparison(PrintabilityStatus.NOT_EVALUATED, PrintabilityConfidence.UNKNOWN, (), (), (), 0.0, ("Orientation comparison is disabled by the recorded feature-flag snapshot.",))


def _masked_base_payload(base: Any, flags: FeatureFlagSet) -> tuple[dict[str, Any], tuple[dict[str, str], ...]]:
    payload = base.to_dict()
    disabled: list[dict[str, str]] = []
    for check in payload["check_results"]:
        flag_name = _BASE_FLAG_CHECKS.get(check["check"])
        if flag_name and not bool(getattr(flags, flag_name)):
            check.clear()
            check.update({"check": next(name for name, flag in _BASE_FLAG_CHECKS.items() if flag == flag_name), "status": "NOT_EVALUATED", "confidence": "UNKNOWN", "reason": f"Disabled by feature flag {flag_name}."})
            disabled.append({"check": flag_name, "state": "NOT_EVALUATED", "reason": "Disabled by explicit Sprint 4 feature flag."})
    payload["skipped_checks"] = list(payload.get("skipped_checks", [])) + disabled
    return payload, tuple(disabled)


def analyze_advanced_preparation(
    obj: Any,
    scene: Any,
    hardware: HardwareProfile,
    material: MaterialProfile,
    process: ComposedProcessContext,
    flags: FeatureFlagSet | None = None,
    settings: PrintabilitySettings | None = None,
    *,
    blender_version: str = "",
    blend_file_path: str = "",
) -> AdvancedPreparationResult:
    started = perf_counter()
    if process.hardware_profile.profile_hash != hardware.profile_hash:
        raise ValueError("Composed process context does not match the selected hardware profile.")
    if process.material_profile.profile_hash != material.profile_hash:
        raise ValueError("Composed process context does not match the selected material profile.")
    active_flags = flags or build_feature_flags()
    legacy_profile = legacy_profile_for_context(process)
    effective_settings = (settings or PrintabilitySettings()).resolved(legacy_profile)
    source_before = printability_source_snapshot(obj, blend_file_path)
    base = analyze_printability(
        obj, scene, legacy_profile, effective_settings, blender_version=blender_version, blend_file_path=blend_file_path,
    )
    context_started = perf_counter()
    geometry = build_geometry_facts(obj, scene, effective_settings)
    context_seconds = perf_counter() - context_started
    bridge = analyze_bridge_risk(geometry, process, effective_settings.mode, effective_settings.normalized_build_direction()) if active_flags.bridge_risk else _disabled_bridge()
    resin = (
        analyze_resin_advisory(geometry, process, effective_settings.mode, base.overhangs, base.floating_components, base.build_plate_contact, effective_settings.normalized_build_direction())
        if active_flags.resin_advisory else _disabled_resin()
    )
    support = (
        analyze_support_risk(
            geometry, process, effective_settings.mode, base.overhangs, base.floating_components,
            base.build_plate_contact, base.thin_features, bridge, resin,
        )
        if active_flags.support_risk else _disabled_support()
    )
    scale = recommend_scale(base, process) if active_flags.scale_evaluation else _disabled_scale()
    orientation = (
        compare_orientations(base.orientation, process, effective_settings.mode, geometry.facts.triangle_count, bridge, support, resin)
        if active_flags.orientation_recommendations else _disabled_orientation()
    )
    if not source_is_unchanged(obj, source_before, blend_file_path):
        raise RuntimeError("Advanced preparation changed protected source or saved-file state; result was rejected.")
    base_payload, disabled = _masked_base_payload(base, active_flags)
    skipped = list(disabled)
    failed: list[dict[str, str]] = []
    advanced_checks = {
        "bridge_risk": bridge.status, "support_risk": support.status,
        "resin_advisory": resin.status, "advanced_scale": scale.status, "orientation_comparison": orientation.status,
    }
    for name, status in advanced_checks.items():
        if status in {PrintabilityStatus.NOT_EVALUATED, PrintabilityStatus.SKIPPED_LIMIT}:
            skipped.append({"check": name, "state": status.value, "reason": "See the check limitations and feature-flag snapshot."})
        elif status == PrintabilityStatus.FAILED:
            failed.append({"check": name, "state": status.value, "reason": "The check failed without source mutation."})
    status = base.score_details.status
    considered = [value for value in advanced_checks.values() if value != PrintabilityStatus.NOT_APPLICABLE]
    if failed:
        status = PrintabilityStatus.FAILED
    elif any(value == PrintabilityStatus.CRITICAL for value in considered):
        status = PrintabilityStatus.CRITICAL
    elif disabled or any(value in {PrintabilityStatus.NOT_EVALUATED, PrintabilityStatus.SKIPPED_LIMIT, PrintabilityStatus.INDETERMINATE} for value in considered):
        status = PrintabilityStatus.INDETERMINATE
    elif status == PrintabilityStatus.PASS and any(value == PrintabilityStatus.WARNING for value in considered):
        status = PrintabilityStatus.WARNING
    score = None if disabled else base.score_details.score
    confidence = PrintabilityConfidence.UNKNOWN if failed else PrintabilityConfidence.LOW
    warnings = list(process.compatibility_warnings) + list(scale.warnings)
    if active_flags.experimental_material_modifiers:
        warnings.append("Experimental material modifiers are explicitly enabled; interpret non-geometric material risk annotations conservatively.")
    timings = {
        "base_printability": base.timings["total"], "geometry_context": context_seconds,
        "bridge_risk": bridge.duration_seconds, "support_risk": support.duration_seconds,
        "resin_advisory": resin.duration_seconds, "orientation_comparison": orientation.duration_seconds,
        "total": perf_counter() - started,
    }
    return AdvancedPreparationResult(
        report_schema_version=ADVANCED_PREPARATION_REPORT_SCHEMA_VERSION, extension_version=DISPLAY_VERSION,
        preparation_run_id=str(uuid4()), analyzed_at=datetime.now(timezone.utc).isoformat(),
        object_metadata={
            **base.object_metadata, "hardware_profile_id": hardware.profile_id, "material_profile_id": material.profile_id,
            "object_identity": int(obj.as_pointer()), "mesh_identity": int(obj.data.as_pointer()),
        },
        geometry_signature=base.geometry_signature, transform_signature=base.transform_signature,
        source_signature=str(source_before["printability_sha256"]), process_context_snapshot=ProcessContextSnapshot(process),
        feature_flags=active_flags, performance_registry_version=PERFORMANCE_REGISTRY_VERSION,
        performance_mode=effective_settings.mode, base_printability=base_payload,
        bridge_risk=bridge, support_risk=support, resin_advisory=resin,
        scale_recommendation=scale, orientation_comparison=orientation,
        score=score, status=status, confidence=confidence, timings=timings,
        skipped_checks=tuple(skipped), failed_checks=tuple(failed), warnings=tuple(warnings),
        limitations=(
            "Software-only advisory preparation; no print-success, support-free, bridge, adhesion, strength, time, usage, or physical calibration guarantee is made.",
            "No geometry, transform, modifier, material, collection, visibility, object property, file-save state, support, slice, G-code, upload, or printer state is changed.",
            "Orientation and scale comparisons are bounded mathematical previews and are never applied automatically.",
        ),
    )
