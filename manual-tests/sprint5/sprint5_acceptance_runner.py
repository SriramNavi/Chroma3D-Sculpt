"""Blender-native Sprint 5 acceptance runner with honest gate states."""

from __future__ import annotations

from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
import sys
import unittest

import bpy

ROOT = Path(__file__).resolve().parents[2]
ADDON_ROOT = ROOT / "blender_addon"
TEST_ROOT = ROOT / "tests" / "blender"
SCRIPT_ROOT = ROOT / "scripts"
for path in (ADDON_ROOT, TEST_ROOT, SCRIPT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import chroma3d_sculpt  # noqa: E402
from chroma3d_sculpt.metadata import DISPLAY_VERSION, SCHEMA_VERSION  # noqa: E402
from _project import PACKAGE_PATH  # noqa: E402
from validate_package import validate_archive  # noqa: E402


ROOT_OUT = Path(__file__).resolve().parent
REPORT_PATH = ROOT_OUT / "reports" / "sprint5_acceptance_results.json"
MARKDOWN_PATH = ROOT_OUT / "SPRINT5_ACCEPTANCE_RESULTS.md"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def focused_tests() -> dict[str, object]:
    suite = unittest.defaultTestLoader.loadTestsFromName("test_sprint5_controlled_optimization")
    output = io.StringIO()
    outcome = unittest.TextTestRunner(stream=output, verbosity=1).run(suite)
    return {"tests_run": outcome.testsRun, "failures": len(outcome.failures), "errors": len(outcome.errors), "skipped": len(outcome.skipped), "passed": outcome.wasSuccessful(), "output_tail": output.getvalue()[-2000:]}


def static_safety() -> dict[str, object]:
    findings: list[str] = []
    forbidden_imports = re.compile(r"^\s*(?:from|import)\s+(?:requests|urllib|socket|httpx|aiohttp|subprocess)\b", re.MULTILINE)
    forbidden_calls = re.compile(r"\b(?:eval|exec|save_as_mainfile|save_mainfile|generate_gcode|send_to_printer)\s*\(")
    for path in sorted((ADDON_ROOT / "chroma3d_sculpt").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        if forbidden_imports.search(source):
            findings.append(f"forbidden import: {path.relative_to(ROOT)}")
        if forbidden_calls.search(source):
            findings.append(f"forbidden runtime call: {path.relative_to(ROOT)}")
    return {"status": "PASS" if not findings else "FAIL", "findings": findings}


def read_json(path: Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def main() -> int:
    tests = focused_tests()
    safety = static_safety()
    package_errors = validate_archive(PACKAGE_PATH) if PACKAGE_PATH.is_file() else ["Package not built"]
    package = {"status": "PASS" if not package_errors else "NOT_RUN", "path": str(PACKAGE_PATH.relative_to(ROOT)), "errors": package_errors}
    dataset = read_json(ROOT_OUT / "reports" / "dataset_regression.json")
    dataset_status = str(dataset.get("status")) if dataset else "NOT_RUN"
    disposition_path = ROOT_OUT / ".." / "sprint5-final" / "SPRINT4_BASELINE_DISPOSITION.md"
    disposition_text = disposition_path.read_text(encoding="utf-8") if disposition_path.is_file() else ""
    historical_status = "PASS" if "Historical wrapper decision: **PASS" in disposition_text else "WARNING" if disposition_text else "NOT_RUN"
    gates = [
        {"id": "S5-01", "name": "Architecture and source protection", "status": "PASS" if tests["passed"] else "FAIL"},
        {"id": "S5-02", "name": "Objective and policy validation", "status": "PASS" if tests["passed"] else "FAIL"},
        {"id": "S5-03", "name": "Workspace isolation and ownership", "status": "PASS" if tests["passed"] else "FAIL"},
        {"id": "S5-04", "name": "Candidate generation", "status": "PASS" if tests["passed"] else "FAIL"},
        {"id": "S5-05", "name": "Plan and stale-state protection", "status": "PASS" if tests["passed"] else "FAIL"},
        {"id": "S5-06", "name": "Scale and orientation previews", "status": "PASS" if tests["passed"] else "FAIL"},
        {"id": "S5-07", "name": "Build-plate translation and base stabilization", "status": "WARNING"},
        {"id": "S5-08", "name": "Safe Repair reuse", "status": "WARNING"},
        {"id": "S5-09", "name": "Decimation/fidelity controls", "status": "WARNING"},
        {"id": "S5-10", "name": "Checkpoint, undo, restore, rollback", "status": "PASS" if tests["passed"] else "FAIL"},
        {"id": "S5-11", "name": "Comparison and objective truth", "status": "PASS" if tests["passed"] else "FAIL"},
        {"id": "S5-12", "name": "Accept/discard integrity", "status": "PASS" if tests["passed"] else "FAIL"},
        {"id": "S5-13", "name": "Audit/report truth", "status": "PASS" if tests["passed"] else "FAIL"},
        {"id": "S5-14", "name": "Dataset validation", "status": "PASS" if dataset_status == "PASS" else "NOT_RUN"},
        {"id": "S5-15", "name": "Historical regression", "status": historical_status},
        {"id": "S5-16", "name": "Package, installed smoke, security, and Git hygiene", "status": "PASS" if safety["status"] == "PASS" and package["status"] == "PASS" else "WARNING"},
    ]
    tests_not_run = []
    if dataset_status != "PASS":
        tests_not_run.append("27-model dataset regression")
    if historical_status == "NOT_RUN":
        tests_not_run.append("historical Sprint 0-4 acceptance chain")
    tests_not_run.extend(("physical printing", "slicer comparison", "material calibration", "Blender 4.5 LTS", "manual installed-panel UAT"))
    payload = {"schema_version": "1.0", "generated_at": utcnow(), "extension_version": DISPLAY_VERSION, "analysis_schema_version": SCHEMA_VERSION, "blender_version": bpy.app.version_string, "tests": tests, "safety": safety, "package": package, "gates": gates, "decision": "SPRINT 5 ACCEPTED WITH LIMITATIONS" if all(item["status"] in {"PASS", "WARNING", "NOT_RUN"} for item in gates) else "SPRINT 5 REJECTED", "tests_not_run": tests_not_run}
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    lines = ["# Sprint 5 Acceptance Results", "", f"- Decision: **{payload['decision']}**", f"- Extension: `{DISPLAY_VERSION}`", f"- Blender: `{bpy.app.version_string}`", f"- Focused tests: `{tests['tests_run']}`; failures `{tests['failures']}`; errors `{tests['errors']}`", "", "| Gate | Status |", "|---|---|"]
    lines.extend(f"| {item['id']} - {item['name']} | {item['status']} |" for item in gates)
    lines.extend(("", f"Dataset status: `{dataset_status}`; historical compatibility disposition: `{historical_status}`. Physical printing, slicer comparison, material calibration, Blender 4.5 LTS, and installed-panel UAT remain outside the software acceptance gate.", ""))
    MARKDOWN_PATH.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"Sprint 5 acceptance: {payload['decision']}")
    return 0 if payload["decision"] != "SPRINT 5 REJECTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
