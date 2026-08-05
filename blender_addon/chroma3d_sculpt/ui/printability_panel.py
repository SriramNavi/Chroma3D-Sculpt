"""Compact Printability section for the Chroma3D 3D Viewport sidebar."""

from __future__ import annotations

import bpy

from ..printability_settings import settings_from_property_group
from ..services.printability_session import STALE_MESSAGE, get_result, stale_state
from ..services.printer_profile_loader import profile_from_property_group
from ..models.printability_models import StaleState
from ..utilities.context import is_valid_mesh_object


def display_result_for_state(obj: object, state: object) -> tuple[object | None, str | None]:
    result = get_result(obj)
    if result is None:
        return None, None
    try:
        profile = profile_from_property_group(state)
        settings = settings_from_property_group(state)
    except (AttributeError, TypeError, ValueError):
        return None, STALE_MESSAGE
    if stale_state(obj, result, profile, settings) != StaleState.CURRENT:
        return None, STALE_MESSAGE
    return result, None


def _check_box(layout: bpy.types.UILayout, title: str, result: object, category: str | None = None) -> None:
    box = layout.box()
    box.label(text=title)
    status = getattr(getattr(result, "status", None), "value", "UNKNOWN")
    confidence = getattr(getattr(result, "confidence", None), "value", "UNKNOWN")
    box.label(text=f"{status} / {confidence}", icon="CHECKMARK" if status == "PASS" else "ERROR" if status in {"WARNING", "INDETERMINATE", "SKIPPED_LIMIT"} else "CANCEL" if status in {"CRITICAL", "FAILED"} else "INFO")
    limitations = tuple(getattr(result, "limitations", ()))
    if limitations:
        text = limitations[0]
        box.label(text=text if len(text) <= 88 else f"{text[:85]}...", icon="INFO")
    if category:
        has_evidence = any(
            getattr(result, name, ())
            for name in ("evidence_faces", "evidence_vertices", "components")
        )
        row = box.row()
        row.enabled = bool(has_evidence)
        operator = row.operator("chroma3d.select_printability_issue", text="Select Evidence", icon="RESTRICT_SELECT_OFF")
        operator.evidence_category = category


class CHROMA3D_PT_printability(bpy.types.Panel):
    bl_idname = "CHROMA3D_PT_printability"
    bl_label = "Printability"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Chroma3D"
    bl_parent_id = "CHROMA3D_PT_sculpt"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        state = context.window_manager.chroma3d_sculpt_state
        obj = getattr(context, "active_object", None)
        valid = is_valid_mesh_object(obj)
        result, stale_message = display_result_for_state(obj, state) if valid else (None, None)

        profile_box = layout.box()
        profile_box.label(text="Profile", icon="PREFERENCES")
        profile_box.prop(state, "printability_profile", text="Profile")
        if state.printability_profile == "custom":
            profile_box.prop(state, "printability_custom_process")
            profile_box.prop(state, "printability_custom_manufacturer")
            profile_box.prop(state, "printability_custom_model")
            profile_box.prop(state, "printability_custom_material")
            column = profile_box.column(align=True)
            for name in (
                "printability_custom_build_x_mm", "printability_custom_build_y_mm", "printability_custom_build_z_mm",
                "printability_custom_margin_mm", "printability_custom_nozzle_mm", "printability_custom_layer_mm",
                "printability_custom_wall_warning_mm", "printability_custom_wall_critical_mm",
                "printability_custom_feature_warning_mm", "printability_custom_feature_critical_mm",
                "printability_custom_overhang_warning_deg", "printability_custom_overhang_critical_deg",
                "printability_custom_contact_tolerance_mm",
            ):
                column.prop(state, name)
        elif result:
            profile = result.printer_profile_snapshot.profile
            profile_box.label(text=f"Process: {profile.process_type.value}")
            profile_box.label(text=f"Build: {profile.build_volume_mm.x:g} x {profile.build_volume_mm.y:g} x {profile.build_volume_mm.z:g} mm")
            profile_box.label(text=f"Source: {profile.source_classification.value}")

        mode_box = layout.box()
        mode_box.label(text="Mode and Build Direction", icon="ORIENTATION_GIMBAL")
        mode_box.prop(state, "printability_mode", expand=True)
        row = mode_box.row(align=True)
        row.prop(state, "printability_build_direction_x", text="X")
        row.prop(state, "printability_build_direction_y", text="Y")
        row.prop(state, "printability_build_direction_z", text="Z")
        mode_box.prop(state, "printability_show_advanced", text="Candidate Settings", icon="DISCLOSURE_TRI_DOWN" if state.printability_show_advanced else "DISCLOSURE_TRI_RIGHT", emboss=False)
        if state.printability_show_advanced:
            mode_box.prop(state, "printability_principal_candidates")
            mode_box.prop(state, "printability_planar_candidates")
            mode_box.prop(state, "printability_sampled_candidates")

        analysis = layout.box()
        analysis.label(text="Analysis", icon="VIEWZOOM")
        row = analysis.row()
        row.enabled = valid and obj.mode != "EDIT"
        row.operator("chroma3d.analyze_printability", icon="VIEWZOOM")
        analysis.label(text=f"State: {'STALE' if stale_message else state.printability_state}")
        analysis.label(text=f"Duration: {state.printability_last_result or 'Not run'}")
        if result is None:
            analysis.label(text=stale_message or "No printability result for the active mesh", icon="ERROR" if stale_message else "QUESTION")
            return

        overall = layout.box()
        overall.label(text="Overall Result", icon="ERROR" if result.score_details.status.value != "PASS" else "CHECKMARK")
        score = "Unavailable" if result.score_details.score is None else f"{result.score_details.score}/100"
        overall.label(text=f"Score: {score}")
        overall.label(text=f"Status: {result.score_details.status.value}")
        overall.label(text=f"Confidence: {result.score_details.confidence.value}")
        overall.label(text=f"Critical: {len(result.score_details.critical_reasons)}  Missing/skipped: {len(result.score_details.missing_checks) + len(result.score_details.skipped_checks)}")

        _check_box(layout, "Wall Thickness", result.wall_thickness, "WALL_THICKNESS")
        _check_box(layout, "Thin Features (Experimental)", result.thin_features, "THIN_FEATURE")
        _check_box(layout, "Overhangs", result.overhangs, "OVERHANG")
        _check_box(layout, "Floating Components", result.floating_components, "FLOATING_COMPONENT")
        _check_box(layout, "Build-Plate Contact", result.build_plate_contact, "BUILD_CONTACT")
        _check_box(layout, "Build Volume and Scale", result.scale_evaluation)

        orientation = layout.box()
        orientation.label(text="Orientation Suggestions", icon="ORIENTATION_GIMBAL")
        for rank, candidate in enumerate(result.orientation.candidates[:4], 1):
            orientation.label(text=f"{rank}. {candidate.source.value}: {candidate.score}/100 / {candidate.overall_risk.value}")
            if candidate.trade_offs:
                text = candidate.trade_offs[0]
                orientation.label(text=text if len(text) <= 84 else f"{text[:81]}...", icon="INFO")
        if not result.orientation.candidates:
            orientation.label(text="No bounded candidate available", icon="INFO")
        orientation.label(text="Recommendations only; no Apply button", icon="LOCKED")

        exports = layout.box()
        exports.label(text="Export", icon="EXPORT")
        row = exports.row(align=True)
        row.operator("chroma3d.export_printability_json", text="JSON")
        row.operator("chroma3d.export_printability_markdown", text="Markdown")


CLASSES = (CHROMA3D_PT_printability,)
