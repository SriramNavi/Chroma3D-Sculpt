"""Deterministic, bounded strategy generation above Sprint 5 candidates."""

from __future__ import annotations

from itertools import product
from time import perf_counter
from typing import Any, Callable, Iterable, Mapping, Sequence

from ..models.intelligent_optimization_models import (
    ConstraintKind,
    ConstraintSeverity,
    IntelligentStrategy,
    OptimizationOperationType,
    PruningRecord,
    SearchBudgetUsage,
    SearchPolicy,
    StrategyGenerationReason,
    StrategySet,
    StrategyState,
    StrategyStep,
    stable_hash,
)
from .constraint_engine import default_constraint_set, validate_constraint_set
from .search_policy import default_search_policy, policy_hash, validate_search_policy


_FAMILY_OPERATIONS: dict[str, tuple[str, ...]] = {
    "Scale only": ("UNIFORM_SCALE",),
    "Orientation only": ("ORIENTATION",),
    "Translation only": ("BUILD_PLATE_TRANSLATION",),
    "Repair-first": ("REPAIR_REUSE", "ORIENTATION", "UNIFORM_SCALE"),
    "Orientation-first": ("ORIENTATION", "BUILD_PLATE_TRANSLATION", "UNIFORM_SCALE"),
    "Scale-first": ("UNIFORM_SCALE", "ORIENTATION", "BUILD_PLATE_TRANSLATION"),
    "Contact-first": ("BUILD_PLATE_TRANSLATION", "BASE_STABILIZATION", "ORIENTATION"),
    "Fidelity-first": ("REPAIR_REUSE", "ORIENTATION", "UNIFORM_SCALE"),
    "Minimum-support": ("ORIENTATION", "BASE_STABILIZATION", "BUILD_PLATE_TRANSLATION"),
    "Minimum-bridge": ("ORIENTATION", "BUILD_PLATE_TRANSLATION"),
    "Fit-to-printer": ("UNIFORM_SCALE", "ORIENTATION", "BUILD_PLATE_TRANSLATION"),
    "Stable-base": ("BASE_STABILIZATION", "ORIENTATION", "BUILD_PLATE_TRANSLATION"),
    "Lightweight": ("DECIMATION", "UNIFORM_SCALE"),
    "Balanced": ("ORIENTATION", "UNIFORM_SCALE", "BUILD_PLATE_TRANSLATION"),
    "High-fidelity": ("REPAIR_REUSE", "ORIENTATION"),
    "Repair + orientation": ("REPAIR_REUSE", "ORIENTATION"),
    "Repair + scale": ("REPAIR_REUSE", "UNIFORM_SCALE"),
    "Orientation + scale": ("ORIENTATION", "UNIFORM_SCALE"),
    "Scale + orientation": ("UNIFORM_SCALE", "ORIENTATION"),
    "Repair + orientation + translation": ("REPAIR_REUSE", "ORIENTATION", "BUILD_PLATE_TRANSLATION"),
    "Repair + scale + orientation": ("REPAIR_REUSE", "UNIFORM_SCALE", "ORIENTATION"),
    "Base stabilization + orientation": ("BASE_STABILIZATION", "ORIENTATION"),
    "Decimation + scale": ("DECIMATION", "UNIFORM_SCALE"),
    "Decimation + orientation": ("DECIMATION", "ORIENTATION"),
}


def _value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(key, default)
    return getattr(item, key, default)


def _operation(candidate: Any) -> str:
    category = _value(candidate, "category", _value(candidate, "operation", ""))
    return str(getattr(category, "value", category))


def _parameters(candidate: Any) -> dict[str, Any]:
    operation = _value(candidate, "geometry_operation")
    parameters = _value(operation, "parameters", None) if operation is not None else None
    if parameters is None:
        parameters = _value(candidate, "parameters", {})
    return dict(parameters or {})


def _candidate_id(candidate: Any) -> str:
    return str(_value(candidate, "candidate_id", ""))


def _candidate_fingerprint(candidate: Any) -> str:
    return str(_value(candidate, "fingerprint", stable_hash({"id": _candidate_id(candidate), "operation": _operation(candidate), "parameters": _parameters(candidate)})))


