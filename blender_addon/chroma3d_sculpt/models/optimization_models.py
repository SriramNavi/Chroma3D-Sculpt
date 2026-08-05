"""Deterministic, Blender-reference-free models for Sprint 5 optimization.

The optimization layer deliberately serializes only names, ids, signatures and
bounded evidence.  Blender objects and geometry arrays never cross this model
boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime
from enum import Enum
import json
import math
from typing import Any, Mapping


OPTIMIZATION_PLAN_SCHEMA_VERSION = "1.0"
OPTIMIZATION_SESSION_SCHEMA_VERSION = "1.0"
OPTIMIZATION_AUDIT_SCHEMA_VERSION = "1.0"
OPTIMIZATION_COMPARISON_SCHEMA_VERSION = "1.0"
OPTIMIZATION_POLICY_SCHEMA_VERSION = "1.0"
OPTIMIZATION_CANDIDATE_SCHEMA_VERSION = "1.0"


class OptimizationObjective(str, Enum):
    BUILD_VOLUME_FIT = "BUILD_VOLUME_FIT"
    WALL_THICKNESS_PRESERVATION = "WALL_THICKNESS_PRESERVATION"
    THIN_FEATURE_PRESERVATION = "THIN_FEATURE_PRESERVATION"
    OVERHANG_REDUCTION = "OVERHANG_REDUCTION"
    BRIDGE_RISK_REDUCTION = "BRIDGE_RISK_REDUCTION"
    SUPPORT_RISK_REDUCTION = "SUPPORT_RISK_REDUCTION"
    CONTACT_IMPROVEMENT = "CONTACT_IMPROVEMENT"
    HEIGHT_REDUCTION = "HEIGHT_REDUCTION"
    FLOATING_COMPONENT_REDUCTION = "FLOATING_COMPONENT_REDUCTION"
    TOPOLOGY_CLEANLINESS = "TOPOLOGY_CLEANLINESS"
    GEOMETRY_FIDELITY = "GEOMETRY_FIDELITY"
    TRIANGLE_COUNT_REDUCTION = "TRIANGLE_COUNT_REDUCTION"
    RESIN_ADVISORY_IMPROVEMENT = "RESIN_ADVISORY_IMPROVEMENT"


class OptimizationOperationType(str, Enum):
    UNIFORM_SCALE = "UNIFORM_SCALE"
    ORIENTATION = "ORIENTATION"
    BUILD_PLATE_TRANSLATION = "BUILD_PLATE_TRANSLATION"
    BASE_STABILIZATION = "BASE_STABILIZATION"
    REPAIR_REUSE = "REPAIR_REUSE"
    DECIMATION = "DECIMATION"
    EXPERIMENTAL_REMESH = "EXPERIMENTAL_REMESH"
    COMBINED_SCALE_ORIENTATION = "COMBINED_SCALE_ORIENTATION"


class OptimizationSessionState(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    WORKSPACE_READY = "WORKSPACE_READY"
    PLAN_READY = "PLAN_READY"
    OPERATION_IN_PROGRESS = "OPERATION_IN_PROGRESS"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ACCEPTED = "ACCEPTED"
    DISCARDED = "DISCARDED"
    FAILED = "FAILED"
    STALE = "STALE"


class OptimizationOperationState(str, Enum):
    PLANNED = "PLANNED"
    READY = "READY"
    APPLIED = "APPLIED"
    NO_CHANGE = "NO_CHANGE"
    FAILED = "FAILED"
    UNDONE = "UNDONE"
    SKIPPED = "SKIPPED"
    REJECTED = "REJECTED"
    STALE = "STALE"


class OptimizationConfidence(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ComparisonClassification(str, Enum):
    IMPROVEMENT = "IMPROVEMENT"
    REGRESSION = "REGRESSION"
    NEUTRAL = "NEUTRAL"
    INDETERMINATE = "INDETERMINATE"
    SKIPPED_LIMIT = "SKIPPED_LIMIT"


class FidelityStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    INDETERMINATE = "INDETERMINATE"
    SKIPPED_LIMIT = "SKIPPED_LIMIT"


def _finite_number(value: Any, name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number.")
    result = float(value)
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        raise ValueError(f"{name} must be a finite number >= {minimum}.")
    return result


def plain_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {item.name: plain_value(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): plain_value(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (tuple, list)):
        return [plain_value(item) for item in value]
    return value


class DeterministicModel:
    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True, slots=True)
class ObjectiveWeight(DeterministicModel):
    objective: OptimizationObjective | str
    weight: float
    source_classification: str = "PROJECT_DEFAULT"
    provenance: str = "Sprint 5 controlled optimization default"
    enabled: bool = True
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "objective", OptimizationObjective(self.objective))
        object.__setattr__(self, "weight", _finite_number(self.weight, "weight", minimum=0.0))
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean.")
        if not self.source_classification or not self.provenance:
            raise ValueError("Objective provenance and source classification are required.")


@dataclass(frozen=True, slots=True)
class ObjectiveSnapshot(DeterministicModel):
    preset: str
    weights: tuple[ObjectiveWeight, ...]
    normalized_weights: tuple[ObjectiveWeight, ...]
    objective_hash: str
    total_weight: float
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OptimizationPolicy(DeterministicModel):
    policy_id: str = "safe-default"
    policy_version: str = OPTIMIZATION_POLICY_SCHEMA_VERSION
    enabled_operation_families: tuple[str, ...] = (
        OptimizationOperationType.UNIFORM_SCALE.value,
        OptimizationOperationType.ORIENTATION.value,
        OptimizationOperationType.BUILD_PLATE_TRANSLATION.value,
    )
    maximum_uniform_scale_change: float = 0.20
    maximum_rotation_candidates: int = 8
    maximum_translation_distance: float = 1000.0
    maximum_base_modification_height: float = 2.0
    maximum_base_added_volume_ratio: float = 0.10
    maximum_decimation_ratio: float = 0.50
    maximum_geometric_deviation: float = 0.25
    maximum_remesh_voxel_size: float = 0.50
    maximum_operation_count: int = 8
    maximum_checkpoint_count: int = 4
    objective_weights: tuple[ObjectiveWeight, ...] = ()
    required_minimum_confidence: OptimizationConfidence = OptimizationConfidence.LOW
    approval_requirements: tuple[str, ...] = ("GEOMETRY_CHANGE", "EXPERIMENTAL_OPERATION")
    experimental_remesh_enabled: bool = False
    experimental_decimation_enabled: bool = False
    provenance: str = "Sprint 5 safe default policy"
    performance_limits: dict[str, float] = field(default_factory=lambda: {
        "candidate_generation_seconds": 30.0,
        "comparison_seconds": 120.0,
        "evidence_items": 256.0,
    })

    def __post_init__(self) -> None:
        if not self.policy_id or not self.policy_version or not self.provenance:
            raise ValueError("policy_id, policy_version, and provenance are required.")
        object.__setattr__(self, "required_minimum_confidence", OptimizationConfidence(self.required_minimum_confidence))
        for name in (
            "maximum_uniform_scale_change", "maximum_translation_distance", "maximum_base_modification_height",
            "maximum_base_added_volume_ratio", "maximum_decimation_ratio", "maximum_geometric_deviation",
            "maximum_remesh_voxel_size",
        ):
            value = _finite_number(getattr(self, name), name, minimum=0.0)
            if name == "maximum_uniform_scale_change" and value > 1.0:
                raise ValueError("maximum_uniform_scale_change cannot exceed 1.0.")
            if name == "maximum_base_added_volume_ratio" and value > 1.0:
                raise ValueError("maximum_base_added_volume_ratio cannot exceed 1.0.")
            if name in {"maximum_decimation_ratio", "maximum_geometric_deviation"} and value > 1.0:
                raise ValueError(f"{name} cannot exceed 1.0.")
            object.__setattr__(self, name, value)
        for name in ("maximum_rotation_candidates", "maximum_operation_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer.")
        if self.maximum_rotation_candidates > 64:
            raise ValueError("maximum_rotation_candidates exceeds the safe bound of 64.")
        if self.maximum_operation_count > 64:
            raise ValueError("maximum_operation_count exceeds the safe bound of 64.")
        if isinstance(self.maximum_checkpoint_count, bool) or not isinstance(self.maximum_checkpoint_count, int) or self.maximum_checkpoint_count < 2:
            raise ValueError("maximum_checkpoint_count must be at least 2 so the session-start checkpoint is retained.")
        if self.maximum_checkpoint_count > 20:
            raise ValueError("maximum_checkpoint_count exceeds the safe bound of 20.")
        if self.maximum_translation_distance > 10000.0:
            raise ValueError("maximum_translation_distance exceeds the safe bound of 10000 mm.")
        if self.maximum_base_modification_height > 100.0:
            raise ValueError("maximum_base_modification_height exceeds the safe bound of 100 mm.")
        if self.maximum_remesh_voxel_size > 10.0:
            raise ValueError("maximum_remesh_voxel_size exceeds the safe bound of 10 mm.")
        for operation in self.enabled_operation_families:
            try:
                OptimizationOperationType(operation)
            except ValueError as exc:
                raise ValueError(f"Unknown optimization operation type: {operation!r}") from exc
        if not isinstance(self.experimental_remesh_enabled, bool) or not isinstance(self.experimental_decimation_enabled, bool):
            raise ValueError("Experimental feature flags must be booleans.")
        for key, value in self.performance_limits.items():
            _finite_number(value, f"performance_limits[{key!r}]", minimum=0.0)


@dataclass(frozen=True, slots=True)
class OptimizationPolicySnapshot(DeterministicModel):
    policy: OptimizationPolicy
    policy_hash: str


@dataclass(frozen=True, slots=True)
class CandidateTransform(DeterministicModel):
    scale: float = 1.0
    rotation_euler: tuple[float, float, float] = (0.0, 0.0, 0.0)
    translation: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        object.__setattr__(self, "scale", _finite_number(self.scale, "scale", minimum=0.000001))
        for name, values in (("rotation_euler", self.rotation_euler), ("translation", self.translation)):
            if len(values) != 3:
                raise ValueError(f"{name} must have exactly three values.")
            object.__setattr__(self, name, tuple(_finite_number(item, f"{name} value") for item in values))


@dataclass(frozen=True, slots=True)
class CandidateGeometryOperation(DeterministicModel):
    operation: OptimizationOperationType | str
    parameters: dict[str, Any] = field(default_factory=dict)
    approval_required: bool = False
    experimental: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "operation", OptimizationOperationType(self.operation))
        if not isinstance(self.approval_required, bool) or not isinstance(self.experimental, bool):
            raise ValueError("Candidate approval and experimental flags must be booleans.")


@dataclass(frozen=True, slots=True)
class CandidateEvaluation(DeterministicModel):
    expected_objective_effect: dict[str, float] = field(default_factory=dict)
    confidence: OptimizationConfidence = OptimizationConfidence.LOW
    estimated_cost_seconds: float = 0.0
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "confidence", OptimizationConfidence(self.confidence))
        object.__setattr__(self, "estimated_cost_seconds", _finite_number(self.estimated_cost_seconds, "estimated_cost_seconds", minimum=0.0))
        for key, value in self.expected_objective_effect.items():
            _finite_number(value, f"expected_objective_effect[{key!r}]")


@dataclass(frozen=True, slots=True)
class OptimizationCandidate(DeterministicModel):
    candidate_id: str
    fingerprint: str
    category: OptimizationOperationType | str
    transform: CandidateTransform = field(default_factory=CandidateTransform)
    geometry_operation: CandidateGeometryOperation | None = None
    source_evidence: tuple[dict[str, Any], ...] = ()
    evaluation: CandidateEvaluation = field(default_factory=CandidateEvaluation)
    source_signature: str = ""
    process_context_hash: str = ""
    optimization_policy_hash: str = ""
    implementation_fingerprint: str = ""
    required_approval_level: str = "REVIEW"
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.fingerprint:
            raise ValueError("Candidate id and fingerprint are required.")
        object.__setattr__(self, "category", OptimizationOperationType(self.category))
        if len(self.source_evidence) > 256:
            raise ValueError("Candidate evidence exceeds the bounded policy limit.")


@dataclass(frozen=True, slots=True)
class OptimizationPlanStep(DeterministicModel):
    order: int
    candidate_id: str
    operation: OptimizationOperationType | str
    parameters: dict[str, Any] = field(default_factory=dict)
    expected_objective_deltas: tuple[dict[str, Any], ...] = ()
    prerequisite_states: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    approval_required: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.order, bool) or not isinstance(self.order, int) or self.order < 1:
            raise ValueError("Plan step order must be a positive integer.")
        object.__setattr__(self, "operation", OptimizationOperationType(self.operation))
        if not self.candidate_id:
            raise ValueError("Plan step candidate_id is required.")


@dataclass(slots=True)
class OptimizationPlan(DeterministicModel):
    plan_id: str
    session_id: str
    created_at: str
    source_signature: str
    workspace_signature: str
    policy_hash: str
    objective_hash: str
    implementation_fingerprint: str
    process_context_hash: str = ""
    feature_flag_hash: str = ""
    performance_registry_version: str = ""
    candidate_set_hash: str = ""
    steps: list[OptimizationPlanStep] = field(default_factory=list)
    status: str = "READY"
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    plan_hash: str = ""


@dataclass(frozen=True, slots=True)
class OptimizationCheckpoint(DeterministicModel):
    checkpoint_id: str
    operation_index: int
    candidate_id: str
    created_at: str
    workspace_signature: str
    workspace_object_identity: int
    workspace_mesh_identity: int
    source_signature: str
    policy_hash: str
    process_context_hash: str
    retained: bool = True


@dataclass(slots=True)
class OptimizationOperationRecord(DeterministicModel):
    operation_id: str
    candidate_id: str
    operation: OptimizationOperationType | str
    state: OptimizationOperationState | str
    started_at: str
    completed_at: str = ""
    checkpoint_id: str = ""
    before_workspace_signature: str = ""
    after_workspace_signature: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    comparison: dict[str, Any] = field(default_factory=dict)
    fidelity: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "operation", OptimizationOperationType(self.operation))
        object.__setattr__(self, "state", OptimizationOperationState(self.state))


@dataclass(frozen=True, slots=True)
class ObjectiveDelta(DeterministicModel):
    objective: OptimizationObjective | str
    before: float | None
    after: float | None
    delta: float | None
    classification: ComparisonClassification | str
    confidence: OptimizationConfidence | str = OptimizationConfidence.LOW
    limitation: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "objective", OptimizationObjective(self.objective))
        object.__setattr__(self, "classification", ComparisonClassification(self.classification))
        object.__setattr__(self, "confidence", OptimizationConfidence(self.confidence))


@dataclass(frozen=True, slots=True)
class RiskDelta(DeterministicModel):
    name: str
    before: float | None
    after: float | None
    delta: float | None
    classification: ComparisonClassification | str
    confidence: OptimizationConfidence | str = OptimizationConfidence.LOW
    limitation: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "classification", ComparisonClassification(self.classification))
        object.__setattr__(self, "confidence", OptimizationConfidence(self.confidence))


@dataclass(frozen=True, slots=True)
class OptimizationComparison(DeterministicModel):
    comparison_id: str
    before: dict[str, Any]
    after: dict[str, Any]
    objective_deltas: tuple[ObjectiveDelta, ...] = ()
    risk_deltas: tuple[RiskDelta, ...] = ()
    fidelity: dict[str, Any] = field(default_factory=dict)
    objective_score_before: float | None = None
    objective_score_after: float | None = None
    overall_classification: ComparisonClassification | str = ComparisonClassification.NEUTRAL
    critical_regressions: tuple[str, ...] = ()
    skipped_checks: tuple[str, ...] = ()
    indeterminate_checks: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "overall_classification", ComparisonClassification(self.overall_classification))


@dataclass(slots=True)
class AcceptanceRecord(DeterministicModel):
    accepted_at: str
    source_object_name: str
    optimized_object_name: str
    source_signature: str
    final_workspace_signature: str
    explicit_user_action: bool = True


@dataclass(slots=True)
class DiscardRecord(DeterministicModel):
    discarded_at: str
    source_object_name: str
    source_signature: str
    final_workspace_signature: str
    explicit_user_action: bool = True


@dataclass(slots=True)
class OptimizationSession(DeterministicModel):
    session_id: str
    started_at: str
    state: OptimizationSessionState | str
    source_object_name: str
    source_object_identity: int
    source_mesh_name: str
    source_mesh_identity: int
    source_signature: str
    source_snapshot: dict[str, Any]
    workspace_object_name: str
    workspace_object_identity: int
    workspace_mesh_name: str
    workspace_mesh_identity: int
    initial_workspace_signature: str
    current_workspace_signature: str
    process_context_hash: str = ""
    feature_flag_hash: str = ""
    performance_registry_version: str = ""
    policy_snapshot: OptimizationPolicySnapshot | None = None
    objective_snapshot: ObjectiveSnapshot | None = None
    candidates: list[OptimizationCandidate] = field(default_factory=list)
    plan: OptimizationPlan | None = None
    checkpoints: list[OptimizationCheckpoint] = field(default_factory=list)
    checkpoint_history: list[OptimizationCheckpoint] = field(default_factory=list)
    operation_records: list[OptimizationOperationRecord] = field(default_factory=list)
    comparisons: list[OptimizationComparison] = field(default_factory=list)
    stale_events: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    acceptance: AcceptanceRecord | None = None
    discard: DiscardRecord | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", OptimizationSessionState(self.state))


@dataclass(frozen=True, slots=True)
class OptimizationAudit(DeterministicModel):
    schema_version: str
    extension_version: str
    blender_version: str
    exported_at: str
    source_identity: dict[str, Any]
    source_signature: str
    workspace_identity: dict[str, Any]
    process_context_hash: str
    feature_flag_hash: str
    performance_registry_version: str
    optimization_policy: dict[str, Any]
    objectives: dict[str, Any]
    generated_candidates: tuple[dict[str, Any], ...]
    selected_plan: dict[str, Any]
    operation_history: tuple[dict[str, Any], ...]
    checkpoints: tuple[dict[str, Any], ...]
    comparisons: tuple[dict[str, Any], ...]
    fidelity_evidence: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]
    failures: tuple[str, ...]
    skipped_checks: tuple[str, ...]
    stale_events: tuple[dict[str, Any], ...]
    acceptance_outcome: dict[str, Any] | None
    discard_outcome: dict[str, Any] | None
    advisory_disclaimer: str = (
        "Controlled Optimization is a bounded software preview. It is not a slicer, does not generate G-code, "
        "does not control a printer, and does not guarantee printability or physical success."
    )


__all__ = [name for name in globals() if not name.startswith("_")]
