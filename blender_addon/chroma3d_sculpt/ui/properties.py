"""Small UI-safe scalar state; complete reports stay in the session cache."""

import bpy
from bpy.props import BoolProperty, StringProperty

from ..models.analysis_result import AnalysisResult


class CHROMA3D_PG_session_state(bpy.types.PropertyGroup):
    has_analysis: BoolProperty(name="Has analysis", default=False, options={"HIDDEN"})
    analyzed_object_name: StringProperty(name="Analyzed object", default="", options={"HIDDEN"})
    severity: StringProperty(name="Severity", default="", options={"HIDDEN"})
    last_analysis: StringProperty(name="Last analysis", default="", options={"HIDDEN"})


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
