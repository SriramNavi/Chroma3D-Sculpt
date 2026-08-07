"""Evaluate the exact G0-01..G0-22 ledger from retained local evidence."""

from __future__ import annotations

from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
import io
import subprocess
import unittest
import zipfile
from typing import Any, Callable

from _support import GENERATIVE_ROOT, PROJECT_ROOT
from backends.base import BackendDescriptor, ExecutionPolicy, GenerationBackend
from backends.registry import backend_registry, registry_matrix
from common import CGB_VERSION, VALIDATION_ROOT, read_json, sha256_file, stable_hash, write_json
import _project


EXPECTED_H4 = "70657006b69627591f563b61977d7c378a9b1985"
EXPECTED_H4_TAG_OBJECT = "9c8b5d6d0ebac0eb668c3855a28736ebb1c63c83"
EXPECTED_BRANCH = "feature/g0-generative-benchmark"
RECOVERY_TAGS = (
    "v0.8.0-alpha.1", "v0.8.0-pre-hardening-backup",
    "v0.8.0-h0-hardening-baseline", "v0.8.0-h1-hardening-checkpoint",
    "v0.8.0-h2-hardening-checkpoint", "v0.8.0-h3-hardening-checkpoint",
    "v0.8.0-h4-hardening-checkpoint",
)
ALLOWED_STATUS_ROOTS = (
    "PROJECT_RULES.md", "benchmarks/generative/", "manual-tests/g0/", "docs/generative/",
)


