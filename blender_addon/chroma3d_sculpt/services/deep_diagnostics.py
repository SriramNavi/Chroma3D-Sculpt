"""Bounded BVH self-intersection candidates and shell-containment heuristics."""

from __future__ import annotations

from dataclasses import dataclass, replace
from time import perf_counter

from mathutils import Vector
from mathutils.bvhtree import BVHTree

from ..analysis_settings import AnalysisSettings
from ..models.analysis_result import (
    AnalysisProfile,
    CheckConfidence,
    CheckResult,
    CheckTiming,
    ContainmentEvidence,
    DeepDiagnosticMetrics,
    EvaluationStatus,
    IssueCategory,
    IssueDomain,
    IssueEvidence,
    SelfIntersectionState,
    ShellContainmentState,
    ShellMetrics,
    WatertightState,
)
from ..utilities.geometry import WorldTriangle
from .shell_analyzer import ShellAnalysis


@dataclass(frozen=True, slots=True)
class DeepAnalysis:
    metrics: DeepDiagnosticMetrics
    shells: tuple[ShellMetrics, ...]
    issue_evidence: tuple[IssueEvidence, ...]
    checks: tuple[CheckResult, ...]
    timings: tuple[CheckTiming, ...]


def _self_intersections(
    world_vertices: tuple[Vector, ...],
    triangles: tuple[WorldTriangle, ...],
    settings: AnalysisSettings,
) -> tuple[EvaluationStatus, SelfIntersectionState, int | None, tuple[tuple[int, int], ...], bool, str, tuple[int, ...]]:
    triangle_count = len(triangles)
    if triangle_count > settings.self_intersection_triangle_limit:
        return (
            EvaluationStatus.SKIPPED,
            SelfIntersectionState.SKIPPED_LIMIT,
            None,
            (),
            False,
            f"Skipped: {triangle_count:,} triangles exceed the configured limit of {settings.self_intersection_triangle_limit:,}.",
            (),
        )
    if not triangles:
        return (
            EvaluationStatus.NOT_APPLICABLE,
            SelfIntersectionState.NOT_EVALUATED,
            None,
            (),
            False,
            "No triangles were available.",
            (),
        )
    bvh = BVHTree.FromPolygons(
        world_vertices,
        [triangle.vertex_indices for triangle in triangles],
        all_triangles=True,
        epsilon=1e-9,
    )
    raw_pairs = bvh.overlap(bvh)
    triangle_vertex_sets = tuple(frozenset(triangle.vertex_indices) for triangle in triangles)
    face_pairs: set[tuple[int, int]] = set()
    for left_index, right_index in raw_pairs:
        if left_index == right_index:
            continue
        left, right = triangles[left_index], triangles[right_index]
        if left.face_index == right.face_index:
            continue
        if triangle_vertex_sets[left_index].intersection(triangle_vertex_sets[right_index]):
            continue
        pair = tuple(sorted((left.face_index, right.face_index)))
        face_pairs.add(pair)
    ordered = tuple(sorted(face_pairs))
    cap = settings.maximum_stored_self_intersection_pairs
    stored = ordered[:cap]
    faces = tuple(sorted({face for pair in stored for face in pair}))
    state = SelfIntersectionState.CANDIDATES_DETECTED if ordered else SelfIntersectionState.NO_CANDIDATES_DETECTED
    detail = (
        f"{len(ordered)} BVH overlap candidate face pair(s) remained after shared-topology filtering."
        if ordered
        else "No BVH overlap candidates remained after shared-topology filtering."
    )
    return EvaluationStatus.COMPLETED, state, len(ordered), stored, len(ordered) > cap, detail, faces


_RAY_DIRECTIONS = tuple(
    Vector(values).normalized()
    for values in ((1.0, 0.173, 0.311), (-0.271, 1.0, 0.419), (0.337, -0.229, 1.0))
)


def _ray_parity(point: Vector, bvh: BVHTree, maximum_distance: float) -> bool:
    positive_directions = 0
    epsilon = max(maximum_distance * 1e-8, 1e-8)
    for direction in _RAY_DIRECTIONS:
        origin = point.copy()
        travelled = 0.0
        intersections = 0
        for _iteration in range(128):
            location, _normal, _index, distance = bvh.ray_cast(
                origin,
                direction,
                max(maximum_distance - travelled, 0.0),
            )
            if location is None or distance is None:
                break
            intersections += 1
            step = float(distance) + epsilon
            travelled += step
            if travelled >= maximum_distance:
                break
            origin = location + direction * epsilon
        if intersections % 2 == 1:
            positive_directions += 1
    return positive_directions >= 2


