"""Explicit issue-inspection operator; selection state may change, geometry may not."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty

from ..models.analysis_result import IssueCategory, IssueDomain
from ..session import get_result
from ..utilities.context import is_valid_mesh_object
from ..utilities.signatures import is_topology_signature_current


_CATEGORY_ITEMS = tuple(
    (category.value, category.value.replace("_", " ").title(), f"Select stored {category.value.lower()} evidence")
    for category in IssueCategory
)


class CHROMA3D_OT_select_diagnostic_issue(bpy.types.Operator):
    bl_idname = "chroma3d.select_diagnostic_issue"
    bl_label = "Select Diagnostic Issue"
    bl_description = "Select bounded issue evidence from the latest non-stale analysis"
    bl_options = {"REGISTER", "UNDO"}

    issue_category: EnumProperty(name="Issue", items=_CATEGORY_ITEMS)
    additive: BoolProperty(name="Add to Selection", default=False)

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        obj = getattr(context, "active_object", None)
        return is_valid_mesh_object(obj) and get_result(obj) is not None

    def execute(self, context: bpy.types.Context) -> set[str]:
        obj = getattr(context, "active_object", None)
        result = get_result(obj)
        if obj is None or result is None:
            self.report({"ERROR"}, "Run Analyze Mesh on the active object first.")
            return {"CANCELLED"}
        if not is_topology_signature_current(obj, result.topology_signature):
            self.report({"ERROR"}, "Analysis is stale. Run Analyze Mesh again.")
            return {"CANCELLED"}
        try:
            category = IssueCategory(self.issue_category)
        except ValueError:
            self.report({"ERROR"}, "The requested issue category is invalid.")
            return {"CANCELLED"}
        evidence = next((item for item in result.issue_evidence if item.category == category), None)
        if evidence is None or not evidence.indices:
            self.report({"WARNING"}, "No stored issue indices are available for this category.")
            return {"CANCELLED"}
        if evidence.domain == IssueDomain.SHELL:
            self.report({"ERROR"}, "Shell-only evidence cannot be selected as mesh elements.")
            return {"CANCELLED"}

        mesh = obj.data
        try:
            if obj.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            if not self.additive:
                for vertex in mesh.vertices:
                    vertex.select = False
                for edge in mesh.edges:
                    edge.select = False
                for polygon in mesh.polygons:
                    polygon.select = False
            collection = {
                IssueDomain.VERTEX: mesh.vertices,
                IssueDomain.EDGE: mesh.edges,
                IssueDomain.FACE: mesh.polygons,
            }[evidence.domain]
            selected = 0
            for index in evidence.indices:
                if 0 <= index < len(collection):
                    collection[index].select = True
                    selected += 1
            context.tool_settings.mesh_select_mode = {
                IssueDomain.VERTEX: (True, False, False),
                IssueDomain.EDGE: (False, True, False),
                IssueDomain.FACE: (False, False, True),
            }[evidence.domain]
            bpy.ops.object.mode_set(mode="EDIT")
        except (RuntimeError, TypeError, AttributeError) as exc:
            self.report({"ERROR"}, f"Could not select diagnostic evidence: {exc}")
            return {"CANCELLED"}
        if selected == 0:
            self.report({"WARNING"}, "Stored evidence contained no valid current mesh indices.")
            return {"CANCELLED"}
        suffix = " Evidence is truncated to the configured cap." if evidence.truncated else ""
        self.report({"INFO"}, f"Selected {selected} {evidence.domain.value.lower()} item(s).{suffix}")
        return {"FINISHED"}


CLASSES = (CHROMA3D_OT_select_diagnostic_issue,)
