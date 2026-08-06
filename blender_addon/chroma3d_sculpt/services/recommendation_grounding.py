"""Ground recommendations in current local evidence and derive confidence locally."""

from __future__ import annotations

from typing import Any, Mapping

from ..models.ai_assistance_models import (
    AIRecommendation, AssistancePolicy, ConfidenceClassification, ContextManifest,
    EvidenceState, OperationEcho, RecommendationType, deterministic_id,
)
from .recommendation_resolver import TargetDescriptor, resolve_target


UNKNOWN_STATES = {
    EvidenceState.WARNING, EvidenceState.SKIPPED_LIMIT, EvidenceState.NOT_EVALUATED,
    EvidenceState.INDETERMINATE, EvidenceState.STALE, EvidenceState.CANCELLED,
    EvidenceState.BUDGET_EXHAUSTED,
}


def _confidence(evidence: tuple[Any, ...], *, target: TargetDescriptor | None, prerequisites: tuple[str, ...], provider_hint: ConfidenceClassification) -> ConfidenceClassification:
    if prerequisites or any(item.state == EvidenceState.FAIL for item in evidence):
        return ConfidenceClassification.UNKNOWN
    if not evidence or any(item.state in UNKNOWN_STATES for item in evidence):
        return ConfidenceClassification.LOW
    if target is None:
        return ConfidenceClassification.MEDIUM if provider_hint in {ConfidenceClassification.HIGH, ConfidenceClassification.MEDIUM} else ConfidenceClassification.LOW
    if provider_hint == ConfidenceClassification.HIGH and all(item.confidence == ConfidenceClassification.HIGH for item in evidence):
        return ConfidenceClassification.HIGH
    return ConfidenceClassification.MEDIUM if provider_hint != ConfidenceClassification.UNKNOWN else ConfidenceClassification.LOW


def ground_recommendations(
    document: Mapping[str, Any],
    *,
    context: ContextManifest,
    registry: Mapping[str, TargetDescriptor],
    policy: AssistancePolicy,
    provider_generated: bool,
) -> tuple[AIRecommendation, ...]:
    if context.policy_hash != policy.policy_hash:
        raise ValueError("Recommendation policy does not match the consented context policy hash.")
    evidence_by_id = {item.evidence_id: item for item in context.evidence}
    results: list[AIRecommendation] = []
    for raw in document["recommendations"]:
        references = tuple(raw["evidence_references"])
        if any(item not in evidence_by_id for item in references):
            raise ValueError("Recommendation references unknown local evidence.")
        linked = tuple(evidence_by_id[item] for item in references)
        kind = RecommendationType(raw["recommendation_type"])
        target_id = raw.get("target_id")
        disclosed_ids = {
            RecommendationType.SELECT_EXISTING_STRATEGY: set(context.strategy_ids),
            RecommendationType.SELECT_EXISTING_CANDIDATE: set(context.candidate_ids),
            RecommendationType.SELECT_EXISTING_PLAN: set(context.plan_ids),
        }.get(kind, set())
        if target_id is not None and target_id not in disclosed_ids:
            raise ValueError("Recommendation target was not present in the consented context manifest.")
        target = resolve_target(raw, registry, policy, source_signature=context.source_signature_hash)
        hard_failure = any(item.critical and item.state != EvidenceState.PASS for item in linked)
        action_available = target is not None and not hard_failure and not raw["unmet_prerequisites"]
        confidence = _confidence(linked, target=target, prerequisites=tuple(raw["unmet_prerequisites"]), provider_hint=raw["confidence_hint"])
        if hard_failure:
            raise ValueError("Unknown, skipped, indeterminate, stale, or failed evidence cannot satisfy a hard requirement.")
        identity = {
            "context_hash": context.context_hash, "policy_hash": policy.policy_hash,
            "provider_generated": provider_generated, "payload": raw,
            "confidence": confidence.value, "action_available": action_available,
        }
        results.append(AIRecommendation(
            recommendation_id=deterministic_id("recommendation", identity),
            provider_exchange_id=None,
            recommendation_type=kind,
            target_id=target.target_id if target else None,
            target_fingerprint=target.fingerprint if target else None,
            alternative_ids=tuple(raw["alternative_ids"]), reason_codes=tuple(raw["reason_codes"]),
            reason=raw["reason"], assumptions=tuple(raw["assumptions"]),
            trade_offs=tuple(raw["trade_offs"]), evidence_references=references,
            confidence=confidence, unmet_prerequisites=tuple(raw["unmet_prerequisites"]),
            limitations=tuple(raw["limitations"]) + tuple(document["overall_limitations"]),
            operation_echo=tuple(OperationEcho(**item) for item in raw["operation_echo"]),
            action_available=action_available, provider_generated=provider_generated,
        ))
    return tuple(results)


__all__ = ("UNKNOWN_STATES", "ground_recommendations")
