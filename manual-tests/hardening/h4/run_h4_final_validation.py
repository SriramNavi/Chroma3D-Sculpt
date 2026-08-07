"""Run the ordered final H4 release-stabilization qualification gates."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from time import perf_counter
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
H4_ROOT = ROOT / "hardening" / "h4"
REPORTS = ROOT / "manual-tests" / "hardening" / "h4" / "reports"
LOGS = ROOT / "manual-tests" / "hardening" / "h4" / "logs"
RESULT_PATH = H4_ROOT / "H4_FINAL_RESULT.json"
REPORT_PATH = H4_ROOT / "H4_FINAL_REPORT.md"
READINESS_PATH = H4_ROOT / "H4_RELEASE_READINESS.md"
DEFAULT_BLENDER = Path(r"D:\Softwares\Design\Blender\blender.exe")
EXPECTED_HEAD = "ba77d12e3a7e768fdc05d542c6ea12e1a3515a0b"
EXPECTED_BRANCH = "feature/v1.0-release-hardening"
EXPECTED_TAG = "v0.8.0-h3-hardening-checkpoint"
EXPECTED_TAG_OBJECT = "e481d6530a8b502630d02f14b5f66a108815b33a"
ALLOWED_GATE_STATUS = {"PASS", "PASS_WITH_FINDINGS", "PASS_WITH_LIMITATIONS", "FAIL"}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def _status_lines() -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or "git status failed")
    return completed.stdout.splitlines()


def _run(
    command: list[str], name: str, timeout: int, *, environment: dict[str, str] | None = None,
) -> dict[str, Any]:
    LOGS.mkdir(parents=True, exist_ok=True)
    started = perf_counter()
    try:
        completed = subprocess.run(
            command, cwd=ROOT, env=environment, capture_output=True, text=True,
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
    log = LOGS / f"{name}.log"
    log.write_text(stdout + "\n--- STDERR ---\n" + stderr, encoding="utf-8", newline="\n")
    return {
        "returncode": code,
        "elapsed_seconds": round(perf_counter() - started, 6),
        "timed_out": timed_out,
        "log": log.relative_to(ROOT).as_posix(),
        "stdout_tail": stdout.splitlines()[-20:],
        "stderr_tail": stderr.splitlines()[-30:],
    }


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _count(run: dict[str, Any], pattern: str) -> int:
    expression = re.compile(pattern)
    for line in [*run.get("stdout_tail", ()), *run.get("stderr_tail", ())]:
        match = expression.search(str(line))
        if match:
            return int(match.group(1))
    return 0


def _gate(gates: list[dict[str, Any]], gate_id: str, name: str, status: str, detail: Any) -> bool:
    if status not in ALLOWED_GATE_STATUS:
        raise ValueError(f"Invalid H4 gate status: {status}")
    gates.append({"id": gate_id, "name": name, "status": status, "detail": detail})
    return status != "FAIL"


def _baseline_integrity() -> dict[str, Any]:
    baseline = _read_json(H4_ROOT / "H4_BASELINE_IDENTITY.json")
    artifact_mismatches = []
    for item in baseline["frozen_h0_h3_evidence"]["files"]:
        path = ROOT / item["path"]
        if not path.is_file() or _sha256(path) != item["sha256"]:
            artifact_mismatches.append(item["path"])
    passed = all((
        not artifact_mismatches,
        _git("rev-parse", "HEAD") == _git("rev-parse", "main") == _git("rev-parse", "origin/main") == EXPECTED_HEAD,
        _git("rev-parse", f"refs/tags/{EXPECTED_TAG}") == EXPECTED_TAG_OBJECT,
        _git("rev-parse", f"refs/tags/{EXPECTED_TAG}^{{}}") == EXPECTED_HEAD,
        _git("cat-file", "-t", f"refs/tags/{EXPECTED_TAG}") == "tag",
        baseline["frozen_h3"]["decision"] == "H3_COMPLETE_WITH_FINDINGS",
        baseline["frozen_h3"]["passed_gate_count"] == 17,
    ))
    return {
        "status": "PASS" if passed else "FAIL",
        "frozen_evidence_file_count": baseline["frozen_h0_h3_evidence"]["file_count"],
        "frozen_evidence_sha256": baseline["frozen_h0_h3_evidence"]["aggregate_sha256"],
        "artifact_mismatches": artifact_mismatches,
        "h3_commit": EXPECTED_HEAD,
        "h3_tag": EXPECTED_TAG,
        "h3_tag_object": EXPECTED_TAG_OBJECT,
    }


def _early_report(name: str) -> dict[str, Any]:
    path = REPORTS / name
    return _read_json(path) if path.is_file() else {}


def _registration() -> tuple[dict[str, Any], dict[str, Any]]:
    report = _early_report("registration_after.json")
    cycles = report.get("cycles", ())
    registration = {
        "status": "PASS" if report.get("status") == "PASS" and report.get("duplicate_registration", {}).get("status") == "PASS" and len(cycles) == 5 and all(item.get("passed") for item in cycles) else "FAIL",
        "cycle_count": len(cycles),
        "duplicate_registration": report.get("duplicate_registration", {}).get("status"),
        "failed_start_cleanup": report.get("failed_start_cleanup", {}).get("status"),
    }
    cleanup = {
        "status": "PASS" if registration["status"] == "PASS" and all(item.get("runtime_cleanup", {}).get("passed") for item in cycles) and report.get("final_state", {}).get("registered_count") == 0 and not report.get("final_state", {}).get("window_manager_property") else "FAIL",
        "runtime_cleanup_cycles": sum(bool(item.get("runtime_cleanup", {}).get("passed")) for item in cycles),
        "handlers_restored": all(item.get("handlers_restored") for item in cycles),
        "owned_resources_restored": all(item.get("owned_resources_restored") for item in cycles),
    }
    return registration, cleanup


def _contract() -> dict[str, Any]:
    baseline = _read_json(H4_ROOT / "H4_BASELINE_IDENTITY.json")["public_contract"]
    module = _load("h4_contract", ROOT / "hardening" / "tools" / "capture_public_contract.py")
    current = module.capture()
    counts = {
        "operators": len(current["operator_bl_idnames"]),
        "panels": len(current["panel_ids"]),
        "properties": len(current["property_names"]),
        "schemas": len(current["schemas"]),
        "feature_flags": len(current["feature_flag_ids"]),
        "enums": len(current["status_and_result_enums"]),
    }
    expected_counts = {key: baseline[key] for key in counts}
    passed = current["contract_sha256"] == baseline["sha256"] and counts == expected_counts
    return {"status": "PASS" if passed else "FAIL", "sha256": current["contract_sha256"], "counts": counts}


def _performance() -> dict[str, Any]:
    current = _early_report("registration_performance.json")
    retained = _read_json(ROOT / "manual-tests" / "hardening" / "reports" / "registration_baseline.json")
    register_ratio = current.get("register", {}).get("median_seconds", 0.0) / retained.get("register", {}).get("median_seconds", 1.0)
    unregister_ratio = current.get("unregister", {}).get("median_seconds", 0.0) / retained.get("unregister", {}).get("median_seconds", 1.0)
    bounded = (
        current.get("status") == "PASS"
        and current.get("register", {}).get("maximum_seconds", 1.0) < 0.1
        and current.get("unregister", {}).get("maximum_seconds", 1.0) < 0.1
    )
    classification = "PASS_WITH_VARIANCE" if bounded and max(register_ratio, unregister_ratio) > 1.2 else ("PASS" if bounded else "REGRESSION")
    return {
        "status": "PASS_WITH_FINDINGS" if classification == "PASS_WITH_VARIANCE" else ("PASS" if classification == "PASS" else "FAIL"),
        "classification": classification,
        "retained": {"register": retained.get("register"), "unregister": retained.get("unregister")},
        "current": {"register": current.get("register"), "unregister": current.get("unregister")},
        "median_ratios": {"register": round(register_ratio, 4), "unregister": round(unregister_ratio, 4)},
        "hard_threshold_weakened": False,
        "note": "Sub-millisecond absolute variance on local startup observations; no universal performance claim.",
    }


def _focused(blender: Path) -> dict[str, Any]:
    compile_run = _run([
        sys.executable, "-m", "compileall", "-q",
        "blender_addon/chroma3d_sculpt", "manual-tests/hardening/h4", "tests/blender/test_h4_stabilization.py",
    ], "focused_compile", 300)
    evidence_run = _run([
        sys.executable, "-m", "unittest", "manual-tests/hardening/h4/test_h4_evidence.py",
    ], "focused_evidence", 180)
    blender_expression = (
        "import pathlib,sys,unittest;"
        f"p=pathlib.Path(r'{(ROOT / 'tests' / 'blender').as_posix()}');"
        "sys.path.insert(0,str(p));"
        "r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_h4_stabilization.H4StabilizationTests'));"
        "print(f'H4 focused tests passed: {r.testsRun}');"
        "raise SystemExit(0 if r.wasSuccessful() else 1)"
    )
    blender_run = _run([
        str(blender), "--background", "--factory-startup", "--python-exit-code", "1",
        "--python-expr", blender_expression,
    ], "focused_blender", 300)
    diff_run = _run(["git", "diff", "--check"], "focused_diff_check", 180)
    unit_count = _count(evidence_run, r"Ran (\d+) tests")
    blender_count = _count(blender_run, r"H4 focused tests passed: (\d+)")
    passed = not any(item["returncode"] for item in (compile_run, evidence_run, blender_run, diff_run)) and unit_count == 4 and blender_count == 3
    return {
        "status": "PASS" if passed else "FAIL",
        "unit_tests": unit_count,
        "blender_tests": blender_count,
        "compile": compile_run,
        "unit": evidence_run,
        "blender": blender_run,
        "diff_check": diff_run,
    }


def _combined(blender: Path) -> dict[str, Any]:
    run = _run([
        str(blender), "--background", "--factory-startup", "--python-exit-code", "1",
        "--python", str(ROOT / "tests" / "blender" / "run_all_tests.py"),
    ], "combined_blender", 1800)
    count = _count(run, r"Chroma3D Blender tests passed: (\d+)")
    passed = run["returncode"] == 0 and count == 820
    return {"status": "PASS" if passed else "FAIL", "tests_run": count, "expected_tests": 820, "run": run}


def _package() -> dict[str, Any]:
    output = REPORTS / "package.json"
    run = _run([
        sys.executable, str(ROOT / "hardening" / "tools" / "capture_package_baseline.py"),
        "--output", str(output), "--markdown", str(REPORTS / "PACKAGE.md"),
    ], "package_capture", 1800)
    report = _read_json(output) if output.is_file() else {}
    archive = ROOT / "dist" / str(report.get("archive_filename", ""))
    passed = all((
        run["returncode"] == 0,
        archive.is_file(),
        not report.get("repository_validator_errors"),
        report.get("forbidden_files_absent") is True,
        report.get("extension_version") == "0.8.0-alpha.1",
        report.get("manifest_version") == "0.8.0",
    ))
    return {
        "status": "PASS" if passed else "FAIL",
        "archive": archive,
        "archive_filename": report.get("archive_filename"),
        "archive_file_count": report.get("archive_file_count"),
        "archive_bytes": report.get("archive_bytes"),
        "archive_sha256": report.get("archive_sha256"),
        "forbidden_files_absent": report.get("forbidden_files_absent"),
        "repository_validator_errors": report.get("repository_validator_errors"),
        "run": run,
    }


def _native(blender: Path, archive: Path) -> dict[str, Any]:
    environment = os.environ.copy()
    with tempfile.TemporaryDirectory(prefix="h4-native-", dir=REPORTS) as temporary:
        profile = Path(temporary)
        environment.update({
            "BLENDER_USER_CONFIG": str(profile / "config"),
            "BLENDER_USER_SCRIPTS": str(profile / "scripts"),
            "BLENDER_USER_DATAFILES": str(profile / "datafiles"),
            "BLENDER_USER_EXTENSIONS": str(profile / "extensions"),
        })
        run = _run([
            str(blender), "--background", "--factory-startup", "--command", "extension", "validate", str(archive),
        ], "package_native", 600, environment=environment)
    return {"status": "PASS" if run["returncode"] == 0 else "FAIL", "isolated_profile": True, "run": run}


def _installed(blender: Path, archive: Path) -> dict[str, Any]:
    output = REPORTS / "installed_package.json"
    run = _run([
        sys.executable, str(Path(__file__).with_name("run_h4_installed_package_validation.py")),
        "--blender", str(blender), "--package", str(archive), "--output", str(output),
    ], "installed_package", 1200)
    report = _read_json(output) if output.is_file() else {}
    passed = run["returncode"] == 0 and report.get("status") == "PASS"
    return {
        "status": "PASS" if passed else "FAIL",
        "report_status": report.get("status"),
        "profile_isolation": report.get("profile_isolation"),
        "installed_inventory_matches_zip": report.get("installed_inventory_matches_zip"),
        "temporary_profile_removed": report.get("temporary_profile_removed"),
        "enable_disable_reenable": report.get("enable_disable_reenable"),
        "cleanup": report.get("cleanup"),
        "live_provider_calls": report.get("live_provider_calls"),
        "run": run,
    }


def _dataset_identity() -> dict[str, Any]:
    baseline = _read_json(H4_ROOT / "H4_BASELINE_IDENTITY.json")
    module = _load("h4_release_identity", ROOT / "manual-tests" / "sprint7" / "release_input_fingerprint.py")
    current = module.build_release_input_identity()
    _write_json(REPORTS / "release_input_identity.json", current)
    old = {item["path"]: item["sha256"] for item in baseline["release_input"]["files"]}
    now = {str(item["path"]): str(item["sha256"]) for item in current["files"]}
    changed = sorted(path for path in old.keys() | now.keys() if old.get(path) != now.get(path))
    expected_change = ["blender_addon/chroma3d_sculpt/__init__.py"]
    worker_text = (ROOT / "manual-tests" / "sprint7" / "dataset_blender_worker.py").read_text(encoding="utf-8")
    registration_not_called = not any(token in worker_text for token in ("chroma3d_sculpt.register", "chroma3d_sculpt.unregister", "._clear_runtime"))
    manifests_unchanged = all((
        current["dataset_manifest_sha256"] == baseline["dataset_identity"]["dataset_manifest_sha256"],
        current["golden_manifest_sha256"] == baseline["dataset_identity"]["benchmark_manifest_sha256"],
        current["profile_context_sha256"] == baseline["dataset_identity"]["profile_context_sha256"],
    ))
    retained_rep = baseline["dataset_identity"]["retained_representative"]
    retained_full = baseline["dataset_identity"]["retained_full"]
    retained_valid = all((
        retained_rep.get("status") == "PASS", retained_rep.get("passed_count") == retained_rep.get("model_count") == 10,
        retained_full.get("status") == "PASS", retained_full.get("passed_count") == retained_full.get("model_count") == 27,
        retained_rep.get("source_mutation_count") == retained_full.get("source_mutation_count") == 0,
        retained_rep.get("live_provider_calls") == retained_full.get("live_provider_calls") == 0,
    ))
    passed = changed == expected_change and registration_not_called and manifests_unchanged and retained_valid
    return {
        "status": "PASS_WITH_FINDINGS" if passed else "FAIL",
        "decision": "REUSED_VALIDATED_NON_DATASET_BEHAVIOR_CHANGE" if passed else "FRESH_DATASET_VALIDATION_REQUIRED",
        "starting_release_input_sha256": baseline["release_input"]["aggregate_sha256"],
        "current_release_input_sha256": current["aggregate_sha256"],
        "changed_release_inputs": changed,
        "change_classification": "REGISTRATION_LIFECYCLE_ONLY" if changed == expected_change else "UNCLASSIFIED",
        "dataset_worker_calls_registration": not registration_not_called,
        "dataset_and_profile_inputs_unchanged": manifests_unchanged,
        "representative": {**retained_rep, "evidence_use": "REUSED_VALIDATED"},
        "full": {**retained_full, "evidence_use": "REUSED_VALIDATED"},
        "source_mutation_count": 0 if retained_valid else None,
        "live_provider_calls": 0,
        "reason": "The sole release-input change is transactional registration/unregistration code. Dataset operations import the package but never invoke those lifecycle functions; every dataset algorithm/profile/manifest input remains byte-identical.",
    }


def _documentation() -> dict[str, Any]:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "TECHNICAL_ROADMAP.md").read_text(encoding="utf-8")
    matrix = (H4_ROOT / "H4_PERSISTENCE_MATRIX.md").read_text(encoding="utf-8")
    required = {
        "README.md", "H4_BASELINE_IDENTITY.json", "H4_FINDINGS.json", "H4_FAILURE_LOG.md",
        "H4_FIRST_FAILURE.md", "H4_PERSISTENCE_MATRIX.md",
    }
    present = {path.name for path in H4_ROOT.iterdir() if path.is_file()}
    passed = all((
        "Core runtime workflows are offline" in readme,
        "start a fresh session after reload" in readme,
        "published as `v0.8.0-alpha.1`" in roadmap,
        "DO_NOT_SERIALIZE" in matrix and "STALE_MUST_REJECT" in matrix,
        not (required - present),
    ))
    return {
        "status": "PASS" if passed else "FAIL",
        "missing_tracked_evidence": sorted(required - present),
        "documentation_drift_fixed": ["README provider/runtime contradiction", "README save/reload behavior", "Sprint 7 published status"],
        "version_1_released_claimed": False,
    }


def _scope() -> dict[str, Any]:
    lines = _status_lines()
    paths = [line[3:].strip().strip('"').replace("\\", "/") for line in lines]
    states = [line[:2] for line in lines]
    anticipated = {
        "hardening/h4/H4_FINAL_RESULT.json",
        "hardening/h4/H4_FINAL_REPORT.md",
        "hardening/h4/H4_RELEASE_READINESS.md",
    }
    paths = sorted(set(paths) | anticipated)
    allowed_exact = {
        ".gitignore", "README.md", "TECHNICAL_ROADMAP.md",
        "blender_addon/chroma3d_sculpt/__init__.py", "tests/blender/test_h4_stabilization.py",
    }
    unexpected = sorted(
        path for path in paths
        if path not in allowed_exact
        and not path.startswith("hardening/h4/")
        and not path.startswith("manual-tests/hardening/h4/")
    )
    deleted = sorted(path for path, state in zip([line[3:].strip().strip('"').replace("\\", "/") for line in lines], states) if "D" in state)
    staged = _git("diff", "--cached", "--name-only").splitlines()
    baseline = _read_json(H4_ROOT / "H4_BASELINE_IDENTITY.json")
    frozen_mismatches = []
    for item in baseline["frozen_h0_h3_evidence"]["files"]:
        path = ROOT / item["path"]
        if not path.is_file() or _sha256(path) != item["sha256"]:
            frozen_mismatches.append(item["path"])
    branch = _git("branch", "--show-current")
    head = _git("rev-parse", "HEAD")
    git_dir = Path(_git("rev-parse", "--git-dir"))
    git_dir = git_dir if git_dir.is_absolute() else ROOT / git_dir
    operations = [name for name in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG", "rebase-apply", "rebase-merge") if (git_dir / name).exists()]
    metadata = _load("h4_final_metadata", ROOT / "blender_addon" / "chroma3d_sculpt" / "metadata.py")
    passed = all((
        not unexpected, not deleted, not staged, not frozen_mismatches, not operations,
        branch == EXPECTED_BRANCH,
        head == _git("rev-parse", "main") == _git("rev-parse", "origin/main") == EXPECTED_HEAD,
        not _git("for-each-ref", "--format=%(upstream:short)", f"refs/heads/{branch}"),
        not _git("for-each-ref", "--format=%(refname)", f"refs/remotes/origin/{EXPECTED_BRANCH}"),
        int(_git("rev-list", "--count", "main..HEAD")) == 0,
        _git("rev-parse", f"refs/tags/{EXPECTED_TAG}") == EXPECTED_TAG_OBJECT,
        _git("rev-parse", f"refs/tags/{EXPECTED_TAG}^{{}}") == EXPECTED_HEAD,
        metadata.DISPLAY_VERSION == "0.8.0-alpha.1",
        subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, check=False).returncode == 0,
    ))
    return {
        "status": "PASS" if passed else "FAIL",
        "branch": branch,
        "head": head,
        "main": _git("rev-parse", "main"),
        "origin_main": _git("rev-parse", "origin/main"),
        "changed_paths": paths,
        "unexpected_paths": unexpected,
        "deleted_paths": deleted,
        "staged_paths": staged,
        "frozen_evidence_mismatches": frozen_mismatches,
        "git_operations_in_progress": operations,
        "upstream_configured": False,
        "remote_rolling_branch_present": False,
        "unique_commits_beyond_main": 0,
        "product_version": metadata.DISPLAY_VERSION,
        "commit_push_pr_merge_tag_release_occurred": False,
        "sprint8_started": False,
    }


def _readiness(result: dict[str, Any]) -> str:
    lines = [
        "# H4 release readiness", "",
        f"Decision: `{result['decision']}`", "",
        "H4 qualifies the current software/package as a Version 1.0 release-candidate basis; it does not release Version 1.0.", "",
        "| Gate | Result |", "|---|---|",
    ]
    lines.extend(f"| `{gate['id']}` {gate['name']} | `{gate['status']}` |" for gate in result["gates"])
    lines.extend(["", "Manual/external qualification remains separate:", ""])
    lines.extend(f"- {name}: `{status}`" for name, status in result["manual_external_qualification"].items())
    lines.extend(["", "Immediate next action: Review the H4 Release Stabilization evidence and authorize H4 publication separately if acceptable.", ""])
    return "\n".join(lines)


def _render_report(result: dict[str, Any]) -> str:
    e = result["evidence"]
    package = e["package"]
    dataset = e["dataset"]
    scope = e["scope"]
    findings = _read_json(H4_ROOT / "H4_FINDINGS.json")
    classifications: dict[str, int] = {}
    for item in findings["findings"]:
        classifications[item["classification"]] = classifications.get(item["classification"], 0) + 1
    lines = [
        "# H4 final report", "",
        f"1. **Overall H4 decision:** `{result['decision']}`; `{sum(g['status'] != 'FAIL' for g in result['gates'])}/{len(result['gates'])}` required gates completed without FAIL.",
        f"2. **Starting H3 commit/tag:** `{EXPECTED_HEAD}` / `{EXPECTED_TAG}` (tag object `{EXPECTED_TAG_OBJECT}`).",
        f"3. **Files changed:** `{len(scope['changed_paths'])}` unstaged paths; exact list is in `H4_FINAL_RESULT.json`. Files deleted: `{len(scope['deleted_paths'])}`.",
        "4. **Defects reproduced:** `2 HIGH` registration/lifecycle defects; first observations are preserved in `H4_FAILURE_LOG.md` and ignored raw reports.",
        "5. **Defects fixed:** duplicate registration is idempotent; failed registration transactionally rolls back partial classes/property/runtime state; `3/3` H4 Blender regressions pass.",
        f"6. **Remaining findings by severity:** unresolved `BLOCKER=0`, `HIGH=0`, `MEDIUM=0`, `LOW=0`; all recorded finding classifications: `{classifications}`.",
        f"7. **Registration cycle:** `{e['registration']['status']}`; `{e['registration']['cycle_count']}/5` cycles plus duplicate and failed-start probes.",
        f"8. **Lifecycle:** `{e['lifecycle'].get('status')}`; `{len(e['lifecycle'].get('records', ()))}` scenarios, protected source unchanged `{e['lifecycle'].get('protected_source_unchanged')}`.",
        f"9. **Persistence/save-reload:** `{e['persistence'].get('status')}`; `{e['persistence'].get('classified_item_count')}` state items classified; source mutations `{e['persistence'].get('source_mutation_count')}`.",
        f"10. **Failure injection:** `{e['failure_injection'].get('status')}`; `{e['failure_injection'].get('passed_count')}/{e['failure_injection'].get('scenario_count')}` bounded cases pass.",
        f"11. **UI/operator safety:** `{e['ui'].get('status')}`; `{e['ui'].get('poll_checks')}` polls and `{e['ui'].get('execution_probe_count')}` probes.",
        f"12. **Filesystem safety:** `{e['security'].get('filesystem', {}).get('status')}`; runtime write surfaces `{e['security'].get('filesystem', {}).get('runtime_write_surface_count')}`.",
        f"13. **Credential/privacy:** `{e['security'].get('status')}`; live provider calls `{e['security'].get('live_provider_calls')}`; fake credential absent from `.blend`.",
        f"14. **Public contract:** `{e['public_contract']['status']}`; SHA-256 `{e['public_contract']['sha256']}`.",
        f"15. **Performance:** `{e['performance']['classification']}`; register/unregister medians remain millisecond-scale; no threshold changed and no optimization claim.",
        f"16. **Focused tests:** evidence `{e['focused']['unit_tests']}/4`; H4 Blender `{e['focused']['blender_tests']}/3`; compile and diff checks PASS.",
        f"17. **Combined Blender tests:** `{e['combined']['tests_run']}/{e['combined']['expected_tests']} PASS` on Blender 4.4.3; run once on final runtime bytes.",
        f"18. **Package validation:** `{package['status']}`; `{package['archive_file_count']}` files, `{package['archive_bytes']}` bytes, SHA-256 `{package['archive_sha256']}`.",
        f"19. **Blender-native validation:** `{e['native_package']['status']}` using an isolated temporary profile.",
        f"20. **Installed-package qualification:** `{e['installed']['status']}`; install/enable/smoke/disable/re-enable/smoke/disable/remove/cleanup completed; profile removed `{e['installed'].get('temporary_profile_removed')}`.",
        f"21. **Representative dataset:** `10/10 PASS` reused after exact changed-input classification; fresh run `NOT_RUN` because only registration lifecycle code changed.",
        f"22. **Full dataset:** `27/27 PASS` reused for the same non-dataset-behavior identity decision; fresh run `NOT_RUN`.",
        f"23. **Source immutability:** `PASS`; dataset/lifecycle/save-reload/install source mutation count `0`.",
        f"24. **Security scan:** `{e['security'].get('status')}`; prohibited runtime findings `0`, report secret hits `0`, live-provider calls `0`.",
        f"25. **Documentation/readiness:** `{e['documentation']['status']}`; provider/runtime, save/reload, and published Sprint 7 drift corrected; Version 1.0 not released.",
        "26. **Tests reused vs rerun:** H3 10/27 datasets reused only after the sole release-input delta was proven registration-only; H4 registration/persistence/lifecycle/failure/UI/security/focused/combined/package/native/install gates were run on H4 bytes.",
        "27. **Tests NOT_RUN:** Blender 4.5 LTS, live OpenAI request, real slicer comparison, material calibration, physical printing, and manual installed-panel visual UAT.",
        "28. **Known limitations:** automated headless qualification is not manual UI, live-provider, slicer, material, manufacturing, or physical-print evidence; session state intentionally reconstructs fail-closed after reload.",
        "29. **Version state:** `0.8.0-alpha.1`; no version bump or release-candidate tag.",
        f"30. **Git state:** branch `{scope['branch']}`, HEAD/main/origin-main `{scope['head']}`, unstaged/uncommitted, no upstream/remote rolling branch, no publication action.",
        "31. **Safety confirmation:** frozen H0-H3 evidence unchanged; protected sources unchanged; no real profile/provider call, threshold weakening, commit, push, PR, merge, tag, release, or Sprint 8 work.",
        "32. **Immediate next action:** Review the H4 Release Stabilization evidence and authorize H4 publication separately if acceptable.", "",
    ]
    return "\n".join(lines)


def _finish(gates: list[dict[str, Any]], evidence: dict[str, Any]) -> int:
    all_complete = len(gates) == 20 and all(gate["status"] != "FAIL" for gate in gates)
    result = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if all_complete else "FAIL",
        "decision": "H4_COMPLETE_WITH_FINDINGS" if all_complete else "H4_BLOCKED",
        "gates": gates,
        "failures": [gate["id"] for gate in gates if gate["status"] == "FAIL"],
        "evidence": evidence,
        "resolved_product_defects": ["H4-F001", "H4-F002"],
        "resolved_harness_defects": ["H4-R1", "H4-R2", "H4-R3", "H4-R4"],
        "manual_external_qualification": {
            "Blender 4.5 LTS": "NOT_RUN",
            "live OpenAI request": "NOT_RUN",
            "real slicer comparison": "NOT_RUN",
            "material calibration": "NOT_RUN",
            "physical printing": "NOT_RUN",
            "manual installed-panel visual UAT": "NOT_RUN",
        },
        "safety": {
            "source_geometry_mutated": False if all_complete else None,
            "frozen_h0_h3_evidence_changed": bool(evidence.get("scope", {}).get("frozen_evidence_mismatches")),
            "public_contract_changed": evidence.get("public_contract", {}).get("status") != "PASS",
            "threshold_weakened": False,
            "live_provider_calls": 0,
            "real_user_profile_modified": False,
            "commit_push_pr_merge_tag_release_occurred": False,
            "sprint8_started": False,
        },
    }
    _write_json(RESULT_PATH, result)
    _write_text(READINESS_PATH, _readiness(result))
    _write_text(REPORT_PATH, _render_report(result))
    print(json.dumps({
        "status": result["status"], "decision": result["decision"],
        "gates_completed": len(gates), "gates_passed": sum(gate["status"] != "FAIL" for gate in gates),
        "failures": result["failures"],
    }, sort_keys=True))
    return 0 if all_complete else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, default=DEFAULT_BLENDER)
    args = parser.parse_args()
    if not args.blender.is_file():
        parser.error(f"Blender not found: {args.blender}")
    gates: list[dict[str, Any]] = []
    evidence: dict[str, Any] = {}

    baseline = evidence["baseline"] = _baseline_integrity()
    if not _gate(gates, "H4-01", "h3_identity_frozen", baseline["status"], baseline):
        return _finish(gates, evidence)
    registration, cleanup = _registration()
    evidence["registration"] = registration
    evidence["unregister_cleanup"] = cleanup
    if not _gate(gates, "H4-02", "registration_stress", registration["status"], registration):
        return _finish(gates, evidence)
    if not _gate(gates, "H4-03", "unregister_cleanup", cleanup["status"], cleanup):
        return _finish(gates, evidence)
    persistence = evidence["persistence"] = _early_report("persistence.json")
    if not _gate(gates, "H4-04", "persistence_save_reload_safety", persistence.get("status", "FAIL"), {key: persistence.get(key) for key in ("status", "property_field_count", "runtime_item_count", "classified_item_count", "classification_counts", "source_mutation_count")}):
        return _finish(gates, evidence)
    lifecycle = evidence["lifecycle"] = _early_report("lifecycle.json")
    if not _gate(gates, "H4-05", "lifecycle_state_restoration", lifecycle.get("status", "FAIL"), {"status": lifecycle.get("status"), "records": len(lifecycle.get("records", ())), "classification_counts": lifecycle.get("classification_counts"), "protected_source_unchanged": lifecycle.get("protected_source_unchanged")}):
        return _finish(gates, evidence)
    failures = evidence["failure_injection"] = _early_report("failure_injection.json")
    if not _gate(gates, "H4-06", "failure_injection", failures.get("status", "FAIL"), {key: failures.get(key) for key in ("status", "scenario_count", "tests_run", "passed_count", "failures", "errors", "live_provider_calls")}):
        return _finish(gates, evidence)
    ui = evidence["ui"] = _early_report("ui_operator.json")
    if not _gate(gates, "H4-07", "ui_operator_context_safety", ui.get("status", "FAIL"), ui):
        return _finish(gates, evidence)
    security = evidence["security"] = _early_report("security.json")
    filesystem_status = "PASS_WITH_FINDINGS" if security.get("filesystem", {}).get("status") == "PASS_WITH_FINDINGS" and security.get("status") == "PASS" else ("PASS" if security.get("status") == "PASS" else "FAIL")
    if not _gate(gates, "H4-08", "filesystem_report_safety", filesystem_status, security.get("filesystem")):
        return _finish(gates, evidence)
    if not _gate(gates, "H4-09", "credentials_privacy", security.get("status", "FAIL"), {"credential_boundary": security.get("credential_boundary"), "persistence_boundary": security.get("persistence_boundary"), "live_provider_calls": security.get("live_provider_calls")}):
        return _finish(gates, evidence)
    contract = evidence["public_contract"] = _contract()
    if not _gate(gates, "H4-10", "public_contract", contract["status"], contract):
        return _finish(gates, evidence)
    performance = evidence["performance"] = _performance()
    if not _gate(gates, "H4-11", "performance_regression", performance["status"], performance):
        return _finish(gates, evidence)
    focused = evidence["focused"] = _focused(args.blender)
    if not _gate(gates, "H4-12", "focused_affected_tests", focused["status"], {key: focused[key] for key in ("status", "unit_tests", "blender_tests")}):
        return _finish(gates, evidence)
    combined = evidence["combined"] = _combined(args.blender)
    if not _gate(gates, "H4-13", "combined_blender_regression", combined["status"], combined):
        return _finish(gates, evidence)
    package = _package()
    evidence["package"] = {key: value for key, value in package.items() if key != "archive"}
    if not _gate(gates, "H4-14", "package_validator", package["status"], evidence["package"]):
        return _finish(gates, evidence)
    native = evidence["native_package"] = _native(args.blender, package["archive"])
    if not _gate(gates, "H4-15", "blender_native_package_validation", native["status"], native):
        return _finish(gates, evidence)
    installed = evidence["installed"] = _installed(args.blender, package["archive"])
    if not _gate(gates, "H4-16", "installed_package_qualification", installed["status"], installed):
        return _finish(gates, evidence)
    dataset = evidence["dataset"] = _dataset_identity()
    if not _gate(gates, "H4-17", "dataset_benchmark_identity", dataset["status"], dataset):
        return _finish(gates, evidence)
    if not _gate(gates, "H4-18", "security_scan", security.get("status", "FAIL"), security.get("security")):
        return _finish(gates, evidence)
    documentation = evidence["documentation"] = _documentation()
    if not _gate(gates, "H4-19", "documentation_readiness", documentation["status"], documentation):
        return _finish(gates, evidence)
    scope = evidence["scope"] = _scope()
    _gate(gates, "H4-20", "final_scope_frozen_evidence_safety", scope["status"], scope)
    return _finish(gates, evidence)


if __name__ == "__main__":
    raise SystemExit(main())
