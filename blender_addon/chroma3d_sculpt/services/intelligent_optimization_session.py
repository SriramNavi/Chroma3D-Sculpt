"""Runtime ownership for Sprint 6 sessions and the Sprint 5 workspace bridge."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping
from uuid import uuid4

from ..intelligent_optimization_settings import IntelligentOptimizationSettings, ObjectiveProfile, build_objective_profile
from ..metadata import DISPLAY_VERSION, PERFORMANCE_REGISTRY_VERSION
from ..models.intelligent_optimization_models import (
    IntelligentOptimizationSession,
    IntelligentSessionState,
    SearchBudgetUsage,
    SearchPolicy,
    StrategyEvaluation,
    stable_hash,
)
from ..utilities.optimization_signatures import source_signature
from .optimization_session import get_workspace as get_controlled_workspace
from .optimization_session import start_session as start_controlled_session


_active: IntelligentOptimizationSession | None = None
_archived: IntelligentOptimizationSession | None = None
_controlled_session: Any | None = None
_runtime_profiles: dict[str, ObjectiveProfile] = {}
_runtime_policies: dict[str, SearchPolicy] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_active_session() -> IntelligentOptimizationSession | None:
    return _active


def get_archived_session() -> IntelligentOptimizationSession | None:
    return _archived


def get_controlled_session() -> Any | None:
    return _controlled_session


def _source_identity(source: Any, signature: Mapping[str, Any]) -> dict[str, Any]:
    pointer = lambda value: int(value.as_pointer()) if value is not None and hasattr(value, "as_pointer") else 0
    return {
        "object_name": str(getattr(source, "name", "")),
        "object_identity": pointer(source),
        "mesh_name": str(getattr(getattr(source, "data", None), "name", "")),
        "mesh_identity": pointer(getattr(source, "data", None)),
        "geometry_sha256": str(signature.get("geometry_sha256", "")),
        "location": tuple(signature.get("location", ())),
        "rotation_euler": tuple(signature.get("rotation_euler", ())),
        "scale": tuple(signature.get("scale", ())),
    }


def start_intelligent_session(
    source: Any,
    scene: Any,
    *,
    settings: IntelligentOptimizationSettings | None = None,
    policy: SearchPolicy | None = None,
    sprint5_policy: Any | None = None,
    process_context_hash: str = "",
    hardware_profile_hash: str = "",
    material_profile_hash: str = "",
    feature_flag_hash: str = "",
    blend_file_path: str = "",
) -> IntelligentOptimizationSession:
    global _active, _controlled_session
    if _active is not None and _active.state not in {IntelligentSessionState.ACCEPTED, IntelligentSessionState.DISCARDED, IntelligentSessionState.CANCELLED, IntelligentSessionState.FAILED}:
        raise RuntimeError("An intelligent optimization session is already active.")
    selected_settings = settings or IntelligentOptimizationSettings()
    selected_policy = policy
    if selected_policy is None:
        from .search_policy import default_search_policy
        selected_policy = default_search_policy(selected_settings.search_mode, experimental_operations_enabled=selected_settings.experimental_operations_enabled)
    from .search_policy import validate_search_policy, policy_hash
    validate_search_policy(selected_policy)
    source_snapshot = source_signature(source, blend_file_path)
    controlled = start_controlled_session(source, scene, policy=sprint5_policy, blend_file_path=blend_file_path)
    _controlled_session = controlled
    objective = build_objective_profile(selected_settings.objective_preset, dict(selected_settings.custom_weights))
    _active = IntelligentOptimizationSession(
        session_id=f"s6-session-{uuid4().hex}",
        started_at=_now(),
        state=IntelligentSessionState.INPUTS_READY,
        source_identity=_source_identity(source, source_snapshot),
        source_signature=str(source_snapshot.get("source_signature", "")),
        source_transform_signature=stable_hash({"location": source_snapshot.get("location", ()), "rotation_euler": source_snapshot.get("rotation_euler", ()), "scale": source_snapshot.get("scale", ())}),
        hardware_profile_hash=hardware_profile_hash,
        material_profile_hash=material_profile_hash,
        process_context_hash=process_context_hash,
        feature_flag_hash=feature_flag_hash,
        performance_registry_version=PERFORMANCE_REGISTRY_VERSION,
        sprint5_policy_hash=str(getattr(getattr(controlled, "policy_snapshot", None), "policy_hash", "")),
        sprint5_objective_hash=str(getattr(getattr(controlled, "objective_snapshot", None), "objective_hash", "")),
        implementation_fingerprint="sprint6-intelligent-optimization-1.2-verification",
        ranking_method_hash=stable_hash({"ranking_method": selected_policy.ranking_method}),
        search_policy_hash=policy_hash(selected_policy),
        constraint_set_hash=selected_policy.constraints.constraint_set_hash,
        objective_profile_hash=objective.profile_hash,
        limitations=["Protected source remains owned by Sprint 5; this session only owns its model and isolated controlled workspace.", "Recommendation never auto-executes and never claims a global optimum."],
    )
    _runtime_profiles[_active.session_id] = objective
    _runtime_policies[_active.session_id] = selected_policy
    return _active


def current_objective_profile() -> ObjectiveProfile:
    if _active is None:
        raise RuntimeError("No active intelligent optimization session.")
    return _runtime_profiles[_active.session_id]


def current_search_policy() -> SearchPolicy:
    if _active is None:
        raise RuntimeError("No active intelligent optimization session.")
    return _runtime_policies[_active.session_id]


def update_runtime_inputs(
    *,
    settings: IntelligentOptimizationSettings | None = None,
    policy: SearchPolicy | None = None,
) -> IntelligentOptimizationSession:
    """Replace objectives or policy and invalidate all derived search evidence."""
    if _active is None:
        raise RuntimeError("No active intelligent optimization session.")
    current_profile = current_objective_profile()
    selected_settings = settings or IntelligentOptimizationSettings(
        objective_preset=current_profile.preset,
        custom_weights=tuple(current_profile.weights.items()),
    )
    selected_policy = policy or current_search_policy()
    from .search_policy import policy_hash, validate_search_policy
    validate_search_policy(selected_policy)
    objective = build_objective_profile(selected_settings.objective_preset, dict(selected_settings.custom_weights))
    _runtime_profiles[_active.session_id] = objective
    _runtime_policies[_active.session_id] = selected_policy
    _active.search_policy_hash = policy_hash(selected_policy)
    _active.constraint_set_hash = selected_policy.constraints.constraint_set_hash
    _active.objective_profile_hash = objective.profile_hash
    _active.ranking_method_hash = stable_hash({"ranking_method": selected_policy.ranking_method})
    _active.strategy_set = None
    _active.strategy_set_hash = ""
    _active.evaluations.clear()
    _active.frontier = None
    _active.pareto_frontier_hash = ""
    _active.rankings.clear()
    _active.recommendation = None
    _active.explanations.clear()
    _active.selected_strategy_id = ""
    _active.budget_usage = SearchBudgetUsage()
    _active.state = IntelligentSessionState.INPUTS_READY
    _active.warnings.append("Search evidence invalidated after objective or constraint update; bounded search must be re-run.")
    return _active


def clear_runtime() -> None:
    global _active, _archived, _controlled_session
    _active = None
    _archived = None
    _controlled_session = None
    _runtime_profiles.clear()
    _runtime_policies.clear()


def archive_session(session: IntelligentOptimizationSession) -> None:
    global _active, _archived, _controlled_session
    _archived = session
    _active = None
    _controlled_session = None


__all__ = (
    "archive_session", "clear_runtime", "current_objective_profile", "current_search_policy",
    "get_active_session", "get_archived_session", "get_controlled_session", "start_intelligent_session",
    "update_runtime_inputs",
)
