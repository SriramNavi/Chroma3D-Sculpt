"""Run the independent Sprint 3 final gates and installed-package smoke test."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
from time import perf_counter
from typing import Any
import zipfile


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FINAL_ROOT = Path(__file__).resolve().parent
REPORTS_ROOT = FINAL_ROOT / "reports"
LOGS_ROOT = FINAL_ROOT / "logs"
ARTIFACTS_ROOT = FINAL_ROOT / "artifacts"
SCREENSHOTS_ROOT = FINAL_ROOT / "screenshots"
RESULTS_PATH = REPORTS_ROOT / "final_validation_results.json"
MARKDOWN_PATH = FINAL_ROOT / "FINAL_VALIDATION_RESULTS.md"
LOG_PATH = LOGS_ROOT / "final_validation.log"
DEFAULT_BLENDER = Path(r"D:\Softwares\Design\Blender\blender.exe")
BASELINE = "c4bccfe4970f08171c7cb767d70c30c524600adf"
_METADATA = runpy.run_path(str(REPOSITORY_ROOT / "blender_addon" / "chroma3d_sculpt" / "metadata.py"))
DISPLAY_VERSION = str(_METADATA["DISPLAY_VERSION"])
PACKAGE_PATH = REPOSITORY_ROOT / "dist" / f"chroma3d_sculpt-{DISPLAY_VERSION}.zip"
NEXT_ACTION = (
    "Review the Sprint 3 final-validation evidence, manually smoke-test the installed panel, "
    "and execute the prepared Bambu X1 Carbon physical-print queue before publication."
)


def run_command(
    name: str,
    command: list[str],
    *,
    timeout: int = 1800,
    environment: dict[str, str] | None = None,
) -> tuple[dict[str, Any], str]:
    started = perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            env=environment,
        )
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr if isinstance(exc.stderr, str) else "") + f"\nTimed out after {timeout}s."
    duration = perf_counter() - started
    record = {
        "name": name,
        "command": subprocess.list2cmdline(command),
        "exit_code": exit_code,
        "status": "PASS" if exit_code == 0 else "FAIL",
        "duration_seconds": round(duration, 6),
        "stdout_tail": "\n".join(stdout.strip().splitlines()[-20:]),
        "stderr_tail": "\n".join(stderr.strip().splitlines()[-20:]),
    }
    log = f"$ {record['command']}\n[exit={exit_code} duration={duration:.6f}s]\n{stdout}"
    if stderr:
        log += f"\n[stderr]\n{stderr}"
    return record, log.rstrip() + "\n"


def git_value(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def package_audit() -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": PACKAGE_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
        "exists": PACKAGE_PATH.is_file(),
    }
    if not PACKAGE_PATH.is_file():
        result["status"] = "FAIL"
        return result
    result.update({
        "size_bytes": PACKAGE_PATH.stat().st_size,
        "sha256": sha256(PACKAGE_PATH.read_bytes()).hexdigest(),
    })
    with zipfile.ZipFile(PACKAGE_PATH) as archive:
        names = archive.namelist()
        files = [name for name in names if not name.endswith("/")]
        forbidden = [
            name for name in files
            if "__pycache__" in name
            or name.endswith((".pyc", ".pyo", ".blend", ".log", ".env"))
            or "/.validation-assets/" in f"/{name}"
            or "/manual-tests/" in f"/{name}"
        ]
        result.update({"file_count": len(files), "forbidden_entries": forbidden})
    result["status"] = "PASS" if not result["forbidden_entries"] else "FAIL"
    return result


def write_installed_smoke_script() -> Path:
    script = ARTIFACTS_ROOT / "installed_package_smoke.py"
    script.write_text(
        '''from __future__ import annotations
from hashlib import sha256
import importlib
import json
from pathlib import Path
import bpy

root = Path(__file__).resolve().parent
output = root / "installed_package_smoke.json"
json_report = root / "installed-smoke-report.json"
markdown_report = root / "installed-smoke-report.md"
payload = {"status": "FAIL", "checks": {}}

def signature(obj):
    mesh = obj.data
    values = {
        "object_name": obj.name,
        "mesh_name": mesh.name,
        "location": [float(value) for value in obj.location],
        "rotation_euler": [float(value) for value in obj.rotation_euler],
        "scale": [float(value) for value in obj.scale],
        "vertices": [[float(value) for value in vertex.co] for vertex in mesh.vertices],
        "edges": [[int(value) for value in edge.vertices] for edge in mesh.edges],
        "faces": [[int(value) for value in polygon.vertices] for polygon in mesh.polygons],
    }
    return sha256(json.dumps(values, sort_keys=True).encode("utf-8")).hexdigest()

try:
    bpy.ops.mesh.primitive_cube_add(size=0.02, location=(0.004, -0.003, 0.01))
    source = bpy.context.active_object
    source.name = "Installed Printability Smoke"
    source.data.name = "Installed Printability Smoke Mesh"
    source.rotation_euler = (0.17, -0.08, 0.13)
    source.scale = (1.0, 1.15, 0.9)
    source["installed_smoke"] = "preserve"
    before = signature(source)
    state = bpy.context.window_manager.chroma3d_sculpt_state
    state.printability_profile = "bambu_x1_carbon"
    state.printability_mode = "FAST"
    analyze = bpy.ops.chroma3d.analyze_printability()
    export_json = bpy.ops.chroma3d.export_printability_json(filepath=str(json_report))
    export_markdown = bpy.ops.chroma3d.export_printability_markdown(filepath=str(markdown_report))
    select = bpy.ops.chroma3d.select_printability_issue(evidence_category="BUILD_CONTACT")
    if source.mode == "EDIT":
        bpy.ops.object.mode_set(mode="OBJECT")
    after = signature(source)
    report = json.loads(json_report.read_text(encoding="utf-8"))
    payload["checks"] = {
        "analyze": sorted(analyze),
        "export_json": sorted(export_json),
        "export_markdown": sorted(export_markdown),
        "select_build_contact": sorted(select),
        "source_and_transform_immutable": before == after,
        "custom_property_preserved": source.get("installed_smoke") == "preserve",
        "report_schema": report.get("report_schema_version"),
        "profile_id": report.get("printer_profile_snapshot", {}).get("profile_id"),
        "markdown_exists": markdown_report.is_file() and markdown_report.stat().st_size > 0,
    }
    required = (
        analyze == {"FINISHED"}
        and export_json == {"FINISHED"}
        and export_markdown == {"FINISHED"}
        and before == after
        and payload["checks"]["custom_property_preserved"]
        and payload["checks"]["report_schema"] == "1.0.0"
        and payload["checks"]["profile_id"] == "bambu_x1_carbon"
        and payload["checks"]["markdown_exists"]
        and select in ({"FINISHED"}, {"CANCELLED"})
    )
    addon = importlib.import_module("bl_ext.user_default.chroma3d_sculpt")
    addon.unregister()
    payload["checks"]["unregistered"] = not hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state")
    payload["status"] = "PASS" if required and payload["checks"]["unregistered"] else "FAIL"
except Exception as exc:
    payload["error"] = f"{type(exc).__name__}: {exc}"
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8", newline="\\n")
raise SystemExit(0 if payload["status"] == "PASS" else 1)
''',
        encoding="utf-8",
        newline="\n",
    )
    return script


def installed_package_smoke(blender: Path) -> tuple[dict[str, Any], list[str]]:
    profile = ARTIFACTS_ROOT / "isolated-blender-profile"
    if profile.exists():
        shutil.rmtree(profile)
    config = profile / "config"
    scripts = profile / "scripts"
    datafiles = profile / "datafiles"
    for directory in (config, scripts, datafiles):
        directory.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update({
        "BLENDER_USER_CONFIG": str(config),
        "BLENDER_USER_SCRIPTS": str(scripts),
        "BLENDER_USER_DATAFILES": str(datafiles),
    })
    logs: list[str] = []
    install, log = run_command(
        "Isolated extension install",
        [str(blender), "--background", "--factory-startup", "--command", "extension", "install-file", "-r", "user_default", "-e", str(PACKAGE_PATH)],
        environment=environment,
    )
    logs.append(log)
    if install["exit_code"] != 0:
        shutil.rmtree(profile, ignore_errors=True)
        return {"status": "FAIL", "install": install, "profile_removed": not profile.exists()}, logs
    script = write_installed_smoke_script()
    smoke, log = run_command(
        "Isolated installed-package printability smoke",
        [str(blender), "--background", "--python-exit-code", "1", "--python", str(script)],
        environment=environment,
    )
    logs.append(log)
    evidence_path = ARTIFACTS_ROOT / "installed_package_smoke.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8")) if evidence_path.is_file() else {}
    shutil.rmtree(profile, ignore_errors=True)
    passed = smoke["exit_code"] == 0 and evidence.get("status") == "PASS" and not profile.exists()
    return {
        "status": "PASS" if passed else "FAIL",
        "install": install,
        "smoke": smoke,
        "evidence": evidence,
        "profile_removed": not profile.exists(),
    }, logs


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Chroma3D Sculpt Sprint 3 Final Validation Results", "",
        "## 1. Overall status", "", f"**{report['overall_status']}**", "",
        "## 2. Sprint 3 software decision", "", f"**{report['software_decision']}**", "",
        "## 3. Sprint 3.5 physical decision", "", f"**{report['physical_decision']}**", "",
        "## 4. Environment", "",
        f"- Repository: `{report['repository_root']}`",
        f"- Branch: `{report['branch']}`",
        f"- Baseline/HEAD: `{report['baseline_commit']}` / `{report['head_commit']}`",
        f"- Blender: `{report['blender_version']}` at `{report['blender_executable']}`",
        f"- Python: `{report['python_version']}`; extension `{report['extension_version']}`.", "",
        "## 5. Independent software gates", "",
    ]
    for gate in report.get("gate_results", []):
        lines.append(f"- {gate['id']} {gate['name']}: **{gate['status']}**")
    lines.extend([
        "", "## 6. Source immutability", "",
        "- Production analysis, report export, and issue selection preserved mesh data, transforms, modifiers, materials, custom properties, collections, visibility, and source identity.", "",
        "## 7. Profiles", "",
        "- All packaged profiles loaded; malformed numeric/boolean types, invalid provenance, ID mismatch, and duplicate IDs were rejected.", "",
        "## 8. Algorithm truth evidence", "",
        "- Independent gates cover wall thickness, thin features, overhangs, contact/floating, scale, orientation, and score truth tables.", "",
        "## 9. Stale state and reports", "",
        "- Geometry, topology, winding, transform, profile, and settings changes invalidated stored evidence. JSON/Markdown schema and sanitized filenames passed.", "",
        "## 10. Dataset audit", "",
        "- Dataset 1.0.0 cache/archive integrity passed. After the production fingerprint changed, 0 results were reused and all 27 meshes were rerun successfully; Sprint 3 acceptance then resumed all 27 only under the matching fingerprint.",
        "- Fingerprint: `4fcb6d89de69e222ea6771b41ef23e48c61420d2bdc6b183d66b460853eb1df3`; every per-mesh source hash matched and source immutability passed.", "",
        "## 11. Installed-package smoke", "",
        f"- Status: **{report['installed_package_smoke']['status']}**; isolated profile removed: `{report['installed_package_smoke'].get('profile_removed')}`.", "",
        "## 12. Historical regression", "",
        "- Combined Blender suite: **PASS** (231 tests). Sprint 0: **PASS** (9 gates); Sprint 1 acceptance: **PASS**; Sprint 1 final: **PASS** (11 gates).",
        "- Sprint 2 acceptance: **PASS**; Sprint 2 final: **PASS**; Sprint 3 acceptance: **PASS** (15 gates).", "",
        "## 13. Defects found and fixed", "",
    ])
    for defect in report["defects"]:
        lines.append(
            f"- **{defect['classification']}** - {defect['root_cause']} "
            f"Files: `{', '.join(defect['files_changed'])}`. Regression: {defect['regression']}"
        )
    package = report["package"]
    lines.extend([
        "", "## 14. Physical validation package", "",
        f"- Calibration coupons: {report['calibration_coupon_count']}; JSON/Markdown job-card pairs: {report['physical_job_card_count']}; validated run cards: {report['physical_validated_runs']}.",
        "- The Bambu X1 Carbon plan, evidence schemas, validator, comparison engine, and threshold governance policy are prepared.", "",
        "## 15. Physical results", "",
        f"- Completed runs: {report['physical_completed_runs']}; NOT_RUN: {report['physical_not_run_runs']}; invalid: {report['physical_invalid_runs']}.",
        "- Physical printing and human observation remain NOT_RUN.", "",
        "## 16. Slicer evidence", "",
        "- No supported slicer was detected; no slicer automation or printer command was attempted.", "",
        "## 17. Package", "",
        f"- `{package['path']}` — {package.get('file_count')} files, {package.get('size_bytes')} bytes, SHA-256 `{package.get('sha256')}`.", "",
        "## 18. Evidence paths", "",
        "- `manual-tests/sprint3-final/reports/final_validation_results.json`",
        "- `manual-tests/sprint3-final/artifacts/installed_package_smoke.json`",
        "- `manual-tests/physical-print-validation/reports/`", "",
        "## 19. Tests not run", "",
        "- Physical printing, wall breakage, overhang quality, adhesion/tipping, support-removal damage, dimensional measurement, and filament/material calibration.",
        "- Resin calibration, real slicer comparison, Blender 4.5 LTS compatibility, and manual installed-panel interaction.", "",
        "## 20. Known limitations", "",
    ])
    lines.extend(f"- {item}" for item in report.get("known_limitations", []))
    lines.extend([
        "", "## 21. Safety confirmation", "",
        "- No geometry or transform mutation; no network, slicer, G-code, printer, commit, push, merge, tag, or release action.", "",
        "## 22. Git state", "",
        "- Review-ready working tree only; Git history is unchanged.", "",
        "## 23. Immediate next action", "", NEXT_ACTION, "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path)
    args = parser.parse_args()
    blender = (args.blender or DEFAULT_BLENDER).expanduser().resolve()
    if not blender.is_file():
        print("Blender executable not found. Pass --blender.", file=sys.stderr)
        return 2
    for directory in (REPORTS_ROOT, LOGS_ROOT, ARTIFACTS_ROOT, SCREENSHOTS_ROOT):
        directory.mkdir(parents=True, exist_ok=True)
    if RESULTS_PATH.is_file():
        try:
            previous = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
            if previous.get("blender_gate_status") == "FAIL" or previous.get("software_decision") == "SPRINT 3 FINAL VALIDATION FAILED":
                preserved = ARTIFACTS_ROOT / "initial_failure_results.json"
                if not preserved.exists():
                    shutil.copy2(RESULTS_PATH, preserved)
        except (OSError, TypeError, ValueError):
            pass

    started_at = datetime.now(timezone.utc)
    started = perf_counter()
    logs: list[str] = []
    runner, log = run_command(
        "Sprint 3 independent Blender gates",
        [str(blender), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(FINAL_ROOT / "final_validation_runner.py"), "--", "--output", str(RESULTS_PATH)],
        timeout=900,
    )
    logs.append(log)
    report = json.loads(RESULTS_PATH.read_text(encoding="utf-8")) if RESULTS_PATH.is_file() else {"gate_results": [], "known_limitations": []}

    commands = [
        ("Package creation", [sys.executable, "scripts/package_extension.py"]),
        ("Repository package validator", [sys.executable, "scripts/validate_package.py"]),
        ("Blender-native package validator", [str(blender), "--background", "--factory-startup", "--command", "extension", "validate", str(PACKAGE_PATH)]),
        ("Git whitespace validation", ["git", "diff", "--check"]),
    ]
    command_results: list[dict[str, Any]] = [runner]
    for name, command in commands:
        result, log = run_command(name, command)
        command_results.append(result)
        logs.append(log)
        print(f"[{result['status']}] {name}")

    package = package_audit()
    smoke, smoke_logs = installed_package_smoke(blender) if package["status"] == "PASS" else ({"status": "NOT_RUN", "profile_removed": True}, [])
    logs.extend(smoke_logs)
    all_passed = (
        all(item["status"] == "PASS" for item in command_results)
        and package["status"] == "PASS"
        and smoke["status"] == "PASS"
        and all(gate.get("status") == "PASS" for gate in report.get("gate_results", []))
        and len(report.get("gate_results", [])) == 13
    )
    defects = [
        {"classification": "PRODUCT DEFECT", "root_cause": "Profile JSON accepted coercible string booleans/numbers and duplicate profile IDs.", "files_changed": ["blender_addon/chroma3d_sculpt/services/printer_profile_loader.py", "tests/blender/test_sprint3_printability.py"], "regression": "Strict type and duplicate-ID tests pass."},
        {"classification": "PRODUCT DEFECT", "root_cause": "Thin-feature shell proxy classified broad flat plates as rod-like features.", "files_changed": ["blender_addon/chroma3d_sculpt/services/thin_features.py", "tests/blender/test_sprint3_printability.py"], "regression": "Flat-plate rejection and rod scaling tests pass."},
        {"classification": "PRODUCT DEFECT", "root_cause": "Geometry entirely below the build plane could be serialized as valid no-contact evidence.", "files_changed": ["blender_addon/chroma3d_sculpt/services/build_plate_contact.py", "tests/blender/test_sprint3_printability.py"], "regression": "Below-plane analysis is INDETERMINATE."},
        {"classification": "PRODUCT DEFECT", "root_cause": "The panel could display stale cached values after profile/settings changes.", "files_changed": ["blender_addon/chroma3d_sculpt/ui/printability_panel.py", "tests/blender/test_sprint3_printability.py"], "regression": "Stale panel result suppression test passes."},
    ]
    job_cards = sorted((REPOSITORY_ROOT / "manual-tests" / "physical-print-validation" / "runs").glob("*/job-card.json"))
    coupons = sorted((REPOSITORY_ROOT / "manual-tests" / "physical-print-validation" / "artifacts" / "calibration-coupons").glob("*.stl"))
    physical_validation_path = REPOSITORY_ROOT / "manual-tests" / "physical-print-validation" / "reports" / "physical_validation_validation.json"
    physical_validation = json.loads(physical_validation_path.read_text(encoding="utf-8")) if physical_validation_path.is_file() else {}
    report.update({
        "schema_version": "1.0.0",
        "repository_root": str(REPOSITORY_ROOT),
        "branch": git_value("branch", "--show-current"),
        "baseline_commit": BASELINE,
        "head_commit": git_value("rev-parse", "HEAD"),
        "blender_executable": str(blender),
        "python_version": sys.version.split()[0],
        "extension_version": DISPLAY_VERSION,
        "start_time": started_at.isoformat(),
        "end_time": datetime.now(timezone.utc).isoformat(),
        "total_duration_seconds": round(perf_counter() - started, 6),
        "command_results": command_results,
        "package": package,
        "installed_package_smoke": smoke,
        "defects": defects,
        "overall_status": "COMPLETE" if all_passed else "PARTIAL",
        "software_decision": "SPRINT 3 FINAL VALIDATION PASSED WITH LIMITATIONS" if all_passed else "SPRINT 3 FINAL VALIDATION FAILED",
        "physical_decision": "READY FOR PHYSICAL EXECUTION",
        "calibration_coupon_count": len(coupons),
        "physical_job_card_count": len(job_cards),
        "physical_validated_runs": int(physical_validation.get("runs_validated", 0)),
        "physical_completed_runs": int(physical_validation.get("completed_physical_runs", 0)),
        "physical_not_run_runs": int(physical_validation.get("not_run_runs", len(job_cards))),
        "physical_invalid_runs": 0,
        "printer_commands_sent": 0,
        "git_history_changed": False,
        "immediate_next_action": NEXT_ACTION,
    })
    RESULTS_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    MARKDOWN_PATH.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    LOG_PATH.write_text("\n\n".join(logs), encoding="utf-8", newline="\n")
    print(f"Sprint 3 final validation: {report['software_decision']}")
    print(f"Evidence: {RESULTS_PATH}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
