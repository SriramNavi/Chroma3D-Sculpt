"""Build the bounded, consent-scoped Sprint 7 provider context manifest."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from ..models.ai_assistance_models import (
    AssistanceLimits,
    AssistancePolicy,
    ConsentRecord,
    ContextManifest,
    EvidenceReference,
    EvidenceState,
    canonical_json,
    deterministic_id,
    stable_hash,
    validate_hash,
)
from .context_budget import fit_payload, select_evidence
from .context_redaction import assert_allow_list_payload, safe_display_name, sanitize_text


ALLOWED_SUMMARY_KEYS = {
    "user_goal", "printer_profile_id", "material_profile_id", "nozzle_mm", "layer_height_mm",
    "process_summary", "diagnostic_counts", "printability_status", "risk_summary",
    "advanced_preparation_summary", "pareto_summary", "performance_mode", "hard_risk_summary",
    "unknown_states",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_map(values: Mapping[str, str], name: str) -> dict[str, str]:
    if len(values) > 32:
        raise ValueError(f"{name} exceeds the maximum dependency count.")
    result: dict[str, str] = {}
    for key, value in sorted(values.items()):
        if not key or len(key) > 64:
            raise ValueError(f"{name} contains an invalid key.")
        result[str(key)] = validate_hash(str(value), f"{name}.{key}")
    return result


def _bounded_ids(values: Sequence[str], name: str, maximum: int) -> tuple[str, ...]:
    result = tuple(sorted(str(value) for value in values))
    if len(result) > maximum or len(result) != len(set(result)) or any(not value or len(value) > 128 for value in result):
        raise ValueError(f"{name} exceeds bounds or contains invalid/duplicate IDs.")
    return result


def build_context_manifest(
    *,
    source_signature_hash: str,
    object_display_name: str,
    policy: AssistancePolicy,
    limits: AssistanceLimits,
    user_goal: str,
    profile_hashes: Mapping[str, str] = {},
    settings_hashes: Mapping[str, str] = {},
    evidence: Iterable[EvidenceReference] = (),
    candidate_ids: Sequence[str] = (),
    plan_ids: Sequence[str] = (),
    strategy_ids: Sequence[str] = (),
    ranking_information: Sequence[Mapping[str, Any]] = (),
    summaries: Mapping[str, Any] = {},
    destination: str = "api.openai.com/v1/responses",
    purpose: str = "Generate advisory recommendations over existing validated Chroma3D candidates and strategies.",
    retention_disclosure: str = "OpenAI provider retention applies; Chroma3D does not persist raw exchanges by default.",
    cost_disclosure: str = "Usage may incur charges from the user's API provider; no guaranteed currency estimate is shown.",
    consent_approved: bool = False,
    consent_timestamp: str | None = None,
) -> ContextManifest:
    validate_hash(source_signature_hash, "source_signature_hash")
    if policy.maximum_request_bytes > limits.context_bytes or policy.maximum_evidence_items > limits.evidence_links:
        raise ValueError("Policy exceeds the selected assistance-mode limits.")
    safe_name, name_reasons = safe_display_name(object_display_name)
    safe_goal, goal_reasons = sanitize_text(user_goal, maximum=limits.intent_bytes, label="user_goal")
    selected_evidence, evidence_budget = select_evidence(evidence, min(policy.maximum_evidence_items, limits.evidence_links))
    safe_summaries: dict[str, Any] = {}
    for key, value in sorted(summaries.items()):
        if key not in ALLOWED_SUMMARY_KEYS:
            raise ValueError(f"Summary field is not allow-listed: {key}")
        safe_summaries[key] = value
    safe_summaries["user_goal"] = safe_goal
    unknown_states = tuple(sorted(item.evidence_id for item in selected_evidence if item.state not in {EvidenceState.PASS, EvidenceState.NOT_APPLICABLE}))
    safe_summaries["unknown_states"] = unknown_states
    candidates = _bounded_ids(candidate_ids, "candidate_ids", 256)
    plans = _bounded_ids(plan_ids, "plan_ids", 64)
    strategies = _bounded_ids(strategy_ids, "strategy_ids", min(32, policy.maximum_strategies))
    rankings = tuple(dict(item) for item in ranking_information[: policy.maximum_strategies])
    category_set = {"USER_INTENT", "SOURCE_IDENTITY"}
    category_set.update(item.evidence_type for item in selected_evidence)
    if candidates:
        category_set.add("OPTIMIZATION_CANDIDATES")
    if strategies:
        category_set.add("INTELLIGENT_STRATEGIES")
    if rankings:
        category_set.add("RANKING")
    included_categories = tuple(sorted(category_set))
    omitted_categories = tuple(sorted({"RAW_GEOMETRY", "BLEND_FILE", "IMAGES", "PATHS", "CREDENTIALS", "UNRELATED_SCENE_DATA", "RAW_LOGS", "SOURCE_CODE"}))
    scope_payload = {
        "destination": destination,
        "purpose": purpose,
        "data_categories": included_categories,
        "retention_disclosure": retention_disclosure,
        "cost_disclosure": cost_disclosure,
        "source_signature_hash": source_signature_hash,
        "policy_hash": policy.policy_hash,
    }
    scope_hash = stable_hash(scope_payload)
    consent = ConsentRecord(
        consent_id=deterministic_id("consent", scope_payload),
        approved=consent_approved,
        approved_at=consent_timestamp if consent_approved else None,
        scope_hash=scope_hash,
        data_categories=included_categories,
        destination=destination,
        purpose=purpose,
        retention_disclosure=retention_disclosure,
        cost_disclosure=cost_disclosure,
    )
    redaction_record = {
        "mode": "STRICT_ALLOW_LIST",
        "object_name_actions": name_reasons,
        "user_goal_actions": goal_reasons,
        "excluded_categories": omitted_categories,
        "geometry_elements_exported": 0,
    }
    payload = {
        "source_signature_hash": source_signature_hash,
        "object_safe_display_name": safe_name,
        "profile_hashes": _hash_map(profile_hashes, "profile_hashes"),
        "settings_hashes": _hash_map(settings_hashes, "settings_hashes"),
        "evidence": [item.to_dict() for item in selected_evidence],
        "candidate_ids": candidates,
        "plan_ids": plans,
        "strategy_ids": strategies,
        "ranking_information": rankings,
        "summaries": safe_summaries,
        "unknown_states": unknown_states,
        "limitations": (
            "Context contains summaries and local evidence identities only; no raw geometry or files.",
            "Provider output cannot override local evidence or execution policy.",
        ),
        "included_categories": included_categories,
        "omitted_categories": omitted_categories,
        "redaction_record": redaction_record,
        "consent_scope_hash": scope_hash,
        "policy_hash": policy.policy_hash,
        "geometry_elements_exported": 0,
    }
    fitted, byte_budget = fit_payload(payload, maximum_bytes=min(policy.maximum_request_bytes, limits.context_bytes))
    assert_allow_list_payload(fitted)
    context_bytes = len(canonical_json(fitted).encode("utf-8"))
    context_hash = stable_hash(fitted)
    return ContextManifest(
        context_id=deterministic_id("context", fitted),
        created_at=_now(),
        source_signature_hash=source_signature_hash,
        object_safe_display_name=safe_name,
        profile_hashes=fitted["profile_hashes"],
        settings_hashes=fitted["settings_hashes"],
        evidence=selected_evidence,
        candidate_ids=candidates,
        plan_ids=plans,
        strategy_ids=strategies,
        ranking_information=tuple(fitted.get("ranking_information", ())),
        summaries=fitted["summaries"],
        unknown_states=unknown_states,
        limitations=tuple(fitted["limitations"]),
        included_categories=included_categories,
        omitted_categories=omitted_categories,
        redaction_record={**redaction_record, "evidence_budget": evidence_budget},
        truncation_record=byte_budget,
        byte_count=context_bytes,
        token_estimate=(context_bytes + 3) // 4,
        consent=consent,
        context_hash=context_hash,
        policy_hash=policy.policy_hash,
        geometry_elements_exported=0,
    )


__all__ = ("ALLOWED_SUMMARY_KEYS", "build_context_manifest")
