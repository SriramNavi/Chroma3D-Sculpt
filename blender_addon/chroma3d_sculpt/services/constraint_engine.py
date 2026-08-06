"""Fail-closed hard/soft constraint evaluation for Sprint 6."""

from __future__ import annotations

from hashlib import sha256
import json
import math
from typing import Any, Iterable, Mapping

from ..models.intelligent_optimization_models import (
    ConstraintEvaluation,
    ConstraintKind,
    ConstraintSet,
    ConstraintSeverity,
    ConstraintState,
    EvidenceState,
    OptimizationConstraint,
    stable_hash,
)


_CONFIDENCE_ORDER = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}


def default_constraint_set(*, allowed_operations: Iterable[str] = (), experimental_enabled: bool = False) -> ConstraintSet:
    allowed = tuple(sorted(set(str(item) for item in allowed_operations)))
    if not allowed:
        allowed = ("UNIFORM_SCALE", "ORIENTATION", "BUILD_PLATE_TRANSLATION")
    constraints = [
        OptimizationConstraint("source-protected", ConstraintKind.SOURCE_PROTECTED, actual_key="source_protected", required_value=True, description="The protected source identity and geometry remain unchanged."),
        OptimizationConstraint("allowed-operations", ConstraintKind.ALLOWED_OPERATION, actual_key="operations_allowed", required_value=allowed, description="Every step belongs to the selected Sprint 5 operation policy."),
        OptimizationConstraint("strategy-depth", ConstraintKind.MAX_DEPTH, actual_key="strategy_depth", maximum=3, description="Strategy depth remains bounded by the search policy."),
        OptimizationConstraint("fidelity-status", ConstraintKind.FIDELITY_STATUS, actual_key="fidelity_status", required_value="PASS", description="A failed fidelity result cannot pass a hard constraint."),
        OptimizationConstraint("critical-defect", ConstraintKind.CRITICAL_DEFECT, actual_key="critical_defect_introduced", required_value=False, description="A new critical defect rejects a strategy."),
        OptimizationConstraint("experimental-operations", ConstraintKind.EXPERIMENTAL_OPERATION, actual_key="experimental_operation", required_value=experimental_enabled, description="Experimental operations require an explicit policy toggle."),
        OptimizationConstraint("max-geometric-deviation", ConstraintKind.MAX_GEOMETRIC_DEVIATION, actual_key="geometric_deviation", maximum=0.25, description="Geometric deviation remains within the Sprint 5 fidelity bound."),
        OptimizationConstraint("max-area-drift", ConstraintKind.MAX_AREA_DRIFT, actual_key="area_drift", maximum=0.25, description="Area drift remains bounded when measured."),
        OptimizationConstraint("max-volume-drift", ConstraintKind.MAX_VOLUME_DRIFT, actual_key="volume_drift", maximum=0.25, description="Volume drift remains bounded when measured."),
        OptimizationConstraint("min-confidence", ConstraintKind.MIN_CONFIDENCE, actual_key="confidence", required_value="LOW", description="Evidence must meet the selected minimum confidence."),
        OptimizationConstraint("soft-support-risk", ConstraintKind.MIN_SUPPORT_RISK, ConstraintSeverity.SOFT, actual_key="support_risk", maximum=1.0, description="Support risk is advisory and may be traded against fidelity."),
        OptimizationConstraint("soft-bridge-risk", ConstraintKind.MIN_BRIDGE_RISK, ConstraintSeverity.SOFT, actual_key="bridge_risk", maximum=1.0, description="Bridge risk is advisory and remains visible in ranking."),
        OptimizationConstraint("soft-contact", ConstraintKind.MIN_CONTACT, ConstraintSeverity.SOFT, actual_key="contact_quality", minimum=0.0, description="Contact quality is an advisory preference."),
    ]
    return ConstraintSet(tuple(constraints), set_id="s6-default-constraints", provenance="Sprint 6 safe constraint defaults")


def validate_constraint_set(constraint_set: ConstraintSet) -> None:
    if not isinstance(constraint_set, ConstraintSet):
        raise TypeError("constraint_set must be a ConstraintSet.")
    seen: set[str] = set()
    bounds: dict[str, tuple[float | None, float | None]] = {}
    for constraint in constraint_set.constraints:
        if constraint.constraint_id in seen:
            raise ValueError(f"Duplicate constraint ID: {constraint.constraint_id}")
        seen.add(constraint.constraint_id)
        previous = bounds.get(constraint.actual_key)
        if previous is not None:
            lower = max(item for item in (previous[0], constraint.minimum) if item is not None) if any(item is not None for item in (previous[0], constraint.minimum)) else None
            upper = min(item for item in (previous[1], constraint.maximum) if item is not None) if any(item is not None for item in (previous[1], constraint.maximum)) else None
            if lower is not None and upper is not None and lower > upper:
                raise ValueError(f"Conflicting bounds for constraint key {constraint.actual_key!r}.")
            bounds[constraint.actual_key] = (lower, upper)
        else:
            bounds[constraint.actual_key] = (constraint.minimum, constraint.maximum)
    canonical = constraint_set.to_dict()
    expected = stable_hash({key: value for key, value in canonical.items() if key != "constraint_set_hash"})
    # A ConstraintSet created by the model hashes its exact identity.  Accept
    # older callers that supplied an explicit compatible hash but fail closed
    # for tampered values.
    if constraint_set.constraint_set_hash != stable_hash({"schema_version": constraint_set.schema_version, "set_id": constraint_set.set_id, "constraints": constraint_set.constraints}):
        raise ValueError("Constraint-set hash does not match its deterministic payload.")


