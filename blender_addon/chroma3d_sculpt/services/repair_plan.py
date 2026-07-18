"""Read-only repair-plan generation from current bounded evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ..models.analysis_result import NormalConsistencyState, ShellOrientationState
from ..models.repair_models import (
    RepairOperationType,
    RepairPlan,
    RepairPlanItem,
    RepairPlanStatus,
    RepairSession,
)
from ..repair_settings import RepairSettings
from ..utilities.boundary_loops import detect_small_hole_candidates
from ..utilities.repair_signatures import repair_workspace_signature
from .repair_operations import degenerate_face_indices, duplicate_clusters, tiny_shell_candidates
from .repair_session import get_current_analysis


def generate_plan(session: RepairSession, workspace: object, factor: float, settings: RepairSettings) -> RepairPlan:
    result = get_current_analysis(session)
    if result is None or result.analysis_id != session.current_analysis_id:
        raise RuntimeError("Analyze the repair workspace before generating a plan.")
    signature_before = repair_workspace_signature(workspace)
    if signature_before != session.current_workspace_signature:
        raise RuntimeError("Repair workspace changed outside the session. Analyze it and generate a new plan.")

    duplicate_count = sum(len(cluster) - 1 for cluster in duplicate_clusters(workspace, factor, settings.merge_distance_mm))
    zero_count = result.topology.zero_length_edges
    degenerate_count = len(degenerate_face_indices(workspace, factor, settings.degenerate_face_area_tolerance_mm2))
    loose_count = result.topology.loose_edges + result.topology.loose_vertices
    inconsistent = result.topology.normal_consistency == NormalConsistencyState.INCONSISTENT
    inward = sum(shell.orientation_state == ShellOrientationState.INWARD for shell in result.shells)
    tiny = list(tiny_shell_candidates(workspace, factor, result, settings))
    holes = list(detect_small_hole_candidates(workspace, factor, settings))

    items = [
        RepairPlanItem(RepairOperationType.MERGE_DUPLICATE_VERTICES, duplicate_count > 0, duplicate_count > 0, "Potential nearby duplicate vertices detected." if duplicate_count else "No nearby duplicate vertices detected.", duplicate_count),
        RepairPlanItem(RepairOperationType.COLLAPSE_ZERO_LENGTH_EDGES, zero_count > 0, zero_count > 0, "Zero-length edges detected." if zero_count else "No zero-length edges detected.", zero_count),
        RepairPlanItem(RepairOperationType.REMOVE_DEGENERATE_FACES, degenerate_count > 0, degenerate_count > 0, "Degenerate faces detected." if degenerate_count else "No degenerate faces detected.", degenerate_count, ("Loose geometry created by face removal is retained unless loose cleanup is selected.",)),
        RepairPlanItem(RepairOperationType.REMOVE_LOOSE_GEOMETRY, loose_count > 0, loose_count > 0, "Loose edges or vertices detected." if loose_count else "No loose geometry detected.", loose_count),
        RepairPlanItem(RepairOperationType.REMOVE_SELECTED_TINY_SHELLS, bool(tiny), False, "Tiny-shell candidates require explicit review and selection." if tiny else "No tiny-shell candidates detected.", len(tiny)),
        RepairPlanItem(RepairOperationType.FILL_SELECTED_SMALL_HOLES, bool(holes), False, "Bounded small-hole candidates require explicit review and selection." if holes else "No eligible bounded small holes detected.", len(holes)),
        RepairPlanItem(RepairOperationType.REPAIR_NORMAL_CONSISTENCY, inconsistent, False, "Inconsistent face orientation detected; explicit selection is required." if inconsistent else "No inconsistent face orientation detected.", result.topology.face_shell_count if inconsistent else 0),
        RepairPlanItem(RepairOperationType.ORIENT_CLOSED_SHELLS_OUTWARD, inward > 0, False, "Inward valid closed shell detected; explicit selection is required." if inward else "No inward valid closed shell detected.", inward),
    ]
    signature_after = repair_workspace_signature(workspace)
    if signature_after != signature_before:
        raise RuntimeError("Repair-plan generation unexpectedly changed workspace geometry.")
    return RepairPlan(
        plan_id=str(uuid4()),
        session_id=session.session_id,
        created_at=datetime.now(timezone.utc),
        status=RepairPlanStatus.READY,
        workspace_signature=signature_before,
        source_signature=session.source_signature,
        analysis_id=result.analysis_id,
        selected_profile=result.analysis_profile.value,
        settings_snapshot=settings.snapshot(),
        items=items,
        candidates=tiny + holes,
        warnings=["Candidate removal and filling are never preselected.", "Normal repair and shell orientation require explicit selection."],
        limitations=("Repair candidates are evidence-based and require human review.", "The plan is session-only and becomes stale after geometry changes."),
    )