def _git(*args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    if check and completed.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout.rstrip()


def _run_unit_tests() -> dict[str, Any]:
    suite = unittest.defaultTestLoader.discover(str(PROJECT_ROOT / "manual-tests" / "g0"), pattern="test_*.py")
    stream = io.StringIO()
    with redirect_stdout(stream), redirect_stderr(stream):
        result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    return {
        "status": "PASS" if result.wasSuccessful() else "FAIL",
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
    }


def _gate(
    gate_id: str,
    name: str,
    check: Callable[[], tuple[bool, dict[str, Any]]],
    *,
    limitation: str | None = None,
) -> dict[str, Any]:
    try:
        passed, evidence = check()
        status = "PASS_WITH_LIMITATIONS" if passed and limitation else "PASS" if passed else "FAIL"
        return {"gate_id": gate_id, "name": name, "status": status, "evidence": evidence, "limitation": limitation}
    except Exception as exc:
        return {
            "gate_id": gate_id, "name": name, "status": "FAIL", "evidence": {},
            "limitation": None, "error": f"{type(exc).__name__}: {exc}",
        }


def _h4_identity() -> tuple[bool, dict[str, Any]]:
    head = _git("rev-parse", "HEAD")
    main = _git("rev-parse", "main")
    origin_main = _git("rev-parse", "origin/main")
    tag_object = _git("rev-parse", "v0.8.0-h4-hardening-checkpoint^{tag}")
    peeled = _git("rev-parse", "v0.8.0-h4-hardening-checkpoint^{}")
    return (
        head == main == origin_main == peeled == EXPECTED_H4 and tag_object == EXPECTED_H4_TAG_OBJECT,
        {"head": head, "main": main, "origin_main": origin_main, "h4_tag_object": tag_object, "h4_peeled": peeled},
    )


def _north_star() -> tuple[bool, dict[str, Any]]:
    rules = (PROJECT_ROOT / "PROJECT_RULES.md").read_text(encoding="utf-8")
    required = ("CHROMA3D PRODUCT NORTH-STAR GATE", "ROADMAP_DRIFT", "generative 3D")
    return all(item in rules for item in required), {"required_phrases": list(required)}


def _registry() -> tuple[bool, dict[str, Any]]:
    rows = registry_matrix(ExecutionPolicy())
    ids = [row["backend_id"] for row in rows]
    complete = set(ids) == {"trellis2", "hunyuan3d_2_1", "tripo", "meshy", "rodin", "fake_generator"}
    strict = all(set(row) >= {field.name for field in BackendDescriptor.__dataclass_fields__.values()} for row in rows)
    provenance = all(row["model_version"] and row["official_sources"] for row in rows)
    return complete and strict and provenance, {
        "backend_ids": ids,
        "registry_hash": stable_hash([{key: value for key, value in row.items() if key != "environment"} for row in rows]),
        "availability": {row["backend_id"]: row["availability_state"] for row in rows},
    }


def _corpus() -> tuple[bool, dict[str, Any]]:
    corpus = read_json(GENERATIVE_ROOT / "corpus" / "manifest.json")
    counts = {
        name: read_json(GENERATIVE_ROOT / "corpus" / f"{name}.json")["case_count"]
        for name in ("smoke3", "core10", "full27")
    }
    passed = (
        corpus["cgb_version"] == CGB_VERSION and corpus["case_count"] == 27
        and corpus["rights_cleared"] is True and corpus["source_immutable"] is True
        and counts == {"smoke3": 3, "core10": 10, "full27": 27}
    )
    return passed, {"counts": counts, "corpus_hash": corpus["corpus_hash"], "rendered_case_count": corpus["rendered_case_count"]}


def _renderer() -> tuple[bool, dict[str, Any]]:
    index = read_json(VALIDATION_ROOT / "reference-renders" / "index.json")
    coverage = [
        view["foreground_fraction"]
        for case in index["cases"].values()
        for view in case["views"].values()
    ]
    passed = (
        index["case_count"] == 3 and index["render_count"] == 12
        and index["determinism_check"] == "PASS" and index["source_mutation_count"] == 0
        and all(value > 0 for value in coverage)
    )
    return passed, {
        "renderer_version": index["renderer_version"], "blender_version": index["blender_version"],
        "render_config_hash": index["render_config_hash"], "case_count": index["case_count"],
        "render_count": index["render_count"], "determinism": index["determinism_check"],
        "minimum_foreground_fraction": min(coverage),
    }


def _source_identity() -> tuple[bool, dict[str, Any]]:
    corpus = read_json(GENERATIVE_ROOT / "corpus" / "manifest.json")
    mismatches = []
    for case in corpus["cases"]:
        source = PROJECT_ROOT / case["source_storage_hint"]
        if not source.is_file() or sha256_file(source) != case["source_sha256"]:
            mismatches.append(case["case_id"])
    return not mismatches, {"checked": len(corpus["cases"]), "mismatches": mismatches, "source_mutation_count": len(mismatches)}


def _backend_contract() -> tuple[bool, dict[str, Any]]:
    required = {"backend_info", "validate_environment", "estimate_cost", "submit", "poll", "cancel", "retrieve", "normalize_metadata"}
    present = {name for name in required if callable(getattr(GenerationBackend, name, None))}
    return present == required, {"methods": sorted(present), "fake_backend": "fake_generator" in backend_registry(ExecutionPolicy())}


def _cost_guards() -> tuple[bool, dict[str, Any]]:
    policy = ExecutionPolicy()
    evidence = policy.to_dict()
    passed = evidence == {
        "max_spend_usd": "0", "max_live_jobs": 0,
        "allow_model_downloads": False, "allow_cloud_gpu": False,
        "allow_live_provider_calls": False, "allow_unknown_cost": False,
    }
    return passed, evidence


def _hardware() -> tuple[bool, dict[str, Any]]:
    rows = {row["backend_id"]: row for row in registry_matrix(ExecutionPolicy())}
    open_rows = {key: rows[key] for key in ("trellis2", "hunyuan3d_2_1")}
    allowed = {"READY_LOCAL", "NOT_INSTALLED", "WEIGHTS_NOT_PRESENT", "INSUFFICIENT_HARDWARE", "UNSUPPORTED_PLATFORM", "CLOUD_RECOMMENDED"}
    return all(row["availability_state"] in allowed for row in open_rows.values()), {
        key: {
            "availability_state": value["availability_state"],
            "feasibility": value["environment"]["feasibility"],
            "gpu": value["environment"]["gpu"],
            "checkpoint_present": value["environment"]["checkpoint_present"],
        }
        for key, value in open_rows.items()
    }


def _current_run() -> dict[str, Any]:
    return read_json(VALIDATION_ROOT / "runs" / "fake-smoke3-current" / "run.json")


def _raw_artifacts() -> tuple[bool, dict[str, Any]]:
    root = VALIDATION_ROOT / "runs" / "fake-smoke3-current"
    attempts = _current_run()["attempts"]
    failures = []
    for record in attempts:
        path = root / record["raw_artifact_path"]
        if not path.is_file() or sha256_file(path) != record["raw_artifact_sha256"]:
            failures.append(record["case_id"])
    return not failures and len(attempts) == 3, {"artifact_count": len(attempts), "hash_failures": failures}


def _metric_gate(section: str, required: tuple[str, ...]) -> tuple[bool, dict[str, Any]]:
    attempts = _current_run()["attempts"]
    missing = []
    for record in attempts:
        value = record.get("raw_metrics", {}).get(section, {})
        if not all(key in value for key in required):
            missing.append(record["case_id"])
    return not missing and len(attempts) == 3, {"attempts": len(attempts), "missing": missing, "required": list(required)}


def _conditioning() -> tuple[bool, dict[str, Any]]:
    retained = read_json(VALIDATION_ROOT / "runs" / "fake-smoke3" / "run.json")
    attempts = retained["attempts"]
    passed = all(
        record.get("conditioning", {}).get("status") == "PASS"
        and record.get("conditioning", {}).get("source_immutable") is True
        and isinstance(record.get("conditioning_fidelity_drift"), (int, float))
        for record in attempts
    )
    return passed and len(attempts) == 3, {
        "conditioned_attempts": len(attempts),
        "statuses": {record["case_id"]: record.get("conditioning", {}).get("status") for record in attempts},
        "source_mutation_count": retained["source_mutation_count"],
    }


def _operational() -> tuple[bool, dict[str, Any]]:
    run = _current_run()
    present = all(
        isinstance(record.get("latency", {}).get("end_to_end_seconds"), (int, float))
        and record.get("cost_state") == "KNOWN"
        and record.get("credits") == 0
        for record in run["attempts"]
    )
    return present, {
        "attempts": run["attempt_count"], "successes": run["success_count"],
        "elapsed_seconds": run["elapsed_seconds"], "api_spend_usd": run["api_spend_usd"],
    }


def _cache() -> tuple[bool, dict[str, Any]]:
    records = _current_run()["attempts"]
    required = {"artifact_sha256", "evaluator_version", "evaluation_settings_hash", "evaluation_cache_key"}
    passed = all(
        set(record.get("evaluation_cache_identity", {})) == required
        and record["cache_identity"]["evaluator_version"] == record["evaluation_cache_identity"]["evaluator_version"]
        for record in records
    )
    return passed, {"attempts": len(records), "evaluation_identity_bound": passed}


def _report() -> tuple[bool, dict[str, Any]]:
    result = read_json(VALIDATION_ROOT / "runs" / "fake-smoke3-current" / "result.json")
    passed = (
        result["primary_truth"] == "RAW_DIMENSIONS_AND_STATUSES"
        and result["no_model_winner_declared"] is True
        and result["winner_declarations"] == {}
        and result["pareto_frontier"] == []
    )
    return passed, {
        "decision": result["decision"], "scorecards": len(result["scorecards"]),
        "pareto_real_backends": result["pareto_frontier"], "no_model_winner_declared": result["no_model_winner_declared"],
    }


def _fake_e2e() -> tuple[bool, dict[str, Any]]:
    run = _current_run()
    passed = run["status"] == "PASS" and run["attempt_count"] == run["success_count"] == 3 and run["source_mutation_count"] == 0
    return passed, {
        "status": run["status"], "attempts": run["attempt_count"], "successes": run["success_count"],
        "run_hash": run["run_hash"], "source_mutation_count": run["source_mutation_count"],
    }


def _package() -> tuple[bool, dict[str, Any]]:
    package = _project.PACKAGE_PATH
    with zipfile.ZipFile(package) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
    forbidden_roots = ("benchmarks/", "manual-tests/", "docs/generative/", ".validation-assets/")
    forbidden = [name for name in names if name.startswith(forbidden_roots)]
    return package.is_file() and not forbidden, {
        "package": package.relative_to(PROJECT_ROOT).as_posix(), "file_count": len(names),
        "archive_bytes": package.stat().st_size, "forbidden_entries": forbidden,
    }


def _runtime_scope() -> tuple[bool, dict[str, Any]]:
    changed = _git("diff", "--name-only", "main", "--", "blender_addon", "schemas", "profiles").splitlines()
    metadata = (PROJECT_ROOT / "blender_addon" / "chroma3d_sculpt" / "metadata.py").read_text(encoding="utf-8")
    passed = not changed and 'EXTENSION_VERSION = "0.8.0"' in metadata and 'STAGE_LABEL = "alpha.1"' in metadata
    return passed, {"shipping_files_changed": changed, "product_version": "0.8.0-alpha.1"}


def _no_live() -> tuple[bool, dict[str, Any]]:
    run = _current_run()
    policy = run["policy"]
    passed = (
        run["live_generations"] == 0 and run["live_api_calls"] == 0 and run["api_spend_usd"] == 0
        and run["model_downloads"] == 0 and run["cloud_gpu_usage"] == 0
        and policy["allow_live_provider_calls"] is False and policy["max_spend_usd"] == "0"
    )
    return passed, {
        "live_generations": run["live_generations"], "live_api_calls": run["live_api_calls"],
        "api_spend_usd": run["api_spend_usd"], "model_downloads": run["model_downloads"],
        "cloud_gpu_usage": run["cloud_gpu_usage"],
    }


def _git_scope() -> tuple[bool, dict[str, Any]]:
    branch = _git("branch", "--show-current")
    staged = _git("diff", "--cached", "--name-only").splitlines()
    ahead_behind = _git("rev-list", "--left-right", "--count", "main...HEAD")
    upstream = _git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", check=False)
    status_lines = _git("status", "--porcelain=v1", "-uall").splitlines()
    status_paths = [line[3:].replace("\\", "/") for line in status_lines]
    unexpected = [path for path in status_paths if not path.startswith(ALLOWED_STATUS_ROOTS)]
    remote_branch = _git("ls-remote", "--heads", "origin", f"refs/heads/{EXPECTED_BRANCH}")
    local_g0_tags = _git("tag", "--list", "*g0*").splitlines()
    remote_g0_tags = _git("ls-remote", "--tags", "origin", "*g0*").splitlines()
    recovery = {}
    recovery_ok = True
    remote_tags = _git("ls-remote", "--tags", "origin", *[f"refs/tags/{tag}*" for tag in RECOVERY_TAGS]).splitlines()
    remote_lookup = {line.split("\t", 1)[1]: line.split("\t", 1)[0] for line in remote_tags if "\t" in line}
    for tag in RECOVERY_TAGS:
        local_object = _git("rev-parse", f"{tag}^{{tag}}")
        local_peeled = _git("rev-parse", f"{tag}^{{}}")
        remote_object = remote_lookup.get(f"refs/tags/{tag}")
        remote_peeled = remote_lookup.get(f"refs/tags/{tag}^{{}}")
        matches = local_object == remote_object and local_peeled == remote_peeled
        recovery[tag] = {"object": local_object, "peeled": local_peeled, "matches_remote": matches}
        recovery_ok = recovery_ok and matches
    passed = (
        branch == EXPECTED_BRANCH and not staged and ahead_behind == "0\t0" and not upstream
        and not unexpected and not remote_branch and not local_g0_tags and not remote_g0_tags
        and _git("rev-parse", "main") == _git("rev-parse", "origin/main") == EXPECTED_H4
        and recovery_ok and not _git("diff", "--check")
    )
    return passed, {
        "branch": branch, "staged": staged, "ahead_behind_main": ahead_behind,
        "upstream": upstream or None, "status_paths": status_paths, "unexpected_paths": unexpected,
        "remote_g0_branch": bool(remote_branch), "g0_tags": local_g0_tags + remote_g0_tags,
        "main": _git("rev-parse", "main"), "origin_main": _git("rev-parse", "origin/main"),
        "recovery_tags": recovery,
    }


def main() -> int:
    unit = _run_unit_tests()
    gates = [
        _gate("G0-01", "H4 frozen starting identity", _h4_identity),
        _gate("G0-02", "Product north-star gate", _north_star),
        _gate("G0-03", "Official backend registry/provenance", _registry),
        _gate("G0-04", "Rights-cleared corpus manifest", _corpus),
        _gate("G0-05", "Reference renderer", _renderer, limitation="Smoke3 rendered; Core10 and Full27 remain staged and NOT_RUN."),
        _gate("G0-06", "Source immutability", _source_identity),
        _gate("G0-07", "Backend abstraction", _backend_contract),
        _gate("G0-08", "Commercial cost/live-call guards", _cost_guards),
        _gate("G0-09", "Open-model feasibility detection", _hardware, limitation="No weights downloaded or local model inference executed."),
        _gate("G0-10", "Raw artifact preservation", _raw_artifacts),
        _gate("G0-11", "Geometry evaluation", lambda: _metric_gate("raw_geometry", ("vertex_count", "triangle_count", "boundary_edges", "geometry_health_score"))),
        _gate("G0-12", "Ground-truth fidelity", lambda: _metric_gate("shape_fidelity", ("normalized_symmetric_chamfer", "f_score", "normal_consistency", "bounding_box_proportion_error"))),
        _gate("G0-13", "Silhouette evaluation", lambda: _metric_gate("silhouette", ("views", "mean_iou", "worst_view_iou"))),
        _gate("G0-14", "Conditioning uplift", _conditioning, limitation="Conditioning evidence predates the render-hash-only corpus refresh; source geometry identities are unchanged."),
        _gate("G0-15", "Operational metrics", _operational, limitation="Operational evidence is offline fake-backend only; real provider reliability/cost is NOT_RUN."),
        _gate("G0-16", "Resume/cache identity", _cache),
        _gate("G0-17", "Report/Pareto generation", _report, limitation="No real backend is eligible for Pareto/model ranking."),
        _gate("G0-18", "Fake end-to-end benchmark", _fake_e2e),
        _gate("G0-19", "Package isolation", _package),
        _gate("G0-20", "No product runtime/version/schema/profile modification", _runtime_scope),
        _gate("G0-21", "No unauthorized paid/live generation", _no_live),
        _gate("G0-22", "Final Git/scope safety", _git_scope),
    ]
    if unit["status"] != "PASS":
        gates[6]["status"] = "FAIL"
        gates[6]["error"] = "G0 unit suite failed."
    counts = Counter(gate["status"] for gate in gates)
    overall = "FAIL" if counts["FAIL"] else "PASS_WITH_LIMITATIONS" if counts["PASS_WITH_LIMITATIONS"] else "PASS"
    payload = {
        "schema_version": "1.0.0", "cgb_version": CGB_VERSION,
        "overall_status": overall,
        "decision": "G0_BLOCKED" if counts["FAIL"] else "G0_FRAMEWORK_COMPLETE_READY_FOR_BACKEND_EXECUTION",
        "no_model_winner_declared": True,
        "unit_tests": unit,
        "gate_counts": dict(counts), "gates": gates,
        "human_evaluation": "NOT_RUN",
        "live_generations": 0, "live_api_calls": 0, "api_spend_usd": 0,
        "model_downloads": 0, "cloud_gpu_usage": 0,
        "preserved_failures": [
            ".validation-assets/generative-benchmark/acceptance/first_failure.json",
            ".validation-assets/generative-benchmark/acceptance/render_import_failure.json",
        ],
    }
    payload["acceptance_hash"] = stable_hash(payload)
    output = VALIDATION_ROOT / "acceptance" / "G0_ACCEPTANCE.json"
    write_json(output, payload)
    print(
        f"G0 acceptance {overall}: tests={unit['tests_run']} gates={len(gates)} "
        f"pass={counts['PASS']} limitations={counts['PASS_WITH_LIMITATIONS']} fail={counts['FAIL']} "
        f"decision={payload['decision']} hash={payload['acceptance_hash']}"
    )
    print("NO MODEL WINNER HAS BEEN DECLARED.")
    return 0 if counts["FAIL"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
