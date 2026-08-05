"""Connected-shell contact classification relative to the selected build plane."""

from __future__ import annotations

from time import perf_counter

from mathutils import Vector

from ..models.printability_models import (
    EvidenceState,
    FloatingComponentEvidence,
    FloatingComponentResult,
    PrintabilityConfidence,
    PrintabilityStatus,
)
from ..printability_settings import PrintabilitySettings
from .geometry_facts import GeometryContext


NEUTRAL_FLOATING_MESSAGE = "Disconnected component not contacting the selected build plane; support or orientation review required."


def analyze_floating_components(context: GeometryContext, settings: PrintabilitySettings) -> FloatingComponentResult:
    started = perf_counter()
    direction = Vector(settings.normalized_build_direction())
    tolerance = float(settings.contact_tolerance_mm or 0.0)
    contacting: list[int] = []
    floating: list[int] = []
    evidence: list[FloatingComponentEvidence] = []
    cap = int(settings.evidence_cap or 1)
    retained = 0
    for shell, geometry in zip(context.shells.shells, context.shells.geometries):
        offsets = [float(context.vertices_mm[index].dot(direction)) for index in geometry.vertex_indices]
        minimum = min(offsets, default=float("inf"))
        maximum = max(offsets, default=float("-inf"))
        has_contact = minimum <= tolerance and maximum >= -tolerance
        (contacting if has_contact else floating).append(shell.shell_id)
        face_evidence = geometry.face_indices[: max(0, cap - retained)]
        retained += len(face_evidence)
        evidence.append(
            FloatingComponentEvidence(
                shell_id=shell.shell_id,
                vertex_count=shell.vertex_count,
                face_count=shell.face_count,
                surface_area_mm2=shell.surface_area_mm2,
                bbox_min_mm=shell.bbox_min_mm,
                bbox_max_mm=shell.bbox_max_mm,
                lowest_build_plane_offset_mm=minimum,
                contact_state="CONTACTING" if has_contact else "DISCONNECTED_NON_CONTACTING",
                evidence_faces=face_evidence,
            )
        )
    status = PrintabilityStatus.WARNING if floating else PrintabilityStatus.PASS
    confidence = PrintabilityConfidence.MEDIUM if context.facts.shell_count else PrintabilityConfidence.UNKNOWN
    total_faces = sum(item.face_count for item in evidence)
    return FloatingComponentResult(
        status=status,
        confidence=confidence,
        evidence_state=EvidenceState.TRUNCATED if total_faces > retained else EvidenceState.BOUNDED,
        shell_count=context.facts.shell_count,
        contacting_shell_ids=tuple(contacting),
        floating_shell_ids=tuple(floating),
        components=tuple(evidence),
        duration_seconds=perf_counter() - started,
        limitations=((NEUTRAL_FLOATING_MESSAGE,) if floating else ()) + (
            "Connectivity is geometric only; slicer-generated supports and process behavior are not modeled.",
        ),
    )
