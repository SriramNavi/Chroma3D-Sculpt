"""Bounded Safe Repair controls in the existing Chroma3D sidebar."""

from __future__ import annotations

import bpy

from ..models.repair_models import RepairOperationStatus, RepairPlanStatus, RepairSessionStatus
from ..services.repair_session import get_active_session, get_audit_session
from ..utilities.context import is_valid_mesh_object


class CHROMA3D_UL_tiny_shell_candidates(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0, flt_flag=0):
        row = layout.row(align=True)
        row.prop(item, "selected", text="")
        row.label(text=f"S{item.shell_id}")
        row.label(text=f"{item.face_count} faces")
        row.label(text=f"{item.relative_size:.2f}%")
        row.label(text=item.confidence.title())


class CHROMA3D_UL_small_hole_candidates(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property, index=0, flt_flag=0):
        row = layout.row(align=True)
        row.prop(item, "selected", text="")
        row.label(text=f"{item.edge_count} edges")
        row.label(text=f"{item.perimeter_mm:.3f} mm")
        row.label(text=f"Ø {item.diagonal_mm:.3f} mm")


class CHROMA3D_PT_safe_repair(bpy.types.Panel):
    bl_idname = "CHROMA3D_PT_safe_repair"
    bl_label = "Safe Repair"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Chroma3D"
    bl_parent_id = "CHROMA3D_PT_sculpt"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        state = context.window_manager.chroma3d_sculpt_state
        session = get_active_session()

        session_box = layout.box()
        session_box.label(text="Repair Session", icon="MODIFIER")
        if session is None:
            session_box.label(text="No active repair session")
            row = session_box.row()
            row.enabled = is_valid_mesh_object(getattr(context, "active_object", None))
            row.operator("chroma3d.start_repair_session", icon="DUPLICATE")
            audit = get_audit_session()
            if audit is not None:
                session_box.label(text=f"Last decision: {audit.decision.value}")
                session_box.operator("chroma3d.export_repair_audit", icon="EXPORT")
            return

        session_box.label(text=f"Source: {session.source_object_name}", icon="LOCKED")
        session_box.label(text=f"Workspace: {session.workspace_object_name}", icon="MESH_DATA")
        session_box.label(text=f"Status: {session.status.value.replace('_', ' ').title()}")
        session_box.label(text="Source protected: Yes", icon="CHECKMARK")

        settings_box = layout.box()
        settings_box.label(text="Repair Settings", icon="PREFERENCES")
        settings_box.prop(state, "repair_merge_distance_mm")
        settings_box.prop(state, "repair_zero_length_tolerance_mm")
        settings_box.prop(state, "repair_degenerate_area_tolerance_mm2")
        settings_box.prop(
            state,
            "repair_show_advanced",
            text="Advanced",
            icon="DISCLOSURE_TRI_DOWN" if state.repair_show_advanced else "DISCLOSURE_TRI_RIGHT",
            emboss=False,
        )
        if state.repair_show_advanced:
            settings_box.prop(state, "repair_checkpoint_depth")
            settings_box.prop(state, "repair_candidate_index_cap")
            settings_box.prop(state, "repair_hole_max_edges")
            settings_box.prop(state, "repair_hole_max_perimeter_mm")
            settings_box.prop(state, "repair_hole_max_diagonal_mm")

        plan_box = layout.box()
        plan_box.label(text="Repair Plan", icon="PRESET")
        plan_box.operator("chroma3d.generate_repair_plan", icon="VIEWZOOM")
        plan_box.label(text=f"Plan: {session.plan.status.value if session.plan else 'NOT_GENERATED'}")
        plan_box.label(text=f"Analysis: {session.current_analysis_id[:12] or 'Unavailable'}")
        if session.plan is not None:
            for item in session.plan.items:
                property_name = {
                    "MERGE_DUPLICATE_VERTICES": "repair_merge_duplicates",
                    "COLLAPSE_ZERO_LENGTH_EDGES": "repair_collapse_zero_edges",
                    "REMOVE_DEGENERATE_FACES": "repair_remove_degenerate",
                    "REMOVE_LOOSE_GEOMETRY": "repair_remove_loose",
                    "REPAIR_NORMAL_CONSISTENCY": "repair_normal_consistency",
                    "ORIENT_CLOSED_SHELLS_OUTWARD": "repair_orient_outward",
                }.get(item.operation_type.value)
                if property_name:
                    row = plan_box.row(align=True)
                    row.prop(state, property_name)
                    row.label(text=f"{item.estimated_target_count}", icon="INFO" if item.recommended else "DOT")

        if len(state.repair_tiny_shell_candidates):
            tiny_box = layout.box()
            tiny_box.label(text="Tiny-Shell Candidates — explicit selection", icon="OUTLINER_OB_MESH")
            tiny_box.template_list(
                "CHROMA3D_UL_tiny_shell_candidates",
                "",
                state,
                "repair_tiny_shell_candidates",
                state,
                "repair_tiny_shell_index",
                rows=min(5, len(state.repair_tiny_shell_candidates)),
            )

        if len(state.repair_small_hole_candidates):
            hole_box = layout.box()
            hole_box.label(text="Small-Hole Candidates — explicit selection", icon="MESH_CIRCLE")
            hole_box.template_list(
                "CHROMA3D_UL_small_hole_candidates",
                "",
                state,
                "repair_small_hole_candidates",
                state,
                "repair_small_hole_index",
                rows=min(5, len(state.repair_small_hole_candidates)),
            )

        apply_box = layout.box()
        apply_box.label(text="Apply", icon="TOOL_SETTINGS")
        row = apply_box.row()
        row.enabled = session.plan is not None and session.plan.status == RepairPlanStatus.READY
        row.operator("chroma3d.apply_repair_plan", icon="PLAY")
        if state.repair_last_result:
            apply_box.label(text=state.repair_last_result[:96], icon="INFO")

        recovery = layout.box()
        recovery.label(text="Recovery", icon="RECOVER_LAST")
        undoable = any(record.status == RepairOperationStatus.APPLIED for record in session.operation_records)
        row = recovery.row(align=True)
        row.enabled = undoable
        row.operator("chroma3d.undo_last_repair", icon="LOOP_BACK")
        recovery.operator("chroma3d.restore_repair_workspace", icon="FILE_REFRESH")
        recovery.operator("chroma3d.rollback_repair_session", icon="TRASH")

        if session.comparison is not None:
            comparison = layout.box()
            comparison.label(text="Comparison", icon="ARROW_LEFTRIGHT")
            comparison.label(text=f"Improved: {len(session.comparison.improved)}")
            comparison.label(text=f"Regressed: {len(session.comparison.regressed)}")
            comparison.label(text="Full details in repair audit JSON")

        finalize = layout.box()
        finalize.label(text="Finalize", icon="CHECKMARK")
        finalize.operator("chroma3d.accept_repaired_copy", icon="CHECKMARK")
        finalize.operator("chroma3d.export_repair_audit", icon="EXPORT")
        finalize.label(text="Alpha output — further review required", icon="ERROR")


CLASSES = (CHROMA3D_UL_tiny_shell_candidates, CHROMA3D_UL_small_hole_candidates, CHROMA3D_PT_safe_repair)
