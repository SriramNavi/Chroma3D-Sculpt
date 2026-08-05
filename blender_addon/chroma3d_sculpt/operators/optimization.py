"""Blender operators for the explicit Sprint 5 optimization lifecycle."""

from __future__ import annotations

from pathlib import Path

import bpy
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper

from ..models.optimization_models import OptimizationOperationType, OptimizationPolicy
from ..optimization_settings import OptimizationSettings
from ..services.optimization_audit import build_audit, sanitize_optimization_filename, write_json_audit, write_markdown_audit
from ..services.optimization_coordinator import (
    accept_optimized_copy, apply_selected_step, discard_workspace, generate_session_candidates, generate_session_plan,
    rerun_comparison, restore_session_to_start, start_session, undo_last_step,
)
from ..services.optimization_session import get_active_session, get_archived_session, get_workspace
from ..utilities.context import active_mesh_object, is_valid_mesh_object
from ..utilities.logging import get_logger


logger = get_logger()


def _source_for(session: object) -> bpy.types.Object | None:
    identity = int(getattr(session, "source_object_identity", 0))
    for obj in bpy.data.objects:
        try:
            if int(obj.as_pointer()) == identity:
                return obj
        except (ReferenceError, RuntimeError):
            continue
    return None


def _build_volume(state: object) -> tuple[float, float, float] | None:
    profile = str(getattr(state, "printer_profile", "NONE"))
    if profile == "NONE":
        return None
    if profile == "CUSTOM":
        return (float(state.custom_build_width_mm), float(state.custom_build_depth_mm), float(state.custom_build_height_mm))
    return (256.0, 256.0, 256.0)


def _policy_from_state(state: object) -> OptimizationPolicy:
    enabled = [OptimizationOperationType.UNIFORM_SCALE.value, OptimizationOperationType.ORIENTATION.value, OptimizationOperationType.BUILD_PLATE_TRANSLATION.value]
    if bool(state.optimization_base_stabilization):
        enabled.append(OptimizationOperationType.BASE_STABILIZATION.value)
    if bool(state.optimization_decimation):
        enabled.append(OptimizationOperationType.DECIMATION.value)
    if bool(state.optimization_experimental_remesh):
        enabled.append(OptimizationOperationType.EXPERIMENTAL_REMESH.value)
    return OptimizationPolicy(
        enabled_operation_families=tuple(enabled), maximum_uniform_scale_change=float(state.optimization_max_scale_change),
        maximum_rotation_candidates=int(state.optimization_max_rotation_candidates), maximum_translation_distance=float(state.optimization_max_translation_distance),
        maximum_base_modification_height=float(state.optimization_max_base_height), maximum_base_added_volume_ratio=float(state.optimization_max_base_volume_ratio),
        maximum_decimation_ratio=float(state.optimization_max_decimation_ratio), maximum_geometric_deviation=float(state.optimization_max_deviation),
        maximum_checkpoint_count=int(state.optimization_checkpoint_limit), experimental_decimation_enabled=bool(state.optimization_decimation),
        experimental_remesh_enabled=bool(state.optimization_experimental_remesh),
    )


def _sync(context: bpy.types.Context) -> None:
    state = context.window_manager.chroma3d_sculpt_state
    session = get_active_session()
    if session is None:
        archived = get_archived_session()
        state.optimization_has_session = archived is not None
        state.optimization_state = archived.state.value if archived else "NOT_STARTED"
        return
    state.optimization_has_session = True
    state.optimization_state = session.state.value
    state.optimization_source_name = session.source_object_name
    state.optimization_workspace_name = session.workspace_object_name
    state.optimization_plan_status = session.plan.status if session.plan else "NOT_GENERATED"
    state.optimization_candidate_count = len(session.candidates)
    if not state.optimization_selected_candidate_id and session.candidates:
        state.optimization_selected_candidate_id = session.candidates[0].candidate_id


