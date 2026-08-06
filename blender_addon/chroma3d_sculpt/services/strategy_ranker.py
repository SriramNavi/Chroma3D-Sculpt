"""Explainable deterministic ranking over bounded strategy evaluations."""

from __future__ import annotations

from math import isfinite, sqrt
from typing import Any, Mapping, Sequence

from ..intelligent_optimization_settings import ObjectiveProfile, build_objective_profile
from ..models.intelligent_optimization_models import (
    EvidenceState,
    RankingMethod,
    RankingRecord,
    RecommendationRecord,
    StrategyEvaluation,
)


_CONFIDENCE = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}


def _profile(profile: ObjectiveProfile | Mapping[str, Any] | None) -> dict[str, Any]:
    value = profile or build_objective_profile("Balanced")
    return value.to_dict() if isinstance(value, ObjectiveProfile) else dict(value)


def _goodness(evaluation: StrategyEvaluation, key: str) -> float | None:
    value = evaluation.objective_vector.normalized_values.get(key)
    evidence_state = evaluation.objective_vector.evidence_states.get(key, EvidenceState.INDETERMINATE)
    if value is None or evidence_state in {EvidenceState.INDETERMINATE, EvidenceState.SKIPPED_LIMIT, EvidenceState.NOT_APPLICABLE}:
        return None
    if not isfinite(float(value)):
        return None
    direction = str(evaluation.objective_vector.directions.get(key, "MAXIMIZE"))
    return float(value) if direction in {"MAXIMIZE", "ObjectiveDirection.MAXIMIZE"} else 1.0 - float(value)


def _weighted_sum(evaluation: StrategyEvaluation, profile: Mapping[str, Any]) -> tuple[float, dict[str, float]]:
    weights = profile.get("normalized_weights", profile.get("weights", {}))
    contributions: dict[str, float] = {}
    total = 0.0
    total_weight = 0.0
    for key, weight in sorted(weights.items()):
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not isfinite(float(weight)) or float(weight) < 0.0:
            raise ValueError(f"Objective weight for {key!r} must be finite and non-negative.")
        goodness = _goodness(evaluation, str(key))
        if goodness is None:
            continue
        contribution = float(weight) * goodness
        contributions[str(key)] = round(contribution, 12)
        total += contribution
        total_weight += float(weight)
    return (round(total / total_weight, 12) if total_weight else 0.0), contributions


def _score(evaluation: StrategyEvaluation, method: RankingMethod, profile: Mapping[str, Any], user_priority: Sequence[str]) -> tuple[float, dict[str, float], str]:
    weighted, contributions = _weighted_sum(evaluation, profile)
    if method == RankingMethod.WEIGHTED_SUM or method == RankingMethod.CONSTRAINT_FIRST:
        return weighted, contributions, "Visible weighted objective contributions."
    if method == RankingMethod.WEIGHTED_TCHEBYCHEFF:
        weights = profile.get("normalized_weights", profile.get("weights", {}))
        distances = [float(weight) * (1.0 - (_goodness(evaluation, str(key)) or 0.0)) for key, weight in weights.items() if _goodness(evaluation, str(key)) is not None]
        return (round(1.0 - max(distances, default=1.0), 12), contributions, "Weighted distance from the explicit ideal point.")
    if method == RankingMethod.BALANCED_DISTANCE_TO_IDEAL:
        values = [1.0 - (_goodness(evaluation, str(key)) or 0.0) for key in profile.get("normalized_weights", profile.get("weights", {})) if _goodness(evaluation, str(key)) is not None]
        return (round(1.0 - sqrt(sum(item * item for item in values) / max(1, len(values))), 12), contributions, "Euclidean distance to the visible balanced ideal.")
    if method == RankingMethod.FIDELITY_FIRST:
        return _priority_score(evaluation, ("geometry_fidelity", "wall_thickness_preservation", "thin_feature_preservation"), weighted, contributions, "Fidelity-first priority.")
    if method == RankingMethod.MINIMUM_SUPPORTS:
        return _priority_score(evaluation, ("support_risk", "bridge_risk", "overhang_risk"), weighted, contributions, "Minimum-support priority.")
    if method == RankingMethod.FIT_TO_PRINTER:
        return _priority_score(evaluation, ("build_volume_fit", "height", "contact_quality"), weighted, contributions, "Fit-to-printer priority.")
    if method == RankingMethod.STABLE_BASE:
        return _priority_score(evaluation, ("contact_quality", "support_risk", "height"), weighted, contributions, "Stable-base priority.")
    if method == RankingMethod.LIGHTWEIGHT:
        return _priority_score(evaluation, ("triangle_count", "runtime_cost", "memory_observation"), weighted, contributions, "Lightweight priority.")
    if method == RankingMethod.USER_PRIORITY:
        return _priority_score(evaluation, tuple(user_priority), weighted, contributions, "User-selected priority order.")
    if method == RankingMethod.LEXICOGRAPHIC:
        keys = tuple(profile.get("normalized_weights", profile.get("weights", {})))
        values = [_goodness(evaluation, str(key)) for key in keys]
        score = sum((item or 0.0) / (10 ** index) for index, item in enumerate(values))
        return round(score, 12), contributions, "Lexicographic order over explicit objective priorities."
    return weighted, contributions, "Deterministic bounded ranking method."


