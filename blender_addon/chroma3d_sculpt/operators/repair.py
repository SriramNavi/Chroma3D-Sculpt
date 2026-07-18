"""Blender operators for the controlled Sprint 2 repair lifecycle."""

from __future__ import annotations

from pathlib import Path

import bpy
from bpy.props import EnumProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from ..analysis_settings import settings_from_property_group
from ..models.repair_models import RepairCandidateType, RepairOperationType, RepairPlanStatus, RepairSessionStatus
from ..repair_settings import settings_from_repair_property_group
from ..services.repair_audit import sanitize_repair_audit_filename, write_repair_audit
from ..services.repair_coordinator import (
    accept_repaired_copy,
    apply_repair_plan,
    generate_repair_plan,
    restore_workspace_to_initial,
    rollback_repair_session,
    undo_last_repair,
)
from ..services.repair_session import get_active_session, get_audit_session, start_session
from ..utilities.context import active_mesh_object, is_valid_mesh_object
from ..utilities.logging import get_logger


logger = get_logger()

_TOGGLE_MAP = {
    RepairOperationType.MERGE_DUPLICATE_VERTICES: "repair_merge_duplicates",
    RepairOperationType.COLLAPSE_ZERO_LENGTH_EDGES: "repair_collapse_zero_edges",
    RepairOperationType.REMOVE_DEGENERATE_FACES: "repair_remove_degenerate",
    RepairOperationType.REMOVE_LOOSE_GEOMETRY: "repair_remove_loose",
    RepairOperationType.REPAIR_NORMAL_CONSISTENCY: "repair_normal_consistency",
    RepairOperationType.ORIENT_CLOSED_SHELLS_OUTWARD: "repair_orient_outward",
}


def _sync_session_scalars(context: bpy.types.Context) -> None:
    state = context.window_manager.chroma3d_sculpt_state
    session = get_active_session()
    if session is None:
        state.repair_session_status = "NOT_STARTED"
        state.repair_plan_status = "NOT_GENERATED"
        return
    state.repair_session_status = session.status.value
    state.repair_plan_status = session.plan.status.value if session.plan else "NOT_GENERATED"
    state.repair_source_name = session.source_object_name
    state.repair_workspace_name = session.workspace_object_name
    state.repair_analysis_id = session.current_analysis_id


def _populate_plan_ui(context: bpy.types.Context) -> None:
    session = get_active_session()
    if session is None or session.plan is None:
        return
    state = context.window_manager.chroma3d_sculpt_state
    for item in session.plan.items:
        property_name = _TOGGLE_MAP.get(item.operation_type)
        if property_name:
            setattr(state, property_name, item.selected)
    state.repair_tiny_shell_candidates.clear()
    state.repair_small_hole_candidates.clear()
    for candidate in session.plan.candidates:
        if candidate.candidate_type == RepairCandidateType.TINY_SHELL:
            item = state.repair_tiny_shell_candidates.add()
            item.selected = False
            item.candidate_id = candidate.candidate_id
            item.shell_id = candidate.shell_id if candidate.shell_id is not None else -1
            item.face_count = candidate.total_face_count
            item.relative_size = candidate.relative_size_percent or 0.0
            item.confidence = candidate.confidence.value
        elif candidate.candidate_type == RepairCandidateType.SMALL_HOLE:
            item = state.repair_small_hole_candidates.add()
            item.selected = False
            item.candidate_id = candidate.candidate_id
            item.edge_count = candidate.total_edge_count
            item.perimeter_mm = candidate.perimeter_mm or 0.0
            item.diagonal_mm = candidate.diagonal_mm or 0.0
    _sync_session_scalars(context)


def _sync_plan_selection(context: bpy.types.Context) -> None:
    session = get_active_session()
    if session is None or session.plan is None:
        return
    state = context.window_manager.chroma3d_sculpt_state
    for item in session.plan.items:
        property_name = _TOGGLE_MAP.get(item.operation_type)
        if property_name:
            item.selected = bool(getattr(state, property_name))
    tiny = {item.candidate_id: bool(item.selected) for item in state.repair_tiny_shell_candidates}
    holes = {item.candidate_id: bool(item.selected) for item in state.repair_small_hole_candidates}
    for candidate in session.plan.candidates:
        if candidate.candidate_type == RepairCandidateType.TINY_SHELL:
            candidate.selected = tiny.get(candidate.candidate_id, False)
        elif candidate.candidate_type == RepairCandidateType.SMALL_HOLE:
            candidate.selected = holes.get(candidate.candidate_id, False)


