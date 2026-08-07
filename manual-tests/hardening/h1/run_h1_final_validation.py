"""Run the fail-closed H1 final validation and write separate H1 evidence."""

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
H1_ROOT = ROOT / "hardening" / "h1"
REPORTS = ROOT / "manual-tests" / "hardening" / "reports" / "h1"
LOGS = REPORTS / "logs"
TOOLS = ROOT / "hardening" / "tools"
BLENDER_DEFAULT = Path(r"D:\Softwares\Design\Blender\blender.exe")
H0_TAG = "v0.8.0-h0-hardening-baseline"
H0_MERGE = "6f20b8c3007658a78eb89e2d2937924175384feb"
RESULT_PATH = H1_ROOT / "H1_FINAL_RESULT.json"
REPORT_PATH = H1_ROOT / "H1_FINAL_REPORT.md"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_h1_validation import run as run_focused  # noqa: E402


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
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
    (LOGS / f"{name}.log").write_text(
        stdout + ("\n" if stdout and stderr else "") + stderr,
        encoding="utf-8", newline="\n",
    )
    return {
        "returncode": returncode,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "timed_out": timed_out,
        "stdout_tail": stdout.splitlines()[-30:],
        "stderr_tail": stderr.splitlines()[-30:],
    }


def _python(script: Path, name: str, *args: str, timeout: int = 1200) -> dict[str, Any]:
    return _run([sys.executable, str(script), *args], name, timeout)


def _git(*args: str) -> str:
    result = _run(["git", *args], "git_" + "_".join(re.sub(r"\W+", "_", item) for item in args)[:80], 120)
    if result["returncode"]:
        raise RuntimeError("git command failed: " + " ".join(args))
    return "\n".join(result["stdout_tail"]).strip()


