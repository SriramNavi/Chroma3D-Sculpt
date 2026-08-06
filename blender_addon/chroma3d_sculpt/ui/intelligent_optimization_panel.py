"""Native Blender panel for the Sprint 6 explainable optimization workflow."""

from __future__ import annotations

import bpy

from ..services.intelligent_optimization_session import get_active_session, get_archived_session
from ..utilities.context import is_valid_mesh_object


class CHROMA3D_PT_intelligent_optimization(bpy.types.Panel):
    bl_label = "Intelligent Optimization"
    bl_idname = "CHROMA3D_PT_intelligent_optimization"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Chroma3D"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        state = context.window_manager.chroma3d_sculpt_state
        session = get_active_session() or get_archived_session()

        source = layout.box()
        source.label(text="Source", icon="LOCKED")
        source.label(text=f"Protected source: {session.source_identity.get('object_name', context.active_object.name if context.active_object else 'None') if session else (context.active_object.name if context.active_object else 'None')}")
        source.label(text=f"Source state: {state.intelligent_optimization_state}")
        source.label(text="Source is never replaced or mutated.", icon="INFO")

        search = layout.box()
        search.label(text="Search", icon="VIEWZOOM")
        search.prop(state, "intelligent_optimization_search_mode")
        search.prop(state, "intelligent_optimization_objective_preset")
        search.prop(state, "intelligent_optimization_ranking_method")
        search.prop(state, "intelligent_optimization_max_generated")
        search.prop(state, "intelligent_optimization_max_evaluated")
        search.prop(state, "intelligent_optimization_max_depth")
        search.prop(state, "intelligent_optimization_max_frontier")
        search.prop(state, "intelligent_optimization_experimental")
        search.label(text="Experimental operations require explicit enablement.", icon="ERROR")

        start = layout.row()
        start.enabled = get_active_session() is None and is_valid_mesh_object(getattr(context, "active_object", None))
        start.operator("chroma3d.start_intelligent_optimization", text="Start Intelligent Session", icon="ADD")

        if session is None:
            return

        actions = layout.box()
        actions.label(text="Actions", icon="SEQUENCE")
        row = actions.row(align=True)
        row.operator("chroma3d.generate_intelligent_strategies", text="Generate Strategies")
        row.operator("chroma3d.rerun_intelligent_search", text="Re-run Updated")
        row.operator("chroma3d.evaluate_intelligent_strategies", text="Evaluate")
        row = actions.row(align=True)
        row.operator("chroma3d.build_intelligent_frontier", text="Build Pareto Frontier")
        row.operator("chroma3d.rank_intelligent_strategies", text="Rank Strategies")
        row = actions.row(align=True)
        row.operator("chroma3d.review_intelligent_recommendation", text="Review Recommendation")
        row.operator("chroma3d.preview_intelligent_strategy", text="Preview Selected Strategy")
        row = actions.row(align=True)
        row.operator("chroma3d.execute_intelligent_strategy", text="Execute Selected Strategy")
        row.operator("chroma3d.cancel_intelligent_search", text="Cancel Search")

        results = layout.box()
        results.label(text="Results", icon="INFO")
        results.label(text=f"Generated: {len(session.strategy_set.strategies) if session.strategy_set else 0}")
        results.label(text=f"Evaluated: {len(session.evaluations)}")
        results.label(text=f"Pareto points: {len(session.frontier.points) if session.frontier else 0}")
        results.label(text=f"Recommended: {session.recommendation.strategy_id if session.recommendation else 'none'}")
        results.label(text=f"Selected: {session.selected_strategy_id or 'none'}")
        if session.evaluations:
            results.label(text=f"Estimated/skipped: {sum(len(item.estimated_evidence) for item in session.evaluations)}/{sum(len(item.skipped_evidence) + len(item.indeterminate_evidence) for item in session.evaluations)}")
        if session.recommendation:
            results.label(text=session.recommendation.wording[:120], icon="QUESTION")

        finalize = layout.box()
        finalize.label(text="Review and Export", icon="CHECKMARK")
        finalize.operator("chroma3d.accept_intelligent_copy", text="Accept Optimized Copy", icon="CHECKMARK")
        finalize.operator("chroma3d.discard_intelligent_workspace", text="Discard Workspace", icon="TRASH")
        row = finalize.row(align=True)
        row.operator("chroma3d.export_intelligent_optimization_json", text="Export JSON")
        row.operator("chroma3d.export_intelligent_optimization_markdown", text="Export Markdown")
        finalize.operator("chroma3d.export_intelligent_optimization_history", text="Export Strategy History")
        finalize.label(text="Advisory only; no slicer, G-code, printer control, or physical guarantee.", icon="ERROR")


CLASSES = (CHROMA3D_PT_intelligent_optimization,)
