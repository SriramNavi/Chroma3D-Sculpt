"""Advanced Preparation Blender sidebar with advisory-only controls and evidence."""

from __future__ import annotations

import bpy

from ..feature_flags import flags_from_property_group
from ..models.printability_models import StaleState
from ..printability_settings import settings_from_property_group
from ..services.advanced_preparation_session import (
    STALE_PREPARATION_MESSAGE, get_preparation_result, preparation_stale_state,
)
from ..services.batch_preparation_session import get_batch_result
from ..services.hardware_profile_loader import hardware_from_property_group
from ..services.material_profile_loader import material_from_property_group
from ..services.process_context import context_from_property_group
from ..utilities.context import is_valid_mesh_object


def display_preparation_result(obj: object, state: object):
    result = get_preparation_result(obj)
    if result is None:
        return None, None
    try:
        hardware = hardware_from_property_group(state)
        material = material_from_property_group(state)
        process = context_from_property_group(state, hardware, material)
        flags = flags_from_property_group(state)
        settings = settings_from_property_group(state)
    except (AttributeError, TypeError, ValueError):
        return None, STALE_PREPARATION_MESSAGE
    stale = preparation_stale_state(obj, result, hardware, material, process, flags, settings)
    if stale != StaleState.CURRENT:
        return None, f"{STALE_PREPARATION_MESSAGE} ({stale.value})"
    return result, None


def _state_icon(status: str) -> str:
    if status == "PASS": return "CHECKMARK"
    if status in {"WARNING", "INDETERMINATE", "SKIPPED_LIMIT", "NOT_EVALUATED"}: return "ERROR"
    if status in {"CRITICAL", "FAILED"}: return "CANCEL"
    return "INFO"


