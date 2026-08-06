"""Resolve provider references to immutable current Sprint 5/6 objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ..models.ai_assistance_models import AssistancePolicy, RecommendationType, stable_hash


@dataclass(frozen=True, slots=True)
class TargetDescriptor:
    target_id: str
    fingerprint: str
    target_kind: str
    source_signature: str
    operations: tuple[Mapping[str, str], ...]
    feasible: bool = True
    stale: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id, "fingerprint": self.fingerprint, "target_kind": self.target_kind,
            "source_signature": self.source_signature, "operations": [dict(item) for item in self.operations],
            "feasible": self.feasible, "stale": self.stale,
        }


def operation_echo(operation: str, candidate_id: str, parameters: Mapping[str, Any]) -> dict[str, str]:
    return {"operation": str(operation), "candidate_id": str(candidate_id), "parameter_hash": stable_hash(dict(parameters))}


def describe_candidate(candidate: Any) -> TargetDescriptor:
    operation = str(getattr(candidate.category, "value", candidate.category))
    parameters = candidate.geometry_operation.parameters if getattr(candidate, "geometry_operation", None) else candidate.transform.to_dict()
    return TargetDescriptor(candidate.candidate_id, candidate.fingerprint, "CANDIDATE", candidate.source_signature, (operation_echo(operation, candidate.candidate_id, parameters),))


def describe_plan(plan: Any, candidates: Sequence[Any]) -> TargetDescriptor:
    by_id = {item.candidate_id: item for item in candidates}
    operations = tuple(operation_echo(str(getattr(step.operation, "value", step.operation)), step.candidate_id, step.parameters) for step in plan.steps)
    if any(step.candidate_id not in by_id for step in plan.steps):
        raise ValueError("Plan references a missing current candidate.")
    return TargetDescriptor(plan.plan_id, plan.plan_hash, "PLAN", plan.source_signature, operations, feasible=plan.status == "READY")


def describe_strategy(strategy: Any, *, source_signature: str, feasible: bool = True) -> TargetDescriptor:
    operations = tuple(operation_echo(step.operation, step.candidate_id, step.parameters) for step in strategy.steps)
    return TargetDescriptor(strategy.strategy_id, strategy.fingerprint, "STRATEGY", source_signature, operations, feasible=feasible)


def build_target_registry(intelligent_session: Any, controlled_session: Any) -> dict[str, TargetDescriptor]:
    targets = {item.candidate_id: describe_candidate(item) for item in controlled_session.candidates}
    if controlled_session.plan is not None:
        targets[controlled_session.plan.plan_id] = describe_plan(controlled_session.plan, controlled_session.candidates)
    feasible = {item.strategy_id: bool(item.feasible and not item.critical_regressions) for item in intelligent_session.evaluations}
    for item in intelligent_session.strategy_set.strategies if intelligent_session.strategy_set else ():
        targets[item.strategy_id] = describe_strategy(item, source_signature=intelligent_session.source_signature, feasible=feasible.get(item.strategy_id, False))
    return targets


def resolve_target(raw: Mapping[str, Any], registry: Mapping[str, TargetDescriptor], policy: AssistancePolicy, *, source_signature: str) -> TargetDescriptor | None:
    kind = RecommendationType(raw["recommendation_type"])
    if kind not in {RecommendationType.SELECT_EXISTING_STRATEGY, RecommendationType.SELECT_EXISTING_CANDIDATE, RecommendationType.SELECT_EXISTING_PLAN}:
        return None
    target = registry.get(str(raw["target_id"]))
    expected_kind = {RecommendationType.SELECT_EXISTING_STRATEGY: "STRATEGY", RecommendationType.SELECT_EXISTING_CANDIDATE: "CANDIDATE", RecommendationType.SELECT_EXISTING_PLAN: "PLAN"}[kind]
    if target is None or target.target_kind != expected_kind:
        raise ValueError("Recommendation references an unknown or wrong-kind current target.")
    if target.fingerprint != raw["target_fingerprint"]:
        raise ValueError("Recommendation target fingerprint does not match current local evidence.")
    if target.source_signature != source_signature or target.stale:
        raise ValueError("Recommendation target is stale or belongs to a different protected source.")
    if not target.feasible:
        raise ValueError("Recommendation target is not locally feasible.")
    echoed = tuple(dict(item) for item in raw["operation_echo"])
    if echoed != target.operations:
        raise ValueError("Recommendation operation or canonical parameter echo does not match the current deterministic target.")
    for item in target.operations:
        operation = item["operation"]
        if operation in policy.prohibited_operations or operation == "EXPERIMENTAL_REMESH":
            raise ValueError("Recommendation uses a prohibited operation.")
        if operation not in policy.allowed_operations:
            if operation not in policy.gated_operations:
                raise ValueError("Recommendation operation is not enabled by the local policy.")
    return target


__all__ = ("TargetDescriptor", "build_target_registry", "describe_candidate", "describe_plan", "describe_strategy", "operation_echo", "resolve_target")
