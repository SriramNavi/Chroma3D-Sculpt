"""Bounded redacted Sprint 7 user report construction and export."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from uuid import uuid4
from typing import Any

from ..metadata import DISPLAY_VERSION
from ..models.ai_assistance_models import AI_ASSISTANCE_SCHEMA_VERSION, AssistanceReport, AssistanceSession, ContextManifest, deterministic_id, plain_value
from .context_redaction import sanitize_text
from .recommendation_explainer import recommendation_markdown


_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
_SECRET_KEY = re.compile(r"(?i)(?:api.?key|authorization|credential|password|secret|token)")
_RAW_KEY = re.compile(r"(?i)(?:vertices|edges|faces|polygons|coordinates|raw.?geometry|blend.?file|object.?identity|mesh.?identity)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(value: Any, path: str = "report") -> Any:
    value = plain_value(value)
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if _SECRET_KEY.search(key) or _RAW_KEY.search(key):
                continue
            result[key] = _safe(item, f"{path}.{key}")
        return result
    if isinstance(value, list):
        return [_safe(item, f"{path}[]") for item in value]
    if isinstance(value, str):
        return sanitize_text(value, maximum=4096, label=path)[0]
    return value


def build_report(session: AssistanceSession, context: ContextManifest) -> AssistanceReport:
    session_summary = {
        "session_id": session.session_id, "created_at": session.created_at, "updated_at": session.updated_at,
        "state": session.state.value, "context_id": session.context_identity,
        "cancellation_requested": session.cancellation_requested, "provider_attempts": session.provider_attempts,
    }
    stale = tuple(item for item in session.audit_history if item.get("event") == "BOUND_STATE_CHANGED")
    cancelled = tuple(item for item in session.audit_history if "CANCEL" in str(item.get("event", "")))
    payload = {
        "session": session_summary, "context_hash": context.context_hash,
        "recommendations": [item.to_dict() for item in session.recommendations],
        "selected": session.selected_recommendation_id,
    }
    return AssistanceReport(
        schema_version=AI_ASSISTANCE_SCHEMA_VERSION, extension_version=DISPLAY_VERSION, exported_at=_now(),
        report_id=deterministic_id("assistance-report", payload), session=_safe(session_summary),
        source_identity={"safe_display_name": context.object_safe_display_name, "source_signature_hash": context.source_signature_hash},
        policy_hash=session.policy_hash,
        context=_safe({
            "context_id": context.context_id, "context_hash": context.context_hash, "byte_count": context.byte_count, "token_estimate": context.token_estimate,
            "included_categories": context.included_categories, "omitted_categories": context.omitted_categories,
            "redaction_record": context.redaction_record, "truncation_record": context.truncation_record,
            "consent": context.consent.to_dict(), "geometry_elements_exported": 0,
        }),
        provider_exchange=_safe(session.exchange.to_dict()) if session.exchange else None,
        recommendations=tuple(_safe(item.to_dict()) for item in session.recommendations),
        selected_recommendation_id=session.selected_recommendation_id, preview=_safe(session.preview) if session.preview else None,
        approval=_safe(session.approval.to_dict()), stale_events=tuple(_safe(item) for item in stale),
        cancellation_events=tuple(_safe(item) for item in cancelled), failures=tuple(_safe(item) for item in session.failures),
        warnings=(), limitations=tuple(session.limitations),
        disclaimers=("Advisory only; the user remains responsible for the final decision.", "No geometry-correctness, global-optimum, printability, manufacturing, or physical-print guarantee is made."),
    )


def validate_export_path(path: str | Path, suffix: str) -> Path:
    raw = str(path)
    if "\x00" in raw or not raw or len(raw) > 4096:
        raise ValueError("Export path is invalid.")
    if raw.startswith(("\\\\", "//")):
        raise ValueError("Network and UNC export paths are not allowed.")
    candidate = Path(raw)
    if not candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        raise ValueError("Export must use an explicit absolute user-selected path without traversal.")
    if candidate.suffix.lower() != suffix or candidate.stem.upper() in _RESERVED:
        raise ValueError(f"Export filename must be a safe {suffix} filename.")
    if not candidate.parent.exists() or not candidate.parent.is_dir():
        raise ValueError("Export destination folder does not exist.")
    return candidate


def _atomic_write(destination: Path, encoded: bytes) -> Path:
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(encoded)
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


def write_json_report(report: AssistanceReport, path: str | Path, *, maximum_bytes: int = 1_048_576) -> Path:
    destination = validate_export_path(path, ".json")
    encoded = report.to_json().encode("utf-8")
    if len(encoded) > maximum_bytes:
        raise ValueError("Report exceeds the configured size limit.")
    return _atomic_write(destination, encoded)


def write_markdown_report(report: AssistanceReport, path: str | Path, *, maximum_bytes: int = 1_048_576) -> Path:
    destination = validate_export_path(path, ".md")
    lines = [
        "# Chroma3D Sculpt AI Recommendation Report", "",
        f"- Extension: `{report.extension_version}`", f"- Schema: `{report.schema_version}`",
        f"- State: `{report.session['state']}`", f"- Source signature: `{report.source_identity['source_signature_hash']}`",
        f"- Context: `{report.context['context_hash']}`", f"- Policy: `{report.policy_hash}`",
        f"- Selected recommendation: `{report.selected_recommendation_id or 'none'}`", "", "## Recommendations", "",
    ]
    for item in report.recommendations:
        lines.extend((f"### {item['recommendation_type']}", "", str(item["reason"]), "", f"- Confidence: `{item['confidence']}`", f"- Target: `{item.get('target_id') or 'none'}`", f"- Action available: `{item['action_available']}`", ""))
        lines.extend(f"- Limitation: {value}" for value in item.get("limitations", ()))
        lines.append("")
    lines.extend(("## Disclaimers", ""))
    lines.extend(f"- {item}" for item in report.disclaimers)
    encoded = ("\n".join(lines) + "\n").encode("utf-8")
    if len(encoded) > maximum_bytes:
        raise ValueError("Report exceeds the configured size limit.")
    return _atomic_write(destination, encoded)


__all__ = ("build_report", "validate_export_path", "write_json_report", "write_markdown_report")
