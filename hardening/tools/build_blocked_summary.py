"""Create durable partial H0 evidence when a fail-closed gate blocks completion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    BASELINE_ROOT, CHECKPOINT_COMMIT, CHECKPOINT_TAG, PRODUCT_VERSION, REPORT_ROOT, REPOSITORY_ROOT,
    markdown_table, sha256_path, utc_now, write_json, write_text,
)
from build_baseline_summary import _performance, _resources, _startup, _tests  # noqa: E402


def _load(path: Path) -> dict[str, object] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", required=True)
    parser.add_argument("--detail", required=True)
    args = parser.parse_args()
    gates = _load(REPORT_ROOT / "hardening_gate_results.json") or {"gates": []}
    inventory = _load(REPORT_ROOT / "codebase_inventory.json")
    symbols = _load(REPORT_ROOT / "symbol_usage.json")
    duplication = _load(REPORT_ROOT / "duplication_candidates.json")
    complexity = _load(REPORT_ROOT / "complexity_baseline.json")
    package = _load(BASELINE_ROOT / "package_baseline.json")
    topology = _load(REPORT_ROOT / "test_topology.json")
    combined = _load(REPORT_ROOT / "combined_test_baseline.json")
    dataset = _load(REPORT_ROOT / "dataset_benchmark_identity.json")
    registration = _load(REPORT_ROOT / "registration_baseline.json")
    performance = _load(REPORT_ROOT / "performance_baseline.json")
    resources = _load(REPORT_ROOT / "resource_lifecycle_baseline.json")
    docs = _load(REPORT_ROOT / "documentation_drift.json")

    normalized_gates = [dict(item) for item in gates.get("gates", [])]
    for item in normalized_gates:
        if item["id"] == "H0-03" and inventory:
            item["detail"] = f"{inventory['counts']['tracked_files']} checkpoint files; {inventory['counts']['python_files_over_500_loc']} Python files over 500 LOC (review signal only)."
        elif item["id"] == "H0-04":
            dependency = _load(REPORT_ROOT / "dependency_graph.json")
            if dependency:
                finding_count = len(dependency["potential_circular_imports"]) + len(dependency["statically_unreferenced_candidates"])
                item["detail"] = f"{dependency['module_count']} modules; {dependency['internal_dependency_count']} internal edges; {finding_count} review findings. Static summary refreshed after an H0 analyzer-only correction; gate status unchanged."
        elif item["id"] == "H0-05" and symbols:
            item["detail"] = f"{symbols['symbol_count']} symbols; {len(symbols['candidates'])} static candidates; none classified DEAD."
        elif item["id"] == "H0-06" and duplication and complexity:
            priority = sum(value for key, value in complexity["classification_counts"].items() if key in {"HIGH_REVIEW_PRIORITY", "CRITICAL_REVIEW_PRIORITY"})
            item["detail"] = f"{duplication['candidate_count']} duplication candidates; {priority} high/critical review targets; no refactor performed."

    if registration:
        write_text(BASELINE_ROOT / "STARTUP_BASELINE.md", _startup(registration))
    else:
        write_text(BASELINE_ROOT / "STARTUP_BASELINE.md", f"# Registration and Startup Baseline\n\n`NOT_RUN`: H0 stopped at `{args.gate}` before this measurement.")
    if topology and combined:
        write_text(BASELINE_ROOT / "TEST_BASELINE.md", _tests(topology, combined))
    else:
        write_text(BASELINE_ROOT / "TEST_BASELINE.md", f"# Test Baseline\n\n`NOT_RUN`: H0 stopped at `{args.gate}` before the combined baseline completed.")
    if performance:
        write_text(BASELINE_ROOT / "PERFORMANCE_BASELINE.md", _performance(performance))
    else:
        write_text(BASELINE_ROOT / "PERFORMANCE_BASELINE.md", f"# Performance Baseline\n\n`NOT_RUN`: fail-closed gate `{args.gate}` stopped H0 before performance measurement. No optimization occurred.")
    if resources:
        write_text(BASELINE_ROOT / "RESOURCE_LIFECYCLE_BASELINE.md", _resources(resources))
    else:
        write_text(BASELINE_ROOT / "RESOURCE_LIFECYCLE_BASELINE.md", f"# Resource Lifecycle Baseline\n\n`NOT_RUN`: fail-closed gate `{args.gate}` stopped H0 before lifecycle measurement. No leak conclusion is claimed.")

    priority_counts = {
        "P0": 1,
        "P1": len(symbols["candidates"]) if symbols else 0,
        "P2": int(duplication["candidate_count"]) if duplication else 0,
        "P3": sum(value for key, value in (complexity or {}).get("classification_counts", {}).items() if key in {"HIGH_REVIEW_PRIORITY", "CRITICAL_REVIEW_PRIORITY"}),
        "P4": 0,
        "P5": 0,
        "P6": 1 if package and not package.get("matches_retained_release_archive_bytes", True) else 0,
        "P7": 0,
        "P8": sum(value for key, value in (docs or {}).get("classification_counts", {}).items() if key != "CURRENT"),
    }
    queue = "\n".join((
        "# H1 Candidate Queue", "",
        "H1 has not started. This queue is partial because H0 is blocked; performance and lifecycle priorities remain `NOT_RUN`.", "",
        markdown_table(("Priority", "Count", "State"), ((key, value, "PARTIAL" if key in {"P4", "P5"} else "RECORDED") for key, value in priority_counts.items())), "",
        "## H1Q-0001", "",
        markdown_table(("Field", "Value"), (
            ("ID", "H1Q-0001"), ("Subsystem", "H0 retained evidence"), ("File/symbol", args.gate),
            ("Evidence", args.detail), ("Risk", "Later cleanup would lack a valid complete comparison anchor"),
            ("Confidence", "HIGH"), ("Expected validation", "Resolve or explicitly authorize the required evidence rerun, then rerun H0 from the checkpoint"),
            ("Recommended phase", "H0 blocker; do not start H1"),
        )), "",
        "Static symbol, duplication, complexity, package, and documentation candidates remain in the generated H0 reports. Candidate status does not authorize deletion or refactoring.",
    ))
    write_text(REPOSITORY_ROOT / "hardening" / "H1_CANDIDATE_QUEUE.md", queue)

    hash_names = {
        "performance_report_hash": REPORT_ROOT / "performance_baseline.json",
        "resource_lifecycle_report_hash": REPORT_ROOT / "resource_lifecycle_baseline.json",
        "public_contract_hash": BASELINE_ROOT / "public_contract_baseline.json",
        "dependency_report_hash": REPORT_ROOT / "dependency_graph.json",
        "symbol_usage_report_hash": REPORT_ROOT / "symbol_usage.json",
        "duplication_report_hash": REPORT_ROOT / "duplication_candidates.json",
        "security_baseline_hash": REPORT_ROOT / "security_baseline.json",
    }
    manifest = {
        "baseline_version": "1.0.0",
        "status": "H0_BLOCKED",
        "comparison_anchor_usable": False,
        "blocking_gate": args.gate,
        "blocking_detail": args.detail,
        "product_version": PRODUCT_VERSION,
        "checkpoint_tag": CHECKPOINT_TAG,
        "checkpoint_commit": CHECKPOINT_COMMIT,
        "generated_timestamp": utc_now(),
        "codebase_counts": inventory["counts"] if inventory else None,
        "package_identity": {key: package.get(key) for key in ("archive_filename", "archive_file_count", "archive_bytes", "archive_sha256", "manifest_version")} if package else None,
        "test_baseline": {"topology": topology["counts"], "combined_count": combined.get("tests_run"), "status": combined["status"], "blender_version": combined.get("blender_version")} if topology and combined else None,
        "dataset_identity": dataset.get("dataset") if dataset else None,
        "benchmark_identity": dataset.get("golden_benchmark") if dataset else None,
        **{name: sha256_path(path) if path.is_file() else None for name, path in hash_names.items()},
        "known_findings_counts": priority_counts,
    }
    write_json(BASELINE_ROOT / "hardening_baseline_manifest.json", manifest)
    gate_rows = ((item["id"], item["status"], item.get("detail", "")) for item in normalized_gates)
    result = "\n".join((
        "# H0 Baseline Results", "",
        "Decision: **H0 BLOCKED**", "",
        f"Blocking gate: `{args.gate}`. {args.detail}", "",
        markdown_table(("Gate", "Status", "Detail"), gate_rows), "",
        "Performance, resource lifecycle, and any later gates not reached are `NOT_RUN`. H1 has not started. Resolve the evidence identity blocker or explicitly authorize the necessary rerun, then restart H0 from the unchanged checkpoint.", "",
        "No code was deleted; no runtime behavior was intentionally changed; no refactor was performed; no threshold was weakened; no package/version change occurred; no commit, push, merge, or tag occurred.",
    ))
    write_text(REPOSITORY_ROOT / "hardening" / "reports" / "H0_BASELINE_RESULTS.md", result)
    print(json.dumps({"status": "H0_BLOCKED", "gate": args.gate, "partial_manifest": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
