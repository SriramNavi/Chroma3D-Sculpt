"""Centralized bounded settings for Sprint 3 printability analysis."""

from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
import math
from typing import Any

from .metadata import PRINTABILITY_SETTINGS_SCHEMA_VERSION, SCORING_POLICY_VERSION
from .models.printability_models import PrintabilityMode, PrintabilitySettingsSnapshot, PrinterProfile
from .performance_registry import legacy_mode_limits


MODE_LIMITS: dict[PrintabilityMode, tuple[int, int, int, int]] = {
    mode: legacy_mode_limits(mode) for mode in PrintabilityMode
}

DEFAULT_ORIENTATION_WEIGHTS = {
    "fit": 0.20,
    "contact": 0.20,
    "overhang": 0.25,
    "floating": 0.15,
    "height": 0.10,
    "stability": 0.10,
}


@dataclass(frozen=True, slots=True)
class PrintabilitySettings:
    mode: PrintabilityMode = PrintabilityMode.STANDARD
    build_direction: tuple[float, float, float] = (0.0, 0.0, 1.0)
    wall_sample_limit: int | None = None
    triangle_limit: int | None = None
    orientation_candidate_limit: int | None = None
    evidence_cap: int | None = None
    ray_origin_offset_mm: float = 0.001
    maximum_wall_search_distance_mm: float = 100.0
    contact_tolerance_mm: float | None = None
    contact_region_tolerance_mm: float = 0.05
    small_face_area_mm2: float = 0.01
    overhang_region_area_threshold_mm2: float = 0.05
    opposing_normal_dot_max: float = -0.2
    exact_boundary_tolerance_mm: float = 1e-4
    principal_axis_candidates_enabled: bool = True
    planar_face_candidates_enabled: bool = True
    sampled_candidates_enabled: bool = False
    orientation_weights: tuple[tuple[str, float], ...] = tuple(DEFAULT_ORIENTATION_WEIGHTS.items())
    cancellation_enabled: bool = True

    def resolved(self, profile: PrinterProfile) -> "PrintabilitySettings":
        defaults = MODE_LIMITS[self.mode]
        resolved = replace(
            self,
            wall_sample_limit=self.wall_sample_limit or defaults[0],
            triangle_limit=self.triangle_limit or defaults[1],
            orientation_candidate_limit=self.orientation_candidate_limit or defaults[2],
            evidence_cap=self.evidence_cap or defaults[3],
            contact_tolerance_mm=self.contact_tolerance_mm or profile.build_plate_contact_tolerance_mm.value,
        )
        resolved.validate()
        return resolved

    def normalized_build_direction(self) -> tuple[float, float, float]:
        values = tuple(float(value) for value in self.build_direction)
        length = math.sqrt(sum(value * value for value in values))
        if len(values) != 3 or not math.isfinite(length) or length <= 1e-12:
            raise ValueError("Build direction must be a finite non-zero 3D vector.")
        return tuple(value / length for value in values)  # type: ignore[return-value]

    def validate(self) -> None:
        self.normalized_build_direction()
        for name in ("wall_sample_limit", "triangle_limit", "orientation_candidate_limit", "evidence_cap"):
            value = getattr(self, name)
            if value is None or int(value) <= 0:
                raise ValueError(f"{name} must be a positive integer after mode resolution.")
        if int(self.orientation_candidate_limit or 0) > 128:
            raise ValueError("orientation_candidate_limit cannot exceed 128.")
        for name in (
            "ray_origin_offset_mm",
            "maximum_wall_search_distance_mm",
            "contact_tolerance_mm",
            "contact_region_tolerance_mm",
            "exact_boundary_tolerance_mm",
        ):
            value = getattr(self, name)
            if value is None or not math.isfinite(float(value)) or float(value) <= 0.0:
                raise ValueError(f"{name} must be finite and positive.")
        if self.small_face_area_mm2 < 0.0 or self.overhang_region_area_threshold_mm2 < 0.0:
            raise ValueError("Area thresholds cannot be negative.")
        if not -1.0 <= self.opposing_normal_dot_max < 0.0:
            raise ValueError("opposing_normal_dot_max must be in [-1, 0).")
        weights = dict(self.orientation_weights)
        if set(weights) != set(DEFAULT_ORIENTATION_WEIGHTS):
            raise ValueError("Orientation weights must contain the approved category keys.")
        if any(not math.isfinite(value) or value < 0.0 for value in weights.values()):
            raise ValueError("Orientation weights must be finite and non-negative.")
        if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9):
            raise ValueError("Orientation weights must total 1.0.")

    def snapshot(self, profile: PrinterProfile) -> PrintabilitySettingsSnapshot:
        effective = self.resolved(profile)
        payload: dict[str, Any] = {
            "settings_schema_version": PRINTABILITY_SETTINGS_SCHEMA_VERSION,
            "performance_mode": effective.mode.value,
            "build_direction": effective.normalized_build_direction(),
            "wall_sample_limit": effective.wall_sample_limit,
            "triangle_limit": effective.triangle_limit,
            "orientation_candidate_limit": effective.orientation_candidate_limit,
            "evidence_cap": effective.evidence_cap,
            "ray_origin_offset_mm": effective.ray_origin_offset_mm,
            "maximum_wall_search_distance_mm": effective.maximum_wall_search_distance_mm,
            "contact_tolerance_mm": effective.contact_tolerance_mm,
            "contact_region_tolerance_mm": effective.contact_region_tolerance_mm,
            "small_face_area_mm2": effective.small_face_area_mm2,
            "overhang_region_area_threshold_mm2": effective.overhang_region_area_threshold_mm2,
            "opposing_normal_dot_max": effective.opposing_normal_dot_max,
            "exact_boundary_tolerance_mm": effective.exact_boundary_tolerance_mm,
            "principal_axis_candidates_enabled": effective.principal_axis_candidates_enabled,
            "planar_face_candidates_enabled": effective.planar_face_candidates_enabled,
            "sampled_candidates_enabled": effective.sampled_candidates_enabled,
            "orientation_weights": dict(effective.orientation_weights),
            "support_assumption": profile.support_assumption.mode,
            "weights_version": SCORING_POLICY_VERSION,
            "cancellation_enabled": effective.cancellation_enabled,
        }
        digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        return PrintabilitySettingsSnapshot(**payload, settings_hash=digest)  # type: ignore[arg-type]


def settings_from_property_group(state: Any) -> PrintabilitySettings:
    """Build an immutable settings object from the Blender UI state."""

    mode = PrintabilityMode(str(state.printability_mode))
    defaults = MODE_LIMITS[mode]
    return PrintabilitySettings(
        mode=mode,
        build_direction=(
            float(state.printability_build_direction_x),
            float(state.printability_build_direction_y),
            float(state.printability_build_direction_z),
        ),
        wall_sample_limit=defaults[0],
        triangle_limit=defaults[1],
        orientation_candidate_limit=defaults[2],
        evidence_cap=defaults[3],
        principal_axis_candidates_enabled=bool(state.printability_principal_candidates),
        planar_face_candidates_enabled=bool(state.printability_planar_candidates),
        sampled_candidates_enabled=bool(state.printability_sampled_candidates),
    )
