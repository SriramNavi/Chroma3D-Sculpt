"""Run resumable isolated Sprint 7 recommendation workers over 10 or 27 models."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from time import perf_counter

from release_input_fingerprint import write_release_input_identity

ROOT = Path(__file__).resolve().parents[2]
WORKER_VERSION = "sprint7-dataset-worker-1.2"
VALIDATION_MODE = "S7_DATASET_FAKE_OFFLINE"
REPRESENTATIVE = (
    "statue-asad-al-lat", "statue-bastet", "statue-cosmic-buddha-smithsonian-150k", "statue-hizen-komainu",
    "statue-hotei-water-basin", "statue-laocoon-group", "statue-mick-odwyer", "statue-pieta-michelangelo",
    "statue-thinker-rodin", "statue-venus-willendorf",
)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"); temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--source-directory", type=Path, required=True); parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--scope", choices=("representative", "full"), required=True); parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--output-directory", type=Path, default=ROOT / "manual-tests" / "sprint7" / "reports" / "dataset")
    args = parser.parse_args(); identity = write_release_input_identity()
    fingerprint = str(identity["aggregate_sha256"])
    dataset_manifest_hash = str(identity["dataset_manifest_sha256"])
    profile_context_hash = str(identity["profile_context_sha256"])
    available = {item.stem: item for item in args.source_directory.iterdir() if item.suffix.lower() in {".stl", ".obj", ".ply"}}
    ids = REPRESENTATIVE if args.scope == "representative" else tuple(sorted(available))
    sources = [(model_id, available[model_id]) for model_id in ids if model_id in available]
    started = perf_counter(); records = []
    for index, (model_id, source) in enumerate(sources, 1):
        digest = hashlib.sha256(source.read_bytes()).hexdigest(); retained = args.output_directory / f"{model_id}.json"
        prior = {}
        if retained.is_file():
            try: prior = json.loads(retained.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError): prior = {}
        reusable = all((
            prior.get("status") == "PASS",
            prior.get("source_file_sha256") == digest,
            prior.get("implementation_fingerprint") == fingerprint,
            prior.get("dataset_manifest_sha256") == dataset_manifest_hash,
            prior.get("profile_context_sha256") == profile_context_hash,
            prior.get("validation_mode") == VALIDATION_MODE,
            prior.get("worker_version") == WORKER_VERSION,
            isinstance(prior.get("performance_limits_hash"), str),
        ))
        if reusable:
            record = prior
        else:
            temp_root = ROOT / "manual-tests" / "sprint7" / "artifacts"
            temp_root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="dataset-", dir=temp_root) as folder:
                output = Path(folder) / "result.json"; worker = Path(__file__).with_name("dataset_blender_worker.py")
                command = [str(args.blender), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(worker), "--", "--model-id", model_id, "--source", str(source), "--output", str(output), "--implementation-fingerprint", fingerprint, "--dataset-manifest-sha256", dataset_manifest_hash, "--profile-context-sha256", profile_context_hash, "--validation-mode", VALIDATION_MODE, "--worker-version", WORKER_VERSION]
                try: completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=args.timeout_seconds, check=False)
                except subprocess.TimeoutExpired: record = {"model_id": model_id, "status": "TIMEOUT", "source_file_sha256": digest, "implementation_fingerprint": fingerprint, "dataset_manifest_sha256": dataset_manifest_hash, "profile_context_sha256": profile_context_hash, "validation_mode": VALIDATION_MODE, "worker_version": WORKER_VERSION}
                else:
                    if completed.returncode == 0 and output.is_file(): record = json.loads(output.read_text(encoding="utf-8"))
                    else: record = {"model_id": model_id, "status": "FAIL", "classification": "ENVIRONMENT_OR_PRODUCT", "source_file_sha256": digest, "implementation_fingerprint": fingerprint, "dataset_manifest_sha256": dataset_manifest_hash, "profile_context_sha256": profile_context_hash, "validation_mode": VALIDATION_MODE, "worker_version": WORKER_VERSION, "worker_exit_code": completed.returncode}
                _write(retained, record)
        records.append(record); print(f"{index}/{len(sources)} {model_id}: {record.get('status')}", flush=True)
    passed = sum(item.get("status") == "PASS" for item in records)
    expected = 10 if args.scope == "representative" else 27
    result = {
        "schema_version": "1.0.0", "milestone": "Sprint 7 AI Recommendation Foundation", "scope": args.scope,
        "status": "PASS" if len(records) == expected and passed == expected else "FAIL", "expected_count": expected, "model_count": len(records), "passed_count": passed,
        "source_mutation_count": sum(item.get("source_immutability") is not True for item in records), "geometry_payload_count": sum(item.get("geometry_elements_exported") != 0 for item in records),
        "timeout_count": sum(item.get("status") == "TIMEOUT" for item in records), "unclassified_failure_count": sum(item.get("status") not in {"PASS", "TIMEOUT"} for item in records),
        "live_provider_calls": 0, "implementation_fingerprint": fingerprint, "dataset_manifest_sha256": dataset_manifest_hash,
        "golden_manifest_sha256": identity["golden_manifest_sha256"], "profile_context_sha256": profile_context_hash,
        "validation_mode": VALIDATION_MODE, "worker_version": WORKER_VERSION,
        "elapsed_seconds": round(perf_counter() - started, 6), "recorded_at": datetime.now(timezone.utc).isoformat(),
        "maximum_observed_point_working_set_bytes": max((int(item.get("point_memory_observation", {}).get("value") or 0) for item in records), default=0),
        "memory_claim": "Maximum of single completion-time point observations; not peak memory.",
        "records": records, "limitations": ["Local fake-provider context/grounding workflow only; no mutation, live provider, slicer, physical print, or production SLA evidence."],
    }
    _write(args.output_directory / f"{args.scope}_summary.json", result)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__": raise SystemExit(main())
