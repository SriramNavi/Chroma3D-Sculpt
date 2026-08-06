"""Blender-reference-free contracts for Sprint 6 intelligent optimization.

The Sprint 6 layer is deliberately a deterministic data/service boundary.  It
stores identities, hashes, bounded evidence, and scalar objective values only;
Blender objects and raw geometry never cross this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json
import math
from typing import Any, Mapping


INTELLIGENT_STRATEGY_SCHEMA_VERSION = "1.0"
STRATEGY_SET_SCHEMA_VERSION = "1.0"
SEARCH_POLICY_SCHEMA_VERSION = "1.0"
CONSTRAINT_SET_SCHEMA_VERSION = "1.0"
PARETO_FRONTIER_SCHEMA_VERSION = "1.0"
STRATEGY_RANKING_SCHEMA_VERSION = "1.0"
STRATEGY_EXPLANATION_SCHEMA_VERSION = "1.0"
OPTIMIZATION_HISTORY_SCHEMA_VERSION = "1.0"
INTELLIGENT_OPTIMIZATION_AUDIT_SCHEMA_VERSION = "1.0"


class SearchMode(str, Enum):
    FAST = "FAST"
    STANDARD = "STANDARD"
    DEEP = "DEEP"
    CUSTOM = "CUSTOM"


class OptimizationOperationType(str, Enum):
    """Stable Sprint 5 operation vocabulary reused by Sprint 6."""

    UNIFORM_SCALE = "UNIFORM_SCALE"
    ORIENTATION = "ORIENTATION"
    BUILD_PLATE_TRANSLATION = "BUILD_PLATE_TRANSLATION"
    BASE_STABILIZATION = "BASE_STABILIZATION"
    REPAIR_REUSE = "REPAIR_REUSE"
    DECIMATION = "DECIMATION"
    EXPERIMENTAL_REMESH = "EXPERIMENTAL_REMESH"
    COMBINED_SCALE_ORIENTATION = "COMBINED_SCALE_ORIENTATION"


class ConstraintSeverity(str, Enum):
    HARD = "HARD"
    SOFT = "SOFT"


class ConstraintKind(str, Enum):
    SOURCE_PROTECTED = "SOURCE_PROTECTED"
    ALLOWED_OPERATION = "ALLOWED_OPERATION"
    MAX_DEPTH = "MAX_DEPTH"
    SCALE_RANGE = "SCALE_RANGE"
    ORIENTATION_COUNT = "ORIENTATION_COUNT"
    BASE_GEOMETRY = "BASE_GEOMETRY"
    DECIMATION_RATIO = "DECIMATION_RATIO"
    FIDELITY_STATUS = "FIDELITY_STATUS"
    CRITICAL_DEFECT = "CRITICAL_DEFECT"
    BUILD_VOLUME_FIT = "BUILD_VOLUME_FIT"
    MIN_WALL_THICKNESS = "MIN_WALL_THICKNESS"
    MIN_THIN_FEATURE = "MIN_THIN_FEATURE"
    MAX_GEOMETRIC_DEVIATION = "MAX_GEOMETRIC_DEVIATION"
    MAX_AREA_DRIFT = "MAX_AREA_DRIFT"
    MAX_VOLUME_DRIFT = "MAX_VOLUME_DRIFT"
    MAX_TRIANGLE_COUNT_CHANGE = "MAX_TRIANGLE_COUNT_CHANGE"
    MIN_CONFIDENCE = "MIN_CONFIDENCE"
    EXPERIMENTAL_OPERATION = "EXPERIMENTAL_OPERATION"
    MIN_SUPPORT_RISK = "MIN_SUPPORT_RISK"
    MIN_BRIDGE_RISK = "MIN_BRIDGE_RISK"
    MIN_CONTACT = "MIN_CONTACT"
    MAX_HEIGHT = "MAX_HEIGHT"
    MIN_FIDELITY = "MIN_FIDELITY"
    MIN_WALL_PRESERVATION = "MIN_WALL_PRESERVATION"
    MIN_FEATURE_PRESERVATION = "MIN_FEATURE_PRESERVATION"
    MIN_BUILD_FIT = "MIN_BUILD_FIT"


class ConstraintState(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    INDETERMINATE = "INDETERMINATE"
    SKIPPED_LIMIT = "SKIPPED_LIMIT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class StrategyGenerationReason(str, Enum):
    OBJECTIVE_ALIGNMENT = "OBJECTIVE_ALIGNMENT"
    CANDIDATE_FAMILY = "CANDIDATE_FAMILY"
    OPERATION_ORDER = "OPERATION_ORDER"
    CONSTRAINT_SATISFACTION = "CONSTRAINT_SATISFACTION"
    PARETO_DIVERSITY = "PARETO_DIVERSITY"
    USER_CUSTOM = "USER_CUSTOM"
    BASELINE = "BASELINE"


class StrategyState(str, Enum):
    GENERATED = "GENERATED"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    DOMINATED = "DOMINATED"
    NON_DOMINATED = "NON_DOMINATED"
    RANKED = "RANKED"
    RECOMMENDED = "RECOMMENDED"
    REJECTED = "REJECTED"
    SELECTED = "SELECTED"
    PREVIEWED = "PREVIEWED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    STALE = "STALE"
    CANCELLED = "CANCELLED"


class EvidenceState(str, Enum):
    ESTIMATED = "ESTIMATED"
    MEASURED = "MEASURED"
    PARTIAL = "PARTIAL"
    INDETERMINATE = "INDETERMINATE"
    SKIPPED_LIMIT = "SKIPPED_LIMIT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ObjectiveDirection(str, Enum):
    MINIMIZE = "MINIMIZE"
    MAXIMIZE = "MAXIMIZE"


class ObjectiveMetric(str, Enum):
    BUILD_VOLUME_FIT = "build_volume_fit"
    WALL_THICKNESS_PRESERVATION = "wall_thickness_preservation"
    THIN_FEATURE_PRESERVATION = "thin_feature_preservation"
    OVERHANG_RISK = "overhang_risk"
    BRIDGE_RISK = "bridge_risk"
    SUPPORT_RISK = "support_risk"
    CONTACT_QUALITY = "contact_quality"
    HEIGHT = "height"
    FLOATING_COMPONENTS = "floating_components"
    TOPOLOGY_CLEANLINESS = "topology_cleanliness"
    GEOMETRY_FIDELITY = "geometry_fidelity"
    TRIANGLE_COUNT = "triangle_count"
    RESIN_ADVISORY = "resin_advisory"
    PRINTABILITY_SCORE = "printability_score"
    ADVANCED_PREPARATION_SCORE = "advanced_preparation_score"
    CONTROLLED_OPTIMIZATION_SCORE = "controlled_optimization_score"
    RUNTIME_COST = "runtime_cost"
    MEMORY_OBSERVATION = "memory_observation"
    OPERATION_COUNT = "operation_count"
    RISK_COUNT = "risk_count"
    CRITICAL_REGRESSION_COUNT = "critical_regression_count"


class DominanceState(str, Enum):
    DOMINATES = "DOMINATES"
    DOMINATED = "DOMINATED"
    NON_DOMINATED = "NON_DOMINATED"
    EQUAL = "EQUAL"
    INCOMPARABLE = "INCOMPARABLE"


class RankingMethod(str, Enum):
    WEIGHTED_SUM = "WEIGHTED_SUM"
    WEIGHTED_TCHEBYCHEFF = "WEIGHTED_TCHEBYCHEFF"
    LEXICOGRAPHIC = "LEXICOGRAPHIC"
    CONSTRAINT_FIRST = "CONSTRAINT_FIRST"
    BALANCED_DISTANCE_TO_IDEAL = "BALANCED_DISTANCE_TO_IDEAL"
    USER_PRIORITY = "USER_PRIORITY"
    FIDELITY_FIRST = "FIDELITY_FIRST"
    MINIMUM_SUPPORTS = "MINIMUM_SUPPORTS"
    FIT_TO_PRINTER = "FIT_TO_PRINTER"
    STABLE_BASE = "STABLE_BASE"
    LIGHTWEIGHT = "LIGHTWEIGHT"


class IntelligentSessionState(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    INPUTS_READY = "INPUTS_READY"
    SEARCHING = "SEARCHING"
    SEARCH_COMPLETE = "SEARCH_COMPLETE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    PREVIEW_ACTIVE = "PREVIEW_ACTIVE"
    EXECUTING = "EXECUTING"
    COMPARISON_READY = "COMPARISON_READY"
    ACCEPTED = "ACCEPTED"
    DISCARDED = "DISCARDED"
    FAILED = "FAILED"
    STALE = "STALE"
    CANCELLED = "CANCELLED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


def _finite(value: Any, name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number.")
    result = float(value)
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        raise ValueError(f"{name} must be finite and >= {minimum}.")
    return result


_GEOMETRY_KEYS = {"geometry", "raw_geometry", "vertices", "edges", "polygons", "loops", "coordinates"}


def _plain(value: Any, path: str = "root") -> Any:
    """Convert only safe JSON-like values and fail closed on Blender objects."""

    if isinstance(value, Enum):
        return value.value
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contains NaN or infinity.")
        return value
    if is_dataclass(value):
        return {item.name: _plain(getattr(value, item.name), f"{path}.{item.name}") for item in fields(value)}
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in sorted(value.items(), key=lambda pair: str(pair[0])):
            name = str(key)
            if name.lower() in _GEOMETRY_KEYS and isinstance(item, (list, tuple, Mapping)):
                raise ValueError(f"{path}.{name} contains raw geometry data.")
            result[name] = _plain(item, f"{path}.{name}")
        return result
    if isinstance(value, (tuple, list)):
        return [_plain(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, (set, frozenset, bytes, bytearray)):
        raise ValueError(f"{path} is not deterministically serializable.")
    if hasattr(value, "as_pointer") or hasattr(value, "bl_rna") or str(type(value).__module__).startswith("bpy"):
        raise ValueError(f"{path} contains a Blender reference.")
    raise ValueError(f"{path} contains unsupported value type {type(value).__name__}.")


def plain_value(value: Any) -> Any:
    return _plain(value)


def stable_hash(value: Any) -> str:
    payload = json.dumps(_plain(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class DeterministicModel:
    def to_dict(self) -> dict[str, Any]:
        result = _plain(self)
        if not isinstance(result, dict):
            raise ValueError("A deterministic model must serialize to an object.")
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True, slots=True)
class SearchBudget(DeterministicModel):
    max_generated_strategies: int = 32
    max_evaluated_strategies: int = 16
    max_workspace_previews: int = 2
    max_operation_steps: int = 64
    max_strategy_depth: int = 3
    max_branch_factor: int = 6
    max_operation_sequence_permutations: int = 24
    max_pareto_points: int = 16
    max_ranking_results: int = 32
    max_wall_time_seconds: float = 30.0
    max_per_strategy_seconds: float = 5.0
    max_memory_observation_mb: float = 512.0
    max_history_entries: int = 128
    max_export_bytes: int = 2_000_000

    def __post_init__(self) -> None:
        integer_fields = (
            "max_generated_strategies", "max_evaluated_strategies", "max_workspace_previews",
            "max_operation_steps", "max_strategy_depth", "max_branch_factor",
            "max_operation_sequence_permutations", "max_pareto_points", "max_ranking_results",
            "max_history_entries", "max_export_bytes",
        )
        maxima = {
            "max_generated_strategies": 256, "max_evaluated_strategies": 128, "max_workspace_previews": 16,
            "max_operation_steps": 512, "max_strategy_depth": 8, "max_branch_factor": 16,
            "max_operation_sequence_permutations": 256, "max_pareto_points": 128, "max_ranking_results": 256,
            "max_history_entries": 1024, "max_export_bytes": 20_000_000,
        }
        for name in integer_fields:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer.")
            if value > maxima[name]:
                raise ValueError(f"{name} exceeds the safe maximum of {maxima[name]}.")
        for name in ("max_wall_time_seconds", "max_per_strategy_seconds", "max_memory_observation_mb"):
            value = _finite(getattr(self, name), name, minimum=0.001)
            if value > {"max_wall_time_seconds": 900.0, "max_per_strategy_seconds": 120.0, "max_memory_observation_mb": 4096.0}[name]:
                raise ValueError(f"{name} exceeds the safe maximum.")


@dataclass(slots=True)
class SearchBudgetUsage(DeterministicModel):
    generated_strategies: int = 0
    evaluated_strategies: int = 0
    workspace_previews: int = 0
    operation_steps: int = 0
    wall_time_seconds: float = 0.0
    memory_observation_mb: float | None = None
    history_entries: int = 0
    exported_bytes: int = 0
    exhausted_dimensions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for name in ("generated_strategies", "evaluated_strategies", "workspace_previews", "operation_steps", "history_entries", "exported_bytes"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer.")
        _finite(self.wall_time_seconds, "wall_time_seconds", minimum=0.0)
        if self.memory_observation_mb is not None:
            _finite(self.memory_observation_mb, "memory_observation_mb", minimum=0.0)


@dataclass(frozen=True, slots=True)
class OptimizationConstraint(DeterministicModel):
    constraint_id: str
    kind: ConstraintKind | str
    severity: ConstraintSeverity | str = ConstraintSeverity.HARD
    actual_key: str = ""
    minimum: float | None = None
    maximum: float | None = None
    required_value: Any = None
    enabled: bool = True
    evidence_required: bool = True
    confidence_threshold: str = "LOW"
    description: str = ""
    provenance: str = "Sprint 6 deterministic constraint"

    def __post_init__(self) -> None:
        if not self.constraint_id:
            raise ValueError("constraint_id is required.")
        object.__setattr__(self, "kind", ConstraintKind(self.kind))
        object.__setattr__(self, "severity", ConstraintSeverity(self.severity))
        if not isinstance(self.enabled, bool) or not isinstance(self.evidence_required, bool):
            raise ValueError("Constraint flags must be booleans.")
        if self.minimum is not None:
            _finite(self.minimum, f"{self.constraint_id}.minimum")
        if self.maximum is not None:
            _finite(self.maximum, f"{self.constraint_id}.maximum")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError(f"Constraint {self.constraint_id} has conflicting bounds.")
        if not self.actual_key:
            object.__setattr__(self, "actual_key", self.kind.value.lower())


@dataclass(frozen=True, slots=True)
class ConstraintSet(DeterministicModel):
    constraints: tuple[OptimizationConstraint, ...] = ()
    schema_version: str = CONSTRAINT_SET_SCHEMA_VERSION
    set_id: str = "default-constraint-set"
    provenance: str = "Sprint 6 safe defaults"
    constraint_set_hash: str = ""

    def __post_init__(self) -> None:
        normalized = tuple(self.constraints)
        object.__setattr__(self, "constraints", normalized)
        seen: set[str] = set()
        for constraint in normalized:
            if not isinstance(constraint, OptimizationConstraint):
                raise TypeError("ConstraintSet entries must be OptimizationConstraint values.")
            if constraint.constraint_id in seen:
                raise ValueError(f"Duplicate constraint ID: {constraint.constraint_id}")
            seen.add(constraint.constraint_id)
        bounds: dict[str, tuple[float | None, float | None]] = {}
        for constraint in normalized:
            prior = bounds.get(constraint.actual_key)
            if prior is not None:
                lower_values = [value for value in (prior[0], constraint.minimum) if value is not None]
                upper_values = [value for value in (prior[1], constraint.maximum) if value is not None]
                lower = max(lower_values) if lower_values else None
                upper = min(upper_values) if upper_values else None
                if lower is not None and upper is not None and lower > upper:
                    raise ValueError(f"Conflicting bounds for constraint key {constraint.actual_key!r}.")
                bounds[constraint.actual_key] = (lower, upper)
            else:
                bounds[constraint.actual_key] = (constraint.minimum, constraint.maximum)
        if not self.set_id or not self.provenance:
            raise ValueError("Constraint set identity and provenance are required.")
        if not self.constraint_set_hash:
            object.__setattr__(self, "constraint_set_hash", stable_hash({"schema_version": self.schema_version, "set_id": self.set_id, "constraints": normalized}))


@dataclass(frozen=True, slots=True)
class SearchPolicy(DeterministicModel):
    policy_id: str = "s6-standard"
    search_mode: SearchMode | str = SearchMode.STANDARD
    enabled_strategy_families: tuple[str, ...] = ("Scale only", "Orientation only", "Balanced")
    allowed_operation_families: tuple[str, ...] = ("UNIFORM_SCALE", "ORIENTATION", "BUILD_PLATE_TRANSLATION")
    budget: SearchBudget = field(default_factory=SearchBudget)
    objective_profile: Mapping[str, Any] = field(default_factory=dict)
    constraints: ConstraintSet = field(default_factory=ConstraintSet)
    ranking_method: str = "CONSTRAINT_FIRST"
    tie_breaking_policy: tuple[str, ...] = (
        "FEWER_HARD_WARNINGS", "FEWER_CRITICAL_REGRESSIONS", "HIGHER_CONFIDENCE",
        "HIGHER_FIDELITY", "FEWER_OPERATIONS", "LOWER_RUNTIME", "STABLE_FINGERPRINT",
    )
    pruning_rules: tuple[str, ...] = ("DUPLICATE", "HARD_CONSTRAINT", "POLICY_LIMIT", "BUDGET_LIMIT", "UNSUPPORTED_COMBINATION")
    duplicate_tolerance: float = 0.0
    dominance_tolerance: float = 1e-9
    deterministic_seed: str = "sprint6-deterministic-v1"
    experimental_operations_enabled: bool = False
    explicit_experimental_enablement: bool = False
    provenance: str = "Sprint 6 deterministic bounded search policy"
    policy_version: str = SEARCH_POLICY_SCHEMA_VERSION
    policy_hash: str = ""

    def __post_init__(self) -> None:
        if not self.policy_id or not self.provenance or not self.deterministic_seed:
            raise ValueError("Search policy identity, provenance, and deterministic seed are required.")
        object.__setattr__(self, "search_mode", SearchMode(self.search_mode))
        if not isinstance(self.experimental_operations_enabled, bool) or not isinstance(self.explicit_experimental_enablement, bool):
            raise ValueError("Experimental search policy flags must be booleans.")
        if self.experimental_operations_enabled and not self.explicit_experimental_enablement:
            raise ValueError("Experimental operations require explicit enablement.")
        try:
            RankingMethod(self.ranking_method)
        except ValueError as exc:
            raise ValueError(f"Unknown ranking method: {self.ranking_method!r}") from exc
        _finite(self.duplicate_tolerance, "duplicate_tolerance", minimum=0.0)
        _finite(self.dominance_tolerance, "dominance_tolerance", minimum=0.0)
        if not self.allowed_operation_families:
            raise ValueError("At least one allowed operation family is required.")
        seen_operations: set[str] = set()
        for operation in self.allowed_operation_families:
            try:
                normalized = OptimizationOperationType(operation).value
            except ValueError as exc:
                raise ValueError(f"Unknown operation family: {operation!r}") from exc
            if normalized in seen_operations:
                raise ValueError(f"Duplicate operation family: {normalized}")
            seen_operations.add(normalized)
        if any(operation in {OptimizationOperationType.DECIMATION.value, OptimizationOperationType.EXPERIMENTAL_REMESH.value} for operation in seen_operations) and not self.experimental_operations_enabled:
            raise ValueError("Experimental operation families require explicit enablement.")
        if self.policy_hash == "":
            object.__setattr__(self, "policy_hash", stable_hash({
                "policy_id": self.policy_id, "policy_version": self.policy_version,
                "search_mode": self.search_mode, "enabled_strategy_families": self.enabled_strategy_families,
                "allowed_operation_families": self.allowed_operation_families, "budget": self.budget,
                "objective_profile": self.objective_profile, "constraints": self.constraints, "ranking_method": self.ranking_method,
                "tie_breaking_policy": self.tie_breaking_policy, "pruning_rules": self.pruning_rules,
                "duplicate_tolerance": self.duplicate_tolerance, "dominance_tolerance": self.dominance_tolerance,
                "deterministic_seed": self.deterministic_seed, "experimental_operations_enabled": self.experimental_operations_enabled,
            }))


@dataclass(frozen=True, slots=True)
class ConstraintEvaluation(DeterministicModel):
    constraint_id: str
    severity: ConstraintSeverity | str
    state: ConstraintState | str
    actual_value: Any = None
    required_bound: Any = None
    evidence_source: str = ""
    confidence: str = "LOW"
    limitation: str = ""
    rejection_reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "severity", ConstraintSeverity(self.severity))
        object.__setattr__(self, "state", ConstraintState(self.state))
        if not self.constraint_id:
            raise ValueError("constraint_id is required.")


@dataclass(frozen=True, slots=True)
class StrategyStep(DeterministicModel):
    order: int
    candidate_id: str
    operation: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    approval_required: bool = False
    experimental: bool = False
    estimated_cost_seconds: float = 0.0
    expected_objective_effects: Mapping[str, float] = field(default_factory=dict)
    source_evidence: tuple[Mapping[str, Any], ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.order, bool) or not isinstance(self.order, int) or self.order < 1:
            raise ValueError("Strategy step order must be a positive integer.")
        if not self.candidate_id or not self.operation:
            raise ValueError("Strategy step candidate_id and operation are required.")
        if not isinstance(self.approval_required, bool) or not isinstance(self.experimental, bool):
            raise ValueError("Strategy step flags must be booleans.")
        _finite(self.estimated_cost_seconds, "estimated_cost_seconds", minimum=0.0)


@dataclass(frozen=True, slots=True)
class IntelligentStrategy(DeterministicModel):
    strategy_id: str
    fingerprint: str
    generation_family: str
    generation_reason: StrategyGenerationReason | str
    steps: tuple[StrategyStep, ...]
    source_evidence: tuple[Mapping[str, Any], ...] = ()
    objective_profile: Mapping[str, Any] = field(default_factory=dict)
    policy_hash: str = ""
    constraint_set_hash: str = ""
    process_context_hash: str = ""
    feature_flag_hash: str = ""
    implementation_fingerprint: str = ""
    estimated_evaluation_cost_seconds: float = 0.0
    required_approval: bool = True
    limitations: tuple[str, ...] = ()
    state: StrategyState | str = StrategyState.GENERATED
    rejection_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.strategy_id or not self.fingerprint or not self.generation_family:
            raise ValueError("Strategy identity and family are required.")
        object.__setattr__(self, "generation_reason", StrategyGenerationReason(self.generation_reason))
        object.__setattr__(self, "state", StrategyState(self.state))
        if not self.steps:
            raise ValueError("A strategy must contain at least one ordered step.")
        if tuple(step.order for step in self.steps) != tuple(range(1, len(self.steps) + 1)):
            raise ValueError("Strategy steps must be contiguous and ordered.")
        if not isinstance(self.required_approval, bool):
            raise ValueError("required_approval must be a boolean.")
        _finite(self.estimated_evaluation_cost_seconds, "estimated_evaluation_cost_seconds", minimum=0.0)


@dataclass(frozen=True, slots=True)
class ObjectiveVector(DeterministicModel):
    raw_values: Mapping[str, float | None] = field(default_factory=dict)
    normalized_values: Mapping[str, float | None] = field(default_factory=dict)
    directions: Mapping[str, ObjectiveDirection | str] = field(default_factory=dict)
    evidence_states: Mapping[str, EvidenceState | str] = field(default_factory=dict)
    confidence: str = "LOW"
    objective_hash: str = ""

    def __post_init__(self) -> None:
        keys = set(self.raw_values) | set(self.normalized_values) | set(self.directions) | set(self.evidence_states)
        normalized_directions = dict(self.directions)
        normalized_states = dict(self.evidence_states)
        for key in keys:
            if key in normalized_directions:
                normalized_directions[key] = ObjectiveDirection(normalized_directions[key])
            else:
                normalized_directions[key] = ObjectiveDirection.MAXIMIZE
            if key in normalized_states:
                normalized_states[key] = EvidenceState(normalized_states[key])
            else:
                normalized_states[key] = EvidenceState.INDETERMINATE
        for name, values in (("raw_values", self.raw_values), ("normalized_values", self.normalized_values)):
            for key, value in values.items():
                if value is not None:
                    _finite(value, f"{name}[{key!r}]")
        object.__setattr__(self, "directions", normalized_directions)
        object.__setattr__(self, "evidence_states", normalized_states)
        if not self.objective_hash:
            object.__setattr__(self, "objective_hash", stable_hash({"raw_values": self.raw_values, "normalized_values": self.normalized_values, "directions": normalized_directions, "evidence_states": normalized_states}))


@dataclass(frozen=True, slots=True)
class StrategyEvaluation(DeterministicModel):
    strategy_id: str
    evaluation_state: EvidenceState | str
    objective_vector: ObjectiveVector
    constraint_evaluations: tuple[ConstraintEvaluation, ...] = ()
    feasible: bool = False
    measured_evidence: tuple[str, ...] = ()
    estimated_evidence: tuple[str, ...] = ()
    skipped_evidence: tuple[str, ...] = ()
    indeterminate_evidence: tuple[str, ...] = ()
    critical_regressions: tuple[str, ...] = ()
    operation_audit: tuple[Mapping[str, Any], ...] = ()
    runtime_seconds: float = 0.0
    memory_observation_mb: float | None = None
    limitations: tuple[str, ...] = ()
    stale_reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "evaluation_state", EvidenceState(self.evaluation_state))
        if not isinstance(self.feasible, bool):
            raise ValueError("feasible must be a boolean.")
        _finite(self.runtime_seconds, "runtime_seconds", minimum=0.0)
        if self.memory_observation_mb is not None:
            _finite(self.memory_observation_mb, "memory_observation_mb", minimum=0.0)


@dataclass(frozen=True, slots=True)
class PruningRecord(DeterministicModel):
    strategy_id: str
    fingerprint: str
    reason_code: str
    reason: str
    evidence: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StrategySet(DeterministicModel):
    strategies: tuple[IntelligentStrategy, ...] = ()
    pruned: tuple[PruningRecord, ...] = ()
    schema_version: str = STRATEGY_SET_SCHEMA_VERSION
    set_id: str = ""
    source_signature: str = ""
    policy_hash: str = ""
    constraint_set_hash: str = ""
    process_context_hash: str = ""
    feature_flag_hash: str = ""
    implementation_fingerprint: str = ""
    budget_usage: SearchBudgetUsage = field(default_factory=SearchBudgetUsage)
    status: str = "COMPLETE"
    strategy_set_hash: str = ""
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.set_id:
            object.__setattr__(self, "set_id", f"strategy-set-{stable_hash(self.strategies)[:16]}")
        if not self.strategy_set_hash:
            object.__setattr__(self, "strategy_set_hash", stable_hash({"strategies": self.strategies, "pruned": self.pruned, "policy_hash": self.policy_hash, "constraint_set_hash": self.constraint_set_hash}))


@dataclass(frozen=True, slots=True)
class DominanceRecord(DeterministicModel):
    left_strategy_id: str
    right_strategy_id: str
    state: DominanceState | str
    better_objectives: tuple[str, ...] = ()
    worse_objectives: tuple[str, ...] = ()
    equal_objectives: tuple[str, ...] = ()
    reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", DominanceState(self.state))


@dataclass(frozen=True, slots=True)
class ParetoPoint(DeterministicModel):
    strategy_id: str
    objective_vector: ObjectiveVector
    feasible: bool
    dominance_state: DominanceState | str = DominanceState.NON_DOMINATED
    dominance_reason: str = ""
    frontier_index: int = -1

    def __post_init__(self) -> None:
        object.__setattr__(self, "dominance_state", DominanceState(self.dominance_state))
        if not isinstance(self.feasible, bool):
            raise ValueError("feasible must be a boolean.")


@dataclass(frozen=True, slots=True)
class ParetoFrontier(DeterministicModel):
    points: tuple[ParetoPoint, ...] = ()
    dominated_strategy_ids: tuple[str, ...] = ()
    dominance_records: tuple[DominanceRecord, ...] = ()
    schema_version: str = PARETO_FRONTIER_SCHEMA_VERSION
    frontier_id: str = ""
    tolerance: float = 0.0
    max_points: int = 128
    strategy_set_hash: str = ""
    frontier_hash: str = ""
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _finite(self.tolerance, "tolerance", minimum=0.0)
        if isinstance(self.max_points, bool) or not isinstance(self.max_points, int) or self.max_points < 1:
            raise ValueError("max_points must be a positive integer.")
        if not self.frontier_id:
            object.__setattr__(self, "frontier_id", f"pareto-{stable_hash(self.points)[:16]}")
        if not self.frontier_hash:
            object.__setattr__(self, "frontier_hash", stable_hash({"points": self.points, "dominated": self.dominated_strategy_ids, "tolerance": self.tolerance}))


@dataclass(frozen=True, slots=True)
class RankingRecord(DeterministicModel):
    strategy_id: str
    rank: int
    method: RankingMethod | str
    score: float
    non_dominated: bool
    tie_group: str = ""
    tie_break_trace: tuple[str, ...] = ()
    objective_contributions: Mapping[str, float] = field(default_factory=dict)
    rationale: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "method", RankingMethod(self.method))
        if isinstance(self.rank, bool) or not isinstance(self.rank, int) or self.rank < 1:
            raise ValueError("rank must be a positive integer.")
        if not isinstance(self.non_dominated, bool):
            raise ValueError("non_dominated must be a boolean.")
        _finite(self.score, "score")


@dataclass(frozen=True, slots=True)
class RecommendationRecord(DeterministicModel):
    strategy_id: str
    ranking_method: RankingMethod | str
    rank: int
    wording: str
    confidence: str
    is_automatic_execution: bool = False
    required_user_approval: bool = True
    alternatives: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "ranking_method", RankingMethod(self.ranking_method))
        if isinstance(self.rank, bool) or not isinstance(self.rank, int) or self.rank < 1:
            raise ValueError("Recommendation rank must be positive.")
        if self.is_automatic_execution:
            raise ValueError("Sprint 6 recommendations may never auto-execute.")


@dataclass(frozen=True, slots=True)
class StrategyExplanation(DeterministicModel):
    strategy_id: str
    why_generated: tuple[str, ...] = ()
    why_feasible: tuple[str, ...] = ()
    improvements: tuple[str, ...] = ()
    regressions: tuple[str, ...] = ()
    hard_constraints_passed: tuple[str, ...] = ()
    soft_constraints_violated: tuple[str, ...] = ()
    ranking_reasons: tuple[str, ...] = ()
    non_dominated_alternatives: tuple[str, ...] = ()
    estimated_evidence: tuple[str, ...] = ()
    measured_evidence: tuple[str, ...] = ()
    skipped_evidence: tuple[str, ...] = ()
    indeterminate_evidence: tuple[str, ...] = ()
    required_approvals: tuple[str, ...] = ()
    confidence: str = "LOW"
    runtime_estimate_seconds: float = 0.0
    limitations: tuple[str, ...] = ()
    advisory_disclaimer: str = "This is a bounded software recommendation, not a global optimum or print-success guarantee."

    def __post_init__(self) -> None:
        _finite(self.runtime_estimate_seconds, "runtime_estimate_seconds", minimum=0.0)


@dataclass(frozen=True, slots=True)
class StrategyHistoryEntry(DeterministicModel):
    entry_id: str
    recorded_at: str
    source_identity: Mapping[str, Any]
    source_signature: str
    strategy_fingerprint: str
    objective_profile: Mapping[str, Any]
    search_policy: Mapping[str, Any]
    constraints: Mapping[str, Any]
    evaluation: Mapping[str, Any]
    rank: int | None = None
    recommendation_state: str = ""
    preview_state: str = "NOT_RUN"
    execution_state: str = "NOT_RUN"
    comparison: Mapping[str, Any] = field(default_factory=dict)
    accepted_state: str = "NOT_DECIDED"
    software_version: str = ""
    schema_versions: Mapping[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class StrategyHistory(DeterministicModel):
    entries: list[StrategyHistoryEntry] = field(default_factory=list)
    schema_version: str = OPTIMIZATION_HISTORY_SCHEMA_VERSION
    history_id: str = "session-history"
    limitations: list[str] = field(default_factory=lambda: ["Local session history only; no telemetry, cloud sync, or hidden learning."])


@dataclass(slots=True)
class IntelligentOptimizationSession(DeterministicModel):
    session_id: str
    started_at: str
    state: IntelligentSessionState | str = IntelligentSessionState.NOT_STARTED
    source_identity: dict[str, Any] = field(default_factory=dict)
    source_signature: str = ""
    source_transform_signature: str = ""
    hardware_profile_hash: str = ""
    material_profile_hash: str = ""
    process_context_hash: str = ""
    feature_flag_hash: str = ""
    performance_registry_version: str = ""
    sprint5_policy_hash: str = ""
    sprint5_objective_hash: str = ""
    sprint5_candidate_set_hash: str = ""
    search_policy_hash: str = ""
    constraint_set_hash: str = ""
    objective_profile_hash: str = ""
    strategy_set_hash: str = ""
    pareto_frontier_hash: str = ""
    ranking_method_hash: str = ""
    implementation_fingerprint: str = ""
    strategy_set: StrategySet | None = None
    evaluations: list[StrategyEvaluation] = field(default_factory=list)
    frontier: ParetoFrontier | None = None
    rankings: list[RankingRecord] = field(default_factory=list)
    recommendation: RecommendationRecord | None = None
    explanations: list[StrategyExplanation] = field(default_factory=list)
    history: StrategyHistory = field(default_factory=StrategyHistory)
    selected_strategy_id: str = ""
    preview_audit: list[Mapping[str, Any]] = field(default_factory=list)
    execution_audit: list[Mapping[str, Any]] = field(default_factory=list)
    stale_events: list[Mapping[str, Any]] = field(default_factory=list)
    cancellation_events: list[Mapping[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=lambda: ["Bounded deterministic search; no global optimum or print-success guarantee."])
    budget_usage: SearchBudgetUsage = field(default_factory=SearchBudgetUsage)

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", IntelligentSessionState(self.state))


@dataclass(frozen=True, slots=True)
class IntelligentOptimizationAudit(DeterministicModel):
    schema_version: str
    extension_version: str
    blender_version: str
    exported_at: str
    source_identity: Mapping[str, Any]
    source_signature: str
    hardware_profile_hash: str
    material_profile_hash: str
    process_context_hash: str
    feature_flag_hash: str
    performance_registry_version: str
    sprint5_policy: Mapping[str, Any]
    sprint5_objectives: Mapping[str, Any]
    sprint5_candidates: Mapping[str, Any]
    search_policy: Mapping[str, Any]
    constraints: Mapping[str, Any]
    budget: Mapping[str, Any]
    strategy_set: Mapping[str, Any]
    evaluations: tuple[Mapping[str, Any], ...]
    pareto_frontier: Mapping[str, Any]
    rankings: tuple[Mapping[str, Any], ...]
    recommendation: Mapping[str, Any] | None
    explanations: tuple[Mapping[str, Any], ...]
    selected_strategy_id: str
    preview_execution_audit: tuple[Mapping[str, Any], ...]
    sprint5_audit: Mapping[str, Any]
    history: Mapping[str, Any]
    stale_events: tuple[Mapping[str, Any], ...]
    cancellation_events: tuple[Mapping[str, Any], ...]
    warnings: tuple[str, ...]
    failures: tuple[str, ...]
    skipped_evidence: tuple[str, ...]
    advisory_disclaimer: str = (
        "Intelligent Optimization is deterministic, local, bounded software analysis. It does not use AI or LLMs, "
        "does not guarantee printability, does not slice, generate G-code, control a printer, or provide physical validation."
    )


__all__ = [name for name in globals() if not name.startswith("_")]
