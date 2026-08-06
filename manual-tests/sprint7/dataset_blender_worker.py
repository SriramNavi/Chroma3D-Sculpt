"""Run one isolated nondestructive Sprint 7 context and grounding workflow."""

from __future__ import annotations

from datetime import datetime, timezone
import ctypes
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

import bpy

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "blender_addon"
if str(ADDON) not in sys.path:
    sys.path.insert(0, str(ADDON))

from chroma3d_sculpt.ai_assistance_settings import default_assistance_policy, limits_for_mode, policy_for_mode  # noqa: E402
from chroma3d_sculpt.models.ai_assistance_models import ConfidenceClassification, EvidenceReference, EvidenceState, stable_hash  # noqa: E402
from chroma3d_sculpt.models.intelligent_optimization_models import SearchMode  # noqa: E402
from chroma3d_sculpt.services.ai_recommendation import validate_provider_recommendations  # noqa: E402
from chroma3d_sculpt.services.assistance_context import build_context_manifest  # noqa: E402
from chroma3d_sculpt.services.optimization_candidates import generate_candidates  # noqa: E402
from chroma3d_sculpt.services.recommendation_resolver import describe_strategy  # noqa: E402
from chroma3d_sculpt.services.search_policy import default_search_policy  # noqa: E402
from chroma3d_sculpt.services.strategy_generator import generate_strategies  # noqa: E402
from chroma3d_sculpt.utilities.optimization_signatures import source_signature  # noqa: E402


class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = (
        ("cb", ctypes.c_ulong), ("page_fault_count", ctypes.c_ulong),
        ("peak_working_set_size", ctypes.c_size_t), ("working_set_size", ctypes.c_size_t),
        ("quota_peak_paged_pool_usage", ctypes.c_size_t), ("quota_paged_pool_usage", ctypes.c_size_t),
        ("quota_peak_non_paged_pool_usage", ctypes.c_size_t), ("quota_non_paged_pool_usage", ctypes.c_size_t),
        ("pagefile_usage", ctypes.c_size_t), ("peak_pagefile_usage", ctypes.c_size_t),
    )


def _point_working_set_bytes() -> int | None:
    counters = _ProcessMemoryCounters(); counters.cb = ctypes.sizeof(counters)
    try:
        ctypes.windll.kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = (ctypes.c_void_p, ctypes.POINTER(_ProcessMemoryCounters), ctypes.c_ulong)
        ctypes.windll.psapi.GetProcessMemoryInfo.restype = ctypes.c_int
        process = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb):
            return int(counters.working_set_size)
    except (AttributeError, OSError):
        return None
    return None


def _arguments() -> dict[str, str]:
    values = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return {values[index]: values[index + 1] for index in range(0, len(values) - 1, 2) if values[index].startswith("--")}


def _import_source(path: Path):
    if path.suffix.lower() == ".stl": bpy.ops.wm.stl_import(filepath=str(path))
    elif path.suffix.lower() == ".obj": bpy.ops.wm.obj_import(filepath=str(path))
    elif path.suffix.lower() == ".ply": bpy.ops.wm.ply_import(filepath=str(path))
    else: raise ValueError("Unsupported dataset asset type.")
    source = bpy.context.object
    if source is None or source.type != "MESH": raise RuntimeError("Dataset import did not create an active mesh.")
    return source