def _bbox_contains(outer_min: Vector, outer_max: Vector, inner_min: Vector, inner_max: Vector) -> bool:
    tolerance = 1e-7
    return all(
        outer_min[axis] <= inner_min[axis] + tolerance and outer_max[axis] >= inner_max[axis] - tolerance
        for axis in range(3)
    )


def _containment(
    world_vertices: tuple[Vector, ...],
    triangles: tuple[WorldTriangle, ...],
    shell_analysis: ShellAnalysis,
    settings: AnalysisSettings,
) -> tuple[EvaluationStatus, tuple[ContainmentEvidence, ...], str, int, int]:
    shell_count = len(shell_analysis.shells)
    triangle_count = len(triangles)
    if shell_count > settings.containment_shell_limit:
        return (
            EvaluationStatus.SKIPPED,
            (),
            f"Skipped: {shell_count:,} shells exceed the configured limit of {settings.containment_shell_limit:,}.",
            shell_count,
            settings.containment_shell_limit,
        )
    if triangle_count > settings.containment_triangle_limit:
        return (
            EvaluationStatus.SKIPPED,
            (),
            f"Skipped: {triangle_count:,} triangles exceed the configured limit of {settings.containment_triangle_limit:,}.",
            triangle_count,
            settings.containment_triangle_limit,
        )

    evidence: list[ContainmentEvidence] = []
    geometry_by_id = {geometry.shell_id: geometry for geometry in shell_analysis.geometries}
    valid = [
        shell
        for shell in shell_analysis.shells
        if shell.watertight_state == WatertightState.TOPOLOGICALLY_WATERTIGHT
        and shell.absolute_volume_mm3 is not None
    ]
    excluded_count = shell_count - len(valid)
    for outer in sorted(valid, key=lambda item: item.shell_id):
        outer_geometry = geometry_by_id[outer.shell_id]
        outer_triangles = [triangles[index].vertex_indices for index in outer_geometry.triangle_indices]
        if not outer_triangles:
            continue
        bvh = BVHTree.FromPolygons(world_vertices, outer_triangles, all_triangles=True, epsilon=1e-9)
        maximum_distance = max(float((outer_geometry.bbox_max - outer_geometry.bbox_min).length) * 4.0, 1.0)
        for inner in sorted(valid, key=lambda item: item.shell_id):
            if inner.shell_id == outer.shell_id or (inner.absolute_volume_mm3 or 0.0) >= (outer.absolute_volume_mm3 or 0.0):
                continue
            inner_geometry = geometry_by_id[inner.shell_id]
            if not _bbox_contains(
                outer_geometry.bbox_min,
                outer_geometry.bbox_max,
                inner_geometry.bbox_min,
                inner_geometry.bbox_max,
            ):
                continue
            sample_points = [
                inner_geometry.centroid,
                (inner_geometry.bbox_min + inner_geometry.bbox_max) * 0.5,
            ]
            if inner_geometry.triangle_indices:
                a, b, c = triangles[inner_geometry.triangle_indices[0]].coordinates
                sample_points.append((a + b + c) / 3.0)
            votes = sum(1 for point in sample_points if _ray_parity(point, bvh, maximum_distance))
            if votes * 2 <= len(sample_points):
                continue
            confidence = (
                CheckConfidence.HIGH
                if votes == len(sample_points)
                else CheckConfidence.MEDIUM
                if votes >= 2
                else CheckConfidence.LOW
            )
            evidence.append(
                ContainmentEvidence(
                    containing_shell_id=outer.shell_id,
                    candidate_shell_id=inner.shell_id,
                    broad_phase_bbox_contained=True,
                    sample_count=len(sample_points),
                    positive_votes=votes,
                    confidence=confidence,
                )
            )
    return (
        EvaluationStatus.COMPLETED,
        tuple(evidence),
        (
            f"Evaluated {len(valid)} closed shell(s) with AABB and deterministic ray-parity voting; "
            f"{excluded_count} open or volume-indeterminate shell(s) remained unclassified."
        ),
        triangle_count,
        settings.containment_triangle_limit,
    )


