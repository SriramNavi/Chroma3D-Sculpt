"""Explicit Blender operators for Sprint 7 AI recommendation assistance."""

from __future__ import annotations

import bpy
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper

from ..ai_assistance_settings import default_assistance_policy
from ..models.ai_assistance_models import AssistanceState
from ..services.ai_assistance_audit import build_audit, write_json_audit, write_markdown_audit
from ..services.ai_assistance_coordinator import (
    accept_copy, approve_context_consent, approve_preview, cancel, context_for, discard,
    execute_approved, offline_fallback, preview_selected, provider_settings,
    request_recommendations, select_recommendation, start_assistance,
)
from ..services.ai_assistance_report import build_report, write_json_report, write_markdown_report
from ..services.ai_assistance_session import get_active_session, get_archived_session
from ..services.ai_credentials import clear_session_key, credential_status, set_session_key


def _sync(context: bpy.types.Context, message: str = "") -> None:
    ui = context.window_manager.chroma3d_sculpt_state
    session = get_active_session() or get_archived_session()
    ui.ai_assistance_has_session = session is not None
    ui.ai_assistance_state = session.state.value if session else AssistanceState.INITIAL.value
    ui.ai_assistance_recommendation_count = len(session.recommendations) if session else 0
    ui.ai_assistance_selected_recommendation_id = session.selected_recommendation_id if session else ""
    if message:
        ui.ai_assistance_last_result = message[:1024]


class CHROMA3D_OT_set_ai_session_key(bpy.types.Operator):
    bl_idname = "chroma3d.set_ai_session_key"
    bl_label = "Set Session-only API Key"
    bl_description = "Hold a key only in process memory for this Blender session; never save it in the blend file or reports"
    key_value: StringProperty(name="API Key", subtype="PASSWORD", maxlen=512, options={"SKIP_SAVE"})

    def invoke(self, context, _event):
        self.key_value = ""
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        try:
            set_session_key(self.key_value)
            self.key_value = ""
            _sync(context, "Session-only key configured; the value was not persisted.")
            return {"FINISHED"}
        except Exception as exc:
            self.key_value = ""
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class CHROMA3D_OT_clear_ai_session_key(bpy.types.Operator):
    bl_idname = "chroma3d.clear_ai_session_key"
    bl_label = "Clear Session Key"

    def execute(self, context):
        clear_session_key()
        _sync(context, "Session-only key cleared.")
        return {"FINISHED"}


class CHROMA3D_OT_start_ai_assistance(bpy.types.Operator):
    bl_idname = "chroma3d.start_ai_assistance"
    bl_label = "Prepare Bounded Context"
    bl_description = "Build a local allow-listed context manifest; this action makes no network request"

    def execute(self, context):
        ui = context.window_manager.chroma3d_sculpt_state
        if not ui.ai_assistance_enabled:
            self.report({"ERROR"}, "Enable AI Assistance first; offline Sprint 6 remains available.")
            return {"CANCELLED"}
        try:
            start_assistance(user_goal=ui.ai_assistance_user_goal, mode=ui.ai_assistance_mode, policy=default_assistance_policy(enabled=True))
            _sync(context, "Bounded context prepared locally. Review the disclosure and consent before requesting.")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            _sync(context, str(exc))
            return {"CANCELLED"}


