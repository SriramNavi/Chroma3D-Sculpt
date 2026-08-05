"""Blender UI settings plus small session-state scalars."""

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, StringProperty

from ..models.analysis_result import AnalysisResult


def _mark_printability_profile_stale(self: bpy.types.PropertyGroup, _context: bpy.types.Context) -> None:
    if bool(getattr(self, "printability_has_result", False)):
        self.printability_state = "STALE_PROFILE"


def _mark_printability_settings_stale(self: bpy.types.PropertyGroup, _context: bpy.types.Context) -> None:
    if bool(getattr(self, "printability_has_result", False)):
        self.printability_state = "STALE_SETTINGS"


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
