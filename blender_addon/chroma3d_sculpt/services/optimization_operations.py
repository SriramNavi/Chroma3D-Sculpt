"""Workspace-only operation execution with checkpointed rollback."""

from __future__ import annotations

from datetime import datetime, timezone
from math import isclose
from typing import Any
from uuid import uuid4

import bpy
import bmesh
from mathutils import Vector

from ..models.optimization_models import (
    OptimizationCandidate, OptimizationOperationRecord, OptimizationOperationState, OptimizationOperationType,
    OptimizationPolicy, OptimizationSession,
)
from ..repair_settings import RepairSettings
from ..services.repair_operations import (
    collapse_zero_length_edges, merge_duplicate_vertices, remove_degenerate_faces, remove_loose_geometry,
    orient_closed_shells_outward, repair_normal_consistency,
)
from ..utilities.optimization_signatures import source_is_current, workspace_signature
from .optimization_workspace import create_checkpoint, discard_checkpoint, enforce_checkpoint_limit, restore_checkpoint, workspace_is_owned


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mesh_counts(obj: Any) -> dict[str, int]:
    return {"vertices": len(obj.data.vertices), "edges": len(obj.data.edges), "faces": len(obj.data.polygons), "triangles": sum(max(0, len(poly.vertices) - 2) for poly in obj.data.polygons)}


def _clear_checkpoint(session: OptimizationSession, checkpoint_id: str) -> None:
    # The workspace service owns both the model record and the Blender
    # datablock; no-change attempts must not leak either one.
    discard_checkpoint(session, checkpoint_id)


def _apply_base_stabilization(workspace: Any, policy: OptimizationPolicy, parameters: dict[str, Any]) -> dict[str, Any]:
    height = float(parameters.get("height", 0.0))
    ratio = float(parameters.get("volume_ratio", 0.0))
    if height <= 0.0 or height > policy.maximum_base_modification_height:
        raise ValueError("Base stabilization height exceeds the selected policy.")
    if ratio <= 0.0 or ratio > policy.maximum_base_added_volume_ratio:
        raise ValueError("Base stabilization volume ratio exceeds the selected policy.")
    if not workspace.data.vertices:
        raise ValueError("Cannot stabilize an empty workspace.")
    coords = [Vector(vertex.co) for vertex in workspace.data.vertices]
    minimum = Vector((min(value.x for value in coords), min(value.y for value in coords), min(value.z for value in coords)))
    maximum = Vector((max(value.x for value in coords), max(value.y for value in coords), max(value.z for value in coords)))
    width = max((maximum.x - minimum.x) * 0.35, height * 2.0)
    depth = max((maximum.y - minimum.y) * 0.35, height * 2.0)
    base_volume = width * depth * height
    bounding_volume = max((maximum.x - minimum.x) * (maximum.y - minimum.y) * (maximum.z - minimum.z), 1e-9)
    if base_volume / bounding_volume > ratio + 1e-9:
        raise ValueError("Deterministic base would exceed the selected volume ratio.")
    bm = bmesh.new()
    try:
        bm.from_mesh(workspace.data)
        result = bmesh.ops.create_cube(bm, size=1.0)
        base_vertices = result.get("verts", ())
        bmesh.ops.scale(bm, vec=Vector((width, depth, height)), verts=base_vertices)
        bmesh.ops.translate(bm, vec=Vector((minimum.x + width * 0.5, minimum.y + depth * 0.5, minimum.z - height * 0.5)), verts=base_vertices)
        bm.to_mesh(workspace.data)
        workspace.data.update()
    finally:
        bm.free()
    return {"height": height, "volume_ratio": base_volume / bounding_volume, "base_volume": base_volume, "deterministic": True}


def _apply_decimation(workspace: Any, policy: OptimizationPolicy, parameters: dict[str, Any]) -> dict[str, Any]:
    ratio = float(parameters.get("ratio", 1.0))
    if not 0.0 < ratio <= policy.maximum_decimation_ratio:
        raise ValueError("Decimation ratio exceeds the selected policy.")
    before = _mesh_counts(workspace)
    modifier = workspace.modifiers.new("Chroma3D Optimization Decimation", "DECIMATE")
    modifier.ratio = ratio
    modifier.use_collapse_triangulate = True
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = workspace.evaluated_get(depsgraph)
    new_mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=depsgraph)
    old_mesh = workspace.data
    workspace.data = new_mesh
    workspace.modifiers.remove(modifier)
    try:
        if old_mesh.users == 0:
            bpy.data.meshes.remove(old_mesh)
    except RuntimeError:
        pass
    return {"before": before, "after": _mesh_counts(workspace), "ratio": ratio, "boundary_preserved_requested": bool(parameters.get("preserve_boundary", True))}


