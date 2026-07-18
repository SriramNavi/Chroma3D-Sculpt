"""Typed, JSON-safe models for controlled Sprint 2 mesh repair."""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime
from enum import Enum
import json
from typing import Any


class RepairSessionStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    ACTIVE = "ACTIVE"
    PLAN_READY = "PLAN_READY"
    REPAIRING = "REPAIRING"
    REPAIRED = "REPAIRED"
    ACCEPTED = "ACCEPTED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"


class RepairPlanStatus(str, Enum):
    NOT_GENERATED = "NOT_GENERATED"
    READY = "READY"
    STALE = "STALE"
    APPLIED = "APPLIED"


class RepairOperationType(str, Enum):
    MERGE_DUPLICATE_VERTICES = "MERGE_DUPLICATE_VERTICES"
    COLLAPSE_ZERO_LENGTH_EDGES = "COLLAPSE_ZERO_LENGTH_EDGES"
    REMOVE_DEGENERATE_FACES = "REMOVE_DEGENERATE_FACES"
    REMOVE_LOOSE_GEOMETRY = "REMOVE_LOOSE_GEOMETRY"
    REMOVE_SELECTED_TINY_SHELLS = "REMOVE_SELECTED_TINY_SHELLS"
    FILL_SELECTED_SMALL_HOLES = "FILL_SELECTED_SMALL_HOLES"
    REPAIR_NORMAL_CONSISTENCY = "REPAIR_NORMAL_CONSISTENCY"
    ORIENT_CLOSED_SHELLS_OUTWARD = "ORIENT_CLOSED_SHELLS_OUTWARD"


SAFE_OPERATION_ORDER = tuple(RepairOperationType)


class RepairOperationStatus(str, Enum):
    PLANNED = "PLANNED"
    APPLIED = "APPLIED"
    NO_CHANGE = "NO_CHANGE"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    UNDONE = "UNDONE"


