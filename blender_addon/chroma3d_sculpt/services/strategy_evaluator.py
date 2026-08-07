"""Virtual and bounded workspace-independent strategy evaluation."""

from __future__ import annotations

from time import perf_counter
import math
from typing import Any, Callable, Mapping

from ..intelligent_optimization_settings import ObjectiveProfile, build_objective_profile, objective_directions
from ..models.intelligent_optimization_models import (
    ConstraintSet,
    EvidenceState,
    IntelligentStrategy,
    ObjectiveDirection,
    ObjectiveMetric,
    ObjectiveVector,
    SearchBudgetUsage,
    SearchPolicy,
    StrategyEvaluation,
    StrategySet,
)
from .constraint_engine import constraints_are_feasible, default_constraint_set, evaluate_constraints
from .search_policy import default_search_policy, validate_search_policy


def _profile_dict(profile: ObjectiveProfile | Mapping[str, Any] | None, policy: SearchPolicy | None) -> dict[str, Any]:
    if profile is None:
        if policy is not None and policy.objective_profile:
            return dict(policy.objective_profile)
        return build_objective_profile("Balanced").to_dict()
    return profile.to_dict() if isinstance(profile, ObjectiveProfile) else dict(profile)


def _effect(strategy: IntelligentStrategy, key: str) -> float:
    values = [step.expected_objective_effects.get(key, step.expected_objective_effects.get(key.upper(), 0.0)) for step in strategy.steps]
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) for value in values):
        raise ValueError(f"Strategy objective effect for {key!r} must be finite numeric evidence.")
    return sum(float(value) for value in values)


def _direction(key: str, profile: Mapping[str, Any]) -> ObjectiveDirection:
    directions = profile.get("directions", {})
    if key in directions:
        return ObjectiveDirection(directions[key])
    return objective_directions().get(key, ObjectiveDirection.MAXIMIZE)


def _normalise(value: float | None, key: str, bounds: Mapping[str, Any]) -> float | None:
    if value is None:
        return None
    bound = bounds.get(key)
    if isinstance(bound, Mapping) and bound.get("maximum") is not None and bound.get("minimum") is not None:
        minimum = float(bound["minimum"])
        maximum = float(bound["maximum"])
        if maximum > minimum:
            return max(0.0, min(1.0, (value - minimum) / (maximum - minimum)))
    if 0.0 <= value <= 1.0:
        return float(value)
    if key in {ObjectiveMetric.HEIGHT.value, ObjectiveMetric.TRIANGLE_COUNT.value, ObjectiveMetric.RUNTIME_COST.value, ObjectiveMetric.MEMORY_OBSERVATION.value, ObjectiveMetric.OPERATION_COUNT.value}:
        return 1.0 / (1.0 + max(0.0, float(value)))
    return max(0.0, min(1.0, float(value)))


def _metric_keys(profile: Mapping[str, Any]) -> tuple[str, ...]:
    keys = set(str(key) for key in profile.get("weights", {}))
    keys.update(metric.value for metric in ObjectiveMetric)
    return tuple(sorted(keys))