def _apply_repair(workspace: Any, parameters: dict[str, Any]) -> dict[str, Any]:
    operation = str(parameters.get("repair_operation", ""))
    settings = RepairSettings()
    functions = {
        "MERGE_DUPLICATE_VERTICES": merge_duplicate_vertices,
        "COLLAPSE_ZERO_LENGTH_EDGES": collapse_zero_length_edges,
        "REMOVE_DEGENERATE_FACES": remove_degenerate_faces,
        "REMOVE_LOOSE_GEOMETRY": remove_loose_geometry,
        "REPAIR_NORMAL_CONSISTENCY": repair_normal_consistency,
        "ORIENT_CLOSED_SHELLS_OUTWARD": orient_closed_shells_outward,
    }
    function = functions.get(operation)
    if function is None:
        raise ValueError(f"Unsupported or unselected repair reuse operation: {operation}")
    outcome = function(workspace, 1.0, settings)
    if outcome.status.value == "FAILED":
        raise RuntimeError("Reused Safe Repair operation failed; checkpoint restored.")
    return {"repair_operation": operation, "status": outcome.status.value, "metrics": outcome.metrics, "warnings": list(outcome.warnings)}


def _mutate_workspace(workspace: Any, candidate: OptimizationCandidate, policy: OptimizationPolicy) -> tuple[bool, dict[str, Any]]:
    operation = candidate.category
    parameters = dict(candidate.geometry_operation.parameters if candidate.geometry_operation else {})
    before = _mesh_counts(workspace)
    if operation == OptimizationOperationType.UNIFORM_SCALE:
        scale = float(parameters.get("scale", 1.0))
        if scale <= 0.0 or abs(scale - 1.0) > policy.maximum_uniform_scale_change + 1e-9:
            raise ValueError("Uniform scale is outside the selected bounded policy.")
        if isclose(scale, 1.0, abs_tol=1e-9):
            return False, {"counts_before": before, "no_change": True}
        workspace.scale = tuple(float(value) * scale for value in workspace.scale)
        return True, {"counts_before": before, "scale": scale}
    if operation == OptimizationOperationType.ORIENTATION:
        rotation = tuple(float(value) for value in parameters.get("rotation_euler", (0.0, 0.0, 0.0)))
        if len(rotation) != 3:
            raise ValueError("Orientation requires three Euler values.")
        if all(isclose(float(workspace.rotation_euler[index]), rotation[index], abs_tol=1e-9) for index in range(3)):
            return False, {"counts_before": before, "no_change": True}
        workspace.rotation_euler = rotation
        return True, {"counts_before": before, "rotation_euler": rotation}
    if operation == OptimizationOperationType.BUILD_PLATE_TRANSLATION:
        if not workspace.data.vertices:
            raise ValueError("Build-plate translation requires mesh vertices.")
        world_z = [float((workspace.matrix_world @ vertex.co).z) for vertex in workspace.data.vertices]
        if not world_z or any(not isinstance(value, float) for value in world_z):
            raise ValueError("Build-contact evidence is indeterminate.")
        target = float(parameters.get("target_z", 0.0))
        offset = target - min(world_z)
        if abs(offset) > policy.maximum_translation_distance:
            raise ValueError("Build-plate translation exceeds the selected policy.")
        if isclose(offset, 0.0, abs_tol=1e-9):
            return False, {"counts_before": before, "no_change": True, "lowest_world_z": min(world_z)}
        workspace.location.z += offset
        return True, {"counts_before": before, "translation_z": offset, "lowest_world_z_before": min(world_z)}
    if operation == OptimizationOperationType.BASE_STABILIZATION:
        return True, {"counts_before": before, **_apply_base_stabilization(workspace, policy, parameters)}
    if operation == OptimizationOperationType.DECIMATION:
        return True, {"counts_before": before, **_apply_decimation(workspace, policy, parameters)}
    if operation == OptimizationOperationType.EXPERIMENTAL_REMESH:
        raise ValueError("Experimental remesh is deferred: no safe bounded implementation is enabled.")
    if operation == OptimizationOperationType.REPAIR_REUSE:
        result = _apply_repair(workspace, parameters)
        return result.get("status") != "NO_CHANGE", {"counts_before": before, **result}
    if operation == OptimizationOperationType.COMBINED_SCALE_ORIENTATION:
        scale = float(parameters.get("scale", 1.0))
        rotation = tuple(parameters.get("rotation_euler", (0.0, 0.0, 0.0)))
        if scale <= 0.0 or abs(scale - 1.0) > policy.maximum_uniform_scale_change:
            raise ValueError("Combined scale exceeds the selected policy.")
        if len(rotation) != 3:
            raise ValueError("Combined orientation requires three Euler values.")
        if isclose(scale, 1.0, abs_tol=1e-9) and all(isclose(float(workspace.rotation_euler[index]), float(rotation[index]), abs_tol=1e-9) for index in range(3)):
            return False, {"counts_before": before, "no_change": True}
        workspace.scale = tuple(float(value) * scale for value in workspace.scale)
        workspace.rotation_euler = rotation
        return True, {"counts_before": before, "scale": scale, "rotation_euler": rotation}
    raise ValueError(f"Unsupported optimization operation: {operation.value}")


