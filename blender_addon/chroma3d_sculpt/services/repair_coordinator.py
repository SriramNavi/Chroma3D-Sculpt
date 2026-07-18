"""Safety-gated orchestration for controlled workspace-only mesh repair."""

from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

import bpy

from ..analysis_settings import AnalysisSettings
from ..models.analysis_result import AnalysisResult, EvaluationStatus
from ..models.repair_models import (
    RepairCandidate,
    RepairCandidateType,
    RepairComparison,
    RepairDecision,
    RepairOperationRecord,
    RepairOperationStatus,
    RepairOperationType,
    RepairPlanStatus,
    RepairSession,
    RepairSessionStatus,
    SAFE_OPERATION_ORDER,
)
from ..repair_settings import RepairSettings
from ..utilities.repair_signatures import protected_source_is_current, repair_workspace_signature
from ..utilities.units import millimetres_per_blender_unit
from .mesh_analyzer import analyze_mesh
from .repair_operations import (
    collapse_zero_length_edges,
    fill_selected_small_holes,
    merge_duplicate_vertices,
    mesh_counts,
    orient_closed_shells_outward,
    remove_degenerate_faces,
    remove_loose_geometry,
    remove_selected_tiny_shells,
    repair_normal_consistency,
)
from .repair_plan import generate_plan as build_plan
from .repair_session import (
    SOURCE_CHANGED_MESSAGE,
    STALE_PLAN_MESSAGE,
    analysis_summary,
    archive_session,
    clear_checkpoints,
    create_operation_checkpoint,
    discard_checkpoint,
    enforce_checkpoint_history,
    get_current_analysis,
    restore_captured_selection,
    restore_checkpoint,
    set_current_analysis,
    source_object,
    workspace_object,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _validate_source(session: RepairSession, blend_file_path: str) -> bpy.types.Object:
    source = source_object(session)
    if source is None or source.data is None:
        raise RuntimeError("The protected source object or mesh datablock no longer exists.")
    if source.data.as_pointer() != session.source_mesh_identity:
        raise RuntimeError(SOURCE_CHANGED_MESSAGE)
    if not protected_source_is_current(source, session.source_snapshot, blend_file_path):
        raise RuntimeError(SOURCE_CHANGED_MESSAGE)
    return source


def _validate_workspace(session: RepairSession, *, expected_current: bool = True) -> bpy.types.Object:
    workspace = workspace_object(session)
    if workspace is None or workspace.data is None:
        raise RuntimeError("The repair workspace object or mesh datablock no longer exists.")
    if workspace.data.as_pointer() != session.workspace_mesh_identity:
        raise RuntimeError("Repair workspace mesh changed outside the session.")
    if expected_current and repair_workspace_signature(workspace) != session.current_workspace_signature:
        raise RuntimeError("Repair workspace changed outside the session. Analyze it and generate a new plan.")
    return workspace


def validate_active_session(
    session: RepairSession,
    *,
    blend_file_path: str,
    active_object: bpy.types.Object | None = None,
    require_workspace_active: bool = False,
) -> tuple[bpy.types.Object, bpy.types.Object]:
    if session.status in {RepairSessionStatus.ACCEPTED, RepairSessionStatus.ROLLED_BACK}:
        raise RuntimeError("This repair session has already ended.")
    source = _validate_source(session, blend_file_path)
    workspace = _validate_workspace(session)
    if source is workspace or source.data is workspace.data:
        raise RuntimeError("Source/workspace isolation failed; repair was blocked.")
    if require_workspace_active and active_object is not workspace:
        raise RuntimeError("Activate the current repair workspace before running a repair command.")
    return source, workspace


def generate_repair_plan(
    session: RepairSession,
    scene: bpy.types.Scene,
    settings: RepairSettings,
    *,
    blend_file_path: str,
    active_object: bpy.types.Object | None = None,
) -> Any:
    _, workspace = validate_active_session(
        session,
        blend_file_path=blend_file_path,
        active_object=active_object,
        require_workspace_active=active_object is not None,
    )
    factor, _, _ = millimetres_per_blender_unit(scene)
    plan = build_plan(session, workspace, factor, settings)
    session.plan = plan
    session.status = RepairSessionStatus.PLAN_READY
    return plan


def validate_plan(session: RepairSession, settings: RepairSettings, *, blend_file_path: str) -> None:
    plan = session.plan
    if plan is None or plan.status != RepairPlanStatus.READY:
        raise RuntimeError(STALE_PLAN_MESSAGE)
    if plan.session_id != session.session_id or plan.source_signature != session.source_signature:
        plan.status = RepairPlanStatus.STALE
        raise RuntimeError(STALE_PLAN_MESSAGE)
    _validate_source(session, blend_file_path)
    workspace = _validate_workspace(session)
    current = get_current_analysis(session)
    if (
        repair_workspace_signature(workspace) != plan.workspace_signature
        or plan.workspace_signature != session.current_workspace_signature
        or current is None
        or current.analysis_id != plan.analysis_id
        or current.analysis_id != session.current_analysis_id
        or plan.settings_snapshot != settings.snapshot()
    ):
        plan.status = RepairPlanStatus.STALE
        raise RuntimeError(STALE_PLAN_MESSAGE)


def _metric_summary(result: AnalysisResult, signature: str) -> dict[str, Any]:
    return {
        "vertices": result.geometry.vertex_count,
        "edges": result.geometry.edge_count,
        "faces": result.geometry.polygon_count,
        "triangles": result.geometry.triangle_count,
        "shell_count": len(result.shells),
        "boundary_edges": result.topology.boundary_edges,
        "non_manifold_edges": result.topology.non_manifold_edges,
        "vertex_manifold_anomalies": result.topology.vertex_manifold_anomalies,
        "loose_vertices": result.topology.loose_vertices,
        "loose_edges": result.topology.loose_edges,
        "zero_length_edges": result.topology.zero_length_edges,
        "degenerate_faces": result.topology.degenerate_faces,
        "potential_duplicate_vertices": result.topology.potential_duplicate_vertices,
        "orientation_state": result.topology.normal_consistency.value,
        "tiny_shell_candidates": len(result.tiny_shell_candidate_ids),
        "watertightness": result.topology.watertight_state.value,
        "dimensions_mm": [result.dimensions.width_mm, result.dimensions.depth_mm, result.dimensions.height_mm],
        "surface_area_mm2": result.surface_volume.total_surface_area_mm2,
        "reliable_volume_mm3": result.surface_volume.reliable_closed_shell_volume_mm3,
        "build_volume_result": result.build_volume.fit_state.value,
        "severity": result.severity.value,
        "analysis_duration_ms": result.duration_ms,
        "world_space_bounding_box_mm": [result.dimensions.width_mm, result.dimensions.depth_mm, result.dimensions.height_mm],
        "workspace_signature": signature,
    }


def compare_results(before: AnalysisResult, after: AnalysisResult, source_signature: str, workspace_signature: str) -> RepairComparison:
    first = _metric_summary(before, before.topology_signature.topology_sha256)
    second = _metric_summary(after, workspace_signature)
    issue_metrics = (
        "boundary_edges",
        "non_manifold_edges",
        "vertex_manifold_anomalies",
        "loose_vertices",
        "loose_edges",
        "zero_length_edges",
        "degenerate_faces",
        "potential_duplicate_vertices",
        "tiny_shell_candidates",
    )
    deltas: dict[str, Any] = {name: second[name] - first[name] for name in issue_metrics}
    improved = tuple(name for name in issue_metrics if second[name] < first[name])
    regressed = tuple(name for name in issue_metrics if second[name] > first[name])
    unchanged = tuple(name for name in issue_metrics if second[name] == first[name])
    deltas["source_signature"] = source_signature
    deltas["workspace_signature"] = workspace_signature
    return RepairComparison(
        before=first,
        after=second,
        deltas=deltas,
        improved=improved,
        unchanged=unchanged,
        regressed=regressed,
        skipped_checks=tuple(check.message for check in after.checks if check.status == EvaluationStatus.SKIPPED),
        failed_checks=tuple(check.message for check in after.checks if check.status == EvaluationStatus.FAILED),
    )


def _selected_candidates(session: RepairSession, candidate_type: RepairCandidateType) -> tuple[RepairCandidate, ...]:
    if session.plan is None:
        return ()
    return tuple(candidate for candidate in session.plan.candidates if candidate.candidate_type == candidate_type and candidate.selected)


def _dispatch_operation(
    operation: RepairOperationType,
    workspace: bpy.types.Object,
    factor: float,
    settings: RepairSettings,
    current_analysis: AnalysisResult,
    session: RepairSession,
) -> Any:
    if operation == RepairOperationType.MERGE_DUPLICATE_VERTICES:
        return merge_duplicate_vertices(workspace, factor, settings)
    if operation == RepairOperationType.COLLAPSE_ZERO_LENGTH_EDGES:
        return collapse_zero_length_edges(workspace, factor, settings)
    if operation == RepairOperationType.REMOVE_DEGENERATE_FACES:
        return remove_degenerate_faces(workspace, factor, settings)
    if operation == RepairOperationType.REMOVE_LOOSE_GEOMETRY:
        return remove_loose_geometry(workspace, factor, settings)
    if operation == RepairOperationType.REPAIR_NORMAL_CONSISTENCY:
        return repair_normal_consistency(workspace, factor, settings)
    if operation == RepairOperationType.ORIENT_CLOSED_SHELLS_OUTWARD:
        return orient_closed_shells_outward(workspace, factor, settings)
    if operation == RepairOperationType.REMOVE_SELECTED_TINY_SHELLS:
        return remove_selected_tiny_shells(
            workspace,
            factor,
            settings,
            _selected_candidates(session, RepairCandidateType.TINY_SHELL),
            current_analysis,
        )
    if operation == RepairOperationType.FILL_SELECTED_SMALL_HOLES:
        return fill_selected_small_holes(
            workspace,
            factor,
            settings,
            _selected_candidates(session, RepairCandidateType.SMALL_HOLE),
        )
    raise ValueError(f"Unsupported repair operation: {operation.value}")


def _run_analysis(workspace: bpy.types.Object, scene: bpy.types.Scene, settings: AnalysisSettings, blend_file_path: str) -> AnalysisResult:
    result = analyze_mesh(
        workspace,
        scene,
        settings=settings,
        blender_version=bpy.app.version_string,
        blend_file_path=blend_file_path,
    )
    if result.errors:
        raise RuntimeError("Post-repair diagnostics failed: " + "; ".join(result.errors))
    return result


def _apply_one(
    session: RepairSession,
    operation: RepairOperationType,
    scene: bpy.types.Scene,
    repair_settings: RepairSettings,
    analysis_settings: AnalysisSettings,
    *,
    blend_file_path: str,
) -> RepairOperationRecord:
    _validate_source(session, blend_file_path)
    workspace = _validate_workspace(session)
    current_analysis = get_current_analysis(session)
    if current_analysis is None:
        raise RuntimeError("Current workspace diagnostics are unavailable.")
    operation_id = str(uuid4())
    started_at = _utcnow()
    timer = perf_counter()
    record = RepairOperationRecord(
        operation_id=operation_id,
        operation_type=operation,
        status=RepairOperationStatus.PLANNED,
        started_at=started_at,
        before_workspace_signature=session.current_workspace_signature,
        before_analysis_id=current_analysis.analysis_id,
        counts_before=mesh_counts(workspace),
        parameters={
            "repair_settings": repair_settings.snapshot(),
            "selected_candidate_ids": [
                candidate.candidate_id
                for candidate in (session.plan.candidates if session.plan else ())
                if candidate.selected
            ],
        },
    )
    checkpoint = None
    try:
        checkpoint = create_operation_checkpoint(session, operation_id)
        record.checkpoint_id = checkpoint.checkpoint_id
        factor, _, _ = millimetres_per_blender_unit(scene)
        outcome = _dispatch_operation(operation, workspace, factor, repair_settings, current_analysis, session)
        _validate_source(session, blend_file_path)
        new_signature = repair_workspace_signature(workspace)
        result = _run_analysis(workspace, scene, analysis_settings, blend_file_path)
        session.workspace_mesh_identity = workspace.data.as_pointer()
        session.workspace_mesh_name = str(workspace.data.name)
        session.current_workspace_signature = new_signature
        set_current_analysis(session, result)
        record.status = outcome.status
        record.metrics = outcome.metrics
        record.warnings.extend(outcome.warnings)
        record.after_workspace_signature = new_signature
        record.after_analysis_id = result.analysis_id
        record.counts_after = mesh_counts(workspace)
        if outcome.status == RepairOperationStatus.NO_CHANGE:
            discard_checkpoint(session, checkpoint.checkpoint_id)
        else:
            enforce_checkpoint_history(session)
        session.status = RepairSessionStatus.REPAIRED
    except Exception as exc:
        if checkpoint is not None:
            try:
                restore_checkpoint(session, checkpoint.checkpoint_id, consume=True)
            except Exception as restore_exc:
                session.errors.append(f"Checkpoint restoration failed: {type(restore_exc).__name__}: {restore_exc}")
        try:
            restored = _validate_workspace(session)
            restored_result = _run_analysis(restored, scene, analysis_settings, blend_file_path)
            set_current_analysis(session, restored_result)
        except Exception as restore_exc:
            session.errors.append(f"Checkpoint restoration verification failed: {type(restore_exc).__name__}: {restore_exc}")
        record.status = RepairOperationStatus.FAILED
        record.error = f"{type(exc).__name__}: {exc}"
        record.after_workspace_signature = session.current_workspace_signature
        record.counts_after = mesh_counts(workspace_object(session)) if workspace_object(session) is not None else {}
        session.status = RepairSessionStatus.FAILED
        session.errors.append(record.error)
        raise
    finally:
        record.completed_at = _utcnow()
        record.duration_ms = (perf_counter() - timer) * 1000.0
        session.operation_records.append(record)
    return record


def apply_repair_plan(
    session: RepairSession,
    scene: bpy.types.Scene,
    repair_settings: RepairSettings,
    analysis_settings: AnalysisSettings,
    *,
    blend_file_path: str,
    active_object: bpy.types.Object | None,
    single_operation: RepairOperationType | None = None,
) -> tuple[RepairOperationRecord, ...]:
    _, workspace = validate_active_session(
        session,
        blend_file_path=blend_file_path,
        active_object=active_object,
        require_workspace_active=True,
    )
    validate_plan(session, repair_settings, blend_file_path=blend_file_path)
    plan = session.plan
    assert plan is not None
    if single_operation is not None:
        operations = (single_operation,)
    else:
        operations = plan.selected_operations()
    if not operations:
        raise ValueError("Select at least one evidenced repair operation or candidate.")
    session.status = RepairSessionStatus.REPAIRING
    window_manager = bpy.context.window_manager
    records: list[RepairOperationRecord] = []
    window_manager.progress_begin(0, len(operations))
    try:
        for index, operation in enumerate(SAFE_OPERATION_ORDER):
            if operation not in operations:
                continue
            records.append(
                _apply_one(
                    session,
                    operation,
                    scene,
                    repair_settings,
                    analysis_settings,
                    blend_file_path=blend_file_path,
                )
            )
            window_manager.progress_update(index + 1)
    finally:
        window_manager.progress_end()
    final = get_current_analysis(session)
    if final is not None:
        # The full initial result is not retained as a Blender object; rerun on the initial checkpoint is unnecessary.
        session.final_analysis = analysis_summary(final)
        before_metrics = session.before_analysis
        before_stub = None
        # A complete comparison uses the retained first analysis when no runtime reload occurred.
        # Store exact key deltas directly from JSON-safe summaries.
        issue_keys = (
            "boundary_edges", "non_manifold_edges", "vertex_manifold_anomalies", "loose_vertices",
            "loose_edges", "zero_length_edges", "degenerate_faces", "potential_duplicate_vertices",
        )
        first_topology = before_metrics.get("topology", {})
        last_topology = session.final_analysis.get("topology", {})
        deltas = {key: int(last_topology.get(key, 0)) - int(first_topology.get(key, 0)) for key in issue_keys}
        session.comparison = RepairComparison(
            before=before_metrics,
            after=session.final_analysis,
            deltas={**deltas, "source_signature": session.source_signature, "workspace_signature": session.current_workspace_signature},
            improved=tuple(key for key, value in deltas.items() if value < 0),
            unchanged=tuple(key for key, value in deltas.items() if value == 0),
            regressed=tuple(key for key, value in deltas.items() if value > 0),
            skipped_checks=tuple(final.skipped_check_reasons),
            failed_checks=tuple(check.message for check in final.checks if check.status == EvaluationStatus.FAILED),
        )
    plan.status = RepairPlanStatus.APPLIED
    session.status = RepairSessionStatus.REPAIRED
    return tuple(records)


def undo_last_repair(
    session: RepairSession,
    scene: bpy.types.Scene,
    analysis_settings: AnalysisSettings,
    *,
    blend_file_path: str,
    active_object: bpy.types.Object | None,
) -> RepairOperationRecord:
    validate_active_session(session, blend_file_path=blend_file_path, active_object=active_object, require_workspace_active=True)
    record = next((item for item in reversed(session.operation_records) if item.status == RepairOperationStatus.APPLIED), None)
    if record is None:
        raise RuntimeError("No applied repair operation is available to undo.")
    restore_checkpoint(session, record.checkpoint_id, consume=True)
    workspace = _validate_workspace(session)
    result = _run_analysis(workspace, scene, analysis_settings, blend_file_path)
    set_current_analysis(session, result)
    record.status = RepairOperationStatus.UNDONE
    session.undo_records.append({"operation_id": record.operation_id, "checkpoint_id": record.checkpoint_id, "undone_at": _utcnow().isoformat()})
    if session.plan is not None:
        session.plan.status = RepairPlanStatus.STALE
    session.status = RepairSessionStatus.ACTIVE
    session.final_analysis = analysis_summary(result)
    return record


def restore_workspace_to_initial(
    session: RepairSession,
    scene: bpy.types.Scene,
    analysis_settings: AnalysisSettings,
    *,
    blend_file_path: str,
    active_object: bpy.types.Object | None,
) -> None:
    validate_active_session(session, blend_file_path=blend_file_path, active_object=active_object, require_workspace_active=True)
    restore_checkpoint(session, session.initial_checkpoint_id, consume=False)
    clear_checkpoints(session, keep_initial=True)
    for record in session.operation_records:
        if record.status == RepairOperationStatus.APPLIED:
            record.status = RepairOperationStatus.UNDONE
    workspace = _validate_workspace(session)
    result = _run_analysis(workspace, scene, analysis_settings, blend_file_path)
    set_current_analysis(session, result)
    session.plan = None
    session.status = RepairSessionStatus.ACTIVE
    session.final_analysis = {}
    session.comparison = None
    session.undo_records.append({"action": "RESTORE_INITIAL", "restored_at": _utcnow().isoformat()})


def accept_repaired_copy(
    session: RepairSession,
    scene: bpy.types.Scene,
    analysis_settings: AnalysisSettings,
    *,
    blend_file_path: str,
    active_object: bpy.types.Object | None,
) -> bpy.types.Object:
    source, workspace = validate_active_session(session, blend_file_path=blend_file_path, active_object=active_object, require_workspace_active=True)
    result = _run_analysis(workspace, scene, analysis_settings, blend_file_path)
    set_current_analysis(session, result)
    _validate_source(session, blend_file_path)
    workspace.name = f"{source.name}_Chroma3D_Repaired"
    workspace.data.name = f"{source.data.name}_Chroma3D_Repaired"
    session.workspace_object_name = str(workspace.name)
    session.workspace_mesh_name = str(workspace.data.name)
    session.current_workspace_signature = repair_workspace_signature(workspace)
    session.final_analysis = analysis_summary(result)
    session.status = RepairSessionStatus.ACCEPTED
    session.decision = RepairDecision.ACCEPTED
    session.ended_at = _utcnow()
    if session.plan is not None:
        session.plan.status = RepairPlanStatus.APPLIED
    clear_checkpoints(session)
    archive_session(session)
    return workspace


def rollback_repair_session(session: RepairSession, *, blend_file_path: str) -> None:
    workspace = workspace_object(session)
    if workspace is None:
        raise RuntimeError("Repair workspace no longer exists; no unrelated object was removed.")
    source = source_object(session)
    if source is None:
        session.warnings.append("Protected source was unavailable during rollback; only the repair workspace was removed.")
    elif not protected_source_is_current(source, session.source_snapshot, blend_file_path):
        session.warnings.append(SOURCE_CHANGED_MESSAGE)
    mesh = workspace.data
    bpy.data.objects.remove(workspace, do_unlink=True)
    if mesh.users == 0:
        bpy.data.meshes.remove(mesh)
    clear_checkpoints(session)
    session.status = RepairSessionStatus.ROLLED_BACK
    session.decision = RepairDecision.ROLLED_BACK
    session.ended_at = _utcnow()
    restore_captured_selection(session)
    archive_session(session)
