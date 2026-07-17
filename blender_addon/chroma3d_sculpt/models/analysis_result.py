"""Immutable, deterministic models for production mesh diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime
from enum import Enum
import json
from typing import Any


class AnalysisProfile(str, Enum):
    STANDARD = "STANDARD"
    DEEP = "DEEP"


class AnalysisSeverity(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


class EvaluationStatus(str, Enum):
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class CheckConfidence(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class WatertightState(str, Enum):
    TOPOLOGICALLY_WATERTIGHT = "TOPOLOGICALLY_WATERTIGHT"
    NOT_WATERTIGHT = "NOT_WATERTIGHT"
    INDETERMINATE = "INDETERMINATE"
    NOT_EVALUATED = "NOT_EVALUATED"


class EdgeManifoldState(str, Enum):
    MANIFOLD = "MANIFOLD"
    NON_MANIFOLD = "NON_MANIFOLD"
    NOT_EVALUATED = "NOT_EVALUATED"


class VertexManifoldState(str, Enum):
    MANIFOLD = "MANIFOLD"
    ANOMALIES_DETECTED = "ANOMALIES_DETECTED"
    INDETERMINATE = "INDETERMINATE"
    NOT_EVALUATED = "NOT_EVALUATED"


class NormalConsistencyState(str, Enum):
    CONSISTENT = "CONSISTENT"
    INCONSISTENT = "INCONSISTENT"
    OPEN = "OPEN"
    INDETERMINATE = "INDETERMINATE"
    POTENTIALLY_INCONSISTENT = "POTENTIALLY_INCONSISTENT"
    NOT_EVALUATED = "NOT_EVALUATED"


class ShellOrientationState(str, Enum):
    OUTWARD = "OUTWARD"
    INWARD = "INWARD"
    INCONSISTENT = "INCONSISTENT"
    OPEN = "OPEN"
    INDETERMINATE = "INDETERMINATE"
    NOT_EVALUATED = "NOT_EVALUATED"


class ShellContainmentState(str, Enum):
    MAIN_SHELL = "MAIN_SHELL"
    POSSIBLY_INTERNAL = "POSSIBLY_INTERNAL"
    DISCONNECTED_EXTERNAL = "DISCONNECTED_EXTERNAL"
    UNCLASSIFIED = "UNCLASSIFIED"
    NOT_EVALUATED = "NOT_EVALUATED"


class SelfIntersectionState(str, Enum):
    NO_CANDIDATES_DETECTED = "NO_CANDIDATES_DETECTED"
    CANDIDATES_DETECTED = "CANDIDATES_DETECTED"
    SKIPPED_LIMIT = "SKIPPED_LIMIT"
    FAILED = "FAILED"
    NOT_EVALUATED = "NOT_EVALUATED"


class BuildVolumeFitState(str, Enum):
    FITS = "FITS"
    DOES_NOT_FIT = "DOES_NOT_FIT"
    NO_PROFILE = "NO_PROFILE"
    INDETERMINATE = "INDETERMINATE"
    NOT_EVALUATED = "NOT_EVALUATED"


class PrinterProfile(str, Enum):
    NONE = "NONE"
    BAMBU_X1_CARBON = "BAMBU_X1_CARBON"
    CUSTOM = "CUSTOM"


class IssueDomain(str, Enum):
    VERTEX = "VERTEX"
    EDGE = "EDGE"
    FACE = "FACE"
    SHELL = "SHELL"


class IssueCategory(str, Enum):
    BOUNDARY_EDGES = "BOUNDARY_EDGES"
    LOOSE_EDGES = "LOOSE_EDGES"
    LOOSE_VERTICES = "LOOSE_VERTICES"
    HIGH_INCIDENCE_EDGES = "HIGH_INCIDENCE_EDGES"
    VERTEX_MANIFOLD_ANOMALIES = "VERTEX_MANIFOLD_ANOMALIES"
    ZERO_LENGTH_EDGES = "ZERO_LENGTH_EDGES"
    DEGENERATE_FACES = "DEGENERATE_FACES"
    INCONSISTENT_FACES = "INCONSISTENT_FACES"
    INCONSISTENT_SHARED_EDGES = "INCONSISTENT_SHARED_EDGES"
    TINY_SHELL_FACES = "TINY_SHELL_FACES"
    POSSIBLE_INTERNAL_SHELL_FACES = "POSSIBLE_INTERNAL_SHELL_FACES"
    SELF_INTERSECTION_FACES = "SELF_INTERSECTION_FACES"


@dataclass(frozen=True, slots=True)
class ObjectMetadata:
    object_name: str = ""
    mesh_data_name: str = ""
    object_mode: str = ""
    object_type: str = ""
    material_slot_count: int = 0
    modifier_count: int = 0
    collection_names: tuple[str, ...] = ()
    blend_file_path: str | None = None
    blend_file_unsaved: bool = True
    analysis_source: str = "ORIGINAL_MESH_DATABLOCK"
    modifiers_evaluated: bool = False


@dataclass(frozen=True, slots=True)
class GeometryMetrics:
    vertex_count: int = 0
    edge_count: int = 0
    polygon_count: int = 0
    triangle_count: int = 0
    loop_count: int = 0
    material_slot_count: int = 0
    modifier_count: int = 0
    metric_source: str = "ORIGINAL_MESH_DATABLOCK"
    triangle_source: str = "ORIGINAL_MESH_LOOP_TRIANGLES"


@dataclass(frozen=True, slots=True)
class DimensionMetrics:
    width_mm: float = 0.0
    depth_mm: float = 0.0
    height_mm: float = 0.0
    unit_system: str = "NONE"
    scene_scale_length: float = 1.0
    millimetres_per_blender_unit: float = 1000.0
    source: str = "WORLD_SPACE_AXIS_ALIGNED_BOUNDING_BOX"


@dataclass(frozen=True, slots=True)
class TransformMetrics:
    location_applied: bool = True
    rotation_applied: bool = True
    scale_applied: bool = True
    location: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation_euler: tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    tolerance: float = 1e-6


@dataclass(frozen=True, slots=True)
class TopologyMetrics:
    non_manifold_edges: int = 0
    boundary_edges: int = 0
    manifold_edges: int = 0
    high_incidence_non_manifold_edges: int = 0
    loose_vertices: int = 0
    loose_edges: int = 0
    zero_length_edges: int = 0
    degenerate_faces: int = 0
    connected_components: int = 0
    disconnected_shells: int = 0
    face_shell_count: int = 0
    potential_duplicate_vertices: int = 0
    duplicate_evaluation_status: EvaluationStatus = EvaluationStatus.COMPLETED
    edge_manifold_state: EdgeManifoldState = EdgeManifoldState.NOT_EVALUATED
    vertex_manifold_state: VertexManifoldState = VertexManifoldState.NOT_EVALUATED
    vertex_manifold_anomalies: int = 0
    watertight_state: WatertightState = WatertightState.NOT_EVALUATED
    watertight_detail: str = "Not evaluated."
    normal_consistency: NormalConsistencyState = NormalConsistencyState.NOT_EVALUATED
    normal_consistency_detail: str = "Not evaluated."


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    status: EvaluationStatus
    message: str
    duration_ms: float = 0.0
    actual_size: int | None = None
    configured_limit: int | None = None


@dataclass(frozen=True, slots=True)
class CheckTiming:
    name: str
    status: EvaluationStatus
    duration_ms: float
    detail: str = ""


@dataclass(frozen=True, slots=True)
class AnalysisSettingsSnapshot:
    analysis_profile: AnalysisProfile = AnalysisProfile.STANDARD
    duplicate_position_tolerance: float = 1e-6
    duplicate_vertex_limit: int = 500_000
    degenerate_edge_tolerance: float = 1e-9
    degenerate_face_tolerance: float = 1e-18
    tiny_shell_max_face_count: int = 12
    tiny_shell_max_volume_mm3: float = 1000.0
    tiny_shell_max_relative_volume_percent: float = 0.5
    tiny_shell_max_diagonal_mm: float = 10.0
    maximum_stored_issue_indices: int = 10_000
    self_intersection_triangle_limit: int = 50_000
    maximum_stored_self_intersection_pairs: int = 10_000
    containment_shell_limit: int = 64
    containment_triangle_limit: int = 100_000
    printer_profile: PrinterProfile = PrinterProfile.NONE
    build_volume_mm: tuple[float, float, float] | None = None
    extension_version: str = ""
    blender_version: str = ""


@dataclass(frozen=True, slots=True)
class TopologySignature:
    analysis_id: str = ""
    object_name: str = ""
    mesh_data_name: str = ""
    vertex_count: int = 0
    edge_count: int = 0
    polygon_count: int = 0
    topology_sha256: str = ""


@dataclass(frozen=True, slots=True)
class IssueEvidence:
    category: IssueCategory
    domain: IssueDomain
    total_count: int
    indices: tuple[int, ...] = ()
    pairs: tuple[tuple[int, int], ...] = ()
    truncated: bool = False
    evidence_cap: int = 0
    shell_id: int | None = None
    note: str = ""


@dataclass(frozen=True, slots=True)
class ShellMetrics:
    shell_id: int
    face_count: int
    triangle_count: int
    vertex_count: int
    edge_count: int
    boundary_edge_count: int
    non_manifold_edge_count: int
    bbox_min_mm: tuple[float, float, float]
    bbox_max_mm: tuple[float, float, float]
    dimensions_mm: tuple[float, float, float]
    surface_area_mm2: float
    signed_volume_mm3: float | None
    absolute_volume_mm3: float | None
    volume_status: EvaluationStatus
    centroid_mm: tuple[float, float, float]
    watertight_state: WatertightState
    orientation_consistency: NormalConsistencyState
    orientation_state: ShellOrientationState
    relative_volume_percent: float | None = None
    relative_surface_area_percent: float = 0.0
    classification: ShellContainmentState = ShellContainmentState.UNCLASSIFIED
    tiny_shell_candidate: bool = False
    tiny_criteria_evaluated: tuple[str, ...] = ()
    tiny_criteria_matched: tuple[str, ...] = ()
    classification_confidence: CheckConfidence = CheckConfidence.NONE
    containing_shell_id: int | None = None
    diagnostic_notes: tuple[str, ...] = ()
    check_statuses: tuple[CheckResult, ...] = ()


@dataclass(frozen=True, slots=True)
class SurfaceVolumeMetrics:
    surface_area_status: EvaluationStatus = EvaluationStatus.NOT_APPLICABLE
    total_surface_area_mm2: float = 0.0
    volume_status: EvaluationStatus = EvaluationStatus.NOT_APPLICABLE
    reliable_closed_shell_volume_mm3: float | None = None
    reliable_volume_shell_count: int = 0
    unavailable_volume_shell_count: int = 0
    detail: str = "Not evaluated."


@dataclass(frozen=True, slots=True)
class BuildVolumeMetrics:
    status: EvaluationStatus = EvaluationStatus.NOT_APPLICABLE
    fit_state: BuildVolumeFitState = BuildVolumeFitState.NOT_EVALUATED
    printer_profile: PrinterProfile = PrinterProfile.NONE
    model_dimensions_mm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    build_dimensions_mm: tuple[float, float, float] | None = None
    fits_x: bool | None = None
    fits_y: bool | None = None
    fits_z: bool | None = None
    overall_fit: bool | None = None
    excess_mm: tuple[float, float, float] = (0.0, 0.0, 0.0)
    maximum_uniform_scale_percent: float | None = None
    current_orientation_only: bool = True
    message: str = "Not evaluated."


@dataclass(frozen=True, slots=True)
class ContainmentEvidence:
    containing_shell_id: int
    candidate_shell_id: int
    broad_phase_bbox_contained: bool
    sample_count: int
    positive_votes: int
    confidence: CheckConfidence


@dataclass(frozen=True, slots=True)
class DeepDiagnosticMetrics:
    self_intersection_status: EvaluationStatus = EvaluationStatus.NOT_APPLICABLE
    self_intersection_state: SelfIntersectionState = SelfIntersectionState.NOT_EVALUATED
    self_intersection_candidate_count: int | None = None
    self_intersection_pairs: tuple[tuple[int, int], ...] = ()
    self_intersection_evidence_truncated: bool = False
    containment_status: EvaluationStatus = EvaluationStatus.NOT_APPLICABLE
    possible_internal_shell_ids: tuple[int, ...] = ()
    containment_evidence: tuple[ContainmentEvidence, ...] = ()
    notes: tuple[str, ...] = ()


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {item.name: _plain(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    schema_version: str
    extension_version: str
    blender_version: str
    operating_system: str
    analyzed_at: datetime
    duration_ms: float
    severity: AnalysisSeverity
    summary: str
    analysis_id: str = ""
    analysis_profile: AnalysisProfile = AnalysisProfile.STANDARD
    settings_snapshot: AnalysisSettingsSnapshot = field(default_factory=AnalysisSettingsSnapshot)
    topology_signature: TopologySignature = field(default_factory=TopologySignature)
    object_metadata: ObjectMetadata = field(default_factory=ObjectMetadata)
    geometry: GeometryMetrics = field(default_factory=GeometryMetrics)
    dimensions: DimensionMetrics = field(default_factory=DimensionMetrics)
    transforms: TransformMetrics = field(default_factory=TransformMetrics)
    topology: TopologyMetrics = field(default_factory=TopologyMetrics)
    surface_volume: SurfaceVolumeMetrics = field(default_factory=SurfaceVolumeMetrics)
    shells: tuple[ShellMetrics, ...] = ()
    main_shell_id: int | None = None
    tiny_shell_candidate_ids: tuple[int, ...] = ()
    disconnected_external_shell_ids: tuple[int, ...] = ()
    possible_internal_shell_ids: tuple[int, ...] = ()
    build_volume: BuildVolumeMetrics = field(default_factory=BuildVolumeMetrics)
    deep_diagnostics: DeepDiagnosticMetrics = field(default_factory=DeepDiagnosticMetrics)
    issue_evidence: tuple[IssueEvidence, ...] = ()
    checks: tuple[CheckResult, ...] = ()
    timings: tuple[CheckTiming, ...] = ()
    skipped_check_reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible dictionary in stable dataclass field order."""

        return _plain(self)

    def to_json(self) -> str:
        """Return readable deterministic UTF-8-compatible JSON text."""

        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n"
