"""Deterministic JSON/Markdown reports for Sprint 4 object and batch results."""

from __future__ import annotations

import json
from pathlib import Path
import re

from ..models.advanced_preparation_models import AdvancedPreparationResult, BatchPreparationResult


ADVISORY_DISCLAIMER = (
    "This software-only report is advisory. It does not guarantee printability, bridge success, support-free printing, adhesion, "
    "orientation optimality, material usage, print time, physical strength, or calibrated material behavior."
)


def sanitize_preparation_filename(object_name: str, suffix: str) -> str:
    if not re.fullmatch(r"[a-z0-9]{1,10}", suffix, re.IGNORECASE):
        raise ValueError("Report filename suffix is invalid.")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", object_name.strip()).strip("._") or "mesh"
    reserved_base = stem.split(".", 1)[0].upper()
    if reserved_base in {"CON", "PRN", "AUX", "NUL", *(f"COM{index}" for index in range(1, 10)), *(f"LPT{index}" for index in range(1, 10))}:
        stem = f"mesh_{stem}"
    return f"{stem[:120]}_chroma3d_preparation.{suffix}"


def preparation_markdown(result: AdvancedPreparationResult) -> str:
    process = result.process_context_snapshot.context
    interval = result.scale_recommendation.recommended_interval
    score = "Unavailable" if result.score is None else f"{result.score}/100"
    lines = [
        f"# Chroma3D Advanced Print Preparation - {result.object_metadata['object_name']}", "",
        "## Process context", "",
        f"- Hardware: {process.hardware_profile.manufacturer} {process.hardware_profile.printer_model}",
        f"- Material: {process.material_profile.display_name}", f"- Nozzle / resolution input: {process.nozzle_mm:g} mm",
        f"- Layer height: {process.layer_height_mm:g} mm", f"- Build plate: {process.build_plate_type}",
        f"- Support policy: {process.support_policy}", f"- Context hash: `{process.context_hash}`", "",
        "### Effective thresholds and provenance", "",
    ]
    for name in sorted(process.effective_thresholds):
        provenance = process.threshold_provenance[name]
        lines.append(
            f"- {name}: {process.effective_thresholds[name]:g} "
            f"({provenance['classification']}; {provenance['origin']})"
        )
    lines.extend([
        "", "## Batch context", "", "- Single-object analysis; no batch context.", "",
        "## Overall advisory result", "", f"- Score: {score}", f"- Status: {result.status.value}", f"- Confidence: {result.confidence.value}",
        f"- Performance mode: {result.performance_mode.value}", f"- Performance registry: {result.performance_registry_version}", "",
        "## Advanced checks", "",
        f"- Bridge risk: {result.bridge_risk.status.value}; candidates: {result.bridge_risk.candidate_region_count}",
        f"- Support risk: {result.support_risk.status.value}; regions: {result.support_risk.region_count}; area: {result.support_risk.total_risk_area_mm2:.3f} mm2",
        f"- Resin advisory: {result.resin_advisory.status.value}",
        f"- Scale interval: {interval.state} ({interval.minimum_percent}, {interval.maximum_percent})",
        f"- Orientation candidates: {len(result.orientation_comparison.candidates)}; Pareto/non-dominated: {len(result.orientation_comparison.pareto_candidate_ids)}", "",
        "## Bridge-risk regions", "",
    ])
    for region in result.bridge_risk.regions:
        lines.append(
            f"- {region.region_id}: {region.severity.value}; span {region.estimated_span_mm:.3f} mm; "
            f"unsupported {region.projected_unsupported_distance_mm:.3f} mm; supports {region.supporting_side_count}; confidence {region.confidence.value}"
        )
    if not result.bridge_risk.regions:
        lines.append("- None reported.")
    lines.extend(("", "## Support-risk regions", ""))
    for region in result.support_risk.regions:
        reasons = ", ".join(reason.value for reason in region.reason_categories)
        lines.append(f"- {region.region_id}: {region.severity.value}; {region.surface_area_mm2:.3f} mm2; {reasons}; {region.message}")
    if not result.support_risk.regions:
        lines.append("- None reported.")
    lines.extend(("", "## Resin advisory", ""))
    for name, evidence in sorted(result.resin_advisory.checks.items()):
        lines.append(f"- {name}: {evidence.get('state', 'NOT_EVALUATED')} ({evidence.get('classification', 'ADVISORY')})")
    if not result.resin_advisory.checks:
        lines.append("- Not applicable or disabled.")
    lines.extend(("", "## Orientation comparison", ""))
    for candidate in result.orientation_comparison.candidates:
        lines.append(
            f"- Rank {candidate['deterministic_rank']} / {candidate['candidate_id']}: fit {candidate['build_fit']}; "
            f"contact {candidate['contact_class']}; bridge risks {candidate['bridge_risk_count']}; "
            f"support-risk area {candidate['support_risk_area_mm2']:.3f} mm2"
        )
    if not result.orientation_comparison.candidates:
        lines.append("- No bounded candidate comparison available.")
    lines.extend(("", "## Feature flags", ""))
    for name, value in result.feature_flags.to_dict().items():
        if name not in {"schema_version", "experimental_flags", "flag_hash"}:
            lines.append(f"- {name}: {value}")
    lines.extend(("", "## Skipped checks", ""))
    lines.extend(f"- {item['check']}: {item['state']} - {item['reason']}" for item in result.skipped_checks)
    if not result.skipped_checks:
        lines.append("- None.")
    lines.extend(("", "## Failed checks", ""))
    lines.extend(f"- {item['check']}: {item['state']} - {item['reason']}" for item in result.failed_checks)
    if not result.failed_checks:
        lines.append("- None.")
    lines.extend(("", "## Warnings", ""))
    lines.extend(f"- {item}" for item in result.warnings)
    if not result.warnings:
        lines.append("- None.")
    lines.extend(("", "## Limitations", ""))
    lines.extend(f"- {item}" for item in result.limitations)
    lines.extend(("", "## Advisory disclaimer", "", ADVISORY_DISCLAIMER, ""))
    return "\n".join(lines)