class RepairDecision(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    ROLLED_BACK = "ROLLED_BACK"


class RepairConfidence(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RepairCandidateType(str, Enum):
    TINY_SHELL = "TINY_SHELL"
    SMALL_HOLE = "SMALL_HOLE"


def plain_value(value: Any) -> Any:
    """Convert repair data into deterministic JSON-compatible values."""

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {item.name: plain_value(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return {str(key): plain_value(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (tuple, list)):
        return [plain_value(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class RepairSettingsSnapshot:
    merge_distance_mm: float = 0.001
    zero_length_edge_tolerance_mm: float = 0.000001
    degenerate_face_area_tolerance_mm2: float = 0.00000001
    maximum_stored_candidate_indices: int = 10_000
    maximum_repair_checkpoints: int = 3
    small_hole_maximum_edge_count: int = 12
    small_hole_maximum_perimeter_mm: float = 2.0
    small_hole_maximum_diagonal_mm: float = 1.0
    tiny_shell_requires_selection: bool = True
    hole_fill_requires_selection: bool = True
    normal_repair_requires_selection: bool = True


@dataclass(slots=True)
class RepairCandidate:
    candidate_id: str
    candidate_type: RepairCandidateType
    mapping_sha256: str
    selected: bool = False
    eligible: bool = True
    confidence: RepairConfidence = RepairConfidence.MEDIUM
    shell_id: int | None = None
    face_indices: tuple[int, ...] = ()
    edge_indices: tuple[int, ...] = ()
    vertex_indices: tuple[int, ...] = ()
    total_face_count: int = 0
    total_edge_count: int = 0
    total_vertex_count: int = 0
    surface_area_mm2: float | None = None
    volume_mm3: float | None = None
    perimeter_mm: float | None = None
    diagonal_mm: float | None = None
    relative_size_percent: float | None = None
    criteria_matched: tuple[str, ...] = ()
    rejection_reason: str = ""
    evidence_truncated: bool = False


@dataclass(slots=True)
class RepairPlanItem:
    operation_type: RepairOperationType
    recommended: bool
    selected: bool
    recommendation_reason: str
    estimated_target_count: int = 0
    warnings: tuple[str, ...] = ()


@dataclass(slots=True)
class RepairPlan:
    plan_id: str
    session_id: str
    created_at: datetime
    status: RepairPlanStatus
    workspace_signature: str
    source_signature: str
    analysis_id: str
    selected_profile: str
    settings_snapshot: RepairSettingsSnapshot
    items: list[RepairPlanItem] = field(default_factory=list)
    candidates: list[RepairCandidate] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: tuple[str, ...] = ()

    def selected_operations(self) -> tuple[RepairOperationType, ...]:
        selected = {item.operation_type for item in self.items if item.selected}
        if any(candidate.selected for candidate in self.candidates if candidate.candidate_type == RepairCandidateType.TINY_SHELL):
            selected.add(RepairOperationType.REMOVE_SELECTED_TINY_SHELLS)
        if any(candidate.selected for candidate in self.candidates if candidate.candidate_type == RepairCandidateType.SMALL_HOLE):
            selected.add(RepairOperationType.FILL_SELECTED_SMALL_HOLES)
        return tuple(operation for operation in SAFE_OPERATION_ORDER if operation in selected)


@dataclass(slots=True)
class RepairCheckpointRecord:
    checkpoint_id: str
    operation_id: str
    created_at: datetime
    workspace_signature: str
    mesh_datablock_identity: int
    vertex_count: int
    edge_count: int
    face_count: int
    initial: bool = False
    retained: bool = True


@dataclass(slots=True)
class RepairOperationRecord:
    operation_id: str
    operation_type: RepairOperationType
    status: RepairOperationStatus
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: float = 0.0
    checkpoint_id: str = ""
    before_workspace_signature: str = ""
    after_workspace_signature: str = ""
    before_analysis_id: str = ""
    after_analysis_id: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    counts_before: dict[str, int] = field(default_factory=dict)
    counts_after: dict[str, int] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: str = ""


@dataclass(frozen=True, slots=True)
class RepairOperationOutcome:
    status: RepairOperationStatus
    metrics: dict[str, Any]
    warnings: tuple[str, ...] = ()


@dataclass(slots=True)
class RepairComparison:
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)
    deltas: dict[str, Any] = field(default_factory=dict)
    improved: tuple[str, ...] = ()
    unchanged: tuple[str, ...] = ()
    regressed: tuple[str, ...] = ()
    skipped_checks: tuple[str, ...] = ()
    failed_checks: tuple[str, ...] = ()


@dataclass(slots=True)
class RepairSession:
    session_id: str
    started_at: datetime
    status: RepairSessionStatus
    source_object_name: str
    source_object_identity: int
    source_mesh_name: str
    source_mesh_identity: int
    workspace_object_name: str
    workspace_object_identity: int
    workspace_mesh_name: str
    workspace_mesh_identity: int
    source_signature: str
    source_snapshot: dict[str, Any]
    initial_workspace_signature: str
    current_workspace_signature: str
    settings_snapshot: RepairSettingsSnapshot
    initial_checkpoint_id: str
    captured_active_identity: int | None = None
    captured_selected_identities: tuple[int, ...] = ()
    plan: RepairPlan | None = None
    operation_records: list[RepairOperationRecord] = field(default_factory=list)
    checkpoint_records: list[RepairCheckpointRecord] = field(default_factory=list)
    undo_records: list[dict[str, Any]] = field(default_factory=list)
    before_analysis: dict[str, Any] = field(default_factory=dict)
    final_analysis: dict[str, Any] = field(default_factory=dict)
    current_analysis_id: str = ""
    comparison: RepairComparison | None = None
    decision: RepairDecision = RepairDecision.PENDING
    ended_at: datetime | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n"


@dataclass(frozen=True, slots=True)
class RepairAudit:
    schema_version: str
    extension_version: str
    analysis_schema_version: str
    blender_version: str
    operating_system: str
    exported_at: datetime
    session: dict[str, Any]
    source_protection_signature: str
    initial_workspace_signature: str
    final_workspace_signature: str
    final_decision: RepairDecision
    failure_records: tuple[dict[str, Any], ...] = ()
    known_limitations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return plain_value(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n"
