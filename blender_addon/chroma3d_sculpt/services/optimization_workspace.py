"""Isolated Blender workspace and bounded checkpoint ownership."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import bpy

from ..models.optimization_models import OptimizationCheckpoint, OptimizationSession
from ..utilities.optimization_signatures import workspace_signature


OWNER_PROPERTY = "chroma3d_optimization_session_id"
COLLECTION_PROPERTY = "chroma3d_optimization_owned_collection"
_checkpoint_meshes: dict[str, Any] = {}
_checkpoint_transforms: dict[str, tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]] = {}
_checkpoint_names: dict[str, str] = {}


def _pointer(value: Any | None) -> int:
    try:
        return int(value.as_pointer()) if value is not None else 0
    except (AttributeError, ReferenceError, TypeError):
        return 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _remove_mesh(mesh: Any) -> None:
    try:
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    except (AttributeError, ReferenceError, RuntimeError):
        return


def _owned_collection(scene: Any, session_id: str) -> Any:
    name = f"Chroma3D Optimization {session_id}"
    collection = bpy.data.collections.new(name)
    collection[COLLECTION_PROPERTY] = session_id
    scene.collection.children.link(collection)
    return collection


def create_optimization_workspace(source: Any, scene: Any, session_id: str | None = None) -> tuple[Any, Any, str]:
    if source is None or source.type != "MESH" or source.data is None:
        raise ValueError("Select a valid mesh object before starting optimization.")
    if source.mode == "EDIT":
        raise ValueError("Exit Edit Mode before starting optimization.")
    if len(source.data.vertices) == 0 or len(source.data.polygons) == 0:
        raise ValueError("An empty mesh or a mesh without faces cannot start optimization.")
    session_id = session_id or str(uuid4())
    collection = _owned_collection(scene, session_id)
    workspace = source.copy()
    workspace.data = source.data.copy()
    workspace.name = f"{source.name}_Chroma3D_Optimization_{session_id[:8]}"
    workspace.data.name = f"{source.data.name}_Chroma3D_Optimization_{session_id[:8]}"
    workspace[OWNER_PROPERTY] = session_id
    # ID properties use a signed 32-bit-compatible scalar on some Blender
    # builds; pointer identities are retained as strings to avoid truncation.
    workspace["chroma3d_optimization_source_identity"] = str(_pointer(source))
    workspace["chroma3d_optimization_source_mesh_identity"] = str(_pointer(source.data))
    collection.objects.link(workspace)
    if workspace is source or workspace.data is source.data:
        collection.objects.unlink(workspace)
        bpy.data.objects.remove(workspace)
        _remove_mesh(workspace.data)
        bpy.data.collections.remove(collection)
        raise RuntimeError("Optimization workspace isolation failed.")
    return workspace, collection, session_id


def workspace_is_owned(
    workspace: Any,
    session_id: str,
    *,
    object_identity: int | None = None,
    source_mesh_identity: int | None = None,
) -> bool:
    try:
        if str(workspace.get(OWNER_PROPERTY, "")) != session_id:
            return False
        if object_identity is not None and _pointer(workspace) != int(object_identity):
            return False
        if source_mesh_identity is not None and _pointer(workspace.data) == int(source_mesh_identity):
            return False
        return True
    except (AttributeError, ReferenceError):
        return False


def create_checkpoint(
    session: OptimizationSession,
    workspace: Any,
    *,
    candidate_id: str = "",
    process_context_hash: str = "",
    policy_hash: str = "",
    defer_eviction: bool = False,
) -> OptimizationCheckpoint:
    if not workspace_is_owned(workspace, session.session_id):
        raise RuntimeError("Cannot checkpoint a workspace not owned by this optimization session.")
    checkpoint_id = f"{session.session_id}:checkpoint:{len(session.checkpoints) + 1:04d}:{uuid4().hex[:8]}"
    mesh_copy = workspace.data.copy()
    mesh_copy.name = f"{workspace.data.name}_checkpoint_{len(session.checkpoints) + 1:04d}"
    _checkpoint_meshes[checkpoint_id] = mesh_copy
    _checkpoint_transforms[checkpoint_id] = (
        tuple(float(value) for value in workspace.location),
        tuple(float(value) for value in workspace.rotation_euler),
        tuple(float(value) for value in workspace.scale),
    )
    _checkpoint_names[checkpoint_id] = mesh_copy.name
    checkpoint = OptimizationCheckpoint(
        checkpoint_id=checkpoint_id,
        operation_index=len(session.operation_records),
        candidate_id=candidate_id,
        created_at=_now(),
        workspace_signature=workspace_signature(workspace),
        workspace_object_identity=_pointer(workspace),
        workspace_mesh_identity=_pointer(workspace.data),
        source_signature=session.source_signature,
        policy_hash=policy_hash,
        process_context_hash=process_context_hash,
    )
    session.checkpoints.append(checkpoint)
    session.checkpoint_history.append(checkpoint)
    if not defer_eviction:
        enforce_checkpoint_limit(session, exclude_checkpoint_id=checkpoint.checkpoint_id)
    return checkpoint


def enforce_checkpoint_limit(session: OptimizationSession, *, exclude_checkpoint_id: str = "") -> None:
    maximum = session.policy_snapshot.policy.maximum_checkpoint_count if session.policy_snapshot else 4
    while len(session.checkpoints) > maximum:
        # The session-start checkpoint has no candidate id and is never
        # eligible for eviction. Applied-operation checkpoints are bounded.
        removable = next(
            (
                item
                for item in session.checkpoints
                if item.candidate_id and item.checkpoint_id != exclude_checkpoint_id
            ),
            None,
        )
        if removable is None:
            break
        session.checkpoints.remove(removable)
        _discard_checkpoint(removable.checkpoint_id)


def _discard_checkpoint(checkpoint_id: str) -> None:
    mesh = _checkpoint_meshes.pop(checkpoint_id, None)
    _checkpoint_transforms.pop(checkpoint_id, None)
    _checkpoint_names.pop(checkpoint_id, None)
    _remove_mesh(mesh)


def discard_checkpoint(session: OptimizationSession, checkpoint_id: str) -> None:
    """Discard one session-owned checkpoint datablock and its live record."""

    retained = next((item for item in session.checkpoints if item.checkpoint_id == checkpoint_id), None)
    if retained is None:
        return
    if not retained.candidate_id:
        raise RuntimeError("The session-start checkpoint cannot be discarded.")
    session.checkpoints.remove(retained)
    _discard_checkpoint(checkpoint_id)


def restore_checkpoint(session: OptimizationSession, workspace: Any, checkpoint: OptimizationCheckpoint) -> None:
    if not workspace_is_owned(workspace, session.session_id, object_identity=session.workspace_object_identity, source_mesh_identity=session.source_mesh_identity):
        raise RuntimeError("Cannot restore a workspace not owned by this optimization session.")
    mesh = _checkpoint_meshes.get(checkpoint.checkpoint_id)
    transform = _checkpoint_transforms.get(checkpoint.checkpoint_id)
    if mesh is None or transform is None:
        raise RuntimeError("Checkpoint is unavailable or ambiguous.")
    old_mesh = workspace.data
    workspace.data = mesh.copy()
    workspace.data.name = f"{workspace.name}_restored_{checkpoint.operation_index:04d}"
    workspace.location = transform[0]
    workspace.rotation_euler = transform[1]
    workspace.scale = transform[2]
    _remove_mesh(old_mesh)


def restore_session_start(session: OptimizationSession, workspace: Any) -> None:
    if not session.checkpoints:
        raise RuntimeError("Optimization session has no retained checkpoint.")
    initial = session.checkpoints[0]
    restore_checkpoint(session, workspace, initial)
    session.current_workspace_signature = workspace_signature(workspace)


def cleanup_session_resources(session: OptimizationSession, workspace: Any | None, collection: Any | None) -> None:
    """Delete only resources owned by this session; never touch the source."""

    if collection is not None and str(collection.get(COLLECTION_PROPERTY, "")) == session.session_id and workspace is not None:
        unrelated = [
            item
            for item in collection.objects
            if item is not workspace and not workspace_is_owned(item, session.session_id, source_mesh_identity=session.source_mesh_identity)
        ]
        if unrelated:
            raise RuntimeError("Session collection contains an unrelated object; cleanup is rejected.")
    for checkpoint in tuple(session.checkpoints):
        if checkpoint.checkpoint_id.startswith(f"{session.session_id}:checkpoint:"):
            _discard_checkpoint(checkpoint.checkpoint_id)
    session.checkpoints.clear()
    if workspace is not None and workspace_is_owned(workspace, session.session_id, object_identity=session.workspace_object_identity, source_mesh_identity=session.source_mesh_identity):
        mesh = workspace.data
        for linked in tuple(workspace.users_collection):
            linked.objects.unlink(workspace)
        bpy.data.objects.remove(workspace)
        _remove_mesh(mesh)
    if collection is not None and str(collection.get(COLLECTION_PROPERTY, "")) == session.session_id:
        for parent in tuple(bpy.data.collections):
            if collection.name in parent.children:
                parent.children.unlink(collection)
        for scene in tuple(bpy.data.scenes):
            if collection.name in scene.collection.children:
                scene.collection.children.unlink(collection)
        if collection.users == 0:
            bpy.data.collections.remove(collection)


def clear_runtime() -> None:
    for checkpoint_id in tuple(_checkpoint_meshes):
        _discard_checkpoint(checkpoint_id)
    _checkpoint_meshes.clear()
    _checkpoint_transforms.clear()
    _checkpoint_names.clear()


__all__ = (
    "COLLECTION_PROPERTY", "OWNER_PROPERTY", "cleanup_session_resources", "clear_runtime",
    "create_checkpoint", "create_optimization_workspace", "discard_checkpoint", "enforce_checkpoint_limit", "restore_checkpoint", "restore_session_start", "workspace_is_owned",
)
