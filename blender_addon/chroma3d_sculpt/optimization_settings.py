"""Validated objective presets and Sprint 5 settings snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable

from .models.optimization_models import (
    ObjectiveSnapshot, ObjectiveWeight, OptimizationObjective, plain_value,
)


_ALL = tuple(OptimizationObjective)
_PRESET_OBJECTIVES = {
    "Balanced FDM": {
        OptimizationObjective.BUILD_VOLUME_FIT: 1.0,
        OptimizationObjective.WALL_THICKNESS_PRESERVATION: 1.0,
        OptimizationObjective.THIN_FEATURE_PRESERVATION: 1.0,
        OptimizationObjective.OVERHANG_REDUCTION: 1.0,
        OptimizationObjective.SUPPORT_RISK_REDUCTION: 1.0,
        OptimizationObjective.CONTACT_IMPROVEMENT: 1.0,
        OptimizationObjective.HEIGHT_REDUCTION: 0.5,
        OptimizationObjective.GEOMETRY_FIDELITY: 1.0,
    },
    "Minimum Supports": {
        OptimizationObjective.BUILD_VOLUME_FIT: 1.0,
        OptimizationObjective.OVERHANG_REDUCTION: 2.0,
        OptimizationObjective.BRIDGE_RISK_REDUCTION: 2.0,
        OptimizationObjective.SUPPORT_RISK_REDUCTION: 3.0,
        OptimizationObjective.CONTACT_IMPROVEMENT: 1.0,
        OptimizationObjective.HEIGHT_REDUCTION: 1.0,
    },
    "Maximum Fidelity": {
        OptimizationObjective.WALL_THICKNESS_PRESERVATION: 2.0,
        OptimizationObjective.THIN_FEATURE_PRESERVATION: 2.0,
        OptimizationObjective.GEOMETRY_FIDELITY: 4.0,
        OptimizationObjective.TOPOLOGY_CLEANLINESS: 1.0,
        OptimizationObjective.BUILD_VOLUME_FIT: 1.0,
    },
    "Fit to Printer": {
        OptimizationObjective.BUILD_VOLUME_FIT: 4.0,
        OptimizationObjective.HEIGHT_REDUCTION: 1.0,
        OptimizationObjective.CONTACT_IMPROVEMENT: 1.0,
        OptimizationObjective.GEOMETRY_FIDELITY: 1.0,
    },
    "Stable Base": {
        OptimizationObjective.CONTACT_IMPROVEMENT: 4.0,
        OptimizationObjective.SUPPORT_RISK_REDUCTION: 1.0,
        OptimizationObjective.HEIGHT_REDUCTION: 1.0,
        OptimizationObjective.BUILD_VOLUME_FIT: 1.0,
        OptimizationObjective.GEOMETRY_FIDELITY: 1.0,
    },
    "Lightweight Preview": {
        OptimizationObjective.TRIANGLE_COUNT_REDUCTION: 3.0,
        OptimizationObjective.GEOMETRY_FIDELITY: 2.0,
        OptimizationObjective.BUILD_VOLUME_FIT: 1.0,
    },
    "Resin Advisory": {
        OptimizationObjective.FLOATING_COMPONENT_REDUCTION: 2.0,
        OptimizationObjective.SUPPORT_RISK_REDUCTION: 2.0,
        OptimizationObjective.BRIDGE_RISK_REDUCTION: 1.0,
        OptimizationObjective.RESIN_ADVISORY_IMPROVEMENT: 3.0,
        OptimizationObjective.GEOMETRY_FIDELITY: 1.0,
    },
}


@dataclass(frozen=True, slots=True)
class OptimizationSettings:
    objective_preset: str = "Balanced FDM"
    custom_weights: tuple[ObjectiveWeight, ...] = ()
    selected_candidate_id: str = ""
    require_explicit_approval: bool = True

    def snapshot(self) -> ObjectiveSnapshot:
        return build_objective_snapshot(self.objective_preset, self.custom_weights)


def _weights_for(preset: str, custom_weights: Iterable[ObjectiveWeight]) -> tuple[ObjectiveWeight, ...]:
    if preset == "Custom":
        weights = tuple(custom_weights)
        if not weights:
            raise ValueError("Custom objective mode requires at least one objective weight.")
        return weights
    try:
        preset_values = _PRESET_OBJECTIVES[preset]
    except KeyError as exc:
        raise ValueError(f"Unknown objective preset: {preset!r}") from exc
    return tuple(
        ObjectiveWeight(
            objective=objective,
            weight=weight,
            source_classification="PROJECT_DEFAULT",
            provenance=f"Sprint 5 preset: {preset}",
            limitations=("Objective is heuristic and bounded by available software evidence.",),
        )
        for objective, weight in sorted(preset_values.items(), key=lambda item: item[0].value)
    )


def build_objective_snapshot(preset: str = "Balanced FDM", custom_weights: Iterable[ObjectiveWeight] = ()) -> ObjectiveSnapshot:
    weights = _weights_for(preset, custom_weights)
    by_objective: dict[OptimizationObjective, ObjectiveWeight] = {}
    for item in weights:
        objective = OptimizationObjective(item.objective)
        if objective in by_objective:
            raise ValueError(f"Duplicate objective weight: {objective.value}")
        by_objective[objective] = item
    total = sum(item.weight for item in by_objective.values() if item.enabled)
    if total <= 0.0:
        raise ValueError("Objective weights must have a positive enabled total.")
    normalized = tuple(
        ObjectiveWeight(
            objective=item.objective,
            weight=round(item.weight / total, 12),
            source_classification=item.source_classification,
            provenance=item.provenance,
            enabled=item.enabled,
            limitations=item.limitations,
        )
        for item in sorted(by_objective.values(), key=lambda value: value.objective.value)
    )
    payload = {"preset": preset, "weights": plain_value(normalized)}
    objective_hash = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return ObjectiveSnapshot(
        preset=preset,
        weights=tuple(sorted(by_objective.values(), key=lambda value: value.objective.value)),
        normalized_weights=normalized,
        objective_hash=objective_hash,
        total_weight=round(total, 12),
        limitations=(
            "Objective values are bounded software evidence and not physical print guarantees.",
            "Disabled or missing checks remain visible as indeterminate rather than improvements.",
        ),
    )


def objective_hash(snapshot: ObjectiveSnapshot) -> str:
    return snapshot.objective_hash


def available_presets() -> tuple[str, ...]:
    return tuple(_PRESET_OBJECTIVES) + ("Custom",)


__all__ = ("OptimizationSettings", "available_presets", "build_objective_snapshot", "objective_hash")
