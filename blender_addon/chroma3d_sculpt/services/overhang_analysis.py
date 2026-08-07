"""World-space, area-weighted overhang analysis using the approved convention."""

from __future__ import annotations

import math
from time import perf_counter

from mathutils import Vector

from ..models.printability_models import (
    EvidenceState,
    OverhangRegion,
    OverhangResult,
    PrintabilityConfidence,
    PrintabilityStatus,
    PrinterProfile,
)
from ..printability_settings import PrintabilitySettings
from .geometry_facts import GeometryContext
from .printability_statistics import percentiles


def overhang_angle_deg(normal: Vector, build_direction: Vector) -> float | None:
    dot = float(normal.dot(build_direction))
    if dot >= 0.0:
        return None
    return math.degrees(math.acos(max(-1.0, min(1.0, -dot))))


def _regions(context: GeometryContext, bands: dict[int, str], angles: dict[int, float], settings: PrintabilitySettings) -> tuple[OverhangRegion, ...]:
    visited: set[int] = set()
    regions: list[OverhangRegion] = []
    for seed in sorted(bands):
        if seed in visited:
            continue
        band = bands[seed]
        visited.add(seed)
        stack = [seed]
        members: list[int] = []
        while stack:
            face = stack.pop()
            members.append(face)
            for edge_index in context.topology.face_edges[face]:
                for neighbor in context.topology.edge_faces[edge_index]:
                    if neighbor in bands and bands[neighbor] == band and neighbor not in visited:
                        visited.add(neighbor)
                        stack.append(neighbor)
        area = sum(context.face_areas_mm2[face] for face in members)
        if area < settings.overhang_region_area_threshold_mm2:
            continue
        centroid = sum(
            (context.face_centroids_mm[face] * context.face_areas_mm2[face] for face in members),
            Vector((0.0, 0.0, 0.0)),
        ) / max(area, 1e-12)
        regions.append(
            OverhangRegion(
                region_id=f"overhang-region-{len(regions):04d}",
                band=band,
                face_count=len(members),
                area_mm2=area,
                representative_face=min(members),
                centroid_mm=tuple(float(value) for value in centroid),
                minimum_angle_deg=min(angles[face] for face in members),
            )
        )
    return tuple(regions)


def analyze_overhangs(context: GeometryContext, profile: PrinterProfile, settings: PrintabilitySettings) -> OverhangResult:
    started = perf_counter()
    if context.facts.triangle_count > int(settings.triangle_limit or 0):
        return OverhangResult(
            status=PrintabilityStatus.SKIPPED_LIMIT,
            confidence=PrintabilityConfidence.UNKNOWN,
            evidence_state=EvidenceState.UNAVAILABLE,
            faces_attempted=context.facts.face_count,
            faces_skipped=context.facts.face_count,
            build_direction=settings.normalized_build_direction(),
            warning_threshold_deg=profile.overhang_warning_angle_deg.value,
            critical_threshold_deg=profile.overhang_critical_angle_deg.value,
            duration_seconds=perf_counter() - started,
            limitations=("Overhang analysis was skipped at the configured triangle limit.",),
        )
    direction = Vector(settings.normalized_build_direction())
    warning_threshold = profile.overhang_warning_angle_deg.value
    critical_threshold = profile.overhang_critical_angle_deg.value
    bands: dict[int, str] = {}
    angles: dict[int, float] = {}
    downward_angles: list[float] = []
    eligible_area = 0.0
    warning_area = 0.0
    critical_area = 0.0
    suppressed_count = 0
    suppressed_area = 0.0
    for face_index, normal in enumerate(context.face_normals):
        face_offsets = [float(context.vertices_mm[index].dot(direction)) for index in context.face_vertices[face_index]]
        if face_offsets and all(abs(value) <= float(settings.contact_tolerance_mm or 0.0) for value in face_offsets):
            continue
        angle = overhang_angle_deg(normal, direction)
        if angle is None:
            continue
        area = context.face_areas_mm2[face_index]
        eligible_area += area
        downward_angles.append(angle)
        if angle <= critical_threshold:
            bands[face_index] = "CRITICAL"
            angles[face_index] = angle
            critical_area += area
            warning_area += area
        elif angle <= warning_threshold:
            bands[face_index] = "WARNING"
            angles[face_index] = angle
            warning_area += area
        if face_index in bands and area < settings.small_face_area_mm2:
            suppressed_count += 1
            suppressed_area += area
    regions = _regions(context, bands, angles, settings)
    status = PrintabilityStatus.CRITICAL if any(band == "CRITICAL" for band in bands.values()) else PrintabilityStatus.WARNING if bands else PrintabilityStatus.PASS
    cap = int(settings.evidence_cap or 1)
    evidence = tuple(sorted(bands))
    confidence = PrintabilityConfidence.MEDIUM if context.facts.watertight else PrintabilityConfidence.LOW
    return OverhangResult(
        status=status,
        confidence=confidence,
        evidence_state=EvidenceState.TRUNCATED if len(evidence) > cap else EvidenceState.BOUNDED,
        faces_attempted=context.facts.face_count,
        faces_evaluated=context.facts.face_count,
        affected_face_count=len(bands),
        eligible_surface_area_mm2=eligible_area,
        warning_area_mm2=warning_area,
        critical_area_mm2=critical_area,
        warning_area_percent=warning_area / eligible_area * 100.0 if eligible_area else 0.0,
        critical_area_percent=critical_area / eligible_area * 100.0 if eligible_area else 0.0,
        suppressed_face_count=suppressed_count,
        suppressed_area_mm2=suppressed_area,
        angle_percentiles_deg=percentiles(downward_angles),
        regions=regions[:cap],
        evidence_faces=evidence[:cap],
        build_direction=tuple(float(value) for value in direction),
        warning_threshold_deg=warning_threshold,
        critical_threshold_deg=critical_threshold,
        duration_seconds=perf_counter() - started,
        limitations=(
            "Flagged downward surfaces are advisory support-sensitive geometry; support need is not determined.",
            "Curved surfaces are evaluated face-wise and small-face suppression affects retained regions, not measured risk area.",
        ),
    )