class CHROMA3D_OT_start_repair_session(bpy.types.Operator):
    bl_idname = "chroma3d.start_repair_session"
    bl_label = "Start Repair Session"
    bl_description = "Create an independent repair workspace while preserving the source"
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
            session = start_session(
                source,
                context.scene,
                settings_from_repair_property_group(state),
                settings_from_property_group(state),
                blender_version=bpy.app.version_string,
                blend_file_path=bpy.data.filepath,
            )
            _sync_session_scalars(context)
            state.repair_last_result = "Original source preserved; independent repair workspace created."
        except Exception as exc:
            logger.exception("Repair-session creation failed")
            self.report({"ERROR"}, f"Could not start repair session: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, "Repair workspace created. Original source preserved.")
        return {"FINISHED"}


class CHROMA3D_OT_generate_repair_plan(bpy.types.Operator):
    bl_idname = "chroma3d.generate_repair_plan"
    bl_label = "Generate Repair Plan"
    bl_description = "Preview evidence-based repair candidates without changing geometry"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return get_active_session() is not None

    def execute(self, context: bpy.types.Context) -> set[str]:
        session = get_active_session()
        assert session is not None
        try:
            state = context.window_manager.chroma3d_sculpt_state
            plan = generate_repair_plan(
                session,
                context.scene,
                settings_from_repair_property_group(state),
                blend_file_path=bpy.data.filepath,
                active_object=context.active_object,
            )
            _populate_plan_ui(context)
            state.repair_last_result = f"Plan ready: {sum(item.recommended for item in plan.items)} evidenced operation(s)."
        except Exception as exc:
            logger.exception("Repair-plan generation failed")
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, "Repair plan generated without changing geometry.")
        return {"FINISHED"}


class CHROMA3D_OT_apply_repair_plan(bpy.types.Operator):
    bl_idname = "chroma3d.apply_repair_plan"
    bl_label = "Apply Selected Repairs"
    bl_description = "Apply explicitly selected repairs in the documented safe order"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        session = get_active_session()
        return session is not None and session.plan is not None and session.plan.status == RepairPlanStatus.READY

    def execute(self, context: bpy.types.Context) -> set[str]:
        session = get_active_session()
        assert session is not None
        try:
            state = context.window_manager.chroma3d_sculpt_state
            _sync_plan_selection(context)
            records = apply_repair_plan(
                session,
                context.scene,
                settings_from_repair_property_group(state),
                settings_from_property_group(state),
                blend_file_path=bpy.data.filepath,
                active_object=context.active_object,
            )
            state.repair_last_result = f"Controlled repair completed: {len(records)} operation(s); review remaining warnings."
            _sync_session_scalars(context)
        except Exception as exc:
            logger.exception("Repair-plan application failed")
            self.report({"ERROR"}, f"Repair stopped safely: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, "Repair completed with remaining warnings subject to review.")
        return {"FINISHED"}


class CHROMA3D_OT_apply_single_repair(bpy.types.Operator):
    bl_idname = "chroma3d.apply_single_repair"
    bl_label = "Apply One Repair"
    bl_description = "Apply one explicitly chosen repair operation"
    bl_options = {"REGISTER"}

    operation_type: EnumProperty(
        name="Operation",
        items=tuple((item.value, item.value.replace("_", " ").title(), "") for item in RepairOperationType),
    )

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        session = get_active_session()
        return session is not None and session.plan is not None and session.plan.status == RepairPlanStatus.READY

    def execute(self, context: bpy.types.Context) -> set[str]:
        session = get_active_session()
        assert session is not None
        try:
            state = context.window_manager.chroma3d_sculpt_state
            _sync_plan_selection(context)
            records = apply_repair_plan(
                session,
                context.scene,
                settings_from_repair_property_group(state),
                settings_from_property_group(state),
                blend_file_path=bpy.data.filepath,
                active_object=context.active_object,
                single_operation=RepairOperationType(self.operation_type),
            )
            state.repair_last_result = f"{records[-1].operation_type.value}: {records[-1].status.value}"
            _sync_session_scalars(context)
        except Exception as exc:
            logger.exception("Single repair failed")
            self.report({"ERROR"}, f"Repair stopped safely: {exc}")
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_undo_last_repair(bpy.types.Operator):
    bl_idname = "chroma3d.undo_last_repair"
    bl_label = "Undo Last Repair"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        session = get_active_session()
        if session is None:
            return {"CANCELLED"}
        try:
            state = context.window_manager.chroma3d_sculpt_state
            record = undo_last_repair(session, context.scene, settings_from_property_group(state), blend_file_path=bpy.data.filepath, active_object=context.active_object)
            state.repair_last_result = f"Undid {record.operation_type.value}. Generate a new plan."
            _sync_session_scalars(context)
        except Exception as exc:
            logger.exception("Repair undo failed")
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_restore_repair_workspace(bpy.types.Operator):
    bl_idname = "chroma3d.restore_repair_workspace"
    bl_label = "Restore Workspace to Start"
    bl_options = {"REGISTER"}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context: bpy.types.Context) -> set[str]:
        session = get_active_session()
        if session is None:
            return {"CANCELLED"}
        try:
            state = context.window_manager.chroma3d_sculpt_state
            restore_workspace_to_initial(session, context.scene, settings_from_property_group(state), blend_file_path=bpy.data.filepath, active_object=context.active_object)
            state.repair_last_result = "Repair workspace restored to its initial session state."
            _sync_session_scalars(context)
        except Exception as exc:
            logger.exception("Workspace restore failed")
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_accept_repaired_copy(bpy.types.Operator):
    bl_idname = "chroma3d.accept_repaired_copy"
    bl_label = "Accept Repaired Copy"
    bl_description = "Keep the repaired copy without replacing the original source"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        session = get_active_session()
        if session is None:
            return {"CANCELLED"}
        try:
            state = context.window_manager.chroma3d_sculpt_state
            accepted = accept_repaired_copy(session, context.scene, settings_from_property_group(state), blend_file_path=bpy.data.filepath, active_object=context.active_object)
            state.repair_session_status = "ACCEPTED"
            state.repair_plan_status = "APPLIED"
            state.repair_last_result = f"Accepted {accepted.name}; original source preserved."
        except Exception as exc:
            logger.exception("Accept repaired copy failed")
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, "Repaired copy accepted. Original source preserved.")
        return {"FINISHED"}


