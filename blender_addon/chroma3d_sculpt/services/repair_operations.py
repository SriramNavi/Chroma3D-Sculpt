"""Focused BMesh operations that mutate only an authorized repair workspace."""

from __future__ import annotations

from collections import defaultdict, deque
import math
from time import perf_counter
from typing import Any, Iterable

import bmesh
from mathutils import Vector

from ..models.analysis_result import AnalysisResult, ShellMetrics
from ..models.repair_models import (
    RepairCandidate,
    RepairCandidateType,
    RepairConfidence,
    RepairOperationOutcome,
    RepairOperationStatus,
)
from ..repair_settings import RepairSettings
from ..utilities.boundary_loops import coordinate_mapping_sha256, detect_small_hole_candidates


def mesh_counts(obj: Any) -> dict[str, int]:
    mesh = obj.data
    return {"vertices": len(mesh.vertices), "edges": len(mesh.edges), "faces": len(mesh.polygons)}


def _world_mm(obj: Any, coordinate: Vector, factor: float) -> Vector:
    return (obj.matrix_world @ coordinate) * factor


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, first: int, second: int) -> None:
        a = self.find(first)
        b = self.find(second)
        if a == b:
            return
        representative = min(a, b)
        self.parent[max(a, b)] = representative


def duplicate_clusters(obj: Any, factor: float, tolerance_mm: float) -> tuple[tuple[int, ...], ...]:
    """Return deterministic near-duplicate clusters using neighboring spatial cells."""

    coordinates = tuple(_world_mm(obj, vertex.co, factor) for vertex in obj.data.vertices)
    if len(coordinates) < 2:
        return ()
    inverse = 1.0 / tolerance_mm
    cells: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    union = _UnionFind(len(coordinates))
    offsets = tuple((x, y, z) for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1))
    for index, point in enumerate(coordinates):
        cell = (math.floor(point.x * inverse), math.floor(point.y * inverse), math.floor(point.z * inverse))
        for offset in offsets:
            neighbor = (cell[0] + offset[0], cell[1] + offset[1], cell[2] + offset[2])
            for other in cells.get(neighbor, ()):
                if (point - coordinates[other]).length <= tolerance_mm:
                    union.union(index, other)
        cells[cell].append(index)
    grouped: dict[int, list[int]] = defaultdict(list)
    for index in range(len(coordinates)):
        grouped[union.find(index)].append(index)
    return tuple(tuple(items) for _, items in sorted(grouped.items()) if len(items) > 1)


def merge_duplicate_vertices(obj: Any, factor: float, settings: RepairSettings) -> RepairOperationOutcome:
    started = perf_counter()
    before = mesh_counts(obj)
    clusters = duplicate_clusters(obj, factor, settings.merge_distance_mm)
    if not clusters:
        return RepairOperationOutcome(
            RepairOperationStatus.NO_CHANGE,
            {**before, "candidate_duplicate_count": 0, "cluster_count": 0, "vertices_merged": 0, "duration_ms": (perf_counter() - started) * 1000.0, "tolerance_mm": settings.merge_distance_mm},
        )
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        targetmap = {}
        for cluster in clusters:
            representative = bm.verts[min(cluster)]
            for index in cluster:
                if index != representative.index:
                    targetmap[bm.verts[index]] = representative
        bmesh.ops.weld_verts(bm, targetmap=targetmap)
        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()
    after = mesh_counts(obj)
    return RepairOperationOutcome(
        RepairOperationStatus.APPLIED,
        {
            "original_vertex_count": before["vertices"],
            "candidate_duplicate_count": sum(len(cluster) - 1 for cluster in clusters),
            "cluster_count": len(clusters),
            "vertices_merged": before["vertices"] - after["vertices"],
            "final_vertex_count": after["vertices"],
            "resulting_counts": after,
            "duration_ms": (perf_counter() - started) * 1000.0,
            "tolerance_mm": settings.merge_distance_mm,
        },
    )


def _short_edge_groups(obj: Any, factor: float, tolerance_mm: float) -> tuple[tuple[int, ...], int]:
    vertex_count = len(obj.data.vertices)
    union = _UnionFind(vertex_count)
    found = 0
    coordinates = tuple(_world_mm(obj, vertex.co, factor) for vertex in obj.data.vertices)
    for edge in obj.data.edges:
        first, second = (int(value) for value in edge.vertices)
        if (coordinates[first] - coordinates[second]).length <= tolerance_mm:
            union.union(first, second)
            found += 1
    groups: dict[int, list[int]] = defaultdict(list)
    for index in range(vertex_count):
        groups[union.find(index)].append(index)
    return tuple(tuple(group) for _, group in sorted(groups.items()) if len(group) > 1), found


