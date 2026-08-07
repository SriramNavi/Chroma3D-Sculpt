"""In-memory Sprint 7 session ownership and legal state transitions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..models.ai_assistance_models import (
    ApprovalRecord, AssistanceSession, AssistanceState, deterministic_id, stable_hash,
)
from .provider_transport import CancellationToken


class AssistanceStateError(RuntimeError):
    pass


LEGAL_TRANSITIONS: dict[AssistanceState, frozenset[AssistanceState]] = {
    AssistanceState.INITIAL: frozenset({AssistanceState.LOADING}),
    AssistanceState.LOADING: frozenset({AssistanceState.READY, AssistanceState.FAILED}),
    AssistanceState.READY: frozenset({AssistanceState.ANALYZING, AssistanceState.CANCELLED, AssistanceState.FAILED}),
    AssistanceState.ANALYZING: frozenset({AssistanceState.EVIDENCE_AVAILABLE, AssistanceState.CANCELLING, AssistanceState.FAILED}),
    AssistanceState.CANCELLING: frozenset({AssistanceState.CANCELLED, AssistanceState.RESTORED}),
    AssistanceState.EVIDENCE_AVAILABLE: frozenset({AssistanceState.STALE, AssistanceState.PREVIEWING, AssistanceState.DISCARDED, AssistanceState.EXPORTED, AssistanceState.ACCEPTED, AssistanceState.CANCELLED}),
    AssistanceState.PREVIEWING: frozenset({AssistanceState.APPROVAL_REQUIRED, AssistanceState.STALE, AssistanceState.FAILED, AssistanceState.CANCELLED}),
    AssistanceState.APPROVAL_REQUIRED: frozenset({AssistanceState.EXECUTING, AssistanceState.DISCARDED, AssistanceState.STALE, AssistanceState.CANCELLING, AssistanceState.CANCELLED}),
    AssistanceState.EXECUTING: frozenset({AssistanceState.EVIDENCE_AVAILABLE, AssistanceState.CANCELLING, AssistanceState.RESTORED, AssistanceState.FAILED}),
    AssistanceState.RESTORED: frozenset({AssistanceState.EXPORTED, AssistanceState.DISCARDED}),
    AssistanceState.STALE: frozenset({AssistanceState.LOADING, AssistanceState.EXPORTED, AssistanceState.DISCARDED}),
    AssistanceState.ACCEPTED: frozenset({AssistanceState.EXPORTED, AssistanceState.FINALIZED}),
    AssistanceState.DISCARDED: frozenset({AssistanceState.EXPORTED, AssistanceState.FINALIZED}),
    AssistanceState.EXPORTED: frozenset({AssistanceState.FINALIZED}),
    AssistanceState.CANCELLED: frozenset({AssistanceState.EXPORTED, AssistanceState.FINALIZED}),
    AssistanceState.FAILED: frozenset({AssistanceState.READY, AssistanceState.EXPORTED, AssistanceState.FINALIZED}),
    AssistanceState.FINALIZED: frozenset(),
}


_active: AssistanceSession | None = None
_archived: AssistanceSession | None = None
_tokens: dict[str, CancellationToken] = {}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session(*, source_identity: dict[str, Any], source_signature_hash: str) -> AssistanceSession:
    global _active
    if _active is not None and _active.state not in {AssistanceState.FINALIZED, AssistanceState.ACCEPTED, AssistanceState.DISCARDED, AssistanceState.CANCELLED, AssistanceState.FAILED, AssistanceState.EXPORTED, AssistanceState.RESTORED, AssistanceState.STALE}:
        raise AssistanceStateError("An AI assistance session is already active.")
    created = now_utc()
    identity = {"source_signature_hash": source_signature_hash, "created_nonce": created}
    _active = AssistanceSession(
        session_id=deterministic_id("assistance", identity), created_at=created, updated_at=created,
        state=AssistanceState.INITIAL, source_identity=dict(source_identity), source_signature_hash=source_signature_hash,
        limitations=["Advisory-only AI assistance; no print-success, geometry-correctness, or global-optimum guarantee."],
    )
    _tokens[_active.session_id] = CancellationToken()
    return _active


def get_active_session() -> AssistanceSession | None:
    return _active


def get_archived_session() -> AssistanceSession | None:
    return _archived


def cancellation_token(session: AssistanceSession | None = None) -> CancellationToken:
    active = session or _active
    if active is None:
        raise AssistanceStateError("No active AI assistance session.")
    return _tokens.setdefault(active.session_id, CancellationToken())


def transition(session: AssistanceSession, target: AssistanceState | str, *, event: str, detail: dict[str, Any] | None = None) -> AssistanceSession:
    destination = AssistanceState(target)
    current = AssistanceState(session.state)
    if destination not in LEGAL_TRANSITIONS[current]:
        raise AssistanceStateError(f"Illegal AI assistance transition: {current.value} -> {destination.value}.")
    session.state = destination
    session.updated_at = now_utc()
    session.audit_history.append({"at": session.updated_at, "event": event, "from": current.value, "to": destination.value, "detail": dict(detail or {})})
    return session


def invalidate(session: AssistanceSession, reason: str) -> None:
    if session.state not in {AssistanceState.EVIDENCE_AVAILABLE, AssistanceState.PREVIEWING, AssistanceState.APPROVAL_REQUIRED}:
        raise AssistanceStateError("Only derived recommendation state can become stale.")
    if AssistanceState.STALE not in LEGAL_TRANSITIONS[AssistanceState(session.state)]:
        raise AssistanceStateError("Current state cannot transition to stale.")
    session.stale_reasons.append(reason)
    session.preview = None
    session.approval = ApprovalRecord()
    transition(session, AssistanceState.STALE, event="BOUND_STATE_CHANGED", detail={"reason": reason})


def approval_scope_hash(session: AssistanceSession) -> str:
    return stable_hash({
        "session_id": session.session_id, "source": session.source_signature_hash,
        "context": session.context_hash, "policy": session.policy_hash,
        "provider": session.provider_settings_hash, "recommendation": session.selected_recommendation_id,
        "preview": session.preview,
    })


def approve_current_preview(session: AssistanceSession) -> ApprovalRecord:
    if session.state != AssistanceState.APPROVAL_REQUIRED or not session.preview or not session.selected_recommendation_id:
        raise AssistanceStateError("A current preview and selected recommendation are required before approval.")
    session.approval = ApprovalRecord(required=True, approved=True, scope_hash=approval_scope_hash(session), approved_at=now_utc())
    session.audit_history.append({"at": session.approval.approved_at, "event": "EXPLICIT_EXECUTION_APPROVAL", "scope_hash": session.approval.scope_hash, "recommendation_id": session.selected_recommendation_id})
    return session.approval


def request_cancellation(session: AssistanceSession) -> None:
    if session.cancellation_requested:
        return
    session.cancellation_requested = True
    cancellation_token(session).cancel()
    session.approval = ApprovalRecord()
    session.audit_history.append({"at": now_utc(), "event": "CANCELLATION_REQUESTED", "state": session.state.value})


def archive_session(session: AssistanceSession) -> None:
    global _active, _archived
    _archived = session
    if _active is session:
        _active = None
    _tokens.pop(session.session_id, None)


def clear_runtime() -> None:
    global _active, _archived
    for token in _tokens.values():
        token.cancel()
    _tokens.clear()
    _active = None
    _archived = None


__all__ = (
    "AssistanceStateError", "LEGAL_TRANSITIONS", "approval_scope_hash", "approve_current_preview",
    "archive_session", "cancellation_token", "clear_runtime", "create_session", "get_active_session",
    "get_archived_session", "invalidate", "now_utc", "request_cancellation", "transition",
)
