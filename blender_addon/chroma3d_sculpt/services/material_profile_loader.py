"""Strict local material-profile validation and immutable snapshots."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from typing import Any

from ..metadata import MATERIAL_PROFILE_SCHEMA_VERSION
from ..models.advanced_preparation_models import MaterialFamily, MaterialProfile
from ..models.printability_models import PrintabilityConfidence, ProcessType, RuleClassification
from ..utilities.blender_paths import extension_root


PACKAGED_MATERIAL_PROFILE_IDS = (
    "generic_pla", "generic_petg", "generic_abs", "generic_asa", "generic_tpu", "generic_resin_material",
)
_FILES = {
    "generic_pla": "generic_pla.json", "generic_petg": "generic_petg.json", "generic_abs": "generic_abs.json",
    "generic_asa": "generic_asa.json", "generic_tpu": "generic_tpu.json", "generic_resin_material": "generic_resin.json",
}
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
_SOURCE_RE = re.compile(r"^SRC-[0-9]{3}$")
_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH", "UNKNOWN"}
_REQUIRED = {
    "schema_version", "profile_id", "display_name", "material_family", "compatible_process_types", "source_classification",
    "source_references", "confidence", "nozzle_range_mm", "layer_height_range_mm", "wall_thickness_multiplier",
    "thin_feature_multiplier", "bridge_risk_modifier", "overhang_risk_modifier", "support_removal_risk", "warping_risk",
    "brittleness_risk", "adhesion_risk", "dimensional_change_guidance", "user_editable_fields", "notes", "created_at", "updated_at",
}
_OPTIONAL = {"manufacturer", "temperature_information", "limitations"}


def material_profile_directory() -> Path:
    packaged = extension_root() / "profiles" / "materials"
    if packaged.is_dir():
        return packaged
    development = extension_root().parents[1] / "profiles" / "materials"
    if development.is_dir():
        return development
    raise FileNotFoundError("Packaged material profiles are unavailable.")


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a JSON number, not a boolean or string.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite.")
    return result


def _positive(value: Any, name: str) -> float:
    result = _number(value, name)
    if result <= 0.0:
        raise ValueError(f"{name} must be positive.")
    return result


def _range(value: Any, name: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must contain exactly two dimensions.")
    lower, upper = (_positive(value[0], f"{name}[0]"), _positive(value[1], f"{name}[1]"))
    if lower > upper:
        raise ValueError(f"{name} lower bound cannot exceed its upper bound.")
    return (lower, upper)


def _strings(value: Any, name: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{name} must be an array of strings.")
    if len(value) != len(set(value)):
        raise ValueError(f"{name} must not contain duplicates.")
    if not allow_empty and not value:
        raise ValueError(f"{name} cannot be empty.")
    return tuple(value)


def load_material_profile_data(data: dict[str, Any]) -> MaterialProfile:
    if not isinstance(data, dict) or not _REQUIRED.issubset(data) or set(data) - _REQUIRED - _OPTIONAL:
        missing = sorted(_REQUIRED - set(data)) if isinstance(data, dict) else sorted(_REQUIRED)
        extra = sorted(set(data) - _REQUIRED - _OPTIONAL) if isinstance(data, dict) else []
        raise ValueError(f"Material profile keys do not match schema; missing={missing}, extra={extra}.")
    if data["schema_version"] != MATERIAL_PROFILE_SCHEMA_VERSION:
        raise ValueError("Unsupported material profile schema version.")
    profile_id = data["profile_id"]
    if not isinstance(profile_id, str) or not _ID_RE.fullmatch(profile_id):
        raise ValueError("Invalid material profile ID.")
    if not isinstance(data["display_name"], str) or not data["display_name"]:
        raise ValueError("Material display_name cannot be empty.")
    try:
        family = MaterialFamily(str(data["material_family"]))
        compatibility = tuple(ProcessType(str(value)) for value in _strings(data["compatible_process_types"], "compatible_process_types", allow_empty=False))
        classification = RuleClassification(str(data["source_classification"]))
        confidence = PrintabilityConfidence(str(data["confidence"]))
    except ValueError as exc:
        raise ValueError(f"Unsupported material enum value: {exc}") from exc
    if classification not in {RuleClassification.PROJECT_DEFAULT, RuleClassification.CONSERVATIVE_HEURISTIC, RuleClassification.USER_CONFIGURABLE}:
        raise ValueError("Material source classification must remain a project default, conservative heuristic, or user configuration.")
    sources = _strings(data["source_references"], "source_references")
    if any(not _SOURCE_RE.fullmatch(item) for item in sources):
        raise ValueError("Malformed material profile provenance reference.")
    for name in ("support_removal_risk", "warping_risk", "brittleness_risk", "adhesion_risk"):
        if data[name] not in _RISK_LEVELS:
            raise ValueError(f"Invalid {name} value.")
    for name in ("dimensional_change_guidance", "created_at", "updated_at"):
        if not isinstance(data[name], str) or not data[name]:
            raise ValueError(f"{name} must be a non-empty string.")
    manufacturer = data.get("manufacturer")
    temperature = data.get("temperature_information")
    if manufacturer is not None and not isinstance(manufacturer, str):
        raise ValueError("manufacturer must be a string or null.")
    if temperature is not None and not isinstance(temperature, str):
        raise ValueError("temperature_information must be a string or null.")
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return MaterialProfile(
        schema_version=MATERIAL_PROFILE_SCHEMA_VERSION,
        profile_id=profile_id,
        display_name=data["display_name"],
        material_family=family,
        manufacturer=manufacturer,
        compatible_process_types=compatibility,
        source_classification=classification,
        source_references=sources,
        confidence=confidence,
        nozzle_range_mm=_range(data["nozzle_range_mm"], "nozzle_range_mm"),
        layer_height_range_mm=_range(data["layer_height_range_mm"], "layer_height_range_mm"),
        wall_thickness_multiplier=_positive(data["wall_thickness_multiplier"], "wall_thickness_multiplier"),
        thin_feature_multiplier=_positive(data["thin_feature_multiplier"], "thin_feature_multiplier"),
        bridge_risk_modifier=_positive(data["bridge_risk_modifier"], "bridge_risk_modifier"),
        overhang_risk_modifier=_positive(data["overhang_risk_modifier"], "overhang_risk_modifier"),
        support_removal_risk=data["support_removal_risk"], warping_risk=data["warping_risk"],
        brittleness_risk=data["brittleness_risk"], adhesion_risk=data["adhesion_risk"],
        dimensional_change_guidance=data["dimensional_change_guidance"], temperature_information=temperature,
        user_editable_fields=_strings(data["user_editable_fields"], "user_editable_fields"),
        notes=_strings(data["notes"], "notes"), limitations=_strings(data.get("limitations", []), "limitations"),
        created_at=data["created_at"], updated_at=data["updated_at"], profile_hash=sha256(canonical).hexdigest(),
    )


def load_material_profile(profile_id: str) -> MaterialProfile:
    filename = _FILES.get(str(profile_id).lower())
    if filename is None:
        raise ValueError(f"Unknown packaged material profile: {profile_id!r}")
    try:
        data = json.loads((material_profile_directory() / filename).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not load material profile {profile_id!r}: {type(exc).__name__}: {exc}") from exc
    profile = load_material_profile_data(data)
    if profile.profile_id != str(profile_id).lower():
        raise ValueError("Packaged material profile ID does not match its filename registry.")
    return profile


def build_custom_material_profile(overrides: dict[str, Any]) -> MaterialProfile:
    data = json.loads((material_profile_directory() / "custom_material.template.json").read_text(encoding="utf-8"))
    custom = deepcopy(data)
    for name, value in overrides.items():
        if name not in custom or name not in custom["user_editable_fields"]:
            raise ValueError(f"Unsupported custom material field: {name}")
        custom[name] = value
    custom["profile_id"] = "custom_material"
    custom["source_classification"] = "USER_CONFIGURABLE"
    return load_material_profile_data(custom)


def validate_all_material_profiles() -> tuple[MaterialProfile, ...]:
    profiles = tuple(load_material_profile(profile_id) for profile_id in PACKAGED_MATERIAL_PROFILE_IDS)
    identifiers = [profile.profile_id for profile in profiles]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Material profile IDs must be unique.")
    return profiles


def material_from_property_group(state: Any) -> MaterialProfile:
    profile_id = str(state.preparation_material_profile)
    if profile_id != "custom_material":
        return load_material_profile(profile_id)
    return build_custom_material_profile(
        {
            "display_name": str(state.preparation_custom_material_name),
            "material_family": str(state.preparation_custom_material_family),
            "wall_thickness_multiplier": float(state.preparation_custom_wall_multiplier),
            "thin_feature_multiplier": float(state.preparation_custom_feature_multiplier),
            "bridge_risk_modifier": float(state.preparation_custom_bridge_modifier),
            "overhang_risk_modifier": float(state.preparation_custom_overhang_modifier),
        }
    )
