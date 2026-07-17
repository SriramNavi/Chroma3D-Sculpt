"""Launch Blender Sprint 0 gates, then finalize package and evidence validation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIRECTORY = REPOSITORY_ROOT / "scripts"
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from find_blender import BlenderDiscovery, discover_blender  # noqa: E402


DEFAULT_BLENDER = Path(r"D:\Softwares\Design\Blender\blender.exe")
MANUAL_TESTS = REPOSITORY_ROOT / "manual-tests"
LOGS_DIRECTORY = MANUAL_TESTS / "logs"
REPORTS_DIRECTORY = MANUAL_TESTS / "reports"
BLENDER_LOG_PATH = LOGS_DIRECTORY / "blender_acceptance.log"
VALIDATION_LOG_PATH = LOGS_DIRECTORY / "validation_commands.log"
RESULTS_PATH = REPORTS_DIRECTORY / "sprint0_regression_on_sprint1.json"
MARKDOWN_PATH = REPORTS_DIRECTORY / "sprint0_regression_on_sprint1.md"
PACKAGE_PATH = REPOSITORY_ROOT / "dist" / "chroma3d_sculpt-0.2.0-alpha.1.zip"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except (OSError, ValueError):
        return str(path)


def _command_text(arguments: list[str]) -> str:
    return subprocess.list2cmdline(arguments)


def _tail(value: str, line_count: int = 12) -> str:
    lines = value.strip().splitlines()
    return "\n".join(lines[-line_count:])


def _run_command(name: str, arguments: list[str], *, timeout: int = 1800) -> tuple[dict[str, Any], str]:
    started = perf_counter()
    try:
        completed = subprocess.run(
            arguments,
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        return_code = 124
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", "replace")
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", "replace")
        stderr += f"\nTimed out after {timeout} seconds."
    except OSError as exc:
        return_code = 127
        stdout = ""
        stderr = f"{type(exc).__name__}: {exc}"

    command = _command_text(arguments)
    duration = round(perf_counter() - started, 6)
    record = {
        "name": name,
        "command": command,
        "exit_code": return_code,
        "duration_seconds": duration,
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
    }
    full_log = f"$ {command}\n[exit_code={return_code} duration_seconds={duration}]\n{stdout}"
    if stderr:
        full_log += f"\n[stderr]\n{stderr}"
    full_log += "\n"
    return record, full_log


def _discover(explicit: Path | None) -> BlenderDiscovery | None:
    if explicit is not None:
        if not explicit.expanduser().is_file():
            return None
        return discover_blender(explicit)
    if DEFAULT_BLENDER.is_file():
        return discover_blender(DEFAULT_BLENDER)
    return discover_blender()


def _fallback_report(discovery: BlenderDiscovery, started_at: datetime) -> dict[str, Any]:
    gate_names = (
        ("GATE-01", "Default cube analysis"),
        ("GATE-02", "Broken/open cube warning"),
        ("GATE-03", "Unapplied scale warning"),
        ("GATE-04", "JSON export"),
        ("GATE-05", "Realistic high-density statue-like mesh"),
        ("GATE-06", "No unintended mesh modification"),
        ("GATE-07", "Blender stability"),
        ("GATE-08", "Registration lifecycle"),
    )
    gates = []
    for gate_id, name in gate_names:
        status = "FAIL" if gate_id == "GATE-07" else "SKIPPED"
        gates.append(
            {
                "id": gate_id,
                "name": name,
                "status": status,
                "duration_seconds": 0.0,
                "expected": {},
                "actual": {},
                "evidence_files": [_relative(BLENDER_LOG_PATH)],
                "notes": ["Blender did not produce the machine-readable gate report."],
            }
        )
    return {
        "schema_version": "1.0",
        "project": "Chroma3D Sculpt",
        "extension_version": "0.2.0-alpha.1",
        "repository_root": str(REPOSITORY_ROOT),
        "blender_executable": str(discovery.executable),
        "blender_version": discovery.version,
        "python_launcher": sys.executable,
        "test_target": "Repository source registered explicitly under Blender --factory-startup",
        "started_at": started_at.isoformat(),
        "completed_at": _utc_now().isoformat(),
        "duration_seconds": 0.0,
        "overall_status": "FAIL",
        "gates": gates,
        "failures": [],
        "warnings": [],
        "defects": [],
        "generated_artifacts": [_relative(BLENDER_LOG_PATH)],
        "tests_not_run": [],
        "safety_confirmation": {},
    }


def _finalize_stability(report: dict[str, Any], blender_record: dict[str, Any], blender_log: str) -> None:
    fatal_tokens = (
        "EXCEPTION_ACCESS_VIOLATION",
        "Fatal Python error",
        "Segmentation fault",
        "Writing: C:\\Users\\Public\\Documents\\Blender\\blender.crash.txt",
    )
    fatal_hits = [token for token in fatal_tokens if token.lower() in blender_log.lower()]
    other_gate_failures = any(
        gate["status"] == "FAIL" and gate["id"] != "GATE-07"
        for gate in report.get("gates", [])
    )
    normal_for_gate_result = blender_record["exit_code"] == 0 or (
        blender_record["exit_code"] == 1 and other_gate_failures and not fatal_hits
    )
    for gate in report.get("gates", []):
        if gate["id"] != "GATE-07":
            continue
        gate["actual"].update(
            {
                "process_exit_code": blender_record["exit_code"],
                "process_duration_seconds": blender_record["duration_seconds"],
                "fatal_signatures": fatal_hits,
                "normal_exit_or_gate_failure_exit": normal_for_gate_result,
                "log_captured": _relative(BLENDER_LOG_PATH),
            }
        )
        gate["evidence_files"] = sorted(set(gate.get("evidence_files", []) + [_relative(BLENDER_LOG_PATH)]))
        if fatal_hits or not normal_for_gate_result:
            gate["status"] = "FAIL"
            gate["notes"].append("Blender did not terminate as a normal pass or genuine gate-failure exit.")
        break


def _run_windows_validations(discovery: BlenderDiscovery) -> tuple[dict[str, Any], str]:
    started = perf_counter()
    commands = (
        (
            "Python syntax validation",
            [
                sys.executable,
                "-m",
                "compileall",
                "-q",
                "blender_addon",
                "scripts",
                "tests",
                "manual-tests",
            ],
        ),
        (
            "Existing Blender background tests",
            [
                sys.executable,
                str(SCRIPTS_DIRECTORY / "run_blender_tests.py"),
                "--blender",
                str(discovery.executable),
            ],
        ),
        ("Package creation", [sys.executable, str(SCRIPTS_DIRECTORY / "package_extension.py")]),
        ("Repository package validator", [sys.executable, str(SCRIPTS_DIRECTORY / "validate_package.py")]),
        (
            "Blender native extension validator",
            [
                str(discovery.executable),
                "--background",
                "--command",
                "extension",
                "validate",
                str(PACKAGE_PATH),
            ],
        ),
        ("Git diff whitespace check", ["git", "diff", "--check"]),
        ("Git status", ["git", "status", "--short", "--branch"]),
    )
    records: list[dict[str, Any]] = []
    logs: list[str] = []
    for name, arguments in commands:
        record, output = _run_command(name, arguments)
        records.append(record)
        logs.append(output)
        print(f"[{'PASS' if record['exit_code'] == 0 else 'FAIL'}] {name} ({record['duration_seconds']:.3f}s)")
    package_valid = PACKAGE_PATH.is_file() and PACKAGE_PATH.stat().st_size > 0
    status = "PASS" if all(record["exit_code"] == 0 for record in records) and package_valid else "FAIL"
    gate = {
        "id": "GATE-09",
        "name": "Package and validation",
        "status": status,
        "duration_seconds": round(perf_counter() - started, 6),
        "expected": {
            "compileall": 0,
            "existing_blender_tests": 0,
            "package_creation": 0,
            "repository_validator": 0,
            "blender_native_validator": 0,
            "git_checks": 0,
        },
        "actual": {
            "commands": records,
            "package_path": _relative(PACKAGE_PATH),
            "package_exists": PACKAGE_PATH.is_file(),
            "package_size_bytes": PACKAGE_PATH.stat().st_size if PACKAGE_PATH.is_file() else 0,
        },
        "evidence_files": [_relative(VALIDATION_LOG_PATH)] + ([_relative(PACKAGE_PATH)] if PACKAGE_PATH.is_file() else []),
        "notes": [] if status == "PASS" else ["One or more required validation commands failed; inspect the validation log."],
    }
    return gate, "\n".join(logs)


def _key_evidence(gate: dict[str, Any]) -> str:
    actual = gate.get("actual", {})
    gate_id = gate["id"]
    if gate_id == "GATE-01":
        geometry = actual.get("geometry", {})
        return f"V/E/F/T={geometry.get('vertex_count')}/{geometry.get('edge_count')}/{geometry.get('polygon_count')}/{geometry.get('triangle_count')}"
    if gate_id == "GATE-02":
        return f"Boundary edges={actual.get('topology', {}).get('boundary_edges')}"
    if gate_id == "GATE-03":
        transforms = actual.get("transforms", {})
        return f"Scale applied={transforms.get('scale_applied')}; scale={transforms.get('scale')}"
    if gate_id == "GATE-04":
        return f"Valid JSON={actual.get('valid_json')}; {actual.get('output_file', '')}"
    if gate_id == "GATE-05":
        geometry = actual.get("geometry", {})
        return f"{geometry.get('vertex_count', 0):,} vertices; analysis {actual.get('duration_ms', 0):.3f} ms"
    if gate_id == "GATE-06":
        return f"{actual.get('meshes_compared', 0)} signatures; match={actual.get('all_signatures_match')}"
    if gate_id == "GATE-07":
        return f"Exit={actual.get('process_exit_code')}; fatal signatures={len(actual.get('fatal_signatures', []))}"
    if gate_id == "GATE-08":
        return f"Final classes present={any(actual.get('after_final_unregister', {}).values()) if actual.get('after_final_unregister') else 'unknown'}"
    if gate_id == "GATE-09":
        commands = actual.get("commands", [])
        return f"{sum(item.get('exit_code') == 0 for item in commands)}/{len(commands)} commands passed"
    return "See detailed evidence"


def _markdown_actual(gate: dict[str, Any]) -> dict[str, Any]:
    actual = gate.get("actual", {})
    gate_id = gate["id"]
    if gate_id in {"GATE-01", "GATE-02", "GATE-03", "GATE-05"}:
        return {
            key: actual.get(key)
            for key in ("severity", "duration_ms", "geometry", "transforms", "topology", "warnings", "errors", "immutability_differences")
            if key in actual
        }
    if gate_id == "GATE-06":
        return {
            "meshes_compared": actual.get("meshes_compared"),
            "all_signatures_match": actual.get("all_signatures_match"),
            "records": [
                {
                    "mesh": item.get("mesh"),
                    "matched": item.get("matched"),
                    "differences": item.get("differences"),
                }
                for item in actual.get("records", [])
            ],
        }
    if gate_id == "GATE-09":
        return {
            "package_path": actual.get("package_path"),
            "package_exists": actual.get("package_exists"),
            "package_size_bytes": actual.get("package_size_bytes"),
            "commands": [
                {
                    "name": item.get("name"),
                    "command": item.get("command"),
                    "exit_code": item.get("exit_code"),
                    "duration_seconds": item.get("duration_seconds"),
                }
                for item in actual.get("commands", [])
            ],
        }
    return actual


def _render_markdown(report: dict[str, Any]) -> str:
    gates = report.get("gates", [])
    gate_by_id = {gate["id"]: gate for gate in gates}
    environment_rows = (
        ("Repository root", report.get("repository_root", "Unknown")),
        ("Blender executable", report.get("blender_executable", "Unknown")),
        ("Blender version", report.get("blender_version", "Unknown")),
        ("Python launcher", report.get("python_launcher", "Unknown")),
        ("Extension version", report.get("extension_version", "Unknown")),
        ("Timestamp", report.get("completed_at", "Unknown")),
        ("Total duration", f"{report.get('duration_seconds', 0):.3f} seconds"),
        ("Test target", report.get("test_target", "Unknown")),
    )
    lines = [
        "# Chroma3D Sculpt Sprint 0 Acceptance Results",
        "",
        "## 1. Overall Result",
        "",
        f"**{report.get('overall_status', 'FAIL')}**",
        "",
        "## 2. Environment",
        "",
    ]
    lines.extend(f"- {label}: `{value}`" for label, value in environment_rows)
    lines.extend(
        [
            "",
            "## 3. Gate Summary Table",
            "",
            "| Gate | Result | Key evidence | Duration | Notes |",
            "|---|---|---|---:|---|",
        ]
    )
    for gate in gates:
        notes = "; ".join(gate.get("notes", [])) or "None"
        cells = [gate["id"], gate["status"], _key_evidence(gate), f"{gate.get('duration_seconds', 0):.3f}s", notes]
        lines.append("| " + " | ".join(str(cell).replace("|", "\\|").replace("\n", " ") for cell in cells) + " |")
    lines.extend(["", "## 4. Detailed Gate Results", ""])
    for gate in gates:
        lines.extend(
            [
                f"### {gate['id']} — {gate['name']}",
                "",
                f"- Result: **{gate['status']}**",
                f"- Pass/fail reason: {_key_evidence(gate)}",
                f"- Evidence: {', '.join(f'`{item}`' for item in gate.get('evidence_files', [])) or 'None'}",
                f"- Limitations/notes: {'; '.join(gate.get('notes', [])) or 'None'}",
                "- Expected behaviour:",
                "",
                "```json",
                json.dumps(gate.get("expected", {}), indent=2, ensure_ascii=False),
                "```",
                "",
                "- Actual values:",
                "",
                "```json",
                json.dumps(_markdown_actual(gate), indent=2, ensure_ascii=False),
                "```",
                "",
            ]
        )

    immutability = gate_by_id.get("GATE-06", {}).get("actual", {})
    lines.extend(["## 5. Mesh Immutability Evidence", ""])
    for item in immutability.get("records", []):
        before = item.get("before", {})
        lines.append(
            f"- `{item.get('mesh')}`: match={item.get('matched')}; differences={item.get('differences')}; "
            f"coordinate=`{before.get('coordinate_sha256')}`; edge=`{before.get('edge_connectivity_sha256')}`; "
            f"polygon=`{before.get('polygon_connectivity_sha256')}`."
        )
    if not immutability.get("records"):
        lines.append("- No completed signature comparisons were available.")

    export = gate_by_id.get("GATE-04", {}).get("actual", {})
    lines.extend(
        [
            "",
            "## 6. JSON Export Evidence",
            "",
            f"- Report: `{export.get('output_file', 'Not generated')}`",
            f"- UTF-8 readable: {export.get('utf8_readable', False)}",
            f"- Valid JSON: {export.get('valid_json', False)}",
            f"- Ends with newline: {export.get('ends_with_newline', False)}",
            f"- Per-check states present: {export.get('per_check_statuses_present', False)}",
            f"- Sanitization samples: `{json.dumps(export.get('filename_sanitization', {}), ensure_ascii=False)}`",
            "",
        ]
    )
    stress = gate_by_id.get("GATE-05", {}).get("actual", {})
    stress_geometry = stress.get("geometry", {})
    stress_topology = stress.get("topology", {})
    lines.extend(
        [
            "## 7. Stress-Test Evidence",
            "",
            f"- Vertices: {stress_geometry.get('vertex_count', 'Not available')}",
            f"- Edges: {stress_geometry.get('edge_count', 'Not available')}",
            f"- Faces: {stress_geometry.get('polygon_count', 'Not available')}",
            f"- Triangles: {stress_geometry.get('triangle_count', 'Not available')}",
            f"- Connected components: {stress_topology.get('connected_components', 'Not available')}",
            f"- Duplicate check: {stress_topology.get('duplicate_evaluation_status', 'Not available')}",
            f"- Analysis duration: {stress.get('duration_ms', 'Not available')} ms",
            f"- Scene artifact: `{stress.get('scene_saved_after_analysis', 'Not generated')}`",
            f"- Practical behavior: {stress.get('peak_observable_practical_behaviour', 'Not available')}",
            "",
        ]
    )
    registration = gate_by_id.get("GATE-08", {}).get("actual", {})
    lines.extend(
        [
            "## 8. Registration Evidence",
            "",
            f"- Initial registration: `{json.dumps(registration.get('initial_registered_state', {}))}`",
            f"- First unregister: `{json.dumps(registration.get('after_first_unregister', {}))}`",
            f"- Re-register: `{json.dumps(registration.get('after_reregister', {}))}`",
            f"- Final unregister: `{json.dumps(registration.get('after_final_unregister', {}))}`",
            f"- Panel placement: `{json.dumps(registration.get('panel', {}))}`",
            f"- Handler counts restored: {registration.get('handler_counts_before') == registration.get('handler_counts_after')}",
            "",
            "## 9. Package Validation",
            "",
        ]
    )
    package = gate_by_id.get("GATE-09", {})
    for command in package.get("actual", {}).get("commands", []):
        lines.append(
            f"- **{command.get('name')}**: exit `{command.get('exit_code')}` in {command.get('duration_seconds', 0):.3f}s — `{command.get('command')}`"
        )
    lines.extend(["", f"Package: `{package.get('actual', {}).get('package_path', 'Not generated')}`", ""])

    defects = report.get("defects", [])
    lines.extend(["## 10. Failures or Defects", ""])
    if defects:
        lines.extend(f"- {item}" for item in defects)
    elif report.get("failures"):
        for failure in report["failures"]:
            lines.append(f"- {failure.get('gate')}: {failure.get('name')} — {'; '.join(failure.get('notes', []))}")
    else:
        lines.append("- Product defects: None.")
    for correction in report.get("test_harness_corrections", []):
        lines.append(
            "- Acceptance harness correction (not a product defect): "
            f"root cause — {correction.get('root_cause')}; exact fix — {correction.get('exact_fix')}; "
            f"files — {', '.join(correction.get('files_changed', []))}; "
            f"regression evidence — {', '.join(correction.get('regression_evidence', []))}."
        )
    lines.extend(["", "## 11. Tests Not Run", ""])
    tests_not_run = report.get("tests_not_run", [])
    lines.extend(f"- {item}" for item in tests_not_run)
    if not tests_not_run:
        lines.append("- None.")

    safety = report.get("safety_confirmation", {})
    lines.extend(["", "## 12. Safety Confirmation", ""])
    confirmations = (
        ("No production user files modified", not safety.get("production_user_files_modified", True)),
        ("No network access", not safety.get("network_access_used", True)),
        ("No API keys", not safety.get("api_keys_used", True)),
        ("No administrator privileges", not safety.get("administrator_privileges_used", True)),
        ("No destructive analysis operations", not safety.get("destructive_analysis_operations_used", True)),
        ("No files changed outside repository except Blender runtime state", not safety.get("files_changed_outside_repository", True)),
        ("No automatic commits", not safety.get("automatic_commits_created", True)),
        ("Sprint 1 not started", not safety.get("sprint_1_started", True)),
    )
    lines.extend(f"- {label}: {'Confirmed' if confirmed else 'Not confirmed'}" for label, confirmed in confirmations)
    lines.extend(
        [
            "",
            "## 13. Sprint 0 Gate Decision",
            "",
            f"**{report.get('sprint_0_gate_decision', 'SPRINT 0 REJECTED')}**",
            "",
            "## 14. Recommended Next Action",
            "",
            report.get("recommended_next_action", "Review the failed gate evidence before authorizing additional work."),
            "",
        ]
    )
    return "\n".join(lines)


def _finalize_report(report: dict[str, Any], gate_nine: dict[str, Any], started_timer: float) -> None:
    report["gates"] = [gate for gate in report.get("gates", []) if gate["id"] != "GATE-09"] + [gate_nine]
    statuses = [gate["status"] for gate in report["gates"]]
    report["overall_status"] = "FAIL" if "FAIL" in statuses else "PARTIAL" if "SKIPPED" in statuses else "PASS"
    report["completed_at"] = _utc_now().isoformat()
    report["duration_seconds"] = round(perf_counter() - started_timer, 6)
    report["python_launcher"] = sys.executable
    report["failures"] = [
        {"gate": gate["id"], "name": gate["name"], "notes": gate.get("notes", [])}
        for gate in report["gates"]
        if gate["status"] == "FAIL"
    ]
    generated = set(report.get("generated_artifacts", []))
    generated.update({_relative(BLENDER_LOG_PATH), _relative(VALIDATION_LOG_PATH), _relative(RESULTS_PATH), _relative(MARKDOWN_PATH)})
    if PACKAGE_PATH.is_file():
        generated.add(_relative(PACKAGE_PATH))
    report["generated_artifacts"] = sorted(generated)
    report["sprint_0_gate_decision"] = {
        "PASS": "SPRINT 0 ACCEPTED",
        "PARTIAL": "SPRINT 0 ACCEPTED WITH LIMITATIONS",
        "FAIL": "SPRINT 0 REJECTED",
    }[report["overall_status"]]
    report["recommended_next_action"] = (
        "Review and approve this Sprint 0 evidence package before authorizing any Sprint 1 work."
        if report["overall_status"] == "PASS"
        else "Review the failed Sprint 0 gate evidence and resolve only the documented blocker before another full rerun."
    )
    RESULTS_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    MARKDOWN_PATH.write_text(_render_markdown(report), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, help="Explicit path to blender.exe")
    args = parser.parse_args()
    started_at = _utc_now()
    started_timer = perf_counter()
    discovery = _discover(args.blender)
    if discovery is None:
        print("Blender was not found. Pass --blender or configure the project discovery helper.", file=sys.stderr)
        return 2

    for directory in (LOGS_DIRECTORY, REPORTS_DIRECTORY, MANUAL_TESTS / "artifacts", MANUAL_TESTS / "screenshots"):
        directory.mkdir(parents=True, exist_ok=True)

    blender_command = [
        str(discovery.executable),
        "--background",
        "--factory-startup",
        "--python-exit-code",
        "1",
        "--python",
        str(MANUAL_TESTS / "acceptance_gate_runner.py"),
        "--",
        "--python-launcher",
        sys.executable,
    ]
    print(f"Blender: {discovery.executable} ({discovery.version})")
    blender_record, blender_log = _run_command("Blender Sprint 0 acceptance gates", blender_command)
    BLENDER_LOG_PATH.write_text(blender_log, encoding="utf-8", newline="\n")

    if RESULTS_PATH.is_file():
        try:
            report = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            report = _fallback_report(discovery, started_at)
    else:
        report = _fallback_report(discovery, started_at)
    _finalize_stability(report, blender_record, blender_log)

    gate_nine, validation_log = _run_windows_validations(discovery)
    VALIDATION_LOG_PATH.write_text(validation_log, encoding="utf-8", newline="\n")
    _finalize_report(report, gate_nine, started_timer)

    print("Gate summary:")
    for gate in report["gates"]:
        print(f"  {gate['id']}: {gate['status']} — {_key_evidence(gate)}")
    print(f"Overall: {report['overall_status']}")
    print(f"Decision: {report['sprint_0_gate_decision']}")
    print(f"Machine report: {RESULTS_PATH}")
    print(f"Human report: {MARKDOWN_PATH}")
    return 0 if report["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
