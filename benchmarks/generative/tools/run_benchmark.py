"""Cost-aware, resumable CGB orchestrator with offline fake end-to-end support."""

from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from typing import Any
from uuid import uuid4


GENERATIVE_ROOT = Path(__file__).resolve().parents[1]
if str(GENERATIVE_ROOT) not in sys.path:
    sys.path.insert(0, str(GENERATIVE_ROOT))

from backends.base import BenchmarkPolicyError, CostEstimate, ExecutionPolicy, GenerationRequest  # noqa: E402
from backends.registry import backend_registry  # noqa: E402
from common import (  # noqa: E402
    CGB_VERSION, PROJECT_ROOT, VALIDATION_ROOT, cache_identity, evaluation_cache_identity,
    read_json, relative_to_project, reusable_record, sha256_file, stable_hash, utc_now, write_json,
)
from evaluate_geometry import EVALUATION_SETTINGS, EVALUATOR_VERSION, evaluate_geometry  # noqa: E402
from generate_report import generate as generate_report, markdown as report_markdown  # noqa: E402
from mesh_io import load_mesh  # noqa: E402


RUNNER_VERSION = "cgb-runner-1.0.0"


def _source(case: dict[str, Any]) -> Path:
    path = PROJECT_ROOT / str(case["source_storage_hint"])
    if not path.is_file():
        raise FileNotFoundError(f"Ground-truth source is unavailable for {case['case_id']}")
    return path


def _reference(case: dict[str, Any], track: str) -> tuple[Path, ...]:
    if track == "A":
        return (PROJECT_ROOT / case["single_image_reference"]["path"],)
    if track == "B":
        return tuple(PROJECT_ROOT / item["path"] for item in case["multiview_references"])
    return ()


def _conditioning(blender: Path, raw_artifact: Path, output_root: Path) -> dict[str, Any]:
    conditioned = output_root / "conditioned.stl"
    metrics_path = output_root / "conditioning.json"
    worker = Path(__file__).with_name("evaluate_conditioning.py")
    command = [
        str(blender), "--background", "--factory-startup", "--python-exit-code", "1",
        "--python", str(worker), "--", "--source", str(raw_artifact),
        "--conditioned-output", str(conditioned), "--metrics-output", str(metrics_path),
    ]
    completed = subprocess.run(
        command, cwd=PROJECT_ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300, check=False,
    )
    if not metrics_path.is_file():
        return {"status": "ANALYSIS_FAILED", "worker_exit_code": completed.returncode, "error": "Conditioning metrics were not produced."}
    result = read_json(metrics_path)
    result["worker_exit_code"] = completed.returncode
    result["metrics_path"] = relative_to_project(metrics_path)
    result["conditioned_artifact_path"] = relative_to_project(conditioned) if conditioned.is_file() else None
    return result


def _authorize_commercial_stage(
    *, backend, cases: dict[str, dict[str, Any]], case_ids: list[str], track: str,
    policy: ExecutionPolicy, dry_run: bool,
) -> dict[str, Any] | None:
    """Project and authorize the complete commercial stage before any submit."""

    descriptor = backend.backend_info()
    if dry_run or descriptor.backend_type != "COMMERCIAL_API":
        return None
    estimates: list[CostEstimate] = []
    for case_id in case_ids:
        case = cases[case_id]
        inputs = _reference(case, track)
        if track in {"A", "B"} and (not inputs or any(not item.is_file() for item in inputs)):
            raise RuntimeError(f"Required reference render is NOT_RUN for {case_id} Track {track}.")
        parameters = {"texture": False, "pbr": False, "should_texture": False, "enable_pbr": False}
        request_value = GenerationRequest(
            case_id=case_id, track=track, input_paths=inputs,
            prompt=case.get("prompt_if_defined"), attempt=1,
            seed=0 if descriptor.supports_seed else None,
            parameters=parameters, quality_mode="provider_default", dry_run=False,
        )
        unsupported = backend.unsupported_track_job(request_value)
        if unsupported is not None:
            raise RuntimeError(f"{descriptor.backend_id} does not support CGB Track {track}.")
        estimates.append(backend.estimate_cost(request_value))
    unknown = any(item.state == "UNKNOWN" for item in estimates)
    credits = None if any(item.credits is None for item in estimates) else sum((item.credits for item in estimates), Decimal("0"))
    total_usd = None if unknown else sum((item.estimated_usd or Decimal("0") for item in estimates), Decimal("0"))
    combined = CostEstimate("UNKNOWN" if unknown else "ESTIMATED", total_usd, credits, "Complete CGB stage projection")
    preview = {
        "backend": descriptor.backend_id, "cases": len(case_ids), "attempts": 1,
        "total_jobs": len(case_ids), "cost_state": combined.state,
        "estimated_cost_usd": None if total_usd is None else str(total_usd),
        "estimated_credits": None if credits is None else str(credits),
        "configured_budget_usd": str(policy.max_spend_usd),
        "configured_max_live_jobs": policy.max_live_jobs,
    }
    print("CGB live stage projection: " + json.dumps(preview, sort_keys=True), flush=True)
    policy.authorize_live_stage(jobs=len(case_ids), estimate=combined)
    return preview


