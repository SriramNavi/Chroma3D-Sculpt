"""Run the independent Sprint 2 final validation and regression chain."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from time import perf_counter
from typing import Any
import zipfile


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FINAL_DIRECTORY = Path(__file__).resolve().parent
REPORTS_DIRECTORY = FINAL_DIRECTORY / "reports"
LOGS_DIRECTORY = FINAL_DIRECTORY / "logs"
ARTIFACTS_DIRECTORY = FINAL_DIRECTORY / "artifacts"
RESULTS_PATH = REPORTS_DIRECTORY / "final_validation_results.json"
MARKDOWN_PATH = FINAL_DIRECTORY / "FINAL_VALIDATION_RESULTS.md"
LOG_PATH = LOGS_DIRECTORY / "blender_final_validation.log"
PACKAGE_PATH = REPOSITORY_ROOT / "dist" / "chroma3d_sculpt-0.3.0-alpha.1.zip"
DEFAULT_BLENDER = Path(r"D:\Softwares\Design\Blender\blender.exe")


def _run(name: str, command: list[str], *, timeout: int = 1800, env: dict[str, str] | None = None) -> tuple[dict[str, Any], str]:
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
            env=env,
        )
        code, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as exc:
        code = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr if isinstance(exc.stderr, str) else "") + f"\nTimed out after {timeout}s."
    duration = perf_counter() - started
    record = {
        "name": name,
        "command": subprocess.list2cmdline(command),
        "exit_code": code,
        "status": "PASS" if code == 0 else "FAIL",
        "duration_seconds": round(duration, 6),
        "stdout_tail": "\n".join(stdout.strip().splitlines()[-20:]),
        "stderr_tail": "\n".join(stderr.strip().splitlines()[-20:]),
    }
    log = f"$ {record['command']}\n[exit={code} duration={duration:.6f}s]\n{stdout}"
    if stderr:
        log += f"\n[stderr]\n{stderr}"
    return record, log.rstrip() + "\n"


def _git_value(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments], cwd=REPOSITORY_ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _security_and_package_audit() -> dict[str, Any]:
    source = REPOSITORY_ROOT / "blender_addon" / "chroma3d_sculpt"
    patterns = {
        "network_import": re.compile(r"^\s*(?:from|import)\s+(?:requests|urllib|http\.|socket|aiohttp|httpx)\b", re.MULTILINE),
        "subprocess_runtime": re.compile(r"^\s*(?:from|import)\s+subprocess\b", re.MULTILINE),
        "dynamic_execution": re.compile(r"\b(?:eval|exec)\s*\("),
        "pickle": re.compile(r"^\s*(?:from|import)\s+pickle\b", re.MULTILINE),
        "hard_coded_repository": re.compile(re.escape(str(REPOSITORY_ROOT)), re.IGNORECASE),
        "hard_coded_windows_path": re.compile(r"(?i)[A-Z]:[\\/](?:Users|VPRS|Program Files|Softwares)[\\/]"),
    }
    findings: list[dict[str, str]] = []
    for path in sorted(source.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for label, pattern in patterns.items():
            if pattern.search(text):
                findings.append({"type": label, "path": path.relative_to(REPOSITORY_ROOT).as_posix()})
    forbidden_files = []
    for path in REPOSITORY_ROOT.rglob("*"):
        if not path.is_file():
            continue
        lower = path.name.lower()
        if lower == ".env" or lower.startswith(".env.") or path.suffix.lower() in {".pem", ".p12", ".pfx", ".key"}:
            forbidden_files.append(path.relative_to(REPOSITORY_ROOT).as_posix())

    package: dict[str, Any] = {
        "path": PACKAGE_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
        "exists": PACKAGE_PATH.is_file(),
    }
    if PACKAGE_PATH.is_file():
        package.update({"size_bytes": PACKAGE_PATH.stat().st_size, "sha256": sha256(PACKAGE_PATH.read_bytes()).hexdigest()})
        with zipfile.ZipFile(PACKAGE_PATH) as archive:
            names = archive.namelist()
            bad = [name for name in names if "__pycache__" in name or name.endswith((".pyc", ".pyo", ".blend", ".log"))]
            package.update({"file_count": len([name for name in names if not name.endswith("/")]), "forbidden_entries": bad})
    package["status"] = "PASS" if package.get("exists") and not package.get("forbidden_entries") else "FAIL"
    return {
        "status": "PASS" if not findings and not forbidden_files and package["status"] == "PASS" else "FAIL",
        "runtime_findings": findings,
        "forbidden_files": forbidden_files,
        "package": package,
    }


def _installed_smoke_script() -> Path:
    path = ARTIFACTS_DIRECTORY / "installed_package_smoke.py"
    path.write_text(
        '''from __future__ import annotations
import json
from pathlib import Path
import bpy

output = Path(__file__).with_name("installed_package_smoke.json")
payload = {"status": "FAIL", "checks": {}}
try:
    payload["checks"]["operator_registered"] = hasattr(bpy.ops.chroma3d, "start_repair_session")
    bpy.ops.mesh.primitive_cube_add()
    source = bpy.context.active_object
    source.name = "InstalledSmokeSource"
    source.data.vertices[1].co = source.data.vertices[0].co
    source_hash = tuple(tuple(float(v) for v in vertex.co) for vertex in source.data.vertices)
    start = bpy.ops.chroma3d.start_repair_session()
    workspace = bpy.context.active_object
    workspace_name = workspace.name
    plan = bpy.ops.chroma3d.generate_repair_plan()
    state = bpy.context.window_manager.chroma3d_sculpt_state
    state.repair_merge_duplicates = True
    apply_result = bpy.ops.chroma3d.apply_single_repair(operation_type="MERGE_DUPLICATE_VERTICES")
    undo = bpy.ops.chroma3d.undo_last_repair()
    rollback = bpy.ops.chroma3d.rollback_repair_session()
    payload["checks"].update({
        "start": sorted(start), "plan": sorted(plan), "apply": sorted(apply_result),
        "undo": sorted(undo), "rollback": sorted(rollback),
        "source_preserved": source.name in bpy.data.objects and source_hash == tuple(tuple(float(v) for v in vertex.co) for vertex in source.data.vertices),
        "workspace_removed": workspace_name not in bpy.data.objects,
    })
    payload["status"] = "PASS" if payload["checks"]["operator_registered"] and payload["checks"]["source_preserved"] and payload["checks"]["workspace_removed"] else "FAIL"
except Exception as exc:
    payload["error"] = f"{type(exc).__name__}: {exc}"
output.write_text(json.dumps(payload, indent=2) + "\\n", encoding="utf-8", newline="\\n")
raise SystemExit(0 if payload["status"] == "PASS" else 1)
''',
        encoding="utf-8", newline="\n",
    )
    return path


def _installed_package_smoke(blender: Path) -> tuple[dict[str, Any], list[str]]:
    profile = ARTIFACTS_DIRECTORY / "isolated-blender-profile"
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
    install, log = _run(
        "Isolated extension install",
        [str(blender), "--background", "--factory-startup", "--command", "extension", "install-file", "-r", "user_default", "-e", str(PACKAGE_PATH)],
        env=environment,
    )
    logs.append(log)
    if install["exit_code"] != 0:
        return {"status": "NOT_RUN", "reason": "Isolated Blender extension installation failed.", "install": install}, logs
    script = _installed_smoke_script()
    smoke, log = _run(
        "Isolated installed-package repair smoke",
        [str(blender), "--background", "--python-exit-code", "1", "--python", str(script)],
        env=environment,
    )
    logs.append(log)
    evidence_path = script.with_name("installed_package_smoke.json")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8")) if evidence_path.is_file() else {}
    return {"status": "PASS" if smoke["exit_code"] == 0 and evidence.get("status") == "PASS" else "FAIL", "install": install, "smoke": smoke, "evidence": evidence}, logs


def _render_markdown(report: dict[str, Any]) -> str:
    gates = report.get("gate_results", [])
    operation_gates = [gate for gate in gates if gate.get("phase") == "E"]
    sections = [
        "# Chroma3D Sculpt Sprint 2 Final Validation Results", "",
        "## 1. Overall Result", "", f"**{report['overall_status']}**", "",
        "## 2. Release Recommendation", "", f"**{report['release_recommendation']}**", "",
        "## 3. Environment", "",
        f"- Repository: `{report['repository_root']}`",
        f"- Branch: `{report['branch']}`",
        f"- Baseline tag: `{report['baseline_tag']}`",
        f"- Blender: `{report['blender_version']}` at `{report['blender_executable']}`",
        f"- Python: `{report['python_version']}`",
        f"- Extension: `{report['extension_version']}`; analysis schema `{report['analysis_schema_version']}`; repair audit schema `{report['repair_audit_schema_version']}`.",
        f"- Total duration: `{report['total_duration_seconds']}` seconds.", "",
        "## 4. Static Safety Audit", "", f"- Status: **{report.get('static_audit', {}).get('status', 'NOT RUN')}**", "",
        "## 5. Source-Preservation Matrix", "", f"- `{json.dumps(report.get('source_preservation_matrix', {}), ensure_ascii=False)}`", "",
        "## 6. Workspace Isolation", "", f"- `{json.dumps(report.get('workspace_isolation_evidence', {}), ensure_ascii=False)}`", "",
        "## 7. Plan Read-Only Evidence", "", f"- `{json.dumps(report.get('plan_read_only_evidence', {}), ensure_ascii=False)}`", "",
        "## 8. Operation Isolation Matrix", "",
    ]
    sections.extend(f"- {gate['id']} {gate['name']}: **{gate['status']}** — `{json.dumps(gate.get('evidence', {}), ensure_ascii=False)}`" for gate in operation_gates)
    sections.extend([
        "", "## 9. Checkpoint and Recovery", "", f"- `{json.dumps(report.get('checkpoint_undo_evidence', {}), ensure_ascii=False)}`", "",
        "## 10. Accept and Rollback", "", f"- `{json.dumps(report.get('accept_rollback_evidence', {}), ensure_ascii=False)}`", "",
        "## 11. Repair Audit", "", f"- `{json.dumps(report.get('audit_validation', {}), ensure_ascii=False)}`", "",
        "## 12. Realistic Surface Stress Test", "", f"- `{json.dumps(report.get('realistic_stress_metrics', {}), ensure_ascii=False)}`", "",
        "## 13. Stale-State Rejection", "", f"- `{json.dumps(report.get('stale_state_evidence', {}), ensure_ascii=False)}`", "",
        "## 14. Registration and Installed Package", "", f"- `{json.dumps(report.get('installed_package_smoke', {}), ensure_ascii=False)}`", "",
        "## 15. Sprint 0/1/2 Regression", "",
    ])
    sections.extend(f"- {item['name']}: **{item['status']}** (exit `{item['exit_code']}`, `{item['duration_seconds']}`s)" for item in report.get("regression_results", []))
    sections.extend(["", "## 16. Defects Found and Fixed", ""])
    defects = report.get("defects", [])
    sections.extend(
        f"- {item.get('classification')}: {item.get('summary')} Production: `{item.get('production')}`; files: `{', '.join(item.get('files_changed', [])) or 'none'}`; regression: `{item.get('regression', '')}`."
        for item in defects
    )
    if not defects:
        sections.append("- None.")
    sections.extend(["", "## 17. Tests Not Run", ""])
    sections.extend(f"- {item}" for item in report.get("tests_not_run", []))
    if not report.get("tests_not_run"):
        sections.append("- None.")
    sections.extend(["", "## 18. Known Limitations", ""])
    sections.extend(f"- {item}" for item in report.get("known_limitations", []))
    sections.extend([
        "", "## 19. Safety Confirmation", "",
        f"- `{json.dumps(report.get('safety_confirmation', {}), ensure_ascii=False)}`", "",
        "## 20. Final Decision", "", f"**{report['final_decision']}**", "",
        "## 21. One Immediate Next Action", "",
        "Review the final Sprint 2 evidence and manually smoke-test the installed 0.3.0-alpha.1 repair panel before committing.", "",
    ])
    return "\n".join(sections)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path)
    args = parser.parse_args()
    blender = (args.blender or (DEFAULT_BLENDER if DEFAULT_BLENDER.is_file() else Path(""))).expanduser().resolve()
    if not blender.is_file():
        try:
            from scripts.find_blender import find_blender
            blender = Path(find_blender()).resolve()
        except Exception:
            print("Blender executable not found. Pass --blender.", file=sys.stderr)
            return 2

    for directory in (REPORTS_DIRECTORY, LOGS_DIRECTORY, ARTIFACTS_DIRECTORY, FINAL_DIRECTORY / "screenshots"):
        directory.mkdir(parents=True, exist_ok=True)
    if RESULTS_PATH.is_file():
        try:
            previous = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
            if previous.get("overall_status") == "FAIL":
                preserved = ARTIFACTS_DIRECTORY / "initial_failure_results.json"
                if not preserved.exists():
                    shutil.copy2(RESULTS_PATH, preserved)
        except (OSError, ValueError, TypeError):
            pass
    started_at = datetime.now(timezone.utc)
    timer = perf_counter()
    logs: list[str] = []
    inner, log = _run(
        "Sprint 2 independent Blender final validation",
        [str(blender), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(FINAL_DIRECTORY / "final_validation_runner.py")],
        timeout=1800,
    )
    logs.append(log)
    if RESULTS_PATH.is_file():
        report = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    else:
        report = {"schema_version": "1.0", "project": "Chroma3D Sculpt", "gate_results": [], "defects": [], "warnings": ["Blender runner did not generate evidence."]}

    commands = [
        ("Python compilation", [sys.executable, "-m", "compileall", "-q", "blender_addon", "scripts", "tests", "manual-tests"]),
        ("Combined Blender suite", [sys.executable, "scripts/run_blender_tests.py", "--blender", str(blender)]),
        ("Sprint 0 acceptance", [sys.executable, "manual-tests/run_acceptance_gates.py", "--blender", str(blender)]),
        ("Sprint 1 acceptance", [sys.executable, "manual-tests/sprint1/run_sprint1_acceptance.py", "--blender", str(blender)]),
        ("Sprint 1 final validation", [sys.executable, "manual-tests/sprint1-final/run_final_validation.py", "--blender", str(blender)]),
        ("Sprint 2 acceptance", [sys.executable, "manual-tests/sprint2/run_sprint2_acceptance.py", "--blender", str(blender)]),
        ("Package creation", [sys.executable, "scripts/package_extension.py"]),
        ("Repository package validator", [sys.executable, "scripts/validate_package.py"]),
        ("Blender-native package validator", [str(blender), "--background", "--factory-startup", "--command", "extension", "validate", str(PACKAGE_PATH)]),
        ("Git whitespace validation", ["git", "diff", "--check"]),
    ]
    regressions: list[dict[str, Any]] = [inner]
    for name, command in commands:
        record, command_log = _run(name, command)
        regressions.append(record)
        logs.append(command_log)
        print(f"[{record['status']}] {name}")

    package_audit = _security_and_package_audit()
    smoke, smoke_logs = _installed_package_smoke(blender) if package_audit["package"].get("exists") else ({"status": "NOT_RUN", "reason": "Package was not created."}, [])
    logs.extend(smoke_logs)

    report.update({
        "schema_version": "1.0",
        "project": "Chroma3D Sculpt",
        "extension_version": "0.3.0-alpha.1",
        "analysis_schema_version": "2.0",
        "repair_audit_schema_version": "1.0",
        "repository_root": str(REPOSITORY_ROOT),
        "branch": _git_value("branch", "--show-current"),
        "baseline_tag": "v0.2.0-alpha.1",
        "baseline_commit": _git_value("rev-list", "-n", "1", "v0.2.0-alpha.1"),
        "head_commit": _git_value("rev-parse", "HEAD"),
        "blender_executable": str(blender),
        "python_version": sys.version.split()[0],
        "start_time": started_at.isoformat(),
        "end_time": datetime.now(timezone.utc).isoformat(),
        "total_duration_seconds": round(perf_counter() - timer, 6),
        "regression_results": regressions,
        "package_metadata": package_audit["package"],
        "security_findings": package_audit,
        "installed_package_smoke": smoke,
        "generated_artifacts": [
            RESULTS_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
            LOG_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
            MARKDOWN_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
        ],
    })
    all_required_passed = (
        inner["exit_code"] == 0
        and all(item["exit_code"] == 0 for item in regressions[1:])
        and package_audit["status"] == "PASS"
        and smoke.get("status") == "PASS"
        and all(item.get("status") == "PASS" for item in report.get("gate_results", []))
    )
    report["overall_status"] = "PASS" if all_required_passed else "FAIL"
    report["release_recommendation"] = "READY TO COMMIT WITH LIMITATIONS" if all_required_passed else "NOT READY TO COMMIT"
    report["final_decision"] = "SPRINT 2 FINAL VALIDATION PASSED WITH LIMITATIONS" if all_required_passed else "SPRINT 2 FINAL VALIDATION FAILED"
    report.setdefault("known_limitations", [
        "Real Chroma3D statue UAT deferred.",
        "Session restart persistence not guaranteed.",
        "No remeshing.", "No large-hole reconstruction.", "No Boolean repair.",
        "No wall-thickness repair.", "No AI.", "No printability guarantee.",
    ])
    report.setdefault("tests_not_run", ["Manual installed-panel interaction and real Chroma3D statue UAT remain deferred."])
    RESULTS_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    MARKDOWN_PATH.write_text(_render_markdown(report), encoding="utf-8", newline="\n")
    LOG_PATH.write_text("\n\n".join(logs), encoding="utf-8", newline="\n")
    print(f"Final validation: {report['overall_status']}")
    print(f"Evidence: {RESULTS_PATH}")
    return 0 if all_required_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
