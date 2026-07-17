"""Operator that runs a read-only active-mesh analysis."""

from __future__ import annotations

import bpy

from ..analysis_settings import settings_from_property_group
from ..services.mesh_analyzer import analyze_mesh
from ..session import store_result
from ..ui.properties import update_session_state
from ..utilities.context import active_mesh_object, capture_context_identity, is_valid_mesh_object
from ..utilities.logging import get_logger

logger = get_logger()


class CHROMA3D_OT_analyze_mesh(bpy.types.Operator):
    bl_idname = "chroma3d.analyze_mesh"
    bl_label = "Analyze Mesh"
    bl_description = "Run non-destructive diagnostics on the active original mesh datablock"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return is_valid_mesh_object(getattr(context, "active_object", None))

    def execute(self, context: bpy.types.Context) -> set[str]:
        obj = active_mesh_object(context)
        if obj is None:
            self.report({"ERROR"}, "Select an active mesh object before analysis.")
            return {"CANCELLED"}
        if obj.mode == "EDIT":
            self.report({"WARNING"}, "Exit Edit Mode before analysis; Chroma3D will not change object mode.")
            return {"CANCELLED"}

        identity_before = capture_context_identity(context)
        try:
            settings = settings_from_property_group(context.window_manager.chroma3d_sculpt_state)
            result = analyze_mesh(
                obj,
                context.scene,
                settings=settings,
                blender_version=bpy.app.version_string,
                blend_file_path=bpy.data.filepath,
            )
            if capture_context_identity(context) != identity_before:
                self.report({"ERROR"}, "Active object or selection changed during analysis; result was discarded.")
                return {"CANCELLED"}
            store_result(obj, result)
            update_session_state(context.window_manager, result)
        except Exception as exc:
            logger.exception("Analysis operator failed")
            self.report({"ERROR"}, f"Analysis failed: {type(exc).__name__}: {exc}")
            return {"CANCELLED"}

        if result.errors:
            self.report({"ERROR"}, result.summary)
        elif result.warnings:
            self.report({"WARNING"}, result.summary)
        else:
            self.report({"INFO"}, result.summary)
        return {"FINISHED"}


CLASSES = (CHROMA3D_OT_analyze_mesh,)
