"""Versioned advisory risk aggregation with critical caps and missing-check honesty."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from ..metadata import SCORING_POLICY_VERSION
from ..models.printability_models import PrintabilityConfidence, PrintabilityScore, PrintabilityStatus


CATEGORY_WEIGHTS: dict[str, int] = {
    "topology_readiness": 15,
    "wall_thickness": 15,
    "thin_features": 10,
    "overhangs": 15,
    "floating_components": 15,
    "build_plate_contact": 10,
    "build_volume": 10,
    "orientation": 10,
}

_RISK = {
    PrintabilityStatus.PASS: 0.0,
    PrintabilityStatus.WARNING: 0.5,
    PrintabilityStatus.CRITICAL: 1.0,
    PrintabilityStatus.INDETERMINATE: 0.75,
    PrintabilityStatus.FAILED: 1.0,
}
_CONFIDENCE_RANK = {
    PrintabilityConfidence.UNKNOWN: 0,
    PrintabilityConfidence.LOW: 1,
    PrintabilityConfidence.MEDIUM: 2,
    PrintabilityConfidence.HIGH: 3,
}


def _status(value: Any) -> PrintabilityStatus:
    return value if isinstance(value, PrintabilityStatus) else PrintabilityStatus(str(value))


def score_printability(
    categories: dict[str, tuple[PrintabilityStatus, PrintabilityConfidence, str]],
    critical_reasons: tuple[str, ...] = (),
) -> PrintabilityScore:
    if sum(CATEGORY_WEIGHTS.values()) != 100:
        raise RuntimeError("Printability scoring weights must total 100.")
    missing: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    category_scores: dict[str, float] = {}
    covered_weight = 0
    deducted = 0.0
    confidence_values: list[PrintabilityConfidence] = []
    statuses: list[PrintabilityStatus] = []
    for name, weight in CATEGORY_WEIGHTS.items():
        state, confidence, reason = categories.get(
            name,
            (PrintabilityStatus.NOT_EVALUATED, PrintabilityConfidence.UNKNOWN, "Required category result is missing."),
        )
        state = _status(state)
        statuses.append(state)
        confidence_values.append(confidence)
        record = {"check": name, "state": state.value, "reason": reason}
        if state == PrintabilityStatus.SKIPPED_LIMIT:
            skipped.append(record)
            deducted += weight * 0.5
            continue
        if state in {PrintabilityStatus.NOT_EVALUATED, PrintabilityStatus.NOT_APPLICABLE}:
            missing.append(record)
            if state == PrintabilityStatus.NOT_APPLICABLE:
                covered_weight += weight
                category_scores[name] = float(weight)
            else:
                deducted += weight * 0.5
            continue
        covered_weight += weight
        risk = _RISK.get(state, 1.0)
        retained = weight * (1.0 - risk)
        category_scores[name] = retained
        deducted += weight - retained
        if state == PrintabilityStatus.FAILED:
            failed.append(record)
    coverage = float(covered_weight)
    numeric: int | None
    if covered_weight < 50:
        numeric = None
    else:
        raw = max(0.0, min(100.0, 100.0 - deducted))
        numeric = int(Decimal(str(raw)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if PrintabilityStatus.FAILED in statuses:
        overall = PrintabilityStatus.FAILED
    elif PrintabilityStatus.INDETERMINATE in statuses:
        overall = PrintabilityStatus.INDETERMINATE
    elif PrintabilityStatus.CRITICAL in statuses or critical_reasons:
        overall = PrintabilityStatus.CRITICAL
    elif PrintabilityStatus.WARNING in statuses:
        overall = PrintabilityStatus.WARNING
    elif skipped or missing:
        overall = PrintabilityStatus.INDETERMINATE
    else:
        overall = PrintabilityStatus.PASS
    if overall == PrintabilityStatus.CRITICAL and numeric is not None:
        numeric = min(numeric, 59)
    confidence_rank = min((_CONFIDENCE_RANK[value] for value in confidence_values), default=0)
    if skipped or failed or missing:
        confidence_rank = max(0, confidence_rank - 1)
    confidence = next(key for key, value in _CONFIDENCE_RANK.items() if value == confidence_rank)
    return PrintabilityScore(
        score=numeric,
        status=overall,
        confidence=confidence,
        critical_reasons=critical_reasons,
        missing_checks=tuple(missing),
        skipped_checks=tuple(skipped),
        failed_checks=tuple(failed),
        category_scores=category_scores,
        coverage_percent=coverage,
        scoring_policy_version=SCORING_POLICY_VERSION,
    )
