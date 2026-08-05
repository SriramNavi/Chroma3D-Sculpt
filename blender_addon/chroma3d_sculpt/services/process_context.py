"""Deterministic hardware + material + process composition."""

from __future__ import annotations

from hashlib import sha256
import json
import math
from typing import Any

from ..metadata import PROCESS_CONTEXT_SCHEMA_VERSION, PRINTER_PROFILE_SCHEMA_VERSION
from ..models.advanced_preparation_models import ComposedProcessContext, HardwareProfile, MaterialProfile
from ..models.printability_models import (
    BuildVolumeValue, PrintabilityConfidence, PrinterProfile, ProcessType, ProfileGuidance, RuleClassification, ThresholdValue,
)


SUPPORT_POLICIES = {"REVIEW_REQUIRED", "ASSUME_UNSUPPORTED", "ASSUME_SUPPORTED"}
THRESHOLD_KEYS = {
    "wall_thickness_warning_mm", "wall_thickness_critical_mm", "minimum_feature_warning_mm", "minimum_feature_critical_mm",
    "overhang_warning_angle_deg", "overhang_critical_angle_deg", "bridge_warning_span_mm", "bridge_critical_span_mm",
    "build_plate_contact_tolerance_mm", "dimensional_safety_margin_mm",
}


def _positive(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a JSON number.")
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise ValueError(f"{name} must be finite and positive.")
    return number


def compose_process_context(
    hardware: HardwareProfile,
    material: MaterialProfile,
    *,
    nozzle_mm: float,
    layer_height_mm: float,
    support_policy: str = "REVIEW_REQUIRED",
    build_plate_type: str = "TEXTURED",
    user_overrides: dict[str, float | str] | None = None,
) -> ComposedProcessContext:
    nozzle = _positive(nozzle_mm, "nozzle_mm")
    layer = _positive(layer_height_mm, "layer_height_mm")
    if hardware.process_type not in material.compatible_process_types:
        raise ValueError(f"Material {material.profile_id!r} is incompatible with {hardware.process_type.value} hardware.")
    if not hardware.layer_height_range_mm[0] <= layer <= hardware.layer_height_range_mm[1]:
        raise ValueError("Layer height is outside the hardware profile range.")
    if not material.layer_height_range_mm[0] <= layer <= material.layer_height_range_mm[1]:
        raise ValueError("Layer height is outside the material profile range.")
    if not material.nozzle_range_mm[0] <= nozzle <= material.nozzle_range_mm[1]:
        raise ValueError("Nozzle is outside the material profile range.")
    if hardware.process_type == ProcessType.FDM and all(abs(nozzle - option) > 1e-9 for option in hardware.nozzle_options_mm):
        raise ValueError("Nozzle is not listed by the selected hardware profile.")
    if support_policy not in SUPPORT_POLICIES:
        raise ValueError("Unsupported support policy.")
    if not isinstance(build_plate_type, str) or not build_plate_type:
        raise ValueError("Build plate type cannot be empty.")
    if build_plate_type not in hardware.bed_type_capabilities:
        raise ValueError("Build plate type is not listed by the selected hardware profile.")
    wall_base = max(nozzle * 3.0, layer * 4.0)
    feature_base = max(nozzle * 2.0, layer * 3.0)
    thresholds = {
        "wall_thickness_warning_mm": wall_base * material.wall_thickness_multiplier,
        "wall_thickness_critical_mm": max(nozzle * 2.0, layer * 3.0) * material.wall_thickness_multiplier,
        "minimum_feature_warning_mm": feature_base * material.thin_feature_multiplier,
        "minimum_feature_critical_mm": max(nozzle * 1.125, layer * 2.0) * material.thin_feature_multiplier,
        "overhang_warning_angle_deg": max(1.0, min(90.0, 45.0 / material.overhang_risk_modifier)),
        "overhang_critical_angle_deg": max(0.0, min(90.0, 30.0 / material.overhang_risk_modifier)),
        "bridge_warning_span_mm": 5.0 / material.bridge_risk_modifier,
        "bridge_critical_span_mm": 10.0 / material.bridge_risk_modifier,
        "build_plate_contact_tolerance_mm": max(0.01, min(layer * 0.25, 0.1)),
        "dimensional_safety_margin_mm": hardware.safety_margin_mm,
    }
    overrides = dict(user_overrides or {})
    unknown = set(overrides) - THRESHOLD_KEYS
    if unknown:
        raise ValueError(f"Unsupported process override(s): {sorted(unknown)}")
    provenance: dict[str, dict[str, Any]] = {}
    for name in sorted(thresholds):
        provenance[name] = {
            "classification": (RuleClassification.USER_CONFIGURABLE if name in overrides else RuleClassification.CONSERVATIVE_HEURISTIC).value,
            "hardware_profile_id": hardware.profile_id,
            "hardware_profile_hash": hardware.profile_hash,
            "material_profile_id": material.profile_id,
            "material_profile_hash": material.profile_hash,
            "source_references": sorted(set(hardware.source_references + material.source_references)),
            "origin": "USER_OVERRIDE" if name in overrides else "COMPOSED_PROJECT_POLICY",
        }
        if name in overrides:
            thresholds[name] = _positive(overrides[name], name)
    if thresholds["wall_thickness_critical_mm"] > thresholds["wall_thickness_warning_mm"]:
        raise ValueError("Critical wall threshold cannot exceed warning threshold.")
    if thresholds["minimum_feature_critical_mm"] > thresholds["minimum_feature_warning_mm"]:
        raise ValueError("Critical feature threshold cannot exceed warning threshold.")
    if thresholds["overhang_critical_angle_deg"] > thresholds["overhang_warning_angle_deg"]:
        raise ValueError("Critical overhang angle cannot exceed warning angle.")
    warnings: list[str] = []
    if hardware.process_type == ProcessType.RESIN:
        warnings.append("The composed nozzle value is a resolution-control placeholder for resin and is not an extrusion nozzle.")
    payload = {
        "schema_version": PROCESS_CONTEXT_SCHEMA_VERSION,
        "hardware_profile": hardware.to_dict(), "material_profile": material.to_dict(),
        "nozzle_mm": nozzle, "layer_height_mm": layer, "support_policy": support_policy, "build_plate_type": build_plate_type,
        "user_overrides": overrides, "effective_thresholds": thresholds, "threshold_provenance": provenance,
        "compatibility_warnings": tuple(warnings),
        "limitations": (
            "Material values are generic project defaults or conservative heuristics and are not physically calibrated.",
            "The composed context is advisory and does not guarantee adhesion, strength, bridge success, support-free printing, or print success.",
        ),
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return ComposedProcessContext(
        schema_version=PROCESS_CONTEXT_SCHEMA_VERSION, hardware_profile=hardware, material_profile=material,
        nozzle_mm=nozzle, layer_height_mm=layer, support_policy=support_policy, build_plate_type=build_plate_type,
        user_overrides=overrides, effective_thresholds=thresholds, threshold_provenance=provenance,
        compatibility_warnings=tuple(warnings), limitations=payload["limitations"], context_hash=digest,
    )


def _threshold(value: float, context: ComposedProcessContext, name: str, *, editable: bool = True) -> ThresholdValue:
    provenance = context.threshold_provenance[name]
    return ThresholdValue(
        value=value, classification=RuleClassification(provenance["classification"]),
        source_references=tuple(provenance["source_references"]), rationale=f"Effective {name} from the composed Sprint 4 process context.",
        confidence=PrintabilityConfidence.LOW, user_editable=editable,
    )


def legacy_profile_for_context(context: ComposedProcessContext) -> PrinterProfile:
    """Adapt effective thresholds to the unchanged Sprint 3 analysis boundary."""

    hardware = context.hardware_profile
    material = context.material_profile
    values = context.effective_thresholds
    sources = tuple(sorted(set(hardware.source_references + material.source_references)))
    volume = BuildVolumeValue(
        x=hardware.build_volume_mm[0], y=hardware.build_volume_mm[1], z=hardware.build_volume_mm[2], unit="mm",
        classification=hardware.source_classification, source_references=hardware.source_references,
        rationale="Hardware-only build-volume snapshot used by the composed process context.", confidence=hardware.confidence,
    )
    return PrinterProfile(
        profile_schema_version=PRINTER_PROFILE_SCHEMA_VERSION,
        profile_id=f"composed_{hardware.profile_id}_{material.profile_id}"[:64],
        display_name=f"{hardware.printer_model} + {material.display_name}", manufacturer=hardware.manufacturer,
        printer_model=hardware.printer_model, process_type=hardware.process_type,
        source_classification=RuleClassification.CONSERVATIVE_HEURISTIC, source_references=sources, build_volume_mm=volume,
        dimensional_safety_margin_mm=_threshold(values["dimensional_safety_margin_mm"], context, "dimensional_safety_margin_mm"),
        nozzle_diameter_mm=ThresholdValue(context.nozzle_mm, RuleClassification.USER_CONFIGURABLE, sources, "Selected process nozzle or resin resolution placeholder.", PrintabilityConfidence.LOW, True),
        nominal_layer_height_mm=ThresholdValue(context.layer_height_mm, RuleClassification.USER_CONFIGURABLE, sources, "Selected layer height.", PrintabilityConfidence.LOW, True),
        wall_thickness_warning_mm=_threshold(values["wall_thickness_warning_mm"], context, "wall_thickness_warning_mm"),
        wall_thickness_critical_mm=_threshold(values["wall_thickness_critical_mm"], context, "wall_thickness_critical_mm"),
        minimum_feature_warning_mm=_threshold(values["minimum_feature_warning_mm"], context, "minimum_feature_warning_mm"),
        minimum_feature_critical_mm=_threshold(values["minimum_feature_critical_mm"], context, "minimum_feature_critical_mm"),
        overhang_warning_angle_deg=_threshold(values["overhang_warning_angle_deg"], context, "overhang_warning_angle_deg"),
        overhang_critical_angle_deg=_threshold(values["overhang_critical_angle_deg"], context, "overhang_critical_angle_deg"),
        build_plate_contact_tolerance_mm=_threshold(values["build_plate_contact_tolerance_mm"], context, "build_plate_contact_tolerance_mm"),
        bridge_guidance=ProfileGuidance("QUALITATIVE", RuleClassification.CONSERVATIVE_HEURISTIC, sources, "Bridge risk is bounded advisory geometry, not a success prediction.", PrintabilityConfidence.LOW, True),
        support_assumption=ProfileGuidance(context.support_policy, RuleClassification.USER_CONFIGURABLE, sources, "Explicit support-policy input; supports are never generated.", PrintabilityConfidence.LOW, True),
        material_family=material.material_family.value, notes="Composed transient profile; hardware and material snapshots remain separate in Sprint 4 reports.",
        confidence=PrintabilityConfidence.LOW, user_editable_fields=tuple(sorted(THRESHOLD_KEYS)),
        created_at=material.created_at, updated_at=material.updated_at, profile_hash=context.context_hash,
    )


def context_from_property_group(state: Any, hardware: HardwareProfile, material: MaterialProfile) -> ComposedProcessContext:
    return compose_process_context(
        hardware, material, nozzle_mm=float(state.preparation_nozzle_mm), layer_height_mm=float(state.preparation_layer_height_mm),
        support_policy=str(state.preparation_support_policy), build_plate_type=str(state.preparation_build_plate_type),
    )