def batch_markdown(result: BatchPreparationResult) -> str:
    process = result.process_context_snapshot
    hardware = process.get("hardware_profile", {})
    material = process.get("material_profile", {})
    lines = [
        "# Chroma3D Batch Advanced Print Preparation", "", f"- State: {result.state.value}",
        f"- Objects: {result.object_count}", f"- Completed: {result.completed_count}", f"- Failed: {result.failed_count}",
        f"- Skipped: {result.skipped_count}", f"- Total time: {result.total_time_seconds:.3f}s",
        f"- Hardware: {hardware.get('profile_id', 'unknown')}", f"- Material: {material.get('profile_id', 'unknown')}",
        f"- Process context hash: `{result.process_context_hash}`", f"- Feature flag hash: `{result.feature_flag_hash}`",
        "", "## Per-object summary", "",
    ]
    for item in result.object_results:
        lines.append(f"- {item.get('object_name', 'Unknown')}: {item.get('status', 'UNKNOWN')} / score {item.get('score')}")
    lines.extend(("", "## Limitations", ""))
    lines.extend(f"- {item}" for item in result.limitations)
    lines.extend(("", ADVISORY_DISCLAIMER, ""))
    return "\n".join(lines)


def write_preparation_json(result: AdvancedPreparationResult, destination: Path) -> Path:
    path = destination.expanduser().resolve().with_suffix(".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.to_json(), encoding="utf-8", newline="\n")
    return path


def write_preparation_markdown(result: AdvancedPreparationResult, destination: Path) -> Path:
    path = destination.expanduser().resolve().with_suffix(".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(preparation_markdown(result), encoding="utf-8", newline="\n")
    return path


def write_batch_json(result: BatchPreparationResult, destination: Path) -> Path:
    path = destination.expanduser().resolve().with_suffix(".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return path


def write_batch_markdown(result: BatchPreparationResult, destination: Path) -> Path:
    path = destination.expanduser().resolve().with_suffix(".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(batch_markdown(result), encoding="utf-8", newline="\n")
    return path