def _state_for(key: str, evidence_states: Mapping[str, EvidenceState | str] | None) -> EvidenceState:
    if not evidence_states or key not in evidence_states:
        return EvidenceState.INDETERMINATE
    return EvidenceState(evidence_states[key])


def _confidence_pass(actual: Any, required: str) -> bool:
    return _CONFIDENCE_ORDER.get(str(actual).upper(), -1) >= _CONFIDENCE_ORDER.get(str(required).upper(), 1)


def _compare(constraint: OptimizationConstraint, actual: Any) -> tuple[bool, str]:
    if constraint.kind == ConstraintKind.ALLOWED_OPERATION:
        values = actual if isinstance(actual, (list, tuple, set)) else (actual,)
        allowed = constraint.required_value if isinstance(constraint.required_value, (list, tuple, set)) else (constraint.required_value,)
        invalid = sorted(set(str(value) for value in values) - set(str(value) for value in allowed))
        return not invalid, "Disallowed operation(s): " + ", ".join(invalid) if invalid else ""
    if constraint.kind == ConstraintKind.MIN_CONFIDENCE:
        passed = _confidence_pass(actual, str(constraint.required_value or constraint.confidence_threshold))
        return passed, "Evidence confidence is below the required threshold." if not passed else ""
    if constraint.minimum is not None or constraint.maximum is not None:
        if isinstance(actual, bool) or not isinstance(actual, (int, float)):
            return False, "A numeric bound requires numeric evidence."
        value = float(actual)
        if not math.isfinite(value):
            return False, "A numeric bound requires finite evidence."
        if constraint.minimum is not None and value < constraint.minimum:
            return False, f"Value {value} is below minimum {constraint.minimum}."
        if constraint.maximum is not None and value > constraint.maximum:
            return False, f"Value {value} is above maximum {constraint.maximum}."
        return True, ""
    if constraint.required_value is not None:
        if actual != constraint.required_value:
            return False, f"Actual value {actual!r} does not satisfy required value {constraint.required_value!r}."
    return True, ""


def evaluate_constraint(
    constraint: OptimizationConstraint,
    actual_values: Mapping[str, Any],
    *,
    evidence_states: Mapping[str, EvidenceState | str] | None = None,
    evidence_sources: Mapping[str, str] | None = None,
    confidence: str = "LOW",
) -> ConstraintEvaluation:
    if not constraint.enabled:
        return ConstraintEvaluation(constraint.constraint_id, constraint.severity, ConstraintState.NOT_APPLICABLE, evidence_source="disabled-by-policy", confidence=confidence, limitation="Constraint is disabled by the selected policy.")
    actual = actual_values.get(constraint.actual_key)
    state = _state_for(constraint.actual_key, evidence_states)
    source = (evidence_sources or {}).get(constraint.actual_key, "")
    if actual is None or state in {EvidenceState.INDETERMINATE, EvidenceState.SKIPPED_LIMIT}:
        result_state = ConstraintState.INDETERMINATE if state == EvidenceState.INDETERMINATE else ConstraintState.SKIPPED_LIMIT
        reason = "Unknown or skipped evidence cannot satisfy a hard constraint." if constraint.severity == ConstraintSeverity.HARD else "Evidence is unavailable; soft constraint remains a warning."
        return ConstraintEvaluation(constraint.constraint_id, constraint.severity, result_state, actual_value=actual, required_bound={"minimum": constraint.minimum, "maximum": constraint.maximum, "required": constraint.required_value}, evidence_source=source, confidence=confidence, limitation=reason, rejection_reason=reason if constraint.severity == ConstraintSeverity.HARD else "")
    passed, reason = _compare(constraint, actual)
    result_state = ConstraintState.PASS if passed else (ConstraintState.FAIL if constraint.severity == ConstraintSeverity.HARD else ConstraintState.WARNING)
    return ConstraintEvaluation(constraint.constraint_id, constraint.severity, result_state, actual_value=actual, required_bound={"minimum": constraint.minimum, "maximum": constraint.maximum, "required": constraint.required_value}, evidence_source=source, confidence=confidence, rejection_reason=reason if not passed else "")


def evaluate_constraints(
    constraint_set: ConstraintSet,
    actual_values: Mapping[str, Any],
    *,
    evidence_states: Mapping[str, EvidenceState | str] | None = None,
    evidence_sources: Mapping[str, str] | None = None,
    confidence: str = "LOW",
) -> tuple[ConstraintEvaluation, ...]:
    validate_constraint_set(constraint_set)
    return tuple(evaluate_constraint(item, actual_values, evidence_states=evidence_states, evidence_sources=evidence_sources, confidence=confidence) for item in constraint_set.constraints)


def constraints_are_feasible(evaluations: Iterable[ConstraintEvaluation]) -> bool:
    return not any(item.severity == ConstraintSeverity.HARD and item.state != ConstraintState.PASS for item in evaluations)


def constraint_set_hash(constraint_set: ConstraintSet) -> str:
    validate_constraint_set(constraint_set)
    return constraint_set.constraint_set_hash


def constraint_set_is_current(constraint_set: ConstraintSet, expected_hash: str) -> tuple[bool, str]:
    try:
        current = constraint_set_hash(constraint_set)
    except (TypeError, ValueError) as exc:
        return False, f"INVALID_CONSTRAINT_SET:{exc}"
    return (True, "CURRENT") if current == expected_hash else (False, "CONSTRAINT_SET_CHANGED")


__all__ = (
    "constraint_set_hash", "constraint_set_is_current", "constraints_are_feasible", "default_constraint_set",
    "evaluate_constraint", "evaluate_constraints", "validate_constraint_set",
)
