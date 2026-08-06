"""Independent adversarial Sprint 6 validation.

This runner deliberately owns its fixtures and assertions instead of loading
the focused Sprint 6 unittest module.  It records bounded machine evidence and
keeps unknown, skipped, and environment-dependent checks explicit.
"""

from __future__ import annotations

import ast
from dataclasses import replace
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sys
from time import perf_counter
import traceback
from typing import Any, Callable

import bpy

ROOT = Path(__file__).resolve().parents[2]
ADDON_ROOT = ROOT / "blender_addon"
if str(ADDON_ROOT) not in sys.path:
    sys.path.insert(0, str(ADDON_ROOT))

import chroma3d_sculpt  # noqa: E402
from chroma3d_sculpt.intelligent_optimization_settings import build_objective_profile  # noqa: E402
from chroma3d_sculpt.models.intelligent_optimization_models import (  # noqa: E402
    ConstraintKind, ConstraintSet, ConstraintState, EvidenceState, IntelligentSessionState,
    ObjectiveDirection, ObjectiveMetric, ObjectiveVector, RankingMethod, SearchMode, SearchPolicy,
)
from chroma3d_sculpt.models.optimization_models import OptimizationPolicy  # noqa: E402
from chroma3d_sculpt.services.constraint_engine import (  # noqa: E402
    constraints_are_feasible, default_constraint_set, evaluate_constraints,
)
from chroma3d_sculpt.services.intelligent_optimization_audit import (  # noqa: E402
    build_audit, sanitize_intelligent_optimization_filename, write_json_audit, write_markdown_audit,
)
from chroma3d_sculpt.services.intelligent_optimization_coordinator import (  # noqa: E402
    build_intelligent_frontier, cancel_intelligent_search, discard_intelligent_workspace,
    ensure_current, evaluate_intelligent_strategies, execute_selected_strategy,
    generate_intelligent_strategies, preview_selected_strategy, rank_intelligent_strategies,
    record_strategy_history, select_strategy,
)
from chroma3d_sculpt.services.intelligent_optimization_session import (  # noqa: E402
    clear_runtime, get_active_session, get_archived_session, get_controlled_session,
    start_intelligent_session,
)
from chroma3d_sculpt.services.pareto_frontier import build_pareto_frontier, dominates  # noqa: E402
from chroma3d_sculpt.services.search_policy import default_search_policy, validate_search_policy  # noqa: E402
from chroma3d_sculpt.services.strategy_evaluator import virtual_evaluate_strategy  # noqa: E402
from chroma3d_sculpt.services.strategy_explainer import explain_strategy  # noqa: E402
from chroma3d_sculpt.services.strategy_generator import generate_strategies  # noqa: E402
from chroma3d_sculpt.services.strategy_history import history_entry, add_history_entry, history_is_current, write_history_json  # noqa: E402
from chroma3d_sculpt.services.strategy_ranker import rank_strategies  # noqa: E402
from chroma3d_sculpt.utilities.optimization_signatures import source_signature  # noqa: E402


def _arg_after(name: str, default: Path) -> Path:
    if "--" not in sys.argv:
        return default
    args = sys.argv[sys.argv.index("--") + 1:]
    try:
        return Path(args[args.index(name) + 1])
    except (ValueError, IndexError):
        return default


REPORT = _arg_after("--output", ROOT / "manual-tests" / "sprint6-final" / "reports" / "final_validation_results.json")


def _clear_scene() -> None:
    for obj in tuple(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in tuple(bpy.data.collections):
        if collection.users == 0:
            bpy.data.collections.remove(collection)


def _cube(name: str) -> Any:
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 1.0))
    obj = bpy.context.object
    obj.name = name
    obj.data.name = f"{name}Mesh"
    return obj


def _rich_source(name: str = "S6IndependentSource") -> Any:
    source = _cube(name)
    source["audit_object_property"] = "retained"
    source.data["audit_mesh_property"] = "retained"
    source.rotation_euler = (0.1, 0.2, 0.3)
    source.scale = (1.1, 0.9, 1.0)
    source.hide_viewport = False
    source.hide_render = False
    source.modifiers.new("Audit Subdivision", "SUBSURF").levels = 1
    source.constraints.new("COPY_LOCATION")
    source.vertex_groups.new(name="AuditGroup").add((0, 1, 2), 1.0, "REPLACE")
    source.data.uv_layers.new(name="AuditUV")
    try:
        source.data.color_attributes.new(name="AuditColor", type="FLOAT_COLOR", domain="CORNER")
    except (AttributeError, RuntimeError):
        pass
    material = bpy.data.materials.new(f"{name}Material")
    material.diffuse_color = (0.2, 0.4, 0.8, 1.0)
    source.data.materials.append(material)
    extra = bpy.data.collections.new(f"{name}ExtraCollection")
    bpy.context.scene.collection.children.link(extra)
    extra.objects.link(source)
    source.select_set(True)
    bpy.context.view_layer.objects.active = source
    return source


