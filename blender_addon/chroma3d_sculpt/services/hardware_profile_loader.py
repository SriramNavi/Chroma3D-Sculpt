"""Hardware-only views of the local Sprint 3 printer profile facts."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from ..models.advanced_preparation_models import HardwareProfile
from ..models.printability_models import PrintabilityConfidence, ProcessType, RuleClassification
from .printer_profile_loader import build_custom_profile, load_profile, profile_from_property_group


PACKAGED_HARDWARE_PROFILE_IDS = (
    "generic_fdm",
    "generic_resin",
    "bambu_x1_carbon",
    "bambu_p1s",
    "prusa_mk4",
)
_CAPABILITIES: dict[str, dict[str, tuple[Any, ...]]] = {
    "generic_fdm": {"nozzles": (0.2, 0.4, 0.6, 0.8, 1.0), "layers": (0.05, 0.4), "beds": ("TEXTURED", "SMOOTH", "OTHER"), "extruders": ("SINGLE",)},
    "generic_resin": {"nozzles": (0.05,), "layers": (0.01, 0.2), "beds": ("RESIN_PLATFORM",), "extruders": ("VAT_PHOTOPOLYMERIZATION",)},
    "bambu_x1_carbon": {"nozzles": (0.2, 0.4, 0.6, 0.8), "layers": (0.08, 0.4), "beds": ("TEXTURED", "SMOOTH", "OTHER"), "extruders": ("SINGLE", "HARDENED" )},
    "bambu_p1s": {"nozzles": (0.2, 0.4, 0.6, 0.8), "layers": (0.08, 0.4), "beds": ("TEXTURED", "SMOOTH", "OTHER"), "extruders": ("SINGLE",)},
    "prusa_mk4": {"nozzles": (0.25, 0.4, 0.6, 0.8), "layers": (0.05, 0.35), "beds": ("TEXTURED", "SMOOTH", "OTHER"), "extruders": ("SINGLE",)},
}


def hardware_from_legacy(profile: Any) -> HardwareProfile:
    capabilities = _CAPABILITIES.get(profile.profile_id) or {
        "nozzles": (float(profile.nozzle_diameter_mm.value),),
        "layers": (0.01, max(float(profile.nominal_layer_height_mm.value) * 2.0, 0.02)),
        "beds": ("OTHER",),
        "extruders": ("USER_CONFIGURABLE",),
    }
    payload = {
        "profile_id": profile.profile_id,
        "manufacturer": profile.manufacturer,
        "printer_model": profile.printer_model,
        "process_type": profile.process_type.value,
        "build_volume_mm": profile.build_volume_mm.dimensions,
        "nozzle_options_mm": capabilities["nozzles"],
        "layer_height_range_mm": capabilities["layers"],
        "bed_type_capabilities": capabilities["beds"],
        "extruder_capabilities": capabilities["extruders"],
        "source_references": profile.build_volume_mm.source_references,
        "confidence": profile.build_volume_mm.confidence.value,
        "hardware_only_notes": (
            "Hardware facts only; material behavior and process thresholds are composed separately.",
            "No listed capability is a print-success guarantee.",
        ),
        "source_classification": profile.build_volume_mm.classification.value,
        "safety_margin_mm": profile.dimensional_safety_margin_mm.value,
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return HardwareProfile(
        profile_id=str(payload["profile_id"]),
        manufacturer=str(payload["manufacturer"]),
        printer_model=str(payload["printer_model"]),
        process_type=ProcessType(str(payload["process_type"])),
        build_volume_mm=tuple(float(value) for value in payload["build_volume_mm"]),
        nozzle_options_mm=tuple(float(value) for value in payload["nozzle_options_mm"]),
        layer_height_range_mm=tuple(float(value) for value in payload["layer_height_range_mm"]),
        bed_type_capabilities=tuple(str(value) for value in payload["bed_type_capabilities"]),
        extruder_capabilities=tuple(str(value) for value in payload["extruder_capabilities"]),
        source_references=tuple(str(value) for value in payload["source_references"]),
        confidence=PrintabilityConfidence(str(payload["confidence"])),
        hardware_only_notes=tuple(str(value) for value in payload["hardware_only_notes"]),
        source_classification=RuleClassification(str(payload["source_classification"])),
        safety_margin_mm=float(payload["safety_margin_mm"]),
        profile_hash=digest,
    )


def load_hardware_profile(profile_id: str) -> HardwareProfile:
    return hardware_from_legacy(load_profile(profile_id))


def build_custom_hardware_profile(overrides: dict[str, Any]) -> HardwareProfile:
    return hardware_from_legacy(build_custom_profile(overrides))


def hardware_from_property_group(state: Any) -> HardwareProfile:
    return hardware_from_legacy(profile_from_property_group(state))


def validate_all_hardware_profiles() -> tuple[HardwareProfile, ...]:
    profiles = tuple(load_hardware_profile(profile_id) for profile_id in PACKAGED_HARDWARE_PROFILE_IDS)
    identifiers = [profile.profile_id for profile in profiles]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Hardware profile IDs must be unique.")
    return profiles
