"""Evidence-backed strategy and recommendation explanations."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..models.intelligent_optimization_models import (
    ConstraintSeverity,
    ConstraintState,
    EvidenceState,
    IntelligentStrategy,
    RankingRecord,
    StrategyEvaluation,
    StrategyExplanation,
)


def _objective_labels(evaluation: StrategyEvaluation) -> tuple[tuple[str, ...], tuple[str, ...]]:
    improvements: list[str] = []
    regressions: list[str] = []
    vector = evaluation.objective_vector
    for key in sorted(vector.normalized_values):
        value = vector.normalized_values.get(key)
        if value is None:
            continue
        direction = str(vector.directions.get(key, "MAXIMIZE"))
        if direction.endswith("MAXIMIZE") and value > 0.5:
            improvements.append(f"{key} has estimated normalized value {value:.3f}.")
        elif direction.endswith("MINIMIZE") and value < 0.5:
            improvements.append(f"{key} has estimated normalized value {value:.3f}.")
        elif direction.endswith("MAXIMIZE") and value < 0.5:
            regressions.append(f"{key} is below the neutral normalized value ({value:.3f}).")
        elif direction.endswith("MINIMIZE") and value > 0.5:
            regressions.append(f"{key} is above the neutral normalized value ({value:.3f}).")
    return tuple(improvements), tuple(regressions)


def explain_strategy(
    strategy: IntelligentStrategy,
    evaluation: StrategyEvaluation,
    ranking: RankingRecord | None = None,
    *,
    alternatives: Sequence[str] = (),
) -> StrategyExplanation:
    improvements, regressions = _objective_labels(evaluation)
    hard_passed = tuple(item.constraint_id for item in evaluation.constraint_evaluations if item.severity == ConstraintSeverity.HARD and item.state == ConstraintState.PASS)
    soft_warnings = tuple(item.constraint_id for item in evaluation.constraint_evaluations if item.severity == ConstraintSeverity.SOFT and item.state in {ConstraintState.WARNING, ConstraintState.INDETERMINATE, ConstraintState.SKIPPED_LIMIT})
    why_feasible = tuple(item.constraint_id for item in evaluation.constraint_evaluations if item.state == ConstraintState.PASS)
    ranking_reasons = ((ranking.rationale,) if ranking else ("Ranking has not yet been assigned.",)) + tuple(f"Objective contribution {key}: {value:.6f}" for key, value in sorted((ranking.objective_contributions if ranking else {}).items()))
    return StrategyExplanation(
        strategy_id=strategy.strategy_id,
        why_generated=(f"Generated from the {strategy.generation_family} family.", strategy.generation_reason.value),
        why_feasible=why_feasible if evaluation.feasible else ("Not feasible under all currently known hard constraints; unknown evidence remains disclosed.",),
        improvements=improvements,
        regressions=regressions + tuple(evaluation.critical_regressions),
        hard_constraints_passed=hard_passed,
        soft_constraints_violated=soft_warnings,
        ranking_reasons=ranking_reasons,
        non_dominated_alternatives=tuple(alternatives),
        estimated_evidence=evaluation.estimated_evidence,
        measured_evidence=evaluation.measured_evidence,
        skipped_evidence=evaluation.skipped_evidence,
        indeterminate_evidence=evaluation.indeterminate_evidence,
        required_approvals=("User must explicitly approve preview/execution.",) if strategy.required_approval else ("User selection is still required before execution.",),
        confidence=evaluation.objective_vector.confidence,
        runtime_estimate_seconds=strategy.estimated_evaluation_cost_seconds,
        limitations=tuple(strategy.limitations) + tuple(evaluation.limitations),
    )


def explanation_markdown(explanation: StrategyExplanation) -> str:
    lines = [f"### Strategy `{explanation.strategy_id}`", "", "- This is a bounded recommendation, not a global optimum.", "", "**Why generated**"]
    lines.extend(f"- {item}" for item in explanation.why_generated or ("Not recorded.",))
    lines.append("\n**Trade-offs**")
    lines.extend(f"- Improvement: {item}" for item in explanation.improvements or ("No improvement evidence recorded.",))
    lines.extend(f"- Regression/limitation: {item}" for item in explanation.regressions or ("No regression evidence recorded.",))
    lines.append("\n**Evidence**")
    lines.append(f"- Measured: {', '.join(explanation.measured_evidence) or 'none'}")
    lines.append(f"- Estimated: {', '.join(explanation.estimated_evidence) or 'none'}")
    lines.append(f"- Skipped/indeterminate: {', '.join(explanation.skipped_evidence) or 'none'}")
    lines.append(f"- Confidence: {explanation.confidence}")
    lines.append(f"- Runtime estimate: {explanation.runtime_estimate_seconds:.3f}s")
    return "\n".join(lines) + "\n"


explain_recommendation = explain_strategy


__all__ = ("explain_recommendation", "explain_strategy", "explanation_markdown")
