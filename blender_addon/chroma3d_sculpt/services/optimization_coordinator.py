"""Public Sprint 5 workflow coordinator."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..models.optimization_models import OptimizationOperationState, OptimizationSessionState
from ..optimization_settings import OptimizationSettings
from ..utilities.optimization_signatures import source_is_current, workspace_signature
from .optimization_candidates import generate_candidates
from .optimization_comparison import compare_objects, compare_snapshots, object_facts
from .optimization_operations import apply_candidate
from .optimization_plan import generate_optimization_plan, validate_plan
from .optimization_policy import default_policy
from .optimization_session import (
    accept_optimized_copy, discard_workspace, get_workspace, restore_start, start_session,
)
from .optimization_workspace import discard_checkpoint, restore_checkpoint


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_session_candidates(
    session: Any,
    *,
    source: Any | None = None,
    policy: Any | None = None,
    objectives: Any | None = None,
    build_volume_mm: tuple[float, float, float] | None = None,
    advanced_preparation: Any | None = None,
    printability_report: Any | None = None,
) -> tuple[Any, ...]:
    workspace = get_workspace(session)
    if source is not None and not source_is_current(source, session.source_snapshot):
        session.state = OptimizationSessionState.STALE
        session.stale_events.append({"at": _now(), "reason_code": "SOURCE_CHANGED_BEFORE_CANDIDATES"})
        raise RuntimeError("Protected source changed; candidate generation is rejected.")
    candidates = generate_candidates(
        workspace, source_snapshot=session.source_snapshot, policy=policy or (session.policy_snapshot.policy if session.policy_snapshot else default_policy()),
        objectives=objectives or session.objective_snapshot, process_context_hash=session.process_context_hash,
        build_volume_mm=build_volume_mm, advanced_preparation=advanced_preparation, printability_report=printability_report,
    )
    session.candidates = list(candidates)
    return candidates


def generate_session_plan(session: Any, *, policy: Any | None = None, objectives: Any | None = None) -> Any:
    if not session.candidates:
        raise RuntimeError("Generate candidates before generating an optimization plan.")
    plan = generate_optimization_plan(session, session.candidates, policy=policy, objectives=objectives)
    session.plan = plan
    session.state = OptimizationSessionState.PLAN_READY
    return plan


def apply_selected_step(
    session: Any,
    source: Any,
    candidate_id: str,
    *,
    approved: bool = False,
    policy: Any | None = None,
    build_volume_mm: tuple[float, float, float] | None = None,
    blend_file_path: str = "",
) -> Any:
    workspace = get_workspace(session)
    validate_plan(session, workspace, source, blend_file_path=blend_file_path)
    candidate = next((item for item in session.candidates if item.candidate_id == candidate_id), None)
    if candidate is None:
        raise ValueError(f"Unknown optimization candidate: {candidate_id}")
    if session.plan and not any(item.candidate_id == candidate_id and not item.rejection_reasons for item in session.plan.steps):
        raise ValueError("Candidate is not an executable step in the current plan.")
    before = object_facts(workspace, build_volume_mm=build_volume_mm)
    record = apply_candidate(session, workspace, source, candidate, policy=policy, approved=approved, blend_file_path=blend_file_path)
    if record.state == OptimizationOperationState.APPLIED:
        after = object_facts(workspace, build_volume_mm=build_volume_mm)
        comparison = compare_snapshots(before, after, objectives=session.objective_snapshot, maximum_geometric_deviation=(policy or session.policy_snapshot.policy).maximum_geometric_deviation)
        record.comparison = comparison.to_dict()
        record.fidelity = comparison.fidelity
        session.comparisons.append(comparison)
        if comparison.fidelity.get("status") == "FAIL":
            checkpoint = next((item for item in session.checkpoints if item.checkpoint_id == record.checkpoint_id), None)
            if checkpoint is None:
                raise RuntimeError("Fidelity failure has no rollback checkpoint.")
            restore_checkpoint(session, workspace, checkpoint)
            discard_checkpoint(session, checkpoint.checkpoint_id)
            record.state = OptimizationOperationState.FAILED
            record.error = "Fidelity evidence failed; workspace restored to the pre-operation checkpoint."
            record.after_workspace_signature = workspace_signature(workspace)
            session.state = OptimizationSessionState.REVIEW_REQUIRED
    session.current_workspace_signature = workspace_signature(workspace)
    return record


def rerun_comparison(session: Any, *, policy: Any | None = None, build_volume_mm: tuple[float, float, float] | None = None) -> Any:
    """Recompute comparison evidence for the latest applied operation."""

    workspace = get_workspace(session)
    record = next((item for item in reversed(session.operation_records) if item.comparison), None)
    if record is None:
        raise RuntimeError("Apply an optimization step before re-running comparison.")
    before = dict(record.comparison.get("before", {}))
    after = object_facts(workspace, build_volume_mm=build_volume_mm)
    active_policy = policy or (session.policy_snapshot.policy if session.policy_snapshot else default_policy())
    comparison = compare_snapshots(
        before,
        after,
        objectives=session.objective_snapshot,
        maximum_geometric_deviation=active_policy.maximum_geometric_deviation,
    )
    record.comparison = comparison.to_dict()
    record.fidelity = comparison.fidelity
    session.comparisons.append(comparison)
    session.current_workspace_signature = workspace_signature(workspace)
    session.state = OptimizationSessionState.REVIEW_REQUIRED
    return comparison


def undo_last_step(session: Any, source: Any, *, blend_file_path: str = "") -> Any:
    workspace = get_workspace(session)
    if not source_is_current(source, session.source_snapshot, blend_file_path):
        session.state = OptimizationSessionState.STALE
        session.stale_events.append({"at": _now(), "reason_code": "SOURCE_CHANGED_BEFORE_UNDO"})
        raise RuntimeError("Protected source changed; undo is rejected.")
    record = next((item for item in reversed(session.operation_records) if item.state == OptimizationOperationState.APPLIED), None)
    if record is None or not record.checkpoint_id:
        raise RuntimeError("No applied optimization step is available to undo.")
    checkpoint = next((item for item in session.checkpoints if item.checkpoint_id == record.checkpoint_id), None)
    if checkpoint is None:
        raise RuntimeError("Undo checkpoint is missing or ambiguous.")
    restore_checkpoint(session, workspace, checkpoint)
    record.state = OptimizationOperationState.UNDONE
    record.after_workspace_signature = workspace_signature(workspace)
    session.current_workspace_signature = record.after_workspace_signature
    session.state = OptimizationSessionState.REVIEW_REQUIRED
    return record


def restore_session_to_start(session: Any, source: Any, *, blend_file_path: str = "") -> None:
    if not source_is_current(source, session.source_snapshot, blend_file_path):
        session.state = OptimizationSessionState.STALE
        session.stale_events.append({"at": _now(), "reason_code": "SOURCE_CHANGED_BEFORE_RESTORE"})
        raise RuntimeError("Protected source changed; restore is rejected.")
    restore_start(session)
    for record in session.operation_records:
        if record.state == OptimizationOperationState.APPLIED:
            record.state = OptimizationOperationState.UNDONE
    session.state = OptimizationSessionState.REVIEW_REQUIRED


__all__ = (
    "accept_optimized_copy", "apply_selected_step", "discard_workspace", "generate_session_candidates", "generate_session_plan", "rerun_comparison", "restore_session_to_start", "start_session", "undo_last_step",
)
