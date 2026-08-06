"""Blender UI settings plus small session-state scalars."""

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, StringProperty

from ..models.analysis_result import AnalysisResult


def _mark_printability_profile_stale(self: bpy.types.PropertyGroup, _context: bpy.types.Context) -> None:
    if bool(getattr(self, "printability_has_result", False)):
        self.printability_state = "STALE_PROFILE"
    if bool(getattr(self, "preparation_has_result", False)):
        self.preparation_state = "STALE_HARDWARE_PROFILE"


def _mark_printability_settings_stale(self: bpy.types.PropertyGroup, _context: bpy.types.Context) -> None:
    if bool(getattr(self, "printability_has_result", False)):
        self.printability_state = "STALE_SETTINGS"
    if bool(getattr(self, "preparation_has_result", False)):
        self.preparation_state = "STALE_PROCESS_CONTEXT"


def _mark_preparation_material_stale(self: bpy.types.PropertyGroup, _context: bpy.types.Context) -> None:
    if bool(getattr(self, "preparation_has_result", False)):
        self.preparation_state = "STALE_MATERIAL_PROFILE"


def _mark_preparation_context_stale(self: bpy.types.PropertyGroup, _context: bpy.types.Context) -> None:
    if bool(getattr(self, "preparation_has_result", False)):
        self.preparation_state = "STALE_PROCESS_CONTEXT"


def _mark_preparation_flags_stale(self: bpy.types.PropertyGroup, _context: bpy.types.Context) -> None:
    if bool(getattr(self, "preparation_has_result", False)):
        self.preparation_state = "STALE_FEATURE_FLAGS"


def _mark_optimization_stale(self: bpy.types.PropertyGroup, _context: bpy.types.Context) -> None:
    if bool(getattr(self, "optimization_has_session", False)):
        self.optimization_state = "STALE_SETTINGS"


def _mark_intelligent_optimization_stale(self: bpy.types.PropertyGroup, _context: bpy.types.Context) -> None:
    if bool(getattr(self, "intelligent_optimization_has_session", False)):
        self.intelligent_optimization_state = "STALE_SETTINGS"


def _mark_ai_assistance_stale(self: bpy.types.PropertyGroup, _context: bpy.types.Context) -> None:
    if bool(getattr(self, "ai_assistance_has_session", False)):
        self.ai_assistance_state = "STALE_SETTINGS"
        try:
            from ..models.ai_assistance_models import AssistanceState
            from ..services.ai_assistance_session import get_active_session, invalidate
            session = get_active_session()
            if session is not None and session.state in {AssistanceState.EVIDENCE_AVAILABLE, AssistanceState.PREVIEWING, AssistanceState.APPROVAL_REQUIRED}:
                invalidate(session, "UI_PROVIDER_MODEL_MODE_OR_POLICY_CHANGED")
        except (ImportError, RuntimeError, ValueError):
            pass


class CHROMA3D_PG_tiny_shell_candidate(bpy.types.PropertyGroup):
    selected: BoolProperty(name="Remove", default=False)
    candidate_id: StringProperty(name="Candidate ID", default="")
    shell_id: IntProperty(name="Shell ID", default=-1)
    face_count: IntProperty(name="Faces", default=0)
    relative_size: FloatProperty(name="Relative size (%)", default=0.0)
    confidence: StringProperty(name="Confidence", default="")


class CHROMA3D_PG_small_hole_candidate(bpy.types.PropertyGroup):
    selected: BoolProperty(name="Fill", default=False)
    candidate_id: StringProperty(name="Candidate ID", default="")
    edge_count: IntProperty(name="Edges", default=0)
    perimeter_mm: FloatProperty(name="Perimeter (mm)", default=0.0)
    diagonal_mm: FloatProperty(name="Diagonal (mm)", default=0.0)