def collapse_zero_length_edges(obj: Any, factor: float, settings: RepairSettings) -> RepairOperationOutcome:
    started = perf_counter()
    before = mesh_counts(obj)
    groups, found = _short_edge_groups(obj, factor, settings.zero_length_edge_tolerance_mm)
    if not groups:
        return RepairOperationOutcome(
            RepairOperationStatus.NO_CHANGE,
            {"zero_length_edges_found": found, "vertices_collapsed": 0, "resulting_counts": before, "duration_ms": (perf_counter() - started) * 1000.0, "tolerance_mm": settings.zero_length_edge_tolerance_mm},
        )
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        targetmap = {}
        for group in groups:
            representative = bm.verts[min(group)]
            for index in group:
                if index != representative.index:
                    targetmap[bm.verts[index]] = representative
        bmesh.ops.weld_verts(bm, targetmap=targetmap)
        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()
    after = mesh_counts(obj)
    return RepairOperationOutcome(
        RepairOperationStatus.APPLIED,
        {"zero_length_edges_found": found, "vertices_collapsed": before["vertices"] - after["vertices"], "resulting_counts": after, "duration_ms": (perf_counter() - started) * 1000.0, "tolerance_mm": settings.zero_length_edge_tolerance_mm},
    )


def _face_area_mm2(obj: Any, face: Any, factor: float) -> float:
    points = [_world_mm(obj, vertex.co, factor) for vertex in face.verts]
    if len(points) < 3:
        return 0.0
    origin = points[0]
    return sum((points[index] - origin).cross(points[index + 1] - origin).length * 0.5 for index in range(1, len(points) - 1))


def degenerate_face_indices(obj: Any, factor: float, tolerance_mm2: float) -> tuple[int, ...]:
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        bm.faces.index_update()
        return tuple(face.index for face in bm.faces if _face_area_mm2(obj, face, factor) < tolerance_mm2)
    finally:
        bm.free()


def remove_degenerate_faces(obj: Any, factor: float, settings: RepairSettings) -> RepairOperationOutcome:
    started = perf_counter()
    before = mesh_counts(obj)
    indices = degenerate_face_indices(obj, factor, settings.degenerate_face_area_tolerance_mm2)
    if not indices:
        return RepairOperationOutcome(RepairOperationStatus.NO_CHANGE, {"faces_evaluated": before["faces"], "degenerate_faces_found": 0, "faces_removed": 0, "threshold_mm2": settings.degenerate_face_area_tolerance_mm2, "duration_ms": (perf_counter() - started) * 1000.0, "resulting_counts": before})
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.faces[index] for index in indices], context="FACES_ONLY")
        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()
    after = mesh_counts(obj)
    return RepairOperationOutcome(RepairOperationStatus.APPLIED, {"faces_evaluated": before["faces"], "degenerate_faces_found": len(indices), "faces_removed": before["faces"] - after["faces"], "threshold_mm2": settings.degenerate_face_area_tolerance_mm2, "duration_ms": (perf_counter() - started) * 1000.0, "resulting_counts": after})


def remove_loose_geometry(obj: Any, _factor: float, _settings: RepairSettings) -> RepairOperationOutcome:
    started = perf_counter()
    before = mesh_counts(obj)
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        loose_edges = [edge for edge in bm.edges if not edge.link_faces]
        loose_edge_count = len(loose_edges)
        if loose_edges:
            bmesh.ops.delete(bm, geom=loose_edges, context="EDGES")
        loose_vertices = [vertex for vertex in bm.verts if not vertex.link_edges]
        loose_vertex_count = len(loose_vertices)
        if loose_vertices:
            bmesh.ops.delete(bm, geom=loose_vertices, context="VERTS")
        changed = bool(loose_edge_count or loose_vertex_count)
        if changed:
            bm.to_mesh(obj.data)
            obj.data.update()
    finally:
        bm.free()
    after = mesh_counts(obj)
    return RepairOperationOutcome(
        RepairOperationStatus.APPLIED if changed else RepairOperationStatus.NO_CHANGE,
        {"loose_edges_found": loose_edge_count, "loose_edges_removed": loose_edge_count, "loose_vertices_found": loose_vertex_count, "loose_vertices_removed": loose_vertex_count, "resulting_counts": after, "duration_ms": (perf_counter() - started) * 1000.0},
    )