class CHROMA3D_OT_rollback_repair_session(bpy.types.Operator):
    bl_idname = "chroma3d.rollback_repair_session"
    bl_label = "Roll Back Repair Session"
    bl_description = "Discard only the repair workspace and retain the original source"
    bl_options = {"REGISTER"}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context: bpy.types.Context) -> set[str]:
        session = get_active_session()
        if session is None:
            return {"CANCELLED"}
        try:
            rollback_repair_session(session, blend_file_path=bpy.data.filepath)
            state = context.window_manager.chroma3d_sculpt_state
            state.repair_session_status = "ROLLED_BACK"
            state.repair_plan_status = "NOT_GENERATED"
            state.repair_last_result = "Repair workspace discarded; original source preserved."
        except Exception as exc:
            logger.exception("Repair rollback failed")
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_export_repair_audit(bpy.types.Operator, ExportHelper):
    bl_idname = "chroma3d.export_repair_audit"
    bl_label = "Export Repair Audit"
    bl_description = "Export the complete repair audit as schema 1.0 JSON"
    bl_options = {"REGISTER"}

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return get_audit_session() is not None

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        session = get_audit_session()
        if session is None:
            return {"CANCELLED"}
        directory = Path(bpy.path.abspath("//")) if bpy.data.filepath else Path.home()
        self.filepath = str(directory / sanitize_repair_audit_filename(session.source_object_name))
        return ExportHelper.invoke(self, context, event)

    def execute(self, context: bpy.types.Context) -> set[str]:
        session = get_audit_session()
        if session is None:
            return {"CANCELLED"}
        try:
            output = write_repair_audit(session, Path(self.filepath))
        except (OSError, ValueError, TypeError) as exc:
            logger.exception("Repair audit export failed")
            self.report({"ERROR"}, f"Could not export repair audit: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Repair audit exported: {output.name}")
        return {"FINISHED"}


CLASSES = (
    CHROMA3D_OT_start_repair_session,
    CHROMA3D_OT_generate_repair_plan,
    CHROMA3D_OT_apply_repair_plan,
    CHROMA3D_OT_apply_single_repair,
    CHROMA3D_OT_undo_last_repair,
    CHROMA3D_OT_restore_repair_workspace,
    CHROMA3D_OT_accept_repaired_copy,
    CHROMA3D_OT_rollback_repair_session,
    CHROMA3D_OT_export_repair_audit,
)
