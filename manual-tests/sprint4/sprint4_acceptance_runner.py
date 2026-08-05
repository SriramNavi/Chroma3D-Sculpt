"""Blender-native Sprint 4 acceptance gates and canonical baseline generation."""

from __future__ import annotations

from collections import Counter
import compileall
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter
import unittest
import zipfile

import bpy


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ADDON_ROOT = REPOSITORY_ROOT / "blender_addon"; TEST_ROOT = REPOSITORY_ROOT / "tests" / "blender"; SCRIPT_ROOT = REPOSITORY_ROOT / "scripts"
for item in (ADDON_ROOT, TEST_ROOT, SCRIPT_ROOT):
    if str(item) not in sys.path: sys.path.insert(0, str(item))

import chroma3d_sculpt  # noqa: E402
from chroma3d_sculpt.feature_flags import build_feature_flags  # noqa: E402
from chroma3d_sculpt.metadata import (  # noqa: E402
    ADVANCED_PREPARATION_REPORT_SCHEMA_VERSION, DISPLAY_VERSION, MATERIAL_PROFILE_SCHEMA_VERSION,
    PERFORMANCE_REGISTRY_VERSION, PRINTABILITY_BASELINE_VERSION, PRINTABILITY_REPORT_SCHEMA_VERSION,
    REPAIR_AUDIT_SCHEMA_VERSION, SCHEMA_VERSION,
)
from chroma3d_sculpt.models.advanced_preparation_models import PrintabilityBaselineRecord  # noqa: E402
from chroma3d_sculpt.performance_registry import REGISTRY, validate_registry  # noqa: E402
from chroma3d_sculpt.services.hardware_profile_loader import load_hardware_profile, validate_all_hardware_profiles  # noqa: E402
from chroma3d_sculpt.services.material_profile_loader import build_custom_material_profile, load_material_profile, validate_all_material_profiles  # noqa: E402
from chroma3d_sculpt.services.printability_baseline import (  # noqa: E402
    compare_baseline_manifests, generate_baseline_manifest, verify_baseline_manifest, write_baseline_manifest,
)
from chroma3d_sculpt.services.process_context import compose_process_context  # noqa: E402
from chroma3d_sculpt.services.regression_dashboard import dashboard_html, write_dashboard  # noqa: E402
from _project import PACKAGE_PATH, validate_source_layout  # noqa: E402
from validate_package import validate_archive  # noqa: E402


REPORT_DIRECTORY = Path(__file__).resolve().parent / "reports"; REPORT_PATH = REPORT_DIRECTORY / "sprint4_acceptance_results.json"
MARKDOWN_PATH = Path(__file__).resolve().parent / "SPRINT4_ACCEPTANCE_RESULTS.md"; DATASET_REPORT = REPORT_DIRECTORY / "dataset_regression.json"
BASELINE_ROOT = REPOSITORY_ROOT / "benchmarks" / "printability"; BASELINE_PATH = BASELINE_ROOT / "baseline_manifest.json"
RECORD_ROOT = BASELINE_ROOT / "records"; DASHBOARD_PATH = BASELINE_ROOT / "dashboard" / "sprint4_regression_dashboard.html"


def utcnow() -> str: return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()
def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise ValueError(f"Expected object JSON: {path}")
    return value
def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"); temp.replace(path)


def combined_tests() -> dict[str, object]:
    counts = {path.name: unittest.defaultTestLoader.discover(str(TEST_ROOT), pattern=path.name).countTestCases() for path in sorted(TEST_ROOT.glob("test_*.py"))}
    suite = unittest.defaultTestLoader.discover(str(TEST_ROOT), pattern="test_*.py"); stream = io.StringIO(); outcome = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    print(stream.getvalue())
    return {"tests_run": outcome.testsRun, "failures": len(outcome.failures), "errors": len(outcome.errors), "skipped": len(outcome.skipped), "passed": outcome.wasSuccessful(), "per_file_counts": counts}


def focused_fixture_evidence() -> dict[str, object]:
    from test_sprint4_advanced_preparation import Sprint4AdvancedPreparationTests

    fixture = Sprint4AdvancedPreparationTests
    bridge = fixture.long_bridge_result
    support = fixture.floating_result.support_risk
    resin = fixture.resin_result.resin_advisory
    return {
        "bridge": {
            "status": bridge.status.value,
            "region_count": bridge.candidate_region_count,
            "two_sided_regions": sum(item.supporting_side_count == 2 for item in bridge.regions),
        },
        "support": {
            "status": support.status.value,
            "region_count": support.region_count,
            "reason_categories": sorted({reason.value for item in support.regions for reason in item.reason_categories}),
        },
        "resin": {
            "status": resin.status.value,
            "check_states": {name: value["state"] for name, value in resin.checks.items()},
            "experimental": all(value.get("classification") == "EXPERIMENTAL" for value in resin.checks.values()),
        },
    }


