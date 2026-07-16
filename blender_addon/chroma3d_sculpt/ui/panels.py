"""Compact native 3D Viewport sidebar panel."""

from __future__ import annotations

import bpy

from ..metadata import DISPLAY_VERSION
from ..models.analysis_result import AnalysisSeverity
from ..session import get_result
from ..utilities.context import is_valid_mesh_object

_MAX_PANEL_MESSAGES = 3


def _boolean_row(layout: bpy.types.UILayout, label: str, value: bool) -> None:
    row = layout.row()
    row.label(text=label)
    row.label(text="Yes" if value else "No", icon="CHECKMARK" if value else "ERROR")


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


class CHROMA3D_PT_sculpt(bpy.types.Panel):
    bl_idname = "CHROMA3D_PT_sculpt"
    bl_label = "Chroma3D Sculpt"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Chroma3D"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        obj = getattr(context, "active_object", None)
        valid_mesh = is_valid_mesh_object(obj)
        result = get_result(obj) if valid_mesh else None

        layout.label(text=f"Version {DISPLAY_VERSION}", icon="MESH_DATA")
        model_box = layout.box()
        model_box.label(text="Active Model")
        model_box.label(text=obj.name if valid_mesh else "No mesh selected", icon="OBJECT_DATA" if valid_mesh else "INFO")
        if valid_mesh and obj.mode == "EDIT":
            model_box.label(text="Exit Edit Mode to analyze", icon="INFO")

        analyze_row = layout.row()
        analyze_row.enabled = valid_mesh
        analyze_row.operator("chroma3d.analyze_mesh", icon="VIEWZOOM")

        if result is None:
            status_box = layout.box()
            status_box.label(text="Analysis Status")
            status_box.label(text="Not analyzed", icon="QUESTION")
        else:
            severity_icon = {
                AnalysisSeverity.PASS: "CHECKMARK",
                AnalysisSeverity.WARNING: "ERROR",
                AnalysisSeverity.FAIL: "CANCEL",
            }[result.severity]
            severity_label = {
                AnalysisSeverity.PASS: "Passed",
                AnalysisSeverity.WARNING: "Warnings",
                AnalysisSeverity.FAIL: "Failed",
            }[result.severity]
            status_box = layout.box()
            status_box.label(text="Analysis Status")
            status_box.label(text=severity_label, icon=severity_icon)

            geometry = layout.box()
            geometry.label(text="Geometry", icon="MESH_DATA")
            geometry.label(text=f"Vertices: {result.geometry.vertex_count:,}")
            geometry.label(text=f"Edges: {result.geometry.edge_count:,}")
            geometry.label(text=f"Faces: {result.geometry.polygon_count:,}")
            geometry.label(text=f"Triangles: {result.geometry.triangle_count:,}")
            geometry.label(text=f"Disconnected components: {result.topology.disconnected_shells:,}")

            dimensions = layout.box()
            dimensions.label(text="Dimensions", icon="DRIVER_DISTANCE")
            dimensions.label(text=f"Width: {result.dimensions.width_mm:,.3f} mm")
            dimensions.label(text=f"Depth: {result.dimensions.depth_mm:,.3f} mm")
            dimensions.label(text=f"Height: {result.dimensions.height_mm:,.3f} mm")
            dimensions.label(text="Units: millimetres")

            transforms = layout.box()
            transforms.label(text="Transform Status", icon="ORIENTATION_GLOBAL")
            _boolean_row(transforms, "Location applied:", result.transforms.location_applied)
            _boolean_row(transforms, "Rotation applied:", result.transforms.rotation_applied)
            _boolean_row(transforms, "Scale applied:", result.transforms.scale_applied)

            topology = layout.box()
            topology.label(text="Topology", icon="MOD_TRIANGULATE")
            topology.label(text=f"Non-manifold edges: {result.topology.non_manifold_edges:,}")
            topology.label(text=f"Boundary edges: {result.topology.boundary_edges:,}")
            topology.label(text=f"Loose vertices: {result.topology.loose_vertices:,}")
            topology.label(text=f"Loose edges: {result.topology.loose_edges:,}")
            topology.label(text=f"Zero-length edges: {result.topology.zero_length_edges:,}")
            topology.label(text=f"Degenerate faces: {result.topology.degenerate_faces:,}")
            topology.label(text=f"Normal consistency: {result.topology.normal_consistency.value}")
            topology.label(text=f"Potential duplicates: {result.topology.potential_duplicate_vertices:,}")

            _message_section(layout, "Warnings", result.warnings, "ERROR")
            _message_section(layout, "Errors", result.errors, "CANCEL")

        export_row = layout.row()
        export_row.enabled = result is not None
        export_row.operator("chroma3d.export_analysis_report", icon="EXPORT")
        layout.separator()
        layout.label(
            text=f"Last analysis: {result.analyzed_at.strftime('%Y-%m-%d %H:%M:%S UTC')}" if result else "Last analysis: Never",
            icon="TIME",
        )


CLASSES = (CHROMA3D_PT_sculpt,)
