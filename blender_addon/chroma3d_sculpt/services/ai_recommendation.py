"""Complete provider-output validation pipeline."""

from __future__ import annotations

from typing import Mapping

from ..models.ai_assistance_models import AIRecommendation, AssistanceLimits, AssistancePolicy, ContextManifest
from .recommendation_decoder import decode_recommendation_json
from .recommendation_grounding import ground_recommendations
from .recommendation_resolver import TargetDescriptor
from .recommendation_validator import validate_recommendation_document


def validate_provider_recommendations(
    response: bytes | str,
    *,
    context: ContextManifest,
    registry: Mapping[str, TargetDescriptor],
    policy: AssistancePolicy,
    limits: AssistanceLimits,
    provider_generated: bool = True,
) -> tuple[AIRecommendation, ...]:
    decoded = decode_recommendation_json(response, maximum_bytes=min(limits.response_bytes, policy.maximum_response_bytes), maximum_depth=limits.json_depth)
    validated = validate_recommendation_document(decoded, maximum_recommendations=limits.recommendations, maximum_evidence=limits.evidence_links)
    return ground_recommendations(validated, context=context, registry=registry, policy=policy, provider_generated=provider_generated)


__all__ = ("validate_provider_recommendations",)