def _candidate_cost(candidate: Any) -> float:
    evaluation = _value(candidate, "evaluation")
    return float(_value(evaluation, "estimated_cost_seconds", _value(candidate, "estimated_cost_seconds", 0.01)) or 0.01)


def _candidate_approval(candidate: Any) -> bool:
    operation = _value(candidate, "geometry_operation")
    return bool(_value(operation, "approval_required", _value(candidate, "required_approval_level", "REVIEW") in {"EXPLICIT", "EXPERIMENTAL"}))


def _candidate_experimental(candidate: Any) -> bool:
    operation = _value(candidate, "geometry_operation")
    return bool(_value(operation, "experimental", _operation(candidate) in {"DECIMATION", "EXPERIMENTAL_REMESH"}))


def _candidate_evidence(candidate: Any) -> tuple[Mapping[str, Any], ...]:
    value = _value(candidate, "source_evidence", ())
    return tuple(value or ())


def _candidate_limitations(candidate: Any) -> tuple[str, ...]:
    evaluation = _value(candidate, "evaluation")
    return tuple(_value(candidate, "limitations", ()) or ()) + tuple(_value(evaluation, "limitations", ()) or ())


def _step(candidate: Any, order: int) -> StrategyStep:
    evaluation = _value(candidate, "evaluation")
    return StrategyStep(
        order=order,
        candidate_id=_candidate_id(candidate),
        operation=_operation(candidate),
        parameters=_parameters(candidate),
        approval_required=_candidate_approval(candidate),
        experimental=_candidate_experimental(candidate),
        estimated_cost_seconds=_candidate_cost(candidate),
        expected_objective_effects=dict(_value(evaluation, "expected_objective_effect", _value(evaluation, "expected_objective_effects", {})) or {}),
        source_evidence=_candidate_evidence(candidate),
        limitations=_candidate_limitations(candidate),
    )


def _candidate_map(candidates: Sequence[Any]) -> dict[str, list[Any]]:
    result: dict[str, list[Any]] = {}
    for candidate in sorted(candidates, key=lambda item: (_operation(item), _candidate_id(item), _candidate_fingerprint(item))):
        result.setdefault(_operation(candidate), []).append(candidate)
    return result


def _family_operations(family: str) -> tuple[str, ...] | None:
    operations = _FAMILY_OPERATIONS.get(family)
    if family == "Custom objective-driven":
        operations = ("REPAIR_REUSE", "ORIENTATION", "UNIFORM_SCALE", "BUILD_PLATE_TRANSLATION", "BASE_STABILIZATION", "DECIMATION")
    return operations


def _sequences_for_family(
    family: str,
    by_operation: Mapping[str, list[Any]],
    budget_depth: int,
    *,
    branch_factor: int,
    sequence_limit: int,
) -> tuple[tuple[Any, ...], ...]:
    operations = _family_operations(family)
    if not operations:
        return ()
    options: list[tuple[Any, ...]] = []
    for operation in operations:
        values = by_operation.get(operation, [])
        if not values:
            return ()
        options.append(tuple(values[:branch_factor]))
        if len(options) >= budget_depth:
            break
    if len(options) != min(len(operations), budget_depth):
        return ()
    return tuple(tuple(sequence) for sequence in list(product(*options))[:sequence_limit])


def _known_generation_constraint_violation(strategy_steps: Sequence[StrategyStep], policy: SearchPolicy, constraint_set: Any) -> str:
    operations = tuple(step.operation for step in strategy_steps)
    for constraint in constraint_set.constraints:
        if constraint.severity != ConstraintSeverity.HARD or not constraint.enabled:
            continue
        if constraint.kind == ConstraintKind.ALLOWED_OPERATION:
            allowed = set(str(item) for item in (constraint.required_value or ()))
            invalid = sorted(set(operations) - allowed)
            if invalid:
                return f"Disallowed operation(s): {', '.join(invalid)}"
        elif constraint.kind == ConstraintKind.MAX_DEPTH and constraint.maximum is not None and len(strategy_steps) > constraint.maximum:
            return f"Strategy depth {len(strategy_steps)} exceeds {constraint.maximum}."
        elif constraint.kind == ConstraintKind.EXPERIMENTAL_OPERATION:
            if any(step.experimental for step in strategy_steps) and not policy.experimental_operations_enabled:
                return "Experimental operation is disabled by policy."
    return ""


