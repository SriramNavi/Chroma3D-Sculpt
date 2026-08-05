"""Run the independent Sprint 4 Blender gates, package checks, and installed smoke."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from time import perf_counter
from typing import Any
import zipfile


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FINAL_ROOT = Path(__file__).resolve().parent
REPORT_ROOT = FINAL_ROOT / "reports"
LOG_ROOT = FINAL_ROOT / "logs"
ARTIFACT_ROOT = FINAL_ROOT / "artifacts"
BLENDER_REPORT = REPORT_ROOT / "blender_gate_results.json"
FINAL_REPORT = REPORT_ROOT / "final_validation_results.json"
INITIAL_FAILURE_REPORT = REPORT_ROOT / "initial_failure_results.json"
MARKDOWN_REPORT = FINAL_ROOT / "FINAL_VALIDATION_RESULTS.md"
RUNNER = FINAL_ROOT / "final_validation_runner.py"
PACKAGE_PATH = REPOSITORY_ROOT / "dist" / "chroma3d_sculpt-0.5.0-alpha.1.zip"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def run_command(name: str, command: list[str], timeout: int, *, env: dict[str, str] | None = None) -> dict[str, Any]:
    started = perf_counter()
    try:
        result = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        output = result.stdout or ""
        status = "PASS" if result.returncode == 0 else "FAIL"
        return {"name": name, "command": command, "status": status, "exit_code": result.returncode, "duration_seconds": perf_counter() - started, "output_tail": output[-4000:]}
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        return {"name": name, "command": command, "status": "TIMEOUT", "exit_code": None, "duration_seconds": perf_counter() - started, "output_tail": output[-4000:]}


def installed_smoke_script() -> Path:
    path = ARTIFACT_ROOT / "installed_package_smoke.py"
    source = r'''from __future__ import annotations
import json
from pathlib import Path
import bpy

output = Path(__file__).with_name("installed_package_smoke.json")
evidence = {"status": "FAIL", "checks": {}}
try:
    import bl_ext.user_default.chroma3d_sculpt as addon
    from bl_ext.user_default.chroma3d_sculpt.feature_flags import build_feature_flags
    from bl_ext.user_default.chroma3d_sculpt.printability_settings import PrintabilitySettings
    from bl_ext.user_default.chroma3d_sculpt.services.advanced_preparation_coordinator import analyze_advanced_preparation
    from bl_ext.user_default.chroma3d_sculpt.services.advanced_preparation_report import write_preparation_json
    from bl_ext.user_default.chroma3d_sculpt.services.hardware_profile_loader import load_hardware_profile
    from bl_ext.user_default.chroma3d_sculpt.services.material_profile_loader import load_material_profile
    from bl_ext.user_default.chroma3d_sculpt.services.process_context import compose_process_context
    from bl_ext.user_default.chroma3d_sculpt.services.regression_dashboard import dashboard_html, write_dashboard

    if not hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state"):
        addon.register()
    mesh = bpy.data.meshes.new("InstalledAdvancedMesh")
    mesh.from_pydata(((-5,-5,0),(5,-5,0),(5,5,0),(-5,5,0),(-5,-5,10),(5,-5,10),(5,5,10),(-5,5,10)), (), ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)))
    mesh.update()
    obj = bpy.data.objects.new("InstalledAdvanced", mesh)
    bpy.context.scene.collection.objects.link(obj)
    hardware = load_hardware_profile("bambu_x1_carbon")
    material = load_material_profile("generic_pla")
    process = compose_process_context(hardware, material, nozzle_mm=0.4, layer_height_mm=0.2, build_plate_type="TEXTURED")
    result = analyze_advanced_preparation(obj, bpy.context.scene, hardware, material, process, build_feature_flags(), PrintabilitySettings())
    report = output.with_name("installed_preparation.json")
    dashboard = output.with_name("installed_dashboard.html")
    write_preparation_json(result, report)
    write_dashboard(dashboard_html((), software_version=result.extension_version, dataset_version="1.0.0", baseline_version="1.0.0", profile_context=process.context_hash, generated_at="fixed"), dashboard)
    evidence["checks"] = {
        "panel_registered": hasattr(bpy.types, "CHROMA3D_PT_advanced_preparation"),
        "operator_registered": hasattr(bpy.ops.chroma3d, "analyze_advanced_preparation"),
        "analysis_completed": result.status.value in {"PASS","WARNING","CRITICAL","INDETERMINATE"},
        "report_exported": report.is_file(),
        "dashboard_generated": dashboard.is_file(),
    }
    evidence["status"] = "PASS" if all(evidence["checks"].values()) else "FAIL"
finally:
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
raise SystemExit(0 if evidence["status"] == "PASS" else 1)
'''
    path.write_text(source, encoding="utf-8", newline="\n")
    return path


def installed_package_smoke(blender: Path, timeout: int) -> dict[str, Any]:
    profile = ARTIFACT_ROOT / "isolated-blender-profile"
    if profile.exists():
        shutil.rmtree(profile)
    profile.mkdir(parents=True)
    environment = dict(os.environ)
    environment.update(
        {
            "BLENDER_USER_CONFIG": str(profile / "config"),
            "BLENDER_USER_SCRIPTS": str(profile / "scripts"),
            "BLENDER_USER_DATAFILES": str(profile / "datafiles"),
        }
    )
    install = run_command(
        "Isolated extension install",
        [str(blender), "--background", "--factory-startup", "--command", "extension", "install-file", "-r", "user_default", "-e", str(PACKAGE_PATH)],
        timeout,
        env=environment,
    )
    script = installed_smoke_script()
    compile_result = run_command("Compile installed smoke", [sys.executable, "-m", "py_compile", str(script)], timeout)
    smoke = run_command(
        "Installed Advanced Preparation smoke",
        [str(blender), "--background", "--python-exit-code", "1", "--python", str(script)],
        timeout,
        env=environment,
    ) if install["status"] == "PASS" and compile_result["status"] == "PASS" else {"status": "NOT_RUN", "exit_code": None, "output_tail": "Install or compile failed."}
    evidence_path = ARTIFACT_ROOT / "installed_package_smoke.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8")) if evidence_path.is_file() else {}
    if profile.exists():
        shutil.rmtree(profile)
    passed = install["status"] == "PASS" and compile_result["status"] == "PASS" and smoke["status"] == "PASS" and evidence.get("status") == "PASS" and not profile.exists()
    return {"status": "PASS" if passed else "FAIL", "install": install, "compile": compile_result, "smoke": smoke, "evidence": evidence, "profile_removed": not profile.exists()}


def package_checks(blender: Path, timeout: int) -> dict[str, Any]:
    build = run_command("Package creation", [sys.executable, "scripts/package_extension.py"], timeout)
    repository = run_command("Repository package validator", [sys.executable, "scripts/validate_package.py"], timeout)
    native = run_command("Blender-native package validator", [str(blender), "--background", "--command", "extension", "validate", str(PACKAGE_PATH)], timeout)
    files = []
    if PACKAGE_PATH.is_file():
        with zipfile.ZipFile(PACKAGE_PATH) as archive:
            files = [name for name in archive.namelist() if not name.endswith("/")]
    passed = all(item["status"] == "PASS" for item in (build, repository, native)) and PACKAGE_PATH.is_file()
    return {
        "status": "PASS" if passed else "FAIL",
        "build": build,
        "repository_validator": repository,
        "native_validator": native,
        "path": str(PACKAGE_PATH.relative_to(REPOSITORY_ROOT)),
        "file_count": len(files),
        "size_bytes": PACKAGE_PATH.stat().st_size if PACKAGE_PATH.is_file() else 0,
        "sha256": sha256(PACKAGE_PATH.read_bytes()).hexdigest() if PACKAGE_PATH.is_file() else None,
    }


def write_markdown(report: dict[str, Any]) -> None:
    lines = [
        "# Sprint 4 Independent Final Validation", "",
        f"- Decision: **{report['decision']}**",
        f"- Independent gates: {report['passed_gates']}/{report['total_gates']}",
        f"- Blender: {report['blender_version']}",
        f"- Extension: {report['extension_version']}", "",
        "## Gates", "", "| Gate | Result |", "|---|---|",
    ]
    lines.extend(f"| {item['gate_id']} - {item['name']} | {item['status']} |" for item in report["gates"])
    lines.extend(
        (
            "", "## Defects", "",
            f"- Product defects reproduced and fixed: {len(report['defects']['product'])}",
            f"- Harness defects reproduced and fixed: {len(report['defects']['harness'])}",
            f"- Fixture defects reproduced and fixed: {len(report['defects']['fixture'])}", "",
            "## Package", "",
            f"- Path: `{report['package']['path']}`",
            f"- Files: {report['package']['file_count']}",
            f"- Size: {report['package']['size_bytes']} bytes",
            f"- SHA-256: `{report['package']['sha256']}`", "",
            "## Deferred truth", "",
            "Physical printing, real slicer comparison, material calibration, Blender 4.5 LTS, and manual installed-panel interaction were not run. No print-success guarantee is made.", "",
        )
    )
    MARKDOWN_REPORT.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=2400)
    args = parser.parse_args()
    blender = args.blender.expanduser().resolve()
    if not blender.is_file():
        raise SystemExit(f"Blender executable not found: {blender}")
    for directory in (REPORT_ROOT, LOG_ROOT, ARTIFACT_ROOT):
        directory.mkdir(parents=True, exist_ok=True)

    package = package_checks(blender, args.timeout_seconds)
    blender_run = run_command(
        "Independent Sprint 4 Blender gates",
        [str(blender), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(RUNNER)],
        args.timeout_seconds,
    )
    (LOG_ROOT / "final_validation.log").write_text(blender_run.get("output_tail", "") + "\n", encoding="utf-8", newline="\n")
    payload = json.loads(BLENDER_REPORT.read_text(encoding="utf-8")) if BLENDER_REPORT.is_file() else {
        "overall_status": "FAIL", "passed_gates": 0, "total_gates": 16, "gates": [], "blender_version": "unknown", "extension_version": "unknown"
    }
    installed = installed_package_smoke(blender, args.timeout_seconds) if package["status"] == "PASS" else {"status": "NOT_RUN", "profile_removed": True}
    for gate in payload.get("gates", []):
        if gate.get("gate_id") == "S4F-N":
            gate["evidence"]["installed_package"] = installed
            if installed.get("status") != "PASS":
                gate["status"] = "FAIL"
                gate["error"] = "Installed-package smoke did not pass."
        if gate.get("gate_id") == "S4F-P":
            gate["evidence"]["wrapper_package"] = package
            if package.get("status") != "PASS":
                gate["status"] = "FAIL"
                gate["error"] = "Package validators did not pass."
    passed = sum(item.get("status") == "PASS" for item in payload.get("gates", []) if item.get("gate_id") != "S4F-CLEANUP")
    defects = {
        "product": [
            {"gate": "S4F-B", "status": "FIXED", "summary": "Custom hardware inputs converted booleans before strict numeric validation."},
            {"gate": "S4F-I", "status": "FIXED", "summary": "Batch resume accepted stale source evidence."},
            {"gate": "S4F-J", "status": "FIXED", "summary": "Baseline verifier accepted internally mismatched identity hashes."},
            {"gate": "S4F-L", "status": "FIXED", "summary": "Dashboard accepted non-local or executable evidence links."},
        ],
        "harness": [
            {"gate": "S4F-A", "status": "FIXED", "summary": "The export-artifact assertion expected seven files although the implementation correctly emits six."},
            {"gate": "S4F-F", "status": "FIXED", "summary": "The resin advisory assertion depended on one literal wording instead of the documented advisory state."},
            {"gate": "S4F-P", "status": "FIXED", "summary": "The ZIP audit assumed a legacy enclosing directory instead of the Blender Extension archive-root layout."},
        ],
        "fixture": [
            {"gate": "S4F-G", "status": "FIXED", "summary": "Independent geometry fixtures were initially authored in metres rather than millimetres."},
        ],
    }
    decision = "SPRINT 4 FINAL VALIDATION PASSED" if passed == 16 and blender_run["status"] == "PASS" else "SPRINT 4 FINAL VALIDATION FAILED"
    report = {
        **payload,
        "generated_at": utcnow(),
        "overall_status": "PASS" if decision.endswith("PASSED") else "FAIL",
        "decision": decision,
        "passed_gates": passed,
        "total_gates": 16,
        "gates": payload.get("gates", []),
        "package": package,
        "installed_package_smoke": installed,
        "blender_run": blender_run,
        "defects": defects,
        "deferred": ["physical printing", "real slicer comparison", "material calibration", "Blender 4.5 LTS", "manual installed-panel interaction"],
    }
    atomic_json(FINAL_REPORT, report)
    if report["overall_status"] != "PASS" and not INITIAL_FAILURE_REPORT.exists():
        atomic_json(INITIAL_FAILURE_REPORT, report)
    write_markdown(report)
    print(f"Sprint 4 independent final validation: {decision} ({passed}/16)")
    print(f"Evidence: {FINAL_REPORT}")
    return 0 if report["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
