"""Runtime ownership, lifecycle and source-safe finalization for Sprint 5."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import bpy

from ..metadata import PERFORMANCE_REGISTRY_VERSION
from ..models.optimization_models import (
    AcceptanceRecord, DiscardRecord, OptimizationOperationState, OptimizationSession, OptimizationSessionState,
)
from ..optimization_settings import OptimizationSettings, build_objective_snapshot
from ..utilities.optimization_signatures import source_is_current, source_signature, workspace_signature
from .optimization_policy import default_policy, policy_snapshot
from .optimization_workspace import (
    cleanup_session_resources, create_checkpoint, create_optimization_workspace, restore_session_start, workspace_is_owned,
)


_active_session: OptimizationSession | None = None
_archived_session: OptimizationSession | None = None
_session_workspaces: dict[str, Any] = {}
_session_collections: dict[str, Any] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pointer(value: Any | None) -> int:
    try:
        return int(value.as_pointer()) if value is not None else 0
    except (AttributeError, ReferenceError, TypeError):
        return 0


def _find_object(identity: int) -> Any | None:
    for obj in bpy.data.objects:
        if _pointer(obj) == identity:
            return obj
    return None


def get_active_session() -> OptimizationSession | None:
    return _active_session


def get_archived_session() -> OptimizationSession | None:
    return _archived_session


def get_workspace(session: OptimizationSession) -> Any:
    workspace = _session_workspaces.get(session.session_id)
    if workspace is None or not workspace_is_owned(
        workspace,
        session.session_id,
        object_identity=session.workspace_object_identity,
        source_mesh_identity=session.source_mesh_identity,
    ):
        raise RuntimeError("Optimization workspace is missing or no longer owned by the session.")
    return workspace


def get_collection(session: OptimizationSession) -> Any | None:
    return _session_collections.get(session.session_id)


def start_session(
    source: Any,
    scene: Any,
    *,
    settings: OptimizationSettings | None = None,
    policy: Any | None = None,
    process_context_hash: str = "",
    feature_flag_hash: str = "",
    blend_file_path: str = "",
) -> OptimizationSession:
    global _active_session, _archived_session
    if _active_session is not None and _active_session.state not in {OptimizationSessionState.ACCEPTED, OptimizationSessionState.DISCARDED}:
        raise RuntimeError("Another optimization session is active.")
    selected_settings = settings or OptimizationSettings()
    selected_policy = policy or default_policy()
    source_snapshot = source_signature(source, blend_file_path)
    session_id = str(uuid4())
    workspace, collection, session_id = create_optimization_workspace(source, scene, session_id)
    try:
        if not source_is_current(source, source_snapshot, blend_file_path):
            raise RuntimeError("Protected source changed during workspace creation; optimization session rejected.")
        session = OptimizationSession(
            session_id=session_id, started_at=_now(), state=OptimizationSessionState.WORKSPACE_READY,
            source_object_name=str(source.name), source_object_identity=_pointer(source), source_mesh_name=str(source.data.name), source_mesh_identity=_pointer(source.data),
            source_signature=str(source_snapshot["source_signature"]), source_snapshot=source_snapshot,
            workspace_object_name=str(workspace.name), workspace_object_identity=_pointer(workspace), workspace_mesh_name=str(workspace.data.name), workspace_mesh_identity=_pointer(workspace.data),
            initial_workspace_signature=workspace_signature(workspace), current_workspace_signature=workspace_signature(workspace),
            process_context_hash=process_context_hash, feature_flag_hash=feature_flag_hash, performance_registry_version=PERFORMANCE_REGISTRY_VERSION,
            policy_snapshot=policy_snapshot(selected_policy), objective_snapshot=selected_settings.snapshot(),
            limitations=[
                "Protected source is never mutated by optimization operations.",
                "Workspace sessions are transient and are not guaranteed to survive Blender restart.",
                "Optimization is bounded advisory software evidence; no physical or slicer guarantee is made.",
            ],
        )
        create_checkpoint(session, workspace, process_context_hash=process_context_hash, policy_hash=session.policy_snapshot.policy_hash if session.policy_snapshot else "")
        _session_workspaces[session_id] = workspace
        _session_collections[session_id] = collection
        _active_session = session
        _archived_session = None
        # Keep the protected source selection/active-object contract intact.
        for item in bpy.context.selected_objects:
            item.select_set(False)
        source.select_set(True)
        bpy.context.view_layer.objects.active = source
        return session
    except Exception:
        cleanup_session_resources(session if "session" in locals() else OptimizationSession(
            session_id=session_id, started_at=_now(), state=OptimizationSessionState.FAILED,
            source_object_name=str(source.name), source_object_identity=_pointer(source), source_mesh_name=str(source.data.name), source_mesh_identity=_pointer(source.data),
            source_signature=str(source_snapshot["source_signature"]), source_snapshot=source_snapshot,
            workspace_object_name=str(workspace.name), workspace_object_identity=_pointer(workspace), workspace_mesh_name=str(workspace.data.name), workspace_mesh_identity=_pointer(workspace.data),
            initial_workspace_signature=workspace_signature(workspace), current_workspace_signature=workspace_signature(workspace),
        ), workspace, collection)
        raise


def restore_start(session: OptimizationSession) -> None:
    restore_session_start(session, get_workspace(session))
    session.current_workspace_signature = workspace_signature(get_workspace(session))
    session.state = OptimizationSessionState.REVIEW_REQUIRED


def accept_optimized_copy(session: OptimizationSession, *, blend_file_path: str = "") -> Any:
    global _active_session, _archived_session
    source = _find_object(session.source_object_identity)
    workspace = get_workspace(session)
    if source is None:
        raise RuntimeError("Protected source no longer exists; acceptance is rejected.")
    if not session.checkpoints or not session.plan or not session.candidates:
        raise RuntimeError("Acceptance requires complete session, candidate, plan, and checkpoint evidence.")
    current_workspace_signature = workspace_signature(workspace)
    if current_workspace_signature != session.current_workspace_signature:
        session.state = OptimizationSessionState.STALE
        session.stale_events.append({"at": _now(), "reason_code": "WORKSPACE_CHANGED_BEFORE_ACCEPT"})
        raise RuntimeError("Optimization workspace changed; acceptance is rejected.")
    latest_record = next((item for item in reversed(session.operation_records) if item.comparison), None)
    latest_comparison = session.comparisons[-1] if session.comparisons else None
    if latest_record is None or latest_comparison is None or latest_record.comparison != latest_comparison.to_dict():
        raise RuntimeError("Acceptance requires untampered comparison evidence.")
    if latest_record.state not in {OptimizationOperationState.APPLIED, OptimizationOperationState.UNDONE}:
        raise RuntimeError("Acceptance requires a successfully reviewed operation.")
    if latest_comparison.critical_regressions or latest_comparison.fidelity.get("status") == "FAIL":
        raise RuntimeError("Acceptance is rejected because comparison or fidelity evidence failed.")
    if not source_is_current(source, session.source_snapshot, blend_file_path):
        session.state = OptimizationSessionState.STALE
        session.stale_events.append({"at": _now(), "reason_code": "SOURCE_CHANGED_BEFORE_ACCEPT"})
        raise RuntimeError("Protected source changed; acceptance is rejected.")
    accepted_name = f"{session.source_object_name}_Chroma3D_Optimized_{session.session_id[:8]}"
    if bpy.data.objects.get(accepted_name) is not None:
        raise RuntimeError("A deterministic accepted-copy name already exists; acceptance is rejected.")
    accepted = workspace.copy()
    accepted.data = workspace.data.copy()
    accepted.name = accepted_name
    accepted.data.name = f"{workspace.data.name}_accepted"
    target_collection = next(iter(source.users_collection), None)
    if target_collection is None:
        bpy.context.scene.collection.objects.link(accepted)
    else:
        target_collection.objects.link(accepted)
    if not source_is_current(source, session.source_snapshot, blend_file_path):
        session.state = OptimizationSessionState.STALE
        session.stale_events.append({"at": _now(), "reason_code": "SOURCE_CHANGED_AFTER_ACCEPT"})
        accepted_mesh = accepted.data
        bpy.data.objects.remove(accepted, do_unlink=True)
        if accepted_mesh.users == 0:
            bpy.data.meshes.remove(accepted_mesh)
        raise RuntimeError("Protected source changed during acceptance; optimized copy was not retained.")
    final_workspace_signature = workspace_signature(workspace)
    try:
        cleanup_session_resources(session, workspace, _session_collections.get(session.session_id))
    except Exception:
        accepted_mesh = accepted.data
        bpy.data.objects.remove(accepted, do_unlink=True)
        if accepted_mesh.users == 0:
            bpy.data.meshes.remove(accepted_mesh)
        raise
    session.acceptance = AcceptanceRecord(_now(), session.source_object_name, str(accepted.name), session.source_signature, final_workspace_signature, True)
    session.state = OptimizationSessionState.ACCEPTED
    _archived_session = session
    _active_session = None
    _session_workspaces.pop(session.session_id, None)
    _session_collections.pop(session.session_id, None)
    return accepted


def discard_workspace(session: OptimizationSession, *, blend_file_path: str = "") -> None:
    global _active_session, _archived_session
    source = _find_object(session.source_object_identity)
    workspace = get_workspace(session)
    if session.state in {OptimizationSessionState.ACCEPTED, OptimizationSessionState.DISCARDED}:
        raise RuntimeError("This optimization session has already been finalized.")
    if not session.checkpoints:
        raise RuntimeError("Discard requires a retained checkpoint; cleanup is rejected.")
    current_workspace_signature = workspace_signature(workspace)
    if current_workspace_signature != session.current_workspace_signature:
        session.state = OptimizationSessionState.STALE
        session.stale_events.append({"at": _now(), "reason_code": "WORKSPACE_CHANGED_BEFORE_DISCARD"})
        raise RuntimeError("Optimization workspace changed; discard is rejected.")
    source_current = source is not None and source_is_current(source, session.source_snapshot, blend_file_path)
    if not source_current:
        session.state = OptimizationSessionState.STALE
        session.stale_events.append({"at": _now(), "reason_code": "SOURCE_CHANGED_BEFORE_DISCARD" if source is not None else "SOURCE_MISSING_BEFORE_DISCARD"})
        # Discarding session-owned resources cannot mutate the protected source.
        # Cleanup remains safe even when source evidence is stale or unavailable;
        # retaining an orphaned workspace would leak user-visible state.
    cleanup_session_resources(session, workspace, _session_collections.get(session.session_id))
    session.discard = DiscardRecord(_now(), session.source_object_name, session.source_signature, current_workspace_signature, True)
    session.state = OptimizationSessionState.DISCARDED
    _archived_session = session
    _active_session = None
    _session_workspaces.pop(session.session_id, None)
    _session_collections.pop(session.session_id, None)


def clear_runtime() -> None:
    global _active_session, _archived_session
    _active_session = None
    _archived_session = None
    _session_workspaces.clear()
    _session_collections.clear()


__all__ = (
    "accept_optimized_copy", "clear_runtime", "discard_workspace", "get_active_session", "get_archived_session", "get_collection", "get_workspace", "restore_start", "start_session",
)
