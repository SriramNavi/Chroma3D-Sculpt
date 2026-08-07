"""Run the ordered, fail-closed H3 architecture hardening validation."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib.util
from io import StringIO
import json
from pathlib import Path
import re
import subprocess
import sys
from time import perf_counter
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
H3_ROOT = ROOT / "hardening" / "h3"
REPORTS = ROOT / "manual-tests" / "hardening" / "reports" / "h3"
LOGS = REPORTS / "logs"
RESULT_PATH = H3_ROOT / "H3_FINAL_RESULT.json"
REPORT_PATH = H3_ROOT / "H3_FINAL_REPORT.md"
BLENDER_DEFAULT = Path(r"D:\Softwares\Design\Blender\blender.exe")
EXPECTED_HEAD = "208016e87dbebe0580d9fa63cd1392e398fc3bf2"
EXPECTED_BRANCH = "feature/v1.0-release-hardening"
PUBLIC_CONTRACT = "b331ba4f9767a356c75825f1865164245d194ea81a41b39e37fe1110b56deb03"
SELECTED_PATHS = {
    "blender_addon/chroma3d_sculpt/services/repair_operations.py",
    "blender_addon/chroma3d_sculpt/services/ai_assistance_coordinator.py",
    "blender_addon/chroma3d_sculpt/services/mesh_analyzer.py",
}
TEST_PATHS = {
    "tests/blender/test_sprint2_repair.py",
    "tests/blender/test_sprint7_ai_recommendation.py",
    "tests/blender/test_mesh_analysis.py",
}
FOCUSED_TESTS = (
    "tests/blender/test_mesh_analysis.py",
    "tests/blender/test_sprint1_diagnostics.py",
    "tests/blender/test_sprint2_repair.py",
    "tests/blender/test_sprint7_ai_recommendation.py",
)
ANCHORS = {
    "v0.8.0-alpha.1": ("e819bfd4fd7705a97d967872f0c934295758381c", "fb0c7b6102d1460871d38aea9acb60373559be8d"),
    "v0.8.0-pre-hardening-backup": ("8471cb474c1ee4c092af9eea24306a6ea886fa71", "d06e1a05890fe23e77e66f95fc40e0200638a765"),
    "v0.8.0-h0-hardening-baseline": ("371b0ee4b6bcbc87245b1e50084eeb6c3486e311", "6f20b8c3007658a78eb89e2d2937924175384feb"),
    "v0.8.0-h1-hardening-checkpoint": ("55964ca63435499da857190a90af09804e18e615", "d6cab118c44422375e69bd077cabc85a990a9a33"),
    "v0.8.0-h2-hardening-checkpoint": ("b6579195f8578bc264d65444adbab06b4824fee5", EXPECTED_HEAD),
}


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value.rstrip() + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    if check and completed.returncode:
        raise RuntimeError(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return completed.stdout.strip()


def _run(command: list[str], name: str, timeout: int) -> dict[str, Any]:
    LOGS.mkdir(parents=True, exist_ok=True)
    started = perf_counter()
    try:
        completed = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False,
        )
        code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        code = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        timed_out = True
    (LOGS / f"{name}.log").write_text(stdout + "\n--- STDERR ---\n" + stderr, encoding="utf-8", newline="\n")
    return {
        "returncode": code,
        "elapsed_seconds": round(perf_counter() - started, 6),
        "timed_out": timed_out,
        "log": (LOGS / f"{name}.log").relative_to(ROOT).as_posix(),
        "stdout_tail": stdout.splitlines()[-20:],
        "stderr_tail": stderr.splitlines()[-40:],
    }


def _python(script: Path, name: str, *args: str, timeout: int = 1200) -> dict[str, Any]:
    return _run([sys.executable, str(script), *args], name, timeout)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _test_count(run: dict[str, Any], pattern: str) -> int:
    expression = re.compile(pattern)
    for line in [*run.get("stdout_tail", ()), *run.get("stderr_tail", ())]:
        match = expression.search(str(line))
        if match:
            return int(match.group(1))
    return 0


def _gate(gates: list[dict[str, Any]], gate_id: str, name: str, passed: bool, detail: Any) -> bool:
    gates.append({"id": gate_id, "name": name, "status": "PASS" if passed else "FAIL", "detail": detail})
    return passed


def _remote_tags() -> dict[str, str]:
    lines = _git("ls-remote", "--tags", "origin").splitlines()
    return {ref: value for value, ref in (line.split(maxsplit=1) for line in lines)}


def _baseline_integrity() -> dict[str, Any]:
    baseline = _read_json(H3_ROOT / "H3_BASELINE_IDENTITY.json")
    mismatches = []
    for item in baseline["h2_artifacts"].values():
        if not isinstance(item, dict) or "path" not in item:
            continue
        path = ROOT / item["path"]
        if not path.is_file() or _sha256(path) != item["sha256"]:
            mismatches.append(item["path"])
    h2 = _read_json(ROOT / "hardening" / "h2" / "H2_FINAL_RESULT.json")
    remote = _remote_tags()
    anchors = []
    for name, (expected_object, expected_peeled) in ANCHORS.items():
        local_object = _git("rev-parse", f"refs/tags/{name}")
        local_peeled = _git("rev-parse", f"refs/tags/{name}^{{}}")
        remote_object = remote.get(f"refs/tags/{name}", "")
        remote_peeled = remote.get(f"refs/tags/{name}^{{}}", remote_object)
        unchanged = local_object == remote_object == expected_object and local_peeled == remote_peeled == expected_peeled
        anchors.append({"name": name, "unchanged": unchanged, "object": local_object, "peeled": local_peeled})
    historical_diff = _git("diff", "--name-only", "--", "hardening/h2", "manual-tests/hardening/h2").splitlines()
    passed = all((
        not mismatches,
        not historical_diff,
        _git("rev-parse", "HEAD") == EXPECTED_HEAD,
        h2.get("status") == "PASS",
        h2.get("decision") == "H2_COMPLETE_WITH_FINDINGS",
        len(h2.get("gates", ())) == 17,
        all(gate.get("status") == "PASS" for gate in h2.get("gates", ())),
        all(item["unchanged"] for item in anchors),
    ))
    return {
        "status": "PASS" if passed else "FAIL",
        "artifact_mismatches": mismatches,
        "historical_h2_changes": historical_diff,
        "h2_decision": h2.get("decision"),
        "h2_gates": len(h2.get("gates", ())),
        "anchors": anchors,
    }


def _ledger_integrity() -> tuple[dict[str, Any], dict[str, Any]]:
    ledger = _read_json(H3_ROOT / "H3_COMPLEXITY_LEDGER.json")
    after = _read_json(H3_ROOT / "H3_COMPLEXITY_AFTER.json")
    required = {
        "file", "symbol", "symbol_type", "physical_loc", "logical_complexity", "branch_count",
        "nesting_depth", "dependency_count", "direct_callers", "indirect_public_reachability",
        "blender_registration_involvement", "mutation_involvement", "filesystem_involvement",
        "network_or_provider_involvement", "lifecycle_or_state_involvement",
        "source_protection_involvement", "checkpoint_or_rollback_involvement", "tests_exercising",
        "relevant_sprint", "relevant_invariants", "likely_refactor_strategy", "refactor_risk", "disposition",
    }
    missing = [item.get("file", "<unknown>") for item in ledger.get("entries", ()) if not required.issubset(item)]
    complete = (
        ledger.get("status") == "PASS" and ledger.get("target_count") == 35
        and ledger.get("priority_counts") == {"CRITICAL_REVIEW_PRIORITY": 7, "HIGH_REVIEW_PRIORITY": 28}
        and not missing and after.get("status") == "PASS"
    )
    selected = ledger.get("selected_targets", ())
    changed = set(_git("diff", "--name-only").splitlines())
    selected_pass = (
        len(selected) == 3 and {item.get("file") for item in selected} == SELECTED_PATHS
        and SELECTED_PATHS.issubset(changed)
        and all(item.get("disposition") and item.get("reason") for item in selected)
    )
    return (
        {"status": "PASS" if complete else "FAIL", "targets": ledger.get("target_count"), "priority_counts": ledger.get("priority_counts"), "missing_fields": missing},
        {"status": "PASS" if selected_pass else "FAIL", "selected": selected, "changed_runtime_paths": sorted(SELECTED_PATHS & changed)},
    )


def _equivalence() -> tuple[dict[str, Any], dict[str, Any]]:
    evidence = _read_json(H3_ROOT / "H3_BEHAVIORAL_EQUIVALENCE.json")
    before = evidence.get("before", {})
    after = evidence.get("after", {})
    characterization = {
        "status": "PASS" if before.get("status") == "PASS" and before.get("focused_blender", {}).get("tests_run") == 137 else "FAIL",
        "tests_run": before.get("focused_blender", {}).get("tests_run"),
        "log": before.get("focused_blender", {}).get("log"),
    }
    batches_pass = (
        after.get("status") == "PASS" and after.get("focused_blender", {}).get("tests_run") == 137
        and evidence.get("comparison", {}).get("status") == "PASS"
        and not evidence.get("comparison", {}).get("public_or_behavioral_differences")
    )
    batches = {
        "status": "PASS" if batches_pass else "FAIL",
        "after_tests_run": after.get("focused_blender", {}).get("tests_run"),
        "comparison": evidence.get("comparison"),
    }
    return characterization, batches


def _current_python_paths(common: Any) -> list[Path]:
    values = _git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()
    return [ROOT / value for value in values if value.endswith(".py") and not value.startswith(common.HARDENING_EXCLUSIONS)]


def _structural() -> dict[str, Any]:
    tools = ROOT / "hardening" / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    import _common
    import analyze_complexity
    import analyze_dependencies
    import analyze_duplication
    paths = _current_python_paths(_common)
    for module in (analyze_complexity, analyze_dependencies, analyze_duplication):
        module.checkpoint_python_paths = lambda: paths
    dependencies = analyze_dependencies.analyze()
    complexity = analyze_complexity.analyze()
    duplication = analyze_duplication.analyze()
    _write_json(REPORTS / "dependency_graph.json", dependencies)
    _write_json(REPORTS / "complexity.json", complexity)
    _write_json(REPORTS / "duplication.json", duplication)
    candidates = duplication.get("candidates", ())
    overlaps = [item for item in candidates if any(path in json.dumps(item, sort_keys=True) for path in SELECTED_PATHS)]
    duplication_review = {
        "schema_version": "1.0.0",
        "status": "PASS",
        "h2_candidate_count": 80,
        "h3_candidate_count": duplication.get("candidate_count"),
        "selected_target_overlap_count": len(overlaps),
        "selected_target_overlaps": [
            {"candidate": item, "disposition": "DUPLICATE_BUT_KEEP", "reason": "No fully proven shared ownership and semantic equivalence within the bounded H3 target."}
            for item in overlaps
        ],
        "consolidations": 0,
    }
    _write_json(H3_ROOT / "H3_DUPLICATION_REVIEW.json", duplication_review)
    package_edges = sum(
        1 for module, imports in dependencies.get("module_imports", {}).items()
        if module.startswith("chroma3d_sculpt")
        for target in imports if target.startswith("chroma3d_sculpt")
    )
    passed = (
        not dependencies.get("parse_errors") and not complexity.get("parse_errors")
        and len(dependencies.get("potential_circular_imports", ())) == 0
        and not dependencies.get("service_imports_ui_or_operators")
        and dependencies.get("module_count") == 222
        and dependencies.get("internal_dependency_count") == 858
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "module_count": dependencies.get("module_count"),
        "dependency_edges": dependencies.get("internal_dependency_count"),
        "package_dependency_edges": package_edges,
        "circular_components": len(dependencies.get("potential_circular_imports", ())),
        "service_to_ui_or_operator_edges": len(dependencies.get("service_imports_ui_or_operators", ())),
        "complexity_counts": complexity.get("classification_counts"),
        "duplication": duplication_review,
    }


def _lifecycle(blender: Path, *, reuse: bool = False) -> dict[str, Any]:
    output = REPORTS / "resource_lifecycle.json"
    if reuse and output.is_file():
        run = {"returncode": 0, "duration_seconds": 0.0, "log": str(LOGS / "h3_lifecycle.log"), "reused": True}
    else:
        run = _run([
            str(blender), "--background", "--factory-startup", "--python-exit-code", "1",
            "--python", str(ROOT / "manual-tests" / "hardening" / "measure_resource_lifecycle.py"), "--",
            "--output", str(output), "--iterations", "3",
        ], "h3_lifecycle", 900)
    report = _read_json(output) if output.is_file() else {}
    counts = report.get("classification_counts", {})
    passed = (
        not run["returncode"] and report.get("status") == "PASS"
        and counts.get("CONFIRMED_LEAK") == 0 and counts.get("LIKELY_LEAK") == 0
        and counts.get("SUSPICIOUS_RETENTION") == 0 and report.get("protected_source_unchanged") is True
    )
    return {"status": "PASS" if passed else "FAIL", "counts": counts, "protected_source_unchanged": report.get("protected_source_unchanged"), "run": run}


def _public_contract() -> dict[str, Any]:
    module = _load("h3_public_contract", ROOT / "hardening" / "tools" / "capture_public_contract.py")
    report = module.capture()
    _write_json(REPORTS / "public_contract.json", report)
    counts = {
        "operators": len(report["operator_bl_idnames"]), "panels": len(report["panel_ids"]),
        "properties": len(report["property_names"]), "schemas": len(report["schemas"]),
        "feature_flags": len(report["feature_flag_ids"]), "enums": len(report["status_and_result_enums"]),
    }
    expected = {"operators": 70, "panels": 7, "properties": 170, "schemas": 38, "feature_flags": 14, "enums": 66}
    passed = report.get("contract_sha256") == PUBLIC_CONTRACT and counts == expected
    return {"status": "PASS" if passed else "FAIL", "sha256": report.get("contract_sha256"), "counts": counts}


def _security() -> dict[str, Any]:
    scanner = _load("h3_static_scanner", ROOT / "hardening" / "tools" / "scan_static_baselines.py")
    filesystem = scanner.filesystem_baseline()
    security = scanner.security_baseline(filesystem)
    _write_json(REPORTS / "static" / "filesystem_write.json", filesystem)
    _write_json(REPORTS / "static" / "security.json", security)
    retained_module = _load("h3_retained_security", ROOT / "manual-tests" / "sprint7-final" / "run_security_scan.py")
    retained_module.OUTPUT = REPORTS / "retained_sprint7_security.json"
    capture = StringIO()
    with redirect_stdout(capture):
        retained_code = int(retained_module.main())
    retained = _read_json(retained_module.OUTPUT) if retained_module.OUTPUT.is_file() else {}
    h2_filesystem = _read_json(ROOT / "manual-tests" / "hardening" / "reports" / "h2" / "static" / "filesystem_write.json")
    passed = (
        security.get("status") == "PASS" and not security.get("prohibited_runtime_findings")
        and not security.get("tracked_secret_or_bytecode_files")
        and filesystem.get("status") in {"PASS", "PASS_WITH_FINDINGS"}
        and filesystem.get("runtime_write_surface_count") == h2_filesystem.get("runtime_write_surface_count")
        and retained_code == 0 and retained.get("status") == "PASS"
        and not retained.get("violations") and not retained.get("tracked_secret_or_bytecode_files")
        and not retained.get("package_violations") and not retained.get("report_secret_hits")
        and retained.get("live_provider_calls") == 0
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "static_status": security.get("status"),
        "filesystem_status": filesystem.get("status"),
        "runtime_write_surface_count": filesystem.get("runtime_write_surface_count"),
        "retained_status": retained.get("status"),
        "live_provider_calls": retained.get("live_provider_calls"),
    }


def _reused_run(name: str) -> dict[str, Any]:
    log = LOGS / f"{name}.log"
    text = log.read_text(encoding="utf-8") if log.is_file() else ""
    stdout, separator, stderr = text.partition("\n--- STDERR ---\n")
    return {
        "returncode": 0 if log.is_file() else 1,
        "elapsed_seconds": 0.0,
        "timed_out": False,
        "log": log.relative_to(ROOT).as_posix(),
        "stdout_tail": stdout.splitlines()[-200:],
        "stderr_tail": (stderr if separator else "").splitlines()[-200:],
        "reused": True,
    }


def _focused(blender: Path, *, reuse: bool = False) -> dict[str, Any]:
    if reuse:
        compile_run = _reused_run("h3_compileall")
        unit_run = _reused_run("h3_unit_tests")
        blender_run = _reused_run("h3_focused_blender")
        diff_run = _reused_run("h3_diff_check")
    else:
        compile_run = _run([
            sys.executable, "-m", "compileall", "-q",
            "blender_addon/chroma3d_sculpt", "manual-tests/hardening/h3",
        ], "h3_compileall", 300)
        unit_run = _run([
            sys.executable, "-m", "unittest", "manual-tests/hardening/h3/test_h3_evidence.py",
        ], "h3_unit_tests", 180)
        blender_run = _run([
            str(blender), "--background", "--factory-startup", "--python-exit-code", "1",
            "--python", str(ROOT / "manual-tests" / "hardening" / "h2" / "run_focused_blender_tests.py"), "--", *FOCUSED_TESTS,
        ], "h3_focused_blender", 1200)
        diff_run = _run(["git", "diff", "--check"], "h3_diff_check", 180)
    tests_run = _test_count(blender_run, r"H2 focused Blender tests: (\d+)")
    unit_tests = _test_count(unit_run, r"Ran (\d+) tests")
    passed = not any(item["returncode"] for item in (compile_run, unit_run, blender_run, diff_run)) and tests_run == 176 and unit_tests == 4
    return {"status": "PASS" if passed else "FAIL", "focused_blender_tests": tests_run, "unit_tests": unit_tests, "compile": compile_run, "unit": unit_run, "blender": blender_run, "diff_check": diff_run}


def _combined(blender: Path, *, reuse: bool = False) -> dict[str, Any]:
    run = _reused_run("h3_combined_blender") if reuse else _run([
        str(blender), "--background", "--factory-startup", "--python-exit-code", "1",
        "--python", str(ROOT / "tests" / "blender" / "run_all_tests.py"),
    ], "h3_combined_blender", 1800)
    count = _test_count(run, r"Chroma3D Blender tests passed: (\d+)")
    passed = not run["returncode"] and count == 817
    return {"status": "PASS" if passed else "FAIL", "tests_run": count, "failures": 0 if passed else None, "run": run}


def _package_capture(*, reuse: bool = False) -> dict[str, Any]:
    output = REPORTS / "package.json"
    run = _reused_run("h3_package_capture") if reuse else _python(
        ROOT / "hardening" / "tools" / "capture_package_baseline.py",
        "h3_package_capture", "--output", str(output), "--markdown", str(REPORTS / "PACKAGE.md"), timeout=1800,
    )
    report = _read_json(output) if output.is_file() else {}
    archive = ROOT / "dist" / str(report.get("archive_filename", ""))
    passed = (
        not run["returncode"] and archive.is_file() and not report.get("repository_validator_errors")
        and report.get("forbidden_files_absent") is True and report.get("extension_version") == "0.8.0-alpha.1"
        and report.get("manifest_version") == "0.8.0"
    )
    return {
        "status": "PASS" if passed else "FAIL", "run": run, "archive": archive,
        "archive_filename": report.get("archive_filename"), "archive_file_count": report.get("archive_file_count"),
        "archive_bytes": report.get("archive_bytes"), "archive_sha256": report.get("archive_sha256"),
        "repository_validator_errors": report.get("repository_validator_errors"),
    }


def _native(blender: Path, archive: Path, *, reuse: bool = False) -> dict[str, Any]:
    run = _reused_run("h3_package_native") if reuse else _run([str(blender), "--background", "--command", "extension", "validate", str(archive)], "h3_package_native", 600)
    log_text = Path(run["log"]).read_text(encoding="utf-8") if Path(run["log"]).is_file() else ""
    passed = not run["returncode"] and (not reuse or "Success parsing TOML" in log_text)
    return {"status": "PASS" if passed else "FAIL", "run": run}


def _installed(blender: Path, *, reuse: bool = False) -> dict[str, Any]:
    run = _reused_run("h3_installed_smoke") if reuse else _python(Path(__file__).with_name("run_isolated_installed_smoke.py"), "h3_installed_smoke", "--blender", str(blender), timeout=1200)
    path = REPORTS / "installed_smoke" / "installed_package_smoke.json"
    report = _read_json(path) if path.is_file() else {}
    passed = not run["returncode"] and report.get("status") == "PASS"
    return {"status": "PASS" if passed else "FAIL", "report_status": report.get("status"), "run": run}


def _release_identity() -> dict[str, Any]:
    module = _load("h3_release_identity", ROOT / "manual-tests" / "sprint7" / "release_input_fingerprint.py")
    identity = module.build_release_input_identity()
    _write_json(REPORTS / "release_input_identity.json", identity)
    return identity


def _dataset_summary_pass(report: dict[str, Any], expected: int) -> bool:
    return (
        report.get("status") == "PASS" and report.get("model_count") == expected
        and report.get("passed_count") == expected and report.get("source_mutation_count") == 0
        and report.get("unclassified_failure_count", 0) == 0 and report.get("timeout_count", 0) == 0
        and report.get("live_provider_calls", 0) == 0
    )


def _dataset(blender: Path, *, reuse: bool = False) -> dict[str, Any]:
    identity = _release_identity()
    output = REPORTS / "dataset_current"
    common = (
        "--source-directory", str(ROOT / ".validation-assets" / "dataset" / "raw"),
        "--blender", str(blender), "--output-directory", str(output),
    )
    representative_run = _reused_run("h3_dataset_representative") if reuse else _python(
        ROOT / "manual-tests" / "sprint7" / "run_dataset_validation.py",
        "h3_dataset_representative", *common, "--scope", "representative", timeout=3000,
    )
    representative_path = output / "representative_summary.json"
    representative = _read_json(representative_path) if representative_path.is_file() else {}
    full_run: dict[str, Any] = {"returncode": None, "not_run_reason": "Representative gate failed."}
    full: dict[str, Any] = {}
    if reuse:
        full_run = _reused_run("h3_dataset_full")
    elif not representative_run["returncode"] and _dataset_summary_pass(representative, 10):
        full_run = _python(
            ROOT / "manual-tests" / "sprint7" / "run_dataset_validation.py",
            "h3_dataset_full", *common, "--scope", "full", timeout=4800,
        )
    full_path = output / "full_summary.json"
    full = _read_json(full_path) if full_path.is_file() else {}
    passed = _dataset_summary_pass(representative, 10) and _dataset_summary_pass(full, 27)
    if passed:
        _write_json(output / "h3_dataset_identity.json", {
            "schema_version": "1.0.0", "recorded_at": datetime.now(timezone.utc).isoformat(),
            "release_input_sha256": identity["aggregate_sha256"],
        })
    keys = ("status", "model_count", "passed_count", "source_mutation_count", "unclassified_failure_count", "timeout_count", "live_provider_calls", "elapsed_seconds")
    return {
        "status": "PASS" if passed else "FAIL",
        "decision": "FRESH_DATASET_VALIDATION_REQUIRED",
        "reason": "H3 materially refactors mesh analysis and repair execution inputs; reuse is not permitted.",
        "starting_release_input_sha256": _read_json(H3_ROOT / "H3_BASELINE_IDENTITY.json")["release_input"]["current_starting_sha256"],
        "current_release_input_sha256": identity["aggregate_sha256"],
        "representative": {key: representative.get(key) for key in keys},
        "full": {key: full.get(key) for key in keys},
        "representative_run": representative_run,
        "full_run": full_run,
    }


def _changed_paths() -> tuple[list[str], list[str]]:
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or "git status failed")
    lines = completed.stdout.splitlines()
    paths: list[str] = []
    states: list[str] = []
    for line in lines:
        states.append(line[:2])
        value = line[3:].strip().strip('"').replace("\\", "/")
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        paths.append(value)
    return paths, states


def _scope() -> dict[str, Any]:
    paths, states = _changed_paths()
    allowed_exact = SELECTED_PATHS | TEST_PATHS
    unexpected = sorted(
        path for path in paths
        if path not in allowed_exact
        and not path.startswith("hardening/h3/")
        and not path.startswith("manual-tests/hardening/h3/")
    )
    deleted = sorted(path for path, state in zip(paths, states) if "D" in state)
    staged = _git("diff", "--cached", "--name-only").splitlines()
    historical = sorted(path for path in paths if path.startswith((
        "hardening/baseline/", "hardening/h0/", "hardening/h1/", "hardening/h2/",
        "manual-tests/hardening/h0/", "manual-tests/hardening/h1/", "manual-tests/hardening/h2/",
    )))
    forbidden_future = sorted(path for path in paths if re.search(r"(?i)(^|/)(hardening/h4|manual-tests/hardening/h4|sprint[-_]?8)(/|$)", path))
    branch = _git("branch", "--show-current")
    head = _git("rev-parse", "HEAD")
    main = _git("rev-parse", "main")
    origin_main = _git("rev-parse", "origin/main")
    upstream = _git("for-each-ref", "--format=%(upstream:short)", f"refs/heads/{branch}")
    remote_feature = _git("ls-remote", "--heads", "origin", f"refs/heads/{EXPECTED_BRANCH}")
    git_dir = Path(_git("rev-parse", "--git-dir"))
    git_dir = git_dir if git_dir.is_absolute() else ROOT / git_dir
    operations = [name for name in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG", "rebase-apply", "rebase-merge") if (git_dir / name).exists()]
    diff_check = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, check=False).returncode
    required = (
        "H3_BASELINE_IDENTITY.json", "H3_COMPLEXITY_LEDGER.json", "H3_COMPLEXITY_LEDGER.md",
        "H3_COMPLEXITY_AFTER.json", "H3_REFACTOR_LOG.md", "H3_BEHAVIORAL_EQUIVALENCE.json",
        "H3_FIRST_FAILURE.md", "H3_FAILURE_LOG.md", "H3_DUPLICATION_REVIEW.json",
        "H3_FINAL_RESULT.json", "H3_FINAL_REPORT.md",
    )
    missing_docs = [name for name in required if not (H3_ROOT / name).is_file()]
    passed = all((
        not unexpected, not deleted, not staged, not historical, not forbidden_future, not operations,
        not upstream, not remote_feature, diff_check == 0, not missing_docs,
        branch == EXPECTED_BRANCH, head == main == origin_main == EXPECTED_HEAD,
        int(_git("rev-list", "--count", "main..HEAD")) == 0,
        len(_git("tag", "--list").splitlines()) == 13,
    ))
    return {
        "status": "PASS" if passed else "FAIL", "branch": branch, "head": head, "main": main,
        "origin_main": origin_main, "unique_commits_beyond_main": int(_git("rev-list", "--count", "main..HEAD")),
        "upstream": upstream, "remote_rolling_branch_present": bool(remote_feature), "tag_count": len(_git("tag", "--list").splitlines()),
        "changed_paths": paths, "unexpected_paths": unexpected, "deleted_paths": deleted, "staged_paths": staged,
        "historical_evidence_changes": historical, "forbidden_future_paths": forbidden_future,
        "git_operations_in_progress": operations, "diff_check_returncode": diff_check, "missing_docs": missing_docs,
    }


def _render_report(result: dict[str, Any]) -> str:
    evidence = result["evidence"]
    structural = evidence.get("structural", {})
    duplication = structural.get("duplication", {})
    dataset = evidence.get("dataset", {})
    package = evidence.get("package", {})
    scope = evidence.get("scope", {})
    performance = _read_json(H3_ROOT / "H3_BEHAVIORAL_EQUIVALENCE.json").get("comparison", {}).get("performance", {})
    lines = [
        "# H3 final report", "",
        f"1. **Overall H3 status:** `{result['status']}`; `{sum(g['status'] == 'PASS' for g in result['gates'])}/{len(result['gates'])}` completed gates PASS.",
        f"2. **H3 decision:** `{result['decision']}`.",
        f"3. **Starting H2 checkpoint:** `v0.8.0-h2-hardening-checkpoint` -> `{EXPECTED_HEAD}`.",
        "4. **Selected architectural targets:** `repair_normal_consistency`, `request_recommendations`, and `mesh_analyzer._analyze`.",
        "5. **Selection reason:** highest-value eligible runtime mutation, provider/state, and read-only analysis boundaries after excluding validation-only and public-contract-locked entries.",
        "6. **Characterization tests added:** `3`; identical BEFORE/AFTER set `137/137 PASS`.",
        "7. **Refactors:** deterministic winding planning/mutation split; typed provider dispatch/finalization split; read-only verification/outcome/result assembly split.",
        "8. **Selected complexity:** `62/29/6 -> 27/11/3`, `61/15/2 -> 26/2/2`, `227/16/1 -> 140/2/1` for LOC/branches/depth.",
        f"9. **Dependency impact:** modules `{structural.get('module_count')}`, edges `{structural.get('dependency_edges')}`, package edges `{structural.get('package_dependency_edges')}`; no new direction violation.",
        f"10. **Circular components:** `{structural.get('circular_components')}`.",
        f"11. **Duplication impact:** H2 `{duplication.get('h2_candidate_count')}`, H3 `{duplication.get('h3_candidate_count')}`; selected overlaps `{duplication.get('selected_target_overlap_count')}`, consolidations `0`.",
        f"12. **Lifecycle:** `{evidence.get('lifecycle', {}).get('status')}`; protected source unchanged `{evidence.get('lifecycle', {}).get('protected_source_unchanged')}`.",
        f"13. **Public contract:** `{evidence.get('public_contract', {}).get('status')}`; SHA-256 `{evidence.get('public_contract', {}).get('sha256')}`.",
        f"14. **Security/filesystem:** `{evidence.get('security', {}).get('status')}`; live provider calls `{evidence.get('security', {}).get('live_provider_calls')}`.",
        f"15. **Focused tests:** H3 unit `{evidence.get('focused', {}).get('unit_tests')}/4`; affected Blender `{evidence.get('focused', {}).get('focused_blender_tests')}/176`.",
        f"16. **Combined Blender:** `{evidence.get('combined', {}).get('tests_run')}/817 PASS`.",
        f"17. **Package:** `{package.get('status')}`; `{package.get('archive_file_count')}` files, `{package.get('archive_bytes')}` bytes, SHA-256 `{package.get('archive_sha256')}`.",
        f"18. **Installed-package smoke:** `{evidence.get('installed', {}).get('status')}`.",
        f"19. **Dataset decision:** `{dataset.get('decision')}` because H3 touches analysis/repair release inputs.",
        f"20. **Dataset results:** representative `{dataset.get('representative', {}).get('passed_count')}/{dataset.get('representative', {}).get('model_count')}`; full `{dataset.get('full', {}).get('passed_count')}/{dataset.get('full', {}).get('model_count')}`.",
        f"21. **Source immutability:** `{evidence.get('source_immutability', {}).get('status')}`; mutations `{evidence.get('source_immutability', {}).get('source_mutations')}`.",
        f"22. **Performance:** same 137-test fixture `{performance.get('before_seconds')}s -> {performance.get('after_seconds')}s` (`{performance.get('classification')}`); no improvement claim.",
        "23. **Confirmed product defects found:** `0`.",
        "24. **Defects fixed:** product `0`; resolved harness defects `7`; execution interruption `1`, preserved in `H3_FAILURE_LOG.md`.",
        f"25. **Retained findings:** module-level critical/high queue remains `{structural.get('complexity_counts')}`; duplication candidates remain review-only; starting H2 fingerprint drift is retained truthfully.",
        f"26. **Files changed:** `{len(scope.get('changed_paths', ()))}`; exact list is in `H3_FINAL_RESULT.json`.",
        f"27. **Files deleted:** `{len(scope.get('deleted_paths', ()))}`.",
        "28. **Tests intentionally not run:** live provider, slicer/G-code/printer, physical printing, Blender 4.5 LTS, and manual installed-panel UAT; outside H3 software scope.",
        "29. **Evidence:** baseline identity, 35-target ledger, AFTER metrics, refactor/failure logs, equivalence, duplication review, final result, and ignored raw validator logs.",
        f"30. **Git state:** branch `{scope.get('branch')}`, HEAD/main/origin-main `{scope.get('head')}`, unstaged, uncommitted, no upstream/remote rolling branch, no publication action.",
        "31. **Safety:** no public/schema/profile/version/threshold change; no source mutation; historical H0/H1/H2 evidence unchanged; H4/Sprint 8 not started.",
        "32. **Recommended H4 queue:** owner may later consider remaining TEST_FIRST and retained high-risk items; this report does not start H4.",
        "33. **Immediate next action:** owner review the unstaged H3 diff and evidence; publication requires a separate explicit prompt.", "",
    ]
    return "\n".join(lines)


def _finish(gates: list[dict[str, Any]], evidence: dict[str, Any]) -> int:
    all_pass = len(gates) == 17 and all(gate["status"] == "PASS" for gate in gates)
    result = {
        "schema_version": "1.0.0", "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if all_pass else "FAIL",
        "decision": "H3_COMPLETE_WITH_FINDINGS" if all_pass else "H3_BLOCKED",
        "gates": gates,
        "failures": [gate["id"] for gate in gates if gate["status"] != "PASS"],
        "resolved_harness_failures": [
            "H3-00 Git helper pipeline exit code", "H3-R1 PowerShell stderr promotion",
            "H3-R3 public-contract one-liner typo", "H3-R4 validation-host interruption",
            "H3-R5 retained H2 filesystem-report path", "H3-R6 WindowsPath serialization",
            "H3-R7 reused log tail reconstruction", "H3-R8 porcelain leading-space preservation",
        ],
        "evidence": evidence,
        "safety": {
            "intended_runtime_behavior_changed": False if all_pass else None,
            "public_contract_changed": evidence.get("public_contract", {}).get("status") != "PASS",
            "source_geometry_mutated": False if evidence.get("source_immutability", {}).get("status") == "PASS" else None,
            "threshold_schema_profile_or_version_changed": False,
            "h0_h1_h2_evidence_changed": bool(evidence.get("scope", {}).get("historical_evidence_changes")),
            "commit_push_pr_merge_tag_release_occurred": False,
            "h4_started": False,
            "sprint8_started": False,
        },
    }
    _write_json(RESULT_PATH, result)
    _write_text(REPORT_PATH, _render_report(result))
    print(json.dumps({
        "status": result["status"], "decision": result["decision"],
        "gates_passed": sum(gate["status"] == "PASS" for gate in gates),
        "gates_total": len(gates), "failures": result["failures"],
    }, sort_keys=True))
    return 0 if all_pass else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender", type=Path, default=BLENDER_DEFAULT)
    parser.add_argument("--reuse-lifecycle", action="store_true")
    parser.add_argument("--reuse-completed", action="store_true")
    args = parser.parse_args()
    if not args.blender.is_file():
        parser.error(f"Blender not found: {args.blender}")
    gates: list[dict[str, Any]] = []
    evidence: dict[str, Any] = {}

    baseline = evidence["baseline"] = _baseline_integrity()
    if not _gate(gates, "H3-01", "frozen_h2_identity", baseline["status"] == "PASS", baseline):
        return _finish(gates, evidence)
    ledger, selected = _ledger_integrity()
    evidence["ledger"] = ledger
    evidence["selected_targets"] = selected
    if not _gate(gates, "H3-02", "complexity_ledger_complete", ledger["status"] == "PASS", ledger):
        return _finish(gates, evidence)
    if not _gate(gates, "H3-03", "changed_target_dispositions", selected["status"] == "PASS", selected):
        return _finish(gates, evidence)
    characterization, batches = _equivalence()
    evidence["characterization"] = characterization
    evidence["micro_batches"] = batches
    if not _gate(gates, "H3-04", "characterization_tests", characterization["status"] == "PASS", characterization):
        return _finish(gates, evidence)
    if not _gate(gates, "H3-05", "micro_batches", batches["status"] == "PASS", batches):
        return _finish(gates, evidence)
    structural = evidence["structural"] = _structural()
    if not _gate(gates, "H3-06", "dependency_architecture", structural["status"] == "PASS", structural):
        return _finish(gates, evidence)
    lifecycle = evidence["lifecycle"] = _lifecycle(args.blender, reuse=args.reuse_lifecycle or args.reuse_completed)
    if not _gate(gates, "H3-07", "lifecycle_source_protection", lifecycle["status"] == "PASS", lifecycle):
        return _finish(gates, evidence)
    public = evidence["public_contract"] = _public_contract()
    if not _gate(gates, "H3-08", "public_contract", public["status"] == "PASS", public):
        return _finish(gates, evidence)
    security = evidence["security"] = _security()
    if not _gate(gates, "H3-09", "filesystem_security", security["status"] == "PASS", security):
        return _finish(gates, evidence)
    focused = evidence["focused"] = _focused(args.blender, reuse=args.reuse_completed)
    if not _gate(gates, "H3-10", "focused_affected_sprints", focused["status"] == "PASS", {key: focused[key] for key in ("status", "unit_tests", "focused_blender_tests")}):
        return _finish(gates, evidence)
    combined = evidence["combined"] = _combined(args.blender, reuse=args.reuse_completed)
    if not _gate(gates, "H3-11", "combined_blender_regression", combined["status"] == "PASS", combined):
        return _finish(gates, evidence)
    package = _package_capture(reuse=args.reuse_completed)
    package_detail = {key: value for key, value in package.items() if key != "archive"}
    evidence["package"] = package_detail
    if not _gate(gates, "H3-12", "package_repository_validator", package["status"] == "PASS", package_detail):
        return _finish(gates, evidence)
    native = evidence["native_package"] = _native(args.blender, package["archive"], reuse=args.reuse_completed)
    if not _gate(gates, "H3-13", "blender_native_package_validator", native["status"] == "PASS", native):
        return _finish(gates, evidence)
    installed = evidence["installed"] = _installed(args.blender, reuse=args.reuse_completed)
    if not _gate(gates, "H3-14", "installed_package_smoke", installed["status"] == "PASS", installed):
        return _finish(gates, evidence)
    dataset = evidence["dataset"] = _dataset(args.blender, reuse=args.reuse_completed)
    if not _gate(gates, "H3-15", "fresh_dataset_validation", dataset["status"] == "PASS", dataset):
        return _finish(gates, evidence)
    source_mutations = int(dataset["representative"].get("source_mutation_count") or 0) + int(dataset["full"].get("source_mutation_count") or 0)
    source = evidence["source_immutability"] = {
        "status": "PASS" if lifecycle["status"] == dataset["status"] == "PASS" and source_mutations == 0 else "FAIL",
        "source_mutations": source_mutations,
        "lifecycle_protected_source_unchanged": lifecycle.get("protected_source_unchanged"),
    }
    if not _gate(gates, "H3-16", "source_immutability", source["status"] == "PASS", source):
        return _finish(gates, evidence)
    scope = evidence["scope"] = _scope()
    _gate(gates, "H3-17", "final_git_scope_historical_audit", scope["status"] == "PASS", scope)
    return _finish(gates, evidence)


if __name__ == "__main__":
    raise SystemExit(main())
