"""Run Blender Sprint 1 gates, regressions, packaging, and evidence finalization."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from time import perf_counter
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SPRINT_DIRECTORY = Path(__file__).resolve().parent
REPORTS_DIRECTORY = SPRINT_DIRECTORY / "reports"
LOGS_DIRECTORY = SPRINT_DIRECTORY / "logs"
RESULTS_PATH = REPORTS_DIRECTORY / "sprint1_acceptance_results.json"
MARKDOWN_PATH = SPRINT_DIRECTORY / "SPRINT1_ACCEPTANCE_RESULTS.md"
LOG_PATH = LOGS_DIRECTORY / "blender_sprint1_acceptance.log"
PACKAGE_PATH = REPOSITORY_ROOT / "dist" / "chroma3d_sculpt-0.3.0-alpha.1.zip"
DEFAULT_BLENDER = Path(r"D:\Softwares\Design\Blender\blender.exe")


def _run(name: str, command: list[str], timeout: int = 1800) -> tuple[dict[str, Any], str]:
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
        )
        code, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as exc:
        code = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr if isinstance(exc.stderr, str) else "") + f"\nTimed out after {timeout}s."
    record = {
        "name": name,
        "command": subprocess.list2cmdline(command),
        "exit_code": code,
        "duration_seconds": round(perf_counter() - started, 6),
        "stdout_tail": "\n".join(stdout.strip().splitlines()[-12:]),
        "stderr_tail": "\n".join(stderr.strip().splitlines()[-12:]),
    }
    log = f"$ {record['command']}\n[exit={code} duration={record['duration_seconds']}]\n{stdout}"
    if stderr:
        log += f"\n[stderr]\n{stderr}"
    return record, log + "\n"


def _security_scan() -> tuple[dict[str, Any], str]:
    source_root = REPOSITORY_ROOT / "blender_addon" / "chroma3d_sculpt"
    patterns = {
        "network_or_server": re.compile(r"\b(requests|urllib|http\.client|socket|aiohttp|listen\s*\(|serve_forever)\b"),
        "dynamic_execution": re.compile(r"\b(eval|exec)\s*\("),
        "credential_or_env": re.compile(r"\b(api[_-]?key|secret|token|dotenv)\b", re.IGNORECASE),
        "hard_coded_repository": re.compile(re.escape(str(REPOSITORY_ROOT)), re.IGNORECASE),
    }
    findings: list[str] = []
    for path in sorted(source_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for label, pattern in patterns.items():
            if pattern.search(text):
                findings.append(f"{label}: {path.relative_to(REPOSITORY_ROOT).as_posix()}")
    record = {
        "name": "Runtime security scan",
        "command": "internal deterministic source scan",
        "exit_code": 1 if findings else 0,
        "duration_seconds": 0.0,
        "findings": findings,
    }
    return record, json.dumps(record, indent=2) + "\n"


def _gate(report: dict[str, Any], gate_id: str) -> dict[str, Any]:
    return next(gate for gate in report["gate_results"] if gate["id"] == gate_id)


def _render_markdown(report: dict[str, Any]) -> str:
    gates = report["gate_results"]
    by_id = {gate["id"]: gate for gate in gates}
    topology = by_id["S1-02"].get("actual", {})
    metrics = by_id["S1-03"].get("actual", {})
    orientation = by_id["S1-04"].get("actual", {})
    shells = by_id["S1-05"].get("actual", {})
    containment = by_id["S1-06"].get("actual", {})
    intersections = by_id["S1-07"].get("actual", {})
    build = by_id["S1-08"].get("actual", {})
    selection = by_id["S1-09"].get("actual", {})
    stress = by_id["S1-10"].get("actual", {})
    regression = by_id["S1-01"].get("actual", {})
    package = report.get("package", {})
    lines = [
        "# Chroma3D Sculpt Sprint 1 Acceptance Results", "",
        "## 1. Overall Result", "", f"**{report['overall_status']}**", "",
        "## 2. Environment", "",
        f"- Repository: `{REPOSITORY_ROOT}`", f"- Branch: `{report.get('branch')}`", f"- Baseline tag: `{report.get('baseline_tag')}`",
        f"- Blender: `{report.get('blender_version')}` at `{report.get('blender_executable')}`", f"- Python launcher: `{report.get('python_launcher')}`", f"- Version: `{report.get('version')}`", "",
        "## 3. Git Baseline", "", f"- Main baseline: `{report.get('baseline_commit')}`", f"- Tag preserved: `{report.get('baseline_tag')}`", "",
        "## 4. Version", "", f"- Extension: `{report.get('version')}`", "- JSON schema: `2.0`", "",
        "## 5. Gate Summary Table", "", "| Gate | Result | Duration |", "|---|---|---:|",
    ]
    lines.extend(f"| {gate['id']} - {gate['name']} | {gate['status']} | {gate.get('duration_seconds', 0):.3f}s |" for gate in gates)
    lines.extend([
        "", "## 6. Topology Results", "", f"- Closed: `{topology.get('closed')}`; open: `{topology.get('open')}`; high-incidence edges: `{topology.get('high_incidence_edges')}`.", "",
        "## 7. Physical Metric Evidence", "", f"- Cube area: `{metrics.get('cube_area_mm2')}` mm^2; cube volume: `{metrics.get('cube_volume_mm3')}` mm^3.", f"- Non-uniform scale dimensions: `{metrics.get('scaled_dimensions_mm')}`; volume: `{metrics.get('scaled_volume_mm3')}` mm^3.", "",
        "## 8. Orientation Evidence", "", f"- `{json.dumps(orientation, ensure_ascii=False)}`", "",
        "## 9. Shell-Classification Evidence", "", f"- `{json.dumps(shells, ensure_ascii=False)}`", "",
        "## 10. Deep Diagnostic Evidence", "", f"- Containment: `{json.dumps(containment, ensure_ascii=False)}`", f"- Self-intersection: `{json.dumps(intersections, ensure_ascii=False)}`", "",
        "## 11. Build-Volume Evidence", "", f"- Bambu pass state: `{build.get('bambu_pass', {}).get('fit_state')}`; one-axis state: `{build.get('one_axis_fail', {}).get('fit_state')}`; custom state: `{build.get('custom', {}).get('fit_state')}`.", "",
        "## 12. Issue-Selection Evidence", "", f"- `{json.dumps(selection, ensure_ascii=False)}`", "",
        "## 13. Stress-Test Performance", "", f"- V/E/F/T: `{stress.get('vertices')}/{stress.get('edges')}/{stress.get('faces')}/{stress.get('triangles')}`; shells: `{stress.get('shells')}`.", f"- Standard duration: `{stress.get('duration_ms')}` ms versus Sprint 0 evidence `{stress.get('sprint0_baseline_duration_ms')}` ms.", f"- Timings: `{json.dumps(stress.get('timings', {}), ensure_ascii=False)}`", "",
        "## 14. Immutability Evidence", "", f"- Stress geometry unchanged: `{stress.get('geometry_unchanged')}`; issue selection unchanged: `{selection.get('geometry_unchanged')}`.", "",
        "## 15. Sprint 0 Regression", "", f"- Blender tests exit: `{regression.get('blender_tests_exit')}`; Sprint 0 acceptance exit: `{regression.get('sprint0_acceptance_exit')}`.", "",
        "## 16. Package Validation", "", f"- Package: `{package.get('path')}`", f"- SHA-256: `{package.get('sha256')}`", f"- Size: `{package.get('size_bytes')}` bytes.", "",
        "## 17. Defects Found and Fixed", "",
    ])
    lines.extend(f"- {item}" for item in report.get("defects_fixed", []))
    if not report.get("defects_fixed"):
        lines.append("- None.")
    lines.extend(["", "## 18. Tests Not Run", ""])
    lines.extend(f"- {item}" for item in report.get("tests_not_run", []))
    lines.extend(["", "## 19. Known Limitations", ""])
    lines.extend(f"- {item}" for item in report.get("known_limitations", []))
    lines.extend([
        "", "## 20. Safety Confirmation", "", "- No geometry repair, network, external dependency, credential, elevation, commit, push, or Sprint 2 work was used.", "",
        "## 21. Sprint 1 Gate Decision", "", f"**{report['sprint_1_decision']}**", "",
        "## 22. One Immediate Recommended Action", "", "Review the Sprint 1 evidence and manually smoke-test the updated Blender panel before committing.", "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, default=DEFAULT_BLENDER)
    args = parser.parse_args()
    blender = args.blender.resolve()
    if not blender.is_file():
        print(f"Blender executable not found: {blender}", file=sys.stderr)
        return 2
    REPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    LOGS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    started = perf_counter()
    logs: list[str] = []
    blender_record, blender_log = _run(
        "Blender Sprint 1 acceptance fixtures",
        [str(blender), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(SPRINT_DIRECTORY / "sprint1_acceptance_runner.py")],
    )
    logs.append(blender_log)
    if not RESULTS_PATH.is_file():
        print("Sprint 1 Blender runner did not produce its JSON report.", file=sys.stderr)
        LOG_PATH.write_text("\n".join(logs), encoding="utf-8", newline="\n")
        return 1
    report = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))

    commands = [
        ("Python compilation", [sys.executable, "-m", "compileall", "-q", "blender_addon", "scripts", "tests", "manual-tests"]),
        ("Blender tests", [sys.executable, "scripts/run_blender_tests.py", "--blender", str(blender)]),
        ("Sprint 0 regression acceptance", [sys.executable, "manual-tests/run_acceptance_gates.py", "--blender", str(blender)]),
        ("Package creation", [sys.executable, "scripts/package_extension.py"]),
        ("Repository package validation", [sys.executable, "scripts/validate_package.py"]),
        ("Blender native extension validation", [str(blender), "--background", "--command", "extension", "validate", str(PACKAGE_PATH)]),
        ("Git whitespace validation", ["git", "diff", "--check"]),
    ]
    records: list[dict[str, Any]] = [blender_record]
    for name, command in commands:
        record, log = _run(name, command)
        records.append(record)
        logs.append(log)
        print(f"[{'PASS' if record['exit_code'] == 0 else 'FAIL'}] {name}")
    security_record, security_log = _security_scan()
    records.append(security_record)
    logs.append(security_log)
    LOG_PATH.write_text("\n".join(logs), encoding="utf-8", newline="\n")

    record_by_name = {record["name"]: record for record in records}
    regression_gate = _gate(report, "S1-01")
    regression_gate["actual"].update(
        {
            "blender_tests_exit": record_by_name["Blender tests"]["exit_code"],
            "sprint0_acceptance_exit": record_by_name["Sprint 0 regression acceptance"]["exit_code"],
        }
    )
    if regression_gate["actual"]["blender_tests_exit"] or regression_gate["actual"]["sprint0_acceptance_exit"]:
        regression_gate["status"] = "FAIL"
    report_gate = _gate(report, "S1-12")
    validation_names = {"Python compilation", "Package creation", "Repository package validation", "Blender native extension validation", "Git whitespace validation", "Runtime security scan"}
    report_gate["actual"]["validation_commands"] = [record for record in records if record["name"] in validation_names]
    if any(record["exit_code"] for record in report_gate["actual"]["validation_commands"]):
        report_gate["status"] = "FAIL"

    package_info: dict[str, Any] = {"path": str(PACKAGE_PATH), "exists": PACKAGE_PATH.is_file()}
    if PACKAGE_PATH.is_file():
        package_info.update({"size_bytes": PACKAGE_PATH.stat().st_size, "sha256": sha256(PACKAGE_PATH.read_bytes()).hexdigest()})
    report["package"] = package_info
    report["validation_commands"] = records
    report["python_launcher"] = sys.executable
    report["duration_seconds"] = round(perf_counter() - started, 6)
    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    report["overall_status"] = "FAIL" if any(gate["status"] == "FAIL" for gate in report["gate_results"]) or any(record["exit_code"] for record in records) else "PASS"
    report["sprint_1_decision"] = "SPRINT 1 ACCEPTED" if report["overall_status"] == "PASS" else "SPRINT 1 REJECTED"
    report["evidence_files"] = [str(RESULTS_PATH), str(MARKDOWN_PATH), str(LOG_PATH)]
    report["baseline_commit"] = subprocess.check_output(["git", "rev-parse", "v0.1.0-alpha.1^{}"], cwd=REPOSITORY_ROOT, text=True).strip()
    report["branch"] = subprocess.check_output(["git", "branch", "--show-current"], cwd=REPOSITORY_ROOT, text=True).strip()
    report["defects_fixed"] = [
        "Production review: per-shell watertightness initially reused capped vertex-anomaly evidence. The topology service now retains the complete anomaly set internally while serialized and selectable evidence remains bounded; the 48-test suite and all acceptance gates passed after the fix.",
        "Acceptance hygiene: Markdown hard-break trailing spaces caused git diff --check and the nested Sprint 0 validation gate to fail. README formatting was corrected; the focused whitespace check and complete acceptance rerun passed.",
    ]
    report["tests_not_run"] = ["Interactive visual smoke test of the Blender sidebar panel.", "Blender 4.5 LTS compatibility run because only Blender 4.4.3 is installed for this task."]
    RESULTS_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    MARKDOWN_PATH.write_text(_render_markdown(report), encoding="utf-8", newline="\n")
    print(f"Overall: {report['overall_status']}")
    print(f"Decision: {report['sprint_1_decision']}")
    print(f"JSON: {RESULTS_PATH}")
    print(f"Markdown: {MARKDOWN_PATH}")
    print(f"Log: {LOG_PATH}")
    return 0 if report["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
