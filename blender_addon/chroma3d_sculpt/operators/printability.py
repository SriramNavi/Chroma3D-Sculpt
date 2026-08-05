"""Explicit Sprint 3 analyze, evidence-selection, and report-export operators."""

from __future__ import annotations

from pathlib import Path

import bpy
from bpy.props import EnumProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from ..printability_settings import settings_from_property_group
from ..services.printability_coordinator import analyze_printability
from ..services.printability_report import (
    sanitize_printability_filename,
    write_printability_json,
    write_printability_markdown,
)
from ..services.printability_session import get_result, require_current, store_result
from ..services.printer_profile_loader import profile_from_property_group
from ..utilities.context import is_valid_mesh_object
from ..utilities.logging import get_logger


logger = get_logger()


def _current(context: bpy.types.Context):
    state = context.window_manager.chroma3d_sculpt_state
    profile = profile_from_property_group(state)
    settings = settings_from_property_group(state)
    result = require_current(context.active_object, profile, settings)
    return result, profile, settings


class CHROMA3D_OT_analyze_printability(bpy.types.Operator):
    bl_idname = "chroma3d.analyze_printability"
    bl_label = "Analyze Printability"
    bl_description = "Run read-only advisory printability checks with the selected local profile"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        obj = getattr(context, "active_object", None)
        return is_valid_mesh_object(obj) and getattr(obj, "mode", "") != "EDIT"

    def execute(self, context: bpy.types.Context) -> set[str]:
        state = context.window_manager.chroma3d_sculpt_state
        obj = context.active_object
        wm = context.window_manager
        wm.progress_begin(0, 100)
        try:
            wm.progress_update(5)
            profile = profile_from_property_group(state)
            settings = settings_from_property_group(state)
            result = analyze_printability(
                obj,
                context.scene,
                profile,
                settings,
                blender_version=bpy.app.version_string,
                blend_file_path=bpy.data.filepath,
            )
            wm.progress_update(95)
            store_result(obj, result)
            state.printability_has_result = True
            state.printability_object_name = obj.name
            state.printability_status = result.score_details.status.value
            state.printability_confidence = result.score_details.confidence.value
            state.printability_last_result = f"{result.timings['total']:.3f}s"
            state.printability_state = "CURRENT"
        except (MemoryError, OSError, TypeError, ValueError, RuntimeError) as exc:
            logger.exception("Printability analysis failed")
            state.printability_last_result = f"FAILED: {type(exc).__name__}"
            self.report({"ERROR"}, f"Printability analysis failed: {exc}")
            return {"CANCELLED"}
        finally:
            wm.progress_update(100)
            wm.progress_end()
        self.report({"INFO"}, f"Printability analysis complete: {result.score_details.status.value}")
        return {"FINISHED"}


class CHROMA3D_OT_select_printability_issue(bpy.types.Operator):
    bl_idname = "chroma3d.select_printability_issue"
    bl_label = "Select Printability Evidence"
    bl_description = "Select only bounded current evidence; geometry is never changed"
    bl_options = {"REGISTER", "UNDO"}

    evidence_category: EnumProperty(
        items=(
            ("WALL_THICKNESS", "Wall thickness", "Select bounded wall face evidence"),
            ("THIN_FEATURE", "Thin feature", "Select bounded thin-feature vertex evidence"),
            ("OVERHANG", "Overhang", "Select bounded overhang face evidence"),
            ("FLOATING_COMPONENT", "Floating component", "Select bounded floating-shell face evidence"),
            ("BUILD_CONTACT", "Build contact", "Select bounded contact face evidence"),
        )
    )

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return is_valid_mesh_object(getattr(context, "active_object", None)) and get_result(context.active_object) is not None

    def execute(self, context: bpy.types.Context) -> set[str]:
        obj = context.active_object
        try:
            result, _profile, _settings = _current(context)
            faces: tuple[int, ...] = ()
            vertices: tuple[int, ...] = ()
            if self.evidence_category == "WALL_THICKNESS":
                faces = result.wall_thickness.evidence_faces
            elif self.evidence_category == "THIN_FEATURE":
                vertices = result.thin_features.evidence_vertices
            elif self.evidence_category == "OVERHANG":
                faces = result.overhangs.evidence_faces
            elif self.evidence_category == "FLOATING_COMPONENT":
                floating = set(result.floating_components.floating_shell_ids)
                faces = tuple(face for item in result.floating_components.components if item.shell_id in floating for face in item.evidence_faces)
            elif self.evidence_category == "BUILD_CONTACT":
                faces = result.build_plate_contact.evidence_faces
                vertices = result.build_plate_contact.evidence_vertices if not faces else ()
            if any(index < 0 or index >= len(obj.data.polygons) for index in faces) or any(index < 0 or index >= len(obj.data.vertices) for index in vertices):
                raise ValueError("Stored printability evidence contains invalid current mesh indices.")
            if obj.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            for polygon in obj.data.polygons:
                polygon.select = False
            for vertex in obj.data.vertices:
                vertex.select = False
            for index in faces:
                obj.data.polygons[index].select = True
            for index in vertices:
                obj.data.vertices[index].select = True
            if not faces and not vertices:
                self.report({"WARNING"}, "No bounded evidence is available for this result.")
                return {"CANCELLED"}
            bpy.ops.object.mode_set(mode="EDIT")
        except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Selected {len(faces) + len(vertices)} bounded evidence item(s).")
        return {"FINISHED"}


class _PrintabilityExportBase:
    def _invoke_path(self, context: bpy.types.Context, event: bpy.types.Event, suffix: str) -> set[str]:
        try:
            result, _profile, _settings = _current(context)
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        directory = Path(bpy.path.abspath("//")) if bpy.data.filepath else Path.home()
        self.filepath = str(directory / sanitize_printability_filename(str(result.object_metadata["object_name"]), suffix))
        return ExportHelper.invoke(self, context, event)


class CHROMA3D_OT_export_printability_json(_PrintabilityExportBase, bpy.types.Operator, ExportHelper):
    bl_idname = "chroma3d.export_printability_json"
    bl_label = "Export Printability JSON"
    bl_options = {"REGISTER"}
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        return self._invoke_path(context, event, "json")

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            result, _profile, _settings = _current(context)
            output = write_printability_json(result, Path(self.filepath))
        except (OSError, TypeError, ValueError) as exc:
            logger.exception("Printability JSON export failed")
            self.report({"ERROR"}, f"Could not export printability JSON: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Printability JSON exported: {output.name}")
        return {"FINISHED"}


class CHROMA3D_OT_export_printability_markdown(_PrintabilityExportBase, bpy.types.Operator, ExportHelper):
    bl_idname = "chroma3d.export_printability_markdown"
    bl_label = "Export Printability Markdown"
    bl_options = {"REGISTER"}
    filename_ext = ".md"
    filter_glob: StringProperty(default="*.md", options={"HIDDEN"})

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        return self._invoke_path(context, event, "markdown")

    def execute(self, context: bpy.types.Context) -> set[str]:
        try:
            result, _profile, _settings = _current(context)
            output = write_printability_markdown(result, Path(self.filepath))
        except (OSError, TypeError, ValueError) as exc:
            logger.exception("Printability Markdown export failed")
            self.report({"ERROR"}, f"Could not export printability Markdown: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Printability Markdown exported: {output.name}")
        return {"FINISHED"}


CLASSES = (
    CHROMA3D_OT_analyze_printability,
    CHROMA3D_OT_select_printability_issue,
    CHROMA3D_OT_export_printability_json,
    CHROMA3D_OT_export_printability_markdown,
)
