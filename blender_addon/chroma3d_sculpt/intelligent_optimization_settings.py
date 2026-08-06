"""Sprint 6 objective profiles and user-editable settings."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

from .models.intelligent_optimization_models import (
    DeterministicModel,
    ObjectiveDirection,
    ObjectiveMetric,
    plain_value,
    stable_hash,
)


_PRESETS: dict[str, dict[ObjectiveMetric, float]] = {
    "Balanced": {
        ObjectiveMetric.BUILD_VOLUME_FIT: 1.0,
        ObjectiveMetric.WALL_THICKNESS_PRESERVATION: 1.0,
        ObjectiveMetric.THIN_FEATURE_PRESERVATION: 1.0,
        ObjectiveMetric.OVERHANG_RISK: 1.0,
        ObjectiveMetric.BRIDGE_RISK: 1.0,
        ObjectiveMetric.SUPPORT_RISK: 1.0,
        ObjectiveMetric.CONTACT_QUALITY: 1.0,
        ObjectiveMetric.HEIGHT: 0.5,
        ObjectiveMetric.GEOMETRY_FIDELITY: 1.0,
    },
    "Minimum Supports": {
        ObjectiveMetric.SUPPORT_RISK: 3.0,
        ObjectiveMetric.BRIDGE_RISK: 2.0,
        ObjectiveMetric.OVERHANG_RISK: 2.0,
        ObjectiveMetric.CONTACT_QUALITY: 1.0,
        ObjectiveMetric.BUILD_VOLUME_FIT: 1.0,
    },
    "Maximum Fidelity": {
        ObjectiveMetric.GEOMETRY_FIDELITY: 4.0,
        ObjectiveMetric.WALL_THICKNESS_PRESERVATION: 2.0,
        ObjectiveMetric.THIN_FEATURE_PRESERVATION: 2.0,
        ObjectiveMetric.TOPOLOGY_CLEANLINESS: 1.0,
        ObjectiveMetric.BUILD_VOLUME_FIT: 1.0,
    },
    "Fit to Printer": {
        ObjectiveMetric.BUILD_VOLUME_FIT: 4.0,
        ObjectiveMetric.HEIGHT: 1.0,
        ObjectiveMetric.CONTACT_QUALITY: 1.0,
        ObjectiveMetric.GEOMETRY_FIDELITY: 1.0,
    },
    "Stable Base": {
        ObjectiveMetric.CONTACT_QUALITY: 4.0,
        ObjectiveMetric.SUPPORT_RISK: 1.0,
        ObjectiveMetric.HEIGHT: 1.0,
        ObjectiveMetric.BUILD_VOLUME_FIT: 1.0,
        ObjectiveMetric.GEOMETRY_FIDELITY: 1.0,
    },
    "Lightweight": {
        ObjectiveMetric.TRIANGLE_COUNT: 3.0,
        ObjectiveMetric.GEOMETRY_FIDELITY: 2.0,
        ObjectiveMetric.BUILD_VOLUME_FIT: 1.0,
    },
    "Resin Advisory": {
        ObjectiveMetric.FLOATING_COMPONENTS: 2.0,
        ObjectiveMetric.SUPPORT_RISK: 2.0,
        ObjectiveMetric.BRIDGE_RISK: 1.0,
        ObjectiveMetric.RESIN_ADVISORY: 3.0,
        ObjectiveMetric.GEOMETRY_FIDELITY: 1.0,
    },
}

_MINIMIZE = {
    ObjectiveMetric.OVERHANG_RISK,
    ObjectiveMetric.BRIDGE_RISK,
    ObjectiveMetric.SUPPORT_RISK,
    ObjectiveMetric.HEIGHT,
    ObjectiveMetric.FLOATING_COMPONENTS,
    ObjectiveMetric.TRIANGLE_COUNT,
    ObjectiveMetric.RUNTIME_COST,
    ObjectiveMetric.MEMORY_OBSERVATION,
    ObjectiveMetric.OPERATION_COUNT,
    ObjectiveMetric.RISK_COUNT,
    ObjectiveMetric.CRITICAL_REGRESSION_COUNT,
}


@dataclass(frozen=True, slots=True)
class ObjectiveProfile(DeterministicModel):
    preset: str
    weights: Mapping[str, float]
    directions: Mapping[str, ObjectiveDirection | str]
    normalized_weights: Mapping[str, float]
    profile_hash: str = ""
    provenance: str = "Sprint 6 deterministic objective profile"
    limitations: tuple[str, ...] = ("Objective values are bounded software evidence, not physical print guarantees.",)

    def __post_init__(self) -> None:
        if not self.preset:
            raise ValueError("Objective profile preset is required.")
        normalized_directions = {str(key): ObjectiveDirection(value) for key, value in self.directions.items()}
        object.__setattr__(self, "directions", normalized_directions)
        if not self.profile_hash:
            object.__setattr__(self, "profile_hash", stable_hash({"preset": self.preset, "weights": self.weights, "directions": normalized_directions, "normalized_weights": self.normalized_weights}))


@dataclass(frozen=True, slots=True)
class IntelligentOptimizationSettings(DeterministicModel):
    search_mode: str = "STANDARD"
    objective_preset: str = "Balanced"
    ranking_method: str = "CONSTRAINT_FIRST"
    custom_weights: tuple[tuple[str, float], ...] = ()
    experimental_operations_enabled: bool = False
    require_explicit_approval: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.experimental_operations_enabled, bool) or not isinstance(self.require_explicit_approval, bool):
            raise ValueError("Intelligent optimization settings flags must be booleans.")


def available_objective_presets() -> tuple[str, ...]:
    return tuple(_PRESETS) + ("Custom",)


def _custom_values(custom_weights: Mapping[str | ObjectiveMetric, float] | Iterable[tuple[str | ObjectiveMetric, float]]) -> dict[ObjectiveMetric, float]:
    values = dict(custom_weights)
    if not values:
        raise ValueError("Custom objective mode requires at least one objective weight.")
    result: dict[ObjectiveMetric, float] = {}
    for key, value in values.items():
        metric = ObjectiveMetric(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value or value in (float("inf"), float("-inf")) or float(value) < 0.0:
            raise ValueError(f"Invalid objective weight for {metric.value}.")
        if metric in result:
            raise ValueError(f"Duplicate objective weight: {metric.value}")
        result[metric] = float(value)
    if sum(result.values()) <= 0.0:
        raise ValueError("Objective weights must have a positive total.")
    return result


def build_objective_profile(preset: str = "Balanced", custom_weights: Mapping[str | ObjectiveMetric, float] | Iterable[tuple[str | ObjectiveMetric, float]] = ()) -> ObjectiveProfile:
    if preset == "Custom":
        values = _custom_values(custom_weights)
    else:
        try:
            values = dict(_PRESETS[preset])
        except KeyError as exc:
            raise ValueError(f"Unknown objective preset: {preset!r}") from exc
    total = sum(values.values())
    normalized = {metric.value: round(weight / total, 12) for metric, weight in sorted(values.items(), key=lambda item: item[0].value)}
    directions = {metric.value: (ObjectiveDirection.MINIMIZE if metric in _MINIMIZE else ObjectiveDirection.MAXIMIZE) for metric in sorted(values, key=lambda item: item.value)}
    weights = {metric.value: values[metric] for metric in sorted(values, key=lambda item: item.value)}
    return ObjectiveProfile(preset=preset, weights=weights, directions=directions, normalized_weights=normalized)


def objective_profile_hash(profile: ObjectiveProfile | Mapping[str, object]) -> str:
    return profile.profile_hash if isinstance(profile, ObjectiveProfile) else stable_hash(profile)


def objective_directions() -> dict[str, ObjectiveDirection]:
    return {metric.value: (ObjectiveDirection.MINIMIZE if metric in _MINIMIZE else ObjectiveDirection.MAXIMIZE) for metric in ObjectiveMetric}


__all__ = (
    "ObjectiveProfile", "IntelligentOptimizationSettings", "available_objective_presets",
    "build_objective_profile", "objective_directions", "objective_profile_hash", "plain_value",
)
