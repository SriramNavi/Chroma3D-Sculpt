"""Compact Sprint 1 diagnostics UI in the native 3D Viewport sidebar."""

from __future__ import annotations

import bpy

from ..metadata import DISPLAY_VERSION
from ..models.analysis_result import AnalysisProfile, AnalysisSeverity, EvaluationStatus
from ..session import get_result
from ..utilities.context import is_valid_mesh_object

_MAX_PANEL_MESSAGES = 3
_MAX_PANEL_SHELLS = 6


def _message_section(layout: bpy.types.UILayout, title: str, messages: tuple[str, ...], icon: str) -> None:
    box = layout.box()
    box.label(text=title, icon=icon)
    if not messages:
        box.label(text="None")
        return
    for message in messages[:_MAX_PANEL_MESSAGES]:
        text = message if len(message) <= 88 else f"{message[:85]}..."
        box.label(text=text, icon="DOT")
    remaining = len(messages) - _MAX_PANEL_MESSAGES
    if remaining > 0:
        box.label(text=f"+ {remaining} more in JSON report", icon="INFO")


def _select_button(layout: bpy.types.UILayout, label: str, category: str, count: int) -> None:
    if count <= 0:
        return
    operator = layout.operator("chroma3d.select_diagnostic_issue", text=f"{label} ({count:,})", icon="RESTRICT_SELECT_OFF")
    operator.issue_category = category