def virtual_evaluate_strategy(
    strategy: IntelligentStrategy,
    *,
    baseline_values: Mapping[str, Any] | None = None,
    baseline_evidence_states: Mapping[str, EvidenceState | str] | None = None,
    normalization_bounds: Mapping[str, Any] | None = None,
    profile: ObjectiveProfile | Mapping[str, Any] | None = None,
    constraints: ConstraintSet | None = None,
    policy: SearchPolicy | None = None,
) -> StrategyEvaluation:
    """Evaluate a strategy without changing a Blender object or workspace."""

    started = perf_counter()
    values = dict(baseline_values or {})
    profile_data = _profile_dict(profile, policy)
    keys = _metric_keys(profile_data)
    raw: dict[str, float | None] = {}
    normalized: dict[str, float | None] = {}
    states: dict[str, EvidenceState] = {}
    directions: dict[str, ObjectiveDirection] = {}
    evidence_input = dict(baseline_evidence_states or {})
    for key in keys:
        directions[key] = _direction(key, profile_data)
        base = values.get(key)
        effect = _effect(strategy, key)
        if base is None and effect == 0.0 and key not in {ObjectiveMetric.OPERATION_COUNT.value, ObjectiveMetric.RUNTIME_COST.value}:
            raw[key] = None
            normalized[key] = None
            states[key] = EvidenceState(evidence_input.get(key, EvidenceState.INDETERMINATE))
            continue
        if base is None:
            base = 0.5
        if isinstance(base, bool) or not isinstance(base, (int, float)) or not math.isfinite(float(base)):
            raise ValueError(f"Invalid baseline objective value for {key!r}.")
        try:
            numeric = float(base)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid baseline objective value for {key!r}.") from exc
        # Sprint 5 candidate effects are expressed as improvement magnitudes.
        raw_value = numeric + effect if directions[key] == ObjectiveDirection.MAXIMIZE else numeric - effect
        if key == ObjectiveMetric.OPERATION_COUNT.value:
            raw_value = float(len(strategy.steps))
        elif key == ObjectiveMetric.RUNTIME_COST.value:
            raw_value = float(sum(step.estimated_cost_seconds for step in strategy.steps))
        raw[key] = raw_value
        normalized[key] = _normalise(raw_value, key, normalization_bounds or {})
        states[key] = EvidenceState(evidence_input.get(key, EvidenceState.ESTIMATED if effect != 0.0 or key in values else EvidenceState.INDETERMINATE))

    vector = ObjectiveVector(raw_values=raw, normalized_values=normalized, directions=directions, evidence_states=states, confidence="LOW")
    actual_values = dict(values)
    actual_values.update({
        "source_protected": True,
        "operations_allowed": tuple(step.operation for step in strategy.steps),
        "strategy_depth": len(strategy.steps),
        "experimental_operation": any(step.experimental for step in strategy.steps),
        "confidence": "LOW",
    })
    actual_values.setdefault("fidelity_status", values.get("fidelity_status"))
    actual_values.setdefault("critical_defect_introduced", values.get("critical_defect_introduced"))
    actual_values.setdefault("geometric_deviation", values.get("geometric_deviation"))
    actual_values.setdefault("area_drift", values.get("area_drift"))
    actual_values.setdefault("volume_drift", values.get("volume_drift"))
    active_constraints = constraints or (policy.constraints if policy else default_constraint_set(allowed_operations=tuple(step.operation for step in strategy.steps), experimental_enabled=any(step.experimental for step in strategy.steps)))
    constraint_states = dict(states)
    for key in ("source_protected", "operations_allowed", "strategy_depth", "experimental_operation", "confidence", "fidelity_status", "critical_defect_introduced", "geometric_deviation", "area_drift", "volume_drift"):
        constraint_states[key] = EvidenceState.MEASURED if key in {"source_protected", "operations_allowed", "strategy_depth", "experimental_operation", "confidence"} else EvidenceState(evidence_input.get(key, EvidenceState.MEASURED if key in values and values.get(key) is not None else EvidenceState.INDETERMINATE))
    evaluations = evaluate_constraints(active_constraints, actual_values, evidence_states=constraint_states, confidence="LOW")
    feasible = constraints_are_feasible(evaluations)
    measured = tuple(sorted(key for key, state in vector.evidence_states.items() if state == EvidenceState.MEASURED))
    estimated = tuple(sorted(key for key, state in vector.evidence_states.items() if state in {EvidenceState.ESTIMATED, EvidenceState.PARTIAL}))
    skipped = tuple(sorted(key for key, state in vector.evidence_states.items() if state == EvidenceState.SKIPPED_LIMIT))
    indeterminate = tuple(sorted(key for key, state in vector.evidence_states.items() if state == EvidenceState.INDETERMINATE))
    critical = tuple(sorted(item.constraint_id for item in evaluations if item.rejection_reason and "critical" in item.constraint_id.lower()))
    return StrategyEvaluation(
        strategy_id=strategy.strategy_id,
        evaluation_state=EvidenceState.ESTIMATED if not measured else EvidenceState.PARTIAL,
        objective_vector=vector,
        constraint_evaluations=evaluations,
        feasible=feasible,
        measured_evidence=measured,
        estimated_evidence=estimated,
        skipped_evidence=skipped,
        indeterminate_evidence=indeterminate,
        critical_regressions=critical,
        runtime_seconds=round(perf_counter() - started, 6),
        limitations=("Virtual evaluation is estimated/partial evidence; it is not measured geometry evidence.",),
    )


def evaluate_strategies(
    strategy_set: StrategySet,
    *,
    baseline_values: Mapping[str, Any] | None = None,
    baseline_evidence_states: Mapping[str, EvidenceState | str] | None = None,
    profile: ObjectiveProfile | Mapping[str, Any] | None = None,
    constraints: ConstraintSet | None = None,
    policy: SearchPolicy | None = None,
    cancel_requested: Callable[[], bool] | Any | None = None,
) -> tuple[tuple[StrategyEvaluation, ...], SearchBudgetUsage, str]:
    active_policy = policy or default_search_policy()
    validate_search_policy(active_policy)
    usage = SearchBudgetUsage(generated_strategies=strategy_set.budget_usage.generated_strategies)
    results: list[StrategyEvaluation] = []
    status = "COMPLETE"

    def cancelled() -> bool:
        if cancel_requested is None:
            return False
        if callable(cancel_requested):
            return bool(cancel_requested())
        return bool(getattr(cancel_requested, "is_set", lambda: False)()) or bool(getattr(cancel_requested, "cancelled", False))

    started = perf_counter()
    for strategy in strategy_set.strategies:
        if cancelled():
            status = "CANCELLED"
            usage.exhausted_dimensions.append("cancellation")
            break
        if len(results) >= active_policy.budget.max_evaluated_strategies:
            status = "BUDGET_EXHAUSTED"
            usage.exhausted_dimensions.append("evaluated_strategies")
            break
        if perf_counter() - started > active_policy.budget.max_wall_time_seconds:
            status = "BUDGET_EXHAUSTED"
            usage.exhausted_dimensions.append("wall_time_seconds")
            break
        results.append(virtual_evaluate_strategy(strategy, baseline_values=baseline_values, baseline_evidence_states=baseline_evidence_states, profile=profile, constraints=constraints, policy=active_policy))
        usage.evaluated_strategies += 1
    usage.wall_time_seconds = round(perf_counter() - started, 6)
    return tuple(results), usage, status


evaluate_virtual_strategy = virtual_evaluate_strategy


__all__ = ("evaluate_strategies", "evaluate_virtual_strategy", "virtual_evaluate_strategy")