def _priority_score(evaluation: StrategyEvaluation, priorities: Sequence[str], fallback: float, contributions: Mapping[str, float], rationale: str) -> tuple[float, dict[str, float], str]:
    values = [_goodness(evaluation, key) for key in priorities]
    known = [(index, item) for index, item in enumerate(values) if item is not None]
    return (round(sum(item / (10 ** index) for index, item in known), 12) if known else fallback), dict(contributions), rationale


def _tie_key(evaluation: StrategyEvaluation) -> tuple[Any, ...]:
    warnings = sum(item.state.value == "WARNING" for item in evaluation.constraint_evaluations)
    confidence = _CONFIDENCE.get(evaluation.objective_vector.confidence.upper(), 0)
    fidelity = _goodness(evaluation, "geometry_fidelity") or 0.0
    operation_count = evaluation.objective_vector.raw_values.get("operation_count")
    runtime = evaluation.runtime_seconds
    return (warnings, len(evaluation.critical_regressions), -confidence, -fidelity, float(operation_count or 0), runtime, evaluation.strategy_id)


def rank_strategies(
    evaluations: Sequence[StrategyEvaluation],
    *,
    method: RankingMethod | str = RankingMethod.CONSTRAINT_FIRST,
    profile: ObjectiveProfile | Mapping[str, Any] | None = None,
    user_priority: Sequence[str] = (),
    non_dominated_strategy_ids: Sequence[str] = (),
    tie_tolerance: float = 1e-12,
) -> tuple[RankingRecord, ...]:
    ranking_method = RankingMethod(method)
    profile_data = _profile(profile)
    feasible = [item for item in evaluations if item.feasible and not item.critical_regressions]
    scored: list[tuple[StrategyEvaluation, float, dict[str, float], str]] = []
    for evaluation in feasible:
        score, contributions, rationale = _score(evaluation, ranking_method, profile_data, user_priority)
        scored.append((evaluation, score, contributions, rationale))
    scored.sort(key=lambda item: (-item[1], _tie_key(item[0])))
    records: list[RankingRecord] = []
    previous_score: float | None = None
    tie_index = 0
    for index, (evaluation, score, contributions, rationale) in enumerate(scored, 1):
        if previous_score is None or abs(score - previous_score) > tie_tolerance:
            tie_index += 1
        tie_group = f"TIE-{tie_index:03d}"
        records.append(RankingRecord(
            strategy_id=evaluation.strategy_id,
            rank=index,
            method=ranking_method,
            score=score,
            non_dominated=evaluation.strategy_id in set(non_dominated_strategy_ids),
            tie_group=tie_group,
            tie_break_trace=("FEWER_HARD_WARNINGS", "FEWER_CRITICAL_REGRESSIONS", "HIGHER_CONFIDENCE", "HIGHER_FIDELITY", "FEWER_OPERATIONS", "LOWER_RUNTIME", "STABLE_STRATEGY_ID"),
            objective_contributions=contributions,
            rationale=rationale,
        ))
        previous_score = score
    return tuple(records)


def recommend_strategy(rankings: Sequence[RankingRecord], *, alternatives: Sequence[str] = (), confidence: str = "LOW") -> RecommendationRecord | None:
    if not rankings:
        return None
    top = min(rankings, key=lambda item: item.rank)
    others = tuple(alternatives) or tuple(item.strategy_id for item in rankings if item.strategy_id != top.strategy_id)
    return RecommendationRecord(
        strategy_id=top.strategy_id,
        ranking_method=top.method,
        rank=top.rank,
        wording="Recommended under current objectives within the evaluated bounded search; this is not a global optimum.",
        confidence=confidence,
        is_automatic_execution=False,
        required_user_approval=True,
        alternatives=others,
        limitations=("User review, isolated preview, and explicit execution approval remain required.",),
    )


rank = rank_strategies


__all__ = ("rank", "rank_strategies", "recommend_strategy")