class CHROMA3D_OT_start_optimization_session(bpy.types.Operator):
    bl_idname = "chroma3d.start_optimization_session"
    bl_label = "Start Optimization Session"
    bl_description = "Create an isolated controlled-optimization workspace without changing the protected source"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return get_active_session() is None and is_valid_mesh_object(getattr(context, "active_object", None))

    def execute(self, context: bpy.types.Context) -> set[str]:
        source = active_mesh_object(context)
        if source is None:
            self.report({"ERROR"}, "Select a valid mesh object.")
            return {"CANCELLED"}
        try:
            state = context.window_manager.chroma3d_sculpt_state
            session = start_session(source, context.scene, settings=OptimizationSettings(objective_preset=state.optimization_objective_preset), policy=_policy_from_state(state), blend_file_path=bpy.data.filepath)
            _sync(context)
            state.optimization_last_result = "Protected source preserved; isolated optimization workspace created."
        except Exception as exc:
            logger.exception("Optimization-session creation failed")
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, "Optimization workspace created. Original source preserved.")
        return {"FINISHED"}


class CHROMA3D_OT_generate_optimization_candidates(bpy.types.Operator):
    bl_idname = "chroma3d.generate_optimization_candidates"
    bl_label = "Generate Candidates"
    bl_description = "Generate deterministic bounded candidates without applying them"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        session = get_active_session()
        if session is None:
            return {"CANCELLED"}
        try:
            state = context.window_manager.chroma3d_sculpt_state
            generate_session_candidates(session, source=_source_for(session), policy=_policy_from_state(state), build_volume_mm=_build_volume(state))
            _sync(context)
            state.optimization_last_result = f"Generated {len(session.candidates)} deterministic candidate(s)."
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_generate_optimization_plan(bpy.types.Operator):
    bl_idname = "chroma3d.generate_optimization_plan"
    bl_label = "Generate Plan"
    bl_description = "Generate a read-only deterministic optimization plan"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        session = get_active_session()
        if session is None:
            return {"CANCELLED"}
        try:
            plan = generate_session_plan(session, policy=_policy_from_state(context.window_manager.chroma3d_sculpt_state))
            _sync(context)
            context.window_manager.chroma3d_sculpt_state.optimization_last_result = f"Plan ready: {len(plan.steps)} bounded step(s)."
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_apply_optimization_step(bpy.types.Operator):
    bl_idname = "chroma3d.apply_optimization_step"
    bl_label = "Apply Selected Step"
    bl_description = "Apply one explicitly selected plan step to the isolated workspace"
    bl_options = {"REGISTER"}
    candidate_id: StringProperty(name="Candidate ID", default="")

    def execute(self, context: bpy.types.Context) -> set[str]:
        session = get_active_session()
        if session is None:
            return {"CANCELLED"}
        state = context.window_manager.chroma3d_sculpt_state
        selected = self.candidate_id or state.optimization_selected_candidate_id
        try:
            record = apply_selected_step(session, _source_for(session), selected, approved=True, policy=_policy_from_state(state), build_volume_mm=_build_volume(state), blend_file_path=bpy.data.filepath)
            _sync(context)
            state.optimization_last_result = f"{record.operation.value}: {record.state.value}. Review before/after evidence."
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_undo_optimization_step(bpy.types.Operator):
    bl_idname = "chroma3d.undo_optimization_step"
    bl_label = "Undo Last Step"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        session = get_active_session()
        if session is None:
            return {"CANCELLED"}
        try:
            record = undo_last_step(session, _source_for(session), blend_file_path=bpy.data.filepath)
            _sync(context)
            context.window_manager.chroma3d_sculpt_state.optimization_last_result = f"Undid {record.operation.value}; generate a fresh plan before reapplying."
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_rerun_optimization_comparison(bpy.types.Operator):
    bl_idname = "chroma3d.rerun_optimization_comparison"
    bl_label = "Re-run Comparison"
    bl_description = "Recompute bounded before/after evidence for the latest applied step"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        session = get_active_session()
        if session is None:
            return {"CANCELLED"}
        try:
            comparison = rerun_comparison(
                session,
                policy=_policy_from_state(context.window_manager.chroma3d_sculpt_state),
                build_volume_mm=_build_volume(context.window_manager.chroma3d_sculpt_state),
            )
            _sync(context)
            context.window_manager.chroma3d_sculpt_state.optimization_last_result = f"Comparison rerun: {comparison.overall_classification.value}. Review bounded evidence."
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_restore_optimization_session(bpy.types.Operator):
    bl_idname = "chroma3d.restore_optimization_session"
    bl_label = "Restore Session Start"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        session = get_active_session()
        if session is None:
            return {"CANCELLED"}
        try:
            restore_session_to_start(session, _source_for(session), blend_file_path=bpy.data.filepath)
            _sync(context)
            context.window_manager.chroma3d_sculpt_state.optimization_last_result = "Workspace restored to its retained session-start checkpoint."
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_accept_optimization_copy(bpy.types.Operator):
    bl_idname = "chroma3d.accept_optimization_copy"
    bl_label = "Accept Optimized Copy"
    bl_description = "Retain the optimized result as a separate object; never replace the source"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        session = get_active_session()
        if session is None:
            return {"CANCELLED"}
        try:
            accepted = accept_optimized_copy(session, blend_file_path=bpy.data.filepath)
            _sync(context)
            context.window_manager.chroma3d_sculpt_state.optimization_last_result = f"Accepted separate optimized copy: {accepted.name}"
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_discard_optimization_workspace(bpy.types.Operator):
    bl_idname = "chroma3d.discard_optimization_workspace"
    bl_label = "Discard Workspace"
    bl_description = "Discard only the session-owned optimization workspace"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        session = get_active_session()
        if session is None:
            return {"CANCELLED"}
        try:
            discard_workspace(session, blend_file_path=bpy.data.filepath)
            _sync(context)
            context.window_manager.chroma3d_sculpt_state.optimization_last_result = "Workspace discarded; protected source retained."
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class _OptimizationExportBase:
    def _audit(self) -> object | None:
        return build_audit(get_active_session() or get_archived_session(), blender_version=bpy.app.version_string) if (get_active_session() or get_archived_session()) else None


