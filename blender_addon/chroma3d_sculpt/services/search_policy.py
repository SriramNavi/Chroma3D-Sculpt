"""Validated deterministic search policies and bounded Sprint 6 defaults."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Iterable

from ..models.intelligent_optimization_models import (
    OptimizationOperationType,
    SearchBudget,
    SearchMode,
    SearchPolicy,
)
from ..intelligent_optimization_settings import build_objective_profile
from .constraint_engine import default_constraint_set, validate_constraint_set


STRATEGY_FAMILIES = (
    "Scale only", "Orientation only", "Translation only", "Repair-first", "Orientation-first", "Scale-first",
    "Contact-first", "Fidelity-first", "Minimum-support", "Minimum-bridge", "Fit-to-printer", "Stable-base",
    "Lightweight", "Balanced", "High-fidelity", "Repair + orientation", "Repair + scale", "Orientation + scale",
    "Scale + orientation", "Repair + orientation + translation", "Repair + scale + orientation",
    "Base stabilization + orientation", "Decimation + scale", "Decimation + orientation", "Custom objective-driven",
)

_ALLOWED = tuple(item.value for item in OptimizationOperationType)
_NON_EXPERIMENTAL = tuple(item for item in _ALLOWED if item not in {OptimizationOperationType.DECIMATION.value, OptimizationOperationType.EXPERIMENTAL_REMESH.value})
_MODE_BUDGETS = {
    SearchMode.FAST: SearchBudget(max_generated_strategies=12, max_evaluated_strategies=8, max_workspace_previews=1, max_operation_steps=24, max_strategy_depth=2, max_branch_factor=4, max_operation_sequence_permutations=8, max_pareto_points=8, max_ranking_results=12, max_wall_time_seconds=10.0, max_per_strategy_seconds=2.0),
    SearchMode.STANDARD: SearchBudget(),
    SearchMode.DEEP: SearchBudget(max_generated_strategies=96, max_evaluated_strategies=64, max_workspace_previews=4, max_operation_steps=128, max_strategy_depth=5, max_branch_factor=10, max_operation_sequence_permutations=96, max_pareto_points=32, max_ranking_results=96, max_wall_time_seconds=90.0, max_per_strategy_seconds=8.0, max_memory_observation_mb=1024.0),
}


def default_search_policy(mode: SearchMode | str = SearchMode.STANDARD, *, experimental_operations_enabled: bool = False) -> SearchPolicy:
    selected_mode = SearchMode(mode)
    if selected_mode == SearchMode.CUSTOM:
        selected_mode = SearchMode.STANDARD
    allowed = tuple(_ALLOWED if experimental_operations_enabled else _NON_EXPERIMENTAL)
    constraints = default_constraint_set(allowed_operations=allowed, experimental_enabled=experimental_operations_enabled)
    return SearchPolicy(
        policy_id=f"s6-{selected_mode.value.lower()}",
        search_mode=mode,
        enabled_strategy_families=STRATEGY_FAMILIES,
        allowed_operation_families=allowed,
        budget=_MODE_BUDGETS[selected_mode],
        objective_profile=build_objective_profile("Balanced").to_dict(),
        constraints=constraints,
        experimental_operations_enabled=experimental_operations_enabled,
        explicit_experimental_enablement=experimental_operations_enabled,
    )


def policy_hash(policy: SearchPolicy) -> str:
    payload = policy.to_dict()
    payload["policy_hash"] = ""
    payload.pop("policy_hash", None)
    payload.pop("explicit_experimental_enablement", None)
    payload.pop("provenance", None)
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_search_policy(policy: SearchPolicy) -> None:
    if not isinstance(policy, SearchPolicy):
        raise TypeError("policy must be a SearchPolicy.")
    if policy.search_mode == SearchMode.CUSTOM and policy.budget.max_generated_strategies <= 0:
        raise ValueError("Custom search mode requires a positive strategy budget.")
    if len(set(policy.enabled_strategy_families)) != len(policy.enabled_strategy_families):
        raise ValueError("Duplicate strategy family IDs are not allowed.")
    unknown_families = set(policy.enabled_strategy_families) - set(STRATEGY_FAMILIES)
    if unknown_families:
        raise ValueError(f"Unknown strategy family: {sorted(unknown_families)[0]}")
    seen: set[str] = set()
    for operation in policy.allowed_operation_families:
        try:
            normalized = OptimizationOperationType(operation).value
        except ValueError as exc:
            raise ValueError(f"Unknown operation family: {operation!r}") from exc
        if normalized in seen:
            raise ValueError(f"Duplicate operation family: {normalized}")
        seen.add(normalized)
    experimental = {OptimizationOperationType.DECIMATION.value, OptimizationOperationType.EXPERIMENTAL_REMESH.value}
    if experimental & seen and not policy.experimental_operations_enabled:
        raise ValueError("Experimental operations are hidden behind explicit enablement.")
    if policy.experimental_operations_enabled and not policy.explicit_experimental_enablement:
        raise ValueError("Experimental operations require explicit enablement.")
    validate_constraint_set(policy.constraints)
    current_hash = policy_hash(policy)
    if policy.policy_hash != current_hash:
        raise ValueError("Search policy hash does not match its deterministic payload.")


def search_policy_is_current(policy: SearchPolicy, expected_hash: str) -> tuple[bool, str]:
    try:
        validate_search_policy(policy)
    except (TypeError, ValueError) as exc:
        return False, f"INVALID_POLICY:{exc}"
    return (True, "CURRENT") if policy_hash(policy) == expected_hash else (False, "SEARCH_POLICY_CHANGED")


class SearchPolicyRegistry:
    def __init__(self, policies: Iterable[SearchPolicy] = ()) -> None:
        self._policies: dict[str, SearchPolicy] = {}
        for policy in policies:
            self.add(policy)

    def add(self, policy: SearchPolicy) -> None:
        validate_search_policy(policy)
        if policy.policy_id in self._policies:
            raise ValueError(f"Duplicate search policy ID: {policy.policy_id}")
        self._policies[policy.policy_id] = policy

    def get(self, policy_id: str) -> SearchPolicy:
        try:
            return self._policies[policy_id]
        except KeyError as exc:
            raise KeyError(f"Unknown search policy: {policy_id}") from exc

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._policies))


__all__ = (
    "STRATEGY_FAMILIES", "SearchPolicyRegistry", "default_search_policy", "policy_hash",
    "search_policy_is_current", "validate_search_policy",
)
