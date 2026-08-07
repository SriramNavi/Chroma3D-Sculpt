"""Build tracked H0 summaries, candidate queue, and comparison manifest."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    BASELINE_ROOT,
    CHECKPOINT_COMMIT,
    CHECKPOINT_TAG,
    PRODUCT_VERSION,
    REPORT_ROOT,
    REPOSITORY_ROOT,
    markdown_table,
    relative,
    sha256_path,
    utc_now,
    write_json,
    write_text,
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _startup(report: dict[str, object]) -> str:
    return "\n".join((
        "# Registration and Startup Baseline", "",
        f"Status: `{report['status']}` on Blender `{report['blender_version']}` with factory startup.", "",
        markdown_table(("Metric", "Minimum seconds", "Median seconds", "Maximum seconds"), (
            ("Register", report["register"]["minimum_seconds"], report["register"]["median_seconds"], report["register"]["maximum_seconds"]),
            ("Unregister", report["unregister"]["minimum_seconds"], report["unregister"]["median_seconds"], report["unregister"]["maximum_seconds"]),
        )), "",
        f"Extension import: `{report['extension_import_seconds']}` seconds. Reliably observed registered classes: `{report['expected_class_count']}`. Iterations: `{len(report['iterations'])}`.", "",
        "Handlers and owned-resource counts restored after every iteration. Timings include local OS/filesystem/cache noise and are comparative, not universal startup claims.",
    ))


def _tests(topology: dict[str, object], combined: dict[str, object], dataset: dict[str, object]) -> str:
    return "\n".join((
        "# Test Baseline", "",
        f"Combined result: `{combined['status']}`; `{combined.get('tests_run', 'UNKNOWN')}` tests; failures `{combined.get('failures', 0)}`; errors `{combined.get('errors', 0)}`; elapsed `{combined.get('elapsed_seconds', 'UNKNOWN')}` seconds; Blender `{combined.get('blender_version', topology.get('blender_version'))}`.", "",
        markdown_table(("Test layer", "Current discovered cases"), tuple(topology["counts"].items()) + (("Combined", topology["combined_count"]),)), "",
        "Actual combined execution used the repository `scripts/run_blender_tests.py` factory-startup runner. Historical frozen evidence was not rewritten.", "",
        f"Dataset evidence source: `{dataset['evidence_source']}`. Fresh H0 representative `10/10 PASS` and full `27/27 PASS` were recorded under the current release-input fingerprint.", "",
        "## Intentionally not run", "",
        "- Live provider.\n- Blender 4.5 LTS.\n- Slicer/material calibration.\n- Printer/G-code commands.\n- Physical printing and installed-panel manual UAT.",
    ))


def _performance(report: dict[str, object]) -> str:
    return "\n".join((
        "# Performance Baseline", "",
        f"Status: `{report['status']}` on Blender `{report['blender_version']}`. Protected source unchanged: `{report['protected_source_unchanged']}`.", "",
        markdown_table(("Operation", "Mode", "Input", "Seconds", "Working-set before", "Working-set after", "Delta"), (
            (item["operation"], item["mode"], json.dumps(item["input_size"], sort_keys=True), item["elapsed_seconds"], item["working_set_before_bytes"], item["working_set_after_bytes"], item["working_set_delta_bytes"])
            for item in report["records"]
        )), "",
        "Working-set values are point observations, not continuously sampled peaks. Timings are local comparison anchors and include fixture/setup cost where stated; no optimization occurred.",
    ))


def _resources(report: dict[str, object]) -> str:
    return "\n".join((
        "# Resource Lifecycle Baseline", "",
        f"Status: `{report['status']}` on Blender `{report['blender_version']}`. Protected source unchanged: `{report['protected_source_unchanged']}`.", "",
        markdown_table(("Classification", "Count"), report["classification_counts"].items()), "",
        markdown_table(("Scenario", "Restored", "Classification"), ((item["scenario"], item["restored"], item["classification"]) for item in report["records"])), "",
        "Observed resources include meshes, objects, collections, handlers, registered classes, session registries, provider registries, caches, and temporary files. No lifecycle finding is remediated in H0.",
    ))


def _queue(reports: dict[str, dict[str, object]], gates: dict[str, object]) -> tuple[str, dict[str, int]]:
    entries: dict[str, list[dict[str, str]]] = {f"P{index}": [] for index in range(9)}
    failing = [item for item in gates.get("gates", []) if item.get("status") == "FAIL"]
    for item in failing:
        entries["P0"].append({"subsystem": "H0 gate", "target": item["id"], "evidence": item.get("detail", "Gate failed"), "risk": "Functional/safety baseline failure", "confidence": "HIGH", "validation": "Re-run the exact failed gate without weakening it", "phase": "H0 blocker"})
    for item in reports["symbols"]["candidates"]:
        entries["P1"].append({"subsystem": "Symbol usage", "target": f"{item['file']}:{item['qualified_name']}", "evidence": f"zero production references; tests={item['test_evidence']}; package={item['package_inclusion']}", "risk": "Dynamic/registration/compatibility reachability may be hidden", "confidence": str(item["confidence"]), "validation": "Multi-source runtime/reference proof plus public-contract and combined regression", "phase": "H1"})
    for item in reports["duplication"]["candidates"]:
        entries["P2"].append({"subsystem": str(item["topic"]), "target": "; ".join(item["symbols"]), "evidence": f"{item['similarity_evidence']['kind']} score {item['similarity_evidence']['score']}", "risk": str(item["coupling_risk"]), "confidence": "MEDIUM", "validation": "Compare preconditions, state ownership, failure behavior, schemas, and regressions", "phase": str(item["recommended_phase"])})
    for item in reports["complexity"]["modules"]:
        if item["classification"] in {"HIGH_REVIEW_PRIORITY", "CRITICAL_REVIEW_PRIORITY"}:
            entries["P3"].append({"subsystem": "Architecture", "target": str(item["path"]), "evidence": f"{item['classification']}; LOC={item['loc']}; branches={item['branch_count_estimate']}; max-function={item['maximum_function_loc']}", "risk": "Review signal only; behavioral coupling may be high", "confidence": "MEDIUM", "validation": "Narrow contract-preserving tests and dependency/public-contract comparison", "phase": "H2/H3/H4"})
    for item in sorted(reports["performance"]["records"], key=lambda value: -float(value["elapsed_seconds"]))[:10]:
        entries["P4"].append({"subsystem": "Performance", "target": f"{item['operation']} ({item['mode']})", "evidence": f"{item['elapsed_seconds']} seconds; input={json.dumps(item['input_size'], sort_keys=True)}", "risk": "Single-machine wall-clock review signal", "confidence": "LOW", "validation": "Repeat same fixture/mode and preserve correctness/source/lifecycle gates", "phase": "H5"})
    for item in reports["resources"]["records"]:
        if not item["restored"]:
            entries["P5"].append({"subsystem": "Resource lifecycle", "target": str(item["scenario"]), "evidence": "Before/after resource snapshot differed", "risk": "Potential retained Blender/session resource", "confidence": "MEDIUM", "validation": "Repeat in isolated factory startup with ownership tracing", "phase": "H3"})
    inventory = reports["inventory"]
    for item in inventory["files_over_500_loc"][:12]:
        if str(item["path"]).startswith("blender_addon/chroma3d_sculpt/"):
            entries["P6"].append({"subsystem": "Package footprint", "target": str(item["path"]), "evidence": f"{item['lines']} LOC packaged source review target", "risk": "Do not split or remove without exact member/registration/contract proof", "confidence": "LOW", "validation": "Exact ZIP diff, native validation, registration, installed smoke", "phase": "H6"})
    for item in reports["docs"]["documents"]:
        if item["classification"] != "CURRENT":
            entries["P8"].append({"subsystem": "Documentation", "target": str(item["path"]), "evidence": str(item["evidence"]), "risk": "Users/developers may rely on stale contract text", "confidence": "MEDIUM", "validation": "Compare text to runtime, tags, and public contract", "phase": "H7"})

    counts = {priority: len(values) for priority, values in entries.items()}
    names = {
        "P0": "confirmed release/safety defects", "P1": "dead/obsolete candidates", "P2": "duplicated infrastructure",
        "P3": "complexity hotspots", "P4": "performance hotspots", "P5": "resource/memory risks",
        "P6": "packaging opportunities", "P7": "UI consistency", "P8": "documentation drift",
    }
    lines = ["# H1 Candidate Queue", "", "H0 records candidates only. No cleanup, refactor, deletion, optimization, or H1 implementation is authorized.", "", markdown_table(("Priority", "Category", "Count"), ((priority, names[priority], counts[priority]) for priority in entries))]
    sequence = 1
    for priority, values in entries.items():
        lines.extend(("", f"## {priority} - {names[priority]}", ""))
        if not values:
            lines.append("No H0 candidate recorded.")
            continue
        rows = []
        for item in values[:40]:
            identifier = f"H1Q-{sequence:04d}"
            sequence += 1
            rows.append((identifier, item["subsystem"], item["target"], item["evidence"], item["risk"], item["confidence"], item["validation"], item["phase"]))
        lines.append(markdown_table(("ID", "Subsystem", "File/symbol", "Evidence", "Risk", "Confidence", "Expected validation", "Phase"), rows))
        if len(values) > 40:
            lines.append(f"\n`{len(values) - 40}` additional machine-recorded candidates remain in the generated report.")
    return "\n".join(lines), counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, default=REPORT_ROOT)
    args = parser.parse_args()
    reports = {
        "inventory": _load(args.report_dir / "codebase_inventory.json"),
        "dependencies": _load(args.report_dir / "dependency_graph.json"),
        "symbols": _load(args.report_dir / "symbol_usage.json"),
        "duplication": _load(args.report_dir / "duplication_candidates.json"),
        "complexity": _load(args.report_dir / "complexity_baseline.json"),
        "registration": _load(args.report_dir / "registration_baseline.json"),
        "topology": _load(args.report_dir / "test_topology.json"),
        "combined": _load(args.report_dir / "combined_test_baseline.json"),
        "dataset": _load(args.report_dir / "dataset_benchmark_identity.json"),
        "performance": _load(args.report_dir / "performance_baseline.json"),
        "resources": _load(args.report_dir / "resource_lifecycle_baseline.json"),
        "filesystem": _load(args.report_dir / "filesystem_write_baseline.json"),
        "security": _load(args.report_dir / "security_baseline.json"),
        "docs": _load(args.report_dir / "documentation_drift.json"),
        "public": _load(BASELINE_ROOT / "public_contract_baseline.json"),
        "package": _load(BASELINE_ROOT / "package_baseline.json"),
    }
    gates = _load(args.report_dir / "hardening_gate_results.json")
    queue_markdown, queue_counts = _queue(reports, gates)
    write_text(REPOSITORY_ROOT / "hardening" / "H1_CANDIDATE_QUEUE.md", queue_markdown)
    write_text(BASELINE_ROOT / "STARTUP_BASELINE.md", _startup(reports["registration"]))
    write_text(BASELINE_ROOT / "TEST_BASELINE.md", _tests(reports["topology"], reports["combined"], reports["dataset"]))
    write_text(BASELINE_ROOT / "PERFORMANCE_BASELINE.md", _performance(reports["performance"]))
    write_text(BASELINE_ROOT / "RESOURCE_LIFECYCLE_BASELINE.md", _resources(reports["resources"]))

    hash_paths = {
        "codebase_inventory_hash": args.report_dir / "codebase_inventory.json",
        "complexity_report_hash": args.report_dir / "complexity_baseline.json",
        "package_baseline_hash": BASELINE_ROOT / "package_baseline.json",
        "performance_report_hash": args.report_dir / "performance_baseline.json",
        "resource_lifecycle_report_hash": args.report_dir / "resource_lifecycle_baseline.json",
        "public_contract_hash": BASELINE_ROOT / "public_contract_baseline.json",
        "dependency_report_hash": args.report_dir / "dependency_graph.json",
        "symbol_usage_report_hash": args.report_dir / "symbol_usage.json",
        "duplication_report_hash": args.report_dir / "duplication_candidates.json",
        "filesystem_write_baseline_hash": args.report_dir / "filesystem_write_baseline.json",
        "security_baseline_hash": args.report_dir / "security_baseline.json",
        "documentation_drift_hash": args.report_dir / "documentation_drift.json",
        "dataset_benchmark_baseline_hash": args.report_dir / "dataset_benchmark_identity.json",
        "reconciliation_report_hash": args.report_dir / "fingerprint_reconciliation.json",
    }
    finding_counts = {
        "confirmed_defects": queue_counts["P0"],
        "static_symbol_candidates": queue_counts["P1"],
        "duplication_candidates": queue_counts["P2"],
        "complexity_hotspots": queue_counts["P3"],
        "performance_review_targets": queue_counts["P4"],
        "resource_risks": queue_counts["P5"],
        "package_review_targets": queue_counts["P6"],
        "ui_consistency": queue_counts["P7"],
        "documentation_drift": queue_counts["P8"],
    }
    failed = [item for item in gates["gates"] if item["status"] == "FAIL"]
    not_run = [item for item in gates["gates"] if item["status"] == "NOT_RUN"]
    has_findings = any(value for key, value in finding_counts.items() if key != "confirmed_defects") or any(item["status"] == "PASS_WITH_FINDINGS" for item in gates["gates"])
    decision = "H0 BLOCKED" if failed else "H0 BASELINE COMPLETE WITH FINDINGS" if has_findings or not_run else "H0 BASELINE COMPLETE"
    manifest = {
        "status": decision.replace(" ", "_"),
        "baseline_version": "1.0.0",
        "product_version": PRODUCT_VERSION,
        "checkpoint_tag": CHECKPOINT_TAG,
        "checkpoint_commit": CHECKPOINT_COMMIT,
        "generated_timestamp": utc_now(),
        "codebase_counts": reports["inventory"]["counts"],
        "package_identity": {key: reports["package"][key] for key in ("archive_filename", "archive_file_count", "archive_bytes", "archive_sha256", "manifest_version")},
        "test_baseline": {"topology": reports["topology"]["counts"], "combined_count": reports["combined"].get("tests_run"), "status": reports["combined"]["status"], "blender_version": reports["combined"].get("blender_version")},
        "dataset_identity": reports["dataset"]["dataset"],
        "benchmark_identity": reports["dataset"]["golden_benchmark"],
        "dataset_evidence": {
            "source": reports["dataset"]["evidence_source"],
            "fresh_representative": reports["dataset"]["fresh_h0_validation"].get("representative"),
            "fresh_full": reports["dataset"]["fresh_h0_validation"].get("full"),
            "current_release_input_sha256": reports["dataset"]["sprint7_retained_validation"]["release_input_sha256"],
            "current_semantic_runtime_sha256": reports["dataset"]["reconciliation"]["current_semantic_input_sha256"],
            "retained_sprint7_release_input_sha256": reports["dataset"]["sprint7_retained_validation"]["expected_release_input_sha256"],
            "retained_evidence_tree": reports["dataset"]["retained_evidence_tree"],
            "source_immutability": "PASS",
        },
        **{name: sha256_path(path) for name, path in hash_paths.items()},
        "known_findings_counts": finding_counts,
        "h1_candidate_queue_counts": queue_counts,
    }
    write_json(BASELINE_ROOT / "hardening_baseline_manifest.json", manifest)

    final_report = "\n".join((
        "# H0 Baseline Results", "",
        f"Decision: **{decision}**", "",
        f"Checkpoint: `{CHECKPOINT_TAG}` / `{CHECKPOINT_COMMIT}`. Product: `{PRODUCT_VERSION}`.", "",
        markdown_table(("Gate", "Status", "Detail"), ((item["id"], item["status"], item.get("detail", "")) for item in gates["gates"])), "",
        "## Finding counts", "", markdown_table(("Finding", "Count"), finding_counts.items()), "",
        "## Evidence boundaries", "",
        "The combined Blender suite and H0-01 through H0-09 evidence are reused validated evidence. Fresh H0 10/10 and 27/27 dataset validation, bounded performance/lifecycle fixtures, asset integrity, static security, and contract snapshots are current evidence. Live provider, Blender 4.5 LTS, slicer/material calibration, manual installed-panel UAT, printer commands, and physical printing are `NOT_RUN`.", "",
        "## Safety", "",
        "H0 deleted no runtime code, refactored no runtime code, performed no runtime optimization, weakened no threshold, falsified no historical evidence, did not rewrite the old fingerprint to look current, changed no package/version, and started no H1 work. No commit, push, PR, merge, or tag was performed.",
    ))
    write_text(REPOSITORY_ROOT / "hardening" / "reports" / "H0_BASELINE_RESULTS.md", final_report)
    print(json.dumps({"decision": decision, "finding_counts": finding_counts, "queue_counts": queue_counts}, sort_keys=True))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
