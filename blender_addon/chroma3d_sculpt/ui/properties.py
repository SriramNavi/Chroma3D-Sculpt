"""Blender UI settings plus small session-state scalars."""

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty

from ..models.analysis_result import AnalysisResult


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


CLASSES = (CHROMA3D_PG_session_state,)


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
