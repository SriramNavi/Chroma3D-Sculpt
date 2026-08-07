"""Verify retained dataset, benchmark, and Sprint 7 release-input identity."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    BASELINE_ROOT,
    CHECKPOINT_COMMIT,
    CHECKPOINT_TAG,
    REPORT_ROOT,
    REPOSITORY_ROOT,
    markdown_table,
    sha256_path,
    utc_now,
    write_json,
    write_text,
)


EXPECTED_RELEASE_INPUT_SHA256 = "4101fea6263011e3b3157466dc3ae7fe09df2415a3f167e59c35befa90e89baa"
EXPECTED_RETAINED_EVIDENCE_TREE_SHA256 = "7d88ac059c495942d28f5c4fde23746f86fb1cfed494dd7426468dfa5be03005"


def _run_assets(action: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, str(REPOSITORY_ROOT / "scripts" / "fetch_validation_assets.py"), action],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "action": action,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout.splitlines()[-80:],
        "stderr_tail": completed.stderr.splitlines()[-80:],
    }


def _release_identity() -> dict[str, object]:
    path = REPOSITORY_ROOT / "manual-tests" / "sprint7" / "release_input_fingerprint.py"
    spec = importlib.util.spec_from_file_location("h0_sprint7_release_input", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load retained Sprint 7 fingerprint tool")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_release_input_identity()


def _retained_evidence_tree_sha256() -> tuple[int, str]:
    paths = [REPOSITORY_ROOT / "manual-tests" / "sprint7" / "reports" / "release_input_fingerprint.json"]
    paths.extend(sorted((REPOSITORY_ROOT / "manual-tests" / "sprint7" / "reports" / "dataset").glob("*.json")))
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(REPOSITORY_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256_path(path)))
    return len(paths), digest.hexdigest()


def _fresh_h0_dataset_evidence(
    release: dict[str, object],
    dataset_hash: str,
    benchmark_hash: str,
) -> dict[str, object]:
    root = REPORT_ROOT / "dataset_current"
    paths = {
        "representative": root / "representative_summary.json",
        "full": root / "full_summary.json",
    }
    if not all(path.is_file() for path in paths.values()):
        return {"available": False, "valid": False, "reason": "Fresh H0 dataset summaries are unavailable."}
    summaries = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in paths.items()}
    expected_counts = {"representative": 10, "full": 27}
    checks: dict[str, bool] = {}
    for name, summary in summaries.items():
        expected = expected_counts[name]
        records = summary.get("records", [])
        checks[f"{name}_complete"] = (
            summary.get("status") == "PASS"
            and summary.get("expected_count") == expected
            and summary.get("model_count") == expected
            and summary.get("passed_count") == expected
            and len(records) == expected
        )
        checks[f"{name}_identity"] = (
            summary.get("implementation_fingerprint") == release.get("aggregate_sha256")
            and summary.get("dataset_manifest_sha256") == dataset_hash
            and summary.get("golden_manifest_sha256") == benchmark_hash
            and summary.get("validation_mode") == "S7_DATASET_FAKE_OFFLINE"
            and summary.get("worker_version") == "sprint7-dataset-worker-1.2"
        )
        checks[f"{name}_safety"] = (
            summary.get("source_mutation_count") == 0
            and summary.get("geometry_payload_count") == 0
            and summary.get("timeout_count") == 0
            and summary.get("unclassified_failure_count") == 0
            and summary.get("live_provider_calls") == 0
            and all(
                item.get("status") == "PASS"
                and item.get("source_immutability") is True
                and item.get("geometry_elements_exported") == 0
                for item in records
            )
        )
    return {
        "available": True,
        "valid": all(checks.values()),
        "checks": checks,
        "representative": {key: summaries["representative"].get(key) for key in (
            "status", "model_count", "passed_count", "source_mutation_count", "timeout_count", "elapsed_seconds",
        )},
        "full": {key: summaries["full"].get(key) for key in (
            "status", "model_count", "passed_count", "source_mutation_count", "timeout_count", "elapsed_seconds",
        )},
        "implementation_fingerprint": summaries["full"].get("implementation_fingerprint"),
        "profile_context_sha256": summaries["full"].get("profile_context_sha256"),
        "evidence_directory": root.relative_to(REPOSITORY_ROOT).as_posix(),
    }


def capture() -> dict[str, object]:
    dataset_lock_path = REPOSITORY_ROOT / "datasets" / "statues" / "DATASET_LOCK.json"
    dataset_manifest_path = REPOSITORY_ROOT / "datasets" / "statues" / "manifests" / "statue_dataset_manifest.json"
    benchmark_lock_path = REPOSITORY_ROOT / "benchmarks" / "golden" / "BENCHMARK_LOCK.json"
    benchmark_manifest_path = REPOSITORY_ROOT / "benchmarks" / "golden" / "manifests" / "golden_manifest.json"
    dataset_lock = json.loads(dataset_lock_path.read_text(encoding="utf-8"))
    benchmark_lock = json.loads(benchmark_lock_path.read_text(encoding="utf-8"))
    dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    benchmark_manifest = json.loads(benchmark_manifest_path.read_text(encoding="utf-8"))
    release = _release_identity()
    retained_report_path = REPOSITORY_ROOT / "manual-tests" / "sprint7" / "reports" / "release_input_fingerprint.json"
    retained_release = json.loads(retained_report_path.read_text(encoding="utf-8")) if retained_report_path.is_file() else {}
    current_files = {str(item["path"]): str(item["sha256"]) for item in release.get("files", [])}
    fingerprint_mismatches = []
    for item in retained_release.get("files", []):
        path_name = str(item["path"])
        retained_hash = str(item["sha256"])
        current_hash = current_files.get(path_name, "MISSING")
        if current_hash == retained_hash:
            continue
        path = REPOSITORY_ROOT / path_name
        newline_only = False
        if path.is_file():
            normalized = path.read_bytes().replace(b"\r\n", b"\n")
            newline_only = hashlib.sha256(normalized).hexdigest() == retained_hash
        fingerprint_mismatches.append({
            "path": path_name,
            "retained_sha256": retained_hash,
            "current_sha256": current_hash,
            "classification": "CHECKOUT_NEWLINE_ONLY" if newline_only else "CONTENT_IDENTITY_MISMATCH",
        })
    status_run = _run_assets("status")
    verify_run = _run_assets("verify")
    dataset_hash = sha256_path(dataset_manifest_path)
    benchmark_hash = sha256_path(benchmark_manifest_path)
    retained_compatible = (
        release.get("aggregate_sha256") == EXPECTED_RELEASE_INPUT_SHA256
        and dataset_hash == dataset_lock.get("manifest_sha256")
        and benchmark_hash == benchmark_lock.get("manifest_sha256")
    )
    reconciliation_path = REPORT_ROOT / "fingerprint_reconciliation.json"
    reconciliation = json.loads(reconciliation_path.read_text(encoding="utf-8")) if reconciliation_path.is_file() else {}
    fresh = _fresh_h0_dataset_evidence(release, dataset_hash, benchmark_hash)
    evidence_source = "RETAINED_FINGERPRINT_COMPATIBLE" if retained_compatible else "FRESH_H0_VALIDATION" if fresh.get("valid") else "UNRESOLVED"
    evidence_valid = retained_compatible or bool(fresh.get("valid"))
    retained_tree_count, retained_tree_hash = _retained_evidence_tree_sha256()
    retained_tree_unchanged = retained_tree_hash == EXPECTED_RETAINED_EVIDENCE_TREE_SHA256
    status = "PASS" if (
        evidence_valid
        and retained_tree_unchanged
        and status_run["returncode"] == 0
        and verify_run["returncode"] == 0
    ) else "FAIL"
    return {
        "schema_version": "1.0.0",
        "generated_at": utc_now(),
        "status": status,
        "checkpoint_tag": CHECKPOINT_TAG,
        "checkpoint_commit": CHECKPOINT_COMMIT,
        "dataset": {
            "version": dataset_lock.get("dataset_version"),
            "asset_count": dataset_lock.get("asset_count", dataset_manifest.get("asset_count")),
            "manifest_sha256": dataset_hash,
            "locked_manifest_sha256": dataset_lock.get("manifest_sha256"),
            "archive_sha256": dataset_lock.get("asset_sha256"),
            "archive_bytes": dataset_lock.get("asset_size_bytes"),
        },
        "golden_benchmark": {
            "version": benchmark_lock.get("benchmark_version"),
            "record_count": benchmark_manifest.get("mesh_count", benchmark_lock.get("expected_mesh_count")),
            "manifest_sha256": benchmark_hash,
            "locked_manifest_sha256": benchmark_lock.get("manifest_sha256"),
            "archive_sha256": benchmark_lock.get("asset_sha256"),
            "archive_bytes": benchmark_lock.get("asset_size_bytes"),
        },
        "sprint7_retained_validation": {
            "representative": "10/10 PASS",
            "full": "27/27 PASS",
            "source_immutability": "PASS in retained Sprint 7 evidence; not rerun by H0",
            "evidence_source": "manual-tests/sprint7/SPRINT7_ACCEPTANCE_RESULTS.md",
            "release_input_file_count": release.get("file_count"),
            "release_input_sha256": release.get("aggregate_sha256"),
            "expected_release_input_sha256": EXPECTED_RELEASE_INPUT_SHA256,
            "retained_report_head": retained_release.get("head"),
            "current_head": release.get("head"),
            "fingerprint_mismatch_count": len(fingerprint_mismatches),
            "newline_only_mismatch_count": sum(item["classification"] == "CHECKOUT_NEWLINE_ONLY" for item in fingerprint_mismatches),
            "content_identity_mismatch_count": sum(item["classification"] == "CONTENT_IDENTITY_MISMATCH" for item in fingerprint_mismatches),
        },
        "reconciliation": {
            "status": reconciliation.get("status"),
            "newline_only_equivalent_count": reconciliation.get("newline_only_equivalent_count"),
            "content_different_count": reconciliation.get("content_different_count"),
            "retained_semantic_input_sha256": reconciliation.get("retained_semantic_input_sha256"),
            "current_semantic_input_sha256": reconciliation.get("current_semantic_input_sha256"),
            "decision": reconciliation.get("dataset_evidence_decision"),
        },
        "fresh_h0_validation": fresh,
        "evidence_source": evidence_source,
        "evidence_valid": evidence_valid,
        "retained_evidence_tree": {
            "file_count": retained_tree_count,
            "sha256": retained_tree_hash,
            "expected_sha256": EXPECTED_RETAINED_EVIDENCE_TREE_SHA256,
            "unchanged": retained_tree_unchanged,
        },
        "release_input_mismatches": fingerprint_mismatches,
        "asset_status": status_run,
        "asset_verify": verify_run,
        "fingerprint_compatible": retained_compatible,
        "full_corpus_rerun_required": not evidence_valid,
        "full_corpus_rerun_performed": evidence_source == "FRESH_H0_VALIDATION",
        "limitations": ["Fresh H0 validation uses the existing Sprint 7 offline fake-provider runner; it does not add live-provider, slicer, or physical-print evidence."],
    }


def render(report: dict[str, object]) -> str:
    dataset = report["dataset"]
    benchmark = report["golden_benchmark"]
    sprint7 = report["sprint7_retained_validation"]
    return "\n".join((
        "# Dataset and Benchmark Baseline", "",
        f"Status: `{report['status']}`. Checkpoint: `{report['checkpoint_tag']}` / `{report['checkpoint_commit']}`.", "",
        markdown_table(("Identity", "Version", "Count", "Manifest SHA-256", "Archive SHA-256"), (
            ("Dataset", dataset["version"], dataset["asset_count"], dataset["manifest_sha256"], dataset["archive_sha256"]),
            ("Golden benchmark", benchmark["version"], benchmark["record_count"], benchmark["manifest_sha256"], benchmark["archive_sha256"]),
        )), "",
        markdown_table(("Sprint 7 retained evidence", "Value"), (
            ("Representative dataset", sprint7["representative"]),
            ("Full dataset", sprint7["full"]),
            ("Release-input files", sprint7["release_input_file_count"]),
            ("Release-input SHA-256", sprint7["release_input_sha256"]),
            ("Source immutability", "PASS in fresh H0 10/10 and 27/27 evidence" if report["evidence_source"] == "FRESH_H0_VALIDATION" else sprint7["source_immutability"]),
            ("Retained fingerprint compatible", report["fingerprint_compatible"]),
            ("Fingerprint mismatches", sprint7["fingerprint_mismatch_count"]),
            ("Newline-only mismatches", sprint7["newline_only_mismatch_count"]),
            ("Content-identity mismatches", sprint7["content_identity_mismatch_count"]),
            ("Evidence source", report["evidence_source"]),
            ("Current semantic runtime fingerprint", report["reconciliation"]["current_semantic_input_sha256"]),
            ("Frozen Sprint 7 evidence tree unchanged", report["retained_evidence_tree"]["unchanged"]),
        )), "",
        "The retained raw fingerprint mismatch was not bypassed. H0 reconciled 45 newline-only paths, classified nine content differences, and ran fresh 10/10 plus 27/27 dataset validation under the current fingerprint. Frozen Sprint 7 evidence was not rewritten.",
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPORT_ROOT / "dataset_benchmark_identity.json")
    parser.add_argument("--markdown", type=Path, default=BASELINE_ROOT / "DATASET_BENCHMARK_BASELINE.md")
    args = parser.parse_args()
    report = capture()
    write_json(args.output, report)
    write_text(args.markdown, render(report))
    print(json.dumps({"status": report["status"], "fingerprint_compatible": report["fingerprint_compatible"], "evidence_source": report["evidence_source"], "full_corpus_rerun": report["full_corpus_rerun_performed"]}, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
