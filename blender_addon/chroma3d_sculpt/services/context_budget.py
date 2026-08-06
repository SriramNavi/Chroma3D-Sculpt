"""Deterministic Sprint 7 context-count and byte budgeting."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from ..models.ai_assistance_models import EvidenceReference, EvidenceState, canonical_json


_STATE_PRIORITY = {
    EvidenceState.FAIL: 0,
    EvidenceState.INDETERMINATE: 1,
    EvidenceState.STALE: 2,
    EvidenceState.BUDGET_EXHAUSTED: 3,
    EvidenceState.SKIPPED_LIMIT: 4,
    EvidenceState.WARNING: 5,
    EvidenceState.PASS: 6,
    EvidenceState.CANCELLED: 7,
    EvidenceState.NOT_EVALUATED: 8,
    EvidenceState.NOT_APPLICABLE: 9,
}


def select_evidence(items: Iterable[EvidenceReference], maximum: int) -> tuple[tuple[EvidenceReference, ...], dict[str, Any]]:
    values = tuple(items)
    ids = [item.evidence_id for item in values]
    if len(ids) != len(set(ids)):
        raise ValueError("Evidence IDs must be unique.")
    ordered = sorted(values, key=lambda item: (0 if item.critical else 1, _STATE_PRIORITY[item.state], item.evidence_id))
    selected = tuple(ordered[:maximum])
    omitted = tuple(item.evidence_id for item in ordered[maximum:])
    if any(item.critical for item in ordered[maximum:]):
        raise ValueError("The evidence budget cannot represent all critical evidence.")
    return selected, {
        "input_count": len(values),
        "retained_count": len(selected),
        "omitted_count": len(omitted),
        "omitted_ids": omitted,
        "priority": "CRITICAL_THEN_FAIL_UNKNOWN_THEN_STABLE_ID",
    }


def fit_payload(
    payload: dict[str, Any],
    *,
    maximum_bytes: int,
    protected_summary_keys: tuple[str, ...] = ("user_goal", "hard_risk_summary", "unknown_states"),
) -> tuple[dict[str, Any], dict[str, Any]]:
    value = dict(payload)
    rankings = list(value.get("ranking_information", ()))
    summaries = dict(value.get("summaries", {}))
    removed: list[str] = []

    def size() -> int:
        return len(canonical_json(value).encode("utf-8"))

    while size() > maximum_bytes and rankings:
        rankings.pop()
        value["ranking_information"] = rankings
        removed.append("RANKING_ITEM")
    optional_keys = sorted((key for key in summaries if key not in protected_summary_keys), reverse=True)
    while size() > maximum_bytes and optional_keys:
        key = optional_keys.pop(0)
        summaries.pop(key, None)
        value["summaries"] = summaries
        removed.append(f"SUMMARY:{key}")
    if size() > maximum_bytes:
        raise ValueError("Context exceeds the byte budget without dropping protected risk evidence.")
    return value, {
        "truncated": bool(removed),
        "removed": tuple(removed),
        "final_bytes": size(),
        "maximum_bytes": maximum_bytes,
    }


__all__ = ("fit_payload", "select_evidence")
