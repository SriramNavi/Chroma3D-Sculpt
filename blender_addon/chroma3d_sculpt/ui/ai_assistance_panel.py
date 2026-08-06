"""Collapsed Sprint 7 AI Recommendation panel below Intelligent Optimization."""

from __future__ import annotations

import bpy

from ..models.ai_assistance_models import AssistanceState
from ..services.ai_assistance_coordinator import context_for
from ..services.ai_assistance_session import get_active_session, get_archived_session
from ..services.ai_credentials import credential_status


class CHROMA3D_PT_ai_assistance(bpy.types.Panel):
    bl_label = "AI Recommendation (Optional)"
    bl_idname = "CHROMA3D_PT_ai_assistance"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Chroma3D"
    bl_parent_id = "CHROMA3D_PT_intelligent_optimization"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        ui = context.window_manager.chroma3d_sculpt_state
        session = get_active_session() or get_archived_session()
        credentials = credential_status()

        setup = layout.box()
        setup.label(text="Optional external assistance", icon="INFO")
        setup.prop(ui, "ai_assistance_enabled")
        setup.prop(ui, "ai_assistance_mode")
        setup.prop(ui, "ai_assistance_user_goal")
        setup.prop(ui, "ai_assistance_provider")
        setup.prop(ui, "ai_assistance_model_id")
        setup.label(text=f"Credential: {credentials['source']}")
        row = setup.row(align=True)
        row.operator("chroma3d.set_ai_session_key", text="Set Session Key")
        row.operator("chroma3d.clear_ai_session_key", text="Clear")
        setup.operator("chroma3d.start_ai_assistance", text="Prepare Bounded Context")
        setup.label(text="No network activity occurs until Request Recommendations.", icon="LOCKED")

        if session is None:
            setup.label(text="Sprint 6 remains fully available offline.")
            return

        status = layout.box()
        status.label(text=f"State: {session.state.value}", icon="TIME")
        status.label(text=ui.ai_assistance_last_result[:120] or "No result yet.")
        if session.state == AssistanceState.STALE:
            status.label(text="Stale: refresh context and request again.", icon="ERROR")
        if session.failures:
            status.label(text=f"Failure: {session.failures[-1].get('failure_class', 'FAILED')}", icon="ERROR")
        if session.state == AssistanceState.FAILED and session.provider_attempts == 1:
            status.operator("chroma3d.retry_ai_recommendations", text="Retry Once Explicitly")
            status.label(text="No automatic retry or provider switch occurs.")

        if session.state == AssistanceState.READY:
            disclosure = layout.box()
            disclosure.label(text="External request disclosure", icon="WORLD")
            try:
                manifest = context_for(session)
                disclosure.label(text=f"Destination: {manifest.consent.destination}")
                disclosure.label(text=f"Purpose: {manifest.consent.purpose[:100]}")
                disclosure.label(text=f"Included: {', '.join(manifest.included_categories)[:120]}")
                disclosure.label(text="Excluded: geometry, files, paths, credentials, images, logs")
                disclosure.label(text=f"Context: {manifest.byte_count} bytes (~{manifest.token_estimate} tokens); records: {len(manifest.evidence)}")
                disclosure.label(text=manifest.consent.retention_disclosure[:120])
                disclosure.label(text=manifest.consent.cost_disclosure[:120])
            except RuntimeError:
                disclosure.label(text="Context unavailable.", icon="ERROR")
            disclosure.prop(ui, "ai_assistance_consent")
            disclosure.operator("chroma3d.consent_ai_context", text="Bind Consent to This Context")
            disclosure.operator("chroma3d.test_ai_configuration", text="Validate Configuration Locally")
            row = disclosure.row(align=True)
            row.operator("chroma3d.request_ai_recommendations", text="Request Recommendations")
            row.operator("chroma3d.ai_offline_fallback", text="Offline Sprint 6 View")

        if session.recommendations:
            results = layout.box()
            results.label(text=f"Validated recommendations: {len(session.recommendations)}", icon="QUESTION")
            for item in session.recommendations:
                box = results.box()
                box.label(text=f"{item.recommendation_type.value}: {item.confidence.value}")
                box.label(text=item.reason[:120])
                if item.assumptions:
                    box.label(text=f"Assumption: {item.assumptions[0][:100]}")
                box.label(text=f"Target: {item.target_id or 'none'}")
                if item.provider_exchange_id:
                    box.label(text=f"Exchange: {item.provider_exchange_id[:48]}")
                box.label(text=f"Provider generated: {'yes' if item.provider_generated else 'no'}")
                box.label(text=f"Action available: {'yes' if item.action_available else 'no'}")
                for limitation in item.limitations[:2]:
                    box.label(text=f"Limitation: {limitation[:100]}", icon="ERROR")
                op = box.operator("chroma3d.select_ai_recommendation", text="Select for Review")
                op.recommendation_id = item.recommendation_id

        actions = layout.box()
        actions.label(text="Preview and separate approval", icon="LOCKED")
        preview_row = actions.row()
        preview_row.enabled = bool(session.selected_recommendation_id) and session.state == AssistanceState.EVIDENCE_AVAILABLE
        preview_row.operator("chroma3d.preview_ai_recommendation")
        approve_row = actions.row()
        approve_row.enabled = session.state == AssistanceState.APPROVAL_REQUIRED and not session.approval.approved
        approve_row.operator("chroma3d.approve_ai_execution")
        execute_row = actions.row()
        execute_row.enabled = session.state == AssistanceState.APPROVAL_REQUIRED and session.approval.approved
        execute_row.operator("chroma3d.execute_ai_approved")
        actions.label(text="Preview never authorizes execution by itself.", icon="ERROR")

        finalize = layout.box()
        finalize.label(text="Review, export, and cleanup")
        row = finalize.row(align=True)
        row.operator("chroma3d.accept_ai_copy")
        row.operator("chroma3d.discard_ai_workspace")
        row = finalize.row(align=True)
        row.operator("chroma3d.export_ai_report_json")
        row.operator("chroma3d.export_ai_report_markdown")
        finalize.operator("chroma3d.export_ai_audit_json")
        finalize.operator("chroma3d.cancel_ai_assistance")
        finalize.label(text="Advisory only; no print or global-optimum guarantee.", icon="ERROR")


CLASSES = (CHROMA3D_PT_ai_assistance,)
