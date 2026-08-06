"""Strict structural and semantic validation of provider recommendation JSON."""

from __future__ import annotations

import re
from typing import Any, Mapping

from ..models.ai_assistance_models import ConfidenceClassification, RecommendationType, validate_hash


ROOT_FIELDS = {"recommendations", "overall_limitations"}
RECOMMENDATION_FIELDS = {
    "recommendation_type", "target_id", "target_fingerprint", "alternative_ids",
    "reason_codes", "reason", "assumptions", "trade_offs", "evidence_references", "confidence_hint",
    "unmet_prerequisites", "limitations", "operation_echo",
}
OPERATION_FIELDS = {"operation", "candidate_id", "parameter_hash"}
SAFE_OPERATIONS = {
    "UNIFORM_SCALE", "ORIENTATION", "BUILD_PLATE_TRANSLATION", "BASE_STABILIZATION",
    "REPAIR_REUSE", "DECIMATION", "COMBINED_SCALE_ORIENTATION",
}
_REASON_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_DANGEROUS = (
    re.compile(r"\b(?:eval|exec|pickle|subprocess|powershell|cmd\.exe|os\.system|bpy\.ops)\b", re.I),
    re.compile(r"(?:https?://|file://|\\\\|\.\.[\\/]|[A-Za-z]:[\\/])", re.I),
    re.compile(r"(?:ignore (?:all |the )?(?:previous|local|system)|bypass (?:policy|approval|safety))", re.I),
    re.compile(r"(?:globally optimal|guaranteed (?:print|printability|success)|geometry (?:is )?correct|mutate (?:the )?source directly)", re.I),
    re.compile(r"(?:-----BEGIN [A-Z ]+KEY-----|sk-[A-Za-z0-9_-]{12,})"),
    re.compile(r"<[A-Za-z!/][^>]*>", re.I),
)


class RecommendationValidationError(ValueError):
    pass


def _exact_fields(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise RecommendationValidationError(f"{label} fields mismatch; missing={missing}, extra={extra}.")


def _text(value: Any, label: str, *, minimum: int = 0, maximum: int) -> str:
    if not isinstance(value, str) or not minimum <= len(value) <= maximum:
        raise RecommendationValidationError(f"{label} must be bounded text.")
    if any(ord(char) < 32 and char not in "\n\r\t" for char in value):
        raise RecommendationValidationError(f"{label} contains prohibited control content.")
    if any(pattern.search(value) for pattern in _DANGEROUS):
        raise RecommendationValidationError(f"{label} contains prohibited executable, path, URL, secret, policy-bypass, or guarantee content.")
    return value


def _strings(value: Any, label: str, *, maximum_items: int, maximum_text: int, minimum_items: int = 0) -> tuple[str, ...]:
    if not isinstance(value, list) or not minimum_items <= len(value) <= maximum_items:
        raise RecommendationValidationError(f"{label} must be a bounded array.")
    result = tuple(_text(item, f"{label} item", minimum=1, maximum=maximum_text) for item in value)
    if len(set(result)) != len(result):
        raise RecommendationValidationError(f"{label} contains duplicates.")
    return result


def validate_recommendation_document(value: Mapping[str, Any], *, maximum_recommendations: int, maximum_evidence: int) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RecommendationValidationError("Recommendation document must be an object.")
    _exact_fields(value, ROOT_FIELDS, "root")
    recommendations = value["recommendations"]
    if not isinstance(recommendations, list) or not 1 <= len(recommendations) <= maximum_recommendations:
        raise RecommendationValidationError("recommendations exceeds the configured count.")
    normalized: list[dict[str, Any]] = []
    seen_targets: set[tuple[str, str | None]] = set()
    for index, raw in enumerate(recommendations):
        if not isinstance(raw, Mapping):
            raise RecommendationValidationError(f"recommendations[{index}] must be an object.")
        _exact_fields(raw, RECOMMENDATION_FIELDS, f"recommendations[{index}]")
        try:
            kind = RecommendationType(raw["recommendation_type"])
            confidence = ConfidenceClassification(raw["confidence_hint"])
        except (ValueError, TypeError) as exc:
            raise RecommendationValidationError("Unknown recommendation type or confidence value.") from exc
        target_id = raw["target_id"]
        fingerprint = raw["target_fingerprint"]
        if target_id is not None:
            target_id = _text(target_id, "target_id", minimum=1, maximum=128)
        if fingerprint is not None:
            try:
                fingerprint = validate_hash(fingerprint, "target_fingerprint")
            except ValueError as exc:
                raise RecommendationValidationError(str(exc)) from exc
        actionable_kind = kind in {RecommendationType.SELECT_EXISTING_STRATEGY, RecommendationType.SELECT_EXISTING_CANDIDATE, RecommendationType.SELECT_EXISTING_PLAN}
        if actionable_kind != (target_id is not None and fingerprint is not None):
            raise RecommendationValidationError("Only actionable recommendations may and must reference an exact target and fingerprint.")
        key = (kind.value, target_id)
        if key in seen_targets:
            raise RecommendationValidationError("Duplicate recommendation targets are prohibited.")
        seen_targets.add(key)
        reason_codes = _strings(raw["reason_codes"], "reason_codes", maximum_items=32, maximum_text=64, minimum_items=1)
        if any(_REASON_CODE.fullmatch(item) is None for item in reason_codes):
            raise RecommendationValidationError("reason_codes contains an invalid code.")
        operations = raw["operation_echo"]
        if not isinstance(operations, list) or len(operations) > 8:
            raise RecommendationValidationError("operation_echo exceeds bounds.")
        echoes: list[dict[str, str]] = []
        for operation in operations:
            if not isinstance(operation, Mapping):
                raise RecommendationValidationError("operation_echo items must be objects.")
            _exact_fields(operation, OPERATION_FIELDS, "operation_echo")
            if operation["operation"] not in SAFE_OPERATIONS:
                raise RecommendationValidationError("Unknown or prohibited operation.")
            candidate_id = _text(operation["candidate_id"], "candidate_id", minimum=1, maximum=128)
            try:
                parameter_hash = validate_hash(operation["parameter_hash"], "parameter_hash")
            except ValueError as exc:
                raise RecommendationValidationError(str(exc)) from exc
            echoes.append({"operation": operation["operation"], "candidate_id": candidate_id, "parameter_hash": parameter_hash})
        normalized.append({
            "recommendation_type": kind,
            "target_id": target_id,
            "target_fingerprint": fingerprint,
            "alternative_ids": _strings(raw["alternative_ids"], "alternative_ids", maximum_items=32, maximum_text=128),
            "reason_codes": reason_codes,
            "reason": _text(raw["reason"], "reason", minimum=1, maximum=2048),
            "assumptions": _strings(raw["assumptions"], "assumptions", maximum_items=64, maximum_text=1024),
            "trade_offs": _strings(raw["trade_offs"], "trade_offs", maximum_items=64, maximum_text=1024),
            "evidence_references": _strings(raw["evidence_references"], "evidence_references", maximum_items=maximum_evidence, maximum_text=128),
            "confidence_hint": confidence,
            "unmet_prerequisites": _strings(raw["unmet_prerequisites"], "unmet_prerequisites", maximum_items=64, maximum_text=1024),
            "limitations": _strings(raw["limitations"], "limitations", maximum_items=128, maximum_text=1024),
            "operation_echo": tuple(echoes),
        })
    return {"recommendations": tuple(normalized), "overall_limitations": _strings(value["overall_limitations"], "overall_limitations", maximum_items=128, maximum_text=1024)}


__all__ = ("RecommendationValidationError", "SAFE_OPERATIONS", "validate_recommendation_document")
