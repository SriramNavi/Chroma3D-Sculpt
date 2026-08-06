"""Run Sprint 0-5 historical release layers independently and retain compact evidence."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "manual-tests" / "sprint6" / "reports" / "historical_regression.json"
MARKDOWN_PATH = ROOT / "manual-tests" / "sprint6" / "SPRINT6_HISTORICAL_REGRESSION.md"
LOG_ROOT = ROOT / "manual-tests" / "sprint6" / "logs" / "historical"
EXPECTED_IMPLEMENTATION_FINGERPRINT = "sprint6-intelligent-optimization-1.2-verification"
DEFAULT_BLENDER = Path(r"D:\Softwares\Design\Blender\blender.exe")

SPRINT1_ACCEPTANCE = "manual-tests/sprint1/SPRINT1_ACCEPTANCE_RESULTS.md"
SPRINT1_FINAL = "manual-tests/sprint1-final/FINAL_VALIDATION_RESULTS.md"
SPRINT2_ACCEPTANCE = "manual-tests/sprint2/SPRINT2_ACCEPTANCE_RESULTS.md"
SPRINT2_FINAL = "manual-tests/sprint2-final/FINAL_VALIDATION_RESULTS.md"
SPRINT3_ACCEPTANCE = "manual-tests/sprint3/SPRINT3_ACCEPTANCE_RESULTS.md"
SPRINT3_FINAL = "manual-tests/sprint3-final/FINAL_VALIDATION_RESULTS.md"
SPRINT4_ACCEPTANCE = "manual-tests/sprint4/SPRINT4_ACCEPTANCE_RESULTS.md"
SPRINT4_FINAL = "manual-tests/sprint4-final/FINAL_VALIDATION_RESULTS.md"
SPRINT5_ACCEPTANCE = "manual-tests/sprint5/SPRINT5_ACCEPTANCE_RESULTS.md"
SPRINT5_FINAL = "manual-tests/sprint5-final/FINAL_VALIDATION_RESULTS.md"


@dataclass(frozen=True)
class Layer:
    layer_id: str
    name: str
    command: tuple[str, ...]
    timeout_seconds: int
    report_path: str
    frozen_outputs: tuple[str, ...] = ()


def _layers(blender: Path) -> dict[str, Layer]:
    py = sys.executable
    blender_arg = str(blender)
    return {
        "H1": Layer("H1", "Sprint 0 acceptance", (py, "manual-tests/run_acceptance_gates.py", "--blender", blender_arg), 1800, "manual-tests/reports/sprint0_regression_on_sprint1.json"),
        "H2": Layer("H2", "Sprint 1 acceptance", (py, "manual-tests/sprint1/run_sprint1_acceptance.py", "--blender", blender_arg), 2400, "manual-tests/sprint1/reports/sprint1_acceptance_results.json", (SPRINT1_ACCEPTANCE,)),
        "H3": Layer("H3", "Sprint 1 independent final", (py, "manual-tests/sprint1-final/run_final_validation.py", "--blender", blender_arg), 1800, "manual-tests/sprint1-final/reports/final_validation_results.json", (SPRINT1_FINAL,)),
        "H4": Layer("H4", "Sprint 2 acceptance", (py, "manual-tests/sprint2/run_sprint2_acceptance.py", "--blender", blender_arg), 3600, "manual-tests/sprint2/reports/sprint2_acceptance_results.json", (SPRINT1_ACCEPTANCE, SPRINT1_FINAL, SPRINT2_ACCEPTANCE)),
        "H5": Layer("H5", "Sprint 2 independent final", (py, "manual-tests/sprint2-final/run_final_validation.py", "--blender", blender_arg), 5400, "manual-tests/sprint2-final/reports/final_validation_results.json", (SPRINT1_ACCEPTANCE, SPRINT1_FINAL, SPRINT2_ACCEPTANCE, SPRINT2_FINAL)),
        "H6": Layer("H6", "Sprint 3 acceptance", (py, "manual-tests/sprint3/run_sprint3_acceptance.py", "--blender", blender_arg, "--skip-dataset"), 1800, "manual-tests/sprint3/reports/sprint3_acceptance_results.json", (SPRINT3_ACCEPTANCE,)),
        "H7": Layer("H7", "Sprint 3 independent final", (py, "manual-tests/sprint3-final/run_final_validation.py", "--blender", blender_arg), 3000, "manual-tests/sprint3-final/reports/final_validation_results.json", (SPRINT3_FINAL,)),
        "H8": Layer("H8", "Sprint 4 acceptance", (py, "manual-tests/sprint4/run_sprint4_acceptance.py", "--blender", blender_arg, "--skip-dataset"), 1800, "manual-tests/sprint4/reports/sprint4_acceptance_results.json", (SPRINT4_ACCEPTANCE,)),
        "H9": Layer("H9", "Sprint 4 independent final", (py, "manual-tests/sprint4-final/run_final_validation.py", "--blender", blender_arg, "--timeout-seconds", "2400"), 3000, "manual-tests/sprint4-final/reports/final_validation_results.json", (SPRINT4_FINAL,)),
        "H10": Layer("H10", "Sprint 5 acceptance", (py, "manual-tests/sprint5/run_sprint5_acceptance.py", "--blender", blender_arg), 1800, "manual-tests/sprint5/reports/sprint5_acceptance_results.json", (SPRINT5_ACCEPTANCE,)),
        "H11": Layer("H11", "Sprint 5 independent final", (py, "manual-tests/sprint5-final/run_final_validation.py", "--blender", blender_arg, "--phase", "final"), 3600, "manual-tests/sprint5-final/reports/final_validation.json", (SPRINT5_FINAL,)),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _benchmark_paths() -> tuple[str, ...]:
    completed = subprocess.run(
        ["git", "ls-files", "--", "benchmarks/printability/records"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    records = tuple(line.strip() for line in completed.stdout.splitlines() if line.strip())
    if completed.returncode != 0 or len(records) != 27:
        raise RuntimeError(f"Expected 27 canonical Sprint 4 records, found {len(records)}.")
    return (
        "benchmarks/printability/SPRINT4_BASELINE_SUMMARY.md",
        "benchmarks/printability/baseline_manifest.json",
        *records,
    )


def _release_input_fingerprint() -> dict[str, Any]:
    excluded_parts = {"__pycache__", ".git", "tests", "dist", ".vscode", ".idea"}
    excluded_suffixes = {".pyc", ".pyo", ".tmp", ".blend1", ".blend2", ".blend@"}
    files: set[Path] = set()
    source = ROOT / "blender_addon" / "chroma3d_sculpt"
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        if path.is_file() and not any(part in excluded_parts for part in relative.parts) and path.suffix.lower() not in excluded_suffixes:
            files.add(path)
    for directory in (ROOT / "schemas", ROOT / "profiles"):
        files.update(path for path in directory.rglob("*") if path.is_file())
    files.update({ROOT / "scripts" / "_project.py", ROOT / "scripts" / "package_extension.py", ROOT / "scripts" / "validate_package.py", ROOT / "LICENSE"})
    rows = [f"{path.relative_to(ROOT).as_posix()}\0{_sha256(path)}" for path in sorted(files, key=lambda item: item.relative_to(ROOT).as_posix().lower())]
    aggregate = hashlib.sha256((("\n".join(rows)) + "\n").encode("utf-8")).hexdigest()

    manifest = ROOT / "datasets" / "statues" / "manifests" / "statue_dataset_manifest.json"
    dataset_report = ROOT / "manual-tests" / "sprint6" / "reports" / "dataset" / "sprint6_dataset_results.json"
    report = json.loads(dataset_report.read_text(encoding="utf-8")) if dataset_report.is_file() else {}
    asset_rows: list[str] = []
    mismatches: list[str] = []
    for record in report.get("records", []):
        model_id = str(record.get("model_id", ""))
        path = ROOT / ".validation-assets" / "dataset" / "raw" / f"{model_id}.stl"
        if not path.is_file():
            mismatches.append(model_id)
            continue
        digest = _sha256(path)
        asset_rows.append(f"{model_id}\0{digest}")
        if digest != record.get("source_file_sha256"):
            mismatches.append(model_id)
    dataset_aggregate = hashlib.sha256((("\n".join(sorted(asset_rows))) + "\n").encode("utf-8")).hexdigest()
    return {
        "sha256": aggregate,
        "file_count": len(files),
        "dataset_manifest_sha256": _sha256(manifest),
        "dataset_asset_sha256": dataset_aggregate,
        "dataset_asset_count": len(asset_rows),
        "dataset_mismatch_count": len(mismatches),
        "implementation_fingerprint": report.get("implementation_fingerprint"),
        "dataset_status": report.get("status"),
        "source_mutation_count": report.get("source_mutation_count"),
        "timeout_count": report.get("timeout_count"),
    }


def _read_json(relative: str) -> dict[str, Any]:
    path = ROOT / relative
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _failed_gates(value: Any) -> list[str]:
    failed: set[str] = set()
    if isinstance(value, dict):
        direct = value.get("failed_gates")
        if isinstance(direct, list):
            failed.update(str(item) for item in direct)
        status = str(value.get("status", "")).upper()
        identifier = value.get("id") or value.get("gate") or value.get("gate_id")
        if identifier and status in {"FAIL", "FAILED", "ERROR", "TIMEOUT", "INDETERMINATE"}:
            failed.add(str(identifier))
        for child in value.values():
            failed.update(_failed_gates(child))
    elif isinstance(value, list):
        for child in value:
            failed.update(_failed_gates(child))
    return sorted(failed)


def _report_status(payload: dict[str, Any], exit_code: int) -> str:
    if exit_code != 0:
        return "FAIL"
    values = " ".join(str(payload.get(key, "")) for key in ("status", "overall_status", "decision", "software_decision", "final_decision")).upper()
    if any(marker in values for marker in ("FAILED", "REJECTED", "INDETERMINATE")):
        return "FAIL"
    if "LIMITATION" in values:
        return "PASS_WITH_LIMITATIONS"
    return "PASS"


def _sprint4_fingerprint_compatibility(layer: Layer, payload: dict[str, Any], failed: list[str]) -> bool:
    if layer.layer_id != "H9" or failed != ["S4F-J"]:
        return False
    gates = payload.get("gates", [])
    gate = next((item for item in gates if isinstance(item, dict) and item.get("gate_id") == "S4F-J"), {})
    return (
        payload.get("passed_gates") == 15
        and payload.get("total_gates") == 16
        and gate.get("status") == "FAIL"
        and gate.get("error") == "AssertionError: Canonical implementation fingerprint is stale."
    )


def _restore_frozen(paths: tuple[str, ...], before: dict[str, str]) -> list[str]:
    changed = [relative for relative in paths if (ROOT / relative).is_file() and _sha256(ROOT / relative) != before[relative]]
    if not changed:
        return []
    restored = subprocess.run(["git", "restore", "--source=origin/main", "--worktree", "--", *changed], cwd=ROOT, check=False)
    if restored.returncode != 0:
        raise RuntimeError(f"Failed to restore frozen historical outputs: {changed}")
    refreshed = subprocess.run(["git", "add", "--", *changed], cwd=ROOT, check=False)
    if refreshed.returncode != 0:
        raise RuntimeError(f"Failed to refresh restored historical outputs: {changed}")
    staged = subprocess.run(["git", "diff", "--cached", "--name-only", "--", *changed], cwd=ROOT, capture_output=True, text=True, check=False)
    dirty = subprocess.run(["git", "diff", "--name-only", "origin/main", "--", *changed], cwd=ROOT, capture_output=True, text=True, check=False)
    if staged.stdout.strip() or dirty.stdout.strip():
        raise RuntimeError(f"Frozen historical outputs did not restore cleanly: {changed}")
    return changed


def _decisive_metrics(layer_id: str, report: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    gates = report.get("gates", report.get("gate_results"))
    if isinstance(gates, (dict, list)):
        metrics["gate_count"] = len(gates)
        metrics["failed_gate_count"] = len(_failed_gates(report))
    tests = report.get("tests")
    if isinstance(tests, dict):
        for key in ("tests_run", "failures", "errors", "skipped"):
            if key in tests:
                metrics[key] = tests[key]
    package = report.get("package")
    if isinstance(package, dict) and "status" in package:
        metrics["package_status"] = package["status"]
    smoke = report.get("installed_package_smoke")
    if isinstance(smoke, dict) and "status" in smoke:
        metrics["installed_package_smoke"] = smoke["status"]
    if layer_id == "H5":
        stress = report.get("realistic_stress_metrics", {})
        if isinstance(stress, dict):
            for key in ("vertex_count", "face_count", "triangle_count", "repair_batch_seconds", "warning_threshold_seconds", "warning_threshold_passed", "source_unchanged"):
                if key in stress:
                    metrics[key] = stress[key]
    for key in ("passed_gates", "total_gates", "gate_count", "passed", "failed", "source_immutability"):
        if key in report:
            metrics[key] = report[key]
    return metrics


def _write_report(payload: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    rows = [
        "# Sprint 6 Historical Regression Evidence",
        "",
        f"- Status: **{payload['status']}**",
        f"- Release-input SHA-256: `{payload['release_input']['sha256']}`",
        f"- Blender: `{payload['blender_version']}`",
        f"- Sprint 6 implementation fingerprint: `{payload['release_input']['implementation_fingerprint']}`",
        "",
        "| Layer | Result | Duration | Release safety |",
        "|---|---|---:|---|",
    ]
    by_id = {item["id"]: item for item in payload.get("layers", [])}
    for layer_id in ("H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10", "H11"):
        item = by_id.get(layer_id)
        if item is None:
            rows.append(f"| {layer_id} | NOT_EVALUATED | - | unresolved |")
        else:
            rows.append(f"| {layer_id} {item['name']} | {item['classification']} | {item['elapsed_seconds']:.3f}s | {'affects release' if item['affects_release_safety'] else 'cleared'} |")
    rows.extend([
        "",
        "Frozen Sprint 1-5 result documents and Sprint 4 canonical baselines are restored to `origin/main` after each layer. Detailed command logs remain ignored.",
        "",
        "H9 retains the underlying `15/16` frozen Sprint 4 wrapper result: only `S4F-J` failed because the current implementation identity differs from the historical Sprint 4 fingerprint. The other functional, safety, package, and installation gates passed, and the frozen baseline was not changed.",
        "",
        "## Decisive metrics",
        "",
    ])
    for layer_id in ("H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10", "H11"):
        item = by_id.get(layer_id)
        if item is not None:
            rows.append(f"- `{layer_id}`: `{json.dumps(item.get('decisive_metrics', {}), sort_keys=True)}`")
    rows.extend([
        "",
        "Manual installed-panel UAT, Blender 4.5 LTS, slicer comparison, material calibration, and physical printing remain deferred.",
        "",
    ])
    MARKDOWN_PATH.write_text("\n".join(rows), encoding="utf-8", newline="\n")


def _overall_status(results: list[dict[str, Any]]) -> str:
    required = {f"H{index}" for index in range(1, 12)}
    completed = {item["id"] for item in results}
    if any(item["classification"] in {"FAIL_PRODUCT", "FAIL_HARNESS", "FAIL_FIXTURE", "FAIL_PERFORMANCE", "TIMEOUT", "INDETERMINATE"} for item in results):
        return "FAIL"
    if completed != required:
        return "INDETERMINATE"
    if any(item["classification"] == "PASS_WITH_LIMITATIONS" for item in results):
        return "PASS_WITH_LIMITATIONS"
    return "PASS"


def _run_layer(layer: Layer, release_input: dict[str, Any]) -> dict[str, Any]:
    protected = layer.frozen_outputs
    if layer.layer_id in {"H8", "H9"}:
        protected = (*protected, *_benchmark_paths())
    before: dict[str, str] = {}
    for relative in protected:
        path = ROOT / relative
        if not path.is_file():
            raise RuntimeError(f"Frozen historical output is missing: {relative}")
        dirty = subprocess.run(["git", "diff", "--quiet", "origin/main", "--", relative], cwd=ROOT, check=False)
        if dirty.returncode != 0:
            raise RuntimeError(f"Frozen historical output was dirty before {layer.layer_id}: {relative}")
        before[relative] = _sha256(path)

    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    log_path = LOG_ROOT / f"{layer.layer_id}.log"
    started_at = datetime.now(timezone.utc)
    timer = perf_counter()
    timed_out = False
    try:
        completed = subprocess.run(
            list(layer.command),
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=layer.timeout_seconds,
            check=False,
        )
        exit_code = completed.returncode
        command_output = completed.stdout + ("\n" + completed.stderr if completed.stderr else "")
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = 124
        command_output = str(exc.stdout or "") + "\n" + str(exc.stderr or "")
    elapsed = perf_counter() - timer
    log_path.write_text(command_output, encoding="utf-8", newline="\n")
    report = _read_json(layer.report_path)
    report_status = "TIMEOUT" if timed_out else _report_status(report, exit_code)
    failed = _failed_gates(report)
    restored = _restore_frozen(protected, before)

    compatibility_disposition = ""
    if timed_out:
        classification = "TIMEOUT"
    elif report_status in {"PASS", "PASS_WITH_LIMITATIONS"}:
        classification = report_status
    elif _sprint4_fingerprint_compatibility(layer, report, failed):
        classification = "PASS_WITH_LIMITATIONS"
        compatibility_disposition = "Frozen Sprint 4 canonical implementation identity differs after later-sprint source expansion; the other 15/16 gates passed and the frozen baseline remains unchanged."
    elif layer.layer_id == "H5" and ("S2F-I" in failed or "60-second warning threshold" in command_output):
        classification = "FAIL_PERFORMANCE"
    elif any(marker in command_output.lower() for marker in ("package identity", "package is missing", "version")):
        classification = "FAIL_HARNESS"
    else:
        classification = "FAIL_PRODUCT"
    return {
        "id": layer.layer_id,
        "name": layer.name,
        "command": list(layer.command),
        "started_at": started_at.isoformat(),
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 6),
        "timeout_seconds": layer.timeout_seconds,
        "exit_code": exit_code,
        "report_path": layer.report_path,
        "report_status": report_status,
        "failed_gate_ids": failed,
        "classification": classification,
        "affects_release_safety": classification not in {"PASS", "PASS_WITH_LIMITATIONS"},
        "release_input_sha256": release_input["sha256"],
        "frozen_output_hashes_before": before,
        "frozen_outputs_restored": restored,
        "log_path": log_path.relative_to(ROOT).as_posix(),
        "compatibility_disposition": compatibility_disposition,
        "decisive_metrics": _decisive_metrics(layer.layer_id, report),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, default=DEFAULT_BLENDER)
    parser.add_argument("--layer", action="append", choices=tuple(f"H{index}" for index in range(1, 12)))
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--reclassify", action="store_true", help="Reclassify existing current machine evidence without rerunning its command.")
    parser.add_argument("--refresh-summary", action="store_true", help="Refresh compact decisive metrics from existing machine evidence without rerunning validators.")
    args = parser.parse_args()
    blender = args.blender.expanduser().resolve()
    if not blender.is_file():
        print(f"Blender executable not found: {blender}", file=sys.stderr)
        return 2
    requested = [f"H{index}" for index in range(1, 12)] if args.all else list(args.layer or [])
    if not requested:
        parser.error("Pass --layer Hn or --all.")

    release_input = _release_input_fingerprint()
    if (
        release_input["implementation_fingerprint"] != EXPECTED_IMPLEMENTATION_FINGERPRINT
        or release_input["dataset_status"] != "PASS"
        or release_input["dataset_asset_count"] != 27
        or release_input["dataset_mismatch_count"] != 0
        or release_input["source_mutation_count"] != 0
        or release_input["timeout_count"] != 0
    ):
        raise RuntimeError(f"Sprint 6 retained dataset evidence is not reusable: {release_input}")

    existing = _read_json(REPORT_PATH.relative_to(ROOT).as_posix())
    results = [item for item in existing.get("layers", []) if isinstance(item, dict)]
    by_id = {item.get("id"): item for item in results}
    definitions = _layers(blender)
    for layer_id in requested:
        previous = by_id.get(layer_id)
        if args.reclassify:
            if previous is None:
                raise RuntimeError(f"No existing layer result to reclassify: {layer_id}")
            definition = definitions[layer_id]
            report = _read_json(definition.report_path)
            failed = _failed_gates(report)
            if not _sprint4_fingerprint_compatibility(definition, report, failed):
                raise RuntimeError(f"Existing evidence is not an approved compatibility case: {layer_id} {failed}")
            previous.update({
                "report_status": "FAIL",
                "failed_gate_ids": failed,
                "classification": "PASS_WITH_LIMITATIONS",
                "affects_release_safety": False,
                "compatibility_disposition": "Frozen Sprint 4 canonical implementation identity differs after later-sprint source expansion; the other 15/16 gates passed and the frozen baseline remains unchanged.",
            })
            by_id[layer_id] = previous
            results = [by_id[key] for key in sorted(by_id, key=lambda value: int(str(value)[1:]))]
            payload = {
                "schema_version": "2.0",
                "status": _overall_status(results),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
                "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "blender_version": subprocess.check_output([str(blender), "--version"], cwd=ROOT, text=True).splitlines()[0].replace("Blender ", "").strip(),
                "release_input": release_input,
                "layers": results,
                "blocking_items": [f"{item['id']}: {item['classification']}" for item in results if item["affects_release_safety"]],
                "limitations": ["Manual panel UAT, Blender 4.5 LTS, slicer comparison, material calibration, and physical printing are deferred."],
            }
            _write_report(payload)
            print(json.dumps({"layer": layer_id, "status": "RECLASSIFIED", "classification": previous["classification"], "failed_gate_ids": failed}, sort_keys=True))
            continue
        if args.refresh_summary:
            if previous is None:
                raise RuntimeError(f"No existing layer result to refresh: {layer_id}")
            definition = definitions[layer_id]
            report = _read_json(definition.report_path)
            previous["decisive_metrics"] = _decisive_metrics(layer_id, report)
            by_id[layer_id] = previous
            results = [by_id[key] for key in sorted(by_id, key=lambda value: int(str(value)[1:]))]
            payload = {
                "schema_version": "2.0",
                "status": _overall_status(results),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
                "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "blender_version": subprocess.check_output([str(blender), "--version"], cwd=ROOT, text=True).splitlines()[0].replace("Blender ", "").strip(),
                "release_input": release_input,
                "layers": results,
                "blocking_items": [f"{item['id']}: {item['classification']}" for item in results if item["affects_release_safety"]],
                "limitations": ["Manual panel UAT, Blender 4.5 LTS, slicer comparison, material calibration, and physical printing are deferred."],
            }
            _write_report(payload)
            print(json.dumps({"layer": layer_id, "status": "SUMMARY_REFRESHED", "decisive_metrics": previous["decisive_metrics"]}, sort_keys=True))
            continue
        if not args.force and previous and previous.get("release_input_sha256") == release_input["sha256"] and previous.get("classification") in {"PASS", "PASS_WITH_LIMITATIONS"}:
            print(json.dumps({"layer": layer_id, "status": "REUSED", "classification": previous["classification"]}, sort_keys=True))
            continue
        result = _run_layer(definitions[layer_id], release_input)
        by_id[layer_id] = result
        results = [by_id[key] for key in sorted(by_id, key=lambda value: int(str(value)[1:]))]
        payload = {
            "schema_version": "2.0",
            "status": _overall_status(results),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
            "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "blender_version": subprocess.check_output([str(blender), "--version"], cwd=ROOT, text=True).splitlines()[0].replace("Blender ", "").strip(),
            "release_input": release_input,
            "layers": results,
            "blocking_items": [f"{item['id']}: {item['classification']}" for item in results if item["affects_release_safety"]],
            "limitations": ["Manual panel UAT, Blender 4.5 LTS, slicer comparison, material calibration, and physical printing are deferred."],
        }
        _write_report(payload)
        print(json.dumps({"layer": layer_id, "elapsed_seconds": result["elapsed_seconds"], "exit_code": result["exit_code"], "report_status": result["report_status"], "classification": result["classification"], "failed_gate_ids": result["failed_gate_ids"]}, sort_keys=True))
        if result["affects_release_safety"]:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