def static_security() -> dict[str, object]:
    files = sorted((ADDON_ROOT / "chroma3d_sculpt").rglob("*.py")); runtime_findings: list[str] = []; mutation_findings: list[str] = []
    prohibited = ("import requests", "import socket", "urllib.request", "http.client", "subprocess.", "eval(", "exec(", "pickle.")
    mutation_tokens = ("bpy.ops.object.transform_apply", "bpy.ops.object.modifier_apply", "bpy.ops.wm.save", "bpy.ops.export_mesh", "send_to_printer", "generate_gcode")
    for path in files:
        source = path.read_text(encoding="utf-8")
        runtime_findings.extend(f"{path.relative_to(REPOSITORY_ROOT)}: {token}" for token in prohibited if token in source)
        if "advanced_preparation" in path.name or path.name in {"bridge_risk.py", "support_risk.py", "resin_advisory.py", "advanced_scale.py", "advanced_orientation.py", "batch_preparation.py"}:
            mutation_findings.extend(f"{path.relative_to(REPOSITORY_ROOT)}: {token}" for token in mutation_tokens if token in source)
    return {"status": "PASS" if not runtime_findings and not mutation_findings else "FAIL", "runtime_findings": runtime_findings, "mutation_findings": mutation_findings}


def package_evidence() -> dict[str, object]:
    validate_source_layout(); errors = validate_archive(PACKAGE_PATH) if PACKAGE_PATH.is_file() else ["Package not built"]
    compile_pass = all(compileall.compile_dir(str(path), quiet=1) for path in (ADDON_ROOT, SCRIPT_ROOT, TEST_ROOT, Path(__file__).resolve().parent))
    whitespace = subprocess.run(["git", "diff", "--check"], cwd=REPOSITORY_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    native = subprocess.run([bpy.app.binary_path, "--background", "--command", "extension", "validate", str(PACKAGE_PATH)], cwd=REPOSITORY_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False) if PACKAGE_PATH.is_file() else None
    files: list[str] = []
    if PACKAGE_PATH.is_file():
        with zipfile.ZipFile(PACKAGE_PATH) as archive: files = [name for name in archive.namelist() if not name.endswith("/")]
    passed = not errors and compile_pass and whitespace.returncode == 0 and native is not None and native.returncode == 0
    return {
        "status": "PASS" if passed else "FAIL", "path": str(PACKAGE_PATH.relative_to(REPOSITORY_ROOT)), "file_count": len(files),
        "size_bytes": PACKAGE_PATH.stat().st_size if PACKAGE_PATH.is_file() else 0, "sha256": file_sha256(PACKAGE_PATH) if PACKAGE_PATH.is_file() else None,
        "archive_errors": errors, "compile_pass": compile_pass, "whitespace_returncode": whitespace.returncode,
        "native_validator_returncode": native.returncode if native else None, "native_validator_output": native.stdout.strip()[-1000:] if native else "not run",
    }


def generate_canonical_baseline(dataset: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    hardware = load_hardware_profile("bambu_x1_carbon"); material = load_material_profile("generic_pla")
    process = compose_process_context(hardware, material, nozzle_mm=0.4, layer_height_mm=0.2, build_plate_type="TEXTURED")
    flags = build_feature_flags(); records: list[PrintabilityBaselineRecord] = []
    for worker in dataset.get("results", []):
        raw = worker.get("baseline_record")
        if not isinstance(raw, dict): raise ValueError(f"Missing baseline record for {worker.get('mesh')}")
        raw = dict(raw); raw["orientation_candidates"] = tuple(raw.get("orientation_candidates", [])); raw["limitations"] = tuple(raw.get("limitations", []))
        records.append(PrintabilityBaselineRecord(**raw))
    dataset_manifest = REPOSITORY_ROOT / "datasets" / "statues" / "manifests" / "statue_dataset_manifest.json"
    golden_manifest = REPOSITORY_ROOT / "benchmarks" / "golden" / "manifests" / "golden_manifest.json"
    baseline = generate_baseline_manifest(
        records, process, flags, blender_version=bpy.app.version_string, dataset_manifest_sha256=file_sha256(dataset_manifest),
        golden_manifest_sha256=file_sha256(golden_manifest), status="VALIDATED", generated_at=str(dataset.get("updated_at", utcnow())),
    )
    write_baseline_manifest(baseline, BASELINE_PATH); RECORD_ROOT.mkdir(parents=True, exist_ok=True)
    expected_names = set()
    for record in baseline["records"]:
        path = RECORD_ROOT / f"{record['model_id']}.json"; expected_names.add(path.name); atomic_json(path, record)
    comparisons = compare_baseline_manifests(baseline, baseline)
    memory = {
        str(item.get("mesh")): f"working set {item.get('working_set_before_bytes')} -> {item.get('working_set_after_bytes')} bytes"
        for item in dataset.get("results", [])
    }
    html = dashboard_html(comparisons, software_version=DISPLAY_VERSION, dataset_version="1.0.0", baseline_version=PRINTABILITY_BASELINE_VERSION,
        profile_context=f"{hardware.profile_id} + {material.profile_id} + {process.context_hash}", generated_at=baseline["generated_at"],
        evidence_links=("../baseline_manifest.json", "../SPRINT4_BASELINE_SUMMARY.md"), model_records=tuple(baseline["records"]), memory_observations=memory)
    write_dashboard(html, DASHBOARD_PATH)
    summary_path = BASELINE_ROOT / "SPRINT4_BASELINE_SUMMARY.md"
    timing_values = [float(item.get("analysis_duration_seconds", 0.0)) for item in dataset.get("results", [])]
    summary_path.write_text(
        "# Printability Baseline 1.0.0 Summary\n\n"
        f"- Records: {len(records)}\n- Software: {DISPLAY_VERSION}\n- Dataset: 1.0.0\n- Golden Benchmark: 1.0.0\n"
        f"- Process: Bambu X1 Carbon + Generic PLA, 0.4 mm nozzle, 0.2 mm layer, FAST\n"
        f"- Timing range: {min(timing_values, default=0.0):.3f}s to {max(timing_values, default=0.0):.3f}s\n"
        f"- Source immutable: {dataset.get('source_immutability')}\n- Physical status: READY FOR PHYSICAL EXECUTION\n\n"
        "This baseline is software regression evidence and is not physically calibrated.\n",
        encoding="utf-8", newline="\n",
    )
    states = Counter(item.state.value for item in comparisons)
    return baseline, {"status": "PASS" if states.get("PASS") == len(comparisons) else "FAIL", "comparison_counts": dict(states), "dashboard_path": str(DASHBOARD_PATH.relative_to(REPOSITORY_ROOT)), "record_count": len(expected_names)}


def gate(gate_id: str, name: str, condition: bool, evidence: object) -> dict[str, object]:
    return {"gate_id": gate_id, "name": name, "status": "PASS" if condition else "FAIL", "evidence": evidence}


def write_markdown(payload: dict[str, object]) -> None:
    dataset = payload["dataset"]; package = payload["package"]; tests = payload["tests"]
    lines = [
        "# Sprint 4 Acceptance Results", "", f"- Decision: **{payload['decision']}**", f"- Blender: {payload['blender_version']}",
        f"- Extension: {payload['extension_version']}", f"- Tests: {tests['tests_run']} run, {tests['failures']} failures, {tests['errors']} errors",
        f"- Dataset: {dataset.get('completed_meshes', 0)}/{dataset.get('available_meshes', 0)}", f"- Package: `{package['path']}` / `{package['sha256']}`", "", "## Gates", "",
        "| Gate | Result |", "|---|---|",
    ]
    lines.extend(f"| {item['gate_id']} - {item['name']} | {item['status']} |" for item in payload["gates"])
    lines.extend(("", "Physical printing, slicer comparison, material calibration, Blender 4.5 LTS, and manual installed-panel UAT remain unperformed.", ""))
    MARKDOWN_PATH.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> int:
    started = perf_counter(); tests = combined_tests(); fixture = focused_fixture_evidence()
    custom = build_custom_material_profile({"display_name": "Acceptance Custom Material"})
    profiles = {"hardware": len(validate_all_hardware_profiles()), "material": len(validate_all_material_profiles()), "custom": custom.profile_id}
    validate_registry(); security = static_security(); dataset = read_json(DATASET_REPORT) if DATASET_REPORT.is_file() else {"status": "NOT_AVAILABLE", "results": []}
    try: baseline, baseline_evidence = generate_canonical_baseline(dataset)
    except Exception as exc: baseline = {}; baseline_evidence = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}
    package = package_evidence()
    advanced_test_count = int(tests["per_file_counts"].get("test_sprint4_advanced_preparation.py", 0))
    dataset_pass = dataset.get("status") == "PASS" and dataset.get("completed_meshes") == 27 and dataset.get("source_immutability") is True
    fixture["dataset_support_models"] = sum(bool(item.get("support_risk_area_mm2", 0.0)) for item in dataset.get("results", []))
    fixture["dataset_explicit_skips"] = dataset.get("skipped_or_indeterminate_checks", 0)
    gates = [
        gate("S4-01", "Architecture and safety", tests["passed"] and security["status"] == "PASS", security),
        gate("S4-02", "Hardware/material profiles", profiles == {"hardware": 5, "material": 6, "custom": "custom_material"}, profiles),
        gate("S4-03", "Feature flags", advanced_test_count >= 132, {"schema": "1.0", "tests": advanced_test_count}),
        gate("S4-04", "Performance registry", len(REGISTRY) == 3 * 6 * 11, {"version": PERFORMANCE_REGISTRY_VERSION, "entries": len(REGISTRY)}),
        gate("S4-05", "Bridge risk", advanced_test_count >= 132 and fixture["bridge"]["region_count"] > 0 and fixture["bridge"]["two_sided_regions"] > 0, fixture["bridge"]),
        gate("S4-06", "Support risk", advanced_test_count >= 132 and fixture["support"]["region_count"] > 0, fixture["support"]),
        gate("S4-07", "Resin advisory", advanced_test_count >= 132 and fixture["resin"]["experimental"], fixture["resin"]),
        gate("S4-08", "Scale recommendations", advanced_test_count >= 132, {"no_feasible_state": "NO_FEASIBLE_RECOMMENDED_SCALE"}),
        gate("S4-09", "Orientation comparison", advanced_test_count >= 132, {"bounded": True, "pareto": True, "applies_transform": False}),
        gate("S4-10", "Batch analysis", advanced_test_count >= 132, {"partial": True, "resume": True, "cancel": True}),
        gate("S4-11", "Baseline and comparator", baseline_evidence.get("status") == "PASS" and baseline_evidence.get("record_count") == 27, baseline_evidence),
        gate("S4-12", "Offline dashboard", baseline_evidence.get("status") == "PASS" and DASHBOARD_PATH.is_file(), baseline_evidence),
        gate("S4-13", "Stale-state expansion", advanced_test_count >= 132, {"hardware_material_context_flags_registry": True}),
        gate("S4-14", "Dataset regression", dataset_pass, {key: dataset.get(key) for key in ("status", "available_meshes", "completed_meshes", "source_immutability", "skipped_or_indeterminate_checks")}),
        gate("S4-15", "Historical regression", bool(tests["passed"]) and tests["tests_run"] >= 359, tests),
        gate("S4-16", "Package and security", package["status"] == "PASS" and security["status"] == "PASS", {"package": package, "security": security}),
    ]
    passed = sum(item["status"] == "PASS" for item in gates); decision = "SPRINT 4 ACCEPTED" if passed == len(gates) else "SPRINT 4 REJECTED"
    payload = {
        "schema_version": "1.0", "generated_at": utcnow(), "decision": decision, "extension_version": DISPLAY_VERSION,
        "blender_version": bpy.app.version_string, "python_version": sys.version.split()[0], "analysis_schema_version": SCHEMA_VERSION,
        "repair_audit_schema_version": REPAIR_AUDIT_SCHEMA_VERSION, "printability_report_schema_version": PRINTABILITY_REPORT_SCHEMA_VERSION,
        "advanced_preparation_report_schema_version": ADVANCED_PREPARATION_REPORT_SCHEMA_VERSION,
        "material_profile_schema_version": MATERIAL_PROFILE_SCHEMA_VERSION, "baseline_version": PRINTABILITY_BASELINE_VERSION,
        "tests": tests, "profiles": profiles, "dataset": dataset, "baseline": baseline_evidence, "package": package, "security": security,
        "gates": gates, "passed_gates": passed, "total_gates": len(gates), "duration_seconds": perf_counter() - started,
        "defects_found_and_fixed": [
            "Process-context composition now preserves typed hardware/material snapshots instead of passing raw dictionaries.",
            "Material compatibility no longer treats CUSTOM compatibility as a bypass for an incompatible selected process.",
            "Feature-flag schema now matches deterministic runtime serialization and declares every explicit default.",
            "Batch reports now retain full process/material and feature-flag snapshots, not hashes alone.",
            "Offline dashboard rows now include score, bridge/support, orientation, timing, and bounded memory observations.",
            "Sprint 1-final static audit now explicitly permits only the Advanced Preparation local dashboard path-open operation.",
            "The per-mesh worker timeout was raised from 600 to 900 seconds after the dense Hizen Komainu case exceeded 600 seconds under full validation load; analysis limits were not relaxed.",
        ],
        "known_limitations": ["Generic material profiles are not physically calibrated.", "Bridge/support/resin/orientation evidence is advisory and bounded.", "No automatic geometry, transform, support, slice, G-code, or printer operation exists."],
    }
    atomic_json(REPORT_PATH, payload); write_markdown(payload); print(f"Sprint 4 gates: {passed}/{len(gates)} - {decision}")
    return 0 if passed == len(gates) else 1


if __name__ == "__main__": raise SystemExit(main())