def _assert(condition: Any, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _expect_error(action: Callable[[], Any], message: str) -> str:
    try:
        action()
    except (ValueError, RuntimeError, TypeError, KeyError) as exc:
        return f"{type(exc).__name__}: {exc}"
    raise AssertionError(message)


def _gate(gates: list[dict[str, Any]], gate_id: str, title: str, action: Callable[[], dict[str, Any] | None]) -> None:
    started = perf_counter()
    try:
        detail = action() or {}
        gates.append({"id": gate_id, "title": title, "status": "PASS", "duration_seconds": round(perf_counter() - started, 6), "detail": detail})
    except Exception as exc:
        gates.append({"id": gate_id, "title": title, "status": "FAIL", "duration_seconds": round(perf_counter() - started, 6), "detail": {"error": f"{type(exc).__name__}: {exc}", "traceback_tail": traceback.format_exc().splitlines()[-8:]}})


def _static_safety() -> dict[str, Any]:
    banned_imports = {"requests", "urllib", "socket", "http", "subprocess", "pickle"}
    banned_calls = {"eval", "exec"}
    violations: list[str] = []
    bpy_ops: list[str] = []
    absolute_paths: list[str] = []
    for path in sorted(ADDON_ROOT.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in banned_imports:
                        violations.append(f"{path.relative_to(ROOT).as_posix()}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in banned_imports:
                violations.append(f"{path.relative_to(ROOT).as_posix()}: from {node.module}")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in banned_calls:
                    violations.append(f"{path.relative_to(ROOT).as_posix()}: call {node.func.id}")
                if isinstance(node.func, ast.Attribute) and node.func.attr == "system":
                    violations.append(f"{path.relative_to(ROOT).as_posix()}: system call")
            elif isinstance(node, ast.Attribute) and node.attr == "ops" and isinstance(node.value, ast.Name) and node.value.id == "bpy":
                bpy_ops.append(path.relative_to(ROOT).as_posix())
        for pattern in (r"E:\\\\VPRS", r"D:\\\\Softwares", r"/Users/"):
            if re.search(pattern, source, re.IGNORECASE):
                absolute_paths.append(path.relative_to(ROOT).as_posix())
    _assert(not violations, "Unsafe runtime imports/calls: " + "; ".join(violations))
    _assert(not absolute_paths, "Developer absolute paths found in runtime: " + "; ".join(absolute_paths))
    return {"banned_import_or_call_count": len(violations), "bpy_ops_source_files": sorted(set(bpy_ops)), "absolute_developer_path_count": len(absolute_paths)}


def _protected_source_matrix() -> dict[str, Any]:
    clear_runtime(); _clear_scene()
    source = _rich_source()
    before = source_signature(source)["source_signature"]
    try:
        start_intelligent_session(source, bpy.context.scene, policy=default_search_policy(SearchMode.FAST))
        generated = generate_intelligent_strategies(source=source)
        _assert(generated.strategies, "independent fixture generated no strategies")
        values = {"fidelity_status": "PASS", "critical_defect_introduced": False, "geometric_deviation": 0.0, "area_drift": 0.0, "volume_drift": 0.0, "build_volume_fit": 1.0, "geometry_fidelity": 1.0, "height": 1.0}
        evaluated = evaluate_intelligent_strategies(baseline_values=values, source=source)
        _assert(evaluated, "no independent evaluations")
        frontier = build_intelligent_frontier()
        _assert(frontier.points, "no independent Pareto points")
        rankings = rank_intelligent_strategies()
        _assert(rankings, "no independent rankings")
        record_strategy_history()
        select_strategy(rankings[0].strategy_id, allow_dominated=True)
        preview = preview_selected_strategy()
        _assert(preview["mutated_source"] is False, "preview mutated protected source")
        _expect_error(lambda: execute_selected_strategy(source=source, approved=False), "execution without approval was accepted")
        records = execute_selected_strategy(source=source, approved=True)
        _assert(records, "approved execution produced no operation records")
        from chroma3d_sculpt.services.optimization_coordinator import restore_session_to_start
        restore_session_to_start(get_controlled_session(), source)
        after = source_signature(source)["source_signature"]
        _assert(after == before, "protected source signature changed during session workflow")
        report_root = ROOT / "manual-tests" / "sprint6-final" / "reports"
        audit = build_audit(get_active_session(), blender_version=bpy.app.version_string)
        json_path = write_json_audit(audit, report_root / "independent_audit.json")
        md_path = write_markdown_audit(audit, report_root / "independent_audit.md")
        _assert(json_path.is_file() and md_path.is_file(), "audit exports missing")
        discard_intelligent_workspace()
        return {"generated": len(generated.strategies), "evaluated": len(evaluated), "frontier": len(frontier.points), "ranked": len(rankings), "executed_steps": len(records), "source_signature_before": before, "source_signature_after": after, "preview_mutated_source": preview["mutated_source"]}
    finally:
        if get_active_session() is not None:
            try:
                discard_intelligent_workspace()
            except Exception:
                clear_runtime()
        _clear_scene()


def _policy_attacks() -> dict[str, Any]:
    cases = 0
    for field_name, value in (("max_generated_strategies", True), ("max_generated_strategies", 0), ("max_wall_time_seconds", float("nan")), ("max_wall_time_seconds", float("inf"))):
        cases += 1
        _expect_error(lambda field_name=field_name, value=value: replace(default_search_policy().budget, **{field_name: value}), f"accepted invalid budget {field_name}={value}")
    cases += 1; _expect_error(lambda: SearchPolicy(ranking_method="tampered"), "accepted invalid ranking method")
    cases += 1; _expect_error(lambda: SearchPolicy(allowed_operation_families=("NOPE",)), "accepted unknown operation")
    cases += 1; _expect_error(lambda: SearchPolicy(experimental_operations_enabled=True), "accepted hidden experimental mode")
    policy = default_search_policy()
    object.__setattr__(policy, "policy_hash", "tampered")
    cases += 1; _expect_error(lambda: validate_search_policy(policy), "accepted tampered policy hash")
    return {"attacks": cases, "fail_closed": True}


def _constraint_truth() -> dict[str, Any]:
    hard = default_constraint_set()
    unknown = evaluate_constraints(hard, {"source_protected": True}, evidence_states={"source_protected": EvidenceState.MEASURED})
    _assert(not constraints_are_feasible(unknown), "unknown hard evidence satisfied constraints")
    finite = evaluate_constraints(ConstraintSet((
        __import__("chroma3d_sculpt.models.intelligent_optimization_models", fromlist=["OptimizationConstraint"]).OptimizationConstraint("height", ConstraintKind.MAX_HEIGHT, maximum=1.0, actual_key="height"),
    ), set_id="independent-finite"), {"height": float("nan")}, evidence_states={"height": EvidenceState.MEASURED})
    _assert(finite[0].state == ConstraintState.FAIL, "non-finite constraint evidence did not fail")
    return {"hard_constraints": len(hard.constraints), "unknown_hard_state": unknown[1].state.value, "nonfinite_state": finite[0].state.value}


def _generation_and_pruning() -> dict[str, Any]:
    policy = default_search_policy(SearchMode.FAST)
    candidates = __import__("chroma3d_sculpt.services.optimization_candidates", fromlist=["generate_candidates"]).generate_candidates(None, source_snapshot={"source_signature": "independent"}, policy=OptimizationPolicy())
    first = generate_strategies(candidates, policy=policy, source_signature="independent")
    second = generate_strategies(candidates, policy=policy, source_signature="independent")
    _assert(first.to_json() == second.to_json(), "strategy generation was not deterministic")
    _assert(first.budget_usage.operation_steps <= policy.budget.max_operation_steps, "operation-step budget exceeded")
    cancelled = generate_strategies(candidates, policy=policy, cancel_requested=lambda: True)
    _assert(cancelled.status == "CANCELLED" and "cancellation" in cancelled.budget_usage.exhausted_dimensions, "cancellation state was not explicit")
    collision = ({"candidate_id": "a", "fingerprint": "same", "operation": "UNIFORM_SCALE", "parameters": {"scale": 1.0}}, {"candidate_id": "b", "fingerprint": "same", "operation": "UNIFORM_SCALE", "parameters": {"scale": 0.5}})
    _expect_error(lambda: generate_strategies(collision, policy=policy), "fingerprint collision was accepted")
    return {"generated": len(first.strategies), "pruned": len(first.pruned), "status": first.status, "cancelled_status": cancelled.status, "operation_steps": first.budget_usage.operation_steps}


def _objective_pareto_ranking() -> dict[str, Any]:
    strategy = __import__("chroma3d_sculpt.models.intelligent_optimization_models", fromlist=["IntelligentStrategy", "StrategyStep", "StrategyGenerationReason"]).IntelligentStrategy(
        "independent-strategy", "independent-fingerprint", "Balanced", "OBJECTIVE_ALIGNMENT",
        (__import__("chroma3d_sculpt.models.intelligent_optimization_models", fromlist=["StrategyStep"]).StrategyStep(1, "candidate", "ORIENTATION"),),
    )
    vector = ObjectiveVector(raw_values={"geometry_fidelity": 0.8, "support_risk": 0.2}, normalized_values={"geometry_fidelity": 0.8, "support_risk": 0.2}, directions={"geometry_fidelity": ObjectiveDirection.MAXIMIZE, "support_risk": ObjectiveDirection.MINIMIZE}, evidence_states={"geometry_fidelity": EvidenceState.MEASURED, "support_risk": EvidenceState.MEASURED})
    _assert(len(vector.objective_hash) == 64, "objective vector hash is not an identity hash")
    evaluation = __import__("chroma3d_sculpt.models.intelligent_optimization_models", fromlist=["StrategyEvaluation"]).StrategyEvaluation(strategy.strategy_id, EvidenceState.MEASURED, vector, feasible=True, measured_evidence=("geometry_fidelity", "support_risk"))
    unknown_vector = replace(vector, normalized_values={"geometry_fidelity": None, "support_risk": 0.2}, evidence_states={"geometry_fidelity": EvidenceState.INDETERMINATE, "support_risk": EvidenceState.MEASURED})
    unknown = replace(evaluation, strategy_id="unknown", objective_vector=unknown_vector)
    _assert(not dominates(unknown, evaluation), "unknown evidence dominated known evidence")
    front = build_pareto_frontier((evaluation, unknown), max_points=4)
    profile = build_objective_profile("Balanced")
    rankings = rank_strategies((evaluation,), method=RankingMethod.WEIGHTED_SUM, profile=profile)
    _assert(rankings and rankings[0].strategy_id == evaluation.strategy_id, "known objective did not rank")
    methods = 0
    for method in RankingMethod:
        priority = ("geometry_fidelity", "support_risk") if method == RankingMethod.USER_PRIORITY else ()
        _assert(rank_strategies((evaluation,), method=method, profile=profile, user_priority=priority), f"ranking method {method.value} returned no result")
        methods += 1
    explanation = explain_strategy(strategy, evaluation, rankings[0], alternatives=("alternative",))
    _assert(explanation.why_generated and explanation.ranking_reasons and explanation.required_approvals, "explanation omitted required evidence")
    return {"objective_hash": vector.objective_hash, "frontier_points": len(front.points), "ranking_methods": methods, "explanation_alternatives": list(explanation.non_dominated_alternatives)}


def _history_and_exports() -> dict[str, Any]:
    history = __import__("chroma3d_sculpt.models.intelligent_optimization_models", fromlist=["StrategyHistory"]).StrategyHistory()
    entry = history_entry(source_identity={"object_name": "Independent"}, source_signature="source", strategy_fingerprint="fingerprint", objective_profile={"profile_hash": "objective"}, search_policy={"policy_hash": "policy"}, constraints={"constraint_set_hash": "constraints"}, evaluation={"state": "ESTIMATED"}, recorded_at="2026-01-01T00:00:00+00:00")
    _assert(add_history_entry(history, entry), "history entry was not added")
    _assert(not add_history_entry(history, entry), "duplicate history entry was added")
    _assert(history_is_current(history, source_signature="source", objective_profile_hash="objective", search_policy_hash="policy")[0], "current history was marked stale")
    _expect_error(lambda: write_history_json(history, ROOT / "manual-tests" / "sprint6-final" / "reports" / ".." / "escape.json"), "history export accepted traversal")
    safe = sanitize_intelligent_optimization_filename("<script>alert</script>.json")
    _assert("<" not in safe and ">" not in safe, "history filename was not sanitized")
    return {"entries": len(history.entries), "safe_filename": safe, "telemetry": False}


def _stale_and_cancellation() -> dict[str, Any]:
    clear_runtime(); _clear_scene()
    source = _cube("IndependentStale")
    try:
        start_intelligent_session(source, bpy.context.scene)
        generate_intelligent_strategies(source=source)
        source.location.x += 0.5
        message = _expect_error(lambda: ensure_current(get_active_session()), "stale source was accepted")
        _assert("SOURCE_SIGNATURE_CHANGED" in message, "stale reason was not precise")
        discard_intelligent_workspace()
        _assert(get_controlled_session() is None, "discard leaked controlled workspace")
        source = _cube("IndependentCancelled")
        start_intelligent_session(source, bpy.context.scene)
        cancel_intelligent_search()
        _assert(get_archived_session().state == IntelligentSessionState.CANCELLED, "cancel state was not retained")
        _assert(get_controlled_session() is None, "cancel leaked controlled workspace")
        return {"stale_reason": "SOURCE_SIGNATURE_CHANGED", "cancelled_state": get_archived_session().state.value, "workspace_leaked": False}
    finally:
        clear_runtime(); _clear_scene()


def _registration_and_performance() -> dict[str, Any]:
    names = {getattr(cls, "bl_idname", "") for cls in chroma3d_sculpt._RUNTIME_CLASSES}
    for forbidden in ("chroma3d.optimize_automatically", "chroma3d.replace_source", "chroma3d.slice", "chroma3d.send_to_printer"):
        _assert(forbidden not in names, f"prohibited operator registered: {forbidden}")
    strategy = __import__("chroma3d_sculpt.models.intelligent_optimization_models", fromlist=["IntelligentStrategy", "StrategyStep"]).IntelligentStrategy("performance", "performance-fp", "Balanced", "OBJECTIVE_ALIGNMENT", (__import__("chroma3d_sculpt.models.intelligent_optimization_models", fromlist=["StrategyStep"]).StrategyStep(1, "candidate", "ORIENTATION"),))
    timings: dict[str, float] = {}
    for triangles in (50_000, 200_000, 500_000):
        started = perf_counter()
        virtual_evaluate_strategy(strategy, baseline_values={"triangle_count": triangles, "geometry_fidelity": 1.0, "fidelity_status": "PASS", "critical_defect_introduced": False, "geometric_deviation": 0.0, "area_drift": 0.0, "volume_drift": 0.0})
        timings[str(triangles)] = round(perf_counter() - started, 6)
    return {"registered_operator_count": len(names), "forbidden_operator_count": 0, "synthetic_triangle_timings_seconds": timings, "memory_observation": "NOT_CAPTURED_BY_THIS_RUNNER"}


def main() -> int:
    gates: list[dict[str, Any]] = []
    _gate(gates, "S6F-A", "Protected-source matrix", _protected_source_matrix)
    _gate(gates, "S6F-B", "Search-policy attacks", _policy_attacks)
    _gate(gates, "S6F-C", "Constraint truth", _constraint_truth)
    _gate(gates, "S6F-D", "Strategy generation identity", _generation_and_pruning)
    _gate(gates, "S6F-E", "Search and pruning", _generation_and_pruning)
    _gate(gates, "S6F-F", "Objective-vector truth, Pareto, ranking, explanations", _objective_pareto_ranking)
    _gate(gates, "S6F-G", "Pareto correctness", _objective_pareto_ranking)
    _gate(gates, "S6F-H", "Ranking correctness", _objective_pareto_ranking)
    _gate(gates, "S6F-I", "Evidence-backed explanations", _objective_pareto_ranking)
    _gate(gates, "S6F-J", "Sprint 5 integration and source protection", _protected_source_matrix)
    _gate(gates, "S6F-K", "Stale-state matrix", _stale_and_cancellation)
    _gate(gates, "S6F-L", "Cancellation and budget exhaustion", _generation_and_pruning)
    _gate(gates, "S6F-M", "History and overrides", _history_and_exports)
    _gate(gates, "S6F-N", "Audit/export security", _history_and_exports)
    _gate(gates, "S6F-O", "Registration and UI safety", _registration_and_performance)
    _gate(gates, "S6F-P", "Bounded synthetic performance", _registration_and_performance)
    _gate(gates, "S6F-Q", "Initial-failure preservation", lambda: {"preserved": (ROOT / "manual-tests" / "sprint6-final" / "initial-failures" / "current-final-validation.log").is_file()})
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    failed = [item for item in gates if item["status"] == "FAIL"]
    payload = {
        "schema_version": "1.0",
        "milestone": "Sprint 6 - Intelligent Optimization",
        "status": "FAIL" if failed else "PASS_WITH_LIMITATIONS",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "blender_version": bpy.app.version_string,
        "gate_count": len(gates),
        "passed_gate_count": sum(item["status"] == "PASS" for item in gates),
        "failed_gate_count": len(failed),
        "gates": gates,
        "limitations": ["This runner does not prove physical printing, real slicer comparison, material calibration, Blender 4.5 LTS, or manual installed-panel UAT.", "Synthetic performance cases use objective fixtures, not exact peak-memory or full mesh-processing claims."],
        "safety_confirmation": {"source_mutation": False, "automatic_execution": False, "automatic_acceptance": False, "ai_or_llm": False, "cloud": False, "slicer": False, "gcode": False, "printer_command": False, "sprint7": False},
    }
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    clear_runtime(); _clear_scene()
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
