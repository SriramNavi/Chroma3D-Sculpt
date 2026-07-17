"""Linear-time topology diagnostics on the original mesh datablock."""

from __future__ import annotations

from array import array
from dataclasses import dataclass
import math
from time import perf_counter
from typing import Any

from ..analysis_settings import AnalysisSettings
from ..models.analysis_result import (
    CheckResult,
    CheckTiming,
    EdgeManifoldState,
    EvaluationStatus,
    IssueCategory,
    IssueDomain,
    IssueEvidence,
    NormalConsistencyState,
    TopologyMetrics,
    VertexManifoldState,
    WatertightState,
)


@dataclass(frozen=True, slots=True)
class TopologyAnalysis:
    metrics: TopologyMetrics
    edge_faces: tuple[tuple[int, ...], ...]
    face_edges: tuple[tuple[int, ...], ...]
    face_shells: tuple[tuple[int, ...], ...]
    inconsistent_edge_indices: tuple[int, ...]
    inconsistent_face_indices: tuple[int, ...]
    vertex_anomaly_indices: tuple[int, ...]
    issue_evidence: tuple[IssueEvidence, ...]
    checks: tuple[CheckResult, ...]
    timings: tuple[CheckTiming, ...]


def _bounded_evidence(
    category: IssueCategory,
    domain: IssueDomain,
    indices: list[int] | tuple[int, ...],
    cap: int,
    note: str = "",
) -> IssueEvidence:
    ordered = tuple(sorted(set(int(index) for index in indices)))
    return IssueEvidence(
        category=category,
        domain=domain,
        total_count=len(ordered),
        indices=ordered[:cap],
        truncated=len(ordered) > cap,
        evidence_cap=cap,
        note=note,
    )


def _connected_component_count(vertex_count: int, edges: Any) -> int:
    if vertex_count == 0:
        return 0
    parent = array("I", range(vertex_count))
    rank = bytearray(vertex_count)

    def find(index: int) -> int:
        root = index
        while parent[root] != root:
            root = parent[root]
        while parent[index] != index:
            next_index = parent[index]
            parent[index] = root
            index = next_index
        return root

    for edge in edges:
        left, right = int(edge.vertices[0]), int(edge.vertices[1])
        root_left, root_right = find(left), find(right)
        if root_left == root_right:
            continue
        if rank[root_left] < rank[root_right]:
            root_left, root_right = root_right, root_left
        parent[root_right] = root_left
        if rank[root_left] == rank[root_right]:
            rank[root_left] += 1
    return sum(1 for index in range(vertex_count) if find(index) == index)


def potential_duplicate_count(
    vertices: Any,
    settings: AnalysisSettings,
) -> tuple[int, EvaluationStatus, str]:
    vertex_count = len(vertices)
    if vertex_count > settings.duplicate_vertex_limit:
        return (
            0,
            EvaluationStatus.SKIPPED,
            f"Skipped: {vertex_count:,} vertices exceed the configured limit of {settings.duplicate_vertex_limit:,}.",
        )

    inverse = 1.0 / settings.duplicate_position_tolerance
    tolerance_squared = settings.duplicate_position_tolerance**2
    buckets: dict[tuple[int, int, int], list[tuple[float, float, float]]] = {}
    duplicates = 0
    for vertex in vertices:
        coordinate = tuple(float(item) for item in vertex.co[:3])
        cell = tuple(math.floor(value * inverse) for value in coordinate)
        matched = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for candidate in buckets.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), ()):
                        if sum((left - right) ** 2 for left, right in zip(coordinate, candidate)) <= tolerance_squared:
                            duplicates += 1
                            matched = True
                            break
                    if matched:
                        break
                if matched:
                    break
            if matched:
                break
        if not matched:
            buckets.setdefault(cell, []).append(coordinate)
    return duplicates, EvaluationStatus.COMPLETED, "Spatial-hash duplicate-position check completed in object-local coordinates."


