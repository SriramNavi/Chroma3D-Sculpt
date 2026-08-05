"""Read-only build-plane contact classes and bounded stability heuristic."""

from __future__ import annotations

import math
from time import perf_counter

from mathutils import Vector

from ..models.printability_models import (
    BuildPlateContactResult,
    ContactClassification,
    EvidenceState,
    PrintabilityConfidence,
    PrintabilityStatus,
    StabilityHeuristic,
)
from ..printability_settings import PrintabilitySettings
from .geometry_facts import GeometryContext


def _plane_basis(normal: Vector) -> tuple[Vector, Vector]:
    reference = Vector((1.0, 0.0, 0.0)) if abs(normal.x) < 0.9 else Vector((0.0, 1.0, 0.0))
    first = normal.cross(reference).normalized()
    second = normal.cross(first).normalized()
    return first, second


def _convex_hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    unique = sorted(set(points))
    if len(unique) <= 1:
        return unique

    def cross(origin: tuple[float, float], first: tuple[float, float], second: tuple[float, float]) -> float:
        return (first[0] - origin[0]) * (second[1] - origin[1]) - (first[1] - origin[1]) * (second[0] - origin[0])

    lower: list[tuple[float, float]] = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0.0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float]] = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0.0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _polygon_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    return abs(sum(points[index][0] * points[(index + 1) % len(points)][1] - points[(index + 1) % len(points)][0] * points[index][1] for index in range(len(points)))) * 0.5


def _point_state(point: tuple[float, float], hull: list[tuple[float, float]], tolerance: float) -> tuple[StabilityHeuristic, float | None]:
    if len(hull) < 3:
        return StabilityHeuristic.UNAVAILABLE, None
    signs: list[float] = []
    distances: list[float] = []
    for index, first in enumerate(hull):
        second = hull[(index + 1) % len(hull)]
        dx, dy = second[0] - first[0], second[1] - first[1]
        length = math.hypot(dx, dy)
        signed = ((point[0] - first[0]) * dy - (point[1] - first[1]) * dx) / max(length, 1e-12)
        signs.append(signed)
        distances.append(abs(signed))
    all_positive = all(value >= -tolerance for value in signs)
    all_negative = all(value <= tolerance for value in signs)
    if not (all_positive or all_negative):
        return StabilityHeuristic.OUTSIDE, -min(distances)
    margin = min(distances)
    return (StabilityHeuristic.NEAR_BOUNDARY if margin <= tolerance else StabilityHeuristic.INSIDE), margin


def _contact_regions(context: GeometryContext, faces: set[int]) -> int:
    visited: set[int] = set()
    count = 0
    for seed in sorted(faces):
        if seed in visited:
            continue
        count += 1
        visited.add(seed)
        stack = [seed]
        while stack:
            face = stack.pop()
            for edge_index in context.topology.face_edges[face]:
                for neighbor in context.topology.edge_faces[edge_index]:
                    if neighbor in faces and neighbor not in visited:
                        visited.add(neighbor)
                        stack.append(neighbor)
    return count


def _volume_centroid(context: GeometryContext) -> Vector | None:
    if not context.facts.watertight or context.facts.reliable_volume_mm3 is None:
        return None
    weighted = Vector((0.0, 0.0, 0.0))
    volume = 0.0
    for triangle in context.triangles_mm:
        a, b, c = triangle.coordinates
        signed = float(a.dot(b.cross(c))) / 6.0
        volume += signed
        weighted += (a + b + c) * (signed / 4.0)
    if abs(volume) <= 1e-12:
        return None
    return weighted / volume


