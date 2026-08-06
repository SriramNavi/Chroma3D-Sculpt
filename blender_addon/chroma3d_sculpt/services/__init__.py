"""Analysis and report services."""

from .mesh_analyzer import analyze_mesh
from .report_generator import sanitize_report_filename, write_json_report
from .repair_coordinator import apply_repair_plan, generate_repair_plan
from .repair_session import get_active_session, start_session
from .printability_coordinator import analyze_printability
from .printer_profile_loader import load_profile
from .optimization_coordinator import (
    accept_optimized_copy, apply_selected_step, discard_workspace, generate_session_candidates, generate_session_plan,
    rerun_comparison, restore_session_to_start, start_session as start_optimization_session, undo_last_step,
)
from .intelligent_optimization_coordinator import (
    accept_selected_strategy, build_intelligent_frontier, cancel_intelligent_search, discard_intelligent_workspace,
    evaluate_intelligent_strategies, execute_selected_strategy, generate_intelligent_strategies, preview_selected_strategy,
    rank_intelligent_strategies, rerun_intelligent_search, select_strategy, start_intelligent_session,
)

__all__ = (
    "analyze_mesh",
    "analyze_printability",
    "apply_repair_plan",
    "generate_repair_plan",
    "get_active_session",
    "sanitize_report_filename",
    "start_session",
    "load_profile",
    "write_json_report",
    "apply_selected_step",
    "accept_optimized_copy",
    "discard_workspace",
    "generate_session_candidates",
    "generate_session_plan",
    "rerun_comparison",
    "restore_session_to_start",
    "start_optimization_session",
    "undo_last_step",
    "start_intelligent_session", "generate_intelligent_strategies", "evaluate_intelligent_strategies",
    "build_intelligent_frontier", "rank_intelligent_strategies", "select_strategy", "preview_selected_strategy",
    "execute_selected_strategy", "accept_selected_strategy", "discard_intelligent_workspace", "cancel_intelligent_search",
    "rerun_intelligent_search",
)
