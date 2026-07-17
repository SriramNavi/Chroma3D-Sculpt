"""Face-shell decomposition metrics, physical measurements, and classification."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from time import perf_counter

from mathutils import Vector

from ..analysis_settings import AnalysisSettings
from ..models.analysis_result import (
    CheckConfidence,
    CheckResult,
    CheckTiming,
    EvaluationStatus,
    IssueCategory,
    IssueDomain,
    IssueEvidence,
    NormalConsistencyState,
    ShellContainmentState,
    ShellMetrics,
    ShellOrientationState,
    SurfaceVolumeMetrics,
    WatertightState,
)
from ..utilities.geometry import WorldTriangle, bounding_box
from .topology_analyzer import TopologyAnalysis


@dataclass(frozen=True, slots=True)
class ShellGeometry:
    shell_id: int
    face_indices: tuple[int, ...]
    vertex_indices: tuple[int, ...]
    edge_indices: tuple[int, ...]
    triangle_indices: tuple[int, ...]
    bbox_min: Vector
    bbox_max: Vector
    centroid: Vector


@dataclass(frozen=True, slots=True)
class ShellAnalysis:
    shells: tuple[ShellMetrics, ...]
    geometries: tuple[ShellGeometry, ...]
    surface_volume: SurfaceVolumeMetrics
    main_shell_id: int | None
    tiny_shell_ids: tuple[int, ...]
    external_shell_ids: tuple[int, ...]
    issue_evidence: tuple[IssueEvidence, ...]
    checks: tuple[CheckResult, ...]
    timings: tuple[CheckTiming, ...]


def _values_mm(vector: Vector, factor: float) -> tuple[float, float, float]:
    return tuple(float(value) * factor for value in vector[:3])  # type: ignore[return-value]


def _select_main_shell(shells: tuple[ShellMetrics, ...]) -> int | None:
    if not shells:
        return None
    reliable = [shell for shell in shells if shell.absolute_volume_mm3 is not None]
    if reliable:
        return max(reliable, key=lambda shell: (shell.absolute_volume_mm3 or 0.0, -shell.shell_id)).shell_id
    with_area = [shell for shell in shells if shell.surface_area_mm2 > 0.0]
    if with_area:
        return max(with_area, key=lambda shell: (shell.surface_area_mm2, -shell.shell_id)).shell_id
    return max(shells, key=lambda shell: (shell.face_count, -shell.shell_id)).shell_id


def _tiny_classification(
    shell: ShellMetrics,
    settings: AnalysisSettings,
) -> tuple[bool, tuple[str, ...], tuple[str, ...], CheckConfidence]:
    evaluated = ["face_count", "bounding_box_diagonal_mm"]
    matched: list[str] = []
    if shell.face_count <= settings.tiny_shell_max_face_count:
        matched.append("face_count")
    diagonal = math.sqrt(sum(value * value for value in shell.dimensions_mm))
    if diagonal <= settings.tiny_shell_max_diagonal_mm:
        matched.append("bounding_box_diagonal_mm")
    if shell.absolute_volume_mm3 is not None:
        evaluated.extend(("absolute_volume_mm3", "relative_volume_percent"))
        if shell.absolute_volume_mm3 <= settings.tiny_shell_max_volume_mm3:
            matched.append("absolute_volume_mm3")
        if (
            shell.relative_volume_percent is not None
            and shell.relative_volume_percent <= settings.tiny_shell_max_relative_volume_percent
        ):
            matched.append("relative_volume_percent")
    candidate = len(matched) >= 2
    confidence = (
        CheckConfidence.HIGH
        if candidate and len(matched) >= 3
        else CheckConfidence.MEDIUM
        if candidate
        else CheckConfidence.NONE
    )
    return candidate, tuple(evaluated), tuple(matched), confidence


def analyze_shells(
    mesh: object,
    topology: TopologyAnalysis,
    world_vertices: tuple[Vector, ...],
    triangles: tuple[WorldTriangle, ...],
    millimetres_per_unit: float,
    settings: AnalysisSettings,
) -> ShellAnalysis:
    timings: list[CheckTiming] = []
    checks: list[CheckResult] = []
    inconsistent_edge_set = set(topology.inconsistent_edge_indices)
    face_to_shell = {
        face_index: shell_id
        for shell_id, face_indices in enumerate(topology.face_shells)
        for face_index in face_indices
    }
    triangles_by_shell: list[list[int]] = [[] for _ in topology.face_shells]
    for triangle in triangles:
        shell_id = face_to_shell.get(triangle.face_index)
        if shell_id is not None:
            triangles_by_shell[shell_id].append(triangle.triangle_index)

    anomaly_vertices = set(topology.vertex_anomaly_indices)

    started_geometry = perf_counter()
    geometries: list[ShellGeometry] = []
    for shell_id, face_indices in enumerate(topology.face_shells):
        edge_indices = tuple(sorted({edge for face in face_indices for edge in topology.face_edges[face]}))
        vertex_indices = tuple(
            sorted({int(vertex) for face in face_indices for vertex in mesh.polygons[face].vertices})  # type: ignore[attr-defined]
        )
        points = tuple(world_vertices[index] for index in vertex_indices)
        minimum, maximum = bounding_box(points)
        centroid = sum(points, Vector((0.0, 0.0, 0.0))) / max(len(points), 1)
        geometry = ShellGeometry(
            shell_id=shell_id,
            face_indices=face_indices,
            vertex_indices=vertex_indices,
            edge_indices=edge_indices,
            triangle_indices=tuple(triangles_by_shell[shell_id]),
            bbox_min=minimum,
            bbox_max=maximum,
            centroid=centroid,
        )
        geometries.append(geometry)
    geometry_elapsed = (perf_counter() - started_geometry) * 1000.0

    started_area = perf_counter()
    surface_areas: list[float] = []
    for geometry in geometries:
        area_bu2 = 0.0
        for triangle_index in geometry.triangle_indices:
            a, b, c = triangles[triangle_index].coordinates
            area_bu2 += float((b - a).cross(c - a).length) * 0.5
        surface_areas.append(area_bu2 * millimetres_per_unit**2)
    area_elapsed = (perf_counter() - started_area) * 1000.0
    timings.append(CheckTiming("surface_area", EvaluationStatus.COMPLETED, area_elapsed))
    checks.append(CheckResult("surface_area", EvaluationStatus.COMPLETED, "World-space triangle surface area calculated in mm^2.", area_elapsed))

    started_volume = perf_counter()
    shells: list[ShellMetrics] = []
    for geometry, surface_area in zip(geometries, surface_areas):
        boundary = sum(1 for edge in geometry.edge_indices if len(topology.edge_faces[edge]) == 1)
        high_incidence = sum(1 for edge in geometry.edge_indices if len(topology.edge_faces[edge]) > 2)
        inconsistent_edges = [edge for edge in geometry.edge_indices if edge in inconsistent_edge_set]
        has_vertex_anomaly = any(vertex in anomaly_vertices for vertex in geometry.vertex_indices)
        closed = boundary == 0 and high_incidence == 0 and not has_vertex_anomaly and bool(geometry.face_indices)
        if not closed:
            watertight = WatertightState.NOT_WATERTIGHT
        else:
            watertight = WatertightState.TOPOLOGICALLY_WATERTIGHT

        signed_volume: float | None = None
        absolute_volume: float | None = None
        if inconsistent_edges:
            consistency = NormalConsistencyState.INCONSISTENT
            orientation = ShellOrientationState.INCONSISTENT
            volume_status = EvaluationStatus.NOT_APPLICABLE
            volume_note = "Volume unavailable because face orientation is inconsistent."
        elif not closed:
            consistency = NormalConsistencyState.OPEN if boundary else NormalConsistencyState.INDETERMINATE
            orientation = ShellOrientationState.OPEN if boundary else ShellOrientationState.INDETERMINATE
            volume_status = EvaluationStatus.NOT_APPLICABLE
            volume_note = "Volume unavailable because the shell is not a closed, valid two-manifold surface."
        else:
            reference = geometry.bbox_min
            signed_bu3 = 0.0
            for triangle_index in geometry.triangle_indices:
                a, b, c = triangles[triangle_index].coordinates
                signed_bu3 += float((a - reference).dot((b - reference).cross(c - reference))) / 6.0
            signed_volume = signed_bu3 * millimetres_per_unit**3
            if abs(signed_volume) <= 1e-12:
                consistency = NormalConsistencyState.INDETERMINATE
                orientation = ShellOrientationState.INDETERMINATE
                volume_status = EvaluationStatus.FAILED
                signed_volume = None
                volume_note = "Closed shell signed volume was numerically indeterminate."
            else:
                consistency = NormalConsistencyState.CONSISTENT
                orientation = ShellOrientationState.OUTWARD if signed_volume > 0.0 else ShellOrientationState.INWARD
                volume_status = EvaluationStatus.COMPLETED
                absolute_volume = abs(signed_volume)
                volume_note = "Positive signed volume is OUTWARD; negative signed volume is INWARD."

        dimensions = geometry.bbox_max - geometry.bbox_min
        shell = ShellMetrics(
            shell_id=geometry.shell_id,
            face_count=len(geometry.face_indices),
            triangle_count=len(geometry.triangle_indices),
            vertex_count=len(geometry.vertex_indices),
            edge_count=len(geometry.edge_indices),
            boundary_edge_count=boundary,
            non_manifold_edge_count=high_incidence,
            bbox_min_mm=_values_mm(geometry.bbox_min, millimetres_per_unit),
            bbox_max_mm=_values_mm(geometry.bbox_max, millimetres_per_unit),
            dimensions_mm=_values_mm(dimensions, millimetres_per_unit),
            surface_area_mm2=surface_area,
            signed_volume_mm3=signed_volume,
            absolute_volume_mm3=absolute_volume,
            volume_status=volume_status,
            centroid_mm=_values_mm(geometry.centroid, millimetres_per_unit),
            watertight_state=watertight,
            orientation_consistency=consistency,
            orientation_state=orientation,
            diagnostic_notes=(volume_note,),
            check_statuses=(
                CheckResult("watertightness", EvaluationStatus.COMPLETED, watertight.value),
                CheckResult("orientation", EvaluationStatus.COMPLETED, orientation.value),
                CheckResult("volume", volume_status, volume_note),
            ),
        )
        shells.append(shell)
    volume_elapsed = (perf_counter() - started_volume) * 1000.0
    timings.append(CheckTiming("volume", EvaluationStatus.COMPLETED, volume_elapsed))
    checks.append(CheckResult("volume", EvaluationStatus.COMPLETED, "Signed volume evaluated only for closed orientation-consistent shells.", volume_elapsed))
    timings.append(CheckTiming("shell_metrics", EvaluationStatus.COMPLETED, geometry_elapsed))

    shell_tuple = tuple(shells)
    main_shell_id = _select_main_shell(shell_tuple)
    largest_volume = max((shell.absolute_volume_mm3 or 0.0 for shell in shell_tuple), default=0.0)
    total_area = sum(shell.surface_area_mm2 for shell in shell_tuple)
    tiny_started = perf_counter()
    classified: list[ShellMetrics] = []
    for shell in shell_tuple:
        relative_volume = (
            (shell.absolute_volume_mm3 or 0.0) / largest_volume * 100.0
            if shell.absolute_volume_mm3 is not None and largest_volume > 0.0
            else None
        )
        relative_area = shell.surface_area_mm2 / total_area * 100.0 if total_area > 0.0 else 0.0
        classification = (
            ShellContainmentState.MAIN_SHELL
            if shell.shell_id == main_shell_id
            else ShellContainmentState.DISCONNECTED_EXTERNAL
        )
        shell = replace(
            shell,
            relative_volume_percent=relative_volume,
            relative_surface_area_percent=relative_area,
            classification=classification,
        )
        if shell.shell_id != main_shell_id:
            tiny, evaluated, matched, confidence = _tiny_classification(shell, settings)
            shell = replace(
                shell,
                tiny_shell_candidate=tiny,
                tiny_criteria_evaluated=evaluated,
                tiny_criteria_matched=matched,
                classification_confidence=confidence,
            )
        classified.append(shell)

    tiny_ids = tuple(shell.shell_id for shell in classified if shell.tiny_shell_candidate)
    external_ids = tuple(shell.shell_id for shell in classified if shell.classification == ShellContainmentState.DISCONNECTED_EXTERNAL)
    tiny_faces = sorted({face for shell_id in tiny_ids for face in geometries[shell_id].face_indices})
    cap = settings.maximum_stored_issue_indices
    tiny_evidence = IssueEvidence(
        category=IssueCategory.TINY_SHELL_FACES,
        domain=IssueDomain.FACE,
        total_count=len(tiny_faces),
        indices=tuple(tiny_faces[:cap]),
        truncated=len(tiny_faces) > cap,
        evidence_cap=cap,
        note="Candidate classification requires at least two configured criteria; separate ornaments may be intentional.",
    )
    reliable_volumes = [shell.absolute_volume_mm3 for shell in classified if shell.absolute_volume_mm3 is not None]
    surface_volume = SurfaceVolumeMetrics(
        surface_area_status=EvaluationStatus.COMPLETED,
        total_surface_area_mm2=total_area,
        volume_status=EvaluationStatus.COMPLETED if reliable_volumes else EvaluationStatus.NOT_APPLICABLE,
        reliable_closed_shell_volume_mm3=sum(reliable_volumes) if reliable_volumes else None,
        reliable_volume_shell_count=len(reliable_volumes),
        unavailable_volume_shell_count=len(classified) - len(reliable_volumes),
        detail=(
            "Reliable total includes only closed, orientation-consistent shells."
            if reliable_volumes
            else "No closed, orientation-consistent shell volume was available."
        ),
    )
    tiny_elapsed = (perf_counter() - tiny_started) * 1000.0
    timings.append(CheckTiming("tiny_shell_classification", EvaluationStatus.COMPLETED, tiny_elapsed))
    checks.append(CheckResult("tiny_shell_classification", EvaluationStatus.COMPLETED, f"{len(tiny_ids)} tiny-shell candidate(s) found using combined criteria.", tiny_elapsed))
    return ShellAnalysis(
        shells=tuple(classified),
        geometries=tuple(geometries),
        surface_volume=surface_volume,
        main_shell_id=main_shell_id,
        tiny_shell_ids=tiny_ids,
        external_shell_ids=external_ids,
        issue_evidence=(tiny_evidence,),
        checks=tuple(checks),
        timings=tuple(timings),
    )
