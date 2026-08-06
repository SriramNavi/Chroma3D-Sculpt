"""Complete redacted Sprint 7 audit projection."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..metadata import DISPLAY_VERSION
from ..models.ai_assistance_models import AI_ASSISTANCE_SCHEMA_VERSION, AssistanceAudit, AssistanceSession, ContextManifest, deterministic_id
from .ai_assistance_report import _atomic_write, _safe, validate_export_path


def build_audit(session: AssistanceSession, context: ContextManifest) -> AssistanceAudit:
    now = datetime.now(timezone.utc).isoformat()
    stale = tuple(item for item in session.audit_history if item.get("event") == "BOUND_STATE_CHANGED")
    cancelled = tuple(item for item in session.audit_history if "CANCEL" in str(item.get("event", "")))
    operations = tuple(item for item in session.audit_history if str(item.get("event", "")).startswith("DELEGATED_EXECUTION"))
    recovery = tuple(item for item in session.audit_history if "RESTOR" in str(item.get("event", "")))
    cleanup = tuple(item for item in session.audit_history if "DISCARD" in str(item.get("event", "")))
    selection = next((item for item in reversed(session.audit_history) if item.get("event") == "RECOMMENDATION_SELECTED"), None)
    payload = {"session_id": session.session_id, "context_hash": context.context_hash, "history": session.audit_history}
    return AssistanceAudit(
        schema_version=AI_ASSISTANCE_SCHEMA_VERSION, extension_version=DISPLAY_VERSION, exported_at=now,
        audit_id=deterministic_id("assistance-audit", payload),
        session=_safe({"session_id": session.session_id, "state": session.state.value, "history": session.audit_history}),
        consent=_safe(context.consent.to_dict()),
        context=_safe({"context_id": context.context_id, "context_hash": context.context_hash, "byte_count": context.byte_count, "token_estimate": context.token_estimate, "included_categories": context.included_categories, "omitted_categories": context.omitted_categories, "redaction_record": context.redaction_record, "truncation_record": context.truncation_record, "geometry_elements_exported": 0}),
        provider_exchange=_safe(session.exchange.to_dict()) if session.exchange else None,
        validation=tuple(_safe(item) for item in session.audit_history if "VALID" in str(item.get("event", ""))),
        recommendations=tuple(_safe(item.to_dict()) for item in session.recommendations), selection=_safe(selection) if selection else None,
        preview=_safe(session.preview) if session.preview else None, approval=_safe(session.approval.to_dict()),
        operations=tuple(_safe(item) for item in operations), stale_events=tuple(_safe(item) for item in stale),
        cancellation_events=tuple(_safe(item) for item in cancelled), failures=tuple(_safe(item) for item in session.failures),
        recovery=tuple(_safe(item) for item in recovery), cleanup=tuple(_safe(item) for item in cleanup),
        usage=_safe({"classification": session.exchange.usage_classification if session.exchange else "UNAVAILABLE", "input_units": session.exchange.input_units if session.exchange else None, "output_units": session.exchange.output_units if session.exchange else None, "currency_cost": "NOT_CALCULATED"}),
        warnings=(), limitations=tuple(session.limitations),
        disclaimers=("No raw prompt, provider response, credential, geometry, Blender reference, or developer path is retained.", "Software evidence only; slicer, manufacturing and physical printing are not inferred."),
    )


def write_json_audit(audit: AssistanceAudit, path: str | Path, *, maximum_bytes: int = 1_048_576) -> Path:
    destination = validate_export_path(path, ".json")
    encoded = audit.to_json().encode("utf-8")
    if len(encoded) > maximum_bytes:
        raise ValueError("Audit exceeds the configured size limit.")
    return _atomic_write(destination, encoded)


def write_markdown_audit(audit: AssistanceAudit, path: str | Path, *, maximum_bytes: int = 1_048_576) -> Path:
    destination = validate_export_path(path, ".md")
    lines = ["# Chroma3D Sculpt AI Assistance Audit", "", f"- Extension: `{audit.extension_version}`", f"- Schema: `{audit.schema_version}`", f"- Session: `{audit.session['session_id']}`", f"- State: `{audit.session['state']}`", f"- Context: `{audit.context['context_hash']}`", "", "## Audit events", ""]
    lines.extend(f"- `{item.get('at', '')}` {item.get('event', '')}" for item in audit.session.get("history", ()))
    lines.extend(("", "## Limitations", ""))
    lines.extend(f"- {item}" for item in audit.limitations)
    lines.extend(("", "## Disclaimers", ""))
    lines.extend(f"- {item}" for item in audit.disclaimers)
    encoded = ("\n".join(lines) + "\n").encode("utf-8")
    if len(encoded) > maximum_bytes:
        raise ValueError("Audit exceeds the configured size limit.")
    return _atomic_write(destination, encoded)


__all__ = ("build_audit", "write_json_audit", "write_markdown_audit")
