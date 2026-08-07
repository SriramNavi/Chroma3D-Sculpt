"""Deterministic multi-objective Pareto-front construction."""

from __future__ import annotations

import math
from typing import Sequence

from ..models.intelligent_optimization_models import (
    DominanceRecord,
    DominanceState,
    EvidenceState,
    ObjectiveDirection,
    ObjectiveVector,
    ParetoFrontier,
    ParetoPoint,
    StrategyEvaluation,
)


def _evaluation_parts(value: StrategyEvaluation | ParetoPoint | ObjectiveVector) -> tuple[str, ObjectiveVector, bool]:
    if isinstance(value, StrategyEvaluation):
        return value.strategy_id, value.objective_vector, value.feasible
    if isinstance(value, ParetoPoint):
        return value.strategy_id, value.objective_vector, value.feasible
    return "", value, True


def _dominance(left: ObjectiveVector, right: ObjectiveVector, *, left_feasible: bool, right_feasible: bool, tolerance: float) -> tuple[DominanceState, tuple[str, ...], tuple[str, ...], tuple[str, ...], str]:
    if left_feasible and not right_feasible:
        return DominanceState.DOMINATES, (), (), (), "Feasible strategies dominate infeasible strategies after hard filtering."
    if right_feasible and not left_feasible:
        return DominanceState.DOMINATED, (), (), (), "An infeasible strategy cannot dominate a feasible strategy."
    if not left_feasible and not right_feasible:
        return DominanceState.INCOMPARABLE, (), (), (), "Neither infeasible strategy can establish a safe dominance claim."
    keys = sorted(set(left.normalized_values) | set(right.normalized_values))
    better: list[str] = []
    worse: list[str] = []
    equal: list[str] = []
    unknown_left: list[str] = []
    unknown_right: list[str] = []
    for key in keys:
        l_state = left.evidence_states.get(key, EvidenceState.INDETERMINATE)
        r_state = right.evidence_states.get(key, EvidenceState.INDETERMINATE)
        l_value = left.normalized_values.get(key)
        r_value = right.normalized_values.get(key)
        if l_value is None or l_state in {EvidenceState.INDETERMINATE, EvidenceState.SKIPPED_LIMIT}:
            unknown_left.append(key)
        if r_value is None or r_state in {EvidenceState.INDETERMINATE, EvidenceState.SKIPPED_LIMIT}:
            unknown_right.append(key)
        if l_value is None or r_value is None or key in unknown_left or key in unknown_right:
            continue
        direction = ObjectiveDirection(left.directions.get(key, right.directions.get(key, ObjectiveDirection.MAXIMIZE)))
        delta = float(l_value) - float(r_value)
        if abs(delta) <= tolerance:
            equal.append(key)
        elif (direction == ObjectiveDirection.MAXIMIZE and delta > 0.0) or (direction == ObjectiveDirection.MINIMIZE and delta < 0.0):
            better.append(key)
        else:
            worse.append(key)
    if unknown_left and not unknown_right:
        return DominanceState.INCOMPARABLE, tuple(better), tuple(worse), tuple(equal), "Unknown or skipped evidence cannot dominate known evidence."
    if unknown_right and not unknown_left:
        return DominanceState.DOMINATES if not worse else DominanceState.INCOMPARABLE, tuple(better), tuple(worse), tuple(equal), "Known evidence is compared conservatively against unknown evidence."
    if better and not worse:
        return DominanceState.DOMINATES, tuple(better), tuple(worse), tuple(equal), "No objective is worse and at least one objective is better."
    if worse and not better:
        return DominanceState.DOMINATED, tuple(better), tuple(worse), tuple(equal), "At least one objective is worse and none is better."
    if not better and not worse:
        return DominanceState.EQUAL, tuple(better), tuple(worse), tuple(equal), "Objective vectors are equal within the configured tolerance."
    return DominanceState.INCOMPARABLE, tuple(better), tuple(worse), tuple(equal), "Visible objective trade-offs prevent dominance."