class CHROMA3D_OT_export_optimization_json(_OptimizationExportBase, bpy.types.Operator, ExportHelper):
    bl_idname = "chroma3d.export_optimization_json"
    bl_label = "Export JSON Audit"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context: bpy.types.Context) -> set[str]:
        audit = self._audit()
        if audit is None:
            return {"CANCELLED"}
        write_json_audit(audit, self.filepath)
        self.report({"INFO"}, "Controlled optimization JSON audit exported.")
        return {"FINISHED"}


class CHROMA3D_OT_export_optimization_markdown(_OptimizationExportBase, bpy.types.Operator, ExportHelper):
    bl_idname = "chroma3d.export_optimization_markdown"
    bl_label = "Export Markdown Audit"
    filename_ext = ".md"
    filter_glob: StringProperty(default="*.md", options={"HIDDEN"})

    def execute(self, context: bpy.types.Context) -> set[str]:
        audit = self._audit()
        if audit is None:
            return {"CANCELLED"}
        write_markdown_audit(audit, self.filepath)
        self.report({"INFO"}, "Controlled optimization Markdown audit exported.")
        return {"FINISHED"}


CLASSES = (
    CHROMA3D_OT_start_optimization_session, CHROMA3D_OT_generate_optimization_candidates,
    CHROMA3D_OT_generate_optimization_plan, CHROMA3D_OT_apply_optimization_step,
    CHROMA3D_OT_undo_optimization_step, CHROMA3D_OT_restore_optimization_session,
    CHROMA3D_OT_rerun_optimization_comparison,
    CHROMA3D_OT_accept_optimization_copy, CHROMA3D_OT_discard_optimization_workspace,
    CHROMA3D_OT_export_optimization_json, CHROMA3D_OT_export_optimization_markdown,
)
