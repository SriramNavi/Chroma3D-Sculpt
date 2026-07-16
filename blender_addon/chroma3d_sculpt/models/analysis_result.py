"""Serializable typed models for one read-only mesh analysis."""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime
from enum import Enum
import json
from typing import Any


class AnalysisSeverity(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


class EvaluationStatus(str, Enum):
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class NormalConsistencyState(str, Enum):
    CONSISTENT = "CONSISTENT"
    POTENTIALLY_INCONSISTENT = "POTENTIALLY_INCONSISTENT"
    NOT_EVALUATED = "NOT_EVALUATED"


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
    triangle_source: str = "ORIGINAL_POLYGON_TRIANGULATION_ESTIMATE"


@dataclass(frozen=True, slots=True)
class DimensionMetrics:
    width_mm: float = 0.0
    depth_mm: float = 0.0
    height_mm: float = 0.0
    unit_system: str = "NONE"
    scene_scale_length: float = 1.0
    millimetres_per_blender_unit: float = 1000.0
    source: str = "OBJECT_DIMENSIONS_WITH_SCALE"


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
    loose_vertices: int = 0
    loose_edges: int = 0
    zero_length_edges: int = 0
    degenerate_faces: int = 0
    connected_components: int = 0
    disconnected_shells: int = 0
    potential_duplicate_vertices: int = 0
    duplicate_evaluation_status: EvaluationStatus = EvaluationStatus.COMPLETED
    normal_consistency: NormalConsistencyState = NormalConsistencyState.NOT_EVALUATED
    normal_consistency_detail: str = "Not evaluated."


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    status: EvaluationStatus
    message: str


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
    object_metadata: ObjectMetadata = field(default_factory=ObjectMetadata)
    geometry: GeometryMetrics = field(default_factory=GeometryMetrics)
    dimensions: DimensionMetrics = field(default_factory=DimensionMetrics)
    transforms: TransformMetrics = field(default_factory=TransformMetrics)
    topology: TopologyMetrics = field(default_factory=TopologyMetrics)
    checks: tuple[CheckResult, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible dictionary in stable field order."""

        return _plain(self)

    def to_json(self) -> str:
        """Return readable deterministic UTF-8-compatible JSON text."""

        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n"

