"""Read-only deterministic optimization plan generation and stale validation."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence
from uuid import uuid4

from ..models.optimization_models import (
    OptimizationCandidate, OptimizationPlan, OptimizationPlanStep, OptimizationPolicy, ObjectiveSnapshot,
    OptimizationSession,
    plain_value,
)
from ..utilities.optimization_signatures import IMPLEMENTATION_FINGERPRINT, source_is_current, workspace_signature
from .optimization_policy import policy_hash


_ORDER = {
    "UNIFORM_SCALE": 10,
    "ORIENTATION": 20,
    "BUILD_PLATE_TRANSLATION": 30,
    "BASE_STABILIZATION": 40,
    "REPAIR_REUSE": 50,
    "DECIMATION": 60,
    "EXPERIMENTAL_REMESH": 70,
    "COMBINED_SCALE_ORIENTATION": 80,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _plan_hash(plan: OptimizationPlan) -> str:
    payload = plan.to_dict().copy()
    payload["plan_hash"] = ""
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _candidate_set_hash(candidates: Sequence[OptimizationCandidate]) -> str:
    payload = [item.to_dict() for item in candidates]
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def generate_optimization_plan(
    session: OptimizationSession,
    candidates: Sequence[OptimizationCandidate],
    *,
    policy: OptimizationPolicy | None = None,
    objectives: ObjectiveSnapshot | None = None,
) -> OptimizationPlan:
    if not session.source_signature:
        raise ValueError("A protected source signature is required before planning.")
    active_policy = policy or (session.policy_snapshot.policy if session.policy_snapshot else OptimizationPolicy())
    objective = objectives or session.objective_snapshot
    if objective is None:
        from ..optimization_settings import build_objective_snapshot
        objective = build_objective_snapshot()
    selected = sorted(
        candidates,
        key=lambda item: (_ORDER.get(item.category.value, 999), item.candidate_id),
    )[: active_policy.maximum_operation_count]
    steps: list[OptimizationPlanStep] = []
    for order, candidate in enumerate(selected, 1):
        prerequisite = ("WORKSPACE_READY",) if order == 1 else ("REVIEW_REQUIRED", "WORKSPACE_READY")
        reasons: tuple[str, ...] = ()
        if candidate.category.value not in active_policy.enabled_operation_families:
            reasons = ("Operation family is disabled by the selected policy.",)
        if candidate.evaluation.confidence.value == "NONE":
            reasons = reasons + ("Candidate confidence is below the policy minimum.",)
        steps.append(
            OptimizationPlanStep(
                order=order,
                candidate_id=candidate.candidate_id,
                operation=candidate.category,
                parameters=plain_value(candidate.geometry_operation.parameters if candidate.geometry_operation else {}),
                expected_objective_deltas=tuple(
                    {"objective": key, "expected_effect": value} for key, value in sorted(candidate.evaluation.expected_objective_effect.items())
                ),
                prerequisite_states=prerequisite,
                rejection_reasons=reasons,
                limitations=candidate.limitations + candidate.evaluation.limitations,
                approval_required=bool(candidate.geometry_operation and candidate.geometry_operation.approval_required),
            )
        )
    plan = OptimizationPlan(
        plan_id=f"s5-plan-{uuid4().hex}",
        session_id=session.session_id,
        created_at=_now(),
        source_signature=session.source_signature,
        workspace_signature=session.current_workspace_signature,
        policy_hash=policy_hash(active_policy),
        objective_hash=objective.objective_hash,
        implementation_fingerprint=IMPLEMENTATION_FINGERPRINT,
        process_context_hash=session.process_context_hash,
        feature_flag_hash=session.feature_flag_hash,
        performance_registry_version=session.performance_registry_version,
        candidate_set_hash=_candidate_set_hash(candidates),
        steps=steps,
        warnings=["Plan generation is read-only; no candidate is automatically applied."],
        limitations=["Plan is bounded and heuristic; it does not claim globally optimal orientation or guaranteed printability."],
    )
    plan.plan_hash = _plan_hash(plan)
    return plan


def plan_is_current(session: OptimizationSession, workspace: Any, source: Any | None = None, *, blend_file_path: str = "") -> tuple[bool, str]:
    plan = session.plan
    if plan is None:
        return False, "PLAN_MISSING"
    if plan.source_signature != session.source_signature:
        return False, "SOURCE_SIGNATURE_CHANGED"
    if source is not None and not source_is_current(source, session.source_snapshot, blend_file_path):
        return False, "SOURCE_CHANGED"
    current_workspace = workspace_signature(workspace)
    if current_workspace != session.current_workspace_signature:
        return False, "WORKSPACE_CHANGED"
    policy_hash_current = policy_hash(session.policy_snapshot.policy) if session.policy_snapshot else ""
    if plan.policy_hash != policy_hash_current:
        return False, "POLICY_CHANGED"
    if session.objective_snapshot and plan.objective_hash != session.objective_snapshot.objective_hash:
        return False, "OBJECTIVE_WEIGHTS_CHANGED"
    if plan.process_context_hash != session.process_context_hash:
        return False, "PROCESS_CONTEXT_CHANGED"
    if plan.feature_flag_hash != session.feature_flag_hash:
        return False, "FEATURE_FLAGS_CHANGED"
    if plan.performance_registry_version != session.performance_registry_version:
        return False, "PERFORMANCE_REGISTRY_CHANGED"
    if plan.candidate_set_hash != _candidate_set_hash(session.candidates):
        return False, "CANDIDATE_SET_CHANGED"
    if plan.implementation_fingerprint != IMPLEMENTATION_FINGERPRINT:
        return False, "IMPLEMENTATION_CHANGED"
    if plan.plan_hash != _plan_hash(plan):
        return False, "PLAN_HASH_CHANGED"
    return True, "CURRENT"


def validate_plan(session: OptimizationSession, workspace: Any, source: Any | None = None, *, blend_file_path: str = "") -> None:
    current, reason = plan_is_current(session, workspace, source, blend_file_path=blend_file_path)
    if not current:
        event = {"at": _now(), "reason_code": reason}
        session.stale_events.append(event)
        session.state = "STALE"
        raise RuntimeError(f"Optimization plan is stale: {reason}")


generate_plan = generate_optimization_plan

__all__ = ("generate_optimization_plan", "generate_plan", "plan_is_current", "validate_plan")
