"""Bounded, read-only boundary-loop detection for explicit small-hole review."""

from __future__ import annotations

from collections import defaultdict, deque
from hashlib import sha256
import struct
from typing import Any

import bmesh
from mathutils import Vector

from ..models.repair_models import RepairCandidate, RepairCandidateType, RepairConfidence
from ..repair_settings import RepairSettings


def coordinate_mapping_sha256(points_mm: tuple[Vector, ...]) -> str:
    digest = sha256()
    values = sorted((round(point.x, 9), round(point.y, 9), round(point.z, 9)) for point in points_mm)
    for point in values:
        digest.update(struct.pack("<ddd", *point))
    return digest.hexdigest()


def _world_mm(obj: Any, coordinate: Vector, millimetres_per_unit: float) -> Vector:
    return (obj.matrix_world @ coordinate) * millimetres_per_unit


def detect_small_hole_candidates(
    obj: Any,
    millimetres_per_unit: float,
    settings: RepairSettings,
    *,
    include_rejected: bool = False,
) -> tuple[RepairCandidate, ...]:
    """Find simple boundary cycles; rejected components are optional audit evidence."""

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.verts.index_update()
        bm.edges.index_update()
        boundary = [edge for edge in bm.edges if len(edge.link_faces) == 1]
        by_vertex: dict[Any, list[Any]] = defaultdict(list)
        for edge in boundary:
            by_vertex[edge.verts[0]].append(edge)
            by_vertex[edge.verts[1]].append(edge)

        unseen = set(boundary)
        components: list[list[Any]] = []
        while unseen:
            first = min(unseen, key=lambda item: item.index)
            unseen.remove(first)
            component = [first]
            queue = deque(first.verts)
            visited_vertices = set(first.verts)
            while queue:
                vertex = queue.popleft()
                for edge in by_vertex[vertex]:
                    if edge in unseen:
                        unseen.remove(edge)
                        component.append(edge)
                        for neighbor in edge.verts:
                            if neighbor not in visited_vertices:
                                visited_vertices.add(neighbor)
                                queue.append(neighbor)
            components.append(sorted(component, key=lambda item: item.index))

        candidates: list[RepairCandidate] = []
        for component in sorted(components, key=lambda edges: edges[0].index):
            vertices = sorted({vertex for edge in component for vertex in edge.verts}, key=lambda item: item.index)
            degrees = {vertex: sum(edge in component for edge in by_vertex[vertex]) for vertex in vertices}
            rejection = ""
            if any(degree > 2 for degree in degrees.values()):
                rejection = "Boundary component is branched."
            elif any(degree != 2 for degree in degrees.values()) or len(vertices) != len(component):
                rejection = "Boundary component is an open chain."

            points = tuple(_world_mm(obj, vertex.co, millimetres_per_unit) for vertex in vertices)
            perimeter = sum(
                (_world_mm(obj, edge.verts[0].co, millimetres_per_unit) - _world_mm(obj, edge.verts[1].co, millimetres_per_unit)).length
                for edge in component
            )
            if points:
                minimum = Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points)))
                maximum = Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points)))
                diagonal = (maximum - minimum).length
            else:
                diagonal = 0.0
            if not rejection and len(component) > settings.small_hole_maximum_edge_count:
                rejection = "Boundary loop exceeds the configured edge-count limit."
            if not rejection and perimeter > settings.small_hole_maximum_perimeter_mm:
                rejection = "Boundary loop exceeds the configured perimeter limit."
            if not rejection and diagonal > settings.small_hole_maximum_diagonal_mm:
                rejection = "Boundary loop exceeds the configured bounding-box diagonal limit."
            eligible = not rejection
            if not eligible and not include_rejected:
                continue
            mapping = coordinate_mapping_sha256(points)
            cap = settings.maximum_stored_candidate_indices
            candidates.append(
                RepairCandidate(
                    candidate_id=f"small-hole-{len(candidates):04d}-{mapping[:12]}",
                    candidate_type=RepairCandidateType.SMALL_HOLE,
                    mapping_sha256=mapping,
                    eligible=eligible,
                    confidence=RepairConfidence.HIGH if eligible else RepairConfidence.NONE,
                    edge_indices=tuple(edge.index for edge in component[:cap]),
                    vertex_indices=tuple(vertex.index for vertex in vertices[:cap]),
                    total_edge_count=len(component),
                    total_vertex_count=len(vertices),
                    perimeter_mm=float(perimeter),
                    diagonal_mm=float(diagonal),
                    rejection_reason=rejection,
                    evidence_truncated=len(component) > cap or len(vertices) > cap,
                    criteria_matched=("closed", "simple", "non_branching", "bounded") if eligible else (),
                )
            )
        return tuple(candidates)
    finally:
        bm.free()
