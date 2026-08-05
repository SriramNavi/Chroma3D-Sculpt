"""Bounded geometric bridge-risk candidates; never a bridge-success prediction."""

from __future__ import annotations

from time import perf_counter

from mathutils import Vector

from ..models.advanced_preparation_models import BridgeRiskRegion, BridgeRiskResult, ComposedProcessContext
from ..models.printability_models import PrintabilityConfidence, PrintabilityMode, PrintabilityStatus
from ..performance_registry import limit_for
from .geometry_facts import GeometryContext
from .overhang_analysis import overhang_angle_deg


def _basis(direction: Vector) -> tuple[Vector, Vector]:
    seed = Vector((1.0, 0.0, 0.0)) if abs(direction.x) < 0.8 else Vector((0.0, 1.0, 0.0))
    first = direction.cross(seed).normalized()
    return first, direction.cross(first).normalized()


def _face_regions(context: GeometryContext, eligible: set[int]) -> list[list[int]]:
    regions: list[list[int]] = []
    visited: set[int] = set()
    for seed in sorted(eligible):
        if seed in visited:
            continue
        visited.add(seed)
        stack = [seed]
        members: list[int] = []
        while stack:
            face = stack.pop()
            members.append(face)
            for edge_index in context.topology.face_edges[face]:
                for neighbor in context.topology.edge_faces[edge_index]:
                    if neighbor in eligible and neighbor not in visited:
                        visited.add(neighbor)
                        stack.append(neighbor)
        regions.append(sorted(members))
    return regions