def repair_normal_consistency(obj: Any, factor: float, _settings: RepairSettings) -> RepairOperationOutcome:
    started = perf_counter()
    before_coordinates = tuple(tuple(float(value) for value in vertex.co) for vertex in obj.data.vertices)
    bm = bmesh.new()
    changed = 0
    skipped: list[dict[str, Any]] = []
    try:
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        bm.faces.index_update()
        for component_index, component in enumerate(_face_components(bm)):
            component_edges = {edge for face in component for edge in face.edges}
            if any(len(edge.link_faces) > 2 for edge in component_edges):
                skipped.append({"component_id": component_index, "reason": "Component contains a non-manifold edge."})
                continue
            assignments: dict[Any, bool] = {component[0]: False}
            queue = deque([component[0]])
            conflict = False
            while queue and not conflict:
                face = queue.popleft()
                for edge in face.edges:
                    if len(edge.link_faces) != 2:
                        continue
                    neighbor = next(item for item in edge.link_faces if item is not face)
                    face_loop = next(loop for loop in face.loops if loop.edge is edge)
                    neighbor_loop = next(loop for loop in neighbor.loops if loop.edge is edge)
                    same_original_direction = face_loop.vert is neighbor_loop.vert
                    required = assignments[face] ^ same_original_direction
                    if neighbor in assignments:
                        if assignments[neighbor] != required:
                            conflict = True
                            break
                    else:
                        assignments[neighbor] = required
                        queue.append(neighbor)
            if conflict:
                skipped.append({"component_id": component_index, "reason": "Component winding is not consistently orientable."})
                continue
            original_signed_volume = _signed_component_volume_mm3(obj, component, factor)
            component_changed = 0
            for face, should_flip in assignments.items():
                if should_flip:
                    face.normal_flip()
                    component_changed += 1
            if component_edges and all(len(edge.link_faces) == 2 for edge in component_edges) and abs(original_signed_volume) > 1e-12:
                repaired_signed_volume = _signed_component_volume_mm3(obj, component, factor)
                if original_signed_volume * repaired_signed_volume < 0.0:
                    for face in component:
                        face.normal_flip()
                    component_changed = len(component) - component_changed
            changed += component_changed
        if changed:
            bm.to_mesh(obj.data)
            obj.data.update()
    finally:
        bm.free()
    coordinates_unchanged = before_coordinates == tuple(tuple(float(value) for value in vertex.co) for vertex in obj.data.vertices)
    return RepairOperationOutcome(
        RepairOperationStatus.APPLIED if changed else RepairOperationStatus.NO_CHANGE,
        {"faces_evaluated": len(obj.data.polygons), "face_winding_changes": changed, "components_skipped": len(skipped), "skip_details": skipped, "vertex_coordinates_unchanged": coordinates_unchanged, "resulting_counts": mesh_counts(obj), "duration_ms": (perf_counter() - started) * 1000.0},
        tuple(item["reason"] for item in skipped) + (() if coordinates_unchanged else ("Vertex coordinates changed unexpectedly during normal repair.",)),
    )


def _face_components(bm: Any) -> tuple[tuple[Any, ...], ...]:
    unseen = set(bm.faces)
    components: list[tuple[Any, ...]] = []
    while unseen:
        first = min(unseen, key=lambda face: face.index)
        unseen.remove(first)
        found = [first]
        queue = deque([first])
        while queue:
            face = queue.popleft()
            for edge in face.edges:
                for neighbor in edge.link_faces:
                    if neighbor in unseen:
                        unseen.remove(neighbor)
                        found.append(neighbor)
                        queue.append(neighbor)
        components.append(tuple(sorted(found, key=lambda face: face.index)))
    return tuple(components)


def _signed_component_volume_mm3(obj: Any, faces: Iterable[Any], factor: float) -> float:
    volume = 0.0
    for face in faces:
        points = [_world_mm(obj, vertex.co, factor) for vertex in face.verts]
        if len(points) < 3:
            continue
        origin = points[0]
        for index in range(1, len(points) - 1):
            volume += origin.dot(points[index].cross(points[index + 1])) / 6.0
    return volume


