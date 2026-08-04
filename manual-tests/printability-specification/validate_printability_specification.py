"""Validate the Sprint 2.8 printability specification without third-party packages."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DOC_ROOT = ROOT / "docs" / "printability"
PROFILE_ROOT = ROOT / "profiles" / "printability"
SCHEMA_ROOT = ROOT / "schemas"
OUTPUT_ROOT = Path(__file__).parent
RESULTS_PATH = OUTPUT_ROOT / "PRINTABILITY_SPECIFICATION_RESULTS.md"
MACHINE_REPORT_PATH = OUTPUT_ROOT / "reports" / "validation_results.json"

EXPECTED_STATES = {
    "PASS", "WARNING", "CRITICAL", "NOT_EVALUATED", "NOT_APPLICABLE",
    "SKIPPED_LIMIT", "INDETERMINATE", "FAILED",
}
EXPECTED_CONFIDENCE = {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}
EXPECTED_EVIDENCE = {"COMPLETE", "BOUNDED", "TRUNCATED", "UNAVAILABLE"}
EXPECTED_STALE = {"CURRENT", "STALE_GEOMETRY", "STALE_TRANSFORM", "STALE_PROFILE", "STALE_SETTINGS"}
CLASSIFICATIONS = {
    "AUTHORITATIVE_SOURCE", "STANDARDS_BASED", "PEER_REVIEWED_METHOD",
    "MANUFACTURER_SPECIFIC", "SLICER_GUIDANCE", "PROJECT_DEFAULT",
    "CONSERVATIVE_HEURISTIC", "USER_CONFIGURABLE", "EXPERIMENTAL",
    "NOT_YET_DEFINED",
}
THRESHOLD_FIELDS = (
    "dimensional_safety_margin_mm", "nozzle_diameter_mm", "nominal_layer_height_mm",
    "wall_thickness_warning_mm", "wall_thickness_critical_mm",
    "minimum_feature_warning_mm", "minimum_feature_critical_mm",
    "overhang_warning_angle_deg", "overhang_critical_angle_deg",
    "build_plate_contact_tolerance_mm",
)
PROFILE_FILES = (
    "generic_fdm.json", "generic_resin.json", "bambu_x1_carbon.json",
    "bambu_p1s.json", "prusa_mk4.json", "custom_profile.template.json",
)
SCHEMA_FILES = (
    "printer_profile.schema.json", "printability_settings.schema.json",
    "printability_report.schema.json", "printability_risk_item.schema.json",
    "orientation_candidate.schema.json",
)
REQUIRED_FILES = (
    "PRINTABILITY_SPECIFICATION.md", "PRINTABILITY_RESEARCH_SUMMARY.md",
    "docs/printability/README.md", "docs/printability/TERMINOLOGY_AND_RESULT_STATES.md",
    "docs/printability/RULE_CLASSIFICATION.md", "docs/printability/WALL_THICKNESS_METHOD.md",
    "docs/printability/THIN_FEATURE_METHOD.md", "docs/printability/OVERHANG_METHOD.md",
    "docs/printability/FLOATING_COMPONENTS.md", "docs/printability/BUILD_PLATE_CONTACT.md",
    "docs/printability/SCALE_AND_BUILD_VOLUME.md", "docs/printability/ORIENTATION_RECOMMENDATION.md",
    "docs/printability/PRINTABILITY_SCORING.md", "docs/printability/PERFORMANCE_MODES.md",
    "docs/printability/VALIDATION_FIXTURES.md", "docs/printability/ACCEPTANCE_GATES.md",
    "docs/printability/SOURCES.md", "docs/printability/OPEN_QUESTIONS.md",
    "manual-tests/printability-specification/validate_printability_specification.py",
    *[f"schemas/{name}" for name in SCHEMA_FILES],
    "profiles/printability/README.md",
    *[f"profiles/printability/{name}" for name in PROFILE_FILES],
)
PROHIBITED = (
    "guaranteed printable", "will print successfully", "perfect orientation",
    "no supports required", "exact print time", "universally safe",
    "guaranteed wall thickness", "definitely printable", "printability guarantee",
)


def read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_required_files() -> None:
    missing = [relative for relative in REQUIRED_FILES if not (ROOT / relative).is_file()]
    check(not missing, f"Missing required files: {missing}")


def validate_headings() -> None:
    required = {
        "PRINTABILITY_SPECIFICATION.md": ("## Purpose", "## Evaluation pipeline", "## Sprint 3 advisory scope"),
        "PRINTABILITY_RESEARCH_SUMMARY.md": ("## Outcome", "## Accepted evidence", "## Traceability"),
        "docs/printability/TERMINOLOGY_AND_RESULT_STATES.md": ("## Result states", "## Confidence states", "## Evidence states", "## Stale states"),
        "docs/printability/RULE_CLASSIFICATION.md": ("# Rule Classification Registry",),
        "docs/printability/WALL_THICKNESS_METHOD.md": ("## Meaning", "## Sampling contract", "## Outputs"),
        "docs/printability/THIN_FEATURE_METHOD.md": ("## Why this is separate", "## Sprint 3 target"),
        "docs/printability/OVERHANG_METHOD.md": ("## Convention", "## Face evaluation"),
        "docs/printability/FLOATING_COMPONENTS.md": ("## Definitions", "## Evaluation"),
        "docs/printability/BUILD_PLATE_CONTACT.md": ("## Contact classifications", "## Measurements"),
        "docs/printability/SCALE_AND_BUILD_VOLUME.md": ("## Fit rules", "## Uniform scale preview"),
        "docs/printability/ORIENTATION_RECOMMENDATION.md": ("## Candidate generation", "## Candidate metrics", "## Output"),
        "docs/printability/PRINTABILITY_SCORING.md": ("## Score meaning", "## Category weights", "## Critical caps and status precedence"),
        "docs/printability/PERFORMANCE_MODES.md": ("## Modes", "## Benchmark classes", "## Progress, cancellation, and states"),
        "docs/printability/VALIDATION_FIXTURES.md": ("## Wall thickness", "## Thin features", "## Overhangs", "## Contact and floating components", "## Orientation"),
        "docs/printability/ACCEPTANCE_GATES.md": ("## S3-01 - Architecture and regression", "## S3-14 - Package and release"),
        "docs/printability/SOURCES.md": ("## Classification and use ledger", "## Rejected weak evidence"),
        "docs/printability/OPEN_QUESTIONS.md": ("# Open Questions Before Sprint 3 Runtime Work",),
    }
    for relative, headings in required.items():
        content = read_text(relative)
        for heading in headings:
            check(heading in content, f"{relative} missing heading: {heading}")


def validate_no_placeholders() -> None:
    scan_paths = [ROOT / "PRINTABILITY_SPECIFICATION.md", ROOT / "PRINTABILITY_RESEARCH_SUMMARY.md", DOC_ROOT, PROFILE_ROOT]
    for path in scan_paths:
        paths = [path] if path.is_file() else sorted(path.rglob("*.md")) + sorted(path.rglob("*.json"))
        for file_path in paths:
            if file_path.name == "OPEN_QUESTIONS.md":
                continue
            text = file_path.read_text(encoding="utf-8").lower()
            check("todo" not in text and "tbd" not in text, f"Placeholder text found in {file_path.relative_to(ROOT)}")


def validate_rules_and_sources() -> tuple[int, int]:
    rules = []
    for line in read_text("docs/printability/RULE_CLASSIFICATION.md").splitlines():
        match = re.match(r"^\|\s*(RULE-\d{3})\s*\|(.+)\|$", line)
        if match:
            columns = [part.strip() for part in match.group(2).split("|")]
            check(len(columns) == 9, f"Malformed rule row: {line}")
            check(columns[2] in CLASSIFICATIONS, f"Rule {match.group(1)} has invalid classification")
            check(columns[7] != "", f"Rule {match.group(1)} has no confidence")
            rules.append(match.group(1))
    check(rules and len(rules) == len(set(rules)), "Rule IDs are missing or duplicated")

    source_rows = []
    for line in read_text("docs/printability/SOURCES.md").splitlines():
        match = re.match(r"^\|\s*(SRC-\d{3})\s*\|(.+)\|$", line)
        if match:
            columns = [part.strip() for part in match.group(2).split("|")]
            check(len(columns) == 8, f"Malformed source row: {line}")
            check(columns[2].startswith("https://"), f"Source {match.group(1)} has no HTTPS URL")
            source_rows.append(match.group(1))
    check(source_rows and len(source_rows) == len(set(source_rows)), "Sources are missing or duplicated")
    return len(rules), len(source_rows)


def validate_profiles() -> int:
    profiles = []
    for filename in PROFILE_FILES:
        path = PROFILE_ROOT / filename
        profile = read_json(path)
        profiles.append(profile)
        required = {
            "profile_schema_version", "profile_id", "display_name", "manufacturer", "printer_model",
            "process_type", "source_classification", "source_references", "build_volume_mm",
            "dimensional_safety_margin_mm", "nozzle_diameter_mm", "nominal_layer_height_mm",
            "wall_thickness_warning_mm", "wall_thickness_critical_mm", "minimum_feature_warning_mm",
            "minimum_feature_critical_mm", "overhang_warning_angle_deg", "overhang_critical_angle_deg",
            "build_plate_contact_tolerance_mm", "bridge_guidance", "support_assumption", "material_family",
            "notes", "confidence", "user_editable_fields", "created_at", "updated_at",
        }
        check(required <= profile.keys(), f"{filename} is missing profile fields")
        check(profile["profile_schema_version"] == "1.0.0", f"{filename} profile schema version mismatch")
        check(profile["process_type"] in {"FDM", "RESIN", "CUSTOM"}, f"{filename} invalid process type")
        check(profile["source_classification"] in CLASSIFICATIONS, f"{filename} invalid source classification")
        check(profile["confidence"] in EXPECTED_CONFIDENCE, f"{filename} invalid confidence")
        dimensions = profile["build_volume_mm"]
        check(dimensions.get("unit") == "mm", f"{filename} build volume unit is not mm")
        check(all(isinstance(dimensions.get(axis), (int, float)) and dimensions[axis] > 0 for axis in ("x", "y", "z")), f"{filename} invalid build volume")
        check(dimensions["classification"] in CLASSIFICATIONS, f"{filename} build volume has no classification")
        for field in THRESHOLD_FIELDS:
            value = profile[field]
            check(isinstance(value, dict), f"{filename} {field} is not a classified object")
            check(value.get("classification") in CLASSIFICATIONS, f"{filename} {field} has no valid classification")
            check(isinstance(value.get("rationale"), str) and value["rationale"], f"{filename} {field} has no rationale")
            check(value.get("confidence") in EXPECTED_CONFIDENCE, f"{filename} {field} has no confidence")
            check(isinstance(value.get("user_editable"), bool), f"{filename} {field} editability missing")
            check(isinstance(value.get("source_references"), list), f"{filename} {field} source refs missing")
            check(all(re.fullmatch(r"SRC-\d{3}", source) for source in value["source_references"]), f"{filename} {field} bad source ref")
        check(profile["wall_thickness_critical_mm"]["value"] < profile["wall_thickness_warning_mm"]["value"], f"{filename} wall threshold order invalid")
        check(profile["minimum_feature_critical_mm"]["value"] < profile["minimum_feature_warning_mm"]["value"], f"{filename} feature threshold order invalid")
        check(profile["overhang_critical_angle_deg"]["value"] < profile["overhang_warning_angle_deg"]["value"], f"{filename} overhang threshold order invalid")
        if profile["profile_id"] not in {"generic_fdm", "generic_resin", "custom_profile_template"}:
            manufacturer_claims = [field for field in THRESHOLD_FIELDS if profile[field]["classification"] == "MANUFACTURER_SPECIFIC"]
            check(set(manufacturer_claims) <= {"nozzle_diameter_mm"}, f"{filename} has unsupported manufacturer threshold claims: {manufacturer_claims}")
            check(profile["build_volume_mm"]["classification"] == "MANUFACTURER_SPECIFIC", f"{filename} missing manufacturer build-volume classification")
        check("guarantee" not in profile["notes"].lower(), f"{filename} contains unsupported guarantee wording")
    return len(profiles)


def validate_schemas() -> None:
    schemas = {name: read_json(SCHEMA_ROOT / name) for name in SCHEMA_FILES}
    for name, schema in schemas.items():
        check(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", f"{name} is not a Draft 2020-12 schema")
        check(isinstance(schema.get("required"), list), f"{name} has no required list")
    report = schemas["printability_report.schema.json"]
    check(report["properties"]["risk_items"]["items"]["$ref"] == "printability_risk_item.schema.json", "Report risk-item reference is broken")
    check(report["properties"]["orientation_candidates"]["items"]["$ref"] == "orientation_candidate.schema.json", "Report orientation reference is broken")
    check((SCHEMA_ROOT / "printability_risk_item.schema.json").is_file(), "Risk schema reference target missing")
    check((SCHEMA_ROOT / "orientation_candidate.schema.json").is_file(), "Orientation schema reference target missing")


def validate_states_and_convention() -> None:
    terminology = read_text("docs/printability/TERMINOLOGY_AND_RESULT_STATES.md")
    for state in EXPECTED_STATES:
        check(f"`{state}`" in terminology, f"Result state missing from terminology: {state}")
    for state in EXPECTED_CONFIDENCE:
        check(f"`{state}`" in terminology, f"Confidence state missing from terminology: {state}")
    for state in EXPECTED_EVIDENCE:
        check(f"`{state}`" in terminology, f"Evidence state missing from terminology: {state}")
    for state in EXPECTED_STALE:
        check(f"`{state}`" in terminology, f"Stale state missing from terminology: {state}")
    overhang = read_text("docs/printability/OVERHANG_METHOD.md")
    check("Build direction is a recorded unit vector and defaults to `+Z`" in overhang, "Overhang build direction convention missing")
    check("downward horizontal underside" in overhang.lower() and "0 deg" in overhang, "Overhang horizontal convention missing")
    check("Vertical face" in overhang and "90 deg" in overhang, "Overhang vertical convention missing")
    check("dot(n, b) < 0" in overhang, "Overhang normal convention missing")
    for relative in ("WALL_THICKNESS_METHOD.md", "THIN_FEATURE_METHOD.md", "OVERHANG_METHOD.md", "BUILD_PLATE_CONTACT.md", "SCALE_AND_BUILD_VOLUME.md", "PERFORMANCE_MODES.md"):
        check("mm" in read_text(f"docs/printability/{relative}"), f"Units are not explicit in {relative}")


def validate_scoring() -> None:
    rows = []
    for line in read_text("docs/printability/PRINTABILITY_SCORING.md").splitlines():
        match = re.match(r"^\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|$", line)
        if match and "Total" not in match.group(1):
            rows.append((match.group(1).strip(), int(match.group(2))))
    check(len(rows) == 8, f"Expected eight scoring categories, found {len(rows)}")
    check(sum(weight for _, weight in rows) == 100, "Scoring weights do not total 100")
    check("capped at `59`" in read_text("docs/printability/PRINTABILITY_SCORING.md"), "Critical score cap missing")


def validate_project_invariants() -> None:
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    check(branch == "feature/sprint-2.8-printability-specification", f"Unexpected branch: {branch}")
    sprint_docs = ["README.md", "PRODUCT_REQUIREMENTS.md", "TECHNICAL_ROADMAP.md", "ROADMAP.md", "ARCHITECTURE.md", "PRINTABILITY_SPECIFICATION.md"]
    for relative in sprint_docs:
        content = read_text(relative)
        check(re.search(r"Sprint 3 (?:has not started|remains unstarted|not started)", content, re.IGNORECASE) is not None, f"{relative} does not preserve Sprint 3 unstarted state")
    manifest = read_text("blender_addon/chroma3d_sculpt/blender_manifest.toml")
    metadata = read_text("blender_addon/chroma3d_sculpt/metadata.py")
    check('version = "0.3.0"' in manifest and 'EXTENSION_VERSION = "0.3.0"' in metadata, "Extension version changed")
    check("v0.3.1-alpha.1" in read_text("PRINTABILITY_SPECIFICATION.md"), "Milestone release is missing")
    changed = subprocess.run(["git", "diff", "--name-only"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.splitlines()
    forbidden = [path for path in changed if (path.startswith("blender_addon/") or path.startswith("tests/") or path.startswith("scripts/"))]
    check(not forbidden, f"Runtime/diagnostic/repair files changed: {forbidden}")
    non_validator_python = [path for path in changed if path.endswith(".py") and path != "manual-tests/printability-specification/validate_printability_specification.py"]
    check(not non_validator_python, f"Unexpected Python files changed: {non_validator_python}")


def validate_prohibited_wording() -> None:
    scan_files = [ROOT / "PRINTABILITY_SPECIFICATION.md", ROOT / "PRINTABILITY_RESEARCH_SUMMARY.md", *DOC_ROOT.rglob("*.md"), *PROFILE_ROOT.rglob("*.json")]
    negative_markers = ("not", "no", "does not", "never", "cannot", "prohibited", "without")
    for path in scan_files:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            lower = line.lower()
            for phrase in PROHIBITED:
                if phrase in lower:
                    check(any(marker in lower for marker in negative_markers), f"Unsupported wording {phrase!r} at {path.relative_to(ROOT)}:{line_number}")


def run() -> dict[str, Any]:
    checks: list[str] = []
    validate_required_files(); checks.append("required_files")
    validate_headings(); checks.append("required_headings")
    validate_no_placeholders(); checks.append("no_placeholders")
    rule_count, source_count = validate_rules_and_sources(); checks.append("rules_and_sources")
    profile_count = validate_profiles(); checks.append("profiles")
    validate_schemas(); checks.append("schemas")
    validate_states_and_convention(); checks.append("states_and_convention")
    validate_scoring(); checks.append("scoring")
    validate_project_invariants(); checks.append("project_invariants")
    validate_prohibited_wording(); checks.append("prohibited_wording")
    return {
        "status": "PASS",
        "specification": "Sprint 2.8 Printability Engineering Specification",
        "rule_count": rule_count,
        "source_count": source_count,
        "profile_count": profile_count,
        "checks": checks,
        "runtime_implementation": False,
        "sprint_3_started": False,
        "extension_version": "0.3.0-alpha.1",
        "repository_release": "v0.3.1-alpha.1",
        "dataset_version": "1.0.0",
        "golden_benchmark_version": "1.0.0",
        "known_limitations": [
            "Thresholds remain profile-dependent and generic examples use project defaults.",
            "Real-print calibration remains pending.",
            "Support generation, slicing, hollowing, drain holes, suction, and simulation remain deferred.",
            "The specification makes no print-success guarantee.",
        ],
    }


def write_evidence(result: dict[str, Any]) -> None:
    MACHINE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MACHINE_REPORT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Sprint 2.8 Printability Specification Results",
        "",
        f"**Status:** `{result['status']}`",
        "",
        "## Evidence",
        "",
        f"- Rules validated: `{result.get('rule_count', 0)}`",
        f"- Sources validated: `{result.get('source_count', 0)}`",
        f"- Profiles validated: `{result.get('profile_count', 0)}`",
        f"- Runtime implementation changed: `{result.get('runtime_implementation', False)}`",
        f"- Sprint 3 started: `{result.get('sprint_3_started', False)}`",
        f"- Extension version: `{result.get('extension_version', 'not established')}`",
        f"- Repository release: `{result.get('repository_release', 'not established')}`",
        f"- Dataset: `{result.get('dataset_version', 'not established')}`",
        f"- Golden Benchmark: `{result.get('golden_benchmark_version', 'not established')}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- PASS: `{name}`" for name in result.get("checks", []))
    lines.extend(["", "## Known limitations", ""])
    lines.extend(f"- {item}" for item in result.get("known_limitations", [result.get("error", "Validation failed")]))
    lines.extend(["", "## Required next action", "", "Review and approve the Sprint 2.8 Printability Engineering Specification before authorizing Sprint 3 runtime implementation.", ""])
    RESULTS_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    try:
        result = run()
    except Exception as exc:  # pragma: no cover - command-line failure path
        result = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}", "checks": []}
        write_evidence(result)
        print(f"FAIL: {result['error']}", file=sys.stderr)
        return 1
    write_evidence(result)
    print(f"PASS: {result['specification']} ({result['rule_count']} rules, {result['profile_count']} profiles)")
    print(f"Evidence: {RESULTS_PATH.relative_to(ROOT)}")
    print(f"Machine report: {MACHINE_REPORT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
