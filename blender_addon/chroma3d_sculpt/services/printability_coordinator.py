"""Read-only Sprint 3 coordinator for profile-driven advisory checks."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import platform
from time import perf_counter
from typing import Any
from uuid import uuid4

import bpy

from ..metadata import DISPLAY_VERSION, PRINTABILITY_REPORT_SCHEMA_VERSION
from ..models.printability_models import (
    EvidenceState,
    PrintabilityConfidence,
    PrintabilityResult,
    PrintabilityRiskItem,
    PrintabilityStatus,
    PrinterProfile,
    PrinterProfileSnapshot,
    RiskCategory,
    RiskSeverity,
    RuleClassification,
)
from ..printability_settings import PrintabilitySettings
from ..utilities.logging import get_logger
from ..utilities.printability_signatures import (
    geometry_signature,
    printability_source_snapshot,
    source_is_unchanged,
    transform_signature,
)
from .build_plate_contact import analyze_build_plate_contact
from .floating_components import NEUTRAL_FLOATING_MESSAGE, analyze_floating_components
from .geometry_facts import build_geometry_facts
from .orientation_analysis import analyze_orientations
from .overhang_analysis import analyze_overhangs
from .printability_scoring import score_printability
from .scale_evaluation import evaluate_scale_and_volume
from .thin_features import analyze_thin_features
from .wall_thickness import analyze_wall_thickness


logger = get_logger()


def _risk(
    suffix: str,
    rule_id: str,
    category: RiskCategory,
    state: PrintabilityStatus,
    confidence: PrintabilityConfidence,
    evidence_state: EvidenceState,
    message: str,
    review_action: str,
    classification: RuleClassification,
    source_references: tuple[str, ...],
    evidence_refs: tuple[str, ...],
    metrics: dict[str, Any],
    limitations: tuple[str, ...],
) -> PrintabilityRiskItem:
    severity = RiskSeverity.CRITICAL if state == PrintabilityStatus.CRITICAL else RiskSeverity.WARNING if state == PrintabilityStatus.WARNING else RiskSeverity.INFO
    return PrintabilityRiskItem(
        risk_item_schema_version=PRINTABILITY_REPORT_SCHEMA_VERSION,
        risk_id=f"risk-{suffix}",
        rule_id=rule_id,
        category=category,
        state=state,
        severity=severity,
        confidence=confidence,
        evidence_state=evidence_state,
        message=message,
        review_action=review_action,
        source_classification=classification,
        source_references=source_references,
        evidence_refs=evidence_refs,
        metrics=metrics,
        limitations=limitations,
    )


def analyze_printability(
    obj: Any,
    scene: Any,
    profile: PrinterProfile,
    settings: PrintabilitySettings | None = None,
    *,
    blender_version: str = "",
    blend_file_path: str = "",
) -> PrintabilityResult:
    """Run every Sprint 3 check without changing geometry, transforms, or scene state."""

    started = perf_counter()
    effective = (settings or PrintabilitySettings()).resolved(profile)
    snapshot = effective.snapshot(profile)
    source_before = printability_source_snapshot(obj, blend_file_path)
    geometry_hash = geometry_signature(obj)
    transform_hash = transform_signature(obj)
    analysis_id = str(uuid4())
    run_id = str(uuid4())
    logger.info("Printability analysis started: %s (%s/%s)", getattr(obj, "name", "<none>"), profile.profile_id, effective.mode.value)
    context = build_geometry_facts(obj, scene, effective)
    facts_elapsed = perf_counter() - started
    wall = analyze_wall_thickness(context, profile, effective)
    features = analyze_thin_features(context, profile, effective)
    overhangs = analyze_overhangs(context, profile, effective)
    floating = analyze_floating_components(context, effective)
    contact = analyze_build_plate_contact(context, effective)
    scale = evaluate_scale_and_volume(context, profile, effective, wall, features)
    orientation = analyze_orientations(context, profile, effective)
    facts = replace(context.facts, floating_shell_ids=tuple(str(item) for item in floating.floating_shell_ids))
    topology_status = (
        PrintabilityStatus.PASS
        if facts.watertight and facts.non_manifold_edges == 0 and facts.vertex_manifold_anomalies == 0
        else PrintabilityStatus.WARNING
    )
    topology_confidence = PrintabilityConfidence.HIGH if topology_status == PrintabilityStatus.PASS else PrintabilityConfidence.LOW
    topology = {
        "status": topology_status.value,
        "confidence": topology_confidence.value,
        "watertight": facts.watertight,
        "boundary_edges": facts.boundary_edges,
        "non_manifold_edges": facts.non_manifold_edges,
        "vertex_manifold_anomalies": facts.vertex_manifold_anomalies,
        "limitations": ["Topology readiness affects confidence; it does not predict manufacturing success."],
    }
    risks: list[PrintabilityRiskItem] = []
    if topology_status != PrintabilityStatus.PASS:
        risks.append(_risk(
            "topology-readiness", "RULE-002", RiskCategory.TOPOLOGY, topology_status, topology_confidence,
            EvidenceState.BOUNDED, "Open, boundary, or non-manifold topology reduces measurement confidence.",
            "Review diagnostic topology evidence before relying on profile-dependent measurements.",
            RuleClassification.CONSERVATIVE_HEURISTIC, (), (),
            {"boundary_edges": facts.boundary_edges, "non_manifold_edges": facts.non_manifold_edges},
            ("Topology findings do not prove that a print will fail.",),
        ))
    if wall.status in {PrintabilityStatus.WARNING, PrintabilityStatus.CRITICAL, PrintabilityStatus.INDETERMINATE}:
        risks.append(_risk(
            "wall-thickness", "RULE-003", RiskCategory.WALL_THICKNESS, wall.status, wall.confidence, wall.evidence_state,
            "Bounded wall samples crossed configured thickness thresholds." if wall.status in {PrintabilityStatus.WARNING, PrintabilityStatus.CRITICAL} else "Wall thickness could not be determined reliably for this geometry.",
            "Inspect the sampled regions and confirm wall behavior in the selected slicer and process.",
            RuleClassification.EXPERIMENTAL,
            tuple(sorted(set(profile.wall_thickness_warning_mm.source_references + profile.wall_thickness_critical_mm.source_references))),
            tuple(f"face:{item}" for item in wall.evidence_faces),
            {"minimum_sampled_thickness_mm": wall.minimum_sampled_thickness_mm, "samples_completed": wall.samples_completed},
            wall.limitations,
        ))
    if features.status in {PrintabilityStatus.WARNING, PrintabilityStatus.CRITICAL, PrintabilityStatus.INDETERMINATE}:
        risks.append(_risk(
            "thin-feature", "RULE-008", RiskCategory.THIN_FEATURE, features.status, features.confidence, features.evidence_state,
            "The experimental connected-shell diameter proxy crossed configured minimum-feature thresholds.",
            "Review the bounded feature evidence, unsupported length, material, orientation, and support plan.",
            RuleClassification.EXPERIMENTAL,
            tuple(sorted(set(profile.minimum_feature_warning_mm.source_references + profile.minimum_feature_critical_mm.source_references))),
            tuple(f"vertex:{item}" for item in features.evidence_vertices),
            {"minimum_diameter_mm": features.minimum_diameter_mm}, features.limitations,
        ))
    if overhangs.status in {PrintabilityStatus.WARNING, PrintabilityStatus.CRITICAL}:
        risks.append(_risk(
            "overhang", "RULE-011", RiskCategory.OVERHANG, overhangs.status, overhangs.confidence, overhangs.evidence_state,
            "Downward surfaces crossed configured overhang review angles under the recorded build direction.",
            "Review these support-sensitive surfaces in the selected slicer; the check does not determine support need.",
            RuleClassification.PROJECT_DEFAULT,
            tuple(sorted(set(profile.overhang_warning_angle_deg.source_references + profile.overhang_critical_angle_deg.source_references))),
            tuple(f"face:{item}" for item in overhangs.evidence_faces),
            {"warning_area_mm2": overhangs.warning_area_mm2, "critical_area_mm2": overhangs.critical_area_mm2}, overhangs.limitations,
        ))
    if floating.floating_shell_ids:
        risks.append(_risk(
            "floating-component", "RULE-014", RiskCategory.FLOATING_COMPONENT, floating.status, floating.confidence, floating.evidence_state,
            NEUTRAL_FLOATING_MESSAGE, "Review support or orientation for the disconnected component evidence.",
            RuleClassification.CONSERVATIVE_HEURISTIC, (), tuple(f"shell:{item}" for item in floating.floating_shell_ids),
            {"floating_shell_count": len(floating.floating_shell_ids)}, floating.limitations,
        ))
    if contact.status != PrintabilityStatus.PASS:
        risks.append(_risk(
            "build-contact", "RULE-015", RiskCategory.BUILD_CONTACT, contact.status, contact.confidence, contact.evidence_state,
            f"Build-plane contact was classified as {contact.classification.value}.",
            "Review placement, contact footprint, adhesion assumptions, and stability in the selected process.",
            RuleClassification.PROJECT_DEFAULT, (), tuple(f"face:{item}" for item in contact.evidence_faces),
            {"contact_area_mm2": contact.contact_area_mm2, "contact_region_count": contact.contact_region_count}, contact.limitations,
        ))
    if not scale.overall_fit:
        risks.append(_risk(
            "build-volume", "RULE-017", RiskCategory.BUILD_VOLUME, scale.status, scale.confidence, EvidenceState.COMPLETE,
            "The current orientation exceeds the margin-adjusted profile build volume.",
            "Review another orientation or the advisory uniform-scale trade-offs; no scale has been applied.",
            RuleClassification.USER_CONFIGURABLE, profile.build_volume_mm.source_references, (),
            {"overflow_mm": scale.overflow_mm, "maximum_uniform_fit_scale_percent": scale.maximum_uniform_fit_scale_percent}, scale.limitations,
        ))
    categories = {
        "topology_readiness": (topology_status, topology_confidence, "Topology readiness result."),
        "wall_thickness": (wall.status, wall.confidence, "; ".join(wall.limitations)),
        "thin_features": (features.status, features.confidence, "; ".join(features.limitations)),
        "overhangs": (overhangs.status, overhangs.confidence, "; ".join(overhangs.limitations)),
        "floating_components": (floating.status, floating.confidence, "; ".join(floating.limitations)),
        "build_plate_contact": (contact.status, contact.confidence, "; ".join(contact.limitations)),
        "build_volume": (scale.status, scale.confidence, "; ".join(scale.limitations)),
        "orientation": (orientation.status, orientation.confidence, "; ".join(orientation.limitations)),
    }
    critical_reasons = tuple(item.message for item in risks if item.state == PrintabilityStatus.CRITICAL)
    score = score_printability(categories, critical_reasons)
    if not source_is_unchanged(obj, source_before, blend_file_path):
        raise RuntimeError("Printability analysis changed protected source or saved-file state; result was rejected.")
    timings = {
        "geometry_facts": facts_elapsed,
        "wall_thickness": wall.duration_seconds,
        "thin_features": features.duration_seconds,
        "overhangs": overhangs.duration_seconds,
        "floating_components": floating.duration_seconds,
        "build_plate_contact": contact.duration_seconds,
        "scale_evaluation": scale.duration_seconds,
        "orientation": orientation.duration_seconds,
        "total": perf_counter() - started,
    }
    limitations = (
        "Advisory geometric and profile evidence only; this report is not a printability or manufacturing-success guarantee.",
        "No support generation, slicing, G-code, automatic rotation, automatic scaling, repair, remesh, material simulation, or exact print-time prediction is performed.",
        "Thickness is sampled/estimated, thin-feature detection is experimental, stability is heuristic, and orientation candidates are not guaranteed optimal.",
        "Real-print calibration remains pending.",
    )
    result = PrintabilityResult(
        report_schema_version=PRINTABILITY_REPORT_SCHEMA_VERSION,
        extension_version=DISPLAY_VERSION,
        blender_version=blender_version or getattr(bpy.app, "version_string", "Unknown"),
        operating_system=f"{platform.system()} {platform.release()}".strip(),
        analysis_id=analysis_id,
        printability_run_id=run_id,
        analyzed_at=datetime.now(timezone.utc),
        object_metadata={
            "object_name": str(obj.name),
            "mesh_data_name": str(obj.data.name),
            "object_identity": int(obj.as_pointer()),
            "mesh_identity": int(obj.data.as_pointer()),
            "mode": str(obj.mode),
            "blend_file_path": blend_file_path,
            "source": "ORIGINAL_MESH_DATABLOCK_READ_ONLY",
        },
        geometry_signature=geometry_hash,
        transform_signature=transform_hash,
        source_signature=str(source_before["printability_sha256"]),
        printer_profile_snapshot=PrinterProfileSnapshot(profile),
        settings_snapshot=snapshot,
        build_direction=effective.normalized_build_direction(),
        geometry_facts=facts,
        topology_readiness=topology,
        wall_thickness=wall,
        thin_features=features,
        overhangs=overhangs,
        floating_components=floating,
        build_plate_contact=contact,
        scale_evaluation=scale,
        orientation=orientation,
        risk_items=tuple(risks),
        score_details=score,
        timings=timings,
        warnings=tuple(scale.consequence_warnings),
        limitations=limitations,
    )
    logger.info("Printability analysis completed: %s (%s, %.3fs)", obj.name, score.status.value, timings["total"])
    return result
