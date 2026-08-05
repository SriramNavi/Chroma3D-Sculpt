"""Safe policy construction, validation and deterministic hashing."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Iterable

from ..models.optimization_models import (
    OptimizationPolicy, OptimizationPolicySnapshot, OptimizationOperationType, plain_value,
)


def default_policy() -> OptimizationPolicy:
    return OptimizationPolicy()


def policy_hash(policy: OptimizationPolicy) -> str:
    payload = plain_value(policy)
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def policy_snapshot(policy: OptimizationPolicy | None = None) -> OptimizationPolicySnapshot:
    selected = policy or default_policy()
    validate_policy(selected)
    return OptimizationPolicySnapshot(policy=selected, policy_hash=policy_hash(selected))


def validate_policy(policy: OptimizationPolicy) -> None:
    if not isinstance(policy, OptimizationPolicy):
        raise TypeError("policy must be an OptimizationPolicy.")
    seen: set[str] = set()
    for operation in policy.enabled_operation_families:
        value = OptimizationOperationType(operation).value
        if value in seen:
            raise ValueError(f"Duplicate enabled operation family: {value}")
        seen.add(value)
    if policy.experimental_remesh_enabled and OptimizationOperationType.EXPERIMENTAL_REMESH.value not in seen:
        raise ValueError("Experimental remesh cannot be enabled without enabling its operation family.")
    if policy.experimental_decimation_enabled and OptimizationOperationType.DECIMATION.value not in seen:
        raise ValueError("Decimation cannot be enabled without enabling its operation family.")


class PolicyRegistry:
    """Small in-memory registry used to fail closed on duplicate policy ids."""

    def __init__(self, policies: Iterable[OptimizationPolicy] = ()) -> None:
        self._policies: dict[str, OptimizationPolicy] = {}
        for policy in policies:
            self.add(policy)

    def add(self, policy: OptimizationPolicy) -> None:
        validate_policy(policy)
        if policy.policy_id in self._policies:
            raise ValueError(f"Duplicate policy id: {policy.policy_id}")
        self._policies[policy.policy_id] = policy

    def get(self, policy_id: str) -> OptimizationPolicy:
        try:
            return self._policies[policy_id]
        except KeyError as exc:
            raise KeyError(f"Unknown optimization policy: {policy_id}") from exc

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._policies))


__all__ = ("PolicyRegistry", "default_policy", "policy_hash", "policy_snapshot", "validate_policy")