class CHROMA3D_OT_consent_ai_context(bpy.types.Operator):
    bl_idname = "chroma3d.consent_ai_context"
    bl_label = "Approve Disclosed Context"

    def execute(self, context):
        ui = context.window_manager.chroma3d_sculpt_state
        if not ui.ai_assistance_consent:
            self.report({"ERROR"}, "Tick the explicit disclosure consent checkbox first.")
            return {"CANCELLED"}
        try:
            approve_context_consent()
            provider_settings(provider_id=ui.ai_assistance_provider, model_id=ui.ai_assistance_model_id)
            _sync(context, "Consent recorded and bound to the exact context, destination, provider and model.")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class CHROMA3D_OT_test_ai_configuration(bpy.types.Operator):
    bl_idname = "chroma3d.test_ai_configuration"
    bl_label = "Validate Configuration Locally"
    bl_description = "Validate provider/model/key presence locally without making a network request"

    def execute(self, context):
        ui = context.window_manager.chroma3d_sculpt_state
        try:
            provider_settings(provider_id=ui.ai_assistance_provider, model_id=ui.ai_assistance_model_id)
            status = credential_status()
            if not status["configured"]:
                raise RuntimeError("No OpenAI key is configured. Offline fallback remains available.")
            _sync(context, f"Local configuration valid; credential source: {status['source']} (no request sent).")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class CHROMA3D_OT_request_ai_recommendations(bpy.types.Operator):
    bl_idname = "chroma3d.request_ai_recommendations"
    bl_label = "Request Recommendations"
    bl_description = "Make one explicit consented external request; zero automatic retries"

    def execute(self, context):
        try:
            values = request_recommendations()
            _sync(context, f"Validated {len(values)} advisory recommendation(s); no geometry changed.")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            _sync(context, str(exc))
            return {"CANCELLED"}


class CHROMA3D_OT_retry_ai_recommendations(bpy.types.Operator):
    bl_idname = "chroma3d.retry_ai_recommendations"
    bl_label = "Retry Once Explicitly"
    bl_description = "Make the one allowed explicit retry; no retry occurs automatically"

    def execute(self, context):
        try:
            values = request_recommendations(explicit_retry=True)
            _sync(context, f"Validated {len(values)} recommendation(s) on the explicit retry.")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            _sync(context, str(exc))
            return {"CANCELLED"}


class CHROMA3D_OT_ai_offline_fallback(bpy.types.Operator):
    bl_idname = "chroma3d.ai_offline_fallback"
    bl_label = "Show Deterministic Offline Ranking"

    def execute(self, context):
        try:
            values = offline_fallback()
            _sync(context, f"Showing {len(values)} deterministic Sprint 6 fallback item(s); no provider was used.")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class CHROMA3D_OT_select_ai_recommendation(bpy.types.Operator):
    bl_idname = "chroma3d.select_ai_recommendation"
    bl_label = "Select Recommendation"
    recommendation_id: StringProperty(name="Recommendation ID")

    def execute(self, context):
        try:
            select_recommendation(self.recommendation_id)
            _sync(context, "Recommendation selected for review; no preview or execution occurred.")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class CHROMA3D_OT_preview_ai_recommendation(bpy.types.Operator):
    bl_idname = "chroma3d.preview_ai_recommendation"
    bl_label = "Preview Through Protected Workspace"

    def execute(self, context):
        try:
            preview_selected()
            _sync(context, "Current target previewed; separate fresh approval is now required.")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            _sync(context, str(exc))
            return {"CANCELLED"}


class CHROMA3D_OT_approve_ai_execution(bpy.types.Operator):
    bl_idname = "chroma3d.approve_ai_execution"
    bl_label = "Approve This Previewed Plan"
    bl_description = "Bind explicit approval to the current source, context, policy, recommendation and preview"

    def execute(self, context):
        try:
            approve_preview()
            _sync(context, "Fresh approval recorded for this exact preview. Use Execute Approved Plan as a separate action.")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class CHROMA3D_OT_execute_ai_approved(bpy.types.Operator):
    bl_idname = "chroma3d.execute_ai_approved"
    bl_label = "Execute Approved Plan"
    bl_description = "Delegate the approved current target to the existing checkpointed Sprint 5/6 workflow"

    def execute(self, context):
        try:
            values = execute_approved(source=context.active_object, blend_file_path=bpy.data.filepath)
            _sync(context, f"Delegated {len(values)} operation(s); review comparison before accept/discard.")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            _sync(context, str(exc))
            return {"CANCELLED"}