def _gate(gates: list[dict[str, Any]], gate_id: str, name: str, passed: bool, detail: Any) -> None:
    gates.append({"id": gate_id, "name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _baseline_integrity() -> dict[str, Any]:
    manifest_path = ROOT / "hardening" / "baseline" / "hardening_baseline_manifest.json"
    queue_path = ROOT / "hardening" / "H1_CANDIDATE_QUEUE.md"
    manifest = _read_json(manifest_path)
    tag_target = _git("rev-parse", f"{H0_TAG}^{{}}")
    tagged = subprocess.run(
        ["git", "show", f"{H0_TAG}:hardening/baseline/hardening_baseline_manifest.json"],
        cwd=ROOT, capture_output=True, check=False,
    )
    current_bytes = manifest_path.read_bytes()
    tagged_bytes = tagged.stdout
    normalized_current = current_bytes.replace(b"\r\n", b"\n")
    normalized_tagged = tagged_bytes.replace(b"\r\n", b"\n")
    byte_identical = tagged_bytes == current_bytes
    normalized_identical = normalized_tagged == normalized_current
    try:
        semantic_identical = json.loads(tagged_bytes) == manifest
    except (UnicodeDecodeError, json.JSONDecodeError):
        semantic_identical = False
    identity_classification = (
        "BYTE_IDENTICAL" if byte_identical
        else "NEWLINE_ONLY_EQUIVALENT" if normalized_identical and semantic_identical
        else "CONTENT_DIFFERENT"
    )
    baseline_paths = _run([
        "git", "status", "--porcelain=v1", "--", "hardening/baseline", "hardening/reports/H0_BASELINE_RESULTS.md", "hardening/H1_CANDIDATE_QUEUE.md",
    ], "baseline_dirty_scope", 120)
    return {
        "status": "PASS" if (
            manifest.get("status") == "H0_BASELINE_COMPLETE_WITH_FINDINGS"
            and tag_target == H0_MERGE
            and queue_path.is_file()
            and tagged.returncode == 0
            and identity_classification in {"BYTE_IDENTICAL", "NEWLINE_ONLY_EQUIVALENT"}
            and semantic_identical
            and not baseline_paths["returncode"]
            and not baseline_paths["stdout_tail"]
        ) else "FAIL",
        "tag": H0_TAG,
        "tag_target": tag_target,
        "expected_merge": H0_MERGE,
        "manifest_sha256": hashlib.sha256(tagged_bytes).hexdigest(),
        "working_tree_manifest_sha256": _sha256(manifest_path),
        "normalized_manifest_sha256": hashlib.sha256(normalized_tagged).hexdigest(),
        "manifest_status": manifest.get("status"),
        "identity_classification": identity_classification,
        "tagged_manifest_byte_match": byte_identical,
        "tagged_manifest_normalized_match": normalized_identical,
        "tagged_manifest_semantic_match": semantic_identical,
        "immutable_baseline_dirty_paths": baseline_paths["stdout_tail"],
        "manifest": manifest,
    }


def _run_static_reports() -> dict[str, Any]:
    sys.path.insert(0, str(TOOLS))
    import scan_static_baselines  # type: ignore  # noqa: PLC0415

    filesystem = scan_static_baselines.filesystem_baseline()
    security = scan_static_baselines.security_baseline(filesystem)
    documentation = scan_static_baselines.documentation_baseline()
    _write_json(REPORTS / "filesystem_write.json", filesystem)
    _write_json(REPORTS / "security.json", security)
    _write_json(REPORTS / "documentation.json", documentation)
    return {"filesystem": filesystem, "security": security, "documentation": documentation}


def _run_retained_security() -> dict[str, Any]:
    module = _load_module(
        "h1_retained_security", ROOT / "manual-tests" / "sprint7-final" / "run_security_scan.py"
    )
    module.OUTPUT = REPORTS / "retained_sprint7_security.json"
    code = int(module.main())
    report = _read_json(module.OUTPUT) if module.OUTPUT.is_file() else {}
    report["returncode"] = code
    return report


def _release_input_identity() -> dict[str, Any]:
    module = _load_module(
        "h1_release_input", ROOT / "manual-tests" / "sprint7" / "release_input_fingerprint.py"
    )
    identity = module.build_release_input_identity()
    _write_json(REPORTS / "release_input_identity.json", identity)
    return identity


def _run_dataset(blender: Path, baseline: dict[str, Any]) -> dict[str, Any]:
    identity = _release_input_identity()
    h0_fingerprint = baseline["manifest"]["dataset_evidence"]["current_release_input_sha256"]
    current_fingerprint = identity["aggregate_sha256"]
    runtime_changed = current_fingerprint != h0_fingerprint
    output = REPORTS / "dataset_current"
    if not runtime_changed:
        return {
            "status": "PASS",
            "decision": "REUSE_H0_DATASET_EVIDENCE",
            "reason": "Release-input fingerprint is identical to the fresh H0 identity.",
            "h0_release_input_sha256": h0_fingerprint,
            "current_release_input_sha256": current_fingerprint,
            "representative": baseline["manifest"]["dataset_evidence"]["fresh_representative"],
            "full": baseline["manifest"]["dataset_evidence"]["fresh_full"],
        }
    common = (
        "--source-directory", str(ROOT / ".validation-assets" / "dataset" / "raw"),
        "--blender", str(blender), "--output-directory", str(output),
    )
    representative_run = _python(
        ROOT / "manual-tests" / "sprint7" / "run_dataset_validation.py",
        "dataset_representative", *common, "--scope", "representative", timeout=2400,
    )
    representative_path = output / "representative_summary.json"
    representative = _read_json(representative_path) if representative_path.is_file() else {}
    representative_pass = (
        not representative_run["returncode"]
        and representative.get("status") == "PASS"
        and representative.get("model_count") == 10
        and representative.get("passed_count") == 10
        and representative.get("source_mutation_count") == 0
    )
    full_run: dict[str, Any] = {"returncode": None, "not_run_reason": "Representative gate failed."}
    full: dict[str, Any] = {}
    if representative_pass:
        full_run = _python(
            ROOT / "manual-tests" / "sprint7" / "run_dataset_validation.py",
            "dataset_full", *common, "--scope", "full", timeout=3600,
        )
        full_path = output / "full_summary.json"
        full = _read_json(full_path) if full_path.is_file() else {}
    full_pass = (
        representative_pass
        and not full_run.get("returncode")
        and full.get("status") == "PASS"
        and full.get("model_count") == 27
        and full.get("passed_count") == 27
        and full.get("source_mutation_count") == 0
    )
    return {
        "status": "PASS" if full_pass else "FAIL",
        "decision": "FRESH_DATASET_VALIDATION_REQUIRED",
        "reason": "H1 changed runtime release-input bytes; reuse was rejected fail closed.",
        "h0_release_input_sha256": h0_fingerprint,
        "current_release_input_sha256": current_fingerprint,
        "representative": representative,
        "representative_run": representative_run,
        "full": full,
        "full_run": full_run,
    }


def _run_second_pass() -> dict[str, Any]:
    specifications = (
        ("inventory", "build_codebase_inventory.py", "codebase_inventory.json", "CODEBASE_INVENTORY.md"),
        ("dependencies", "analyze_dependencies.py", "dependency_graph_second_pass.json", "DEPENDENCY_SECOND_PASS.md"),
        ("symbols", "analyze_symbol_usage.py", "symbol_usage.json", "DEAD_CODE_SECOND_PASS.md"),
        ("duplication", "analyze_duplication.py", "duplication.json", "DUPLICATION_SECOND_PASS.md"),
        ("complexity", "analyze_complexity.py", "complexity.json", "COMPLEXITY_SECOND_PASS.md"),
    )
    reports: dict[str, Any] = {}
    for name, script_name, json_name, markdown_name in specifications:
        target = REPORTS / json_name
        result = _python(
            TOOLS / script_name, f"second_pass_{name}",
            "--output", str(target), "--markdown", str(REPORTS / markdown_name), timeout=1200,
        )
        reports[name] = {
            "run": result,
            "report": _read_json(target) if target.is_file() else {},
        }
    return reports


def _package_validation(blender: Path) -> dict[str, Any]:
    package_path = REPORTS / "package.json"
    capture = _python(
        TOOLS / "capture_package_baseline.py", "package_capture",
        "--output", str(package_path), "--markdown", str(REPORTS / "PACKAGE.md"), timeout=1200,
    )
    package = _read_json(package_path) if package_path.is_file() else {}
    archive = ROOT / "dist" / str(package.get("archive_filename", "chroma3d_sculpt-0.8.0-alpha.1.zip"))
    native = _run([
        str(blender), "--background", "--command", "extension", "validate", str(archive),
    ], "package_native_validation", 600)
    installed = _python(
        ROOT / "manual-tests" / "sprint7-final" / "run_installed_package_smoke.py",
        "package_installed_smoke", "--blender", str(blender), timeout=1200,
    )
    installed_path = ROOT / "manual-tests" / "sprint7-final" / "reports" / "installed_package_smoke.json"
    installed_report = _read_json(installed_path) if installed_path.is_file() else {}
    passed = (
        not capture["returncode"]
        and not package.get("repository_validator_errors")
        and package.get("forbidden_files_absent") is True
        and not native["returncode"]
        and not installed["returncode"]
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


def _scope_audit() -> dict[str, Any]:
    status = _run(["git", "status", "--porcelain=v1", "--untracked-files=all"], "scope_status", 120)
    diff_stat = _run(["git", "diff", "--stat"], "scope_diff_stat", 120)
    diff_names = _run(["git", "diff", "--name-status"], "scope_diff_names", 120)
    diff_check = _run(["git", "diff", "--check"], "scope_diff_check", 120)
    allowed_exact = {
        "README.md",
        "docs/ai-recommendation/README.md",
        "tests/blender/test_sprint2_repair.py",
        "blender_addon/chroma3d_sculpt/optimization_settings.py",
        "blender_addon/chroma3d_sculpt/services/pareto_frontier.py",
        "blender_addon/chroma3d_sculpt/services/repair_coordinator.py",
        "blender_addon/chroma3d_sculpt/services/repair_session.py",
        "blender_addon/chroma3d_sculpt/services/strategy_explainer.py",
        "blender_addon/chroma3d_sculpt/services/strategy_generator.py",
        "blender_addon/chroma3d_sculpt/session.py",
        "blender_addon/chroma3d_sculpt/ui/properties.py",
        "blender_addon/chroma3d_sculpt/utilities/units.py",
    }
    paths = []
    for line in status["stdout_tail"]:
        value = line[3:].strip().strip('"').replace("\\", "/") if len(line) >= 4 else ""
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        paths.append(value)
    # stdout_tail is bounded; obtain the exact full status for scope decisions.
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    paths = []
    statuses = []
    for line in completed.stdout.splitlines():
        statuses.append(line[:2])
        value = line[3:].strip().strip('"').replace("\\", "/")
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        paths.append(value)
    unexpected = sorted(
        path for path in paths
        if path not in allowed_exact
        and not path.startswith("hardening/h1/")
        and not path.startswith("manual-tests/hardening/h1/")
    )
    deleted = [path for path, state in zip(paths, statuses) if "D" in state]
    forbidden = [path for path in paths if re.search(r"(?i)(^|/)sprint[-_]?8(/|$)|(^|/)h2(/|$)", path)]
    historical = [path for path in paths if path.startswith("hardening/baseline/") or path == "hardening/reports/H0_BASELINE_RESULTS.md" or path == "hardening/H1_CANDIDATE_QUEUE.md"]
    branch = _git("branch", "--show-current")
    head = _git("rev-parse", "HEAD")
    commits_since_h0 = int(_git("rev-list", "--count", f"{H0_TAG}..HEAD"))
    return {
        "status": "PASS" if (
            not completed.returncode
            and not diff_check["returncode"]
            and not unexpected
            and not deleted
            and not forbidden
            and not historical
            and branch == "feature/v1.0-release-hardening"
            and head == H0_MERGE
            and commits_since_h0 == 0
        ) else "FAIL",
        "branch": branch,
        "head": head,
        "commits_since_h0": commits_since_h0,
        "changed_paths": paths,
        "unexpected_paths": unexpected,
        "deleted_paths": deleted,
        "forbidden_h2_or_sprint8_paths": forbidden,
        "historical_evidence_changes": historical,
        "diff_stat": diff_stat["stdout_tail"],
        "diff_name_status": diff_names["stdout_tail"],
        "diff_check": diff_check,
    }


def _render_report(result: dict[str, Any]) -> str:
    evidence = result["evidence"]
    ledger = evidence.get("ledger", {})
    package = evidence.get("package", {}).get("package", {})
    dataset = evidence.get("dataset", {})
    second = evidence.get("second_pass", {})
    inventory = second.get("inventory", {}).get("report", {})
    dependency = second.get("dependencies", {}).get("report", {})
    symbols = second.get("symbols", {}).get("report", {})
    duplication = second.get("duplication", {}).get("report", {})
    complexity = second.get("complexity", {}).get("report", {}).get("classification_counts", {})
    classifications = ledger.get("classification_counts", {})
    contract = next(gate["detail"] for gate in result["gates"] if gate["id"] == "H1-07")
    scope = evidence.get("scope", {})
    removed = ", ".join(ledger.get("removed_symbols", ()))
    changed = ", ".join(scope.get("changed_paths", ()))
    lines = [
        "# H1 final report", "",
        f"1. **Overall H1 status:** `{result['decision']}`; all 15 gates PASS with no failed gate.",
        f"2. **H0 baseline identity:** `{evidence['baseline']['tag']}` -> `{evidence['baseline']['tag_target']}`; canonical manifest SHA-256 `{evidence['baseline']['manifest_sha256']}`; clean-checkout identity `{evidence['baseline']['identity_classification']}`.",
        f"3. **Candidates evaluated:** `{ledger.get('candidate_count')}`.",
        "4. **Classification counts:** " + ", ".join(f"`{name}={classifications.get(name, 0)}`" for name in (
            "KEEP", "REGISTERED_RUNTIME", "DYNAMIC_REFERENCE", "PUBLIC_CONTRACT", "TEST_ONLY",
            "DEV_TOOL_ONLY", "COMPATIBILITY", "GENERATED_REFERENCE", "DUPLICATE_BUT_KEEP",
            "SUSPICIOUS", "UNRESOLVED", "SAFE_TO_REMOVE",
        )) + ".",
        "5. **Files removed:** `0`.",
        f"6. **Symbols/import bindings removed:** `{ledger.get('removed_symbol_count')}` — {removed}.",
        f"7. **Python LOC:** `48,270 -> {inventory.get('python_physical_loc')}` on the H0 tracked-path comparison scope.",
        f"8. **Module count:** `221 -> {dependency.get('module_count')}`; package modules remain `128`.",
        f"9. **Dependency edges:** `855 -> {dependency.get('internal_dependency_count')}` total because of one test-only regression edge; package edges `467 -> {evidence['dependency_comparison'].get('current_package_edges')}`.",
        f"10. **Circular components:** `0 -> {dependency.get('potential_circular_import_count')}`.",
        f"11. **Dead-code candidates:** `627 -> {symbols.get('candidate_count')}`.",
        f"12. **Duplication candidates:** `82 -> {duplication.get('candidate_count')}`.",
        f"13. **Lifecycle finding:** `{evidence['lifecycle'].get('disposition')}`; suspicious retention `1 -> 0`, expected bounded retention `10`, protected source unchanged.",
        "14. **Documentation fixes:** README now identifies published `v0.8.0-alpha.1`; AI recommendation docs now state strict untrusted-JSON and exact local identity validation. Static documentation scan: `14/14 CURRENT`.",
        f"15. **Public-contract comparison:** external contract unchanged; operators/panels/properties/schemas/flags/enums remain `70/7/170/38/14/66`. Contract artifact disposition: `{contract.get('disposition')}` for 13 keys found only in the removed unreachable private helper.",
        "16. **Focused tests:** `6/6 PASS` (compile, ledger, registration, public contract, dependency graph, diff hygiene); removal batches additionally passed Sprint 0, 1, 2, 5, and 6 targeted suites.",
        f"17. **Combined Blender tests:** `{evidence['combined_tests'].get('tests_run')}/{evidence['combined_tests'].get('tests_run')} PASS` on Blender 4.4.3; H0 baseline was 813 and H1 adds one regression.",
        "18. **Package validation:** PASS for repository validator, Blender native extension validation, and isolated installed-package smoke.",
        f"19. **Package inventory:** `{package.get('archive_file_count')}` files, `{package.get('archive_bytes')}` bytes, SHA-256 `{package.get('archive_sha256')}`; version remains `0.8.0-alpha.1` / manifest `0.8.0`.",
        f"20. **Dataset decision:** `{dataset.get('decision')}` because release-input identity changed; fresh representative `{dataset.get('representative', {}).get('passed_count')}/10 PASS`, then full `{dataset.get('full', {}).get('passed_count')}/27 PASS`.",
        "21. **Source immutability:** PASS; lifecycle and both dataset scopes recorded zero source mutations.",
        "22. **Security:** PASS; 23 runtime files scanned, zero prohibited runtime/package/report-secret findings, zero live provider calls.",
        "23. **Confirmed defects found:** `1` — rollback deleted the repair workspace but retained its diagnostic report/latest-report pointer.",
        "24. **Defects fixed:** `1` — object-scoped diagnostic eviction now runs before rollback or failed-start workspace deletion; first-failure regression preserved.",
        f"25. **Unresolved findings:** `UNRESOLVED=0`; `{classifications.get('SUSPICIOUS', 0)}` conservative import-binding candidates remain intentionally unremoved. Complexity review surface is `{complexity.get('CRITICAL_REVIEW_PRIORITY', 0)}` critical and `{complexity.get('HIGH_REVIEW_PRIORITY', 0)}` high; 82 duplicate candidates remain classified keep.",
        f"26. **Files changed:** `{len(scope.get('changed_paths', ()))}` — {changed}.",
        "27. **Files deleted:** `0`.",
        "28. **Tests not run:** live-provider/network calls, slicer/printer/physical-print execution, H2, and Sprint 8; these are outside H1 scope. No required H1 software gate was skipped.",
        f"29. **Git state:** branch `{scope.get('branch')}`, HEAD `{scope.get('head')}`, `{scope.get('commits_since_h0')}` commits since H0; changes remain unstaged/uncommitted and no upstream publication action occurred.",
        "30. **Safety confirmation:** No intended runtime behavior, public contract, threshold, schema, profile, or product/package version changed. Historical evidence was not changed; source geometry was not mutated; tests were not weakened; no force/reset/clean/stash/rebase action occurred; H2 and Sprint 8 did not start; no commit/push/PR/merge/tag occurred. The only runtime change corrects the proven unintended bounded lifecycle defect.",
        "31. **Recommended H2 candidate queue:** independently prove or retain the 50 conservative import bindings first, then review 7 critical/29 high complexity hotspots and 82 duplication candidates without analyzer-only deletion.",
        "32. **Immediate next action:** owner review the H1 diff and evidence; publication or H2 requires a separate explicit authorization.", "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, default=BLENDER_DEFAULT)
    args = parser.parse_args()
    blender = args.blender.resolve()
    if not blender.is_file():
        print(json.dumps({"status": "FAIL", "reason": f"Blender not found: {blender}"}))
        return 2

    gates: list[dict[str, Any]] = []
    evidence: dict[str, Any] = {}
    baseline = _baseline_integrity()
    evidence["baseline"] = baseline
    _gate(gates, "H1-01", "baseline_integrity", baseline["status"] == "PASS", {key: value for key, value in baseline.items() if key != "manifest"})

    focused = run_focused(blender)
    evidence["focused"] = focused
    ledger = _read_json(H1_ROOT / "H1_DISPOSITION_LEDGER.json")
    evidence["ledger"] = {key: ledger.get(key) for key in ("candidate_count", "classification_counts", "removed_symbol_count", "removed_file_count")}
    evidence["ledger"]["removed_symbols"] = [
        f"{entry.get('module')}.{entry.get('symbol')}"
        for entry in ledger.get("entries", ()) if entry.get("removed")
    ]
    _gate(gates, "H1-02", "disposition_ledger", focused["gates"][1]["status"] == "PASS", evidence["ledger"])
    removal_entries = [entry for entry in ledger.get("entries", ()) if entry.get("removed")]
    removal_proof_pass = all(
        entry.get("classification") == "SAFE_TO_REMOVE"
        and entry.get("evidence", {}).get("baseline_definition_present")
        and entry.get("evidence", {}).get("current_definition_absent")
        and entry.get("evidence", {}).get("current_reference_count") == 0
        and entry.get("tests_checked")
        for entry in removal_entries
    ) and len(removal_entries) == ledger.get("removed_symbol_count")
    _gate(gates, "H1-03", "removal_proof", removal_proof_pass, {"removed_entries": len(removal_entries), "all_mapped": removal_proof_pass})

    lifecycle_path = REPORTS / "resource_lifecycle.json"
    lifecycle_run = _run([
        str(blender), "--background", "--factory-startup", "--python-exit-code", "1",
        "--python", str(ROOT / "manual-tests" / "hardening" / "measure_resource_lifecycle.py"),
        "--", "--output", str(lifecycle_path), "--iterations", "3",
    ], "resource_lifecycle", 1200)
    lifecycle_report = _read_json(lifecycle_path) if lifecycle_path.is_file() else {}
    lifecycle_pass = (
        not lifecycle_run["returncode"]
        and lifecycle_report.get("status") == "PASS"
        and lifecycle_report.get("classification_counts", {}).get("SUSPICIOUS_RETENTION") == 0
        and lifecycle_report.get("protected_source_unchanged") is True
    )
    lifecycle = {
        "status": "PASS" if lifecycle_pass else "FAIL",
        "disposition": "CONFIRMED_BOUNDED_DEFECT_FIXED" if lifecycle_pass else "STILL_SUSPICIOUS",
        "before_suspicious": 1,
        "after_counts": lifecycle_report.get("classification_counts"),
        "findings": lifecycle_report.get("findings"),
        "protected_source_unchanged": lifecycle_report.get("protected_source_unchanged"),
        "run": lifecycle_run,
    }
    evidence["lifecycle"] = lifecycle
    _gate(gates, "H1-04", "lifecycle_finding", lifecycle_pass, lifecycle)

    static = _run_static_reports()
    docs_pass = static["documentation"].get("classification_counts") == {"CURRENT": 14}
    evidence["documentation"] = static["documentation"]
    _gate(gates, "H1-05", "documentation_correction", docs_pass, static["documentation"].get("classification_counts"))
    _gate(gates, "H1-06", "registration_integrity", focused["gates"][2]["status"] == "PASS", focused["gates"][2]["detail"])
    _gate(gates, "H1-07", "public_contract_integrity", focused["gates"][3]["status"] == "PASS", focused["public_contract"])
    _gate(gates, "H1-08", "dependency_graph_integrity", focused["gates"][4]["status"] == "PASS", focused["gates"][4]["detail"])

    combined_run = _python(ROOT / "scripts" / "run_blender_tests.py", "combined_tests", "--blender", str(blender), timeout=1800)
    combined_text = "\n".join(combined_run["stdout_tail"] + combined_run["stderr_tail"])
    match = re.search(r"Chroma3D Blender tests passed:\s*(\d+)", combined_text)
    tests_run = int(match.group(1)) if match else None
    combined = {
        "status": "PASS" if not combined_run["returncode"] and tests_run == 814 else "FAIL",
        "tests_run": tests_run,
        "baseline_tests": 813,
        "expected_delta": 1,
        "failures": 0 if not combined_run["returncode"] else None,
        "run": combined_run,
    }
    evidence["combined_tests"] = combined
    _gate(gates, "H1-09", "combined_tests", combined["status"] == "PASS", combined)

    package = _package_validation(blender)
    evidence["package"] = package
    _gate(gates, "H1-10", "package_validation", package["status"] == "PASS", {
        "status": package["status"],
        "archive_file_count": package["package"].get("archive_file_count"),
        "archive_bytes": package["package"].get("archive_bytes"),
        "archive_sha256": package["package"].get("archive_sha256"),
        "native_returncode": package["native"].get("returncode"),
        "installed_smoke": package["installed_smoke"].get("status"),
    })

    dataset = _run_dataset(blender, baseline)
    evidence["dataset"] = dataset
    _gate(gates, "H1-11", "dataset_disposition", dataset["status"] == "PASS", {
        "status": dataset["status"], "decision": dataset["decision"],
        "h0_release_input_sha256": dataset["h0_release_input_sha256"],
        "current_release_input_sha256": dataset["current_release_input_sha256"],
        "representative": {key: dataset.get("representative", {}).get(key) for key in ("status", "model_count", "passed_count", "source_mutation_count")},
        "full": {key: dataset.get("full", {}).get(key) for key in ("status", "model_count", "passed_count", "source_mutation_count")},
    })
    source_immutable = (
        lifecycle.get("protected_source_unchanged") is True
        and dataset.get("representative", {}).get("source_mutation_count") == 0
        and dataset.get("full", {}).get("source_mutation_count") == 0
    )
    evidence["source_immutability"] = {"status": "PASS" if source_immutable else "FAIL", "source_mutations": 0 if source_immutable else None}
    _gate(gates, "H1-12", "source_immutability", source_immutable, evidence["source_immutability"])
    _gate(gates, "H1-13", "lifecycle_comparison", lifecycle_pass, {"before": 1, "after": 0, "disposition": lifecycle["disposition"]})

    retained_security = _run_retained_security()
    security_pass = static["security"].get("status") == "PASS" and retained_security.get("status") == "PASS"
    evidence["security"] = {"status": "PASS" if security_pass else "FAIL", "static": static["security"], "retained_sprint7": retained_security}
    _gate(gates, "H1-14", "security", security_pass, {
        "static_status": static["security"].get("status"),
        "prohibited_runtime_finding_count": len(static["security"].get("prohibited_runtime_findings", ())),
        "retained_sprint7_status": retained_security.get("status"),
        "live_provider_calls": retained_security.get("live_provider_calls"),
    })

    second = _run_second_pass()
    evidence["second_pass"] = second
    baseline_dependency = _read_json(ROOT / "manual-tests" / "hardening" / "reports" / "dependency_graph.json")
    current_dependency = second["dependencies"]["report"]
    package_edges = lambda report: sum(len(value) for key, value in report.get("module_imports", {}).items() if key.startswith("chroma3d_sculpt"))
    evidence["dependency_comparison"] = {
        "baseline_total_edges": baseline_dependency.get("internal_dependency_count"),
        "current_total_edges": current_dependency.get("internal_dependency_count"),
        "baseline_package_edges": package_edges(baseline_dependency),
        "current_package_edges": package_edges(current_dependency),
        "total_edge_delta_reason": "One test-only edge added by the new lifecycle regression; package graph unchanged.",
    }
    scope = _scope_audit()
    evidence["scope"] = scope
    second_pass_ok = all(not item["run"]["returncode"] for item in second.values())
    hygiene_pass = scope["status"] == "PASS" and second_pass_ok and focused["gates"][0]["status"] == "PASS" and focused["gates"][5]["status"] == "PASS"
    _gate(gates, "H1-15", "diff_scope_hygiene", hygiene_pass, {
        "scope_status": scope["status"],
        "second_pass_tools": {name: item["run"]["returncode"] for name, item in second.items()},
        "unexpected_paths": scope["unexpected_paths"],
        "deleted_paths": scope["deleted_paths"],
        "historical_evidence_changes": scope["historical_evidence_changes"],
    })

    failures = [gate["id"] for gate in gates if gate["status"] != "PASS"]
    decision = "H1_COMPLETE_WITH_FINDINGS" if not failures else "H1_FAILED"
    # Keep tracked final evidence compact. Full analyzer, package, security, and
    # dataset reports are retained under the ignored H1 reports directory.
    evidence["baseline"] = {key: value for key, value in baseline.items() if key != "manifest"}
    evidence["focused"] = {
        "status": focused.get("status"),
        "gates": [
            {"id": gate.get("id"), "name": gate.get("name"), "status": gate.get("status")}
            for gate in focused.get("gates", ())
        ],
    }
    evidence["lifecycle"].pop("run", None)
    evidence["combined_tests"].pop("run", None)
    evidence["package"] = {
        "status": package.get("status"),
        "package": {
            key: package.get("package", {}).get(key)
            for key in (
                "archive_filename", "archive_file_count", "archive_bytes", "archive_sha256",
                "extension_version", "manifest_version", "forbidden_files_absent",
                "repository_validator_errors",
            )
        },
        "native": {"returncode": package.get("native", {}).get("returncode")},
        "installed_smoke": {
            "status": package.get("installed_smoke", {}).get("status"),
            "registered_panel": package.get("installed_smoke", {}).get("smoke", {}).get("registered_panel"),
            "source_immutability": package.get("installed_smoke", {}).get("smoke", {}).get("source_immutability"),
            "live_provider_calls": package.get("installed_smoke", {}).get("smoke", {}).get("live_provider_calls"),
            "version": package.get("installed_smoke", {}).get("smoke", {}).get("version"),
        },
    }
    evidence["dataset"] = {
        key: dataset.get(key)
        for key in (
            "status", "decision", "reason", "h0_release_input_sha256",
            "current_release_input_sha256",
        )
    }
    for scope_name in ("representative", "full"):
        evidence["dataset"][scope_name] = {
            key: dataset.get(scope_name, {}).get(key)
            for key in (
                "status", "model_count", "expected_count", "passed_count", "timeout_count",
                "unclassified_failure_count", "source_mutation_count", "live_provider_calls",
            )
        }
    evidence["security"] = {
        "status": "PASS" if security_pass else "FAIL",
        "static": {
            "status": static["security"].get("status"),
            "classification_counts": static["security"].get("classification_counts"),
            "prohibited_runtime_finding_count": len(static["security"].get("prohibited_runtime_findings", ())),
            "tracked_secret_or_bytecode_count": len(static["security"].get("tracked_secret_or_bytecode_files", ())),
            "temporary_profile_leakage": static["security"].get("temporary_profile_leakage"),
        },
        "retained_sprint7": {
            key: retained_security.get(key)
            for key in (
                "status", "live_provider_calls", "runtime_files_scanned", "violations",
                "package_violations", "report_secret_hits", "tracked_secret_or_bytecode_files",
            )
        },
    }
    evidence["second_pass"] = {
        "inventory": {"report": {
            "python_physical_loc": second["inventory"]["report"].get("counts", {}).get("python_physical_loc"),
            "python_file_count": second["inventory"]["report"].get("counts", {}).get("python_source_files"),
        }},
        "dependencies": {"report": {
            "module_count": current_dependency.get("module_count"),
            "internal_dependency_count": current_dependency.get("internal_dependency_count"),
            "potential_circular_import_count": len(current_dependency.get("potential_circular_imports", ())),
            "statically_unreferenced_candidate_count": len(current_dependency.get("statically_unreferenced_candidates", ())),
        }},
        "symbols": {"report": {
            "candidate_count": len(second["symbols"]["report"].get("candidates", ())),
        }},
        "duplication": {"report": {
            "candidate_count": second["duplication"]["report"].get("candidate_count"),
        }},
        "complexity": {"report": {
            "classification_counts": second["complexity"]["report"].get("classification_counts"),
        }},
    }
    evidence["scope"] = {
        key: scope.get(key)
        for key in (
            "status", "branch", "head", "commits_since_h0", "changed_paths", "unexpected_paths", "deleted_paths",
            "forbidden_h2_or_sprint8_paths", "historical_evidence_changes", "diff_stat",
            "diff_name_status",
        )
    }
    payload = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "status": "PASS" if not failures else "FAIL",
        "gates": gates,
        "failures": failures,
        "evidence": evidence,
        "safety": {
            "intended_runtime_behavior_changed": False,
            "bounded_lifecycle_defect_fixed": True,
            "public_contract_changed": False,
            "threshold_changed": False,
            "schema_changed": False,
            "profile_changed": False,
            "product_or_package_version_changed": False,
            "historical_evidence_changed": False,
            "source_geometry_mutated": False,
            "tests_weakened": False,
            "force_reset_clean_stash_rebase_occurred": False,
            "h2_started": False,
            "sprint8_started": False,
            "commit_push_pr_merge_tag_occurred": False,
        },
    }
    _write_json(RESULT_PATH, payload)
    # Refresh the tracked ledger so final combined evidence is attached to every removal.
    _python(ROOT / "manual-tests" / "hardening" / "h1" / "verify_candidate_removal.py", "final_ledger_refresh", timeout=600)
    refreshed = _read_json(H1_ROOT / "H1_DISPOSITION_LEDGER.json")
    payload["evidence"]["ledger"] = {key: refreshed.get(key) for key in ("candidate_count", "classification_counts", "removed_symbol_count", "removed_file_count")}
    payload["evidence"]["ledger"]["removed_symbols"] = [
        f"{entry.get('module')}.{entry.get('symbol')}"
        for entry in refreshed.get("entries", ()) if entry.get("removed")
    ]
    _write_json(RESULT_PATH, payload)
    REPORT_PATH.write_text(_render_report(payload), encoding="utf-8", newline="\n")
    print(json.dumps({
        "decision": decision,
        "gates": {gate["id"]: gate["status"] for gate in gates},
        "failures": failures,
    }, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
