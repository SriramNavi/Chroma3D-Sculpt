from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASELINE_ROOT = REPOSITORY_ROOT / "benchmarks" / "golden"
DATASET_ROOT = REPOSITORY_ROOT / "datasets" / "statues"
DATASET_MANIFEST_PATH = DATASET_ROOT / "manifests" / "statue_dataset_manifest.json"
BASELINE_ROOT = DEFAULT_BASELINE_ROOT
RUNNER_PATH = Path(__file__).with_name("run_golden_benchmark.py")

EXPECTED_BENCHMARK_VERSION = "1.0.0"
EXPECTED_DATASET_VERSION = "1.0.0"
EXPECTED_SOFTWARE_VERSION = "0.3.0-alpha.1"
EXPECTED_MESH_COUNT = 27
REQUIRED_DIRECTORIES = (
    "raw",
    "reports",
    "timings",
    "statistics",
    "comparisons",
    "manifests",
    "thumbnails",
)
REQUIRED_ENTRY_ARTIFACTS = (
    "analysis",
    "repair_audit",
    "rollback_audit",
    "golden",
    "comparison",
    "timings",
    "report",
    "thumbnail",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _schema_descriptor(value: Any, path: str = "$") -> list[str]:
    if isinstance(value, dict):
        lines = [f"{path}:object"]
        for key in sorted(value):
            lines.extend(_schema_descriptor(value[key], f"{path}.{key}"))
        return lines
    if isinstance(value, list):
        lines = [f"{path}:array"]
        item_lines: set[str] = set()
        for item in value:
            item_lines.update(_schema_descriptor(item, f"{path}[]"))
        lines.extend(sorted(item_lines))
        return lines
    if value is None:
        value_type = "null"
    elif isinstance(value, bool):
        value_type = "boolean"
    elif isinstance(value, int):
        value_type = "integer"
    elif isinstance(value, float):
        value_type = "number"
    elif isinstance(value, str):
        value_type = "string"
    else:
        value_type = type(value).__name__
    return [f"{path}:{value_type}"]


def _schema_fingerprint(value: Any) -> str:
    return _stable_hash(_schema_descriptor(value))


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _resolved_artifact_path(recorded_path: str) -> Path:
    if recorded_path.startswith("benchmarks/golden/"):
        path = (BASELINE_ROOT / Path(*recorded_path[len("benchmarks/golden/") :].split("/"))).resolve()
    elif recorded_path.startswith("datasets/statues/"):
        path = (DATASET_ROOT / Path(*recorded_path[len("datasets/statues/") :].split("/"))).resolve()
    else:
        path = (REPOSITORY_ROOT / recorded_path).resolve()
    try:
        path.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError as exc:
        for allowed_root in (BASELINE_ROOT, DATASET_ROOT):
            try:
                path.relative_to(allowed_root.resolve())
                break
            except ValueError:
                continue
        else:
            raise AssertionError(f"Artifact path escapes allowed roots: {recorded_path}") from exc
    return path


def _verify_entry(
    entry: dict[str, Any],
    dataset_asset: dict[str, Any],
) -> dict[str, Any]:
    mesh_id = entry["mesh_id"]
    _check(mesh_id == dataset_asset["unique_id"], f"dataset ID mismatch: {mesh_id}")
    _check(
        entry["source_sha256"] == dataset_asset["checksum_sha256"],
        f"manifest source hash mismatch: {mesh_id}",
    )
    _check(
        entry["triangle_count"] == dataset_asset["triangle_count"],
        f"triangle count mismatch: {mesh_id}",
    )
    _check(
        entry["vertex_count"] == dataset_asset["vertex_count"],
        f"vertex count mismatch: {mesh_id}",
    )
    _check(
        entry["validation_status"] == "PASS",
        f"entry validation is not PASS: {mesh_id}",
    )

    artifacts = entry["artifacts"]
    _check(
        set(REQUIRED_ENTRY_ARTIFACTS) <= set(artifacts),
        f"entry artifact set incomplete: {mesh_id}",
    )
    for label in REQUIRED_ENTRY_ARTIFACTS:
        artifact = artifacts[label]
        path = _resolved_artifact_path(artifact["path"])
        _check(path.is_file(), f"missing {label} artifact: {mesh_id}")
        _check(path.stat().st_size == artifact["size_bytes"], f"size mismatch {label}: {mesh_id}")
        _check(_sha256(path) == artifact["sha256"], f"SHA-256 mismatch {label}: {mesh_id}")

    golden = _read_json(_resolved_artifact_path(artifacts["golden"]["path"]))
    analysis = _read_json(_resolved_artifact_path(artifacts["analysis"]["path"]))
    repair_audit = _read_json(
        _resolved_artifact_path(artifacts["repair_audit"]["path"])
    )
    rollback_audit = _read_json(
        _resolved_artifact_path(artifacts["rollback_audit"]["path"])
    )
    comparison = _read_json(
        _resolved_artifact_path(artifacts["comparison"]["path"])
    )
    timings = _read_json(_resolved_artifact_path(artifacts["timings"]["path"]))
    report = _read_json(_resolved_artifact_path(artifacts["report"]["path"]))

    _check(golden["mesh_id"] == mesh_id, f"golden mesh ID mismatch: {mesh_id}")
    _check(
        golden["benchmark_version"] == EXPECTED_BENCHMARK_VERSION,
        f"golden benchmark version mismatch: {mesh_id}",
    )
    _check(
        golden["dataset_version"] == EXPECTED_DATASET_VERSION,
        f"golden dataset version mismatch: {mesh_id}",
    )
    _check(
        golden["software_version"] == EXPECTED_SOFTWARE_VERSION,
        f"golden software version mismatch: {mesh_id}",
    )
    _check(
        golden["mesh_metadata"] == dataset_asset,
        f"golden dataset metadata differs: {mesh_id}",
    )
    _check(
        golden["analysis_report"] == analysis,
        f"embedded analysis differs from exported analysis: {mesh_id}",
    )
    _check(
        golden["repair_report"] == repair_audit,
        f"embedded repair audit differs: {mesh_id}",
    )
    _check(
        golden["rollback_report"] == rollback_audit,
        f"embedded rollback audit differs: {mesh_id}",
    )
    _check(
        golden["comparison"] == comparison,
        f"embedded comparison differs: {mesh_id}",
    )
    _check(
        golden["timings"] == timings,
        f"embedded timings differ: {mesh_id}",
    )

    hashes = golden["hashes"]
    source_path = _resolved_artifact_path(dataset_asset["stored_path"])
    metadata_path = DATASET_ROOT / "metadata" / f"{mesh_id}.json"
    source_thumbnail = _resolved_artifact_path(dataset_asset["thumbnail_path"])
    _check(_sha256(source_path) == hashes["source_mesh_sha256"], f"source hash mismatch: {mesh_id}")
    _check(_sha256(metadata_path) == hashes["metadata_sha256"], f"metadata hash mismatch: {mesh_id}")
    _check(_sha256(source_thumbnail) == hashes["thumbnail_sha256"], f"source thumbnail hash mismatch: {mesh_id}")
    _check(_sha256(DATASET_MANIFEST_PATH) == hashes["dataset_manifest_sha256"], f"dataset manifest hash mismatch: {mesh_id}")
    _check(
        _sha256(_resolved_artifact_path(artifacts["analysis"]["path"]))
        == hashes["analysis_report_sha256"],
        f"internal analysis hash mismatch: {mesh_id}",
    )
    _check(
        _sha256(_resolved_artifact_path(artifacts["repair_audit"]["path"]))
        == hashes["repair_audit_sha256"],
        f"internal repair hash mismatch: {mesh_id}",
    )
    _check(
        _sha256(_resolved_artifact_path(artifacts["rollback_audit"]["path"]))
        == hashes["rollback_audit_sha256"],
        f"internal rollback hash mismatch: {mesh_id}",
    )
    _check(
        _sha256(_resolved_artifact_path(artifacts["comparison"]["path"]))
        == hashes["comparison_sha256"],
        f"internal comparison hash mismatch: {mesh_id}",
    )
    _check(
        _sha256(_resolved_artifact_path(artifacts["timings"]["path"]))
        == hashes["timings_sha256"],
        f"internal timing hash mismatch: {mesh_id}",
    )

    schema_payloads = {
        "analysis_report": analysis,
        "after_analysis": golden["after_repair_analysis"],
        "repair_audit": repair_audit,
        "rollback_audit": rollback_audit,
        "comparison": comparison,
        "timings": timings,
    }
    for label, payload in schema_payloads.items():
        _check(
            _schema_fingerprint(payload)
            == golden["schema_fingerprints"][label],
            f"schema fingerprint mismatch {label}: {mesh_id}",
        )
        _check(
            golden["schema_fingerprints"][label]
            == entry["schema_fingerprints"][label],
            f"manifest schema fingerprint mismatch {label}: {mesh_id}",
        )

    _check(analysis["schema_version"] == golden["analysis_schema_version"], f"analysis schema mismatch: {mesh_id}")
    _check(repair_audit["schema_version"] == golden["repair_audit_schema_version"], f"repair schema mismatch: {mesh_id}")
    _check(rollback_audit["schema_version"] == golden["repair_audit_schema_version"], f"rollback schema mismatch: {mesh_id}")
    _check(repair_audit["extension_version"] == EXPECTED_SOFTWARE_VERSION, f"repair software mismatch: {mesh_id}")
    _check(rollback_audit["extension_version"] == EXPECTED_SOFTWARE_VERSION, f"rollback software mismatch: {mesh_id}")
    _check(timings["mesh_id"] == mesh_id, f"timings ID mismatch: {mesh_id}")
    _check(comparison["mesh_id"] == mesh_id, f"comparison ID mismatch: {mesh_id}")
    _check(report["mesh_id"] == mesh_id and report["status"] == "PASS", f"per-mesh report failed: {mesh_id}")

    lifecycle = golden["lifecycle_actions"]
    _check(lifecycle["restore"]["executed"], f"restore not exercised: {mesh_id}")
    _check(lifecycle["accept"]["executed"], f"accept not exercised: {mesh_id}")
    _check(lifecycle["rollback"]["executed"], f"rollback not exercised: {mesh_id}")
    _check(
        lifecycle["undo"]["executed"]
        or lifecycle["undo"]["status"] == "NOT_APPLICABLE",
        f"undo accounting invalid: {mesh_id}",
    )
    validation = golden["validation"]
    _check(validation["status"] == "PASS", f"golden validation failed: {mesh_id}")
    _check(validation["source_hash_matches_metadata"], f"source/metadata mismatch: {mesh_id}")
    _check(validation["source_hash_unchanged"], f"source changed: {mesh_id}")
    _check(validation["all_lifecycle_operator_results_finished"], f"operator lifecycle failed: {mesh_id}")
    _check(not validation["errors"], f"golden validation errors present: {mesh_id}")
    _check(repair_audit["final_decision"] == "ACCEPTED", f"accepted audit decision mismatch: {mesh_id}")
    _check(rollback_audit["final_decision"] == "ROLLED_BACK", f"rollback audit decision mismatch: {mesh_id}")
    _check(not repair_audit["failure_records"], f"repair failure records present: {mesh_id}")
    _check(not rollback_audit["failure_records"], f"rollback failure records present: {mesh_id}")
    _check(golden["operation_count"] == len(repair_audit["session"]["operation_records"]), f"operation count mismatch: {mesh_id}")

    return {
        "mesh_id": mesh_id,
        "timing_class": golden["timing_class"],
        "mesh_classifications": golden["mesh_classifications"],
        "severity_before": analysis["severity"],
        "severity_after": golden["after_repair_analysis"]["severity"],
        "warning_count": len(golden["warnings"]),
        "operation_count": golden["operation_count"],
        "total_wall_seconds": timings["total_wall_seconds"],
        "total_cpu_seconds": timings["total_cpu_seconds"],
    }


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate all stored Chroma3D Golden Benchmark artifacts."
    )
    parser.add_argument(
        "--baseline-root",
        type=Path,
        default=DEFAULT_BASELINE_ROOT,
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=DATASET_ROOT,
    )
    return parser.parse_args()


