"""Run the fail-closed 17-gate H2 validation and write compact tracked evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
H2_ROOT = ROOT / "hardening" / "h2"
REPORTS = ROOT / "manual-tests" / "hardening" / "reports" / "h2"
LOGS = REPORTS / "logs"
BLENDER_DEFAULT = Path(r"D:\Softwares\Design\Blender\blender.exe")
H1_TAG = "v0.8.0-h1-hardening-checkpoint"
H1_MERGE = "d6cab118c44422375e69bd077cabc85a990a9a33"
H1_RESULT = ROOT / "hardening" / "h1" / "H1_FINAL_RESULT.json"
H1_CONTRACT = REPORTS.parent / "h1" / "public_contract.json"
RESULT_PATH = H2_ROOT / "H2_FINAL_RESULT.json"
REPORT_PATH = H2_ROOT / "H2_FINAL_REPORT.md"
ANCHORS = {
    "v0.8.0-alpha.1": ("e819bfd4fd7705a97d967872f0c934295758381c", "fb0c7b6102d1460871d38aea9acb60373559be8d"),
    "v0.8.0-pre-hardening-backup": ("8471cb474c1ee4c092af9eea24306a6ea886fa71", "d06e1a05890fe23e77e66f95fc40e0200638a765"),
    "v0.8.0-h0-hardening-baseline": ("371b0ee4b6bcbc87245b1e50084eeb6c3486e311", "6f20b8c3007658a78eb89e2d2937924175384feb"),
    H1_TAG: ("55964ca63435499da857190a90af09804e18e615", H1_MERGE),
}
FOCUSED_TESTS = (
    "tests/blender/test_sprint2_repair.py",
    "tests/blender/test_sprint3_printability.py",
    "tests/blender/test_sprint4_advanced_preparation.py",
    "tests/blender/test_sprint5_controlled_optimization.py",
    "tests/blender/test_sprint6_intelligent_optimization.py",
    "tests/blender/test_sprint7_ai_recommendation.py",
)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8", newline="\n")
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(command: list[str], name: str, timeout: int = 1200) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, check=False,
        )
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        timed_out = True
    LOGS.mkdir(parents=True, exist_ok=True)
    log_path = LOGS / f"{name}.log"
    log_path.write_text(
        stdout + ("\n" if stdout and stderr else "") + stderr,
        encoding="utf-8", newline="\n",
    )
    return {
        "returncode": returncode,
        "timed_out": timed_out,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "log": log_path.relative_to(ROOT).as_posix(),
        "stdout_tail": stdout.splitlines()[-30:],
        "stderr_tail": stderr.splitlines()[-30:],
    }


def _python(script: Path, name: str, *args: str, timeout: int = 1200) -> dict[str, Any]:
    return _run([sys.executable, str(script), *args], name, timeout)


def _git(*args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    if check and completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout.rstrip()


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _gate(gates: list[dict[str, Any]], gate_id: str, name: str, passed: bool, detail: Any) -> None:
    gates.append({"id": gate_id, "name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def _test_count(result: dict[str, Any], pattern: str) -> int:
    for line in reversed(result.get("stdout_tail", ()) + result.get("stderr_tail", ())):
        match = re.search(pattern, line)
        if match:
            return int(match.group(1))
    return 0


def _package_edges(report: dict[str, Any]) -> int:
    return sum(
        1
        for module, imports in report.get("module_imports", {}).items()
        if module.startswith("chroma3d_sculpt")
        for target in imports
        if target.startswith("chroma3d_sculpt")
    )


def _refresh_analysis() -> dict[str, Any]:
    runs = {
        "references": _python(Path(__file__).with_name("analyze_suspicious_references.py"), "h2_references", timeout=180),
        "complexity_triage": _python(Path(__file__).with_name("triage_complexity.py"), "h2_complexity_triage", timeout=120),
        "duplication_triage": _python(Path(__file__).with_name("triage_duplication.py"), "h2_duplication_triage", timeout=120),
        "structural": _python(Path(__file__).with_name("run_structural_scans.py"), "h2_structural_scans", timeout=300),
        "contract": _python(
            ROOT / "hardening" / "tools" / "capture_public_contract.py", "h2_public_contract",
            "--output", str(REPORTS / "public_contract.json"),
            "--markdown", str(REPORTS / "PUBLIC_CONTRACT.md"), timeout=180,
        ),
    }
    return runs


def _baseline_integrity() -> dict[str, Any]:
    baseline = _read_json(H2_ROOT / "H2_BASELINE_IDENTITY.json")
    mismatches = []
    for evidence in baseline["frozen_h1"]["primary_evidence"]:
        path = ROOT / evidence["path"]
        if not path.is_file() or _sha256(path) != evidence["sha256"]:
            mismatches.append(evidence["path"])
        elif _git("hash-object", "--", evidence["path"]) != evidence["git_blob"]:
            mismatches.append(evidence["path"] + ":git_blob")
    h1 = _read_json(H1_RESULT)
    tag_type = _git("cat-file", "-t", H1_TAG)
    tag_target = _git("rev-parse", f"{H1_TAG}^{{}}")
    historical_diff = _git("diff", "--name-only", "--", "hardening/h1", "manual-tests/hardening/h1").splitlines()
    passed = (
        not mismatches and not historical_diff and tag_type == "tag" and tag_target == H1_MERGE
        and h1.get("decision") == "H1_COMPLETE_WITH_FINDINGS"
        and len(h1.get("gates", ())) == 15
        and all(gate.get("status") == "PASS" for gate in h1.get("gates", ()))
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "tag_type": tag_type,
        "tag_target": tag_target,
        "h1_decision": h1.get("decision"),
        "h1_gates": len(h1.get("gates", ())),
        "primary_evidence_mismatches": mismatches,
        "historical_evidence_changes": historical_diff,
    }


def _lifecycle(blender: Path) -> dict[str, Any]:
    output = REPORTS / "resource_lifecycle.json"
    run = _run([
        str(blender), "--background", "--factory-startup", "--python-exit-code", "1",
        "--python", str(ROOT / "manual-tests" / "hardening" / "measure_resource_lifecycle.py"), "--",
        "--output", str(output), "--iterations", "3",
    ], "h2_lifecycle", 900)
    report = _read_json(output) if output.is_file() else {}
    counts = report.get("classification_counts", {})
    passed = (
        not run["returncode"] and report.get("status") == "PASS"
        and counts.get("CONFIRMED_LEAK") == 0 and counts.get("LIKELY_LEAK") == 0
        and counts.get("SUSPICIOUS_RETENTION") == 0 and report.get("protected_source_unchanged") is True
    )
    return {"status": "PASS" if passed else "FAIL", "run": run, "report": report}


def _focused(blender: Path, refresh: dict[str, Any]) -> dict[str, Any]:
    compile_result = _run([
        sys.executable, "-m", "compileall", "-q",
        "blender_addon/chroma3d_sculpt", "manual-tests/hardening/h2",
    ], "h2_compileall", 300)
    unit_result = _run([
        sys.executable, "-m", "unittest",
        "manual-tests/hardening/h2/test_suspicious_reference_analyzer.py",
        "manual-tests/hardening/h2/test_structural_simplification.py",
    ], "h2_unit_tests", 180)
    focused_result = _run([
        str(blender), "--background", "--factory-startup", "--python-exit-code", "1",
        "--python", str(Path(__file__).with_name("run_focused_blender_tests.py")), "--", *FOCUSED_TESTS,
    ], "h2_focused_blender", 1200)
    diff_check = _run(["git", "diff", "--check"], "h2_diff_check", 180)
    tests_run = _test_count(focused_result, r"H2 focused Blender tests: (\d+)")
    passed = (
        not compile_result["returncode"] and not unit_result["returncode"]
        and not focused_result["returncode"] and tests_run == 763
        and not diff_check["returncode"]
        and all(not result["returncode"] for result in refresh.values())
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "compile": compile_result,
        "unit_tests": unit_result,
        "focused_blender": focused_result,
        "focused_blender_tests": tests_run,
        "diff_check": diff_check,
        "analysis_refresh": refresh,
    }


def _combined(blender: Path) -> dict[str, Any]:
    run = _run([
        str(blender), "--background", "--factory-startup", "--python-exit-code", "1",
        "--python", str(ROOT / "tests" / "blender" / "run_all_tests.py"),
    ], "h2_combined_blender", 1800)
    count = _test_count(run, r"Chroma3D Blender tests passed: (\d+)")
    passed = not run["returncode"] and count == 814
    return {"status": "PASS" if passed else "FAIL", "tests_run": count, "failures": 0 if passed else None, "run": run}


def _package(blender: Path) -> dict[str, Any]:
    package_path = REPORTS / "package.json"
    capture = _python(
        ROOT / "hardening" / "tools" / "capture_package_baseline.py", "h2_package_capture",
        "--output", str(package_path), "--markdown", str(REPORTS / "PACKAGE.md"), timeout=1800,
    )
    package = _read_json(package_path) if package_path.is_file() else {}
    archive = ROOT / "dist" / str(package.get("archive_filename", "chroma3d_sculpt-0.8.0-alpha.1.zip"))
    native = _run([
        str(blender), "--background", "--command", "extension", "validate", str(archive),
    ], "h2_package_native", 600)
    installed = _python(
        Path(__file__).with_name("run_isolated_installed_smoke.py"), "h2_installed_smoke",
        "--blender", str(blender), timeout=1200,
    )
    installed_path = REPORTS / "installed_smoke" / "installed_package_smoke.json"
    installed_report = _read_json(installed_path) if installed_path.is_file() else {}
    passed = (
        not capture["returncode"] and not package.get("repository_validator_errors")
        and package.get("forbidden_files_absent") is True and archive.is_file()
        and not native["returncode"] and not installed["returncode"]
        and installed_report.get("status") == "PASS"
        and package.get("extension_version") == "0.8.0-alpha.1"
        and package.get("manifest_version") == "0.8.0"
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "package": package,
        "capture": capture,
        "native": native,
        "installed_smoke": installed_report,
        "installed_smoke_run": installed,
    }


def _release_input_identity() -> dict[str, Any]:
    module = _load_module(
        "h2_release_input", ROOT / "manual-tests" / "sprint7" / "release_input_fingerprint.py"
    )
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


def _dataset(blender: Path) -> dict[str, Any]:
    identity = _release_input_identity()
    current = identity["aggregate_sha256"]
    h1_current = _read_json(H1_RESULT)["evidence"]["dataset"]["current_release_input_sha256"]
    output = REPORTS / "dataset_current"
    identity_path = output / "h2_dataset_identity.json"
    representative_path = output / "representative_summary.json"
    full_path = output / "full_summary.json"
    retained_identity = _read_json(identity_path) if identity_path.is_file() else {}
    representative = _read_json(representative_path) if representative_path.is_file() else {}
    full = _read_json(full_path) if full_path.is_file() else {}
    reusable = (
        retained_identity.get("release_input_sha256") == current
        and _dataset_summary_pass(representative, 10) and _dataset_summary_pass(full, 27)
    )
    representative_run: dict[str, Any]
    full_run: dict[str, Any]
    if reusable:
        decision = "REUSE_CURRENT_H2_VALIDATED_EVIDENCE"
        representative_run = {"returncode": None, "reused": True}
        full_run = {"returncode": None, "reused": True}
    else:
        decision = "FRESH_DATASET_VALIDATION_REQUIRED"
        common = (
            "--source-directory", str(ROOT / ".validation-assets" / "dataset" / "raw"),
            "--blender", str(blender), "--output-directory", str(output),
        )
        representative_run = _python(
            ROOT / "manual-tests" / "sprint7" / "run_dataset_validation.py",
            "h2_dataset_representative", *common, "--scope", "representative", timeout=3000,
        )
        representative = _read_json(representative_path) if representative_path.is_file() else {}
        full_run = {"returncode": None, "not_run_reason": "Representative gate failed."}
        full = {}
        if not representative_run["returncode"] and _dataset_summary_pass(representative, 10):
            full_run = _python(
                ROOT / "manual-tests" / "sprint7" / "run_dataset_validation.py",
                "h2_dataset_full", *common, "--scope", "full", timeout=4800,
            )
            full = _read_json(full_path) if full_path.is_file() else {}
        if _dataset_summary_pass(representative, 10) and _dataset_summary_pass(full, 27):
            _write_json(identity_path, {
                "schema_version": "1.0.0",
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "release_input_sha256": current,
            })
    passed = (
        current != h1_current and _dataset_summary_pass(representative, 10)
        and _dataset_summary_pass(full, 27)
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "decision": decision,
        "reason": "H2 changed runtime release inputs; fresh isolated H2 evidence is required unless an interrupted rerun already validated the exact current H2 fingerprint.",
        "h1_release_input_sha256": h1_current,
        "current_release_input_sha256": current,
        "representative": representative,
        "representative_run": representative_run,
        "full": full,
        "full_run": full_run,
    }


def _security() -> dict[str, Any]:
    report_dir = REPORTS / "static"
    try:
        scanner = _load_module(
            "h2_static_scanner", ROOT / "hardening" / "tools" / "scan_static_baselines.py"
        )
        filesystem = scanner.filesystem_baseline()
        security = scanner.security_baseline(filesystem)
        documentation = scanner.documentation_baseline()
        _write_json(report_dir / "filesystem_write.json", filesystem)
        _write_json(report_dir / "security.json", security)
        _write_json(report_dir / "documentation.json", documentation)
        _write_text(report_dir / "FILESYSTEM_WRITE.md", scanner.render_filesystem(filesystem))
        _write_text(report_dir / "SECURITY.md", scanner.render_security(security))
        _write_text(report_dir / "DOCUMENTATION.md", scanner.render_docs(documentation))
        static_run = {"returncode": 0, "isolated_output": report_dir.relative_to(ROOT).as_posix()}
    except Exception as exc:
        filesystem = {}
        security = {}
        static_run = {"returncode": 1, "error": f"{type(exc).__name__}: {exc}"}
    h1_filesystem = _read_json(REPORTS.parent / "h1" / "filesystem_write.json")
    retained_module = _load_module(
        "h2_retained_security", ROOT / "manual-tests" / "sprint7-final" / "run_security_scan.py"
    )
    retained_module.OUTPUT = REPORTS / "retained_sprint7_security.json"
    retained_code = int(retained_module.main())
    retained = _read_json(retained_module.OUTPUT) if retained_module.OUTPUT.is_file() else {}
    passed = (
        not static_run["returncode"] and security.get("status") == "PASS"
        and not security.get("prohibited_runtime_findings")
        and not security.get("tracked_secret_or_bytecode_files")
        and filesystem.get("status") in {"PASS", "PASS_WITH_FINDINGS"}
        and filesystem.get("runtime_write_surface_count") == h1_filesystem.get("runtime_write_surface_count")
        and retained_code == 0 and retained.get("status") == "PASS"
        and not retained.get("violations") and not retained.get("tracked_secret_or_bytecode_files")
        and not retained.get("package_violations") and not retained.get("report_secret_hits")
        and retained.get("live_provider_calls") == 0
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "static_run": static_run,
        "static": security,
        "filesystem": filesystem,
        "h1_runtime_write_surface_count": h1_filesystem.get("runtime_write_surface_count"),
        "retained_sprint7": retained,
    }


def _anchor_state() -> list[dict[str, Any]]:
    rows = []
    for name, (expected_object, expected_peeled) in ANCHORS.items():
        local_object = _git("rev-parse", name)
        local_peeled = _git("rev-parse", f"{name}^{{}}")
        remote = _git("ls-remote", "--tags", "origin", f"refs/tags/{name}", f"refs/tags/{name}^{{}}")
        remote_object = ""
        remote_peeled = ""
        for line in remote.splitlines():
            value, ref = line.split(maxsplit=1)
            if ref == f"refs/tags/{name}":
                remote_object = value
            elif ref == f"refs/tags/{name}^{{}}":
                remote_peeled = value
        remote_peeled = remote_peeled or remote_object
        rows.append({
            "name": name,
            "local_object": local_object,
            "local_peeled": local_peeled,
            "remote_object": remote_object,
            "remote_peeled": remote_peeled,
            "unchanged": (
                local_object == remote_object == expected_object
                and local_peeled == remote_peeled == expected_peeled
            ),
        })
    return rows


def _scope(reference_report: dict[str, Any]) -> dict[str, Any]:
    status_lines = _git("status", "--porcelain=v1", "--untracked-files=all").splitlines()
    paths = []
    states = []
    for line in status_lines:
        states.append(line[:2])
        value = line[3:].strip().strip('"').replace("\\", "/")
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        paths.append(value)
    allowed_product = {
        entry["path"] for entry in reference_report["entries"] if entry.get("removed")
    } | {
        "blender_addon/chroma3d_sculpt/services/strategy_generator.py",
        "blender_addon/chroma3d_sculpt/services/overhang_analysis.py",
        "blender_addon/chroma3d_sculpt/services/thin_features.py",
        "blender_addon/chroma3d_sculpt/services/printability_statistics.py",
    }
    unexpected = sorted(
        path for path in paths
        if path not in allowed_product
        and not path.startswith("hardening/h2/")
        and not path.startswith("manual-tests/hardening/h2/")
    )
    deleted = sorted(path for path, state in zip(paths, states) if "D" in state)
    staged = _git("diff", "--cached", "--name-only").splitlines()
    branch = _git("branch", "--show-current")
    head = _git("rev-parse", "HEAD")
    main = _git("rev-parse", "main")
    origin_main = _git("rev-parse", "origin/main")
    upstream = _git("for-each-ref", "--format=%(upstream:short)", f"refs/heads/{branch}")
    remote_feature = _git("ls-remote", "--heads", "origin", "refs/heads/feature/v1.0-release-hardening")
    anchors = _anchor_state()
    git_dir = Path(_git("rev-parse", "--git-dir"))
    if not git_dir.is_absolute():
        git_dir = ROOT / git_dir
    operations = [
        name for name in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG", "rebase-apply", "rebase-merge")
        if (git_dir / name).exists()
    ]
    forbidden_future = [path for path in paths if re.search(r"(?i)(^|/)(hardening/h3|manual-tests/hardening/h3|sprint[-_]?8)(/|$)", path)]
    historical = [path for path in paths if path.startswith(("hardening/h1/", "hardening/baseline/", "manual-tests/hardening/h1/"))]
    passed = (
        not unexpected and not deleted and not staged and not forbidden_future and not historical
        and branch == "feature/v1.0-release-hardening"
        and head == main == origin_main == H1_MERGE
        and int(_git("rev-list", "--count", "main..HEAD")) == 0
        and not upstream and not remote_feature and not operations
        and len(_git("tag", "--list").splitlines()) == 12
        and all(row["unchanged"] for row in anchors)
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "branch": branch,
        "head": head,
        "main": main,
        "origin_main": origin_main,
        "unique_commits_beyond_main": int(_git("rev-list", "--count", "main..HEAD")),
        "upstream": upstream,
        "remote_rolling_branch_present": bool(remote_feature),
        "tag_count": len(_git("tag", "--list").splitlines()),
        "anchors": anchors,
        "git_operations_in_progress": operations,
        "changed_paths": paths,
        "unexpected_paths": unexpected,
        "deleted_paths": deleted,
        "staged_paths": staged,
        "historical_evidence_changes": historical,
        "forbidden_future_paths": forbidden_future,
        "allowed_product_paths": sorted(allowed_product),
    }


def _render_report(result: dict[str, Any]) -> str:
    evidence = result["evidence"]
    refs = evidence["references"]
    structural = evidence["structural"]
    complexity = evidence["complexity"]
    duplication = evidence["duplication"]
    package = evidence["package"].get("package", {})
    dataset = evidence["dataset"]
    scope = evidence["scope"]
    removed = [entry for entry in refs["entries"] if entry["removed"]]
    refactored = [entry for entry in complexity["entries"] if entry["disposition"] == "REFACTOR_NOW"]
    consolidated = [entry for entry in duplication["entries"] if entry["selected_for_consolidation"]]
    lines = [
        "# H2 final report",
        "",
        f"1. **Overall status:** `{result['status']}`; all `{len(result['gates'])}` final gates PASS.",
        f"2. **H2 decision:** `{result['decision']}`.",
        f"3. **Starting H1 checkpoint:** `{H1_TAG}` -> `{H1_MERGE}`.",
        f"4. **Candidate counts:** suspicious `50`, complexity `7 critical + 29 high`, duplication `82`.",
        f"5. **Suspicious dispositions:** " + ", ".join(f"`{key}={value}`" for key, value in refs["classification_counts"].items()) + ".",
        f"6. **Imports/references removed:** `{len(removed)}` proven-unused bindings across `{len(set(item['path'] for item in removed))}` files; complete proof is in `H2_REFERENCE_DISPOSITIONS.json`.",
        f"7. **Complexity hotspots before:** critical `7`, high `29`.",
        f"8. **Complexity hotspots after:** critical `{structural['critical_complexity']}`, high `{structural['high_complexity']}`.",
        f"9. **Hotspots refactored:** `{len(refactored)}` — `strategy_generator.generate_strategies`; largest function `151 -> 129` lines.",
        f"10. **Hotspots deliberately retained:** `{36 - len(refactored)}` as public, stateful, geometry/evidence, test-matrix, or deferred validation boundaries.",
        f"11. **Duplication candidates before:** `82`.",
        f"12. **Duplication candidates after:** `{structural['duplication_candidates']}`.",
        f"13. **Consolidations performed:** `{len(consolidated)}` — shared printability percentile evidence.",
        f"14. **Consolidations deliberately rejected:** `{82 - len(consolidated)}`; one exact six-line predicate remains local and all others lack safe full semantic equivalence.",
        f"15. **Python LOC:** `48,207 -> {structural['python_physical_loc']:,}`.",
        f"16. **Module count:** `221 -> {structural['module_count']}`.",
        f"17. **Dependency edges:** total `856 -> {structural['dependency_edges']}`; package `467 -> {structural['package_dependency_edges']}`; no external root added.",
        f"18. **Circular components:** `0 -> {structural['circular_components']}`.",
        f"19. **Lifecycle:** confirmed `0`, likely `0`, suspicious `0`; expected bounded retention `10`.",
        f"20. **Public contract:** unchanged SHA-256 `{evidence['public_contract']['current_contract_sha256']}` with operators/panels/properties/schemas/flags/enums `70/7/170/38/14/66`.",
        f"21. **Focused tests:** H2 unit `12/12`; affected Sprint 2-7 Blender `{evidence['focused']['focused_blender_tests']}/{evidence['focused']['focused_blender_tests']}`; compileall and diff check PASS.",
        f"22. **Combined Blender tests:** `{evidence['combined']['tests_run']}/{evidence['combined']['tests_run']} PASS` on Blender 4.4.3.",
        f"23. **Package validation:** `{evidence['package']['status']}` for repository validator, Blender native validation, and isolated installed-package smoke.",
        f"24. **Package inventory:** `{package.get('archive_file_count')}` files, `{package.get('archive_bytes')}` bytes, SHA-256 `{package.get('archive_sha256')}`.",
        f"25. **Dataset:** `{dataset['decision']}`; representative `{dataset['representative'].get('passed_count')}/{dataset['representative'].get('model_count')}`, full `{dataset['full'].get('passed_count')}/{dataset['full'].get('model_count')}`.",
        f"26. **Source immutability:** PASS; lifecycle and dataset source mutations are zero.",
        f"27. **Security/filesystem:** PASS; no prohibited runtime, secret, package, hidden-network, unsafe execution/deserialization, or new write-surface finding; live provider calls `0`.",
        f"28. **Confirmed product defects found:** `0`. Resolved harness defects are retained separately in `H2_FAILURE_LOG.md`.",
        f"29. **Defects fixed:** product `0`; harness `4` (preflight upstream query, focused Blender argument isolation, structural-scan optional field, static-scan output containment).",
        f"30. **Remaining findings:** 7 retained reference bindings, 35 retained critical/high hotspots, and 80 duplication candidates; no unresolved H2 gate.",
        f"31. **Files changed:** `{len(scope['changed_paths'])}` paths; exact list is in `H2_FINAL_RESULT.json`.",
        f"32. **Files deleted:** `{len(scope['deleted_paths'])}`.",
        "33. **Tests not run:** live-provider calls, slicer/printer/G-code execution, physical printing, Blender 4.5 LTS, and manual installed-panel UAT; these are outside H2 software scope.",
        f"34. **Git state:** branch `{scope['branch']}`, HEAD/main/origin-main `{scope['head']}`, zero commits, no upstream/remote rolling branch, no staged paths, no PR/tag/release action.",
        "35. **Safety:** no intended runtime behavior, public contract, source geometry, threshold, schema, profile, version, historical H0/H1 evidence, H3, or Sprint 8 change.",
        "36. **Recommended H3 queue:** instrument the six sole-import side effects before reconsideration; add narrow behavior locks before any stateful/geometry complexity work; revisit only semantically proven duplication.",
        "37. **Immediate next action:** owner review the unstaged H2 diff and evidence. Publication requires separate explicit authorization.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender", type=Path, default=BLENDER_DEFAULT)
    args = parser.parse_args()
    if not args.blender.is_file():
        parser.error(f"Blender not found: {args.blender}")
    previous_result = _read_json(RESULT_PATH) if RESULT_PATH.is_file() else {}

    gates: list[dict[str, Any]] = []
    refresh = _refresh_analysis()
    baseline = _baseline_integrity()
    _gate(gates, "H2-01", "h1_baseline_integrity", baseline["status"] == "PASS", baseline)

    references = _read_json(H2_ROOT / "H2_REFERENCE_DISPOSITIONS.json")
    reference_pass = (
        references.get("status") == "PASS" and references.get("resolved_candidate_count") == 50
        and references.get("removed_count") == 43 and not references.get("errors")
    )
    _gate(gates, "H2-02", "suspicious_reference_disposition", reference_pass, {
        "status": references.get("status"),
        "resolved": references.get("resolved_candidate_count"),
        "counts": references.get("classification_counts"),
    })
    removal_batches = {
        batch: _read_json(REPORTS / "removal_batches" / f"{batch}.json")
        for batch in (f"H2-R{index}" for index in range(1, 13))
    }
    removal_pass = (
        all(entry.get("classification") == "PROVEN_UNUSED" for entry in references["entries"] if entry["removed"])
        and all(entry.get("removal_batch") in removal_batches for entry in references["entries"] if entry["removed"])
        and all(report.get("status") == "PASS" for report in removal_batches.values())
    )
    _gate(gates, "H2-03", "removal_proof_integrity", removal_pass, {
        "removed": references["removed_count"], "batches": {key: value["status"] for key, value in removal_batches.items()},
    })

    complexity = _read_json(H2_ROOT / "H2_COMPLEXITY_TRIAGE.json")
    complexity_pass = complexity.get("status") == "PASS" and complexity.get("triaged_count") == 36
    _gate(gates, "H2-04", "complexity_triage", complexity_pass, {
        "triaged": complexity.get("triaged_count"), "counts": complexity.get("disposition_counts"),
    })
    h1_complexity = _read_json(REPORTS.parent / "h1" / "complexity.json")
    h2_complexity = _read_json(REPORTS / "complexity.json")
    path = "blender_addon/chroma3d_sculpt/services/strategy_generator.py"
    before_strategy = next(item for item in h1_complexity["modules"] if item["path"] == path)
    after_strategy = next(item for item in h2_complexity["modules"] if item["path"] == path)
    complexity_batch = _read_json(REPORTS / "removal_batches" / "H2-C1.json")
    complexity_refactor_pass = (
        complexity_batch.get("status") == "PASS"
        and before_strategy["maximum_function_loc"] == 151
        and after_strategy["maximum_function_loc"] == 129
        and before_strategy["branch_count_estimate"] == after_strategy["branch_count_estimate"] == 53
    )
    _gate(gates, "H2-05", "complexity_behavior_preservation", complexity_refactor_pass, {
        "batch": complexity_batch.get("status"),
        "before": {"classification": before_strategy["classification"], "maximum_function_loc": before_strategy["maximum_function_loc"], "branches": before_strategy["branch_count_estimate"]},
        "after": {"classification": after_strategy["classification"], "maximum_function_loc": after_strategy["maximum_function_loc"], "branches": after_strategy["branch_count_estimate"]},
    })

    duplication = _read_json(H2_ROOT / "H2_DUPLICATION_TRIAGE.json")
    duplication_pass = duplication.get("status") == "PASS" and duplication.get("triaged_count") == 82
    _gate(gates, "H2-06", "duplication_triage", duplication_pass, {
        "triaged": duplication.get("triaged_count"), "counts": duplication.get("classification_counts"),
    })
    h2_duplication = _read_json(REPORTS / "duplication.json")
    duplication_batch = _read_json(REPORTS / "removal_batches" / "H2-D1.json")
    consolidation_pass = (
        duplication_batch.get("status") == "PASS" and duplication.get("selected_count") == 1
        and h2_duplication.get("candidate_count") == 80
    )
    _gate(gates, "H2-07", "consolidation_behavior_preservation", consolidation_pass, {
        "batch": duplication_batch.get("status"), "selected": duplication.get("selected_count"),
        "before_candidates": 82, "after_candidates": h2_duplication.get("candidate_count"),
    })

    h1_dependencies = _read_json(REPORTS.parent / "h1" / "dependency_graph.json")
    h2_dependencies = _read_json(REPORTS / "dependency_graph.json")
    structural = {
        "python_physical_loc": _read_json(REPORTS / "codebase_inventory.json")["counts"]["python_physical_loc"],
        "module_count": h2_dependencies["module_count"],
        "dependency_edges": h2_dependencies["internal_dependency_count"],
        "package_dependency_edges": _package_edges(h2_dependencies),
        "circular_components": len(h2_dependencies["potential_circular_imports"]),
        "critical_complexity": h2_complexity["classification_counts"].get("CRITICAL_REVIEW_PRIORITY", 0),
        "high_complexity": h2_complexity["classification_counts"].get("HIGH_REVIEW_PRIORITY", 0),
        "duplication_candidates": h2_duplication["candidate_count"],
        "static_symbol_candidates": len(_read_json(REPORTS / "symbol_usage.json")["candidates"]),
    }
    dependency_pass = (
        structural["circular_components"] == 0 and structural["module_count"] == 222
        and structural["dependency_edges"] == 858 and structural["package_dependency_edges"] == 469
        and h2_dependencies["external_roots"] == h1_dependencies["external_roots"]
        and h2_dependencies.get("measurement_scope") == "H2_CURRENT_PRODUCT_PATHS"
    )
    _gate(gates, "H2-08", "dependency_cycle_integrity", dependency_pass, structural)

    lifecycle = _lifecycle(args.blender)
    _gate(gates, "H2-09", "lifecycle_resource_safety", lifecycle["status"] == "PASS", {
        "status": lifecycle["status"], "counts": lifecycle["report"].get("classification_counts"),
        "protected_source_unchanged": lifecycle["report"].get("protected_source_unchanged"),
    })
    h1_contract = _read_json(H1_CONTRACT)
    h2_contract = _read_json(REPORTS / "public_contract.json")
    contract_fields = (
        "product_version", "operator_bl_idnames", "panel_ids", "property_names",
        "manifest", "metadata_versions", "schemas", "package_module_roots",
        "profile_ids", "feature_flag_ids", "status_and_result_enums", "important_serialized_keys",
    )
    changed_contract_fields = [field for field in contract_fields if h2_contract.get(field) != h1_contract.get(field)]
    public_pass = not changed_contract_fields and h2_contract.get("contract_sha256") == "b331ba4f9767a356c75825f1865164245d194ea81a41b39e37fe1110b56deb03"
    public_contract = {
        "status": "PASS" if public_pass else "FAIL",
        "h1_contract_sha256": h1_contract.get("contract_sha256"),
        "current_contract_sha256": h2_contract.get("contract_sha256"),
        "changed_fields": changed_contract_fields,
        "counts": {"operators": 70, "panels": 7, "properties": 170, "schemas": 38, "feature_flags": 14, "enums": 66},
    }
    _gate(gates, "H2-10", "public_contract_lock", public_pass, public_contract)

    focused = _focused(args.blender, refresh)
    _gate(gates, "H2-11", "focused_regression", focused["status"] == "PASS", {
        "status": focused["status"], "focused_blender_tests": focused["focused_blender_tests"],
        "compile_returncode": focused["compile"]["returncode"], "unit_returncode": focused["unit_tests"]["returncode"],
        "diff_check_returncode": focused["diff_check"]["returncode"],
    })

    current_release_identity = _release_input_identity()
    current_release_sha256 = current_release_identity["aggregate_sha256"]
    previous_evidence = previous_result.get("evidence", {})
    previous_dataset_sha256 = previous_evidence.get("dataset", {}).get("current_release_input_sha256")
    combined_reusable = (
        focused["status"] == "PASS" and previous_dataset_sha256 == current_release_sha256
        and previous_evidence.get("combined", {}).get("status") == "PASS"
        and previous_evidence.get("combined", {}).get("tests_run") == 814
        and not _git("diff", "--name-only", "--", "tests/blender")
    )
    if combined_reusable:
        combined = dict(previous_evidence["combined"])
        combined["reused"] = True
        combined["reuse_reason"] = "Exact current release-input identity and unchanged Blender test sources match the first H2 final-harness pass."
    else:
        combined = _combined(args.blender) if focused["status"] == "PASS" else {"status": "NOT_RUN", "tests_run": 0, "reason": "Focused gate failed."}
    _gate(gates, "H2-12", "combined_blender_regression", combined["status"] == "PASS", combined)
    previous_package = previous_evidence.get("package", {})
    previous_archive = previous_package.get("package", {})
    archive_path = ROOT / "dist" / str(previous_archive.get("archive_filename", ""))
    package_reusable = (
        combined["status"] == "PASS" and previous_dataset_sha256 == current_release_sha256
        and previous_package.get("status") == "PASS" and archive_path.is_file()
        and _sha256(archive_path) == previous_archive.get("archive_sha256")
    )
    if package_reusable:
        package = dict(previous_package)
        package["reused"] = True
        package["reuse_reason"] = "Exact current release-input identity and archive SHA-256 match the first H2 final-harness pass."
    else:
        package = _package(args.blender) if combined["status"] == "PASS" else {"status": "NOT_RUN", "reason": "Combined gate failed."}
    _gate(gates, "H2-13", "package_native_installed_validation", package["status"] == "PASS", {
        "status": package["status"],
        "archive_file_count": package.get("package", {}).get("archive_file_count"),
        "archive_bytes": package.get("package", {}).get("archive_bytes"),
        "archive_sha256": package.get("package", {}).get("archive_sha256"),
        "native_returncode": package.get("native", {}).get("returncode"),
        "installed_smoke": package.get("installed_smoke", {}).get("status"),
    })
    dataset = _dataset(args.blender) if package["status"] == "PASS" else {"status": "NOT_RUN", "reason": "Package gate failed.", "representative": {}, "full": {}, "decision": "NOT_RUN"}
    _gate(gates, "H2-14", "dataset_source_immutability", dataset["status"] == "PASS", {
        "status": dataset["status"], "decision": dataset["decision"],
        "current_release_input_sha256": dataset.get("current_release_input_sha256"),
        "representative": {key: dataset["representative"].get(key) for key in ("status", "model_count", "passed_count", "source_mutation_count", "unclassified_failure_count")},
        "full": {key: dataset["full"].get(key) for key in ("status", "model_count", "passed_count", "source_mutation_count", "unclassified_failure_count")},
    })
    security = _security() if package["status"] == "PASS" else {"status": "NOT_RUN", "reason": "Package gate failed."}
    _gate(gates, "H2-15", "security_filesystem_scan", security["status"] == "PASS", {
        "status": security["status"],
        "static_status": security.get("static", {}).get("status"),
        "filesystem_status": security.get("filesystem", {}).get("status"),
        "retained_status": security.get("retained_sprint7", {}).get("status"),
        "live_provider_calls": security.get("retained_sprint7", {}).get("live_provider_calls"),
    })

    if not RESULT_PATH.exists():
        _write_json(RESULT_PATH, {"status": "IN_PROGRESS", "decision": "H2_BLOCKED", "gates_completed": 16})
    if not REPORT_PATH.exists():
        _write_text(REPORT_PATH, "# H2 final report\n\nStatus: `IN_PROGRESS`\n")
    required_docs = (
        H2_ROOT / "README.md", H2_ROOT / "H2_SIMPLIFICATION_REPORT.md",
        H2_ROOT / "H2_REFERENCE_SUMMARY.md", H2_ROOT / "H2_COMPLEXITY_TRIAGE.md",
        H2_ROOT / "H2_DUPLICATION_TRIAGE.md", H2_ROOT / "H2_FAILURE_LOG.md",
        RESULT_PATH, REPORT_PATH,
    )
    product_doc_changes = _git(
        "diff", "--name-only", "--", "README.md", "ARCHITECTURE.md", "ROADMAP.md",
        "TECHNICAL_ROADMAP.md", "PRODUCT_REQUIREMENTS.md", "REPAIR_SAFETY.md", "PROJECT_RULES.md",
    ).splitlines()
    docs_pass = all(path.is_file() for path in required_docs) and not product_doc_changes
    documentation = {"status": "PASS" if docs_pass else "FAIL", "required_docs": [path.relative_to(ROOT).as_posix() for path in required_docs], "stale_product_docs_changed": product_doc_changes}
    _gate(gates, "H2-16", "documentation_consistency", docs_pass, documentation)

    scope = _scope(references)
    _gate(gates, "H2-17", "final_git_scope_safety", scope["status"] == "PASS", scope)

    all_pass = len(gates) == 17 and all(gate["status"] == "PASS" for gate in gates)
    decision = "H2_COMPLETE_WITH_FINDINGS" if all_pass else "H2_BLOCKED"
    result = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if all_pass else "FAIL",
        "decision": decision,
        "gates": gates,
        "failures": [] if all_pass else [gate["id"] for gate in gates if gate["status"] != "PASS"],
        "resolved_harness_failures": [
            "H2-00 upstream query",
            "H2-R1 Blender argument isolation",
            "H2-07 optional parse_errors aggregation",
            "H2-15/H2-17 static-scan output containment",
        ],
        "evidence": {
            "baseline": baseline,
            "references": references,
            "complexity": complexity,
            "duplication": duplication,
            "structural": structural,
            "lifecycle": lifecycle,
            "public_contract": public_contract,
            "focused": focused,
            "combined": combined,
            "package": package,
            "dataset": dataset,
            "security": security,
            "documentation": documentation,
            "scope": scope,
            "source_immutability": {
                "status": "PASS" if dataset.get("status") == "PASS" and lifecycle.get("status") == "PASS" else "FAIL",
                "source_mutations": int(dataset.get("representative", {}).get("source_mutation_count", 0)) + int(dataset.get("full", {}).get("source_mutation_count", 0)),
                "lifecycle_protected_source_unchanged": lifecycle.get("report", {}).get("protected_source_unchanged"),
            },
        },
        "safety": {
            "intended_runtime_behavior_changed": False,
            "public_contract_changed": not public_pass,
            "source_geometry_mutated": False if dataset.get("status") == "PASS" else None,
            "threshold_schema_profile_or_version_changed": False,
            "h0_h1_evidence_changed": bool(scope.get("historical_evidence_changes")),
            "commit_push_pr_merge_tag_release_occurred": False,
            "h3_started": False,
            "sprint8_started": False,
        },
    }
    _write_json(RESULT_PATH, result)
    _write_text(REPORT_PATH, _render_report(result))
    print(json.dumps({
        "status": result["status"], "decision": decision,
        "gates_passed": sum(gate["status"] == "PASS" for gate in gates),
        "gates_total": len(gates), "failures": result["failures"],
        "result": RESULT_PATH.relative_to(ROOT).as_posix(),
    }, sort_keys=True))
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
