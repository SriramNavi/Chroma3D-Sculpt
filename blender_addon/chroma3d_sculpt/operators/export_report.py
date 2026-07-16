"""JSON report export through Blender's standard file browser."""

from pathlib import Path

import bpy
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper

from ..services.report_generator import sanitize_report_filename, write_json_report
from ..session import get_result
from ..utilities.logging import get_logger

logger = get_logger()


class CHROMA3D_OT_export_analysis_report(bpy.types.Operator, ExportHelper):
    bl_idname = "chroma3d.export_analysis_report"
    bl_label = "Export JSON Report"
    bl_description = "Export the active model's latest Chroma3D analysis as JSON"
    bl_options = {"REGISTER"}

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return get_result(getattr(context, "active_object", None)) is not None

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> set[str]:
        result = get_result(getattr(context, "active_object", None))
        if result is None:
            self.report({"ERROR"}, "Analyze the active mesh before exporting a report.")
            return {"CANCELLED"}
        filename = sanitize_report_filename(result.object_metadata.object_name)
        blend_directory = Path(bpy.path.abspath("//")) if bpy.data.filepath else Path.home()
        self.filepath = str(blend_directory / filename)
        return ExportHelper.invoke(self, context, event)

    def execute(self, context: bpy.types.Context) -> set[str]:
        result = get_result(getattr(context, "active_object", None))
        if result is None:
            self.report({"ERROR"}, "The latest analysis is unavailable or belongs to another object.")
            return {"CANCELLED"}
        try:
            output = write_json_report(result, Path(self.filepath))
        except (OSError, ValueError, TypeError) as exc:
            logger.exception("Report export failed")
            self.report({"ERROR"}, f"Could not export report: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Analysis report exported: {output.name}")
        return {"FINISHED"}


CLASSES = (CHROMA3D_OT_export_analysis_report,)
