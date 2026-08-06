"""Explicit Blender operators for the Sprint 6 intelligent workflow."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from ..intelligent_optimization_settings import IntelligentOptimizationSettings
from ..models.intelligent_optimization_models import SearchBudget
from ..services.intelligent_optimization_coordinator import (
    accept_selected_strategy,
    build_intelligent_frontier,
    cancel_intelligent_search,
    discard_intelligent_workspace,
    evaluate_intelligent_strategies,
    execute_selected_strategy,
    export_intelligent_audit,
    generate_intelligent_strategies,
    preview_selected_strategy,
    rank_intelligent_strategies,
    record_strategy_history,
    rerun_intelligent_search,
    select_strategy,
    start_intelligent_session,
)
from ..services.intelligent_optimization_session import get_active_session, get_archived_session
from ..services.search_policy import default_search_policy
from ..utilities.context import active_mesh_object, is_valid_mesh_object
from ..utilities.logging import get_logger


logger = get_logger()


def _policy_from_state(state: object):
    mode = str(getattr(state, "intelligent_optimization_search_mode", "STANDARD"))
    experimental = bool(getattr(state, "intelligent_optimization_experimental", False))
    policy = default_search_policy(mode, experimental_operations_enabled=experimental)
    budget = replace(
        policy.budget,
        max_generated_strategies=int(getattr(state, "intelligent_optimization_max_generated", policy.budget.max_generated_strategies)),
        max_evaluated_strategies=int(getattr(state, "intelligent_optimization_max_evaluated", policy.budget.max_evaluated_strategies)),
        max_strategy_depth=int(getattr(state, "intelligent_optimization_max_depth", policy.budget.max_strategy_depth)),
        max_pareto_points=int(getattr(state, "intelligent_optimization_max_frontier", policy.budget.max_pareto_points)),
    )
    return replace(policy, budget=budget, ranking_method=str(getattr(state, "intelligent_optimization_ranking_method", policy.ranking_method)), policy_hash="")


def _sync(context: bpy.types.Context) -> None:
    state = context.window_manager.chroma3d_sculpt_state
    session = get_active_session() or get_archived_session()
    if session is None:
        state.intelligent_optimization_has_session = False
        state.intelligent_optimization_state = "NOT_STARTED"
        return
    state.intelligent_optimization_has_session = True
    state.intelligent_optimization_state = session.state.value
    state.intelligent_optimization_strategy_count = len(session.strategy_set.strategies) if session.strategy_set else 0
    state.intelligent_optimization_evaluation_count = len(session.evaluations)
    state.intelligent_optimization_frontier_count = len(session.frontier.points) if session.frontier else 0
    state.intelligent_optimization_selected_strategy_id = session.selected_strategy_id


class CHROMA3D_OT_start_intelligent_optimization(bpy.types.Operator):
    bl_idname = "chroma3d.start_intelligent_optimization"
    bl_label = "Start Intelligent Session"
    bl_description = "Start a deterministic bounded intelligent optimization session with a protected source"
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
            settings = IntelligentOptimizationSettings(search_mode=state.intelligent_optimization_search_mode, objective_preset=state.intelligent_optimization_objective_preset, ranking_method=state.intelligent_optimization_ranking_method, experimental_operations_enabled=bool(state.intelligent_optimization_experimental))
            start_intelligent_session(source, context.scene, settings=settings, policy=_policy_from_state(state), blend_file_path=bpy.data.filepath)
            _sync(context)
            state.intelligent_optimization_last_result = "Protected source retained; isolated Sprint 5 workspace owned by the session."
        except Exception as exc:
            logger.exception("Intelligent optimization session creation failed")
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_generate_intelligent_strategies(bpy.types.Operator):
    bl_idname = "chroma3d.generate_intelligent_strategies"
    bl_label = "Generate Strategies"
    bl_description = "Generate deterministic strategy families without changing the source or workspace"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            result = generate_intelligent_strategies(source=None)
            _sync(context)
            context.window_manager.chroma3d_sculpt_state.intelligent_optimization_last_result = f"Generated {len(result.strategies)} strategy/strategies; {len(result.pruned)} pruning record(s)."
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_rerun_intelligent_search(bpy.types.Operator):
    bl_idname = "chroma3d.rerun_intelligent_search"
    bl_label = "Re-run With Updated Inputs"
    bl_description = "Invalidate prior search evidence and re-run bounded search with the current objectives and constraints"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            state = context.window_manager.chroma3d_sculpt_state
            settings = IntelligentOptimizationSettings(
                search_mode=state.intelligent_optimization_search_mode,
                objective_preset=state.intelligent_optimization_objective_preset,
                ranking_method=state.intelligent_optimization_ranking_method,
                experimental_operations_enabled=bool(state.intelligent_optimization_experimental),
            )
            result = rerun_intelligent_search(settings=settings, policy=_policy_from_state(state))
            _sync(context)
            state.intelligent_optimization_last_result = f"Re-ran bounded search with updated inputs: {len(result.strategies)} strategy/strategies."
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_evaluate_intelligent_strategies(bpy.types.Operator):
    bl_idname = "chroma3d.evaluate_intelligent_strategies"
    bl_label = "Evaluate Strategies"
    bl_description = "Evaluate strategies with visible virtual evidence and hard-constraint results"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            result = evaluate_intelligent_strategies()
            _sync(context)
            context.window_manager.chroma3d_sculpt_state.intelligent_optimization_last_result = f"Evaluated {len(result)} bounded strategy/strategies; estimated and skipped evidence remains visible."
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_build_intelligent_frontier(bpy.types.Operator):
    bl_idname = "chroma3d.build_intelligent_frontier"
    bl_label = "Build Pareto Frontier"
    bl_description = "Build a bounded Pareto frontier without hiding objective trade-offs"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            frontier = build_intelligent_frontier()
            _sync(context)
            context.window_manager.chroma3d_sculpt_state.intelligent_optimization_last_result = f"Pareto frontier contains {len(frontier.points)} non-dominated point(s)."
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_rank_intelligent_strategies(bpy.types.Operator):
    bl_idname = "chroma3d.rank_intelligent_strategies"
    bl_label = "Rank Strategies"
    bl_description = "Rank feasible strategies with an explicit deterministic method and tie-break evidence"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            state = context.window_manager.chroma3d_sculpt_state
            rankings = rank_intelligent_strategies(method=state.intelligent_optimization_ranking_method)
            record_strategy_history()
            _sync(context)
            state.intelligent_optimization_last_result = f"Ranked {len(rankings)} feasible strategy/strategies; recommendation requires review."
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_review_intelligent_recommendation(bpy.types.Operator):
    bl_idname = "chroma3d.review_intelligent_recommendation"
    bl_label = "Review Recommendation"
    bl_description = "Select the recommendation for review without executing it"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        session = get_active_session()
        if session is None or session.recommendation is None:
            return {"CANCELLED"}
        context.window_manager.chroma3d_sculpt_state.intelligent_optimization_selected_strategy_id = session.recommendation.strategy_id
        _sync(context)
        return {"FINISHED"}


class CHROMA3D_OT_preview_intelligent_strategy(bpy.types.Operator):
    bl_idname = "chroma3d.preview_intelligent_strategy"
    bl_label = "Preview Selected Strategy"
    bl_description = "Preview the selected strategy in the isolated workspace without automatic execution"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            state = context.window_manager.chroma3d_sculpt_state
            preview_selected_strategy(strategy_id=state.intelligent_optimization_selected_strategy_id or None)
            _sync(context)
            state.intelligent_optimization_last_result = "Isolated strategy preview recorded; execution still requires explicit approval."
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_execute_intelligent_strategy(bpy.types.Operator):
    bl_idname = "chroma3d.execute_intelligent_strategy"
    bl_label = "Execute Selected Strategy"
    bl_description = "Execute the selected strategy step-by-step through the Sprint 5 checkpointed workspace"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            state = context.window_manager.chroma3d_sculpt_state
            records = execute_selected_strategy(strategy_id=state.intelligent_optimization_selected_strategy_id or None, approved=True, blend_file_path=bpy.data.filepath)
            _sync(context)
            state.intelligent_optimization_last_result = f"Executed {len(records)} selected step(s) in the isolated workspace; review comparison before acceptance."
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_cancel_intelligent_search(bpy.types.Operator):
    bl_idname = "chroma3d.cancel_intelligent_search"
    bl_label = "Cancel Search"
    bl_description = "Cancel future search work and discard only the owned temporary workspace"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            cancel_intelligent_search(blend_file_path=bpy.data.filepath)
            _sync(context)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_accept_intelligent_copy(bpy.types.Operator):
    bl_idname = "chroma3d.accept_intelligent_copy"
    bl_label = "Accept Optimized Copy"
    bl_description = "Accept a separate optimized copy after explicit comparison review; never replace the source"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            accepted = accept_selected_strategy(blend_file_path=bpy.data.filepath)
            _sync(context)
            context.window_manager.chroma3d_sculpt_state.intelligent_optimization_last_result = f"Accepted separate optimized copy: {accepted.name}"
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_discard_intelligent_workspace(bpy.types.Operator):
    bl_idname = "chroma3d.discard_intelligent_workspace"
    bl_label = "Discard Workspace"
    bl_description = "Discard only the session-owned intelligent optimization workspace"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            discard_intelligent_workspace(blend_file_path=bpy.data.filepath)
            _sync(context)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class _IntelligentExportBase:
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})


class CHROMA3D_OT_export_intelligent_json(_IntelligentExportBase, bpy.types.Operator, ExportHelper):
    bl_idname = "chroma3d.export_intelligent_optimization_json"
    bl_label = "Export JSON"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            export_intelligent_audit(self.filepath, markdown=False, blender_version=bpy.app.version_string)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_export_intelligent_markdown(_IntelligentExportBase, bpy.types.Operator, ExportHelper):
    bl_idname = "chroma3d.export_intelligent_optimization_markdown"
    bl_label = "Export Markdown"
    filename_ext = ".md"
    filter_glob: StringProperty(default="*.md", options={"HIDDEN"})

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            export_intelligent_audit(self.filepath, markdown=True, blender_version=bpy.app.version_string)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


class CHROMA3D_OT_export_intelligent_history(_IntelligentExportBase, bpy.types.Operator, ExportHelper):
    bl_idname = "chroma3d.export_intelligent_optimization_history"
    bl_label = "Export Strategy History"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context: bpy.types.Context) -> set[str]:
        session = get_active_session() or get_archived_session()
        if session is None:
            return {"CANCELLED"}
        try:
            from ..services.strategy_history import write_history_json
            write_history_json(session.history, self.filepath)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"FINISHED"}


CLASSES = (
    CHROMA3D_OT_start_intelligent_optimization,
    CHROMA3D_OT_generate_intelligent_strategies,
    CHROMA3D_OT_rerun_intelligent_search,
    CHROMA3D_OT_evaluate_intelligent_strategies,
    CHROMA3D_OT_build_intelligent_frontier,
    CHROMA3D_OT_rank_intelligent_strategies,
    CHROMA3D_OT_review_intelligent_recommendation,
    CHROMA3D_OT_preview_intelligent_strategy,
    CHROMA3D_OT_execute_intelligent_strategy,
    CHROMA3D_OT_cancel_intelligent_search,
    CHROMA3D_OT_accept_intelligent_copy,
    CHROMA3D_OT_discard_intelligent_workspace,
    CHROMA3D_OT_export_intelligent_json,
    CHROMA3D_OT_export_intelligent_markdown,
    CHROMA3D_OT_export_intelligent_history,
)
