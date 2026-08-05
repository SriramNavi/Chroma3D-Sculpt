"""Controlled Optimization sidebar panel."""

from __future__ import annotations

import bpy

from ..models.optimization_models import OptimizationSessionState
from ..services.optimization_session import get_active_session
from ..utilities.context import is_valid_mesh_object


class CHROMA3D_PT_controlled_optimization(bpy.types.Panel):
    bl_idname = "CHROMA3D_PT_controlled_optimization"
    bl_label = "Controlled Optimization"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Chroma3D"
    bl_parent_id = "CHROMA3D_PT_sculpt"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        state = context.window_manager.chroma3d_sculpt_state
        session = get_active_session()
        valid = is_valid_mesh_object(getattr(context, "active_object", None))

        source = layout.box(); source.label(text="Source", icon="LOCKED")
        source.label(text=f"Protected source: {session.source_object_name if session else getattr(context.active_object, 'name', 'None')}")
        source.label(text=f"State: {state.optimization_state}")
        source.label(text="Source is never replaced or mutated.", icon="INFO")
        start = source.row(); start.enabled = session is None and valid
        start.operator("chroma3d.start_optimization_session", text="Start Optimization Session", icon="ADD")

        if session is None:
            return

        objectives = layout.box(); objectives.label(text="Objectives", icon="SOLO_ON")
        objectives.prop(state, "optimization_objective_preset")
        objectives.label(text=f"Candidate count: {len(session.candidates)}")
        objectives.label(text=f"Objective hash: {(session.objective_snapshot.objective_hash[:16] if session.objective_snapshot else 'not set')}")
        if state.optimization_objective_preset == "Custom":
            for name in ("optimization_weight_build_volume_fit", "optimization_weight_wall_thickness", "optimization_weight_thin_features", "optimization_weight_overhang", "optimization_weight_support", "optimization_weight_contact", "optimization_weight_height", "optimization_weight_fidelity"):
                objectives.prop(state, name)

        policy = layout.box(); policy.label(text="Policy", icon="PREFERENCES")
        policy.prop(state, "optimization_max_scale_change"); policy.prop(state, "optimization_max_rotation_candidates"); policy.prop(state, "optimization_max_translation_distance")
        policy.prop(state, "optimization_checkpoint_limit"); policy.prop(state, "optimization_max_deviation")
        policy.prop(state, "optimization_base_stabilization"); policy.prop(state, "optimization_decimation"); policy.prop(state, "optimization_experimental_remesh")
        policy.label(text="Experimental operations are disabled by default.", icon="ERROR")

        workflow = layout.box(); workflow.label(text="Workflow", icon="SEQUENCE")
        row = workflow.row(align=True); row.operator("chroma3d.generate_optimization_candidates", text="Generate Candidates"); row.operator("chroma3d.generate_optimization_plan", text="Generate Plan")
        workflow.label(text=f"Plan: {session.plan.status if session.plan else 'NOT_GENERATED'}")
        if session.candidates:
            workflow.prop(state, "optimization_selected_candidate_id", text="Candidate ID")
            for candidate in session.candidates[:12]:
                row = workflow.row(align=True)
                row.label(text=f"{candidate.candidate_id[-18:]} / {candidate.category.value}")
                op = row.operator("chroma3d.apply_optimization_step", text="Apply")
                op.candidate_id = candidate.candidate_id
        row = workflow.row(align=True); row.operator("chroma3d.undo_optimization_step", text="Undo Last"); row.operator("chroma3d.restore_optimization_session", text="Restore Start")
        workflow.operator("chroma3d.rerun_optimization_comparison", text="Re-run Comparison", icon="FILE_REFRESH")

        results = layout.box(); results.label(text="Results", icon="ARROW_LEFTRIGHT")
        results.label(text=f"Operations: {len(session.operation_records)} / comparisons: {len(session.comparisons)}")
        if session.comparisons:
            comparison = session.comparisons[-1]
            results.label(text=f"Objective: {comparison.overall_classification.value}")
            results.label(text=f"Critical regressions: {len(comparison.critical_regressions)}")
            results.label(text=f"Fidelity: {comparison.fidelity.get('status', 'INDETERMINATE')}")
            results.label(text=f"Skipped/indeterminate: {len(comparison.skipped_checks)}/{len(comparison.indeterminate_checks)}")
        if state.optimization_last_result:
            results.label(text=state.optimization_last_result[:110], icon="INFO")

        finalize = layout.box(); finalize.label(text="Review and Export", icon="CHECKMARK")
        finalize.operator("chroma3d.accept_optimized_copy", text="Accept Optimized Copy", icon="CHECKMARK")
        finalize.operator("chroma3d.discard_optimization_workspace", text="Discard Workspace", icon="TRASH")
        row = finalize.row(align=True); row.operator("chroma3d.export_optimization_json", text="JSON Audit"); row.operator("chroma3d.export_optimization_markdown", text="Markdown Audit")
        finalize.label(text="Advisory preview only; no supports, slicing, G-code, or printer control.", icon="ERROR")


CLASSES = (CHROMA3D_PT_controlled_optimization,)