class CHROMA3D_PG_session_state(bpy.types.PropertyGroup):
    has_analysis: BoolProperty(name="Has analysis", default=False, options={"HIDDEN"})
    analyzed_object_name: StringProperty(name="Analyzed object", default="", options={"HIDDEN"})
    severity: StringProperty(name="Severity", default="", options={"HIDDEN"})
    last_analysis: StringProperty(name="Last analysis", default="", options={"HIDDEN"})

    analysis_profile: EnumProperty(
        name="Analysis Profile",
        items=(("STANDARD", "Standard", "Routine deterministic diagnostics"), ("DEEP", "Deep", "Include bounded BVH diagnostics")),
        default="STANDARD",
    )
    printer_profile: EnumProperty(
        name="Printer Profile",
        items=(
            ("NONE", "None", "Do not evaluate a build volume"),
            ("BAMBU_X1_CARBON", "Bambu Lab X1 Carbon", "256 x 256 x 256 mm rectangular volume"),
            ("CUSTOM", "Custom", "Use custom rectangular dimensions"),
        ),
        default="NONE",
    )
    custom_build_width_mm: FloatProperty(name="Build X (mm)", default=256.0, min=0.001)
    custom_build_depth_mm: FloatProperty(name="Build Y (mm)", default=256.0, min=0.001)
    custom_build_height_mm: FloatProperty(name="Build Z (mm)", default=256.0, min=0.001)
    show_advanced_settings: BoolProperty(name="Advanced Settings", default=False)
    show_timings: BoolProperty(name="Check Timings", default=False)
    duplicate_position_tolerance: FloatProperty(name="Duplicate Tolerance", default=1e-6, min=1e-12, precision=8)
    duplicate_vertex_limit: IntProperty(name="Duplicate Vertex Limit", default=500_000, min=1)
    degenerate_edge_tolerance: FloatProperty(name="Zero Edge Tolerance", default=1e-9, min=1e-15, precision=10)
    degenerate_face_tolerance: FloatProperty(name="Degenerate Face Tolerance", default=1e-18, min=1e-24, precision=12)
    tiny_shell_max_face_count: IntProperty(name="Tiny Shell Faces", default=12, min=0)
    tiny_shell_max_volume_mm3: FloatProperty(name="Tiny Shell Volume", default=1000.0, min=0.0)
    tiny_shell_max_relative_volume_percent: FloatProperty(name="Tiny Relative Volume %", default=0.5, min=0.0, max=100.0)
    tiny_shell_max_diagonal_mm: FloatProperty(name="Tiny Shell Diagonal", default=10.0, min=0.0)
    maximum_stored_issue_indices: IntProperty(name="Issue Evidence Cap", default=10_000, min=1, max=100_000)
    self_intersection_triangle_limit: IntProperty(name="Intersection Triangle Limit", default=50_000, min=1)
    maximum_stored_self_intersection_pairs: IntProperty(name="Intersection Pair Cap", default=10_000, min=1, max=100_000)
    containment_shell_limit: IntProperty(name="Containment Shell Limit", default=64, min=1)
    containment_triangle_limit: IntProperty(name="Containment Triangle Limit", default=100_000, min=1)

    printability_has_result: BoolProperty(name="Has printability result", default=False, options={"HIDDEN"})
    printability_object_name: StringProperty(name="Printability object", default="", options={"HIDDEN"})
    printability_status: StringProperty(name="Printability status", default="", options={"HIDDEN"})
    printability_confidence: StringProperty(name="Printability confidence", default="", options={"HIDDEN"})
    printability_last_result: StringProperty(name="Printability duration", default="", options={"HIDDEN"})
    printability_state: StringProperty(name="Printability state", default="NOT_RUN", options={"HIDDEN"})
    printability_profile: EnumProperty(
        name="Printer / Process Profile",
        items=(
            ("generic_fdm", "Generic FDM", "Project-default editable FDM example"),
            ("generic_resin", "Generic Resin", "Project-default editable resin example"),
            ("bambu_x1_carbon", "Bambu Lab X1 Carbon", "Manufacturer build-volume facts plus labeled project defaults"),
            ("bambu_p1s", "Bambu Lab P1S", "Manufacturer build-volume facts plus labeled project defaults"),
            ("prusa_mk4", "Original Prusa MK4", "Manufacturer build-volume fact plus labeled project defaults"),
            ("custom", "Custom", "User-supplied profile values"),
        ),
        default="generic_fdm",
        update=_mark_printability_profile_stale,
    )
    printability_mode: EnumProperty(
        name="Mode",
        items=(("FAST", "Fast", "256 wall samples / 100k expensive-triangle limit"), ("STANDARD", "Standard", "2048 samples / 500k limit"), ("DEEP", "Deep", "16384 samples / 1M limit")),
        default="STANDARD",
        update=_mark_printability_settings_stale,
    )
    printability_build_direction_x: FloatProperty(name="Build X", default=0.0, update=_mark_printability_settings_stale)
    printability_build_direction_y: FloatProperty(name="Build Y", default=0.0, update=_mark_printability_settings_stale)
    printability_build_direction_z: FloatProperty(name="Build Z", default=1.0, update=_mark_printability_settings_stale)
    printability_principal_candidates: BoolProperty(name="Principal-axis candidates", default=True, update=_mark_printability_settings_stale)
    printability_planar_candidates: BoolProperty(name="Planar-face candidates", default=True, update=_mark_printability_settings_stale)
    printability_sampled_candidates: BoolProperty(name="Sampled candidates", default=False, update=_mark_printability_settings_stale)
    printability_show_advanced: BoolProperty(name="Advanced Printability Settings", default=False)
    printability_custom_manufacturer: StringProperty(name="Manufacturer", default="User supplied", update=_mark_printability_profile_stale)
    printability_custom_model: StringProperty(name="Printer Model", default="User supplied", update=_mark_printability_profile_stale)
    printability_custom_process: EnumProperty(name="Process", items=(("FDM", "FDM", "Fused deposition process"), ("RESIN", "Resin", "Resin process"), ("CUSTOM", "Custom", "Other user-defined process")), default="CUSTOM", update=_mark_printability_profile_stale)
    printability_custom_material: StringProperty(name="Material", default="User supplied", update=_mark_printability_profile_stale)
    printability_custom_build_x_mm: FloatProperty(name="Build X (mm)", default=200.0, min=0.001, update=_mark_printability_profile_stale)
    printability_custom_build_y_mm: FloatProperty(name="Build Y (mm)", default=200.0, min=0.001, update=_mark_printability_profile_stale)
    printability_custom_build_z_mm: FloatProperty(name="Build Z (mm)", default=200.0, min=0.001, update=_mark_printability_profile_stale)
    printability_custom_margin_mm: FloatProperty(name="Safety Margin (mm)", default=2.0, min=0.001, update=_mark_printability_profile_stale)
    printability_custom_nozzle_mm: FloatProperty(name="Nozzle (mm)", default=0.4, min=0.001, update=_mark_printability_profile_stale)
    printability_custom_layer_mm: FloatProperty(name="Layer Height (mm)", default=0.2, min=0.001, update=_mark_printability_profile_stale)
    printability_custom_wall_warning_mm: FloatProperty(name="Wall Warning (mm)", default=1.2, min=0.001, update=_mark_printability_profile_stale)
    printability_custom_wall_critical_mm: FloatProperty(name="Wall Critical (mm)", default=0.8, min=0.001, update=_mark_printability_profile_stale)
    printability_custom_feature_warning_mm: FloatProperty(name="Feature Warning (mm)", default=0.8, min=0.001, update=_mark_printability_profile_stale)
    printability_custom_feature_critical_mm: FloatProperty(name="Feature Critical (mm)", default=0.45, min=0.001, update=_mark_printability_profile_stale)
    printability_custom_overhang_warning_deg: FloatProperty(name="Overhang Warning (deg)", default=45.0, min=0.001, max=90.0, update=_mark_printability_profile_stale)
    printability_custom_overhang_critical_deg: FloatProperty(name="Overhang Critical (deg)", default=30.0, min=0.001, max=90.0, update=_mark_printability_profile_stale)
    printability_custom_contact_tolerance_mm: FloatProperty(name="Contact Tolerance (mm)", default=0.05, min=0.000001, update=_mark_printability_profile_stale)

    preparation_has_result: BoolProperty(name="Has advanced preparation result", default=False, options={"HIDDEN"})
    preparation_state: StringProperty(name="Preparation state", default="NOT_RUN", options={"HIDDEN"})
    preparation_status: StringProperty(name="Preparation status", default="", options={"HIDDEN"})
    preparation_confidence: StringProperty(name="Preparation confidence", default="", options={"HIDDEN"})
    preparation_last_result: StringProperty(name="Preparation duration", default="", options={"HIDDEN"})
    preparation_batch_status: StringProperty(name="Batch status", default="NOT_RUN", options={"HIDDEN"})
    preparation_batch_summary: StringProperty(name="Batch summary", default="", options={"HIDDEN"})
    preparation_cancel_requested: BoolProperty(name="Cancel requested", default=False, options={"HIDDEN"})
    preparation_baseline_path: StringProperty(name="Baseline path", default="", options={"HIDDEN"})
    preparation_dashboard_path: StringProperty(name="Dashboard path", default="", options={"HIDDEN"})
    preparation_material_profile: EnumProperty(
        name="Material Profile",
        items=(
            ("generic_pla", "Generic PLA", "Project-default generic PLA; not physically calibrated"),
            ("generic_petg", "Generic PETG", "Conservative generic PETG heuristic"),
            ("generic_abs", "Generic ABS", "Conservative generic ABS heuristic"),
            ("generic_asa", "Generic ASA", "Conservative generic ASA heuristic"),
            ("generic_tpu", "Generic TPU", "Conservative generic TPU heuristic"),
            ("generic_resin_material", "Generic Resin", "Experimental generic resin heuristic"),
            ("custom_material", "Custom Material", "User-configured material behavior"),
        ),
        default="generic_pla", update=_mark_preparation_material_stale,
    )
    preparation_nozzle_mm: FloatProperty(name="Nozzle / Resolution (mm)", default=0.4, min=0.001, update=_mark_preparation_context_stale)
    preparation_layer_height_mm: FloatProperty(name="Layer Height (mm)", default=0.2, min=0.001, update=_mark_preparation_context_stale)
    preparation_build_plate_type: EnumProperty(
        name="Build Plate", items=(("TEXTURED", "Textured", "Textured FDM plate"), ("SMOOTH", "Smooth", "Smooth FDM plate"), ("RESIN_PLATFORM", "Resin Platform", "Resin build platform"), ("OTHER", "Other", "Other profile-listed plate")),
        default="TEXTURED", update=_mark_preparation_context_stale,
    )
    preparation_support_policy: EnumProperty(
        name="Supports Policy", items=(("REVIEW_REQUIRED", "Review Required", "Do not assume support state"), ("ASSUME_UNSUPPORTED", "Assume Unsupported", "Evaluate as unsupported"), ("ASSUME_SUPPORTED", "Assume Supported", "Record an explicit supported-process assumption")),
        default="REVIEW_REQUIRED", update=_mark_preparation_context_stale,
    )
    preparation_bridge_risk: BoolProperty(name="Bridge Risk", default=True, update=_mark_preparation_flags_stale)
    preparation_support_risk: BoolProperty(name="Support Risk", default=True, update=_mark_preparation_flags_stale)
    preparation_resin_advisory: BoolProperty(name="Resin Advisory (Experimental)", default=False, update=_mark_preparation_flags_stale)
    preparation_baseline_enabled: BoolProperty(name="Baseline Comparison", default=True, update=_mark_preparation_flags_stale)
    preparation_experimental_modifiers: BoolProperty(name="Experimental Material Modifiers", default=False, update=_mark_preparation_flags_stale)
    preparation_custom_material_name: StringProperty(name="Material Name", default="Custom Material", update=_mark_preparation_material_stale)
    preparation_custom_material_family: EnumProperty(name="Material Family", items=(("PLA", "PLA", "PLA"), ("PETG", "PETG", "PETG"), ("ABS", "ABS", "ABS"), ("ASA", "ASA", "ASA"), ("TPU", "TPU", "TPU"), ("RESIN", "Resin", "Resin"), ("CUSTOM", "Custom", "Custom")), default="CUSTOM", update=_mark_preparation_material_stale)
    preparation_custom_wall_multiplier: FloatProperty(name="Wall Multiplier", default=1.0, min=0.001, update=_mark_preparation_material_stale)
    preparation_custom_feature_multiplier: FloatProperty(name="Feature Multiplier", default=1.0, min=0.001, update=_mark_preparation_material_stale)
    preparation_custom_bridge_modifier: FloatProperty(name="Bridge Modifier", default=1.0, min=0.001, update=_mark_preparation_material_stale)
    preparation_custom_overhang_modifier: FloatProperty(name="Overhang Modifier", default=1.0, min=0.001, update=_mark_preparation_material_stale)

    repair_show_advanced: BoolProperty(name="Advanced Repair Settings", default=False)
    repair_merge_distance_mm: FloatProperty(name="Merge Distance (mm)", default=0.001, min=1e-9, max=1000.0, precision=6)
    repair_zero_length_tolerance_mm: FloatProperty(name="Zero Edge Tolerance (mm)", default=0.000001, min=1e-12, max=1000.0, precision=9)
    repair_degenerate_area_tolerance_mm2: FloatProperty(name="Degenerate Area (mm²)", default=0.00000001, min=1e-16, max=1_000_000.0, precision=10)
    repair_checkpoint_depth: IntProperty(name="Checkpoint History", default=3, min=1, max=20)
    repair_candidate_index_cap: IntProperty(name="Candidate Evidence Cap", default=10_000, min=1, max=100_000)
    repair_hole_max_edges: IntProperty(name="Small Hole Max Edges", default=12, min=3, max=1000)
    repair_hole_max_perimeter_mm: FloatProperty(name="Small Hole Perimeter (mm)", default=2.0, min=1e-6, max=1_000_000.0, precision=4)
    repair_hole_max_diagonal_mm: FloatProperty(name="Small Hole Diagonal (mm)", default=1.0, min=1e-6, max=1_000_000.0, precision=4)
    repair_merge_duplicates: BoolProperty(name="Merge Duplicate Vertices", default=False)
    repair_collapse_zero_edges: BoolProperty(name="Collapse Zero-Length Edges", default=False)
    repair_remove_degenerate: BoolProperty(name="Remove Degenerate Faces", default=False)
    repair_remove_loose: BoolProperty(name="Remove Loose Geometry", default=False)
    repair_normal_consistency: BoolProperty(name="Repair Normal Consistency", default=False)
    repair_orient_outward: BoolProperty(name="Orient Closed Shells Outward", default=False)
    repair_session_status: StringProperty(name="Repair Status", default="NOT_STARTED", options={"HIDDEN"})
    repair_plan_status: StringProperty(name="Plan Status", default="NOT_GENERATED", options={"HIDDEN"})
    repair_source_name: StringProperty(name="Source", default="", options={"HIDDEN"})
    repair_workspace_name: StringProperty(name="Workspace", default="", options={"HIDDEN"})
    repair_analysis_id: StringProperty(name="Analysis ID", default="", options={"HIDDEN"})
    repair_last_result: StringProperty(name="Last Result", default="", options={"HIDDEN"})
    repair_tiny_shell_candidates: CollectionProperty(type=CHROMA3D_PG_tiny_shell_candidate)
    repair_tiny_shell_index: IntProperty(default=0)
    repair_small_hole_candidates: CollectionProperty(type=CHROMA3D_PG_small_hole_candidate)
    repair_small_hole_index: IntProperty(default=0)

    optimization_has_session: BoolProperty(name="Has optimization session", default=False, options={"HIDDEN"})
    optimization_state: StringProperty(name="Optimization State", default="NOT_STARTED", options={"HIDDEN"})
    optimization_source_name: StringProperty(name="Optimization Source", default="", options={"HIDDEN"})
    optimization_workspace_name: StringProperty(name="Optimization Workspace", default="", options={"HIDDEN"})
    optimization_plan_status: StringProperty(name="Optimization Plan", default="NOT_GENERATED", options={"HIDDEN"})
    optimization_last_result: StringProperty(name="Optimization Result", default="", options={"HIDDEN"})
    optimization_selected_candidate_id: StringProperty(name="Selected Candidate", default="")
    optimization_candidate_count: IntProperty(name="Candidate Count", default=0, options={"HIDDEN"})
    optimization_objective_preset: EnumProperty(
        name="Objective Preset",
        items=(
            ("Balanced FDM", "Balanced FDM", "Balanced geometry and print-risk objectives"),
            ("Minimum Supports", "Minimum Supports", "Reduce bounded support-risk proxies"),
            ("Maximum Fidelity", "Maximum Fidelity", "Preserve geometry and sculpt detail"),
            ("Fit to Printer", "Fit to Printer", "Prioritize bounded build-volume fit"),
            ("Stable Base", "Stable Base", "Prioritize build contact"),
            ("Lightweight Preview", "Lightweight Preview", "Prioritize a bounded triangle reduction preview"),
            ("Resin Advisory", "Resin Advisory", "Prioritize resin advisory risk evidence"),
            ("Custom", "Custom", "Use the visible objective weights"),
        ),
        default="Balanced FDM", update=_mark_optimization_stale,
    )
    optimization_base_stabilization: BoolProperty(name="Enable Base Stabilization", default=False, update=_mark_optimization_stale)
    optimization_decimation: BoolProperty(name="Enable Experimental Decimation", default=False, update=_mark_optimization_stale)
    optimization_experimental_remesh: BoolProperty(name="Enable Experimental Remesh", default=False, update=_mark_optimization_stale)
    optimization_max_scale_change: FloatProperty(name="Maximum Scale Change", default=0.20, min=0.0, max=1.0, update=_mark_optimization_stale)
    optimization_max_rotation_candidates: IntProperty(name="Rotation Candidates", default=8, min=1, max=64, update=_mark_optimization_stale)
    optimization_max_translation_distance: FloatProperty(name="Translation Limit (mm)", default=1000.0, min=0.0, update=_mark_optimization_stale)
    optimization_max_base_height: FloatProperty(name="Base Height (mm)", default=2.0, min=0.0, update=_mark_optimization_stale)
    optimization_max_base_volume_ratio: FloatProperty(name="Base Volume Ratio", default=0.10, min=0.0, max=1.0, update=_mark_optimization_stale)
    optimization_max_decimation_ratio: FloatProperty(name="Decimation Ratio", default=0.50, min=0.0, max=1.0, update=_mark_optimization_stale)
    optimization_max_deviation: FloatProperty(name="Maximum Fidelity Deviation", default=0.25, min=0.0, max=1.0, update=_mark_optimization_stale)
    optimization_checkpoint_limit: IntProperty(name="Checkpoint Limit", default=4, min=2, max=20, update=_mark_optimization_stale)
    optimization_weight_build_volume_fit: FloatProperty(name="Build Volume Fit Weight", default=1.0, min=0.0, update=_mark_optimization_stale)
    optimization_weight_wall_thickness: FloatProperty(name="Wall Preservation Weight", default=1.0, min=0.0, update=_mark_optimization_stale)
    optimization_weight_thin_features: FloatProperty(name="Thin Feature Weight", default=1.0, min=0.0, update=_mark_optimization_stale)
    optimization_weight_overhang: FloatProperty(name="Overhang Weight", default=1.0, min=0.0, update=_mark_optimization_stale)
    optimization_weight_support: FloatProperty(name="Support Risk Weight", default=1.0, min=0.0, update=_mark_optimization_stale)
    optimization_weight_contact: FloatProperty(name="Contact Weight", default=1.0, min=0.0, update=_mark_optimization_stale)
    optimization_weight_height: FloatProperty(name="Height Weight", default=0.5, min=0.0, update=_mark_optimization_stale)
    optimization_weight_fidelity: FloatProperty(name="Geometry Fidelity Weight", default=1.0, min=0.0, update=_mark_optimization_stale)

    intelligent_optimization_has_session: BoolProperty(name="Has intelligent optimization session", default=False, options={"HIDDEN"})
    intelligent_optimization_state: StringProperty(name="Intelligent Optimization State", default="NOT_STARTED", options={"HIDDEN"})
    intelligent_optimization_last_result: StringProperty(name="Intelligent Optimization Result", default="", options={"HIDDEN"})
    intelligent_optimization_selected_strategy_id: StringProperty(name="Selected Strategy", default="")
    intelligent_optimization_strategy_count: IntProperty(name="Generated Strategies", default=0, options={"HIDDEN"})
    intelligent_optimization_evaluation_count: IntProperty(name="Evaluated Strategies", default=0, options={"HIDDEN"})
    intelligent_optimization_frontier_count: IntProperty(name="Pareto Points", default=0, options={"HIDDEN"})
    intelligent_optimization_search_mode: EnumProperty(
        name="Search Mode",
        items=(("FAST", "Fast", "Small interactive bounded search"), ("STANDARD", "Standard", "Moderate bounded search"), ("DEEP", "Deep", "Larger bounded search with runtime warning"), ("CUSTOM", "Custom", "Validated user budget within safety maxima")),
        default="STANDARD", update=_mark_intelligent_optimization_stale,
    )
    intelligent_optimization_objective_preset: EnumProperty(
        name="Objective Preset",
        items=(("Balanced", "Balanced", "Visible balanced multi-objective ranking"), ("Minimum Supports", "Minimum Supports", "Prioritize support and bridge risk"), ("Maximum Fidelity", "Maximum Fidelity", "Prioritize fidelity and thin features"), ("Fit to Printer", "Fit to Printer", "Prioritize bounded build fit"), ("Stable Base", "Stable Base", "Prioritize contact and base stability"), ("Lightweight", "Lightweight", "Prioritize triangle and runtime reduction"), ("Resin Advisory", "Resin Advisory", "Prioritize resin advisory evidence"), ("Custom", "Custom", "Use explicit custom objective weights")),
        default="Balanced", update=_mark_intelligent_optimization_stale,
    )
    intelligent_optimization_ranking_method: EnumProperty(
        name="Ranking Method",
        items=(("CONSTRAINT_FIRST", "Constraint-first", "Filter hard constraints before ranking"), ("WEIGHTED_SUM", "Weighted Sum", "Visible weighted objective contributions"), ("WEIGHTED_TCHEBYCHEFF", "Weighted Tchebycheff", "Distance to explicit ideal"), ("LEXICOGRAPHIC", "Lexicographic", "Deterministic objective priority order"), ("BALANCED_DISTANCE_TO_IDEAL", "Distance to Ideal", "Balanced distance to ideal"), ("FIDELITY_FIRST", "Fidelity-first", "Prioritize geometry fidelity"), ("MINIMUM_SUPPORTS", "Minimum Supports", "Prioritize support risk"), ("FIT_TO_PRINTER", "Fit-to-Printer", "Prioritize build fit"), ("STABLE_BASE", "Stable Base", "Prioritize contact"), ("LIGHTWEIGHT", "Lightweight", "Prioritize bounded lightweight result")),
        default="CONSTRAINT_FIRST", update=_mark_intelligent_optimization_stale,
    )
    intelligent_optimization_max_generated: IntProperty(name="Strategy Budget", default=32, min=1, max=256, update=_mark_intelligent_optimization_stale)
    intelligent_optimization_max_evaluated: IntProperty(name="Evaluation Budget", default=16, min=1, max=128, update=_mark_intelligent_optimization_stale)
    intelligent_optimization_max_depth: IntProperty(name="Maximum Strategy Depth", default=3, min=1, max=8, update=_mark_intelligent_optimization_stale)
    intelligent_optimization_max_frontier: IntProperty(name="Maximum Frontier Size", default=16, min=1, max=128, update=_mark_intelligent_optimization_stale)
    intelligent_optimization_experimental: BoolProperty(name="Enable Experimental Operations", default=False, update=_mark_intelligent_optimization_stale)

    ai_assistance_enabled: BoolProperty(name="Enable AI Assistance", default=False, update=_mark_ai_assistance_stale)
    ai_assistance_has_session: BoolProperty(name="Has AI assistance session", default=False, options={"HIDDEN"})
    ai_assistance_state: StringProperty(name="AI Assistance State", default="INITIAL", options={"HIDDEN"})
    ai_assistance_last_result: StringProperty(name="AI Assistance Result", default="", options={"HIDDEN"})
    ai_assistance_user_goal: StringProperty(name="Goal", default="Review the current bounded optimization strategies and explain the safest trade-offs.", maxlen=4096)
    ai_assistance_mode: EnumProperty(
        name="Assistance Mode",
        items=(("FAST", "Fast", "Small bounded context and response"), ("STANDARD", "Standard", "Balanced bounded assistance"), ("DEEP", "Deep", "Larger bounded evidence set with a runtime warning")),
        default="STANDARD", update=_mark_ai_assistance_stale,
    )
    ai_assistance_provider: EnumProperty(
        name="Provider", items=(("openai", "OpenAI", "Direct user-initiated OpenAI Responses API request"),),
        default="openai", update=_mark_ai_assistance_stale,
    )
    ai_assistance_model_id: StringProperty(name="Model ID", default="", maxlen=128, update=_mark_ai_assistance_stale)
    ai_assistance_consent: BoolProperty(name="I approve this disclosed request", default=False)
    ai_assistance_selected_recommendation_id: StringProperty(name="Selected Recommendation", default="")
    ai_assistance_recommendation_count: IntProperty(name="Recommendation Count", default=0, options={"HIDDEN"})


SESSION_STATE_CLASS = CHROMA3D_PG_session_state
CLASSES = (CHROMA3D_PG_tiny_shell_candidate, CHROMA3D_PG_small_hole_candidate, CHROMA3D_PG_session_state)


def update_session_state(window_manager: bpy.types.WindowManager, result: AnalysisResult) -> None:
    state = window_manager.chroma3d_sculpt_state
    state.has_analysis = True
    state.analyzed_object_name = result.object_metadata.object_name
    state.severity = result.severity.value
    state.last_analysis = result.analyzed_at.isoformat()


def reset_session_state(window_manager: bpy.types.WindowManager) -> None:
    state = window_manager.chroma3d_sculpt_state
    state.has_analysis = False
    state.analyzed_object_name = ""
    state.severity = ""
    state.last_analysis = ""