def generate_strategies(
    candidates: Sequence[Any],
    *,
    policy: SearchPolicy | None = None,
    constraint_set: Any | None = None,
    objective_profile: Mapping[str, Any] | None = None,
    source_signature: str = "",
    process_context_hash: str = "",
    feature_flag_hash: str = "",
    implementation_fingerprint: str = "sprint6-intelligent-optimization-1.2-verification",
    cancel_requested: Callable[[], bool] | Any | None = None,
) -> StrategySet:
    active_policy = policy or default_search_policy()
    validate_search_policy(active_policy)
    active_constraints = constraint_set or active_policy.constraints or default_constraint_set(allowed_operations=active_policy.allowed_operation_families, experimental_enabled=active_policy.experimental_operations_enabled)
    validate_constraint_set(active_constraints)
    started = perf_counter()
    candidate_ids: set[str] = set()
    candidate_fingerprints: dict[str, str] = {}
    for candidate in candidates:
        candidate_id = _candidate_id(candidate)
        candidate_fingerprint = _candidate_fingerprint(candidate)
        if not candidate_id or not candidate_fingerprint:
            raise ValueError("Every Sprint 5 candidate must have a non-empty ID and fingerprint.")
        if candidate_id in candidate_ids:
            raise ValueError(f"Duplicate Sprint 5 candidate ID: {candidate_id}")
        candidate_ids.add(candidate_id)
        candidate_payload = stable_hash({"operation": _operation(candidate), "parameters": _parameters(candidate)})
        previous_payload = candidate_fingerprints.get(candidate_fingerprint)
        if previous_payload is not None and previous_payload != candidate_payload:
            raise ValueError("Ambiguous candidate fingerprint remapping rejected.")
        candidate_fingerprints[candidate_fingerprint] = candidate_payload
    by_operation = _candidate_map(candidates)
    usage = SearchBudgetUsage()
    strategies: list[IntelligentStrategy] = []
    pruned: list[PruningRecord] = []
    fingerprints: dict[str, str] = {}
    semantic_seen: set[str] = set()
    ordinal = 0
    status = "COMPLETE"

    def cancelled() -> bool:
        if cancel_requested is None:
            return False
        if callable(cancel_requested):
            return bool(cancel_requested())
        return bool(getattr(cancel_requested, "is_set", lambda: False)()) or bool(getattr(cancel_requested, "cancelled", False))

    for family in active_policy.enabled_strategy_families:
        if cancelled():
            status = "CANCELLED"
            usage.exhausted_dimensions.append("cancellation")
            break
        if usage.generated_strategies >= active_policy.budget.max_generated_strategies:
            status = "BUDGET_EXHAUSTED"
            usage.exhausted_dimensions.append("generated_strategies")
            break
        sequences = _sequences_for_family(
            family,
            by_operation,
            active_policy.budget.max_strategy_depth,
            branch_factor=active_policy.budget.max_branch_factor,
            sequence_limit=active_policy.budget.max_operation_sequence_permutations,
        )
        if not sequences:
            pruned.append(PruningRecord(f"s6-pruned-{len(pruned) + 1:04d}", "", "UNSUPPORTED_COMBINATION", f"No candidate sequence satisfies family {family}."))
            continue
        for sequence in sequences:
            if cancelled():
                status = "CANCELLED"
                usage.exhausted_dimensions.append("cancellation")
                break
            if usage.generated_strategies >= active_policy.budget.max_generated_strategies:
                status = "BUDGET_EXHAUSTED"
                usage.exhausted_dimensions.append("generated_strategies")
                break
            steps = tuple(_step(candidate, index) for index, candidate in enumerate(sequence, 1))
            if usage.operation_steps + len(steps) > active_policy.budget.max_operation_steps:
                pruned.append(PruningRecord(f"s6-pruned-{len(pruned) + 1:04d}", "", "OPERATION_STEP_BUDGET", f"Operation-step budget {active_policy.budget.max_operation_steps} would be exceeded."))
                usage.exhausted_dimensions.append("operation_steps")
                status = "BUDGET_EXHAUSTED"
                break
            if any(step.operation not in active_policy.allowed_operation_families for step in steps):
                pruned.append(PruningRecord(f"s6-pruned-{len(pruned) + 1:04d}", "", "POLICY_LIMIT", f"Family {family} contains an operation disabled by policy."))
                continue
            if any(step.experimental for step in steps) and not active_policy.experimental_operations_enabled:
                pruned.append(PruningRecord(f"s6-pruned-{len(pruned) + 1:04d}", "", "EXPERIMENTAL_OPERATION_DISABLED", f"Family {family} requires explicit experimental enablement."))
                continue
            rejection = _known_generation_constraint_violation(steps, active_policy, active_constraints)
            semantic_payload = {
                "steps": [{"operation": step.operation, "parameters": step.parameters} for step in steps],
                "source_signature": source_signature,
                "policy_hash": policy_hash(active_policy),
                "objective_profile": objective_profile or active_policy.objective_profile,
            }
            semantic_fingerprint = stable_hash(semantic_payload)
            if semantic_fingerprint in semantic_seen:
                pruned.append(PruningRecord(f"s6-pruned-{len(pruned) + 1:04d}", semantic_fingerprint, "DUPLICATE", f"Family {family} is semantically duplicate of an earlier strategy."))
                continue
            semantic_seen.add(semantic_fingerprint)
            if rejection:
                pruned.append(PruningRecord(f"s6-pruned-{len(pruned) + 1:04d}", semantic_fingerprint, "HARD_CONSTRAINT", rejection))
                continue
            previous = fingerprints.get(semantic_fingerprint)
            if previous is not None and previous != json_safe_steps(steps):
                raise ValueError("Ambiguous strategy fingerprint remapping rejected.")
            fingerprints[semantic_fingerprint] = json_safe_steps(steps)
            ordinal += 1
            strategy = IntelligentStrategy(
                strategy_id=f"s6-strategy-{ordinal:04d}-{semantic_fingerprint[:12]}",
                fingerprint=semantic_fingerprint,
                generation_family=family,
                generation_reason=StrategyGenerationReason.USER_CUSTOM if family == "Custom objective-driven" else StrategyGenerationReason.OBJECTIVE_ALIGNMENT,
                steps=steps,
                source_evidence=tuple(evidence for candidate in sequence for evidence in _candidate_evidence(candidate))[:256],
                objective_profile=objective_profile or active_policy.objective_profile,
                policy_hash=policy_hash(active_policy),
                constraint_set_hash=active_constraints.constraint_set_hash,
                process_context_hash=process_context_hash,
                feature_flag_hash=feature_flag_hash,
                implementation_fingerprint=implementation_fingerprint,
                estimated_evaluation_cost_seconds=round(sum(step.estimated_cost_seconds for step in steps), 6),
                required_approval=any(step.approval_required for step in steps),
                limitations=("Generated by deterministic bounded family expansion; no global optimum is claimed.",),
            )
            strategies.append(strategy)
            usage.generated_strategies += 1
            usage.operation_steps += len(steps)
            if perf_counter() - started > active_policy.budget.max_wall_time_seconds:
                status = "BUDGET_EXHAUSTED"
                usage.exhausted_dimensions.append("wall_time_seconds")
                break
        if status != "COMPLETE":
            break
    # Wall-clock observations are intentionally kept out of the deterministic
    # strategy-set identity.  The audit layer can record them separately.
    usage.wall_time_seconds = 0.0
    return StrategySet(
        strategies=tuple(strategies),
        pruned=tuple(pruned),
        set_id=f"s6-strategy-set-{stable_hash([item.fingerprint for item in strategies])[:16]}",
        source_signature=source_signature,
        policy_hash=policy_hash(active_policy),
        constraint_set_hash=active_constraints.constraint_set_hash,
        process_context_hash=process_context_hash,
        feature_flag_hash=feature_flag_hash,
        implementation_fingerprint=implementation_fingerprint,
        budget_usage=usage,
        status=status,
        limitations=("Strategy generation is read-only and bounded. Unevaluated strategies are not failures.",),
    )


def json_safe_steps(steps: Sequence[StrategyStep]) -> str:
    return stable_hash(tuple(step.to_dict() for step in steps))


generate_strategy_set = generate_strategies


__all__ = ("generate_strategies", "generate_strategy_set", "json_safe_steps")