def _attempt(
    *, backend, case: dict[str, Any], track: str, attempt: int, output_root: Path,
    dry_run: bool, fake_mode: str, blender: Path | None,
) -> dict[str, Any]:
    descriptor = backend.backend_info()
    source = _source(case)
    input_paths = (source,) if descriptor.backend_id == "fake_generator" else _reference(case, track)
    parameters: dict[str, Any] = {"fake_mode": fake_mode} if descriptor.backend_id == "fake_generator" else {}
    if descriptor.supports_texture:
        parameters.update({"texture": False, "pbr": False, "should_texture": False, "enable_pbr": False})
    request_value = GenerationRequest(
        case_id=case["case_id"], track=track, input_paths=input_paths,
        prompt=case.get("prompt_if_defined"), attempt=attempt, seed=0 if descriptor.supports_seed else None,
        parameters=parameters, quality_mode="provider_default", dry_run=dry_run,
    )
    parameter_hash = stable_hash(request_value.to_dict()["parameters"])
    cache_key, identity = cache_identity(
        case_hash=case["case_hash"], backend_id=descriptor.backend_id,
        model_version=descriptor.model_version, adapter_version=backend.adapter_version,
        parameter_hash=parameter_hash, attempt=attempt, seed=request_value.seed,
        seed_semantics="SUPPORTED_PROVIDER_SEED" if descriptor.supports_seed else "UNSUPPORTED",
        quality_mode=request_value.quality_mode,
        evaluator_version=EVALUATOR_VERSION,
        evaluation_settings_hash=stable_hash(EVALUATION_SETTINGS),
    )
    cache_path = output_root / "cache" / f"{cache_key}.json"
    if cache_path.is_file():
        retained = read_json(cache_path)
        if reusable_record(retained, identity, output_root):
            retained["resumed"] = True
            return retained
    started = perf_counter()
    record: dict[str, Any] = {
        "run_id": str(uuid4()), "cgb_version": CGB_VERSION, "timestamp": utc_now(),
        "case_id": case["case_id"], "track": track, "backend_id": descriptor.backend_id,
        "provider": descriptor.provider, "model_version": descriptor.model_version,
        "backend_version_source": descriptor.official_sources[0]["url"],
        "input_hashes": [sha256_file(item) for item in input_paths if item.is_file()],
        "attempt": attempt, "seed": request_value.seed, "parameters": parameters,
        "request_parameter_hash": parameter_hash, "quality_mode": request_value.quality_mode,
        "task_id": None, "status": "NOT_RUN", "error_class": None,
        "latency": {}, "credits": None, "estimated_cost_usd": None,
        "raw_artifact_sha256": None, "raw_artifact_format": None,
        "raw_artifact_path": None, "raw_metrics_path": None,
        "conditioned_metrics_path": None, "alignment": None,
        "environment": backend.validate_environment(), "gpu": backend.validate_environment().get("gpu"),
        "driver": None, "notes": [], "cache_key": cache_key, "cache_identity": identity,
        "resumed": False, "dry_run": dry_run,
    }
    source_hash_before = sha256_file(source)
    try:
        estimate = backend.estimate_cost(request_value)
        record["cost_state"] = estimate.state
        record["estimated_cost_usd"] = None if estimate.estimated_usd is None else float(estimate.estimated_usd)
        record["credits"] = None if estimate.credits is None else float(estimate.credits)
        job = backend.submit(request_value, output_root / "raw" / descriptor.backend_id)
        record["task_id"], record["status"], record["error_class"] = job.task_id, job.status, job.error_class
        record["provider_metadata"] = backend.normalize_metadata(job)
        if job.artifact_path is not None and job.artifact_path.is_file():
            record["raw_artifact_sha256"] = sha256_file(job.artifact_path)
            record["evaluation_cache_identity"] = evaluation_cache_identity(
                artifact_sha256=record["raw_artifact_sha256"],
                evaluator_version=EVALUATOR_VERSION,
                evaluation_settings_hash=stable_hash(EVALUATION_SETTINGS),
            )
            record["raw_artifact_format"] = job.artifact_path.suffix.lower().lstrip(".")
            record["raw_artifact_path"] = job.artifact_path.resolve().relative_to(output_root.resolve()).as_posix()
            metrics_path = output_root / "metrics" / descriptor.backend_id / f"{case['case_id']}-attempt-{attempt}-raw.json"
            metrics = evaluate_geometry(load_mesh(source), load_mesh(job.artifact_path))
            write_json(metrics_path, metrics)
            record["raw_metrics"] = metrics
            record["raw_metrics_path"] = relative_to_project(metrics_path)
            record["alignment"] = metrics.get("alignment")
            if metrics.get("status") != "PASS":
                record["status"] = "ANALYSIS_FAILED"
            if blender is not None and record["status"] == "PASS":
                conditioning_root = output_root / "conditioning" / descriptor.backend_id / f"{case['case_id']}-attempt-{attempt}"
                conditioning = _conditioning(blender, job.artifact_path, conditioning_root)
                record["conditioning"] = conditioning
                record["conditioned_metrics_path"] = conditioning.get("metrics_path")
                conditioned_path_value = conditioning.get("conditioned_artifact_path")
                if conditioning.get("status") == "PASS" and isinstance(conditioned_path_value, str):
                    conditioned_path = PROJECT_ROOT / conditioned_path_value
                    conditioned_evaluation = evaluate_geometry(load_mesh(source), load_mesh(conditioned_path))
                    conditioned_metrics_path = conditioning_root / "conditioned_geometry.json"
                    write_json(conditioned_metrics_path, conditioned_evaluation)
                    record["conditioned_evaluation_cache_identity"] = evaluation_cache_identity(
                        artifact_sha256=sha256_file(conditioned_path),
                        evaluator_version=EVALUATOR_VERSION,
                        evaluation_settings_hash=stable_hash(EVALUATION_SETTINGS),
                    )
                    record["conditioned_geometry_metrics_path"] = relative_to_project(conditioned_metrics_path)
                    record["conditioning_fidelity_drift"] = (
                        conditioned_evaluation["shape_fidelity"]["normalized_symmetric_chamfer"]
                        - metrics["shape_fidelity"]["normalized_symmetric_chamfer"]
                    )
                elif conditioning.get("status") != "PASS":
                    record["status"] = "ANALYSIS_FAILED"
            else:
                record["conditioning"] = {"status": "NOT_RUN", "reason": "Blender conditioning worker was not requested."}
        elif not dry_run and record["status"] == "PASS":
            record["status"], record["error_class"] = "INVALID_ARTIFACT", "MISSING_RAW_ARTIFACT"
    except BenchmarkPolicyError as exc:
        record["status"], record["error_class"], record["error"] = exc.classification, exc.classification, str(exc)
    except Exception as exc:
        record["status"], record["error_class"], record["error"] = "ANALYSIS_FAILED", type(exc).__name__, str(exc)
    record["latency"] = {"end_to_end_seconds": round(perf_counter() - started, 6)}
    record["source_immutable"] = sha256_file(source) == source_hash_before == case["source_sha256"]
    if not record["source_immutable"]:
        record["status"], record["error_class"] = "ANALYSIS_FAILED", "SOURCE_MUTATED"
    write_json(cache_path, record)
    return record


