"""Schema 1.0 JSON and human-readable Markdown printability reports."""

from __future__ import annotations

from pathlib import Path
import re

from ..models.printability_models import PrintabilityResult


ADVISORY_DISCLAIMER = (
    "This report is advisory geometric and profile-dependent evidence. It does not guarantee printability, "
    "manufacturing success, support requirements, orientation optimality, print time, or material behavior."
)


def sanitize_printability_filename(object_name: str, suffix: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", object_name.strip()).strip("._") or "mesh"
    stem = stem[:120]
    extension = ".json" if suffix == "json" else ".md"
    return f"{stem}_chroma3d_printability{extension}"


def write_printability_json(result: PrintabilityResult, destination: Path) -> Path:
    path = destination.expanduser().resolve()
    if path.suffix.lower() != ".json":
        path = path.with_suffix(".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.to_json(), encoding="utf-8", newline="\n")
    return path


def markdown_report(result: PrintabilityResult) -> str:
    score = "Unavailable" if result.score_details.score is None else f"{result.score_details.score}/100"
    critical = [item for item in result.risk_items if item.state.value == "CRITICAL"]
    warnings = [item for item in result.risk_items if item.state.value == "WARNING"]
    lines = [
        f"# Chroma3D Printability Report - {result.object_metadata['object_name']}",
        "",
        "## Executive risk summary",
        "",
        f"- Status: {result.score_details.status.value}",
        f"- Advisory score: {score}",
        f"- Confidence: {result.score_details.confidence.value}",
        f"- Critical risks: {len(critical)}",
        f"- Warnings: {len(warnings)}",
        f"- Missing/skipped/failed checks: {len(result.score_details.missing_checks) + len(result.score_details.skipped_checks) + len(result.score_details.failed_checks)}",
        "",
        "## Profile",
        "",
        f"- Profile: {result.printer_profile_snapshot.profile.display_name}",
        f"- Process: {result.printer_profile_snapshot.profile.process_type.value}",
        f"- Source classification: {result.printer_profile_snapshot.profile.source_classification.value}",
        f"- Profile hash: `{result.printer_profile_snapshot.profile.profile_hash}`",
        "",
        "## Critical issues",
        "",
    ]
    lines.extend(f"- {item.message} Review: {item.review_action}" for item in critical)
    if not critical:
        lines.append("- None detected by completed checks.")
    lines.extend(("", "## Warnings", ""))
    lines.extend(f"- {item.message} Review: {item.review_action}" for item in warnings)
    if not warnings:
        lines.append("- None detected by completed checks.")
    facts = result.geometry_facts
    lines.extend(
        (
            "",
            "## Geometry facts",
            "",
            f"- Dimensions: {facts.dimensions_mm[0]:.3f} x {facts.dimensions_mm[1]:.3f} x {facts.dimensions_mm[2]:.3f} mm",
            f"- Triangles: {facts.triangle_count:,}",
            f"- Shells: {facts.shell_count:,}",
            f"- Surface area: {facts.surface_area_mm2:.3f} mm2",
            f"- Reliable volume: {'Unavailable' if facts.reliable_volume_mm3 is None else f'{facts.reliable_volume_mm3:.3f} mm3'}",
            "",
            "## Check summaries",
            "",
        )
    )
    for check in result.check_results():
        lines.append(f"- {check['check'].replace('_', ' ').title()}: {check.get('status', 'UNKNOWN')} / {check.get('confidence', 'UNKNOWN')}")
    lines.extend(("", "## Orientation recommendations", ""))
    for rank, candidate in enumerate(result.orientation.candidates, 1):
        lines.append(f"{rank}. {candidate.candidate_id}: {candidate.score}/100, {candidate.overall_risk.value} - {candidate.recommendation_reason}")
        for trade_off in candidate.trade_offs:
            lines.append(f"   - Trade-off: {trade_off}")
    if not result.orientation.candidates:
        lines.append("- No candidate was evaluated; review the recorded skip/failure state.")
    lines.extend(("", "## Missing, skipped, or failed checks", ""))
    records = result.score_details.missing_checks + result.score_details.skipped_checks + result.score_details.failed_checks
    lines.extend(f"- {item['check']}: {item['state']} - {item['reason']}" for item in records)
    if not records:
        lines.append("- None.")
    lines.extend(("", "## Limitations", ""))
    lines.extend(f"- {item}" for item in result.limitations)
    lines.extend(("", "## Advisory disclaimer", "", ADVISORY_DISCLAIMER, ""))
    return "\n".join(lines)


def write_printability_markdown(result: PrintabilityResult, destination: Path) -> Path:
    path = destination.expanduser().resolve()
    if path.suffix.lower() != ".md":
        path = path.with_suffix(".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown_report(result), encoding="utf-8", newline="\n")
    return path