class CHROMA3D_PT_advanced_preparation(bpy.types.Panel):
    bl_idname = "CHROMA3D_PT_advanced_preparation"
    bl_label = "Advanced Preparation"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Chroma3D"
    bl_parent_id = "CHROMA3D_PT_sculpt"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        state = context.window_manager.chroma3d_sculpt_state
        obj = getattr(context, "active_object", None)
        valid = is_valid_mesh_object(obj)
        result, stale_message = display_preparation_result(obj, state) if valid else (None, None)

        process_box = layout.box(); process_box.label(text="Process Context", icon="PREFERENCES")
        process_box.prop(state, "printability_profile", text="Hardware")
        process_box.prop(state, "preparation_material_profile", text="Material")
        row = process_box.row(align=True); row.prop(state, "preparation_nozzle_mm"); row.prop(state, "preparation_layer_height_mm")
        process_box.prop(state, "preparation_build_plate_type"); process_box.prop(state, "preparation_support_policy")
        if state.preparation_material_profile == "custom_material":
            process_box.prop(state, "preparation_custom_material_name"); process_box.prop(state, "preparation_custom_material_family")
            for name in ("preparation_custom_wall_multiplier", "preparation_custom_feature_multiplier", "preparation_custom_bridge_modifier", "preparation_custom_overhang_modifier"):
                process_box.prop(state, name)
        try:
            hardware = hardware_from_property_group(state); material = material_from_property_group(state)
            process = context_from_property_group(state, hardware, material)
            process_box.label(text=f"Confidence: {material.confidence.value} / {hardware.confidence.value}")
            for name in ("wall_thickness_warning_mm", "minimum_feature_warning_mm", "bridge_warning_span_mm", "overhang_warning_angle_deg"):
                process_box.label(text=f"{name.replace('_', ' ')}: {process.effective_thresholds[name]:.3f}")
            process_box.label(text="Provenance retained in report snapshot", icon="INFO")
        except ValueError as exc:
            process_box.label(text=str(exc)[:100], icon="ERROR")

        flags = layout.box(); flags.label(text="Feature Flags", icon="OPTIONS")
        flags.prop(state, "preparation_bridge_risk"); flags.prop(state, "preparation_support_risk")
        flags.prop(state, "preparation_resin_advisory"); flags.prop(state, "preparation_baseline_enabled")
        flags.prop(state, "preparation_experimental_modifiers")
        flags.label(text="Resin and material modifiers are experimental", icon="INFO")

        analysis = layout.box(); analysis.label(text="Analysis", icon="VIEWZOOM")
        analysis.prop(state, "printability_mode", expand=True)
        row = analysis.row(align=True); row.enabled = valid and obj.mode != "EDIT" if valid else False
        row.operator("chroma3d.analyze_advanced_preparation", text="Analyze Current Object")
        row.operator("chroma3d.analyze_preparation_batch", text="Analyze Selected Objects")
        analysis.operator("chroma3d.cancel_preparation_batch", text="Cancel")
        analysis.label(text=f"State: {'STALE' if stale_message else state.preparation_state}")
        analysis.label(text=f"Progress/result: {state.preparation_last_result or 'Not run'}")
        if stale_message: analysis.label(text=stale_message[:110], icon="ERROR")

        if result:
            overall = layout.box(); overall.label(text="Results", icon=_state_icon(result.status.value))
            overall.label(text=f"Score: {'Unavailable' if result.score is None else f'{result.score}/100'}")
            overall.label(text=f"Status / confidence: {result.status.value} / {result.confidence.value}")
            for title, check in (("Bridge risks", result.bridge_risk), ("Support risks", result.support_risk), ("Resin advisory (Experimental)", result.resin_advisory)):
                overall.label(text=f"{title}: {check.status.value}", icon=_state_icon(check.status.value))
            interval = result.scale_recommendation.recommended_interval
            overall.label(text=f"Scale interval: {interval.state} ({interval.minimum_percent}, {interval.maximum_percent})")
            overall.label(text=f"Orientation candidates: {len(result.orientation_comparison.candidates)}; Pareto: {len(result.orientation_comparison.pareto_candidate_ids)}")
            overall.label(text=f"Missing/skipped: {len(result.skipped_checks)}; failed: {len(result.failed_checks)}")
            for candidate in result.orientation_comparison.candidates[:3]:
                overall.label(text=f"#{candidate['deterministic_rank']} {candidate['source']}: bridge {candidate['bridge_risk_count']}, support {candidate['support_risk_area_mm2']:.2f} mm2")
            exports = overall.row(align=True); exports.operator("chroma3d.export_preparation_json", text="JSON"); exports.operator("chroma3d.export_preparation_markdown", text="Markdown")

        batch = layout.box(); batch.label(text="Batch", icon="OUTLINER_OB_GROUP_INSTANCE")
        selected_count = sum(1 for item in context.selected_objects if is_valid_mesh_object(item))
        batch.label(text=f"Selected mesh objects: {selected_count}")
        batch.label(text=f"Status: {state.preparation_batch_status}")
        batch.label(text=state.preparation_batch_summary or "No batch result")
        batch_result = get_batch_result()
        if batch_result:
            for item in batch_result.object_results[:5]:
                batch.label(text=f"{item.get('object_name')}: {item.get('status')} / {item.get('score')}")
            batch.operator("chroma3d.export_preparation_batch", text="Export Aggregate Report")

        baseline = layout.box(); baseline.label(text="Baseline", icon="FILE_TICK")
        row = baseline.row(align=True); row.enabled = state.preparation_baseline_enabled
        row.operator("chroma3d.generate_preparation_baseline", text="Generate"); row.operator("chroma3d.verify_preparation_baseline", text="Verify")
        baseline.operator("chroma3d.compare_preparation_baseline", text="Compare Current Run")
        baseline.operator("chroma3d.open_preparation_dashboard", text="Open Dashboard File Path")
        if state.preparation_dashboard_path: baseline.label(text=state.preparation_dashboard_path[-100:], icon="FILE")
        baseline.label(text="No orientation, scale, support, slice, or print action is applied", icon="LOCKED")


CLASSES = (CHROMA3D_PT_advanced_preparation,)
