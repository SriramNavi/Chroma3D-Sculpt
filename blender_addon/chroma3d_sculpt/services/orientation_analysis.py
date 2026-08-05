"""Bounded deterministic virtual orientation candidate generation and ranking."""

from __future__ import annotations

from hashlib import sha256
import json
import math
from time import perf_counter

from mathutils import Euler, Quaternion, Vector

from ..metadata import PRINTABILITY_REPORT_SCHEMA_VERSION
from ..models.printability_models import (
    ContactClassification,
    EvidenceState,
    OrientationCandidate,
    OrientationResult,
    OrientationSource,
    PrintabilityConfidence,
    PrintabilityStatus,
    PrinterProfile,
)
from ..printability_settings import PrintabilitySettings
from .geometry_facts import GeometryContext
from .overhang_analysis import overhang_angle_deg


def _canonical_quaternion(value: Quaternion) -> Quaternion:
    result = value.normalized()
    if result.w < 0.0:
        result = Quaternion(tuple(-component for component in result))
    return result


def _deduplicated(items: list[tuple[Quaternion, OrientationSource]], tolerance_degrees: float = 1.0) -> list[tuple[Quaternion, OrientationSource]]:
    retained: list[tuple[Quaternion, OrientationSource]] = []
    cosine = math.cos(math.radians(tolerance_degrees) * 0.5)
    for quaternion, source in items:
        canonical = _canonical_quaternion(quaternion)
        if any(abs(float(canonical.dot(existing))) >= cosine for existing, _source in retained):
            continue
        retained.append((canonical, source))
    return retained


def _candidate_id(quaternion: Quaternion) -> str:
    rounded = [round(float(value), 9) for value in quaternion]
    digest = sha256(json.dumps(rounded, separators=(",", ":")).encode("utf-8")).hexdigest()[:12]
    return f"orientation-{digest}"


def _generate(context: GeometryContext, settings: PrintabilitySettings) -> list[tuple[Quaternion, OrientationSource]]:
    items: list[tuple[Quaternion, OrientationSource]] = [(Quaternion((1.0, 0.0, 0.0, 0.0)), OrientationSource.CURRENT)]
    if settings.principal_axis_candidates_enabled:
        items.extend(
            (
                (Euler((math.pi / 2.0, 0.0, 0.0)).to_quaternion(), OrientationSource.PRINCIPAL_AXIS),
                (Euler((0.0, math.pi / 2.0, 0.0)).to_quaternion(), OrientationSource.PRINCIPAL_AXIS),
                (Euler((math.pi, 0.0, 0.0)).to_quaternion(), OrientationSource.BOUNDING_BOX_AXIS),
                (Euler((0.0, 0.0, math.pi / 2.0)).to_quaternion(), OrientationSource.BOUNDING_BOX_AXIS),
            )
        )
    direction = Vector(settings.normalized_build_direction())
    ordered_faces = sorted(range(context.facts.face_count), key=lambda index: (-context.face_areas_mm2[index], index))
    if settings.planar_face_candidates_enabled:
        for face_index in ordered_faces[:8]:
            normal = context.face_normals[face_index]
            if normal.length_squared > 1e-24:
                items.append((normal.rotation_difference(-direction), OrientationSource.PLANAR_FACE))
    for face_index in ordered_faces[:3]:
        normal = context.face_normals[face_index]
        if normal.length_squared > 1e-24:
            items.append((normal.rotation_difference(-direction), OrientationSource.STABLE_CONTACT))
    if settings.sampled_candidates_enabled:
        items.extend(
            (
                (Euler((math.radians(45.0), 0.0, 0.0)).to_quaternion(), OrientationSource.SAMPLED),
                (Euler((0.0, math.radians(45.0), 0.0)).to_quaternion(), OrientationSource.SAMPLED),
                (Euler((math.radians(35.264), 0.0, math.radians(45.0))).to_quaternion(), OrientationSource.SAMPLED),
            )
        )
    return _deduplicated(items)


