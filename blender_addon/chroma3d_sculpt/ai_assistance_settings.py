"""Validated Sprint 7 assistance policy and bounded mode settings."""

from __future__ import annotations

from dataclasses import replace

from .models.ai_assistance_models import (
    AssistanceLimits,
    AssistanceMode,
    AssistancePolicy,
    DeploymentState,
)
from .performance_registry import AI_ASSISTANCE_LIMITS


def limits_for_mode(mode: AssistanceMode | str, *, custom: AssistanceLimits | None = None) -> AssistanceLimits:
    selected = AssistanceMode(mode)
    if selected is AssistanceMode.CUSTOM:
        if custom is None:
            raise ValueError("CUSTOM assistance mode requires explicit validated limits.")
        return custom
    return AssistanceLimits(**AI_ASSISTANCE_LIMITS[selected.value])


def default_assistance_policy(
    *,
    enabled: bool = False,
    model_allow_list: tuple[str, ...] = (),
    preview_allowed: bool = True,
    execution_delegation_allowed: bool = True,
) -> AssistancePolicy:
    limits = limits_for_mode(AssistanceMode.STANDARD)
    return AssistancePolicy(
        policy_id="chroma3d-sprint7-byok",
        policy_version="1.0.0",
        deployment_state=DeploymentState.APPROVED_BYOK,
        enabled=enabled,
        recommendation_only=True,
        preview_allowed=preview_allowed,
        execution_delegation_allowed=execution_delegation_allowed,
        provider_allow_list=("openai", "fake"),
        model_allow_list=model_allow_list,
        maximum_strategies=limits.recommendations,
        maximum_evidence_items=limits.evidence_links,
        maximum_request_bytes=limits.context_bytes,
        maximum_response_bytes=limits.response_bytes,
        timeout_seconds=limits.provider_timeout_seconds,
        retry_count=0,
        redaction_mode="STRICT_ALLOW_LIST",
        prompt_template_version="chroma3d-s7-recommendation-v1",
    )


def policy_for_mode(policy: AssistancePolicy, mode: AssistanceMode | str, *, custom: AssistanceLimits | None = None) -> AssistancePolicy:
    limits = limits_for_mode(mode, custom=custom)
    return replace(
        policy,
        maximum_strategies=limits.recommendations,
        maximum_evidence_items=limits.evidence_links,
        maximum_request_bytes=limits.context_bytes,
        maximum_response_bytes=limits.response_bytes,
        timeout_seconds=limits.provider_timeout_seconds,
    )


__all__ = ("default_assistance_policy", "limits_for_mode", "policy_for_mode")