def analyze_build_plate_contact(context: GeometryContext, settings: PrintabilitySettings) -> BuildPlateContactResult:
    started = perf_counter()
    direction = Vector(settings.normalized_build_direction())
    first, second = _plane_basis(direction)
    tolerance = float(settings.contact_tolerance_mm or 0.0)
    offsets = [float(point.dot(direction)) for point in context.vertices_mm]
    contact_vertices = {index for index, offset in enumerate(offsets) if abs(offset) <= tolerance}
    contact_edges = {
        index for index, (a, b) in enumerate(context.edge_vertices)
        if a in contact_vertices and b in contact_vertices
    }
    full_faces: set[int] = set()
    partial_faces: set[int] = set()
    for face_index, vertices in enumerate(context.face_vertices):
        values = [offsets[index] for index in vertices]
        if values and all(abs(value) <= tolerance for value in values):
            full_faces.add(face_index)
        elif values and min(values) <= tolerance and max(values) >= -tolerance:
            partial_faces.add(face_index)
    region_faces = full_faces | partial_faces
    region_count = _contact_regions(context, region_faces)
    contact_area = sum(context.face_areas_mm2[index] for index in full_faces)
    projected_points = [
        (float(context.vertices_mm[index].dot(first)), float(context.vertices_mm[index].dot(second)))
        for index in sorted(contact_vertices)
    ]
    hull = _convex_hull(projected_points)
    footprint = _polygon_area(hull) if len(hull) >= 3 else None
    below_build_plane = bool(offsets) and max(offsets) < -tolerance
    if below_build_plane:
        classification = ContactClassification.INDETERMINATE
    elif full_faces and region_count > 1:
        classification = ContactClassification.MULTI_REGION_CONTACT
    elif full_faces:
        classification = ContactClassification.BROAD_CONTACT
    elif partial_faces:
        classification = ContactClassification.PARTIAL_FACE_CONTACT
    elif contact_edges:
        classification = ContactClassification.EDGE_CONTACT
    elif contact_vertices:
        classification = ContactClassification.POINT_CONTACT
    else:
        classification = ContactClassification.NO_CONTACT
    status = PrintabilityStatus.INDETERMINATE if classification == ContactClassification.INDETERMINATE else (
        PrintabilityStatus.PASS if classification in {ContactClassification.BROAD_CONTACT, ContactClassification.MULTI_REGION_CONTACT}
        else PrintabilityStatus.WARNING
    )
    centroid = _volume_centroid(context)
    projection = None if centroid is None else (float(centroid.dot(first)), float(centroid.dot(second)))
    stability, margin = (StabilityHeuristic.UNAVAILABLE, None) if projection is None else _point_state(projection, hull, settings.contact_region_tolerance_mm)
    confidence = PrintabilityConfidence.MEDIUM if full_faces else PrintabilityConfidence.LOW
    if centroid is None:
        confidence = PrintabilityConfidence.LOW
    cap = int(settings.evidence_cap or 1)
    all_faces = tuple(sorted(region_faces))
    truncated = len(contact_vertices) > cap or len(contact_edges) > cap or len(all_faces) > cap
    return BuildPlateContactResult(
        status=status,
        confidence=confidence,
        evidence_state=EvidenceState.TRUNCATED if truncated else EvidenceState.BOUNDED,
        classification=classification,
        minimum_build_plane_offset_mm=min(offsets),
        contact_vertex_count=len(contact_vertices),
        contact_edge_count=len(contact_edges),
        contact_face_count=len(region_faces),
        contact_area_mm2=contact_area,
        contact_region_count=region_count,
        projected_footprint_area_mm2=footprint,
        contact_area_percent=contact_area / context.facts.surface_area_mm2 * 100.0 if context.facts.surface_area_mm2 else 0.0,
        center_of_mass_projection_mm=projection,
        stability_heuristic=stability,
        stability_margin_mm=margin,
        evidence_vertices=tuple(sorted(contact_vertices))[:cap],
        evidence_edges=tuple(sorted(contact_edges))[:cap],
        evidence_faces=all_faces[:cap],
        duration_seconds=perf_counter() - started,
        limitations=(
            "Contact and center-of-mass projection are geometric heuristics, not a physical stability or adhesion simulation.",
            "Friction, acceleration, plate texture, supports, resin peel forces, and material behavior are not modeled.",
        ) + (("The entire surface is below the selected build plane, so contact classification is indeterminate until placement is corrected.",) if below_build_plane else ()) + (("Center-of-mass projection is unavailable for open or unreliable-volume geometry.",) if centroid is None else ()),
    )
