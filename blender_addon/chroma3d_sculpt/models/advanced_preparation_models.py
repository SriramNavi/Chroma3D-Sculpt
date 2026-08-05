"""Typed JSON-safe models for Sprint 4 advanced print preparation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Any

from .printability_models import (
    PrintabilityConfidence,
    PrintabilityMode,
    PrintabilityStatus,
    ProcessType,
    RuleClassification,
    StaleState,
    plain_value,
)


class MaterialFamily(str, Enum):
    PLA = "PLA"
    PETG = "PETG"
    ABS = "ABS"
    ASA = "ASA"
    TPU = "TPU"
    RESIN = "RESIN"
    CUSTOM = "CUSTOM"


class SupportRiskReason(str, Enum):
    OVERHANG = "OVERHANG"
    FLOATING_COMPONENT = "FLOATING_COMPONENT"
    BRIDGE = "BRIDGE"
    LOW_CONTACT = "LOW_CONTACT"
    FRAGILE_FEATURE = "FRAGILE_FEATURE"
    RESIN_ISLAND = "RESIN_ISLAND"
    OTHER = "OTHER"


class BatchPreparationState(str, Enum):
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class RegressionState(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(frozen=True, slots=True)
class HardwareProfile:
    profile_id: str
    manufacturer: str
    printer_model: str
    process_type: ProcessType
    build_volume_mm: tuple[float, float, float]
    nozzle_options_mm: tuple[float, ...]
    layer_height_range_mm: tuple[float, float]
    bed_type_capabilities: tuple[str, ...]
    extruder_capabilities: tuple[str, ...]
    source_references: tuple[str, ...]
    confidence: PrintabilityConfidence
    hardware_only_notes: tuple[str, ...]
    source_classification: RuleClassification
    safety_margin_mm: float
    profile_hash: str

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class MaterialProfile:
    schema_version: str
    profile_id: str
    display_name: str
    material_family: MaterialFamily
    manufacturer: str | None
    compatible_process_types: tuple[ProcessType, ...]
    source_classification: RuleClassification
    source_references: tuple[str, ...]
    confidence: PrintabilityConfidence
    nozzle_range_mm: tuple[float, float]
    layer_height_range_mm: tuple[float, float]
    wall_thickness_multiplier: float
    thin_feature_multiplier: float
    bridge_risk_modifier: float
    overhang_risk_modifier: float
    support_removal_risk: str
    warping_risk: str
    brittleness_risk: str
    adhesion_risk: str
    dimensional_change_guidance: str
    temperature_information: str | None
    user_editable_fields: tuple[str, ...]
    notes: tuple[str, ...]
    limitations: tuple[str, ...]
    created_at: str
    updated_at: str
    profile_hash: str

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class MaterialProfileSnapshot:
    profile: MaterialProfile

    def to_dict(self) -> dict[str, Any]:
        return self.profile.to_dict()


@dataclass(frozen=True, slots=True)
class FeatureFlagSet:
    schema_version: str
    wall_thickness: bool
    thin_features: bool
    overhangs: bool
    floating_components: bool
    build_contact: bool
    scale_evaluation: bool
    orientation_recommendations: bool
    bridge_risk: bool
    support_risk: bool
    resin_advisory: bool
    batch_analysis: bool
    baseline_generation: bool
    dashboard_generation: bool
    experimental_material_modifiers: bool
    experimental_flags: tuple[str, ...]
    flag_hash: str

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class PerformanceLimit:
    mode: PrintabilityMode
    size_class: str
    check_type: str
    maximum_triangles: int
    maximum_samples: int
    maximum_candidate_count: int
    maximum_region_evidence: int
    maximum_batch_size: int
    recommended_warning_time_seconds: float
    hard_skip_limit: int
    expected_memory_class: str

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class ComposedProcessContext:
    schema_version: str
    hardware_profile: HardwareProfile
    material_profile: MaterialProfile
    nozzle_mm: float
    layer_height_mm: float
    support_policy: str
    build_plate_type: str
    user_overrides: dict[str, float | str]
    effective_thresholds: dict[str, float]
    threshold_provenance: dict[str, dict[str, Any]]
    compatibility_warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    context_hash: str

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class ProcessContextSnapshot:
    context: ComposedProcessContext

    def to_dict(self) -> dict[str, Any]:
        return self.context.to_dict()


@dataclass(frozen=True, slots=True)
class BridgeRiskRegion:
    region_id: str
    severity: PrintabilityStatus
    estimated_span_mm: float
    projected_unsupported_distance_mm: float
    supporting_side_count: int
    width_mm: float
    surface_area_mm2: float
    angle_deg: float
    build_direction: tuple[float, float, float]
    profile_material_modifier: float
    confidence: PrintabilityConfidence
    evidence_faces: tuple[int, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class BridgeRiskResult:
    status: PrintabilityStatus
    confidence: PrintabilityConfidence
    candidate_region_count: int
    regions: tuple[BridgeRiskRegion, ...]
    evidence_faces: tuple[int, ...]
    duration_seconds: float
    limitations: tuple[str, ...]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class SupportRiskRegion:
    region_id: str
    severity: PrintabilityStatus
    reason_categories: tuple[SupportRiskReason, ...]
    surface_area_mm2: float
    total_area_percent: float
    confidence: PrintabilityConfidence
    evidence_faces: tuple[int, ...]
    message: str
    profile_material_influence: dict[str, Any]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class SupportRiskResult:
    status: PrintabilityStatus
    confidence: PrintabilityConfidence
    region_count: int
    total_risk_area_mm2: float
    total_risk_area_percent: float
    regions: tuple[SupportRiskRegion, ...]
    evidence_faces: tuple[int, ...]
    duration_seconds: float
    limitations: tuple[str, ...]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class ResinAdvisoryResult:
    status: PrintabilityStatus
    confidence: PrintabilityConfidence
    checks: dict[str, dict[str, Any]]
    evidence_faces: tuple[int, ...]
    duration_seconds: float
    limitations: tuple[str, ...]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class ScaleInterval:
    minimum_percent: float | None
    maximum_percent: float | None
    state: str

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class AdvancedScaleRecommendation:
    status: PrintabilityStatus
    confidence: PrintabilityConfidence
    maximum_uniform_fit_scale_percent: float
    minimum_wall_preserving_scale_percent: float | None
    minimum_feature_preserving_scale_percent: float | None
    recommended_interval: ScaleInterval
    current_score: int | None
    sampled_scale_scores: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class OrientationComparison:
    status: PrintabilityStatus
    confidence: PrintabilityConfidence
    candidates: tuple[dict[str, Any], ...]
    pareto_candidate_ids: tuple[str, ...]
    deterministic_rank_ids: tuple[str, ...]
    duration_seconds: float
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class AdvancedPreparationResult:
    report_schema_version: str
    extension_version: str
    preparation_run_id: str
    analyzed_at: str
    object_metadata: dict[str, Any]
    geometry_signature: str
    transform_signature: str
    source_signature: str
    process_context_snapshot: ProcessContextSnapshot
    feature_flags: FeatureFlagSet
    performance_registry_version: str
    performance_mode: PrintabilityMode
    base_printability: dict[str, Any]
    bridge_risk: BridgeRiskResult
    support_risk: SupportRiskResult
    resin_advisory: ResinAdvisoryResult
    scale_recommendation: AdvancedScaleRecommendation
    orientation_comparison: OrientationComparison
    score: int | None
    status: PrintabilityStatus
    confidence: PrintabilityConfidence
    timings: dict[str, float]
    skipped_checks: tuple[dict[str, str], ...]
    failed_checks: tuple[dict[str, str], ...]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    stale_state: StaleState = StaleState.CURRENT

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True, slots=True)
class BatchPreparationResult:
    schema_version: str
    batch_id: str
    state: BatchPreparationState
    started_at: str
    completed_at: str
    object_count: int
    completed_count: int
    failed_count: int
    skipped_count: int
    total_time_seconds: float
    process_context_hash: str
    feature_flag_hash: str
    process_context_snapshot: dict[str, Any]
    feature_flags: dict[str, Any]
    source_signatures: dict[str, str]
    object_results: tuple[dict[str, Any], ...]
    critical_risks: tuple[dict[str, Any], ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class PrintabilityBaselineRecord:
    model_id: str
    source_sha256: str
    process_context_hash: str
    feature_flags: dict[str, Any]
    score: int | None
    status: str
    confidence: str
    per_check_states: dict[str, str]
    bridge_risks: dict[str, Any]
    support_risk_areas: dict[str, Any]
    resin_advisory_states: dict[str, Any]
    scale_interval: dict[str, Any]
    orientation_candidates: tuple[dict[str, Any], ...]
    timings: dict[str, float]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class RegressionComparison:
    model_id: str
    state: RegressionState
    changes: tuple[dict[str, Any], ...]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class DashboardSummary:
    schema_version: str
    overall_state: RegressionState
    model_count: int
    pass_count: int
    warning_count: int
    fail_count: int
    review_required_count: int
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)