def _shell_decomposition(
    face_edges: tuple[tuple[int, ...], ...],
    edge_faces: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    visited = bytearray(len(face_edges))
    shells: list[tuple[int, ...]] = []
    for seed in range(len(face_edges)):
        if visited[seed]:
            continue
        visited[seed] = 1
        stack = [seed]
        faces: list[int] = []
        while stack:
            face_index = stack.pop()
            faces.append(face_index)
            for edge_index in face_edges[face_index]:
                for neighbor in edge_faces[edge_index]:
                    if not visited[neighbor]:
                        visited[neighbor] = 1
                        stack.append(neighbor)
        shells.append(tuple(sorted(faces)))
    return tuple(sorted(shells, key=lambda item: item[0] if item else -1))


def _vertex_manifold_anomalies(
    mesh: Any,
    edge_faces: tuple[tuple[int, ...], ...],
) -> tuple[int, ...]:
    vertex_faces: list[list[int]] = [[] for _ in mesh.vertices]
    vertex_edges: list[list[int]] = [[] for _ in mesh.vertices]
    for polygon in mesh.polygons:
        for vertex_index in polygon.vertices:
            vertex_faces[int(vertex_index)].append(int(polygon.index))
    for edge in mesh.edges:
        edge_index = int(edge.index)
        for vertex_index in edge.vertices:
            vertex_edges[int(vertex_index)].append(edge_index)

    anomalies: list[int] = []
    for vertex_index, incident_faces_list in enumerate(vertex_faces):
        if not incident_faces_list:
            continue
        incident_faces = set(incident_faces_list)
        if any(len(edge_faces[edge_index]) > 2 for edge_index in vertex_edges[vertex_index]):
            anomalies.append(vertex_index)
            continue
        seed = min(incident_faces)
        visited = {seed}
        stack = [seed]
        while stack:
            current = stack.pop()
            for edge_index in vertex_edges[vertex_index]:
                linked = edge_faces[edge_index]
                if current not in linked:
                    continue
                for neighbor in linked:
                    if neighbor in incident_faces and neighbor not in visited:
                        visited.add(neighbor)
                        stack.append(neighbor)
        if len(visited) != len(incident_faces):
            anomalies.append(vertex_index)
    return tuple(anomalies)


def analyze_topology(mesh: Any, settings: AnalysisSettings) -> TopologyAnalysis:
    timings: list[CheckTiming] = []
    checks: list[CheckResult] = []

    started = perf_counter()
    edge_faces_lists: list[list[int]] = [[] for _ in mesh.edges]
    edge_orientations: list[list[int]] = [[] for _ in mesh.edges]
    face_edges_lists: list[tuple[int, ...]] = []
    for polygon in mesh.polygons:
        polygon_edges: list[int] = []
        loop_start = int(polygon.loop_start)
        loop_total = int(polygon.loop_total)
        for offset in range(loop_total):
            loop_index = loop_start + offset
            next_loop_index = loop_start + ((offset + 1) % loop_total)
            edge_index = int(mesh.loops[loop_index].edge_index)
            start_vertex = int(mesh.loops[loop_index].vertex_index)
            end_vertex = int(mesh.loops[next_loop_index].vertex_index)
            edge = mesh.edges[edge_index]
            orientation = 1 if (start_vertex == edge.vertices[0] and end_vertex == edge.vertices[1]) else 0
            edge_faces_lists[edge_index].append(int(polygon.index))
            edge_orientations[edge_index].append(orientation)
            polygon_edges.append(edge_index)
        face_edges_lists.append(tuple(polygon_edges))
    edge_faces = tuple(tuple(items) for items in edge_faces_lists)
    face_edges = tuple(face_edges_lists)
    elapsed = (perf_counter() - started) * 1000.0
    timings.append(CheckTiming("base_topology", EvaluationStatus.COMPLETED, elapsed, "Face-edge incidence collected."))
    checks.append(CheckResult("base_topology", EvaluationStatus.COMPLETED, "Face-edge incidence collected from the original mesh.", elapsed))

    started = perf_counter()
    loose_edges = [index for index, faces in enumerate(edge_faces) if len(faces) == 0]
    boundary_edges = [index for index, faces in enumerate(edge_faces) if len(faces) == 1]
    manifold_edges = [index for index, faces in enumerate(edge_faces) if len(faces) == 2]
    high_incidence = [index for index, faces in enumerate(edge_faces) if len(faces) > 2]
    inconsistent_edges = [
        index
        for index in manifold_edges
        if len(edge_orientations[index]) == 2 and edge_orientations[index][0] == edge_orientations[index][1]
    ]
    inconsistent_faces = sorted({face for edge_index in inconsistent_edges for face in edge_faces[edge_index]})
    edge_elapsed = (perf_counter() - started) * 1000.0
    timings.append(CheckTiming("edge_manifold_classification", EvaluationStatus.COMPLETED, edge_elapsed))
    checks.append(CheckResult("edge_manifold_classification", EvaluationStatus.COMPLETED, "Every edge was classified by linked-face count.", edge_elapsed))

    started = perf_counter()
    degree = array("I", [0]) * len(mesh.vertices)
    zero_length_edges: list[int] = []
    tolerance_squared = settings.degenerate_edge_tolerance**2
    for edge in mesh.edges:
        left, right = int(edge.vertices[0]), int(edge.vertices[1])
        degree[left] += 1
        degree[right] += 1
        if float((mesh.vertices[left].co - mesh.vertices[right].co).length_squared) <= tolerance_squared:
            zero_length_edges.append(int(edge.index))
    loose_vertices = [index for index, value in enumerate(degree) if value == 0]
    degenerate_faces = [
        int(polygon.index) for polygon in mesh.polygons if float(polygon.area) <= settings.degenerate_face_tolerance
    ]
    components = _connected_component_count(len(mesh.vertices), mesh.edges)
    topology_elapsed = (perf_counter() - started) * 1000.0
    timings.append(CheckTiming("topology_defects", EvaluationStatus.COMPLETED, topology_elapsed))

    started = perf_counter()
    vertex_anomalies = _vertex_manifold_anomalies(mesh, edge_faces)
    vertex_elapsed = (perf_counter() - started) * 1000.0
    vertex_state = VertexManifoldState.ANOMALIES_DETECTED if vertex_anomalies else VertexManifoldState.MANIFOLD
    timings.append(CheckTiming("vertex_manifold_classification", EvaluationStatus.COMPLETED, vertex_elapsed))
    checks.append(CheckResult("vertex_manifold_classification", EvaluationStatus.COMPLETED, "Local face-fan connectivity evaluated at every incident vertex.", vertex_elapsed))

    started = perf_counter()
    shells = _shell_decomposition(face_edges, edge_faces)
    shell_elapsed = (perf_counter() - started) * 1000.0
    timings.append(CheckTiming("shell_decomposition", EvaluationStatus.COMPLETED, shell_elapsed))
    checks.append(CheckResult("shell_decomposition", EvaluationStatus.COMPLETED, f"Found {len(shells)} face-connected shell(s).", shell_elapsed))

    if inconsistent_edges:
        normal_state = NormalConsistencyState.INCONSISTENT
        normal_detail = f"{len(inconsistent_edges)} shared edge(s) have equal adjacent-face winding."
    elif high_incidence or loose_edges:
        normal_state = NormalConsistencyState.INDETERMINATE
        normal_detail = "Loose or high-incidence edges prevent a complete orientation result."
    elif boundary_edges:
        normal_state = NormalConsistencyState.OPEN
        normal_detail = "Evaluated face winding is consistent, but boundary edges leave at least one shell open."
    elif mesh.polygons:
        normal_state = NormalConsistencyState.CONSISTENT
        normal_detail = "All evaluated two-face adjacencies use opposite shared-edge winding."
    else:
        normal_state = NormalConsistencyState.NOT_EVALUATED
        normal_detail = "No faces were available."

    edge_state = EdgeManifoldState.MANIFOLD if not (loose_edges or boundary_edges or high_incidence) else EdgeManifoldState.NON_MANIFOLD
    required_complete = bool(mesh.polygons)
    if not required_complete:
        watertight = WatertightState.INDETERMINATE
        watertight_detail = "Indeterminate because required checks were incomplete."
    elif loose_vertices or loose_edges or boundary_edges or high_incidence or vertex_anomalies:
        watertight = WatertightState.NOT_WATERTIGHT
        watertight_detail = "Not topologically watertight."
    else:
        watertight = WatertightState.TOPOLOGICALLY_WATERTIGHT
        watertight_detail = "Topologically watertight. This is not a printability guarantee."

    metrics = TopologyMetrics(
        non_manifold_edges=len(loose_edges) + len(high_incidence),
        boundary_edges=len(boundary_edges),
        manifold_edges=len(manifold_edges),
        high_incidence_non_manifold_edges=len(high_incidence),
        loose_vertices=len(loose_vertices),
        loose_edges=len(loose_edges),
        zero_length_edges=len(zero_length_edges),
        degenerate_faces=len(degenerate_faces),
        connected_components=components,
        disconnected_shells=max(len(shells) - 1, 0),
        face_shell_count=len(shells),
        edge_manifold_state=edge_state,
        vertex_manifold_state=vertex_state,
        vertex_manifold_anomalies=len(vertex_anomalies),
        watertight_state=watertight,
        watertight_detail=watertight_detail,
        normal_consistency=normal_state,
        normal_consistency_detail=normal_detail,
    )
    cap = settings.maximum_stored_issue_indices
    evidence = (
        _bounded_evidence(IssueCategory.BOUNDARY_EDGES, IssueDomain.EDGE, boundary_edges, cap),
        _bounded_evidence(IssueCategory.LOOSE_EDGES, IssueDomain.EDGE, loose_edges, cap),
        _bounded_evidence(IssueCategory.LOOSE_VERTICES, IssueDomain.VERTEX, loose_vertices, cap),
        _bounded_evidence(IssueCategory.HIGH_INCIDENCE_EDGES, IssueDomain.EDGE, high_incidence, cap),
        _bounded_evidence(IssueCategory.VERTEX_MANIFOLD_ANOMALIES, IssueDomain.VERTEX, vertex_anomalies, cap),
        _bounded_evidence(IssueCategory.ZERO_LENGTH_EDGES, IssueDomain.EDGE, zero_length_edges, cap),
        _bounded_evidence(IssueCategory.DEGENERATE_FACES, IssueDomain.FACE, degenerate_faces, cap),
        _bounded_evidence(IssueCategory.INCONSISTENT_FACES, IssueDomain.FACE, inconsistent_faces, cap),
        _bounded_evidence(IssueCategory.INCONSISTENT_SHARED_EDGES, IssueDomain.EDGE, inconsistent_edges, cap),
    )
    orientation_elapsed = edge_elapsed
    timings.append(CheckTiming("orientation_consistency", EvaluationStatus.COMPLETED, orientation_elapsed, normal_detail))
    checks.append(CheckResult("orientation_consistency", EvaluationStatus.COMPLETED, normal_detail, orientation_elapsed))
    return TopologyAnalysis(
        metrics=metrics,
        edge_faces=edge_faces,
        face_edges=face_edges,
        face_shells=shells,
        inconsistent_edge_indices=tuple(inconsistent_edges),
        inconsistent_face_indices=tuple(inconsistent_faces),
        vertex_anomaly_indices=vertex_anomalies,
        issue_evidence=evidence,
        checks=tuple(checks),
        timings=tuple(timings),
    )