def run(args: argparse.Namespace) -> dict[str, Any]:
    policy = ExecutionPolicy.from_environment()
    registry = backend_registry(policy)
    if args.backend not in registry:
        raise ValueError(f"Unknown backend: {args.backend}")
    backend = registry[args.backend]
    corpus = read_json(GENERATIVE_ROOT / "corpus" / "manifest.json")
    subset = read_json(GENERATIVE_ROOT / "corpus" / f"{args.subset}.json")
    if corpus["cgb_version"] != CGB_VERSION or subset["cgb_version"] != CGB_VERSION:
        raise RuntimeError("CGB version mismatch; incompatible runs cannot be compared.")
    cases = {case["case_id"]: case for case in corpus["cases"]}
    stage_cost_projection = _authorize_commercial_stage(
        backend=backend, cases=cases, case_ids=list(subset["case_ids"]),
        track=args.track, policy=policy, dry_run=args.dry_run,
    )
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    attempts = []
    started = perf_counter()
    for case_id in subset["case_ids"]:
        record = _attempt(
            backend=backend, case=cases[case_id], track=args.track, attempt=1,
            output_root=output_root, dry_run=args.dry_run,
            fake_mode=args.fake_mode, blender=args.blender.resolve() if args.blender else None,
        )
        attempts.append(record)
        print(f"{len(attempts)}/{subset['case_count']} {case_id}: {record['status']}", flush=True)
        if record["status"] != "PASS" and not args.continue_on_failure:
            break
    success_count = sum(record["status"] == "PASS" for record in attempts)
    run_manifest = {
        "schema_version": "1.0.0", "runner_version": RUNNER_VERSION, "run_id": str(uuid4()),
        "cgb_version": CGB_VERSION, "backend_id": args.backend, "subset_id": subset["subset_id"],
        "track": args.track, "attempt_count": len(attempts), "success_count": success_count,
        "status": "PASS" if len(attempts) == subset["case_count"] and success_count == len(attempts) else "GENERATION_FAILED",
        "policy": policy.to_dict(), "live_generations": 0 if args.backend == "fake_generator" or args.dry_run else len(attempts),
        "stage_cost_projection": stage_cost_projection,
        "live_api_calls": 0 if args.backend == "fake_generator" or args.dry_run else "BOUNDED_BY_ADAPTER",
        "api_spend_usd": 0 if args.backend == "fake_generator" or args.dry_run else "UNKNOWN",
        "model_downloads": 0, "cloud_gpu_usage": 0,
        "source_mutation_count": sum(record.get("source_immutable") is not True for record in attempts),
        "elapsed_seconds": round(perf_counter() - started, 6), "attempts": attempts,
    }
    run_manifest["run_hash"] = stable_hash(run_manifest)
    run_path = output_root / "run.json"
    write_json(run_path, run_manifest)
    result = generate_report(run_manifest)
    write_json(output_root / "result.json", result)
    (output_root / "summary.md").write_text(report_markdown(result), encoding="utf-8", newline="\n")
    return run_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default="fake_generator")
    parser.add_argument("--subset", choices=("smoke3", "core10", "full27"), default="smoke3")
    parser.add_argument("--track", choices=tuple("ABCDEFGH"), default="A")
    parser.add_argument("--output-root", type=Path, default=VALIDATION_ROOT / "runs" / "latest")
    parser.add_argument("--blender", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fake-mode", choices=("success", "failure", "timeout", "invalid"), default="success")
    parser.add_argument("--continue-on-failure", action="store_true")
    args = parser.parse_args()
    try:
        result = run(args)
    except Exception as exc:
        print(f"CGB benchmark failed: {type(exc).__name__}: {exc}")
        return 1
    print(
        f"CGB benchmark {result['status']}: attempts={result['attempt_count']} successes={result['success_count']} "
        f"source_mutations={result['source_mutation_count']} live={result['live_generations']} spend={result['api_spend_usd']}"
    )
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