def analyze_bridge_risk(
    context: GeometryContext,
    process: ComposedProcessContext,
    mode: PrintabilityMode,
    build_direction: tuple[float, float, float] = (0.0, 0.0, 1.0),
) -> BridgeRiskResult:
    started = perf_counter()
    limit = limit_for(mode, context.facts.triangle_count, "bridge_risk")
    if context.facts.triangle_count > limit.hard_skip_limit:
        return BridgeRiskResult(
            status=PrintabilityStatus.SKIPPED_LIMIT, confidence=PrintabilityConfidence.UNKNOWN,
            candidate_region_count=0, regions=(), evidence_faces=(), duration_seconds=perf_counter() - started,
            limitations=(f"Bridge-risk analysis skipped at the centralized {limit.hard_skip_limit:,}-triangle hard limit.",),
        )
    try:
        direction = Vector(build_direction).normalized()
        first, second = _basis(direction)
        build_minimum = min(float(point.dot(direction)) for point in context.vertices_mm)
        contact_tolerance = process.effective_thresholds["build_plate_contact_tolerance_mm"]
        warning_span = process.effective_thresholds["bridge_warning_span_mm"]
        critical_span = process.effective_thresholds["bridge_critical_span_mm"]
        downward: set[int] = set()
        angles: dict[int, float] = {}
        for face_index, normal in enumerate(context.face_normals):
            angle = overhang_angle_deg(normal, direction)
            if angle is None or angle > process.effective_thresholds["overhang_warning_angle_deg"]:
                continue
            height = min(float(context.vertices_mm[index].dot(direction)) for index in context.face_vertices[face_index])
            if height <= build_minimum + contact_tolerance:
                continue
            downward.add(face_index)
            angles[face_index] = angle
        retained: list[BridgeRiskRegion] = []
        for members in _face_regions(context, downward):
            vertex_indices = sorted({index for face in members for index in context.face_vertices[face]})
            points = [context.vertices_mm[index] for index in vertex_indices]
            u_values = [float(point.dot(first)) for point in points]
            v_values = [float(point.dot(second)) for point in points]
            u_span = max(u_values) - min(u_values)
            v_span = max(v_values) - min(v_values)
            span_axis, width_axis = (first, second) if u_span >= v_span else (second, first)
            span_values = [float(point.dot(span_axis)) for point in points]
            width_values = [float(point.dot(width_axis)) for point in points]
            span = max(span_values) - min(span_values)
            width = max(width_values) - min(width_values)
            region_height = min(float(point.dot(direction)) for point in points)
            side_tolerance = max(contact_tolerance * 4.0, min(max(span * 0.15, 0.25), 3.0))
            width_padding = max(width * 0.25, contact_tolerance * 4.0)
            low_side = False
            high_side = False
            region_vertices = set(vertex_indices)
            for index, point in enumerate(context.vertices_mm):
                if index in region_vertices or float(point.dot(direction)) >= region_height - contact_tolerance:
                    continue
                across = float(point.dot(width_axis))
                if across < min(width_values) - width_padding or across > max(width_values) + width_padding:
                    continue
                along = float(point.dot(span_axis))
                low_side = low_side or abs(along - min(span_values)) <= side_tolerance
                high_side = high_side or abs(along - max(span_values)) <= side_tolerance
                if low_side and high_side:
                    break
            supporting_sides = int(low_side) + int(high_side)
            if supporting_sides < 2 or span < warning_span:
                continue
            severity = PrintabilityStatus.CRITICAL if span >= critical_span else PrintabilityStatus.WARNING
            area = sum(context.face_areas_mm2[face] for face in members)
            evidence = tuple(members[:limit.maximum_region_evidence])
            retained.append(
                BridgeRiskRegion(
                    region_id=f"bridge-region-{len(retained):04d}", severity=severity,
                    estimated_span_mm=span, projected_unsupported_distance_mm=span,
                    supporting_side_count=supporting_sides, width_mm=width, surface_area_mm2=area,
                    angle_deg=min(angles[face] for face in members), build_direction=tuple(float(value) for value in direction),
                    profile_material_modifier=process.material_profile.bridge_risk_modifier,
                    confidence=PrintabilityConfidence.LOW if context.facts.boundary_edges or context.facts.non_manifold_edges else PrintabilityConfidence.MEDIUM,
                    evidence_faces=evidence,
                    limitations=(
                        "Supporting sides and projected gap are conservative geometric proxies; cooling, speed, extrusion, sag, and slicer bridge settings are not simulated.",
                        "This candidate does not guarantee bridge success or failure.",
                    ),
                )
            )
            if len(retained) >= limit.maximum_candidate_count:
                break
        retained.sort(key=lambda item: (-item.projected_unsupported_distance_mm, item.region_id))
        if retained:
            status = PrintabilityStatus.CRITICAL if any(item.severity == PrintabilityStatus.CRITICAL for item in retained) else PrintabilityStatus.WARNING
            confidence = min((item.confidence for item in retained), key=lambda value: (PrintabilityConfidence.UNKNOWN, PrintabilityConfidence.LOW, PrintabilityConfidence.MEDIUM, PrintabilityConfidence.HIGH).index(value))
        elif context.facts.non_manifold_edges:
            status, confidence = PrintabilityStatus.INDETERMINATE, PrintabilityConfidence.LOW
        else:
            status, confidence = PrintabilityStatus.PASS, PrintabilityConfidence.MEDIUM
        evidence = tuple(face for region in retained for face in region.evidence_faces)[:limit.maximum_region_evidence]
        return BridgeRiskResult(
            status=status, confidence=confidence, candidate_region_count=len(retained), regions=tuple(retained), evidence_faces=evidence,
            duration_seconds=perf_counter() - started,
            limitations=(
                "Not every overhang is a bridge: only two-sided, elevated, downward geometric span candidates are retained.",
                "Bridge analysis is advisory and cannot determine real material behavior or exact bridge success.",
            ),
        )
    except MemoryError:
        raise
    except Exception as exc:
        return BridgeRiskResult(
            status=PrintabilityStatus.FAILED, confidence=PrintabilityConfidence.UNKNOWN, candidate_region_count=0,
            regions=(), evidence_faces=(), duration_seconds=perf_counter() - started,
            limitations=("Bridge-risk analysis failed without changing source geometry or transforms.",), error=f"{type(exc).__name__}: {exc}",
        )
