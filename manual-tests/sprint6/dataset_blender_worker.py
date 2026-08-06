"""Import one immutable model and run the real bounded Sprint 6 workflow."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

import bpy

ROOT = Path(__file__).resolve().parents[2]
ADDON_ROOT = ROOT / "blender_addon"
if str(ADDON_ROOT) not in sys.path:
    sys.path.insert(0, str(ADDON_ROOT))

import chroma3d_sculpt  # noqa: E402
from chroma3d_sculpt.models.intelligent_optimization_models import SearchMode  # noqa: E402
from chroma3d_sculpt.services.intelligent_optimization_coordinator import (  # noqa: E402
    build_intelligent_frontier, discard_intelligent_workspace, evaluate_intelligent_strategies,
    execute_selected_strategy, generate_intelligent_strategies, rank_intelligent_strategies,
    select_strategy,
)
from chroma3d_sculpt.services.optimization_coordinator import restore_session_to_start  # noqa: E402
from chroma3d_sculpt.services.intelligent_optimization_session import (  # noqa: E402
    clear_runtime, current_objective_profile, current_search_policy, get_active_session,
    get_controlled_session, start_intelligent_session,
)
from chroma3d_sculpt.services.search_policy import default_search_policy  # noqa: E402
from chroma3d_sculpt.models.intelligent_optimization_models import stable_hash  # noqa: E402
from chroma3d_sculpt.utilities.optimization_signatures import source_signature  # noqa: E402


def _args() -> dict[str, str]:
    values = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return {values[index]: values[index + 1] for index in range(0, len(values) - 1, 2) if values[index].startswith("--")}


def _import_source(path: Path) -> object:
    suffix = path.suffix.lower()
    if suffix == ".stl":
        bpy.ops.wm.stl_import(filepath=str(path))
    elif suffix == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    elif suffix == ".ply":
        bpy.ops.wm.ply_import(filepath=str(path))
    else:
        raise ValueError(f"Unsupported dataset extension: {suffix}")
    source = bpy.context.object
    if source is None or source.type != "MESH":
        raise RuntimeError("Dataset import did not produce an active mesh object.")
    return source


def main() -> int:
    arguments = _args()
    model_id = arguments["--model-id"]
    source_path = Path(arguments["--source"]).resolve()
    output = Path(arguments["--output"])
    mode = arguments.get("--mode", "full-nondestructive")
    started = perf_counter()
    clear_runtime()
    for obj in tuple(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    chroma3d_sculpt.register()
    try:
        source = _import_source(source_path)
        before = source_signature(source)["source_signature"]
        policy = default_search_policy(SearchMode.FAST)
        start_intelligent_session(
            source, bpy.context.scene, policy=policy,
            process_context_hash=stable_hash({"model_id": model_id, "blender": bpy.app.version_string}),
            hardware_profile_hash=stable_hash("default-hardware-profile"),
            material_profile_hash=stable_hash("default-material-profile"),
            feature_flag_hash=stable_hash("default-feature-flags"),
        )
        generated = generate_intelligent_strategies(source=source)
        facts = {"triangle_count": len(source.data.polygons) * 2, "height": float(source.dimensions.z), "build_volume_fit": 1.0, "geometry_fidelity": 1.0, "fidelity_status": "PASS", "critical_defect_introduced": False, "geometric_deviation": 0.0, "area_drift": 0.0, "volume_drift": 0.0}
        evaluations = evaluate_intelligent_strategies(baseline_values=facts, source=source)
        frontier = build_intelligent_frontier()
        rankings = rank_intelligent_strategies()
        selected = rankings[0].strategy_id if rankings else ""
        executed = 0
        if selected:
            select_strategy(selected, allow_dominated=True)
            if mode == "representative-mutation":
                records = execute_selected_strategy(source=source, strategy_id=selected, approved=True)
                executed = len(records)
                restore_session_to_start(get_controlled_session(), source)
        after = source_signature(source)["source_signature"]
        if after != before:
            raise RuntimeError("Protected source signature changed during dataset workflow.")
        session = get_active_session()
        ranking_hash = stable_hash(tuple(item.to_dict() for item in rankings))
        result = {
            "schema_version": "1.0", "model_id": model_id, "status": "PASS", "workflow_mode": mode,
            "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(), "source_signature": before, "source_signature_after": after, "source_immutability": after == before,
            "blender_version": bpy.app.version_string, "hardware_profile_hash": session.hardware_profile_hash, "material_profile_hash": session.material_profile_hash, "process_context_hash": session.process_context_hash, "feature_flag_hash": session.feature_flag_hash, "performance_registry_version": session.performance_registry_version,
            "sprint5_policy_hash": session.sprint5_policy_hash, "sprint5_candidate_set_hash": stable_hash([item.to_dict() for item in get_controlled_session().candidates]), "sprint6_policy_hash": session.search_policy_hash, "constraint_set_hash": session.constraint_set_hash, "objective_hash": session.objective_profile_hash,
            "strategy_set_hash": session.strategy_set_hash, "frontier_hash": session.pareto_frontier_hash, "ranking_hash": ranking_hash, "generated_count": len(generated.strategies), "feasible_count": sum(item.feasible for item in evaluations), "pruned_count": len(generated.pruned), "evaluated_count": len(evaluations), "frontier_count": len(frontier.points), "recommended_strategy_id": selected, "ranking_method": current_search_policy().ranking_method, "budget_usage": session.budget_usage.to_dict(), "skipped_states": sorted({key for item in evaluations for key in item.skipped_evidence + item.indeterminate_evidence}), "operation_families": sorted({step.operation for item in generated.strategies for step in item.steps}), "executed_steps": executed, "timing_seconds": round(perf_counter() - started, 6), "memory_observation": "NOT_CAPTURED_BY_WORKER",
            "limitations": ["Bounded local strategy evidence; no physical print, slicer, or global-optimum claim."], "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        discard_intelligent_workspace()
    finally:
        clear_runtime()
        for obj in tuple(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        chroma3d_sculpt.unregister()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
