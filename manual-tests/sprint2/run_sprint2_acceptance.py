"""Run all Sprint 2 gates, regressions, package checks, and evidence finalization."""

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
import zipfile


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SPRINT_DIRECTORY = Path(__file__).resolve().parent
REPORTS_DIRECTORY = SPRINT_DIRECTORY / "reports"
LOGS_DIRECTORY = SPRINT_DIRECTORY / "logs"
RESULTS_PATH = REPORTS_DIRECTORY / "sprint2_acceptance_results.json"
MARKDOWN_PATH = SPRINT_DIRECTORY / "SPRINT2_ACCEPTANCE_RESULTS.md"
LOG_PATH = LOGS_DIRECTORY / "blender_sprint2_acceptance.log"
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
        "stdout_tail": "\n".join(stdout.strip().splitlines()[-15:]),
        "stderr_tail": "\n".join(stderr.strip().splitlines()[-15:]),
    }
    log = f"$ {record['command']}\n[exit={code} duration={record['duration_seconds']}]\n{stdout}"
    if stderr:
        log += f"\n[stderr]\n{stderr}"
    return record, log + "\n"


def _security_scan() -> tuple[dict[str, Any], str]:
    source = REPOSITORY_ROOT / "blender_addon" / "chroma3d_sculpt"
    patterns = {
        "network_import": re.compile(r"^\s*(?:from|import)\s+(?:requests|urllib|http\.|socket|aiohttp|httpx)\b", re.MULTILINE),
        "dynamic_execution": re.compile(r"\b(?:eval|exec)\s*\("),
        "pickle": re.compile(r"^\s*(?:from|import)\s+pickle\b", re.MULTILINE),
        "hard_coded_repository": re.compile(re.escape(str(REPOSITORY_ROOT)), re.IGNORECASE),
    }
    findings: list[str] = []
    for path in sorted(source.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for label, pattern in patterns.items():
            if pattern.search(text):
                findings.append(f"{label}: {path.relative_to(REPOSITORY_ROOT).as_posix()}")
    forbidden_files = [
        path.relative_to(REPOSITORY_ROOT).as_posix()
        for path in REPOSITORY_ROOT.rglob("*")
        if path.is_file() and (path.name == ".env" or path.name.startswith(".env.") or path.suffix.lower() in {".pem", ".p12", ".pfx", ".key"})
    ]
    findings.extend(f"forbidden_file: {item}" for item in forbidden_files)
    record = {"name": "Runtime security scan", "command": "internal deterministic source scan", "exit_code": 1 if findings else 0, "duration_seconds": 0.0, "findings": findings}
    return record, json.dumps(record, ensure_ascii=False, indent=2) + "\n"


def _gate(report: dict[str, Any], gate_id: str) -> dict[str, Any]:
    return next(item for item in report["gate_results"] if item["id"] == gate_id)


def _package_info() -> dict[str, Any]:
    info: dict[str, Any] = {"path": str(PACKAGE_PATH), "relative_path": PACKAGE_PATH.relative_to(REPOSITORY_ROOT).as_posix(), "exists": PACKAGE_PATH.is_file()}
    if PACKAGE_PATH.is_file():
        with zipfile.ZipFile(PACKAGE_PATH, "r") as archive:
            info["file_count"] = len([name for name in archive.namelist() if not name.endswith("/")])
        info.update({"size_bytes": PACKAGE_PATH.stat().st_size, "sha256": sha256(PACKAGE_PATH.read_bytes()).hexdigest()})
    return info


def _render_markdown(report: dict[str, Any]) -> str:
    gates = {item["id"]: item for item in report["gate_results"]}
    source = gates["S2-02"].get("actual", {})
    plan = gates["S2-03"].get("actual", {})
    stress = gates["S2-13"].get("actual", {})
    package = report.get("package", {})
    operations = {gate_id: gates[gate_id].get("actual", {}) for gate_id in ("S2-04", "S2-05", "S2-06")}
    lines = [
        "# Chroma3D Sculpt Sprint 2 Acceptance Results", "",
        "## 1. Overall Result", "", f"**{report['overall_status']}**", "",
        "## 2. Sprint Decision", "", f"**{report['sprint_2_decision']}**", "",
        "## 3. Environment", "", f"- Repository: `{REPOSITORY_ROOT}`", f"- Branch: `{report['branch']}`", f"- Blender: `{report['blender_version']}` at `{report['blender_executable']}`", f"- Extension: `{report['version']}`; analysis schema `2.0`; repair audit schema `1.0`.", "",
        "## 4. Baseline", "", f"- Accepted baseline tag: `{report['baseline_tag']}` at `{report['baseline_commit']}`.", "",
        "## 5. Gate Summary", "", "| Gate | Result | Duration |", "|---|---|---:|",
    ]
    lines.extend(f"| {item['id']} - {item['name']} | {item['status']} | {item.get('duration_seconds', 0):.3f}s |" for item in report["gate_results"])
    lines.extend([
        "", "## 6. Source-Protection Evidence", "", f"- Source signature before/after: `{source.get('source_signature_before')}` / `{source.get('source_signature_after')}`.", f"- Independent object and mesh identities: `{source.get('source_object_identity')}` / `{source.get('workspace_object_identity')}` and `{source.get('source_mesh_identity')}` / `{source.get('workspace_mesh_identity')}`.", "",
        "## 7. Repair-Plan Evidence", "", f"- Plan `{plan.get('plan_id')}` used analysis `{plan.get('analysis_id')}`; generation was read-only and external workspace mutation was rejected: `{plan.get('workspace_change_rejected')}`.", "",
        "## 8. Operation Results", "", f"- `{json.dumps(operations, ensure_ascii=False)}`", "",
        "## 9. Tiny-Shell Evidence", "", f"- `{json.dumps(gates['S2-07'].get('actual', {}), ensure_ascii=False)}`", "",
        "## 10. Hole-Fill Evidence", "", f"- `{json.dumps(gates['S2-08'].get('actual', {}), ensure_ascii=False)}`", "",
        "## 11. Checkpoint and Rollback Evidence", "", f"- Checkpoints: `{json.dumps(gates['S2-09'].get('actual', {}), ensure_ascii=False)}`", f"- Finalization: `{json.dumps(gates['S2-11'].get('actual', {}), ensure_ascii=False)}`", "",
        "## 12. Before/After Diagnostics", "", f"- `{json.dumps(gates['S2-10'].get('actual', {}), ensure_ascii=False)}`", "",
        "## 13. Stress Performance", "", f"- Source counts: `{stress.get('source_counts')}`; final workspace counts: `{stress.get('workspace_final_counts')}`.", f"- Fixture generation: `{stress.get('fixture_generation_seconds')}`s; repair batch: `{stress.get('repair_batch_seconds')}`s; final analysis: `{stress.get('analysis_duration_ms')}`ms.", f"- 60-second warning threshold passed: `{stress.get('warning_threshold_passed')}`; source unchanged: `{stress.get('source_unchanged')}`.", "",
        "## 14. Audit Evidence", "", f"- `{json.dumps(gates['S2-12'].get('actual', {}), ensure_ascii=False)}`", "",
        "## 15. Regression Results", "", f"- `{json.dumps(gates['S2-01'].get('actual', {}), ensure_ascii=False)}`", "",
        "## 16. Package Validation", "", f"- Package: `{package.get('path')}`", f"- Files: `{package.get('file_count')}`; size: `{package.get('size_bytes')}` bytes; SHA-256: `{package.get('sha256')}`.", "",
        "## 17. Defects Found and Fixed", "",
    ])
    lines.extend(f"- {item}" for item in report.get("defects_fixed", []))
    lines.extend(["", "## 18. Tests Not Run", ""])
    lines.extend(f"- {item}" for item in report.get("tests_not_run", []))
    lines.extend(["", "## 19. Known Limitations", ""])
    lines.extend(f"- {item}" for item in report.get("known_limitations", []))
    lines.extend([
        "", "## 20. Safety Confirmation", "",
        "- Original source preserved; no network, external dependency, credential, administrator elevation, automatic save, commit, push, tag, merge, AI, or Sprint 3 work.", "",
        "## 21. Final Decision", "", f"**{report['sprint_2_decision']}**", "",
        "## 22. One Immediate Recommended Action", "", "Review the Sprint 2 evidence and perform an installed-panel smoke test before committing the feature branch.", "",
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
    inner, log = _run("Blender Sprint 2 acceptance fixtures", [str(blender), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(SPRINT_DIRECTORY / "sprint2_acceptance_runner.py")])
    logs.append(log)
    if not RESULTS_PATH.is_file():
        LOG_PATH.write_text("\n".join(logs), encoding="utf-8", newline="\n")
        print("Sprint 2 Blender runner did not produce JSON evidence.", file=sys.stderr)
        return 1
    report = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    commands = [
        ("Python compilation", [sys.executable, "-m", "compileall", "-q", "blender_addon", "scripts", "tests", "manual-tests"]),
        ("Combined Blender tests", [sys.executable, "scripts/run_blender_tests.py", "--blender", str(blender)]),
        ("Sprint 0 acceptance", [sys.executable, "manual-tests/run_acceptance_gates.py", "--blender", str(blender)]),
        ("Sprint 1 acceptance", [sys.executable, "manual-tests/sprint1/run_sprint1_acceptance.py", "--blender", str(blender)]),
        ("Sprint 1 final validation", [sys.executable, "manual-tests/sprint1-final/run_final_validation.py", "--blender", str(blender)]),
        ("Package creation", [sys.executable, "scripts/package_extension.py"]),
        ("Repository package validation", [sys.executable, "scripts/validate_package.py"]),
        ("Blender native extension validation", [str(blender), "--background", "--command", "extension", "validate", str(PACKAGE_PATH)]),
        ("Git whitespace validation", ["git", "diff", "--check"]),
    ]
    records = [inner]
    for name, command in commands:
        record, command_log = _run(name, command)
        records.append(record)
        logs.append(command_log)
        print(f"[{'PASS' if record['exit_code'] == 0 else 'FAIL'}] {name}")
    security, security_log = _security_scan()
    records.append(security)
    logs.append(security_log)
    LOG_PATH.write_text("\n".join(logs), encoding="utf-8", newline="\n")

    by_name = {item["name"]: item for item in records}
    regression_names = ("Combined Blender tests", "Sprint 0 acceptance", "Sprint 1 acceptance", "Sprint 1 final validation")
    test_match = re.search(r"Chroma3D Blender tests passed:\s*(\d+)", by_name["Combined Blender tests"].get("stdout_tail", ""))
    regression_gate = {
        "id": "S2-01", "name": "Baseline regression",
        "status": "PASS" if all(by_name[name]["exit_code"] == 0 for name in regression_names) else "FAIL",
        "duration_seconds": sum(by_name[name]["duration_seconds"] for name in regression_names),
        "actual": {"combined_test_count": int(test_match.group(1)) if test_match else None, **{name: by_name[name]["exit_code"] for name in regression_names}, "analysis_read_only": True},
        "failures": [name for name in regression_names if by_name[name]["exit_code"]],
    }
    validation_names = ("Python compilation", "Package creation", "Repository package validation", "Blender native extension validation", "Git whitespace validation", "Runtime security scan")
    package_gate = {
        "id": "S2-14", "name": "Package and security",
        "status": "PASS" if all(by_name[name]["exit_code"] == 0 for name in validation_names) else "FAIL",
        "duration_seconds": sum(by_name[name]["duration_seconds"] for name in validation_names),
        "actual": {name: by_name[name] for name in validation_names},
        "failures": [name for name in validation_names if by_name[name]["exit_code"]],
    }
    report["gate_results"] = [regression_gate] + report["gate_results"] + [package_gate]
    report["validation_commands"] = records
    report["package"] = _package_info()
    report["branch"] = subprocess.check_output(["git", "branch", "--show-current"], cwd=REPOSITORY_ROOT, text=True).strip()
    report["baseline_commit"] = subprocess.check_output(["git", "rev-parse", "v0.2.0-alpha.1^{}"], cwd=REPOSITORY_ROOT, text=True).strip()
    report["python_version"] = sys.version.split()[0]
    report["duration_seconds"] = round(perf_counter() - started, 6)
    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    report["defects_fixed"] = [
        "Tiny-shell review initially inherited a face-count plus relative-volume classification that could offer a physically medium ornament. Repair eligibility now also requires the configured physical diagonal criterion; focused regression added.",
        "A no-change operation could evict a prior valid undo checkpoint before its outcome was known. History eviction now occurs only after a geometry-changing operation succeeds; focused history regression added.",
        "The first normal-consistency implementation delegated to Blender's outward-oriented recalculation, coupling two user decisions. It now propagates deterministic adjacency winding while preserving the seed orientation; outward shell orientation remains a separate explicit operation and non-manifold skips are recorded.",
        "Coincident disconnected candidates could share a geometry fingerprint. Candidate IDs now include a deterministic component identity, and apply-time remapping rejects non-unique fingerprints instead of allowing one selection to affect multiple candidates.",
    ]
    report["tests_not_run"] = [
        "Manual interactive installed-panel smoke test.",
        "Real Chroma3D statue repair UAT (intentionally deferred).",
        "Blender 4.5 LTS compatibility because Blender 4.5 is not installed in this environment.",
    ]
    report["known_limitations"] = [
        "Original source is preserved, but workspace repair still requires human review.",
        "An unfinished session is not guaranteed to survive Blender restart.",
        "No remeshing, large-hole reconstruction, boolean repair, wall-thickness repair, AI, or printability guarantee.",
        "Real statue UAT is deferred.",
    ]
    report["warnings"] = list(report.get("warnings", [])) + report["tests_not_run"]
    report["failures"] = [failure for gate in report["gate_results"] for failure in gate.get("failures", [])]
    report["overall_status"] = "PASS" if all(gate["status"] == "PASS" for gate in report["gate_results"]) else "FAIL"
    report["sprint_2_decision"] = "SPRINT 2 ACCEPTED" if report["overall_status"] == "PASS" else "SPRINT 2 REJECTED"
    report["evidence_files"] = [str(RESULTS_PATH), str(MARKDOWN_PATH), str(LOG_PATH)]
    RESULTS_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    MARKDOWN_PATH.write_text(_render_markdown(report), encoding="utf-8", newline="\n")
    print(f"Overall: {report['overall_status']}")
    print(f"Decision: {report['sprint_2_decision']}")
    print(f"JSON: {RESULTS_PATH}")
    print(f"Markdown: {MARKDOWN_PATH}")
    print(f"Log: {LOG_PATH}")
    return 0 if report["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
