"""Validated local-only printer profile loading and immutable snapshots."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from typing import Any

from ..metadata import PRINTER_PROFILE_SCHEMA_VERSION
from ..models.printability_models import (
    BuildVolumeValue,
    PrintabilityConfidence,
    ProcessType,
    ProfileGuidance,
    PrinterProfile,
    RuleClassification,
    ThresholdValue,
)
from ..utilities.blender_paths import extension_root


PACKAGED_PROFILE_IDS = (
    "generic_fdm",
    "generic_resin",
    "bambu_x1_carbon",
    "bambu_p1s",
    "prusa_mk4",
)

_PROFILE_FILES = {profile_id: f"{profile_id}.json" for profile_id in PACKAGED_PROFILE_IDS}
_REQUIRED_KEYS = {
    "profile_schema_version", "profile_id", "display_name", "manufacturer", "printer_model", "process_type",
    "source_classification", "source_references", "build_volume_mm", "dimensional_safety_margin_mm",
    "nozzle_diameter_mm", "nominal_layer_height_mm", "wall_thickness_warning_mm", "wall_thickness_critical_mm",
    "minimum_feature_warning_mm", "minimum_feature_critical_mm", "overhang_warning_angle_deg",
    "overhang_critical_angle_deg", "build_plate_contact_tolerance_mm", "bridge_guidance", "support_assumption",
    "material_family", "notes", "confidence", "user_editable_fields", "created_at", "updated_at",
}
_SOURCE_RE = re.compile(r"^SRC-[0-9]{3}$")
_PROFILE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")


def profile_directory() -> Path:
    packaged = extension_root() / "profiles" / "printability"
    if packaged.is_dir():
        return packaged
    development = extension_root().parents[1] / "profiles" / "printability"
    if development.is_dir():
        return development
    raise FileNotFoundError("Packaged printability profiles are unavailable.")


def _enum(enum_type: type[Any], value: Any, field_name: str) -> Any:
    try:
        return enum_type(str(value))
    except ValueError as exc:
        raise ValueError(f"Invalid {field_name}: {value!r}") from exc


def _sources(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) != len(set(value)) or any(not _SOURCE_RE.fullmatch(str(item)) for item in value):
        raise ValueError(f"{field_name} must contain unique SRC-NNN references.")
    return tuple(str(item) for item in value)


def _boolean(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")
    return value


def _number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a JSON number.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite.")
    return number


def _positive(value: Any, field_name: str) -> float:
    number = _number(value, field_name)
    if number <= 0.0:
        raise ValueError(f"{field_name} must be finite and positive.")
    return number


def _threshold(data: Any, field_name: str, *, angle: bool = False) -> ThresholdValue:
    required = {"value", "classification", "source_references", "rationale", "confidence", "user_editable"}
    if not isinstance(data, dict) or set(data) != required:
        raise ValueError(f"{field_name} does not match the threshold schema.")
    value = _number(data["value"], f"{field_name}.value")
    if value < 0.0 or (not angle and value == 0.0):
        raise ValueError(f"{field_name}.value must be finite and {'non-negative' if angle else 'positive'}.")
    if angle and value > 90.0:
        raise ValueError(f"{field_name}.value must be in [0, 90].")
    rationale = str(data["rationale"])
    if not rationale:
        raise ValueError(f"{field_name}.rationale cannot be empty.")
    return ThresholdValue(
        value=value,
        classification=_enum(RuleClassification, data["classification"], f"{field_name}.classification"),
        source_references=_sources(data["source_references"], f"{field_name}.source_references"),
        rationale=rationale,
        confidence=_enum(PrintabilityConfidence, data["confidence"], f"{field_name}.confidence"),
        user_editable=_boolean(data["user_editable"], f"{field_name}.user_editable"),
    )


def _guidance(data: Any, field_name: str, allowed_modes: set[str]) -> ProfileGuidance:
    required = {"mode", "classification", "source_references", "description", "confidence", "user_editable"}
    if not isinstance(data, dict) or set(data) != required or str(data.get("mode")) not in allowed_modes:
        raise ValueError(f"{field_name} does not match its schema.")
    description = str(data["description"])
    if not description:
        raise ValueError(f"{field_name}.description cannot be empty.")
    return ProfileGuidance(
        mode=str(data["mode"]),
        classification=_enum(RuleClassification, data["classification"], f"{field_name}.classification"),
        source_references=_sources(data["source_references"], f"{field_name}.source_references"),
        description=description,
        confidence=_enum(PrintabilityConfidence, data["confidence"], f"{field_name}.confidence"),
        user_editable=_boolean(data["user_editable"], f"{field_name}.user_editable"),
    )


def load_profile_data(data: dict[str, Any]) -> PrinterProfile:
    if not isinstance(data, dict):
        raise ValueError("Printer profile root must be an object.")
    if set(data) != _REQUIRED_KEYS:
        missing = sorted(_REQUIRED_KEYS - set(data))
        extra = sorted(set(data) - _REQUIRED_KEYS)
        raise ValueError(f"Profile keys do not match schema; missing={missing}, extra={extra}.")
    if data["profile_schema_version"] != PRINTER_PROFILE_SCHEMA_VERSION:
        raise ValueError("Unsupported printer profile schema version.")
    profile_id = str(data["profile_id"])
    if not _PROFILE_RE.fullmatch(profile_id):
        raise ValueError("profile_id must match the approved identifier format.")
    for name in ("display_name", "manufacturer", "printer_model", "material_family"):
        if not isinstance(data[name], str) or not data[name]:
            raise ValueError(f"{name} cannot be empty.")
    if not isinstance(data["notes"], str):
        raise ValueError("notes must be a string.")
    editable_fields = data["user_editable_fields"]
    if (
        not isinstance(editable_fields, list)
        or any(not isinstance(item, str) for item in editable_fields)
        or len(editable_fields) != len(set(editable_fields))
    ):
        raise ValueError("user_editable_fields must contain unique strings.")
    for name in ("created_at", "updated_at"):
        if not isinstance(data[name], str) or not data[name]:
            raise ValueError(f"{name} must be a non-empty date-time string.")
    volume = data["build_volume_mm"]
    volume_keys = {"x", "y", "z", "unit", "classification", "source_references", "rationale", "confidence"}
    if not isinstance(volume, dict) or set(volume) != volume_keys or volume.get("unit") != "mm":
        raise ValueError("build_volume_mm does not match the approved schema.")
    build_volume = BuildVolumeValue(
        x=_positive(volume["x"], "build_volume_mm.x"),
        y=_positive(volume["y"], "build_volume_mm.y"),
        z=_positive(volume["z"], "build_volume_mm.z"),
        unit="mm",
        classification=_enum(RuleClassification, volume["classification"], "build_volume_mm.classification"),
        source_references=_sources(volume["source_references"], "build_volume_mm.source_references"),
        rationale=str(volume["rationale"]),
        confidence=_enum(PrintabilityConfidence, volume["confidence"], "build_volume_mm.confidence"),
    )
    if not build_volume.rationale:
        raise ValueError("build_volume_mm.rationale cannot be empty.")
    wall_warning = _threshold(data["wall_thickness_warning_mm"], "wall_thickness_warning_mm")
    wall_critical = _threshold(data["wall_thickness_critical_mm"], "wall_thickness_critical_mm")
    feature_warning = _threshold(data["minimum_feature_warning_mm"], "minimum_feature_warning_mm")
    feature_critical = _threshold(data["minimum_feature_critical_mm"], "minimum_feature_critical_mm")
    angle_warning = _threshold(data["overhang_warning_angle_deg"], "overhang_warning_angle_deg", angle=True)
    angle_critical = _threshold(data["overhang_critical_angle_deg"], "overhang_critical_angle_deg", angle=True)
    if wall_critical.value > wall_warning.value:
        raise ValueError("Critical wall threshold must not exceed the warning threshold.")
    if feature_critical.value > feature_warning.value:
        raise ValueError("Critical feature threshold must not exceed the warning threshold.")
    if angle_critical.value > angle_warning.value:
        raise ValueError("Critical overhang angle must not exceed the warning angle under the approved convention.")
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return PrinterProfile(
        profile_schema_version=str(data["profile_schema_version"]),
        profile_id=profile_id,
        display_name=str(data["display_name"]),
        manufacturer=str(data["manufacturer"]),
        printer_model=str(data["printer_model"]),
        process_type=_enum(ProcessType, data["process_type"], "process_type"),
        source_classification=_enum(RuleClassification, data["source_classification"], "source_classification"),
        source_references=_sources(data["source_references"], "source_references"),
        build_volume_mm=build_volume,
        dimensional_safety_margin_mm=_threshold(data["dimensional_safety_margin_mm"], "dimensional_safety_margin_mm"),
        nozzle_diameter_mm=_threshold(data["nozzle_diameter_mm"], "nozzle_diameter_mm"),
        nominal_layer_height_mm=_threshold(data["nominal_layer_height_mm"], "nominal_layer_height_mm"),
        wall_thickness_warning_mm=wall_warning,
        wall_thickness_critical_mm=wall_critical,
        minimum_feature_warning_mm=feature_warning,
        minimum_feature_critical_mm=feature_critical,
        overhang_warning_angle_deg=angle_warning,
        overhang_critical_angle_deg=angle_critical,
        build_plate_contact_tolerance_mm=_threshold(data["build_plate_contact_tolerance_mm"], "build_plate_contact_tolerance_mm"),
        bridge_guidance=_guidance(data["bridge_guidance"], "bridge_guidance", {"QUALITATIVE", "SLICER_SETTING_REQUIRED", "NOT_DEFINED"}),
        support_assumption=_guidance(data["support_assumption"], "support_assumption", {"REVIEW_REQUIRED", "ASSUME_UNSUPPORTED", "ASSUME_SUPPORTED"}),
        material_family=str(data["material_family"]),
        notes=str(data["notes"]),
        confidence=_enum(PrintabilityConfidence, data["confidence"], "confidence"),
        user_editable_fields=tuple(editable_fields),
        created_at=str(data["created_at"]),
        updated_at=str(data["updated_at"]),
        profile_hash=sha256(canonical).hexdigest(),
    )


def load_profile(profile_id: str) -> PrinterProfile:
    filename = _PROFILE_FILES.get(str(profile_id).lower())
    if filename is None:
        raise ValueError(f"Unknown packaged printer profile: {profile_id!r}")
    path = profile_directory() / filename
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not load printer profile {profile_id!r}: {type(exc).__name__}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Printer profile root must be an object.")
    profile = load_profile_data(data)
    expected_id = str(profile_id).lower()
    if profile.profile_id != expected_id:
        raise ValueError(f"Packaged profile ID mismatch: expected {expected_id!r}, found {profile.profile_id!r}.")
    return profile


def build_custom_profile(overrides: dict[str, Any]) -> PrinterProfile:
    template_path = profile_directory() / "custom_profile.template.json"
    try:
        data = json.loads(template_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not load custom profile template: {type(exc).__name__}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Custom profile template root must be an object.")
    custom = deepcopy(data)
    for key, value in overrides.items():
        if key == "build_volume_mm" and isinstance(value, (tuple, list)) and len(value) == 3:
            custom[key].update({"x": value[0], "y": value[1], "z": value[2]})
        elif key in custom and isinstance(custom[key], dict) and "value" in custom[key]:
            custom[key]["value"] = value
        elif key in {"manufacturer", "printer_model", "material_family", "notes", "process_type"}:
            custom[key] = value
        else:
            raise ValueError(f"Unsupported custom profile field: {key}")
    custom["profile_id"] = "custom_profile"
    custom["display_name"] = "Custom"
    return load_profile_data(custom)


def validate_all_packaged_profiles() -> tuple[PrinterProfile, ...]:
    profiles = tuple(load_profile(profile_id) for profile_id in PACKAGED_PROFILE_IDS)
    identifiers = [profile.profile_id for profile in profiles]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Packaged printer profile IDs must be unique.")
    return profiles


def profile_from_property_group(state: Any) -> PrinterProfile:
    profile_id = str(state.printability_profile)
    if profile_id != "custom":
        return load_profile(profile_id)
    return build_custom_profile(
        {
            "manufacturer": str(state.printability_custom_manufacturer),
            "printer_model": str(state.printability_custom_model),
            "process_type": str(state.printability_custom_process),
            "material_family": str(state.printability_custom_material),
            "build_volume_mm": (
                float(state.printability_custom_build_x_mm),
                float(state.printability_custom_build_y_mm),
                float(state.printability_custom_build_z_mm),
            ),
            "dimensional_safety_margin_mm": float(state.printability_custom_margin_mm),
            "nozzle_diameter_mm": float(state.printability_custom_nozzle_mm),
            "nominal_layer_height_mm": float(state.printability_custom_layer_mm),
            "wall_thickness_warning_mm": float(state.printability_custom_wall_warning_mm),
            "wall_thickness_critical_mm": float(state.printability_custom_wall_critical_mm),
            "minimum_feature_warning_mm": float(state.printability_custom_feature_warning_mm),
            "minimum_feature_critical_mm": float(state.printability_custom_feature_critical_mm),
            "overhang_warning_angle_deg": float(state.printability_custom_overhang_warning_deg),
            "overhang_critical_angle_deg": float(state.printability_custom_overhang_critical_deg),
            "build_plate_contact_tolerance_mm": float(state.printability_custom_contact_tolerance_mm),
        }
    )