def main() -> int:
    global BASELINE_ROOT, DATASET_ROOT, DATASET_MANIFEST_PATH
    arguments = _parse_arguments()
    baseline_root = arguments.baseline_root.resolve()
    BASELINE_ROOT = baseline_root
    DATASET_ROOT = arguments.dataset_root.resolve()
    DATASET_MANIFEST_PATH = DATASET_ROOT / "manifests" / "statue_dataset_manifest.json"
    _check(RUNNER_PATH.is_file(), "golden regression runner is missing")
    _check(DATASET_MANIFEST_PATH.is_file(), "dataset manifest is missing")
    for name in REQUIRED_DIRECTORIES:
        _check((baseline_root / name).is_dir(), f"missing benchmark directory: {name}")
    _check((baseline_root / "README.md").is_file(), "golden README is missing")
    _check(
        (baseline_root / "BENCHMARK_SUMMARY.md").is_file(),
        "benchmark summary is missing",
    )
    manifest_path = baseline_root / "manifests" / "golden_manifest.json"
    statistics_path = baseline_root / "statistics" / "golden_statistics.json"
    generation_path = baseline_root / "reports" / "generation_status.json"
    per_mesh_path = baseline_root / "reports" / "golden_per_mesh_summary.json"
    for path in (manifest_path, statistics_path, generation_path, per_mesh_path):
        _check(path.is_file(), f"missing required artifact: {path.name}")

    dataset_manifest = _read_json(DATASET_MANIFEST_PATH)
    golden_manifest = _read_json(manifest_path)
    stats = _read_json(statistics_path)
    generation = _read_json(generation_path)
    per_mesh = _read_json(per_mesh_path)
    _check(
        golden_manifest["benchmark_version"] == EXPECTED_BENCHMARK_VERSION,
        "benchmark version mismatch",
    )
    _check(
        golden_manifest["dataset_version"] == EXPECTED_DATASET_VERSION,
        "dataset version mismatch",
    )
    _check(
        golden_manifest["software_version"] == EXPECTED_SOFTWARE_VERSION,
        "software version mismatch",
    )
    _check(
        golden_manifest["mesh_count"] == EXPECTED_MESH_COUNT,
        "golden manifest mesh count mismatch",
    )
    _check(
        golden_manifest["dataset_manifest_sha256"] == _sha256(DATASET_MANIFEST_PATH),
        "golden manifest dataset hash mismatch",
    )
    _check(
        golden_manifest["source_git_tag"] == EXPECTED_SOFTWARE_VERSION.replace("-", "-", 1)
        or golden_manifest["source_git_tag"] == f"v{EXPECTED_SOFTWARE_VERSION}",
        "source Git tag does not identify the current release",
    )
    _check(generation["failed_mesh_count"] == 0, "generation failures recorded")
    _check(
        generation["completed_mesh_count"] == EXPECTED_MESH_COUNT,
        "generation completion count mismatch",
    )
    _check(per_mesh["mesh_count"] == EXPECTED_MESH_COUNT, "per-mesh report count mismatch")

    dataset_by_id = {
        item["unique_id"]: item for item in dataset_manifest["assets"]
    }
    entries = golden_manifest["benchmark_entries"]
    identifiers = [item["mesh_id"] for item in entries]
    _check(len(entries) == EXPECTED_MESH_COUNT, "benchmark entry count mismatch")
    _check(len(identifiers) == len(set(identifiers)), "duplicate benchmark mesh IDs")
    _check(set(identifiers) == set(dataset_by_id), "dataset/benchmark mesh set mismatch")

    summaries = [
        _verify_entry(entry, dataset_by_id[entry["mesh_id"]])
        for entry in entries
    ]
    _check(
        stats["mesh_count"] == EXPECTED_MESH_COUNT,
        "statistics mesh count mismatch",
    )
    _check(
        stats["timing_class_distribution"]
        == dict(sorted(Counter(item["timing_class"] for item in summaries).items())),
        "timing class distribution mismatch",
    )
    classification_counts: Counter[str] = Counter()
    for item in summaries:
        classification_counts.update(item["mesh_classifications"])
    _check(
        stats["mesh_classification_distribution"]
        == dict(sorted(classification_counts.items())),
        "mesh classification distribution mismatch",
    )
    _check(
        stats["warning_total"] == sum(item["warning_count"] for item in summaries),
        "warning total mismatch",
    )

    _check(
        _sha256(statistics_path) == golden_manifest["statistics"]["sha256"],
        "statistics artifact hash mismatch",
    )
    summary_path = _resolved_artifact_path(
        golden_manifest["summary_report"]["path"]
    )
    _check(
        _sha256(summary_path) == golden_manifest["summary_report"]["sha256"],
        "summary report hash mismatch",
    )

    all_json = sorted(baseline_root.rglob("*.json"))
    for path in all_json:
        _read_json(path)
    _check(not list(baseline_root.rglob("*.part")), "partial artifacts remain")
    _check(not list(baseline_root.rglob("*.pyc")), "Python bytecode remains")
    _check(
        len(list((baseline_root / "raw").glob("*_golden.json")))
        == EXPECTED_MESH_COUNT,
        "golden truth file count mismatch",
    )
    _check(
        len(list((baseline_root / "comparisons").glob("*_comparison.json")))
        == EXPECTED_MESH_COUNT,
        "comparison file count mismatch",
    )
    _check(
        len(list((baseline_root / "timings").glob("*_timings.json")))
        == EXPECTED_MESH_COUNT,
        "timing file count mismatch",
    )
    _check(
        len(list((baseline_root / "thumbnails").glob("*.png")))
        == EXPECTED_MESH_COUNT,
        "thumbnail file count mismatch",
    )

    print(
        "PASS golden manifest, versions, source revision, and 27-entry corpus"
    )
    print("PASS all stored JSON parsed and schema fingerprints matched")
    print("PASS source, metadata, thumbnail, and artifact SHA-256 checks")
    print("PASS analysis, repair, comparison, lifecycle, and no-corruption evidence")
    print("PASS timing, classification, statistics, and report counts")
    print(
        f"Verified {len(summaries)}/{EXPECTED_MESH_COUNT} golden meshes; "
        f"{len(all_json)} JSON artifacts; 0 integrity failures."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL {type(exc).__name__}: {exc}")
        raise SystemExit(1)