def dominance(left: StrategyEvaluation | ParetoPoint, right: StrategyEvaluation | ParetoPoint, *, tolerance: float = 0.0) -> DominanceRecord:
    left_id, left_vector, left_feasible = _evaluation_parts(left)
    right_id, right_vector, right_feasible = _evaluation_parts(right)
    state, better, worse, equal, reason = _dominance(left_vector, right_vector, left_feasible=left_feasible, right_feasible=right_feasible, tolerance=tolerance)
    return DominanceRecord(left_id, right_id, state, better, worse, equal, reason)


def dominates(left: StrategyEvaluation | ParetoPoint, right: StrategyEvaluation | ParetoPoint, *, tolerance: float = 0.0) -> bool:
    return dominance(left, right, tolerance=tolerance).state == DominanceState.DOMINATES


def build_pareto_frontier(
    evaluations: Sequence[StrategyEvaluation],
    *,
    tolerance: float = 0.0,
    max_points: int = 128,
    strategy_set_hash: str = "",
) -> ParetoFrontier:
    if isinstance(max_points, bool) or not isinstance(max_points, int) or max_points < 1:
        raise ValueError("max_points must be a positive integer.")
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not math.isfinite(float(tolerance)) or tolerance < 0.0:
        raise ValueError("tolerance must be a finite non-negative number.")
    ordered = sorted(evaluations, key=lambda item: item.strategy_id)
    records: list[DominanceRecord] = []
    dominated: set[str] = set()
    non_dominated: list[StrategyEvaluation] = []
    for index, current in enumerate(ordered):
        is_dominated = False
        for other_index, other in enumerate(ordered):
            if index == other_index:
                continue
            record = dominance(other, current, tolerance=tolerance)
            if record.state in {DominanceState.DOMINATES, DominanceState.EQUAL}:
                records.append(record)
            if record.state == DominanceState.DOMINATES:
                is_dominated = True
                break
            if record.state == DominanceState.EQUAL and other.strategy_id < current.strategy_id:
                is_dominated = True
                break
        if is_dominated:
            dominated.add(current.strategy_id)
        else:
            non_dominated.append(current)
    non_dominated = sorted(non_dominated, key=lambda item: item.strategy_id)
    limitations: list[str] = []
    if len(non_dominated) > max_points:
        limitations.append(f"Frontier bounded to {max_points} points; additional non-dominated points were retained as bounded-limit evidence.")
        non_dominated = non_dominated[:max_points]
    points = tuple(
        ParetoPoint(
            strategy_id=item.strategy_id,
            objective_vector=item.objective_vector,
            feasible=item.feasible,
            dominance_state=DominanceState.NON_DOMINATED,
            dominance_reason="Non-dominated within the evaluated bounded set.",
            frontier_index=index,
        )
        for index, item in enumerate(non_dominated)
    )
    return ParetoFrontier(
        points=points,
        dominated_strategy_ids=tuple(sorted(dominated)),
        dominance_records=tuple(records),
        tolerance=float(tolerance),
        max_points=max_points,
        strategy_set_hash=strategy_set_hash,
        limitations=tuple(limitations + ["Pareto dominance is bounded by available evidence and does not establish a global optimum."]),
    )


construct_pareto_frontier = build_pareto_frontier


def frontier_is_current(frontier: ParetoFrontier, *, strategy_set_hash: str, expected_frontier_hash: str = "") -> tuple[bool, str]:
    if frontier.strategy_set_hash != strategy_set_hash:
        return False, "STRATEGY_SET_CHANGED"
    if expected_frontier_hash and frontier.frontier_hash != expected_frontier_hash:
        return False, "PARETO_FRONTIER_CHANGED"
    return True, "CURRENT"


__all__ = ("build_pareto_frontier", "construct_pareto_frontier", "dominance", "dominates", "frontier_is_current")
