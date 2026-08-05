"""Typed, deterministic models for advisory printability analysis."""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime
from enum import Enum
import json
from typing import Any


class PrintabilityMode(str, Enum):
    FAST = "FAST"
    STANDARD = "STANDARD"
    DEEP = "DEEP"


class PrintabilityStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    NOT_EVALUATED = "NOT_EVALUATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    SKIPPED_LIMIT = "SKIPPED_LIMIT"
    INDETERMINATE = "INDETERMINATE"
    FAILED = "FAILED"


class PrintabilityConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class EvidenceState(str, Enum):
    COMPLETE = "COMPLETE"
    BOUNDED = "BOUNDED"
    TRUNCATED = "TRUNCATED"
    UNAVAILABLE = "UNAVAILABLE"


class StaleState(str, Enum):
    CURRENT = "CURRENT"
    STALE_GEOMETRY = "STALE_GEOMETRY"
    STALE_TRANSFORM = "STALE_TRANSFORM"
    STALE_PROFILE = "STALE_PROFILE"
    STALE_SETTINGS = "STALE_SETTINGS"


class ProcessType(str, Enum):
    FDM = "FDM"
    RESIN = "RESIN"
    CUSTOM = "CUSTOM"


class RiskCategory(str, Enum):
    TOPOLOGY = "TOPOLOGY"
    WALL_THICKNESS = "WALL_THICKNESS"
    THIN_FEATURE = "THIN_FEATURE"
    OVERHANG = "OVERHANG"
    FLOATING_COMPONENT = "FLOATING_COMPONENT"
    BUILD_CONTACT = "BUILD_CONTACT"
    BUILD_VOLUME = "BUILD_VOLUME"
    ORIENTATION = "ORIENTATION"


class RiskSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class RuleClassification(str, Enum):
    AUTHORITATIVE_SOURCE = "AUTHORITATIVE_SOURCE"
    STANDARDS_BASED = "STANDARDS_BASED"
    PEER_REVIEWED_METHOD = "PEER_REVIEWED_METHOD"
    MANUFACTURER_SPECIFIC = "MANUFACTURER_SPECIFIC"
    SLICER_GUIDANCE = "SLICER_GUIDANCE"
    PROJECT_DEFAULT = "PROJECT_DEFAULT"
    CONSERVATIVE_HEURISTIC = "CONSERVATIVE_HEURISTIC"
    USER_CONFIGURABLE = "USER_CONFIGURABLE"
    EXPERIMENTAL = "EXPERIMENTAL"
    NOT_YET_DEFINED = "NOT_YET_DEFINED"


class ContactClassification(str, Enum):
    BROAD_CONTACT = "BROAD_CONTACT"
    MULTI_REGION_CONTACT = "MULTI_REGION_CONTACT"
    PARTIAL_FACE_CONTACT = "PARTIAL_FACE_CONTACT"
    EDGE_CONTACT = "EDGE_CONTACT"
    POINT_CONTACT = "POINT_CONTACT"
    NO_CONTACT = "NO_CONTACT"
    INDETERMINATE = "INDETERMINATE"


class StabilityHeuristic(str, Enum):
    INSIDE = "INSIDE"
    NEAR_BOUNDARY = "NEAR_BOUNDARY"
    OUTSIDE = "OUTSIDE"
    UNAVAILABLE = "UNAVAILABLE"


class OrientationSource(str, Enum):
    CURRENT = "CURRENT"
    PRINCIPAL_AXIS = "PRINCIPAL_AXIS"
    BOUNDING_BOX_AXIS = "BOUNDING_BOX_AXIS"
    PLANAR_FACE = "PLANAR_FACE"
    STABLE_CONTACT = "STABLE_CONTACT"
    SAMPLED = "SAMPLED"