def _evaluate(
    context: GeometryContext,
    profile: PrinterProfile,
    settings: PrintabilitySettings,
    quaternion: Quaternion,
    source: OrientationSource,
) -> OrientationCandidate:
    points = tuple(quaternion @ point for point in context.vertices_mm)
    minimum = Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points)))
    maximum = Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points)))
    dimensions = tuple(float(value) for value in (maximum - minimum))
    margin = profile.dimensional_safety_margin_mm.value
    usable = tuple(max(value - margin, 0.0) for value in profile.build_volume_mm.dimensions)
    fit = all(model <= available + settings.exact_boundary_tolerance_mm for model, available in zip(dimensions, usable))
    direction = Vector(settings.normalized_build_direction())
    plane_minimum = min(float(point.dot(direction)) for point in points)
    tolerance = float(settings.contact_tolerance_mm or 0.0)
    contact_faces: list[int] = []
    contact_area = 0.0
    for face_index, vertices in enumerate(context.face_vertices):
        offsets = [float(points[index].dot(direction)) - plane_minimum for index in vertices]
        if offsets and all(abs(value) <= tolerance for value in offsets):
            contact_faces.append(face_index)
            contact_area += context.face_areas_mm2[face_index]
    contact_class = ContactClassification.BROAD_CONTACT if contact_faces else ContactClassification.POINT_CONTACT
    warning_area = 0.0
    critical_area = 0.0
    for face_index, normal in enumerate(context.face_normals):
        if face_index in contact_faces:
            continue
        angle = overhang_angle_deg(quaternion @ normal, direction)
        if angle is None:
            continue
        if angle <= profile.overhang_critical_angle_deg.value:
            critical_area += context.face_areas_mm2[face_index]
            warning_area += context.face_areas_mm2[face_index]
        elif angle <= profile.overhang_warning_angle_deg.value:
            warning_area += context.face_areas_mm2[face_index]
    floating = 0
    for geometry in context.shells.geometries:
        shell_minimum = min(float(points[index].dot(direction)) for index in geometry.vertex_indices)
        if shell_minimum - plane_minimum > tolerance:
            floating += 1
    surface = max(context.facts.surface_area_mm2, 1e-12)
    weights = dict(settings.orientation_weights)
    risks = {
        "fit": 0.0 if fit else 1.0,
        "contact": max(0.0, 1.0 - min(contact_area / max(surface * 0.05, 1e-12), 1.0)),
        "overhang": min((warning_area + critical_area) / surface, 1.0),
        "floating": floating / max(context.facts.shell_count, 1),
        "height": min(dimensions[2] / max(usable[2], 1e-12), 1.0),
        "stability": 0.5 if contact_area > 0.0 else 1.0,
    }
    score = max(0.0, min(100.0, 100.0 * (1.0 - sum(weights[key] * risks[key] for key in weights))))
    status = PrintabilityStatus.CRITICAL if not fit or floating else PrintabilityStatus.WARNING if warning_area > 0.0 or not contact_faces else PrintabilityStatus.PASS
    advantages: list[str] = []
    trade_offs: list[str] = []
    (advantages if fit else trade_offs).append("Fits the margin-adjusted profile volume." if fit else "Exceeds the margin-adjusted profile volume.")
    (advantages if contact_area > 0.0 else trade_offs).append("Provides planar contact-area evidence." if contact_area > 0.0 else "Provides only point/edge-level contact evidence.")
    if floating:
        trade_offs.append(f"Leaves {floating} disconnected component(s) above the virtual build plane.")
    if warning_area > 0.0:
        trade_offs.append("Retains downward support-sensitive surface area for slicer review.")
    else:
        advantages.append("Reduces detected downward support-sensitive surface area in the bounded evaluation.")
    return OrientationCandidate(
        candidate_schema_version=PRINTABILITY_REPORT_SCHEMA_VERSION,
        candidate_id=_candidate_id(quaternion),
        rotation_quaternion=tuple(float(value) for value in quaternion),
        source=source,
        score=round(score, 3),
        overall_risk=status,
        advantages=tuple(advantages[:20]),
        trade_offs=tuple(trade_offs[:20]),
        confidence=PrintabilityConfidence.LOW,
        measurement_summary={
            "dimensions_mm": dimensions,
            "fits_build_volume": fit,
            "height_mm": dimensions[2],
            "contact_area_mm2": contact_area,
            "contact_classification": contact_class.value,
            "warning_overhang_area_mm2": warning_area,
            "critical_overhang_area_mm2": critical_area,
            "floating_component_count": floating,
            "support_exposure_proxy_percent": warning_area / surface * 100.0,
            "stability_heuristic": "HEURISTIC_ONLY" if contact_area else "UNAVAILABLE",
        },
        recommendation_reason="Bounded multi-objective what-if candidate; compare its recorded advantages and trade-offs before changing orientation.",
    )


def analyze_orientations(context: GeometryContext, profile: PrinterProfile, settings: PrintabilitySettings) -> OrientationResult:
    started = perf_counter()
    if context.facts.triangle_count > int(settings.triangle_limit or 0):
        return OrientationResult(
            status=PrintabilityStatus.SKIPPED_LIMIT,
            confidence=PrintabilityConfidence.UNKNOWN,
            evidence_state=EvidenceState.UNAVAILABLE,
            candidates_skipped=1,
            duration_seconds=perf_counter() - started,
            limitations=("Orientation evaluation was skipped at the configured triangle limit; no candidate was treated as safe.",),
        )
    try:
        generated = _generate(context, settings)
        limit = int(settings.orientation_candidate_limit or 1)
        selected = generated[:limit]
        candidates = [_evaluate(context, profile, settings, quaternion, source) for quaternion, source in selected]
        candidates.sort(key=lambda item: (-(item.score or -1.0), item.candidate_id))
        status = PrintabilityStatus.PASS if candidates else PrintabilityStatus.NOT_EVALUATED
        return OrientationResult(
            status=status,
            confidence=PrintabilityConfidence.LOW if candidates else PrintabilityConfidence.UNKNOWN,
            evidence_state=EvidenceState.BOUNDED if candidates else EvidenceState.UNAVAILABLE,
            candidates=tuple(candidates),
            candidates_generated=len(generated),
            candidates_evaluated=len(candidates),
            candidates_skipped=max(0, len(generated) - len(candidates)),
            duration_seconds=perf_counter() - started,
            limitations=(
                "Orientation candidates are bounded experimental recommendations and are not guaranteed optimal.",
                "No candidate rotates, moves, or scales the Blender object; supports, slicing, and visible-surface priorities require user review.",
            ),
        )
    except MemoryError:
        raise
    except Exception as exc:
        return OrientationResult(
            status=PrintabilityStatus.FAILED,
            confidence=PrintabilityConfidence.UNKNOWN,
            evidence_state=EvidenceState.UNAVAILABLE,
            duration_seconds=perf_counter() - started,
            limitations=("Orientation candidate evaluation failed without changing the object transform.",),
            error=f"{type(exc).__name__}: {exc}",
        )