class CHROMA3D_PT_sculpt(bpy.types.Panel):
    bl_idname = "CHROMA3D_PT_sculpt"
    bl_label = "Chroma3D Sculpt"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Chroma3D"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        state = context.window_manager.chroma3d_sculpt_state
        obj = getattr(context, "active_object", None)
        valid_mesh = is_valid_mesh_object(obj)
        result = get_result(obj) if valid_mesh else None

        header = layout.box()
        header.label(text=f"Chroma3D Sculpt {DISPLAY_VERSION}", icon="MESH_DATA")
        header.label(text=obj.name if valid_mesh else "No mesh selected", icon="OBJECT_DATA" if valid_mesh else "INFO")
        header.label(
            text=f"Last: {result.analyzed_at.strftime('%Y-%m-%d %H:%M:%S UTC')}" if result else "Last analysis: Never",
            icon="TIME",
        )

        settings_box = layout.box()
        settings_box.label(text="Analysis Settings", icon="PREFERENCES")
        settings_box.prop(state, "analysis_profile", text="Depth")
        settings_box.prop(state, "printer_profile", text="Printer")
        if state.printer_profile == "CUSTOM":
            column = settings_box.column(align=True)
            column.prop(state, "custom_build_width_mm", text="X mm")
            column.prop(state, "custom_build_depth_mm", text="Y mm")
            column.prop(state, "custom_build_height_mm", text="Z mm")
        settings_box.prop(
            state,
            "show_advanced_settings",
            text="Advanced Settings",
            icon="DISCLOSURE_TRI_DOWN" if state.show_advanced_settings else "DISCLOSURE_TRI_RIGHT",
            emboss=False,
        )
        if state.show_advanced_settings:
            advanced = settings_box.column(align=True)
            for property_name in (
                "duplicate_position_tolerance",
                "duplicate_vertex_limit",
                "degenerate_edge_tolerance",
                "degenerate_face_tolerance",
                "tiny_shell_max_face_count",
                "tiny_shell_max_volume_mm3",
                "tiny_shell_max_relative_volume_percent",
                "tiny_shell_max_diagonal_mm",
                "maximum_stored_issue_indices",
                "self_intersection_triangle_limit",
                "maximum_stored_self_intersection_pairs",
                "containment_shell_limit",
                "containment_triangle_limit",
            ):
                advanced.prop(state, property_name)
        analyze_row = settings_box.row()
        analyze_row.enabled = valid_mesh and obj.mode != "EDIT"
        analyze_row.operator("chroma3d.analyze_mesh", icon="VIEWZOOM")
        if valid_mesh and obj.mode == "EDIT":
            settings_box.label(text="Exit Edit Mode before analysis", icon="INFO")

        if result is None:
            layout.label(text="Not analyzed", icon="QUESTION")
            return

        severity_icon = {
            AnalysisSeverity.PASS: "CHECKMARK",
            AnalysisSeverity.WARNING: "ERROR",
            AnalysisSeverity.FAIL: "CANCEL",
        }[result.severity]
        status_box = layout.box()
        status_box.label(text=f"Overall: {result.severity.value}", icon=severity_icon)
        status_box.label(text=f"Duration: {result.duration_ms:,.2f} ms")
        completed = sum(check.status == EvaluationStatus.COMPLETED for check in result.checks)
        skipped = sum(check.status == EvaluationStatus.SKIPPED for check in result.checks)
        failed = sum(check.status == EvaluationStatus.FAILED for check in result.checks)
        status_box.label(text=f"Checks: {completed} complete / {skipped} skipped / {failed} failed")

        geometry = layout.box()
        geometry.label(text="Geometry", icon="MESH_DATA")
        geometry.label(
            text=f"V {result.geometry.vertex_count:,}  E {result.geometry.edge_count:,}  F {result.geometry.polygon_count:,}"
        )
        geometry.label(text=f"Triangles {result.geometry.triangle_count:,}  Shells {len(result.shells):,}")

        topology = layout.box()
        topology.label(text="Topological Integrity", icon="MOD_TRIANGULATE")
        topology.label(text=f"Watertight: {result.topology.watertight_state.value.replace('_', ' ').title()}")
        topology.label(text=f"Edge manifold: {result.topology.edge_manifold_state.value}")
        topology.label(text=f"Vertex manifold: {result.topology.vertex_manifold_state.value}")
        topology.label(text=f"Boundary: {result.topology.boundary_edges:,}  High-incidence: {result.topology.high_incidence_non_manifold_edges:,}")
        topology.label(text=f"Orientation: {result.topology.normal_consistency.value}")

        physical = layout.box()
        physical.label(text="Physical Metrics", icon="DRIVER_DISTANCE")
        physical.label(text=f"{result.dimensions.width_mm:,.3f} x {result.dimensions.depth_mm:,.3f} x {result.dimensions.height_mm:,.3f} mm")
        physical.label(text=f"Surface area: {result.surface_volume.total_surface_area_mm2:,.3f} mm^2")
        if result.surface_volume.reliable_closed_shell_volume_mm3 is None:
            physical.label(text="Reliable volume: Unavailable", icon="INFO")
        else:
            physical.label(text=f"Reliable volume: {result.surface_volume.reliable_closed_shell_volume_mm3:,.3f} mm^3")

        shells = layout.box()
        shells.label(text="Shell Review", icon="OUTLINER_OB_MESH")
        shells.label(text=f"Main: {result.main_shell_id}  Tiny candidates: {len(result.tiny_shell_candidate_ids)}")
        shells.label(text=f"External: {len(result.disconnected_external_shell_ids)}  Possibly internal: {len(result.possible_internal_shell_ids)}")
        for shell in result.shells[:_MAX_PANEL_SHELLS]:
            marker = " [tiny candidate]" if shell.tiny_shell_candidate else ""
            shells.label(text=f"S{shell.shell_id}: {shell.classification.value} / {shell.face_count:,} faces{marker}")
        if len(result.shells) > _MAX_PANEL_SHELLS:
            shells.label(text=f"+ {len(result.shells) - _MAX_PANEL_SHELLS} more in JSON", icon="INFO")

        if result.analysis_profile == AnalysisProfile.DEEP:
            deep = layout.box()
            deep.label(text="Deep Diagnostics", icon="VIEWZOOM")
            deep.label(text=f"Self-intersection: {result.deep_diagnostics.self_intersection_state.value}")
            count = result.deep_diagnostics.self_intersection_candidate_count
            deep.label(text=f"Candidate pairs: {count if count is not None else 'Not evaluated'}")
            deep.label(text=f"Containment: {result.deep_diagnostics.containment_status.value}")
            for note in result.deep_diagnostics.notes:
                if "Skipped" in note or "failed" in note.lower():
                    deep.label(text=note[:88], icon="INFO")

        build = layout.box()
        build.label(text="Build Volume", icon="CUBE")
        build.label(text=f"Profile: {result.build_volume.printer_profile.value.replace('_', ' ').title()}")
        build.label(text=result.build_volume.fit_state.value.replace("_", " ").title())
        if result.build_volume.maximum_uniform_scale_percent is not None:
            build.label(text=f"Maximum uniform scale: {result.build_volume.maximum_uniform_scale_percent:.2f}%")

        issue_box = layout.box()
        issue_box.label(text="Issue Inspection", icon="RESTRICT_SELECT_OFF")
        for evidence in result.issue_evidence:
            _select_button(
                issue_box,
                evidence.category.value.replace("_", " ").title(),
                evidence.category.value,
                len(evidence.indices),
            )
        if not any(evidence.indices for evidence in result.issue_evidence):
            issue_box.label(text="No selectable evidence stored")

        timing_box = layout.box()
        timing_box.prop(
            state,
            "show_timings",
            text="Check Timings",
            icon="DISCLOSURE_TRI_DOWN" if state.show_timings else "DISCLOSURE_TRI_RIGHT",
            emboss=False,
        )
        if state.show_timings:
            for timing in result.timings:
                timing_box.label(text=f"{timing.name}: {timing.status.value} / {timing.duration_ms:.3f} ms")

        _message_section(layout, "Warnings", result.warnings, "ERROR")
        _message_section(layout, "Errors", result.errors, "CANCEL")
        layout.operator("chroma3d.export_analysis_report", icon="EXPORT")


CLASSES = (CHROMA3D_PT_sculpt,)