def plain_value(value: Any) -> Any:
    """Convert supported model values to deterministic JSON-compatible data."""

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {item.name: plain_value(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return {str(key): plain_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain_value(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class ThresholdValue:
    value: float
    classification: RuleClassification
    source_references: tuple[str, ...]
    rationale: str
    confidence: PrintabilityConfidence
    user_editable: bool


@dataclass(frozen=True, slots=True)
class BuildVolumeValue:
    x: float
    y: float
    z: float
    unit: str
    classification: RuleClassification
    source_references: tuple[str, ...]
    rationale: str
    confidence: PrintabilityConfidence

    @property
    def dimensions(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass(frozen=True, slots=True)
class ProfileGuidance:
    mode: str
    classification: RuleClassification
    source_references: tuple[str, ...]
    description: str
    confidence: PrintabilityConfidence
    user_editable: bool


@dataclass(frozen=True, slots=True)
class PrinterProfile:
    profile_schema_version: str
    profile_id: str
    display_name: str
    manufacturer: str
    printer_model: str
    process_type: ProcessType
    source_classification: RuleClassification
    source_references: tuple[str, ...]
    build_volume_mm: BuildVolumeValue
    dimensional_safety_margin_mm: ThresholdValue
    nozzle_diameter_mm: ThresholdValue
    nominal_layer_height_mm: ThresholdValue
    wall_thickness_warning_mm: ThresholdValue
    wall_thickness_critical_mm: ThresholdValue
    minimum_feature_warning_mm: ThresholdValue
    minimum_feature_critical_mm: ThresholdValue
    overhang_warning_angle_deg: ThresholdValue
    overhang_critical_angle_deg: ThresholdValue
    build_plate_contact_tolerance_mm: ThresholdValue
    bridge_guidance: ProfileGuidance
    support_assumption: ProfileGuidance
    material_family: str
    notes: str
    confidence: PrintabilityConfidence
    user_editable_fields: tuple[str, ...]
    created_at: str
    updated_at: str
    profile_hash: str

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class PrinterProfileSnapshot:
    profile: PrinterProfile

    def to_dict(self) -> dict[str, Any]:
        return self.profile.to_dict()


@dataclass(frozen=True, slots=True)
class PrintabilitySettingsSnapshot:
    settings_schema_version: str
    performance_mode: PrintabilityMode
    build_direction: tuple[float, float, float]
    wall_sample_limit: int
    triangle_limit: int
    orientation_candidate_limit: int
    evidence_cap: int
    ray_origin_offset_mm: float
    maximum_wall_search_distance_mm: float
    contact_tolerance_mm: float
    contact_region_tolerance_mm: float
    small_face_area_mm2: float
    overhang_region_area_threshold_mm2: float
    opposing_normal_dot_max: float
    exact_boundary_tolerance_mm: float
    principal_axis_candidates_enabled: bool
    planar_face_candidates_enabled: bool
    sampled_candidates_enabled: bool
    orientation_weights: dict[str, float]
    support_assumption: str
    weights_version: str
    cancellation_enabled: bool
    settings_hash: str

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class GeometryFacts:
    dimensions_mm: tuple[float, float, float]
    bbox_min_mm: tuple[float, float, float]
    bbox_max_mm: tuple[float, float, float]
    shell_count: int
    main_shell_id: int | None
    triangle_count: int
    vertex_count: int
    edge_count: int
    face_count: int
    surface_area_mm2: float
    reliable_volume_mm3: float | None
    boundary_edges: int
    non_manifold_edges: int
    vertex_manifold_anomalies: int
    watertight: bool
    lowest_build_plane_offset_mm: float
    floating_shell_ids: tuple[str, ...] = ()
    reused_analysis_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class WallThicknessResult:
    status: PrintabilityStatus
    confidence: PrintabilityConfidence
    evidence_state: EvidenceState
    samples_attempted: int = 0
    samples_completed: int = 0
    samples_skipped: int = 0
    minimum_sampled_thickness_mm: float | None = None
    percentile_thickness_mm: dict[str, float] = field(default_factory=dict)
    area_below_warning_mm2: float = 0.0
    area_below_critical_mm2: float = 0.0
    percent_below_warning: float = 0.0
    percent_below_critical: float = 0.0
    thin_region_count: int = 0
    largest_thin_region_area_mm2: float = 0.0
    evidence_faces: tuple[int, ...] = ()
    sample_positions_mm: tuple[tuple[float, float, float], ...] = ()
    sample_hits_mm: tuple[tuple[float, float, float], ...] = ()
    sample_thicknesses_mm: tuple[float, ...] = ()
    duration_seconds: float = 0.0
    limitations: tuple[str, ...] = ()
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class ThinFeatureResult:
    status: PrintabilityStatus
    confidence: PrintabilityConfidence
    evidence_state: EvidenceState
    candidates_attempted: int = 0
    candidates_completed: int = 0
    candidates_skipped: int = 0
    minimum_diameter_mm: float | None = None
    percentile_diameters_mm: dict[str, float] = field(default_factory=dict)
    warning_feature_count: int = 0
    critical_feature_count: int = 0
    largest_affected_region_mm: float = 0.0
    evidence_vertices: tuple[int, ...] = ()
    feature_centers_mm: tuple[tuple[float, float, float], ...] = ()
    duration_seconds: float = 0.0
    limitations: tuple[str, ...] = ()
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class OverhangRegion:
    region_id: str
    band: str
    face_count: int
    area_mm2: float
    representative_face: int
    centroid_mm: tuple[float, float, float]
    minimum_angle_deg: float


@dataclass(frozen=True, slots=True)
class OverhangResult:
    status: PrintabilityStatus
    confidence: PrintabilityConfidence
    evidence_state: EvidenceState
    faces_attempted: int = 0
    faces_evaluated: int = 0
    faces_skipped: int = 0
    affected_face_count: int = 0
    eligible_surface_area_mm2: float = 0.0
    warning_area_mm2: float = 0.0
    critical_area_mm2: float = 0.0
    warning_area_percent: float = 0.0
    critical_area_percent: float = 0.0
    suppressed_face_count: int = 0
    suppressed_area_mm2: float = 0.0
    angle_percentiles_deg: dict[str, float] = field(default_factory=dict)
    regions: tuple[OverhangRegion, ...] = ()
    evidence_faces: tuple[int, ...] = ()
    build_direction: tuple[float, float, float] = (0.0, 0.0, 1.0)
    warning_threshold_deg: float = 0.0
    critical_threshold_deg: float = 0.0
    duration_seconds: float = 0.0
    limitations: tuple[str, ...] = ()
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class FloatingComponentEvidence:
    shell_id: int
    vertex_count: int
    face_count: int
    surface_area_mm2: float
    bbox_min_mm: tuple[float, float, float]
    bbox_max_mm: tuple[float, float, float]
    lowest_build_plane_offset_mm: float
    contact_state: str
    evidence_faces: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class FloatingComponentResult:
    status: PrintabilityStatus
    confidence: PrintabilityConfidence
    evidence_state: EvidenceState
    shell_count: int = 0
    contacting_shell_ids: tuple[int, ...] = ()
    floating_shell_ids: tuple[int, ...] = ()
    components: tuple[FloatingComponentEvidence, ...] = ()
    duration_seconds: float = 0.0
    limitations: tuple[str, ...] = ()
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class BuildPlateContactResult:
    status: PrintabilityStatus
    confidence: PrintabilityConfidence
    evidence_state: EvidenceState
    classification: ContactClassification
    minimum_build_plane_offset_mm: float = 0.0
    contact_vertex_count: int = 0
    contact_edge_count: int = 0
    contact_face_count: int = 0
    contact_area_mm2: float = 0.0
    contact_region_count: int = 0
    projected_footprint_area_mm2: float | None = None
    contact_area_percent: float = 0.0
    center_of_mass_projection_mm: tuple[float, float] | None = None
    stability_heuristic: StabilityHeuristic = StabilityHeuristic.UNAVAILABLE
    stability_margin_mm: float | None = None
    evidence_vertices: tuple[int, ...] = ()
    evidence_edges: tuple[int, ...] = ()
    evidence_faces: tuple[int, ...] = ()
    duration_seconds: float = 0.0
    limitations: tuple[str, ...] = ()
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class ScaleEvaluation:
    status: PrintabilityStatus
    confidence: PrintabilityConfidence
    current_dimensions_mm: tuple[float, float, float]
    profile_build_volume_mm: tuple[float, float, float]
    usable_build_volume_mm: tuple[float, float, float]
    axis_fit: tuple[bool, bool, bool]
    overflow_mm: tuple[float, float, float]
    overall_fit: bool
    maximum_uniform_fit_scale_percent: float
    required_scale_percent: float
    current_orientation_only: bool = True
    consequence_warnings: tuple[str, ...] = ()
    duration_seconds: float = 0.0
    limitations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class OrientationCandidate:
    candidate_schema_version: str
    candidate_id: str
    rotation_quaternion: tuple[float, float, float, float]
    source: OrientationSource
    score: float | None
    overall_risk: PrintabilityStatus
    advantages: tuple[str, ...]
    trade_offs: tuple[str, ...]
    confidence: PrintabilityConfidence
    measurement_summary: dict[str, Any]
    recommendation_reason: str
    state: StaleState = StaleState.CURRENT

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class OrientationResult:
    status: PrintabilityStatus
    confidence: PrintabilityConfidence
    evidence_state: EvidenceState
    candidates: tuple[OrientationCandidate, ...] = ()
    candidates_generated: int = 0
    candidates_evaluated: int = 0
    candidates_skipped: int = 0
    duration_seconds: float = 0.0
    limitations: tuple[str, ...] = ()
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class PrintabilityRiskItem:
    risk_item_schema_version: str
    risk_id: str
    rule_id: str
    category: RiskCategory
    state: PrintabilityStatus
    severity: RiskSeverity
    confidence: PrintabilityConfidence
    evidence_state: EvidenceState
    message: str
    review_action: str
    source_classification: RuleClassification
    source_references: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    metrics: dict[str, Any] = field(default_factory=dict)
    limitations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class PrintabilityScore:
    score: int | None
    status: PrintabilityStatus
    confidence: PrintabilityConfidence
    critical_reasons: tuple[str, ...]
    missing_checks: tuple[dict[str, str], ...]
    skipped_checks: tuple[dict[str, str], ...]
    failed_checks: tuple[dict[str, str], ...]
    category_scores: dict[str, float]
    coverage_percent: float
    scoring_policy_version: str

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)


@dataclass(frozen=True, slots=True)
class PrintabilityResult:
    report_schema_version: str
    extension_version: str
    blender_version: str
    operating_system: str
    analysis_id: str
    printability_run_id: str
    analyzed_at: datetime
    object_metadata: dict[str, Any]
    geometry_signature: str
    transform_signature: str
    source_signature: str
    printer_profile_snapshot: PrinterProfileSnapshot
    settings_snapshot: PrintabilitySettingsSnapshot
    build_direction: tuple[float, float, float]
    geometry_facts: GeometryFacts
    topology_readiness: dict[str, Any]
    wall_thickness: WallThicknessResult
    thin_features: ThinFeatureResult
    overhangs: OverhangResult
    floating_components: FloatingComponentResult
    build_plate_contact: BuildPlateContactResult
    scale_evaluation: ScaleEvaluation
    orientation: OrientationResult
    risk_items: tuple[PrintabilityRiskItem, ...]
    score_details: PrintabilityScore
    timings: dict[str, float]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    stale_state: StaleState = StaleState.CURRENT

    def check_results(self) -> tuple[dict[str, Any], ...]:
        return (
            {"check": "topology_readiness", **plain_value(self.topology_readiness)},
            {"check": "wall_thickness", **self.wall_thickness.to_dict()},
            {"check": "thin_features", **self.thin_features.to_dict()},
            {"check": "overhangs", **self.overhangs.to_dict()},
            {"check": "floating_components", **self.floating_components.to_dict()},
            {"check": "build_plate_contact", **self.build_plate_contact.to_dict()},
            {"check": "build_volume_and_scale", **self.scale_evaluation.to_dict()},
            {"check": "orientation", **self.orientation.to_dict()},
        )

    def to_dict(self) -> dict[str, Any]:
        skipped = list(self.score_details.skipped_checks)
        failed = list(self.score_details.failed_checks)
        evidence = [
            {"check": item["check"], "evidence_state": item.get("evidence_state", "UNAVAILABLE")}
            for item in self.check_results()
            if item["check"] != "topology_readiness"
        ]
        return {
            "report_schema_version": self.report_schema_version,
            "extension_version": self.extension_version,
            "blender_version": self.blender_version,
            "operating_system": self.operating_system,
            "analysis_id": self.analysis_id,
            "printability_run_id": self.printability_run_id,
            "object_metadata": plain_value(self.object_metadata),
            "geometry_signature": self.geometry_signature,
            "transform_signature": self.transform_signature,
            "printer_profile_snapshot": self.printer_profile_snapshot.to_dict(),
            "settings_snapshot": self.settings_snapshot.to_dict(),
            "build_direction": plain_value(self.build_direction),
            "geometry_facts": self.geometry_facts.to_dict(),
            "check_results": list(self.check_results()),
            "risk_items": [item.to_dict() for item in self.risk_items],
            "score": self.score_details.score,
            "overall_status": self.score_details.status.value,
            "confidence": self.score_details.confidence.value,
            "orientation_candidates": [item.to_dict() for item in self.orientation.candidates],
            "evidence_summaries": evidence,
            "skipped_checks": skipped,
            "failed_checks": failed,
            "timings": plain_value(self.timings),
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "stale_state": self.stale_state.value,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n"


@dataclass(frozen=True, slots=True)
class PrintabilityReport:
    result: PrintabilityResult

    def to_dict(self) -> dict[str, Any]:
        return self.result.to_dict()

    def to_json(self) -> str:
        return self.result.to_json()