def apply_candidate(
    session: OptimizationSession,
    workspace: Any,
    source: Any,
    candidate: OptimizationCandidate,
    *,
    policy: OptimizationPolicy | None = None,
    approved: bool = False,
    blend_file_path: str = "",
) -> OptimizationOperationRecord:
    active_policy = policy or (session.policy_snapshot.policy if session.policy_snapshot else OptimizationPolicy())
    record = OptimizationOperationRecord(
        operation_id=f"s5-operation-{uuid4().hex}", candidate_id=candidate.candidate_id, operation=candidate.category,
        state=OptimizationOperationState.READY, started_at=_now(), before_workspace_signature=workspace_signature(workspace),
    )
    if not workspace_is_owned(workspace, session.session_id, object_identity=session.workspace_object_identity, source_mesh_identity=session.source_mesh_identity):
        record.state = OptimizationOperationState.REJECTED
        record.error = "Workspace ownership validation failed."
        session.operation_records.append(record)
        raise RuntimeError(record.error)
    if not source_is_current(source, session.source_snapshot, blend_file_path):
        record.state = OptimizationOperationState.STALE
        record.error = "Protected source changed before operation execution."
        session.stale_events.append({"at": _now(), "reason_code": "SOURCE_CHANGED_BEFORE_OPERATION"})
        session.state = "STALE"
        session.operation_records.append(record)
        raise RuntimeError(record.error)
    if candidate.category.value not in active_policy.enabled_operation_families:
        record.state = OptimizationOperationState.REJECTED
        record.error = "Operation family is disabled by the selected policy."
        session.operation_records.append(record)
        return record
    needs_approval = bool(candidate.geometry_operation and candidate.geometry_operation.approval_required)
    if needs_approval and not approved:
        record.state = OptimizationOperationState.REJECTED
        record.error = "Explicit approval is required for this operation."
        session.operation_records.append(record)
        return record
    checkpoint = None
    try:
        record.state = OptimizationOperationState.PLANNED
        session.state = "OPERATION_IN_PROGRESS"
        checkpoint = create_checkpoint(
            session,
            workspace,
            candidate_id=candidate.candidate_id,
            process_context_hash=session.process_context_hash,
            policy_hash=session.policy_snapshot.policy_hash if session.policy_snapshot else "",
            defer_eviction=True,
        )
        record.checkpoint_id = checkpoint.checkpoint_id
        changed, parameters = _mutate_workspace(workspace, candidate, active_policy)
        if not changed:
            record.state = OptimizationOperationState.NO_CHANGE
            record.parameters = parameters
            _clear_checkpoint(session, checkpoint.checkpoint_id)
            session.state = "REVIEW_REQUIRED"
            return record
        if not source_is_current(source, session.source_snapshot, blend_file_path):
            raise RuntimeError("Protected source changed during operation; optimization stopped.")
        record.state = OptimizationOperationState.APPLIED
        record.parameters = parameters
        record.after_workspace_signature = workspace_signature(workspace)
        enforce_checkpoint_limit(session, exclude_checkpoint_id=checkpoint.checkpoint_id)
        session.current_workspace_signature = record.after_workspace_signature
        session.state = "REVIEW_REQUIRED"
        return record
    except Exception as exc:
        if checkpoint is not None:
            restore_checkpoint(session, workspace, checkpoint)
            discard_checkpoint(session, checkpoint.checkpoint_id)
        record.state = OptimizationOperationState.FAILED
        record.error = str(exc)
        record.after_workspace_signature = workspace_signature(workspace)
        session.state = "FAILED"
        session.warnings.append("Failed optimization operation was rolled back to its last valid checkpoint.")
        return record
    finally:
        record.completed_at = _now()
        session.operation_records.append(record)


__all__ = ("apply_candidate",)