class CHROMA3D_OT_cancel_ai_assistance(bpy.types.Operator):
    bl_idname = "chroma3d.cancel_ai_assistance"
    bl_label = "Cancel Assistance"

    def execute(self, context):
        try:
            cancel(); _sync(context, "Cancellation recorded; late output cannot become actionable.")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc)); return {"CANCELLED"}


class CHROMA3D_OT_accept_ai_copy(bpy.types.Operator):
    bl_idname = "chroma3d.accept_ai_copy"
    bl_label = "Accept Separate Copy"

    def execute(self, context):
        try:
            accepted = accept_copy(blend_file_path=bpy.data.filepath); _sync(context, f"Accepted separate copy: {accepted.name}")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc)); return {"CANCELLED"}


class CHROMA3D_OT_discard_ai_workspace(bpy.types.Operator):
    bl_idname = "chroma3d.discard_ai_workspace"
    bl_label = "Reject / Discard Owned Workspace"

    def execute(self, context):
        try:
            discard(blend_file_path=bpy.data.filepath); _sync(context, "Rejected and discarded session-owned workspace only.")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc)); return {"CANCELLED"}


class _ExportBase:
    filter_glob: StringProperty(default="*.*", options={"HIDDEN"})
    kind = "report"
    markdown = False

    def execute(self, context):
        session = get_active_session() or get_archived_session()
        if session is None:
            return {"CANCELLED"}
        try:
            ctx = context_for(session)
            if self.kind == "audit":
                value = build_audit(session, ctx)
                (write_markdown_audit if self.markdown else write_json_audit)(value, self.filepath)
            else:
                value = build_report(session, ctx)
                (write_markdown_report if self.markdown else write_json_report)(value, self.filepath)
            _sync(context, f"Redacted {self.kind} exported.")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc)); return {"CANCELLED"}


class CHROMA3D_OT_export_ai_report_json(_ExportBase, bpy.types.Operator, ExportHelper):
    bl_idname = "chroma3d.export_ai_report_json"; bl_label = "Export Report JSON"; filename_ext = ".json"; filter_glob: StringProperty(default="*.json", options={"HIDDEN"})


class CHROMA3D_OT_export_ai_report_markdown(_ExportBase, bpy.types.Operator, ExportHelper):
    bl_idname = "chroma3d.export_ai_report_markdown"; bl_label = "Export Report Markdown"; filename_ext = ".md"; filter_glob: StringProperty(default="*.md", options={"HIDDEN"}); markdown = True


class CHROMA3D_OT_export_ai_audit_json(_ExportBase, bpy.types.Operator, ExportHelper):
    bl_idname = "chroma3d.export_ai_audit_json"; bl_label = "Export Audit JSON"; filename_ext = ".json"; filter_glob: StringProperty(default="*.json", options={"HIDDEN"}); kind = "audit"


CLASSES = (
    CHROMA3D_OT_set_ai_session_key, CHROMA3D_OT_clear_ai_session_key, CHROMA3D_OT_start_ai_assistance,
    CHROMA3D_OT_consent_ai_context, CHROMA3D_OT_test_ai_configuration, CHROMA3D_OT_request_ai_recommendations,
    CHROMA3D_OT_retry_ai_recommendations,
    CHROMA3D_OT_ai_offline_fallback, CHROMA3D_OT_select_ai_recommendation, CHROMA3D_OT_preview_ai_recommendation,
    CHROMA3D_OT_approve_ai_execution, CHROMA3D_OT_execute_ai_approved, CHROMA3D_OT_cancel_ai_assistance,
    CHROMA3D_OT_accept_ai_copy, CHROMA3D_OT_discard_ai_workspace, CHROMA3D_OT_export_ai_report_json,
    CHROMA3D_OT_export_ai_report_markdown, CHROMA3D_OT_export_ai_audit_json,
)
