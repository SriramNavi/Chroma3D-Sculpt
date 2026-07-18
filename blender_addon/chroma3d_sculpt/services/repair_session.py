"""Repair workspace lifecycle and bounded independent mesh checkpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import bpy

from ..analysis_settings import AnalysisSettings
from ..models.analysis_result import AnalysisResult
from ..models.repair_models import (
    RepairCheckpointRecord,
    RepairDecision,
    RepairSession,
    RepairSessionStatus,
)
from ..repair_settings import RepairSettings
from ..session import store_result
from ..utilities.context import object_session_key
from ..utilities.repair_signatures import protected_source_snapshot, repair_workspace_signature
from .mesh_analyzer import analyze_mesh


SOURCE_CHANGED_MESSAGE = "The protected source changed during the repair session. End this session and start again."
STALE_PLAN_MESSAGE = "Repair plan is stale. Analyze the workspace and generate a new plan."

_active_session: RepairSession | None = None
_archived_session: RepairSession | None = None
_current_analysis: AnalysisResult | None = None
_checkpoint_meshes: dict[str, bpy.types.Mesh] = {}


def _pointer(value: Any | None) -> int:
    try:
        return int(value.as_pointer()) if value is not None else 0
    except (AttributeError, ReferenceError, TypeError):
        return 0


def _find_object(identity: int) -> bpy.types.Object | None:
    for obj in bpy.data.objects:
        if _pointer(obj) == identity:
            return obj
    return None


def source_object(session: RepairSession) -> bpy.types.Object | None:
    return _find_object(session.source_object_identity)


def workspace_object(session: RepairSession) -> bpy.types.Object | None:
    return _find_object(session.workspace_object_identity)


def get_active_session() -> RepairSession | None:
    return _active_session


def get_audit_session() -> RepairSession | None:
    return _active_session or _archived_session


def get_current_analysis(session: RepairSession | None = None) -> AnalysisResult | None:
    if session is not None and session is not _active_session:
        return None
    return _current_analysis


def set_current_analysis(session: RepairSession, result: AnalysisResult) -> None:
    global _current_analysis
    if session is not _active_session:
        raise ValueError("Repair session is no longer active.")
    _current_analysis = result
    session.current_analysis_id = result.analysis_id
    workspace = workspace_object(session)
    if workspace is not None:
        store_result(workspace, result)


def analysis_summary(result: AnalysisResult) -> dict[str, Any]:
    return {
        "analysis_id": result.analysis_id,
        "analyzed_at": result.analyzed_at.isoformat(),
        "duration_ms": result.duration_ms,
        "severity": result.severity.value,
        "geometry": result.to_dict()["geometry"],
        "dimensions": result.to_dict()["dimensions"],
        "topology": result.to_dict()["topology"],
        "surface_volume": result.to_dict()["surface_volume"],
        "shell_count": len(result.shells),
        "tiny_shell_candidate_ids": list(result.tiny_shell_candidate_ids),
        "build_volume": result.to_dict()["build_volume"],
        "checks": result.to_dict()["checks"],
        "warnings": list(result.warnings),
        "errors": list(result.errors),
    }


def _checkpoint_record(mesh: bpy.types.Mesh, workspace: bpy.types.Object, operation_id: str, *, initial: bool) -> RepairCheckpointRecord:
    return RepairCheckpointRecord(
        checkpoint_id=str(uuid4()),
        operation_id=operation_id,
        created_at=datetime.now(timezone.utc),
        workspace_signature=repair_workspace_signature(workspace),
        mesh_datablock_identity=_pointer(mesh),
        vertex_count=len(mesh.vertices),
        edge_count=len(mesh.edges),
        face_count=len(mesh.polygons),
        initial=initial,
    )


def _store_checkpoint(session: RepairSession, workspace: bpy.types.Object, operation_id: str, *, initial: bool = False) -> RepairCheckpointRecord:
    snapshot = workspace.data.copy()
    snapshot.name = f"{workspace.data.name}_Checkpoint"
    record = _checkpoint_record(snapshot, workspace, operation_id, initial=initial)
    _checkpoint_meshes[record.checkpoint_id] = snapshot
    session.checkpoint_records.append(record)
    return record


def _remove_mesh(mesh: bpy.types.Mesh | None) -> None:
    if mesh is not None and mesh.users == 0:
        bpy.data.meshes.remove(mesh)


def discard_checkpoint(session: RepairSession, checkpoint_id: str) -> None:
    snapshot = _checkpoint_meshes.pop(checkpoint_id, None)
    _remove_mesh(snapshot)
    for record in session.checkpoint_records:
        if record.checkpoint_id == checkpoint_id:
            record.retained = False
            break


def _evict_history(session: RepairSession) -> None:
    retained = [item for item in session.checkpoint_records if item.retained and not item.initial]
    while len(retained) > session.settings_snapshot.maximum_repair_checkpoints:
        oldest = retained.pop(0)
        discard_checkpoint(session, oldest.checkpoint_id)


def create_operation_checkpoint(session: RepairSession, operation_id: str) -> RepairCheckpointRecord:
    workspace = workspace_object(session)
    if workspace is None or workspace.data is None:
        raise RuntimeError("Repair workspace or mesh datablock no longer exists.")
    record = _store_checkpoint(session, workspace, operation_id)
    return record


def enforce_checkpoint_history(session: RepairSession) -> None:
    """Evict only after a geometry-changing operation succeeds."""

    _evict_history(session)


def restore_checkpoint(session: RepairSession, checkpoint_id: str, *, consume: bool) -> None:
    workspace = workspace_object(session)
    snapshot = _checkpoint_meshes.get(checkpoint_id)
    if workspace is None or snapshot is None:
        raise RuntimeError("Repair checkpoint is unavailable.")
    old_mesh = workspace.data
    old_name = str(old_mesh.name)
    restored = snapshot.copy()
    workspace.data = restored
    if old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)
    restored.name = old_name
    session.workspace_mesh_identity = _pointer(restored)
    session.workspace_mesh_name = str(restored.name)
    session.current_workspace_signature = repair_workspace_signature(workspace)
    if consume:
        discard_checkpoint(session, checkpoint_id)


def clear_checkpoints(session: RepairSession, *, keep_initial: bool = False) -> None:
    for record in session.checkpoint_records:
        if keep_initial and record.initial:
            continue
        if record.retained:
            discard_checkpoint(session, record.checkpoint_id)


def start_session(
    source: bpy.types.Object,
    scene: bpy.types.Scene,
    repair_settings: RepairSettings,
    analysis_settings: AnalysisSettings,
    *,
    blender_version: str,
    blend_file_path: str,
) -> RepairSession:
    global _active_session, _archived_session, _current_analysis
    if _active_session is not None and _active_session.status in {
        RepairSessionStatus.ACTIVE,
        RepairSessionStatus.PLAN_READY,
        RepairSessionStatus.REPAIRING,
        RepairSessionStatus.REPAIRED,
        RepairSessionStatus.FAILED,
    }:
        raise RuntimeError("Another repair session is active. Accept or roll it back before starting a new session.")
    if source is None or source.type != "MESH" or source.data is None:
        raise ValueError("Select a valid mesh object before starting a repair session.")
    if source.mode == "EDIT":
        raise ValueError("Exit Edit Mode before starting a repair session.")
    if len(source.data.vertices) == 0 or len(source.data.polygons) == 0:
        raise ValueError("An empty mesh or a mesh without faces cannot start a repair session.")

    captured_active = object_session_key(bpy.context.view_layer.objects.active)
    captured_selected = tuple(sorted(filter(None, (object_session_key(obj) for obj in bpy.context.selected_objects))))
    source_snapshot = protected_source_snapshot(source, blend_file_path)
    workspace = source.copy()
    workspace_mesh = source.data.copy()
    workspace.data = workspace_mesh
    workspace.name = f"{source.name}_Chroma3D_Repair"
    workspace_mesh.name = f"{source.data.name}_Chroma3D_Repair"
    try:
        for collection in source.users_collection:
            collection.objects.link(workspace)
        if workspace is source or workspace.data is source.data:
            raise RuntimeError("Repair workspace isolation failed.")
        workspace_signature = repair_workspace_signature(workspace)
        session = RepairSession(
            session_id=str(uuid4()),
            started_at=datetime.now(timezone.utc),
            status=RepairSessionStatus.ACTIVE,
            source_object_name=str(source.name),
            source_object_identity=_pointer(source),
            source_mesh_name=str(source.data.name),
            source_mesh_identity=_pointer(source.data),
            workspace_object_name=str(workspace.name),
            workspace_object_identity=_pointer(workspace),
            workspace_mesh_name=str(workspace.data.name),
            workspace_mesh_identity=_pointer(workspace.data),
            source_signature=str(source_snapshot["protected_sha256"]),
            source_snapshot=source_snapshot,
            initial_workspace_signature=workspace_signature,
            current_workspace_signature=workspace_signature,
            settings_snapshot=repair_settings.snapshot(),
            initial_checkpoint_id="",
            captured_active_identity=captured_active,
            captured_selected_identities=captured_selected,
            limitations=[
                "Original source preserved; workspace repair still requires human review.",
                "An unfinished repair session is not guaranteed to survive Blender restart.",
                "No remeshing, large-hole reconstruction, boolean repair, wall-thickness repair, AI, or printability guarantee.",
                "Manual real-statue repair UAT is deferred.",
            ],
        )
        initial = _store_checkpoint(session, workspace, "INITIAL", initial=True)
        session.initial_checkpoint_id = initial.checkpoint_id
        result = analyze_mesh(
            workspace,
            scene,
            settings=analysis_settings,
            blender_version=blender_version,
            blend_file_path=blend_file_path,
        )
        if result.errors:
            raise RuntimeError("Initial workspace diagnostics failed: " + "; ".join(result.errors))
        session.before_analysis = analysis_summary(result)
        session.current_analysis_id = result.analysis_id
        _active_session = session
        _archived_session = None
        _current_analysis = result
        store_result(workspace, result)
        workspace.select_set(True)
        bpy.context.view_layer.objects.active = workspace
        return session
    except Exception:
        for checkpoint_id, mesh in list(_checkpoint_meshes.items()):
            if mesh.name.startswith(workspace_mesh.name):
                _checkpoint_meshes.pop(checkpoint_id, None)
                _remove_mesh(mesh)
        for collection in tuple(workspace.users_collection):
            collection.objects.unlink(workspace)
        bpy.data.objects.remove(workspace)
        _remove_mesh(workspace_mesh)
        raise


def archive_session(session: RepairSession) -> None:
    global _active_session, _archived_session, _current_analysis
    _archived_session = session
    if _active_session is session:
        _active_session = None
    _current_analysis = None


def restore_captured_selection(session: RepairSession) -> None:
    selected = set(session.captured_selected_identities)
    for obj in bpy.context.scene.objects:
        try:
            obj.select_set(_pointer(obj) in selected)
        except RuntimeError:
            continue
    active = _find_object(session.captured_active_identity or 0)
    if active is not None:
        bpy.context.view_layer.objects.active = active


def clear_runtime() -> None:
    """Release temporary checkpoints on extension unload; never delete the workspace."""

    global _active_session, _archived_session, _current_analysis
    for mesh in tuple(_checkpoint_meshes.values()):
        _remove_mesh(mesh)
    _checkpoint_meshes.clear()
    _active_session = None
    _archived_session = None
    _current_analysis = None