def analyze_deep_diagnostics(
    world_vertices: tuple[Vector, ...],
    triangles: tuple[WorldTriangle, ...],
    shell_analysis: ShellAnalysis,
    settings: AnalysisSettings,
) -> DeepAnalysis:
    cap = settings.maximum_stored_issue_indices
    if settings.profile != AnalysisProfile.DEEP:
        note = "Deep diagnostics were not requested by the Standard profile."
        metrics = DeepDiagnosticMetrics(notes=(note,))
        evidence = (
            IssueEvidence(IssueCategory.POSSIBLE_INTERNAL_SHELL_FACES, IssueDomain.FACE, 0, evidence_cap=cap, note=note),
            IssueEvidence(IssueCategory.SELF_INTERSECTION_FACES, IssueDomain.FACE, 0, evidence_cap=cap, note=note),
        )
        checks = (
            CheckResult("self_intersection_candidates", EvaluationStatus.NOT_APPLICABLE, note),
            CheckResult("containment_analysis", EvaluationStatus.NOT_APPLICABLE, note),
        )
        timings = (
            CheckTiming("self_intersection_candidate_detection", EvaluationStatus.NOT_APPLICABLE, 0.0, note),
            CheckTiming("containment_analysis", EvaluationStatus.NOT_APPLICABLE, 0.0, note),
        )
        return DeepAnalysis(metrics, shell_analysis.shells, evidence, checks, timings)

    started = perf_counter()
    self_status, self_state, candidate_count, pairs, truncated, self_note, self_faces = _self_intersections(
        world_vertices,
        triangles,
        settings,
    )
    self_elapsed = (perf_counter() - started) * 1000.0

    started = perf_counter()
    containment_status, containment_evidence, containment_note, containment_actual, containment_limit = _containment(
        world_vertices,
        triangles,
        shell_analysis,
        settings,
    )
    containment_elapsed = (perf_counter() - started) * 1000.0

    internal_ids = tuple(sorted({item.candidate_shell_id for item in containment_evidence}))
    evidence_by_candidate = {item.candidate_shell_id: item for item in containment_evidence}
    containment_eligible_ids = {
        shell.shell_id
        for shell in shell_analysis.shells
        if shell.watertight_state == WatertightState.TOPOLOGICALLY_WATERTIGHT
        and shell.absolute_volume_mm3 is not None
    }
    classified_shells: list[ShellMetrics] = []
    for shell in shell_analysis.shells:
        if shell.shell_id in evidence_by_candidate:
            evidence = evidence_by_candidate[shell.shell_id]
            shell = replace(
                shell,
                classification=ShellContainmentState.POSSIBLY_INTERNAL,
                containing_shell_id=evidence.containing_shell_id,
                classification_confidence=evidence.confidence,
            )
        elif shell.shell_id != shell_analysis.main_shell_id and (
            containment_status != EvaluationStatus.COMPLETED
            or shell.shell_id not in containment_eligible_ids
        ):
            shell = replace(
                shell,
                classification=ShellContainmentState.UNCLASSIFIED,
                containing_shell_id=None,
            )
        classified_shells.append(shell)
    shells = tuple(classified_shells)
    internal_faces = sorted(
        {
            face
            for shell_id in internal_ids
            for face in shell_analysis.geometries[shell_id].face_indices
        }
    )
    issue_evidence = (
        IssueEvidence(
            category=IssueCategory.SELF_INTERSECTION_FACES,
            domain=IssueDomain.FACE,
            total_count=len(self_faces),
            indices=self_faces[:cap],
            pairs=pairs,
            truncated=truncated or len(self_faces) > cap,
            evidence_cap=cap,
            note=self_note,
        ),
        IssueEvidence(
            category=IssueCategory.POSSIBLE_INTERNAL_SHELL_FACES,
            domain=IssueDomain.FACE,
            total_count=len(internal_faces),
            indices=tuple(internal_faces[:cap]),
            truncated=len(internal_faces) > cap,
            evidence_cap=cap,
            note=containment_note,
        ),
    )
    metrics = DeepDiagnosticMetrics(
        self_intersection_status=self_status,
        self_intersection_state=self_state,
        self_intersection_candidate_count=candidate_count,
        self_intersection_pairs=pairs,
        self_intersection_evidence_truncated=truncated,
        containment_status=containment_status,
        possible_internal_shell_ids=internal_ids,
        containment_evidence=containment_evidence,
        notes=(self_note, containment_note),
    )
    checks = (
        CheckResult(
            "self_intersection_candidates",
            self_status,
            self_note,
            self_elapsed,
            actual_size=len(triangles),
            configured_limit=settings.self_intersection_triangle_limit,
        ),
        CheckResult(
            "containment_analysis",
            containment_status,
            containment_note,
            containment_elapsed,
            actual_size=containment_actual,
            configured_limit=containment_limit,
        ),
    )
    timings = (
        CheckTiming("self_intersection_candidate_detection", self_status, self_elapsed, self_note),
        CheckTiming("containment_analysis", containment_status, containment_elapsed, containment_note),
    )
    return DeepAnalysis(metrics, shells, issue_evidence, checks, timings)
