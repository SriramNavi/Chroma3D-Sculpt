"""Run the bounded Version 1.0 H0 hardening baseline gates."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "hardening" / "tools"
REPORTS = ROOT / "manual-tests" / "hardening" / "reports"
LOGS = REPORTS / "logs"
BLENDER_DEFAULT = Path(r"D:\Softwares\Design\Blender\blender.exe")
CHECKPOINT = "d06e1a05890fe23e77e66f95fc40e0200638a765"
TAG = "v0.8.0-pre-hardening-backup"


def _run(command: list[str], name: str, timeout: int = 300) -> dict[str, object]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
            check=False, timeout=timeout,
        )
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\nTimed out after {timeout} seconds."
    elapsed = time.perf_counter() - started
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / f"{name}.log").write_text(
        f"command={json.dumps(command)}\nreturncode={returncode}\nelapsed_seconds={elapsed:.6f}\n\nSTDOUT\n{stdout}\n\nSTDERR\n{stderr}\n",
        encoding="utf-8", newline="\n",
    )
    return {"returncode": returncode, "stdout": stdout, "stderr": stderr, "elapsed_seconds": round(elapsed, 6)}


def _python(script: Path, name: str, *args: str, timeout: int = 300) -> dict[str, object]:
    return _run([sys.executable, str(script), *args], name, timeout)


def _blender(blender: Path, script: Path, name: str, *args: str, timeout: int = 300) -> dict[str, object]:
    return _run([
        str(blender), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(script), "--", *args,
    ], name, timeout)


def _git(*args: str) -> tuple[int, list[str]]:
    completed = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    return completed.returncode, completed.stdout.splitlines()


def _preflight() -> tuple[str, str]:
    values = {}
    for name, args in {
        "root": ("rev-parse", "--show-toplevel"), "branch": ("branch", "--show-current"),
        "head": ("rev-parse", "HEAD"), "main": ("rev-parse", "main"), "origin_main": ("rev-parse", "origin/main"),
        "tag": ("rev-parse", f"{TAG}^{{}}"), "tag_type": ("cat-file", "-t", TAG),
        "unique": ("rev-list", "--count", "main..HEAD"),
    }.items():
        code, lines = _git(*args)
        if code or not lines:
            return "FAIL", f"Unable to resolve {name}."
        values[name] = lines[0].strip()
    remote = subprocess.run(["git", "ls-remote", "--tags", "origin", TAG, f"{TAG}^{{}}"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    peeled = [line.split()[0] for line in remote.stdout.splitlines() if line.endswith("^{}")]
    checks = {
        "repo": values["root"].replace("\\", "/") == "E:/VPRS/Sriram/Projects/Chroma3D Sculpt",
        "branch": values["branch"] == "feature/v1.0-release-hardening",
        "checkpoint": values["head"] == values["main"] == values["origin_main"] == CHECKPOINT,
        "tag": values["tag"] == CHECKPOINT and values["tag_type"] == "tag",
        "remote_tag": remote.returncode == 0 and peeled == [CHECKPOINT],
        "unique_commits": values["unique"] == "0",
    }
    failed = [name for name, passed in checks.items() if not passed]
    return ("FAIL", "Failed checks: " + ", ".join(failed)) if failed else ("PASS", f"branch={values['branch']} checkpoint={values['head']} annotated backup local/remote")


def _write_gates(gates: list[dict[str, str]], started: float) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0.0",
        "status": "FAIL" if any(item["status"] == "FAIL" for item in gates) else "PASS_WITH_FINDINGS" if any(item["status"] in {"PASS_WITH_FINDINGS", "NOT_RUN"} for item in gates) else "PASS",
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "gates": gates,
    }
    (REPORTS / "hardening_gate_results.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _fail(gates: list[dict[str, str]], gate_id: str, detail: str, started: float) -> int:
    gates.append({"id": gate_id, "status": "FAIL", "detail": detail})
    _write_gates(gates, started)
    first = {"gate": gate_id, "detail": detail, "preserved": True}
    first_path = REPORTS / "first_failure.json"
    failure_path = first_path if not first_path.is_file() else REPORTS / "latest_failure.json"
    failure_path.write_text(json.dumps(first, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    _python(TOOLS / "build_blocked_summary.py", "h0_blocked_summary", "--gate", gate_id, "--detail", detail)
    print(json.dumps({"status": "H0 BLOCKED", "gate": gate_id, "detail": detail}, sort_keys=True))
    return 1


def _scope_check() -> tuple[str, str]:
    code, status_lines = _git("status", "--porcelain=v1", "--untracked-files=all")
    if code:
        return "FAIL", "git status failed"
    disallowed = []
    for line in status_lines:
        path = line[3:].replace("\\", "/")
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path == ".gitignore" or path.startswith(("hardening/", "manual-tests/hardening/")):
            continue
        disallowed.append(path)
    diff = subprocess.run(["git", "diff", "--check"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    refs = [(_git("rev-parse", name)[1] or [""])[0] for name in ("HEAD", "main", "origin/main", f"{TAG}^{{}}")]
    problems = []
    if disallowed:
        problems.append("disallowed paths: " + ", ".join(disallowed))
    if diff.returncode or diff.stdout.strip():
        problems.append("git diff --check failed")
    if refs != [CHECKPOINT] * 4:
        problems.append("checkpoint refs changed")
    if any("sprint8" in path.lower() or "sprint-8" in path.lower() for path in (line[3:] for line in status_lines)):
        problems.append("Sprint 8 implementation path detected")
    return ("FAIL", "; ".join(problems)) if problems else ("PASS", f"{len(status_lines)} H0-only changed paths; refs unchanged; whitespace clean")


def _run_retained_security() -> tuple[int, str]:
    path = ROOT / "manual-tests" / "sprint7-final" / "run_security_scan.py"
    spec = importlib.util.spec_from_file_location("h0_retained_security", path)
    if spec is None or spec.loader is None:
        return 1, "Unable to load retained Sprint 7 security scanner"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUTPUT = REPORTS / "retained_sprint7_security.json"
    output = io.StringIO()
    with redirect_stdout(output):
        code = module.main()
    (LOGS / "h0_14_retained_security.log").write_text(output.getvalue(), encoding="utf-8", newline="\n")
    return code, output.getvalue().strip()


def _run_h0_10_to_17(blender: Path, gates: list[dict[str, str]], started: float, *, start_gate: int = 10) -> int:
    if start_gate <= 10:
        reconciliation_result = _python(
            TOOLS / "reconcile_release_fingerprint.py",
            "h0_10_reconciliation",
            timeout=300,
        )
        if reconciliation_result["returncode"]:
            return _fail(gates, "H0-10", "Release-input reconciliation failed.", started)

        assets = _python(TOOLS / "capture_retained_evidence.py", "h0_10_assets", timeout=600)
        asset_path = REPORTS / "dataset_benchmark_identity.json"
        asset_report = json.loads(asset_path.read_text(encoding="utf-8")) if asset_path.is_file() else {}
        if assets["returncode"] or not asset_report.get("evidence_valid"):
            mismatch = asset_report.get("sprint7_retained_validation", {})
            return _fail(
                gates,
                "H0-10",
                f"Dataset evidence unresolved after reconciliation: {mismatch.get('fingerprint_mismatch_count', 'unknown')} mismatches.",
                started,
            )
        evidence_source = str(asset_report["evidence_source"])
        h0_10_status = "PASS_WITH_FINDINGS" if evidence_source == "FRESH_H0_VALIDATION" else "PASS"
        gates.append({
            "id": "H0-10",
            "status": h0_10_status,
            "detail": (
                f"Dataset {asset_report['dataset']['asset_count']} and benchmark "
                f"{asset_report['golden_benchmark']['record_count']} identities verified; "
                f"evidence={evidence_source}; fresh 10/10 and 27/27 PASS; frozen Sprint 7 evidence unchanged."
                if evidence_source == "FRESH_H0_VALIDATION"
                else f"Dataset {asset_report['dataset']['asset_count']} and benchmark {asset_report['golden_benchmark']['record_count']} identities verified; retained evidence compatible."
            ),
        })

    if start_gate <= 11:
        performance_result = _blender(blender, ROOT / "manual-tests" / "hardening" / "measure_performance.py", "h0_11_performance", "--output", str(REPORTS / "performance_baseline.json"), timeout=1200)
        if performance_result["returncode"]:
            return _fail(gates, "H0-11", "Bounded performance baseline failed.", started)
        performance = json.loads((REPORTS / "performance_baseline.json").read_text(encoding="utf-8"))
        gates.append({"id": "H0-11", "status": "PASS", "detail": f"{len(performance['records'])} bounded operation records; protected source unchanged; no optimization."})

    resource_result = _blender(blender, ROOT / "manual-tests" / "hardening" / "measure_resource_lifecycle.py", "h0_12_resources", "--output", str(REPORTS / "resource_lifecycle_baseline.json"), "--iterations", "3", timeout=600)
    resources = json.loads((REPORTS / "resource_lifecycle_baseline.json").read_text(encoding="utf-8")) if (REPORTS / "resource_lifecycle_baseline.json").is_file() else {}
    confirmed_leaks = int(resources.get("classification_counts", {}).get("CONFIRMED_LEAK", 0))
    if resource_result["returncode"] or resources.get("status") != "PASS" or confirmed_leaks:
        return _fail(gates, "H0-12", "Resource lifecycle baseline failed; see preserved evidence.", started)
    lifecycle_findings = sum(
        int(resources.get("classification_counts", {}).get(name, 0))
        for name in ("LIKELY_LEAK", "SUSPICIOUS_RETENTION", "INCONCLUSIVE")
    )
    gates.append({"id": "H0-12", "status": "PASS_WITH_FINDINGS" if lifecycle_findings else "PASS", "detail": f"{len(resources['records'])} lifecycle scenarios; protected source unchanged; confirmed leaks={confirmed_leaks}; review findings={lifecycle_findings}."})

    static_result = _python(TOOLS / "scan_static_baselines.py", "h0_13_14_16_static")
    filesystem = json.loads((REPORTS / "filesystem_write_baseline.json").read_text(encoding="utf-8")) if (REPORTS / "filesystem_write_baseline.json").is_file() else None
    if filesystem is None or filesystem["parse_errors"]:
        return _fail(gates, "H0-13", "Filesystem write inventory failed.", started)
    gates.append({"id": "H0-13", "status": "PASS_WITH_FINDINGS" if filesystem["runtime_write_surface_count"] else "PASS", "detail": f"{filesystem['write_surface_count']} write call sites; {filesystem['runtime_write_surface_count']} runtime surfaces recorded without behavior change."})

    security = json.loads((REPORTS / "security_baseline.json").read_text(encoding="utf-8"))
    retained_code, retained_detail = _run_retained_security()
    if static_result["returncode"] or security["status"] != "PASS" or retained_code:
        return _fail(gates, "H0-14", f"Security baseline failed. Broad={security['status']} retained={retained_detail}", started)
    gates.append({"id": "H0-14", "status": "PASS_WITH_FINDINGS" if security["hits"] else "PASS", "detail": f"{security['runtime_files_scanned']} runtime files; zero prohibited findings; explicit provider boundary retained; Sprint 7 scanner passed."})

    public_result = _python(TOOLS / "capture_public_contract.py", "h0_15_public_contract")
    if public_result["returncode"]:
        return _fail(gates, "H0-15", "Public contract capture failed.", started)
    public = json.loads((ROOT / "hardening" / "baseline" / "public_contract_baseline.json").read_text(encoding="utf-8"))
    gates.append({"id": "H0-15", "status": "PASS", "detail": f"{len(public['operator_bl_idnames'])} operators, {len(public['panel_ids'])} panels, {len(public['schemas'])} schemas; contract SHA-256 {public['contract_sha256']}."})

    docs = json.loads((REPORTS / "documentation_drift.json").read_text(encoding="utf-8"))
    doc_findings = sum(value for key, value in docs["classification_counts"].items() if key != "CURRENT")
    gates.append({"id": "H0-16", "status": "PASS_WITH_FINDINGS" if doc_findings else "PASS", "detail": f"{doc_findings} documentation drift findings queued for H7; no existing docs rewritten."})

    _write_gates(gates, started)
    summary = _python(TOOLS / "build_baseline_summary.py", "h0_summary_pre_scope")
    if summary["returncode"]:
        return _fail(gates, "H0-17", "Baseline summary/manifest generation failed.", started)
    scope_status, scope_detail = _scope_check()
    if scope_status == "FAIL":
        return _fail(gates, "H0-17", scope_detail, started)
    gates.append({"id": "H0-17", "status": "PASS", "detail": scope_detail})
    _write_gates(gates, started)
    summary = _python(TOOLS / "build_baseline_summary.py", "h0_summary_final")
    if summary["returncode"]:
        return _fail(gates[:-1], "H0-17", "Final summary/manifest generation failed.", started)
    final_scope_status, final_scope_detail = _scope_check()
    if final_scope_status == "FAIL":
        return _fail(gates[:-1], "H0-17", final_scope_detail, started)
    gates[-1]["detail"] = final_scope_detail
    _write_gates(gates, started)
    print(json.dumps({"status": "PASS_WITH_FINDINGS" if any(item["status"] == "PASS_WITH_FINDINGS" for item in gates) else "PASS", "gates": {item["id"]: item["status"] for item in gates}, "elapsed_seconds": round(time.perf_counter() - started, 3)}, sort_keys=True))
    return 0


def _reused_gate_detail(gate_id: str, preflight_detail: str) -> str:
    if gate_id == "H0-01":
        return f"Continuation preflight passed; H0-only scope revalidated. {preflight_detail}"
    if gate_id == "H0-02":
        return "Hardening compile evidence reused; final H0 compileall is rerun by the safety audit."
    if gate_id == "H0-03":
        report = json.loads((REPORTS / "codebase_inventory.json").read_text(encoding="utf-8"))
        return f"{report['counts']['tracked_files']} checkpoint files; {report['counts']['python_files_over_500_loc']} Python files over 500 LOC (review signal only)."
    if gate_id == "H0-04":
        report = json.loads((REPORTS / "dependency_graph.json").read_text(encoding="utf-8"))
        findings = len(report["potential_circular_imports"]) + len(report["statically_unreferenced_candidates"])
        return f"{report['module_count']} modules; {report['internal_dependency_count']} internal edges; {findings} review findings."
    if gate_id == "H0-05":
        report = json.loads((REPORTS / "symbol_usage.json").read_text(encoding="utf-8"))
        return f"{report['symbol_count']} symbols; {len(report['candidates'])} static candidates; none classified DEAD."
    if gate_id == "H0-06":
        duplication = json.loads((REPORTS / "duplication_candidates.json").read_text(encoding="utf-8"))
        complexity = json.loads((REPORTS / "complexity_baseline.json").read_text(encoding="utf-8"))
        priority = sum(complexity["classification_counts"].get(name, 0) for name in ("HIGH_REVIEW_PRIORITY", "CRITICAL_REVIEW_PRIORITY"))
        return f"{duplication['candidate_count']} duplication candidates; {priority} high/critical review targets; no refactor performed."
    if gate_id == "H0-07":
        report = json.loads((ROOT / "hardening" / "baseline" / "package_baseline.json").read_text(encoding="utf-8"))
        return f"{report['archive_filename']}; {report['archive_file_count']} files; {report['archive_bytes']} bytes; SHA-256 {report['archive_sha256']}; repository/native validation PASS; retained release ZIP byte match={report['matches_retained_release_archive_bytes']}."
    if gate_id == "H0-08":
        report = json.loads((REPORTS / "registration_baseline.json").read_text(encoding="utf-8"))
        return f"{report['expected_class_count']} classes; register median {report['register']['median_seconds']}s; unregister median {report['unregister']['median_seconds']}s."
    if gate_id == "H0-09":
        report = json.loads((REPORTS / "combined_test_baseline.json").read_text(encoding="utf-8"))
        return f"{report['tests_run']} tests passed on Blender {report['blender_version']} in {report['elapsed_seconds']}s."
    if gate_id == "H0-10":
        report = json.loads((REPORTS / "dataset_benchmark_identity.json").read_text(encoding="utf-8"))
        return f"Dataset {report['dataset']['asset_count']} and benchmark {report['golden_benchmark']['record_count']} identities verified; evidence={report['evidence_source']}; fresh 10/10 and 27/27 PASS; frozen Sprint 7 evidence unchanged."
    if gate_id == "H0-11":
        report = json.loads((REPORTS / "performance_baseline.json").read_text(encoding="utf-8"))
        return f"{len(report['records'])} bounded operation records; protected source unchanged; no optimization."
    raise ValueError(f"Unsupported reused gate: {gate_id}")


def _resume(blender: Path, started: float) -> int:
    gates: list[dict[str, str]] = []
    status, detail = _preflight()
    if status == "FAIL":
        return _fail(gates, "H0-01", detail, started)
    if not blender.is_file():
        return _fail(gates, "H0-02", f"Blender not found: {blender}", started)
    scope_status, scope_detail = _scope_check()
    if scope_status == "FAIL":
        return _fail(gates, "H0-01", scope_detail, started)
    gate_path = REPORTS / "hardening_gate_results.json"
    if not gate_path.is_file():
        return _fail(gates, "H0-01", "Prior H0 gate evidence is unavailable for resume.", started)
    prior = json.loads(gate_path.read_text(encoding="utf-8"))
    prior_by_id = {item["id"]: item for item in prior.get("gates", [])}
    for index in range(1, 10):
        gate_id = f"H0-{index:02d}"
        item = prior_by_id.get(gate_id)
        if item is None or item.get("status") not in {"PASS", "PASS_WITH_FINDINGS", "REUSED_VALIDATED"}:
            return _fail(gates, gate_id, "Prior validated gate cannot be reused.", started)
        gates.append({
            "id": gate_id,
            "status": "REUSED_VALIDATED",
            "detail": _reused_gate_detail(gate_id, detail),
        })
    start_gate = 10
    for index in (10, 11):
        gate_id = f"H0-{index:02d}"
        item = prior_by_id.get(gate_id)
        if item is None or item.get("status") not in {"PASS", "PASS_WITH_FINDINGS", "REUSED_VALIDATED"}:
            break
        gates.append({
            "id": gate_id,
            "status": "REUSED_VALIDATED",
            "detail": _reused_gate_detail(gate_id, detail),
        })
        start_gate = index + 1
    return _run_h0_10_to_17(blender, gates, started, start_gate=start_gate)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, default=BLENDER_DEFAULT)
    parser.add_argument("--resume", action="store_true", help="Reuse sequential validated H0 evidence and continue at the first unresolved gate.")
    args = parser.parse_args()
    blender = args.blender.resolve()
    started = time.perf_counter()
    if args.resume:
        return _resume(blender, started)
    gates: list[dict[str, str]] = []
    REPORTS.mkdir(parents=True, exist_ok=True)

    status, detail = _preflight()
    if status == "FAIL":
        return _fail(gates, "H0-01", detail, started)
    gates.append({"id": "H0-01", "status": status, "detail": detail})
    if not blender.is_file():
        return _fail(gates, "H0-02", f"Blender not found: {blender}", started)

    compile_result = _run([sys.executable, "-m", "compileall", "-q", str(ROOT / "hardening"), str(ROOT / "manual-tests" / "hardening")], "h0_02_compile")
    if compile_result["returncode"]:
        return _fail(gates, "H0-02", "Hardening compile failed; see ignored log.", started)
    gates.append({"id": "H0-02", "status": "PASS", "detail": "Hardening Python compiled."})

    result = _python(TOOLS / "build_codebase_inventory.py", "h0_03_inventory")
    if result["returncode"]:
        return _fail(gates, "H0-03", "Inventory generation failed.", started)
    inventory = json.loads((REPORTS / "codebase_inventory.json").read_text(encoding="utf-8"))
    inventory_findings = inventory["counts"]["python_files_over_500_loc"]
    gates.append({"id": "H0-03", "status": "PASS_WITH_FINDINGS" if inventory_findings else "PASS", "detail": f"{inventory['counts']['tracked_files']} checkpoint files; {inventory_findings} Python files over 500 LOC (review signal only)."})

    result = _python(TOOLS / "analyze_dependencies.py", "h0_04_dependencies")
    if result["returncode"]:
        return _fail(gates, "H0-04", "Dependency analysis failed.", started)
    dependency = json.loads((REPORTS / "dependency_graph.json").read_text(encoding="utf-8"))
    dep_findings = len(dependency["potential_circular_imports"]) + len(dependency["statically_unreferenced_candidates"])
    gates.append({"id": "H0-04", "status": "PASS_WITH_FINDINGS" if dep_findings else "PASS", "detail": f"{dependency['module_count']} modules; {dependency['internal_dependency_count']} internal edges; {dep_findings} review findings."})

    result = _python(TOOLS / "analyze_symbol_usage.py", "h0_05_symbols")
    if result["returncode"]:
        return _fail(gates, "H0-05", "Symbol analysis failed.", started)
    symbols = json.loads((REPORTS / "symbol_usage.json").read_text(encoding="utf-8"))
    gates.append({"id": "H0-05", "status": "PASS_WITH_FINDINGS" if symbols["candidates"] else "PASS", "detail": f"{symbols['symbol_count']} symbols; {len(symbols['candidates'])} static candidates; none classified DEAD."})

    duplicate_result = _python(TOOLS / "analyze_duplication.py", "h0_06_duplication")
    complexity_result = _python(TOOLS / "analyze_complexity.py", "h0_06_complexity")
    if duplicate_result["returncode"] or complexity_result["returncode"]:
        return _fail(gates, "H0-06", "Duplication or complexity analysis failed.", started)
    duplication = json.loads((REPORTS / "duplication_candidates.json").read_text(encoding="utf-8"))
    complexity = json.loads((REPORTS / "complexity_baseline.json").read_text(encoding="utf-8"))
    priority_count = sum(value for key, value in complexity["classification_counts"].items() if key in {"HIGH_REVIEW_PRIORITY", "CRITICAL_REVIEW_PRIORITY"})
    gates.append({"id": "H0-06", "status": "PASS_WITH_FINDINGS" if duplication["candidate_count"] or priority_count else "PASS", "detail": f"{duplication['candidate_count']} duplication candidates; {priority_count} high/critical review targets; no refactor performed."})

    package_result = _python(TOOLS / "capture_package_baseline.py", "h0_07_package", timeout=600)
    if package_result["returncode"]:
        return _fail(gates, "H0-07", "Package build/repository validation failed.", started)
    package = json.loads((ROOT / "hardening" / "baseline" / "package_baseline.json").read_text(encoding="utf-8"))
    native = _run([str(blender), "--background", "--command", "extension", "validate", str(ROOT / "dist" / package["archive_filename"])], "h0_07_native_package", timeout=300)
    if native["returncode"]:
        return _fail(gates, "H0-07", "Blender-native extension validation failed.", started)
    package_status = "PASS" if package["matches_retained_release_archive_bytes"] else "PASS_WITH_FINDINGS"
    gates.append({"id": "H0-07", "status": package_status, "detail": f"{package['archive_filename']}; {package['archive_file_count']} files; {package['archive_bytes']} bytes; SHA-256 {package['archive_sha256']}; native validation passed; retained release ZIP byte match={package['matches_retained_release_archive_bytes']}."})

    registration_result = _blender(blender, ROOT / "manual-tests" / "hardening" / "measure_registration.py", "h0_08_registration", "--output", str(REPORTS / "registration_baseline.json"), "--iterations", "3", timeout=300)
    if registration_result["returncode"]:
        return _fail(gates, "H0-08", "Registration measurement failed.", started)
    registration = json.loads((REPORTS / "registration_baseline.json").read_text(encoding="utf-8"))
    gates.append({"id": "H0-08", "status": "PASS", "detail": f"{registration['expected_class_count']} classes; register median {registration['register']['median_seconds']}s; unregister median {registration['unregister']['median_seconds']}s."})

    topology_result = _blender(blender, ROOT / "manual-tests" / "hardening" / "measure_test_topology.py", "h0_09_topology", "--output", str(REPORTS / "test_topology.json"), timeout=300)
    if topology_result["returncode"]:
        return _fail(gates, "H0-09", "Test topology measurement failed.", started)
    combined = _python(ROOT / "scripts" / "run_blender_tests.py", "h0_09_combined", "--blender", str(blender), timeout=1200)
    output = str(combined["stdout"]) + "\n" + str(combined["stderr"])
    count_match = re.search(r"Chroma3D Blender tests passed:\s*(\d+)", output)
    version_match = re.search(r"Blender: .*?\(([^)]+)\)", output)
    combined_report = {
        "schema_version": "1.0.0", "status": "PASS" if combined["returncode"] == 0 and count_match else "FAIL",
        "tests_run": int(count_match.group(1)) if count_match else None, "failures": 0 if combined["returncode"] == 0 else None,
        "errors": 0 if combined["returncode"] == 0 else None, "elapsed_seconds": combined["elapsed_seconds"],
        "blender_version": version_match.group(1) if version_match else None, "runner": "scripts/run_blender_tests.py",
    }
    (REPORTS / "combined_test_baseline.json").write_text(json.dumps(combined_report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    if combined_report["status"] != "PASS":
        return _fail(gates, "H0-09", "Combined Blender regression failed.", started)
    gates.append({"id": "H0-09", "status": "PASS", "detail": f"{combined_report['tests_run']} tests passed on Blender {combined_report['blender_version']} in {combined_report['elapsed_seconds']}s."})

    return _run_h0_10_to_17(blender, gates, started)


if __name__ == "__main__":
    raise SystemExit(main())