def orient_closed_shells_outward(obj: Any, factor: float, _settings: RepairSettings) -> RepairOperationOutcome:
    started = perf_counter()
    before_coordinates = tuple(tuple(float(value) for value in vertex.co) for vertex in obj.data.vertices)
    bm = bmesh.new()
    skipped: list[dict[str, Any]] = []
    reoriented = 0
    evaluated = 0
    try:
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        bm.faces.index_update()
        for shell_index, faces in enumerate(_face_components(bm)):
            edges = {edge for face in faces for edge in face.edges}
            if not faces or any(len(edge.link_faces) != 2 for edge in edges):
                skipped.append({"shell_id": shell_index, "reason": "Shell is open or non-manifold."})
                continue
            evaluated += 1
            signed_volume = _signed_component_volume_mm3(obj, faces, factor)
            if abs(signed_volume) <= 1e-12:
                skipped.append({"shell_id": shell_index, "reason": "Signed volume is indeterminate."})
                continue
            if signed_volume < 0.0:
                for face in faces:
                    face.normal_flip()
                reoriented += 1
        if reoriented:
            bm.to_mesh(obj.data)
            obj.data.update()
    finally:
        bm.free()
    coordinates_unchanged = before_coordinates == tuple(tuple(float(value) for value in vertex.co) for vertex in obj.data.vertices)
    warnings = tuple(item["reason"] for item in skipped)
    return RepairOperationOutcome(
        RepairOperationStatus.APPLIED if reoriented else RepairOperationStatus.NO_CHANGE,
        {"shells_evaluated": evaluated, "shells_reoriented": reoriented, "shells_skipped": len(skipped), "skip_details": skipped, "vertex_coordinates_unchanged": coordinates_unchanged, "resulting_counts": mesh_counts(obj), "duration_ms": (perf_counter() - started) * 1000.0},
        warnings,
    )


def _shell_mapping(obj: Any, faces: Iterable[Any], factor: float) -> str:
    vertices = {vertex for face in faces for vertex in face.verts}
    points = tuple(_world_mm(obj, vertex.co, factor) for vertex in vertices)
    return coordinate_mapping_sha256(points)


def tiny_shell_candidates(obj: Any, factor: float, analysis: AnalysisResult, settings: RepairSettings) -> tuple[RepairCandidate, ...]:
    metrics_by_id: dict[int, ShellMetrics] = {shell.shell_id: shell for shell in analysis.shells}
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        bm.faces.index_update()
        candidates: list[RepairCandidate] = []
        for shell_id, faces in enumerate(_face_components(bm)):
            metric = metrics_by_id.get(shell_id)
            if (
                metric is None
                or not metric.tiny_shell_candidate
                or "bounding_box_diagonal_mm" not in metric.tiny_criteria_matched
                or shell_id == analysis.main_shell_id
            ):
                continue
            vertices = sorted({vertex for face in faces for vertex in face.verts}, key=lambda item: item.index)
            edges = sorted({edge for face in faces for edge in face.edges}, key=lambda item: item.index)
            mapping = _shell_mapping(obj, faces, factor)
            cap = settings.maximum_stored_candidate_indices
            candidates.append(
                RepairCandidate(
                    candidate_id=f"tiny-shell-{shell_id:04d}-{mapping[:12]}",
                    candidate_type=RepairCandidateType.TINY_SHELL,
                    mapping_sha256=mapping,
                    shell_id=shell_id,
                    confidence=RepairConfidence(metric.classification_confidence.value),
                    face_indices=tuple(face.index for face in faces[:cap]),
                    edge_indices=tuple(edge.index for edge in edges[:cap]),
                    vertex_indices=tuple(vertex.index for vertex in vertices[:cap]),
                    total_face_count=len(faces),
                    total_edge_count=len(edges),
                    total_vertex_count=len(vertices),
                    surface_area_mm2=metric.surface_area_mm2,
                    volume_mm3=metric.absolute_volume_mm3,
                    diagonal_mm=math.sqrt(sum(value * value for value in metric.dimensions_mm)),
                    relative_size_percent=metric.relative_surface_area_percent,
                    criteria_matched=metric.tiny_criteria_matched,
                    evidence_truncated=max(len(faces), len(edges), len(vertices)) > cap,
                )
            )
        return tuple(candidates)
    finally:
        bm.free()


