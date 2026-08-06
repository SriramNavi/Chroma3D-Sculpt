"""Sprint 6 orchestration with all geometry mutations delegated to Sprint 5."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from ..metadata import DISPLAY_VERSION
from ..models.intelligent_optimization_models import IntelligentSessionState, StrategyState
from .constraint_engine import constraint_set_hash
from .intelligent_optimization_audit import build_audit, write_json_audit, write_markdown_audit
from .intelligent_optimization_session import (
    archive_session,
    current_objective_profile,
    current_search_policy,
    get_active_session,
    get_controlled_session,
    start_intelligent_session,
    update_runtime_inputs,
)
from .optimization_coordinator import (
    accept_optimized_copy as sprint5_accept,
    apply_selected_step as sprint5_apply_step,
    discard_workspace as sprint5_discard,
    generate_session_candidates as sprint5_generate_candidates,
    generate_session_plan as sprint5_generate_plan,
    restore_session_to_start as sprint5_restore_start,
)
from .optimization_policy import policy_hash as sprint5_policy_hash
from .strategy_evaluator import evaluate_strategies
from .strategy_explainer import explain_strategy
from .strategy_generator import generate_strategies
from .pareto_frontier import build_pareto_frontier, frontier_is_current
from .strategy_history import add_history_entry, history_entry
from .strategy_ranker import rank_strategies, recommend_strategy
from ..models.intelligent_optimization_models import StrategyEvaluation


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_for(session: Any, source: Any | None = None) -> Any:
    if source is not None:
        return source
    try:
        import bpy
        identity = int(session.source_identity.get("object_identity", 0))
        for item in bpy.data.objects:
            if int(item.as_pointer()) == identity:
                return item
    except (ImportError, AttributeError, RuntimeError):
        pass
    raise RuntimeError("The protected source object is unavailable.")


def _ensure_active() -> tuple[Any, Any, Any]:
    session = get_active_session()
    controlled = get_controlled_session()
    if session is None or controlled is None:
        raise RuntimeError("No active intelligent optimization session.")
    return session, controlled, current_search_policy()


def _mark_stale(session: Any, reason: str) -> None:
    session.state = IntelligentSessionState.STALE
    session.stale_events.append({"at": _now(), "reason_code": reason})


def stale_reason(session: Any, *, source: Any | None = None) -> str:
    resolved_source = source
    try:
        from ..utilities.optimization_signatures import source_signature
        if resolved_source is None:
            resolved_source = _source_for(session)
        if str(source_signature(resolved_source).get("source_signature", "")) != session.source_signature:
            return "SOURCE_SIGNATURE_CHANGED"
    except (RuntimeError, TypeError, ValueError):
        return "SOURCE_SIGNATURE_UNAVAILABLE"
    policy = current_search_policy() if get_active_session() is session else None
    if policy is not None and session.search_policy_hash != policy.policy_hash:
        return "SEARCH_POLICY_CHANGED"
    if policy is not None and session.constraint_set_hash != policy.constraints.constraint_set_hash:
        return "CONSTRAINT_SET_CHANGED"
    if session.strategy_set is not None and session.strategy_set_hash and session.strategy_set.strategy_set_hash != session.strategy_set_hash:
        return "STRATEGY_SET_CHANGED"
    if session.frontier is not None and session.pareto_frontier_hash and session.frontier.frontier_hash != session.pareto_frontier_hash:
        return "PARETO_FRONTIER_CHANGED"
    return ""


def ensure_current(session: Any, *, source: Any | None = None) -> None:
    reason = stale_reason(session, source=source)
    if reason:
        _mark_stale(session, reason)
        raise RuntimeError(f"Intelligent optimization evidence is stale: {reason}")


def generate_intelligent_strategies(session: Any | None = None, *, source: Any | None = None, build_volume_mm: tuple[float, float, float] | None = None) -> Any:
    active, controlled, policy = _ensure_active()
    if session is not None and session is not active:
        raise RuntimeError("The requested intelligent session is not active.")
    ensure_current(active, source=source)
    source_object = _source_for(active, source)
    if not controlled.candidates:
        sprint5_generate_candidates(controlled, source=source_object, policy=controlled.policy_snapshot.policy if controlled.policy_snapshot else None, build_volume_mm=build_volume_mm)
    strategy_set = generate_strategies(
        controlled.candidates,
        policy=policy,
        objective_profile=current_objective_profile().to_dict(),
        source_signature=active.source_signature,
        process_context_hash=active.process_context_hash,
        feature_flag_hash=active.feature_flag_hash,
        implementation_fingerprint=active.implementation_fingerprint,
    )
    active.strategy_set = strategy_set
    active.strategy_set_hash = strategy_set.strategy_set_hash
    active.state = {
        "CANCELLED": IntelligentSessionState.CANCELLED,
        "BUDGET_EXHAUSTED": IntelligentSessionState.BUDGET_EXHAUSTED,
    }.get(strategy_set.status, IntelligentSessionState.SEARCH_COMPLETE)
    active.budget_usage = strategy_set.budget_usage
    return strategy_set


def rerun_intelligent_search(
    *,
    settings: Any | None = None,
    policy: Any | None = None,
    source: Any | None = None,
    build_volume_mm: tuple[float, float, float] | None = None,
) -> Any:
    """Update objectives or constraints, invalidate derived evidence, and re-run bounded search."""
    active, _controlled, _current_policy = _ensure_active()
    source_object = _source_for(active, source)
    update_runtime_inputs(settings=settings, policy=policy)
    return generate_intelligent_strategies(active, source=source_object, build_volume_mm=build_volume_mm)


def evaluate_intelligent_strategies(session: Any | None = None, *, baseline_values: Mapping[str, Any] | None = None, baseline_evidence_states: Mapping[str, Any] | None = None, source: Any | None = None) -> tuple[StrategyEvaluation, ...]:
    active, _controlled, policy = _ensure_active()
    if session is not None and session is not active:
        raise RuntimeError("The requested intelligent session is not active.")
    ensure_current(active, source=source)
    if active.strategy_set is None:
        raise RuntimeError("Generate strategies before evaluating them.")
    values = dict(baseline_values or {})
    if source is not None and not values:
        from .optimization_comparison import object_facts
        facts = object_facts(source)
        values.update({
            "build_volume_fit": 1.0 if facts.get("build_fit") else 0.0,
            "height": facts.get("height"),
            "triangle_count": facts.get("triangle_count"),
            "geometry_fidelity": 1.0,
            "fidelity_status": "PASS",
            "critical_defect_introduced": False,
            "source_protected": True,
        })
    results, usage, status = evaluate_strategies(active.strategy_set, baseline_values=values, baseline_evidence_states=baseline_evidence_states, profile=current_objective_profile(), constraints=policy.constraints, policy=policy)
    active.evaluations = list(results)
    active.budget_usage = usage
    active.state = IntelligentSessionState.BUDGET_EXHAUSTED if status == "BUDGET_EXHAUSTED" else IntelligentSessionState.SEARCH_COMPLETE
    return results


def build_intelligent_frontier(session: Any | None = None) -> Any:
    active, _controlled, policy = _ensure_active()
    if session is not None and session is not active:
        raise RuntimeError("The requested intelligent session is not active.")
    ensure_current(active)
    if not active.evaluations:
        raise RuntimeError("Evaluate strategies before building the Pareto frontier.")
    frontier = build_pareto_frontier(active.evaluations, tolerance=policy.dominance_tolerance, max_points=policy.budget.max_pareto_points, strategy_set_hash=active.strategy_set_hash)
    active.frontier = frontier
    active.pareto_frontier_hash = frontier.frontier_hash
    active.state = IntelligentSessionState.REVIEW_REQUIRED
    return frontier


def rank_intelligent_strategies(session: Any | None = None, *, method: str | None = None, user_priority: Sequence[str] = ()) -> Any:
    active, _controlled, _policy = _ensure_active()
    if session is not None and session is not active:
        raise RuntimeError("The requested intelligent session is not active.")
    ensure_current(active)
    if active.frontier is None:
        raise RuntimeError("Build the Pareto frontier before ranking strategies.")
    method_value = method or current_search_policy().to_dict().get("ranking_method", "CONSTRAINT_FIRST")
    non_dominated = tuple(point.strategy_id for point in active.frontier.points)
    active.rankings = list(rank_strategies(active.evaluations, method=method_value, profile=current_objective_profile(), user_priority=user_priority, non_dominated_strategy_ids=non_dominated))
    active.recommendation = recommend_strategy(active.rankings, alternatives=non_dominated)
    if active.recommendation:
        active.selected_strategy_id = active.recommendation.strategy_id
        active.state = IntelligentSessionState.REVIEW_REQUIRED
    active.explanations = [
        explain_strategy(strategy, evaluation, next((item for item in active.rankings if item.strategy_id == strategy.strategy_id), None), alternatives=non_dominated)
        for strategy in (active.strategy_set.strategies if active.strategy_set else ())
        for evaluation in active.evaluations if evaluation.strategy_id == strategy.strategy_id
    ]
    return tuple(active.rankings)


def select_strategy(strategy_id: str, *, allow_dominated: bool = False) -> Any:
    active, _controlled, _policy = _ensure_active()
    ensure_current(active)
    strategy = next((item for item in (active.strategy_set.strategies if active.strategy_set else ()) if item.strategy_id == strategy_id), None)
    if strategy is None:
        raise KeyError(f"Unknown strategy: {strategy_id}")
    frontier_ids = {item.strategy_id for item in (active.frontier.points if active.frontier else ())}
    if strategy_id not in frontier_ids and not allow_dominated:
        raise RuntimeError("Selecting a dominated strategy requires an explicit warning override.")
    active.selected_strategy_id = strategy_id
    strategy = strategy if strategy.state == StrategyState.SELECTED else strategy
    active.state = IntelligentSessionState.REVIEW_REQUIRED
    return strategy


def preview_selected_strategy(*, strategy_id: str | None = None) -> Mapping[str, Any]:
    active, controlled, _policy = _ensure_active()
    selected_id = strategy_id or active.selected_strategy_id
    if not selected_id:
        raise RuntimeError("Select a strategy before previewing it.")
    select_strategy(selected_id, allow_dominated=True)
    strategy = next(item for item in active.strategy_set.strategies if item.strategy_id == selected_id)
    preview = {"at": _now(), "strategy_id": selected_id, "steps": [step.to_dict() for step in strategy.steps], "state": "ISOLATED_WORKSPACE_PREVIEW", "mutated_source": False, "measured": False, "limitations": ["Preview is isolated and advisory; explicit execution remains required."]}
    active.preview_audit.append(preview)
    active.state = IntelligentSessionState.PREVIEW_ACTIVE
    return preview


def execute_selected_strategy(*, source: Any | None = None, strategy_id: str | None = None, approved: bool = False, blend_file_path: str = "") -> tuple[Any, ...]:
    active, controlled, _policy = _ensure_active()
    ensure_current(active, source=source)
    selected_id = strategy_id or active.selected_strategy_id
    if not approved:
        raise RuntimeError("Explicit user approval is required before strategy execution.")
    if not selected_id or active.strategy_set is None:
        raise RuntimeError("Select a strategy before execution.")
    source_object = _source_for(active, source)
    strategy = next((item for item in active.strategy_set.strategies if item.strategy_id == selected_id), None)
    if strategy is None:
        raise KeyError(f"Unknown strategy: {selected_id}")
    if not controlled.candidates:
        raise RuntimeError("Sprint 5 candidates are missing; execution is rejected.")
    sprint5_generate_plan(controlled, policy=controlled.policy_snapshot.policy if controlled.policy_snapshot else None)
    active.state = IntelligentSessionState.EXECUTING
    records: list[Any] = []
    try:
        for step in strategy.steps:
            record = sprint5_apply_step(controlled, source_object, step.candidate_id, approved=True, policy=controlled.policy_snapshot.policy if controlled.policy_snapshot else None, blend_file_path=blend_file_path)
            records.append(record)
            active.execution_audit.append({"step": step.to_dict(), "record": record.to_dict(), "source_mutated": False})
            if str(getattr(record.state, "value", record.state)) not in {"APPLIED", "NO_CHANGE", "UNDONE"}:
                raise RuntimeError(f"Sprint 5 rejected strategy step {step.order}: {getattr(record, 'error', '')}")
    except Exception as exc:
        try:
            sprint5_restore_start(controlled, source_object, blend_file_path=blend_file_path)
        finally:
            active.failures.append(str(exc))
            active.state = IntelligentSessionState.FAILED
        raise
    active.state = IntelligentSessionState.COMPARISON_READY
    return tuple(records)


def accept_selected_strategy(*, blend_file_path: str = "") -> Any:
    active, controlled, _policy = _ensure_active()
    if active.state != IntelligentSessionState.COMPARISON_READY:
        raise RuntimeError("A successfully executed and compared strategy is required before acceptance.")
    accepted = sprint5_accept(controlled, blend_file_path=blend_file_path)
    active.state = IntelligentSessionState.ACCEPTED
    active.selected_strategy_id = active.selected_strategy_id
    archive_session(active)
    return accepted


def discard_intelligent_workspace(*, blend_file_path: str = "") -> None:
    active, controlled, _policy = _ensure_active()
    sprint5_discard(controlled, blend_file_path=blend_file_path)
    active.state = IntelligentSessionState.DISCARDED
    archive_session(active)


def cancel_intelligent_search(*, blend_file_path: str = "") -> None:
    active, controlled, _policy = _ensure_active()
    active.cancellation_events.append({"at": _now(), "state": "CANCELLED"})
    try:
        sprint5_discard(controlled, blend_file_path=blend_file_path)
    finally:
        active.state = IntelligentSessionState.CANCELLED
        archive_session(active)


def record_strategy_history(session: Any | None = None) -> int:
    active, _controlled, _policy = _ensure_active()
    if session is not None and session is not active:
        raise RuntimeError("The requested intelligent session is not active.")
    if active.strategy_set is None:
        return 0
    rank_by_id = {item.strategy_id: item for item in active.rankings}
    added = 0
    for strategy in active.strategy_set.strategies:
        evaluation = next((item for item in active.evaluations if item.strategy_id == strategy.strategy_id), None)
        if evaluation is None:
            continue
        record = history_entry(
            source_identity=active.source_identity,
            source_signature=active.source_signature,
            strategy_fingerprint=strategy.fingerprint,
            objective_profile=current_objective_profile().to_dict(),
            search_policy=current_search_policy().to_dict(),
            constraints=current_search_policy().constraints.to_dict(),
            evaluation=evaluation.to_dict(),
            rank=rank_by_id.get(strategy.strategy_id).rank if strategy.strategy_id in rank_by_id else None,
            recommendation_state="RECOMMENDED" if active.recommendation and active.recommendation.strategy_id == strategy.strategy_id else "",
            software_version=DISPLAY_VERSION,
        )
        added += int(add_history_entry(active.history, record, maximum_entries=current_search_policy().budget.max_history_entries))
    active.budget_usage.history_entries = len(active.history.entries)
    return added


def export_intelligent_audit(path: str, *, markdown: bool = False, blender_version: str = "") -> Any:
    active = get_active_session()
    if active is None:
        raise RuntimeError("No active intelligent optimization session.")
    audit = build_audit(active, blender_version=blender_version, search_policy=current_search_policy().to_dict(), constraints=current_search_policy().constraints.to_dict())
    return write_markdown_audit(audit, path) if markdown else write_json_audit(audit, path)


__all__ = (
    "accept_selected_strategy", "build_intelligent_frontier", "cancel_intelligent_search", "discard_intelligent_workspace",
    "ensure_current", "evaluate_intelligent_strategies", "execute_selected_strategy", "export_intelligent_audit",
    "generate_intelligent_strategies", "preview_selected_strategy", "rank_intelligent_strategies", "record_strategy_history",
    "rerun_intelligent_search", "select_strategy", "stale_reason", "start_intelligent_session",
)
