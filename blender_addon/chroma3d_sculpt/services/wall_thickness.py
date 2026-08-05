"""Bounded BVH ray-based local wall-thickness estimation."""

from __future__ import annotations

import bisect
import math
from time import perf_counter

from mathutils import Vector
from mathutils.bvhtree import BVHTree

from ..models.printability_models import (
    EvidenceState,
    PrintabilityConfidence,
    PrintabilityStatus,
    PrinterProfile,
    WallThicknessResult,
)
from ..printability_settings import PrintabilitySettings
from .geometry_facts import GeometryContext


def _percentiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    result: dict[str, float] = {}
    for label, fraction in (("p05", 0.05), ("p25", 0.25), ("p50", 0.5), ("p75", 0.75), ("p95", 0.95)):
        position = (len(ordered) - 1) * fraction
        lower = int(math.floor(position))
        upper = int(math.ceil(position))
        value = ordered[lower] if lower == upper else ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
        result[label] = float(value)
    return result


def _sample_triangles(context: GeometryContext, limit: int) -> tuple[int, ...]:
    areas: list[float] = []
    cumulative: list[float] = []
    total = 0.0
    for triangle in context.triangles_mm:
        a, b, c = triangle.coordinates
        area = float((b - a).cross(c - a).length) * 0.5
        areas.append(area)
        total += area
        cumulative.append(total)
    if total <= 0.0:
        return ()
    count = min(max(limit, 1), len(context.triangles_mm))
    selected: list[int] = []
    seen: set[int] = set()
    for index in range(count):
        target = total * ((index + 0.5) / count)
        triangle_index = min(bisect.bisect_left(cumulative, target), len(cumulative) - 1)
        if triangle_index not in seen and areas[triangle_index] > 0.0:
            selected.append(triangle_index)
            seen.add(triangle_index)
    return tuple(selected)


def _ray_hit(
    bvh: BVHTree,
    context: GeometryContext,
    point: Vector,
    normal: Vector,
    direction_sign: float,
    settings: PrintabilitySettings,
) -> tuple[float, Vector, int] | None:
    direction = normal * direction_sign
    origin = point + direction * settings.ray_origin_offset_mm
    traveled = settings.ray_origin_offset_mm
    remaining = settings.maximum_wall_search_distance_mm
    source_face = None
    for _attempt in range(4):
        location, hit_normal, triangle_index, distance = bvh.ray_cast(origin, direction, remaining)
        if location is None or hit_normal is None or triangle_index is None or distance is None:
            return None
        hit_face = context.triangles_mm[int(triangle_index)].face_index
        if source_face is None:
            source_face = -1
        if float(hit_normal.normalized().dot(normal)) <= settings.opposing_normal_dot_max:
            return traveled + float(distance), location.copy(), hit_face
        advance = float(distance) + settings.ray_origin_offset_mm
        origin = location + direction * settings.ray_origin_offset_mm
        traveled += advance
        remaining -= advance
        if remaining <= 0.0:
            break
    return None


def _region_areas(context: GeometryContext, face_indices: set[int]) -> tuple[int, float]:
    visited: set[int] = set()
    region_areas: list[float] = []
    for seed in sorted(face_indices):
        if seed in visited:
            continue
        visited.add(seed)
        stack = [seed]
        area = 0.0
        while stack:
            face = stack.pop()
            area += context.face_areas_mm2[face]
            for edge_index in context.topology.face_edges[face]:
                for neighbor in context.topology.edge_faces[edge_index]:
                    if neighbor in face_indices and neighbor not in visited:
                        visited.add(neighbor)
                        stack.append(neighbor)
        region_areas.append(area)
    return len(region_areas), max(region_areas, default=0.0)