def remove_selected_tiny_shells(
    obj: Any,
    factor: float,
    settings: RepairSettings,
    selected: tuple[RepairCandidate, ...],
    current_analysis: AnalysisResult,
) -> RepairOperationOutcome:
    started = perf_counter()
    if not selected:
        return RepairOperationOutcome(RepairOperationStatus.NO_CHANGE, {"selected_shell_ids": [], "removed_faces": 0, "duration_ms": (perf_counter() - started) * 1000.0})
    current_candidates = tiny_shell_candidates(obj, factor, current_analysis, settings)
    resolved: list[RepairCandidate] = []
    invalid: list[str] = []
    for selected_candidate in selected:
        matches = [item for item in current_candidates if item.mapping_sha256 == selected_candidate.mapping_sha256]
        if len(matches) != 1:
            invalid.append(selected_candidate.candidate_id)
        else:
            resolved.append(matches[0])
    if invalid:
        raise ValueError("Selected tiny-shell candidate mapping is stale or ambiguous: " + ", ".join(invalid))
    if any(item.shell_id == current_analysis.main_shell_id for item in resolved):
        raise ValueError("The main shell cannot be removed.")
    before = mesh_counts(obj)
    selected_shell_ids = {item.shell_id for item in resolved}
    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        bm.faces.index_update()
        vertices_to_delete = set()
        removed_ids: list[int] = []
        for shell_id, faces in enumerate(_face_components(bm)):
            if shell_id in selected_shell_ids:
                if shell_id == current_analysis.main_shell_id:
                    raise ValueError("The main shell cannot be removed.")
                vertices_to_delete.update(vertex for face in faces for vertex in face.verts)
                removed_ids.append(shell_id)
        if vertices_to_delete:
            bmesh.ops.delete(bm, geom=list(vertices_to_delete), context="VERTS")
            bm.to_mesh(obj.data)
            obj.data.update()
    finally:
        bm.free()
    after = mesh_counts(obj)
    return RepairOperationOutcome(
        RepairOperationStatus.APPLIED if before != after else RepairOperationStatus.NO_CHANGE,
        {"selected_shell_ids": removed_ids, "removed_faces": before["faces"] - after["faces"], "removed_edges": before["edges"] - after["edges"], "removed_vertices": before["vertices"] - after["vertices"], "resulting_counts": after, "duration_ms": (perf_counter() - started) * 1000.0},
    )


def fill_selected_small_holes(
    obj: Any,
    factor: float,
    settings: RepairSettings,
    selected: tuple[RepairCandidate, ...],
) -> RepairOperationOutcome:
    started = perf_counter()
    if not selected:
        return RepairOperationOutcome(RepairOperationStatus.NO_CHANGE, {"selected_candidate_ids": [], "new_face_count": 0, "duration_ms": (perf_counter() - started) * 1000.0})
    current_candidates = detect_small_hole_candidates(obj, factor, settings)
    resolved: list[RepairCandidate] = []
    invalid: list[str] = []
    for selected_candidate in selected:
        matches = [item for item in current_candidates if item.mapping_sha256 == selected_candidate.mapping_sha256]
        if len(matches) != 1:
            invalid.append(selected_candidate.candidate_id)
        else:
            resolved.append(matches[0])
    if invalid:
        raise ValueError("Selected small-hole candidate mapping is stale, ambiguous, or no longer eligible: " + ", ".join(invalid))
    before = mesh_counts(obj)
    bm = bmesh.new()
    new_faces = 0
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.verts.index_update()
        bm.edges.index_update()
        for candidate in resolved:
            edges = [bm.edges[index] for index in candidate.edge_indices]
            result = bmesh.ops.holes_fill(bm, edges=edges, sides=0)
            new_faces += len(result.get("faces", ()))
        if new_faces:
            bm.to_mesh(obj.data)
            obj.data.update()
    finally:
        bm.free()
    after = mesh_counts(obj)
    return RepairOperationOutcome(
        RepairOperationStatus.APPLIED if new_faces else RepairOperationStatus.NO_CHANGE,
        {"selected_candidate_ids": [item.candidate_id for item in selected], "new_face_count": new_faces, "resulting_counts": after, "duration_ms": (perf_counter() - started) * 1000.0},
    )