def main() -> int:
    args = _arguments(); model_id = args["--model-id"]; source_path = Path(args["--source"]); output = Path(args["--output"])
    implementation_fingerprint = args["--implementation-fingerprint"]
    started = perf_counter()
    for item in tuple(bpy.data.objects): bpy.data.objects.remove(item, do_unlink=True)
    source = _import_source(source_path)
    before = source_signature(source)["source_signature"]
    candidates = generate_candidates(None, source_snapshot={"source_signature": before})
    strategy_set = generate_strategies(candidates, policy=default_search_policy(SearchMode.FAST), source_signature=before)
    policy = policy_for_mode(default_assistance_policy(enabled=True), "FAST")
    strategies = tuple(item for item in strategy_set.strategies if all(step.operation in policy.allowed_operations for step in item.steps))[: policy.maximum_strategies]
    if not strategies: raise RuntimeError("No safe-default deterministic strategy was generated.")
    target = describe_strategy(strategies[0], source_signature=before, feasible=True)
    evidence_id = f"dataset-source:{model_id}"
    evidence = EvidenceReference(evidence_id, "DATASET_SOURCE_IDENTITY", EvidenceState.PASS, ConfidenceClassification.MEDIUM, stable_hash({"model_id": model_id, "source_signature": before}), ("Permissioned Sprint dataset",), ("Identity and bounded local strategy evidence only.",), False)
    context = build_context_manifest(
        source_signature_hash=before, object_display_name=model_id, policy=policy, limits=limits_for_mode("FAST"),
        user_goal="Review current deterministic optimization trade-offs.", evidence=(evidence,),
        candidate_ids=tuple(item.candidate_id for item in candidates), strategy_ids=tuple(item.strategy_id for item in strategies),
        ranking_information=tuple({"strategy_id": item.strategy_id, "rank": index} for index, item in enumerate(strategies, 1)),
        summaries={"performance_mode": "FAST", "diagnostic_counts": {"triangles": len(source.data.polygons)}},
        consent_approved=True, consent_timestamp="2026-08-06T00:00:00+00:00",
    )
    response = {"recommendations": [{
        "recommendation_type": "SELECT_EXISTING_STRATEGY", "target_id": target.target_id,
        "target_fingerprint": target.fingerprint, "alternative_ids": [], "reason_codes": ["CURRENT_LOCAL_STRATEGY"],
        "reason": "The target is an existing current deterministic strategy.", "assumptions": ["The current Sprint 6 evidence remains unchanged."], "trade_offs": ["Review local comparison evidence before approval."],
        "evidence_references": [evidence_id], "confidence_hint": "MEDIUM", "unmet_prerequisites": [],
        "limitations": ["Fake-provider fixture; no external request or physical claim."], "operation_echo": list(target.operations),
    }], "overall_limitations": ["Software-only nondestructive dataset validation."]}
    recommendations = validate_provider_recommendations(json.dumps(response, sort_keys=True), context=context, registry={target.target_id: target}, policy=policy, limits=limits_for_mode("FAST"))
    repeated = build_context_manifest(
        source_signature_hash=before, object_display_name=model_id, policy=policy, limits=limits_for_mode("FAST"),
        user_goal="Review current deterministic optimization trade-offs.", evidence=(evidence,),
        candidate_ids=tuple(item.candidate_id for item in candidates), strategy_ids=tuple(item.strategy_id for item in strategies),
        ranking_information=tuple({"strategy_id": item.strategy_id, "rank": index} for index, item in enumerate(strategies, 1)),
        summaries={"performance_mode": "FAST", "diagnostic_counts": {"triangles": len(source.data.polygons)}},
        consent_approved=True, consent_timestamp="2026-08-06T00:00:00+00:00",
    )
    after = source_signature(source)["source_signature"]
    payload = {
        "schema_version": "1.0.0", "model_id": model_id, "status": "PASS" if before == after and recommendations[0].action_available else "FAIL",
        "source_file_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(), "source_signature_before": before, "source_signature_after": after,
        "source_immutability": before == after, "geometry_elements_exported": context.geometry_elements_exported,
        "context_hash": context.context_hash, "repeat_context_hash": repeated.context_hash, "deterministic_context": context.context_hash == repeated.context_hash,
        "context_bytes": context.byte_count, "evidence_count": len(context.evidence), "candidate_count": len(candidates), "strategy_count": len(strategies),
        "recommendation_id": recommendations[0].recommendation_id, "resolved_target_id": recommendations[0].target_id,
        "provider": "FAKE_RECORDED_FIXTURE", "live_provider_calls": 0, "credential_present": False,
        "implementation_fingerprint": implementation_fingerprint,
        "dataset_manifest_sha256": args["--dataset-manifest-sha256"],
        "profile_context_sha256": args["--profile-context-sha256"],
        "validation_mode": args["--validation-mode"], "worker_version": args["--worker-version"],
        "performance_limits_hash": stable_hash(limits_for_mode("FAST").to_dict()),
        "elapsed_seconds": round(perf_counter() - started, 6),
        "point_memory_observation": {"metric": "WORKING_SET_BYTES", "value": _point_working_set_bytes(), "sampling": "single point at worker completion", "peak_claim": False},
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "limitations": ["Nondestructive context/grounding only; no slicer, physical print, live provider, cultural or geometry-correctness claim."],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__": raise SystemExit(main())