def analyze_wall_thickness(
    context: GeometryContext,
    profile: PrinterProfile,
    settings: PrintabilitySettings,
) -> WallThicknessResult:
    started = perf_counter()
    limit = int(settings.triangle_limit or 0)
    if context.facts.triangle_count > limit:
        return WallThicknessResult(
            status=PrintabilityStatus.SKIPPED_LIMIT,
            confidence=PrintabilityConfidence.UNKNOWN,
            evidence_state=EvidenceState.UNAVAILABLE,
            duration_seconds=perf_counter() - started,
            limitations=(f"Triangle count {context.facts.triangle_count} exceeds the configured expensive-check limit {limit}.",),
        )
    if not context.triangles_mm:
        return WallThicknessResult(
            status=PrintabilityStatus.NOT_APPLICABLE,
            confidence=PrintabilityConfidence.UNKNOWN,
            evidence_state=EvidenceState.UNAVAILABLE,
            duration_seconds=perf_counter() - started,
            limitations=("No surface triangles were available for wall sampling.",),
        )
    try:
        bvh = BVHTree.FromPolygons(
            [tuple(float(value) for value in point) for point in context.vertices_mm],
            [triangle.vertex_indices for triangle in context.triangles_mm],
            all_triangles=True,
        )
        selected = _sample_triangles(context, int(settings.wall_sample_limit or 1))
        thicknesses: list[float] = []
        source_faces: list[int] = []
        sample_points: list[tuple[float, float, float]] = []
        hit_points: list[tuple[float, float, float]] = []
        sample_areas: list[float] = []
        for triangle_index in selected:
            triangle = context.triangles_mm[triangle_index]
            a, b, c = triangle.coordinates
            normal = (b - a).cross(c - a)
            if normal.length_squared <= 1e-24:
                continue
            normal.normalize()
            point = (a + b + c) / 3.0
            hits: list[tuple[float, Vector, int]] = []
            inward = _ray_hit(bvh, context, point, normal, -1.0, settings)
            if inward is not None and inward[2] != triangle.face_index:
                hits.append(inward)
            if not context.facts.watertight or not hits:
                outward = _ray_hit(bvh, context, point, normal, 1.0, settings)
                if outward is not None and outward[2] != triangle.face_index:
                    hits.append(outward)
            if not hits:
                continue
            thickness, hit, _hit_face = min(hits, key=lambda item: item[0])
            if thickness <= settings.ray_origin_offset_mm * 2.0:
                continue
            thicknesses.append(float(thickness))
            source_faces.append(triangle.face_index)
            sample_points.append(tuple(float(value) for value in point))
            hit_points.append(tuple(float(value) for value in hit))
            sample_areas.append(float((b - a).cross(c - a).length) * 0.5)
        attempted = len(selected)
        completed = len(thicknesses)
        skipped = attempted - completed
        if not thicknesses:
            status = PrintabilityStatus.INDETERMINATE if not context.facts.watertight else PrintabilityStatus.NOT_EVALUATED
            return WallThicknessResult(
                status=status,
                confidence=PrintabilityConfidence.LOW if attempted else PrintabilityConfidence.UNKNOWN,
                evidence_state=EvidenceState.UNAVAILABLE,
                samples_attempted=attempted,
                samples_completed=0,
                samples_skipped=skipped,
                duration_seconds=perf_counter() - started,
                limitations=("No plausible opposing surface hit was available; a single/open surface is not zero wall thickness.",),
            )
        warning = profile.wall_thickness_warning_mm.value
        critical = profile.wall_thickness_critical_mm.value
        warning_indices = [index for index, value in enumerate(thicknesses) if value <= warning]
        critical_indices = [index for index, value in enumerate(thicknesses) if value <= critical]
        warning_area = sum(sample_areas[index] for index in warning_indices)
        critical_area = sum(sample_areas[index] for index in critical_indices)
        covered_area = sum(sample_areas)
        risk_faces = {source_faces[index] for index in warning_indices}
        region_count, largest_region = _region_areas(context, risk_faces)
        if not context.facts.watertight:
            status = PrintabilityStatus.INDETERMINATE
        elif critical_indices:
            status = PrintabilityStatus.CRITICAL
        elif warning_indices:
            status = PrintabilityStatus.WARNING
        else:
            status = PrintabilityStatus.PASS
        coverage = completed / max(attempted, 1)
        confidence = PrintabilityConfidence.LOW if not context.facts.watertight or coverage < 0.5 else PrintabilityConfidence.MEDIUM
        cap = int(settings.evidence_cap or 1)
        ordered_faces = tuple(sorted(risk_faces))
        truncated = len(ordered_faces) > cap or completed > cap
        limitations = [
            "Wall thickness is a bounded normal-ray estimate, not an exact minimum or manufacturing guarantee.",
            "Curvature, acute corners, overlapping surfaces, and mesh winding can bias opposing hits.",
        ]
        if not context.facts.watertight:
            limitations.append("Open or non-manifold topology makes inside/outside and opposing-hit interpretation indeterminate.")
        return WallThicknessResult(
            status=status,
            confidence=confidence,
            evidence_state=EvidenceState.TRUNCATED if truncated else EvidenceState.BOUNDED,
            samples_attempted=attempted,
            samples_completed=completed,
            samples_skipped=skipped,
            minimum_sampled_thickness_mm=min(thicknesses),
            percentile_thickness_mm=_percentiles(thicknesses),
            area_below_warning_mm2=warning_area,
            area_below_critical_mm2=critical_area,
            percent_below_warning=warning_area / covered_area * 100.0 if covered_area else 0.0,
            percent_below_critical=critical_area / covered_area * 100.0 if covered_area else 0.0,
            thin_region_count=region_count,
            largest_thin_region_area_mm2=largest_region,
            evidence_faces=ordered_faces[:cap],
            sample_positions_mm=tuple(sample_points[:cap]),
            sample_hits_mm=tuple(hit_points[:cap]),
            sample_thicknesses_mm=tuple(thicknesses[:cap]),
            duration_seconds=perf_counter() - started,
            limitations=tuple(limitations),
        )
    except MemoryError:
        raise
    except Exception as exc:
        return WallThicknessResult(
            status=PrintabilityStatus.FAILED,
            confidence=PrintabilityConfidence.UNKNOWN,
            evidence_state=EvidenceState.UNAVAILABLE,
            duration_seconds=perf_counter() - started,
            limitations=("Wall-thickness analysis failed without changing the source mesh.",),
            error=f"{type(exc).__name__}: {exc}",
        )
