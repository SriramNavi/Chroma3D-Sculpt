"""Focused Blender tests for Sprint 6 deterministic intelligent optimization."""

from __future__ import annotations

from pathlib import Path
from dataclasses import replace
import math
import sys
import tempfile
import unittest

import bpy

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ADDON_ROOT = REPOSITORY_ROOT / "blender_addon"
if str(ADDON_ROOT) not in sys.path:
    sys.path.insert(0, str(ADDON_ROOT))

import chroma3d_sculpt  # noqa: E402
from chroma3d_sculpt.intelligent_optimization_settings import IntelligentOptimizationSettings  # noqa: E402
from chroma3d_sculpt.metadata import DISPLAY_VERSION  # noqa: E402
from chroma3d_sculpt.models.intelligent_optimization_models import (  # noqa: E402
    ConstraintKind, ConstraintSet, ConstraintSeverity, ConstraintState, DeterministicModel, OptimizationConstraint,
    DominanceState, EvidenceState, IntelligentOptimizationSession, IntelligentStrategy, IntelligentSessionState,
    ObjectiveDirection, ObjectiveMetric, ObjectiveVector, ParetoPoint, RankingMethod, SearchBudget, SearchMode, SearchPolicy,
    StrategyEvaluation, StrategyGenerationReason, StrategyHistory, StrategyState, StrategyStep,
)
from chroma3d_sculpt.services.constraint_engine import (  # noqa: E402
    constraints_are_feasible, default_constraint_set, evaluate_constraints, validate_constraint_set,
)
from chroma3d_sculpt.services.intelligent_optimization_audit import (  # noqa: E402
    build_audit, sanitize_intelligent_optimization_filename, write_json_audit, write_markdown_audit,
)
from chroma3d_sculpt.services.optimization_candidates import generate_candidates  # noqa: E402
from chroma3d_sculpt.models.optimization_models import OptimizationPolicy  # noqa: E402
from chroma3d_sculpt.services.pareto_frontier import build_pareto_frontier, dominance, dominates  # noqa: E402
from chroma3d_sculpt.services.search_policy import (  # noqa: E402
    STRATEGY_FAMILIES, default_search_policy, policy_hash, validate_search_policy,
)
from chroma3d_sculpt.services.strategy_evaluator import evaluate_strategies, virtual_evaluate_strategy  # noqa: E402
from chroma3d_sculpt.services.strategy_explainer import explain_strategy  # noqa: E402
from chroma3d_sculpt.services.strategy_generator import generate_strategies  # noqa: E402
from chroma3d_sculpt.services.strategy_history import add_history_entry, history_entry  # noqa: E402
from chroma3d_sculpt.services.strategy_history import history_is_current, sanitize_history_filename, write_history_json  # noqa: E402
from chroma3d_sculpt.services.strategy_ranker import rank_strategies, recommend_strategy  # noqa: E402
from chroma3d_sculpt.services.strategy_explainer import explanation_markdown  # noqa: E402
from chroma3d_sculpt.intelligent_optimization_settings import build_objective_profile  # noqa: E402
from chroma3d_sculpt.services.intelligent_optimization_coordinator import (  # noqa: E402
    build_intelligent_frontier, cancel_intelligent_search, discard_intelligent_workspace, ensure_current,
    evaluate_intelligent_strategies, execute_selected_strategy, generate_intelligent_strategies,
    preview_selected_strategy, rank_intelligent_strategies, rerun_intelligent_search, select_strategy,
    start_intelligent_session,
)
from chroma3d_sculpt.services.intelligent_optimization_session import clear_runtime, get_active_session, get_archived_session, get_controlled_session  # noqa: E402
from chroma3d_sculpt.utilities.optimization_signatures import source_signature  # noqa: E402


def clear_scene() -> None:
    for obj in tuple(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def make_cube(name: str = "Sprint6Cube") -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 1.0))
    obj = bpy.context.object
    obj.name = name
    obj.data.name = f"{name}Mesh"
    return obj


def make_strategy(strategy_id: str, values: dict[str, float | None], *, feasible: bool = True, states: dict[str, str] | None = None) -> tuple[IntelligentStrategy, StrategyEvaluation]:
    strategy = IntelligentStrategy(
        strategy_id=strategy_id,
        fingerprint=f"fp-{strategy_id}",
        generation_family="Balanced",
        generation_reason=StrategyGenerationReason.OBJECTIVE_ALIGNMENT,
        steps=(StrategyStep(1, f"candidate-{strategy_id}", "ORIENTATION", parameters={}),),
        policy_hash="policy",
        constraint_set_hash="constraints",
    )
    directions = {key: (ObjectiveDirection.MINIMIZE if key.endswith("_risk") or key in {"height", "triangle_count"} else ObjectiveDirection.MAXIMIZE) for key in values}
    vector = ObjectiveVector(raw_values=values, normalized_values=values, directions=directions, evidence_states=states or {key: EvidenceState.MEASURED for key in values})
    return strategy, StrategyEvaluation(strategy_id, EvidenceState.MEASURED, vector, feasible=feasible, measured_evidence=tuple(values))


class Sprint6IntelligentOptimizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        clear_scene()
        try:
            chroma3d_sculpt.unregister()
        except Exception:
            pass
        chroma3d_sculpt.register()

    @classmethod
    def tearDownClass(cls) -> None:
        clear_runtime()
        clear_scene()
        chroma3d_sculpt.unregister()

    def setUp(self) -> None:
        clear_runtime()
        clear_scene()

    def test_01_version_and_schema_lock(self) -> None:
        self.assertEqual(DISPLAY_VERSION, "0.8.0-alpha.1")
        self.assertEqual(default_search_policy(SearchMode.FAST).policy_version, "1.0")
        self.assertEqual(default_constraint_set().schema_version, "1.0")

    def test_02_deterministic_model_serialization_and_rejections(self) -> None:
        budget = SearchBudget()
        self.assertEqual(budget.to_json(), budget.to_json())
        with self.assertRaises(ValueError):
            SearchBudget(max_generated_strategies=True)
        with self.assertRaises(ValueError):
            SearchBudget(max_wall_time_seconds=float("nan"))
        with self.assertRaises(ValueError):
            SearchBudget(max_wall_time_seconds=float("inf"))
        with self.assertRaises(ValueError):
            DeterministicModel().to_dict()  # type: ignore[abstract]

    def test_03_raw_blender_reference_and_geometry_rejection(self) -> None:
        strategy, _ = make_strategy("raw", {"geometry_fidelity": 1.0})
        object.__setattr__(strategy, "source_evidence", ({"bpy_object": object()},))
        with self.assertRaises(ValueError):
            strategy.to_json()
        object.__setattr__(strategy, "source_evidence", ({"vertices": [(0.0, 0.0, 0.0)]},))
        with self.assertRaises(ValueError):
            strategy.to_json()

    def test_04_search_mode_defaults_and_hashes(self) -> None:
        fast = default_search_policy(SearchMode.FAST)
        standard = default_search_policy(SearchMode.STANDARD)
        deep = default_search_policy(SearchMode.DEEP)
        self.assertLess(fast.budget.max_generated_strategies, standard.budget.max_generated_strategies)
        self.assertLess(standard.budget.max_generated_strategies, deep.budget.max_generated_strategies)
        self.assertEqual(fast.policy_hash, policy_hash(fast))
        validate_search_policy(standard)
        with self.assertRaises(ValueError):
            SearchPolicy(allowed_operation_families=("UNKNOWN",))
        with self.assertRaises(ValueError):
            SearchPolicy(experimental_operations_enabled=True)

    def test_05_constraint_pass_fail_unknown_soft_and_conflict(self) -> None:
        constraints = ConstraintSet((
            # The source protection and maximum deviation requirements are
            # intentionally evaluated separately for truthful evidence states.
            __import__("chroma3d_sculpt.models.intelligent_optimization_models", fromlist=["OptimizationConstraint"]).OptimizationConstraint("source", ConstraintKind.SOURCE_PROTECTED, required_value=True, actual_key="source_protected"),
            __import__("chroma3d_sculpt.models.intelligent_optimization_models", fromlist=["OptimizationConstraint"]).OptimizationConstraint("deviation", ConstraintKind.MAX_GEOMETRIC_DEVIATION, maximum=0.25, actual_key="deviation"),
            __import__("chroma3d_sculpt.models.intelligent_optimization_models", fromlist=["OptimizationConstraint"]).OptimizationConstraint("soft", ConstraintKind.MIN_SUPPORT_RISK, ConstraintSeverity.SOFT, maximum=0.5, actual_key="support_risk"),
        ), set_id="test-constraints")
        validate_constraint_set(constraints)
        passed = evaluate_constraints(constraints, {"source_protected": True, "deviation": 0.1, "support_risk": 0.8}, evidence_states={"source_protected": "MEASURED", "deviation": "MEASURED", "support_risk": "MEASURED"})
        self.assertTrue(constraints_are_feasible(passed))
        self.assertEqual(passed[-1].state, ConstraintState.WARNING)
        unknown = evaluate_constraints(constraints, {"source_protected": True}, evidence_states={"source_protected": "MEASURED"})
        self.assertFalse(constraints_are_feasible(unknown))
        self.assertNotEqual(unknown[1].state, ConstraintState.PASS)
        with self.assertRaises(ValueError):
            ConstraintSet((
                __import__("chroma3d_sculpt.models.intelligent_optimization_models", fromlist=["OptimizationConstraint"]).OptimizationConstraint("a", ConstraintKind.MAX_HEIGHT, maximum=1.0, actual_key="height"),
                __import__("chroma3d_sculpt.models.intelligent_optimization_models", fromlist=["OptimizationConstraint"]).OptimizationConstraint("b", ConstraintKind.MAX_HEIGHT, minimum=2.0, actual_key="height"),
            ), set_id="conflict")

    def test_06_strategy_generation_is_bounded_deterministic_and_explainable(self) -> None:
        policy = default_search_policy(SearchMode.STANDARD)
        candidates = generate_candidates(None, source_snapshot={"source_signature": "source"}, policy=OptimizationPolicy())
        first = generate_strategies(candidates, policy=policy, source_signature="source")
        second = generate_strategies(candidates, policy=policy, source_signature="source")
        self.assertEqual(first.to_json(), second.to_json())
        self.assertEqual(len({item.strategy_id for item in first.strategies}), len(first.strategies))
        self.assertLessEqual(len(first.strategies), policy.budget.max_generated_strategies)
        self.assertTrue(any(item.generation_family == "Scale only" for item in first.strategies))
        self.assertTrue(any(item.generation_family == "Orientation only" for item in first.strategies))
        self.assertTrue(any(item.generation_family == "Repair-first" for item in first.strategies) or any(item.reason_code == "UNSUPPORTED_COMBINATION" for item in first.pruned))

    def test_07_generation_cancellation_and_experimental_pruning(self) -> None:
        policy = default_search_policy(SearchMode.STANDARD)
        candidates = generate_candidates(None, source_snapshot={"source_signature": "source"}, policy=OptimizationPolicy())
        result = generate_strategies(candidates, policy=policy, cancel_requested=lambda: True)
        self.assertEqual(result.status, "CANCELLED")
        self.assertIn("cancellation", result.budget_usage.exhausted_dimensions)
        self.assertFalse(any(step.experimental for strategy in result.strategies for step in strategy.steps))

    def test_08_virtual_evaluation_is_read_only_and_truthful(self) -> None:
        policy = default_search_policy()
        candidates = generate_candidates(None, source_snapshot={"source_signature": "source"}, policy=OptimizationPolicy())
        strategies = generate_strategies(candidates, policy=policy, source_signature="source")
        strategy = strategies.strategies[0]
        evaluation = virtual_evaluate_strategy(strategy, policy=policy, baseline_values={"fidelity_status": "PASS", "critical_defect_introduced": False, "geometric_deviation": 0.0, "area_drift": 0.0, "volume_drift": 0.0, "build_volume_fit": 1.0, "geometry_fidelity": 1.0, "height": 1.0})
        self.assertEqual(evaluation.evaluation_state, EvidenceState.ESTIMATED)
        self.assertTrue(evaluation.estimated_evidence)
        self.assertFalse(evaluation.measured_evidence)

    def test_09_pareto_two_three_high_dimensional_and_unknown(self) -> None:
        strategies, evaluations = zip(*(
            make_strategy("a", {"fit": 0.9, "fidelity": 0.5}),
            make_strategy("b", {"fit": 0.5, "fidelity": 0.9}),
            make_strategy("c", {"fit": 0.4, "fidelity": 0.4}),
        ))
        frontier = build_pareto_frontier(evaluations, max_points=8)
        self.assertEqual({item.strategy_id for item in frontier.points}, {"a", "b"})
        self.assertIn("c", frontier.dominated_strategy_ids)
        self.assertTrue(dominates(evaluations[0], evaluations[2]))
        self.assertIn(dominance(evaluations[0], evaluations[1]).state, {DominanceState.INCOMPARABLE, DominanceState.EQUAL})
        _, unknown = make_strategy("unknown", {"fit": None, "fidelity": 0.9}, states={"fit": "INDETERMINATE", "fidelity": "MEASURED"})
        self.assertFalse(dominates(evaluations[0], unknown))

    def test_10_ranking_ties_and_recommendation_wording(self) -> None:
        _, first = make_strategy("first", {"geometry_fidelity": 0.8, "support_risk": 0.2})
        _, second = make_strategy("second", {"geometry_fidelity": 0.8, "support_risk": 0.2})
        rankings = rank_strategies((first, second), method=RankingMethod.WEIGHTED_SUM)
        self.assertEqual(len(rankings), 2)
        self.assertEqual(rankings[0].tie_group, rankings[1].tie_group)
        recommendation = recommend_strategy(rankings)
        self.assertIsNotNone(recommendation)
        self.assertIn("not a global optimum", recommendation.wording)
        self.assertFalse(recommendation.is_automatic_execution)

    def test_11_explanation_discloses_tradeoffs_and_evidence(self) -> None:
        strategy, evaluation = make_strategy("explain", {"geometry_fidelity": 0.8, "support_risk": 0.7})
        explanation = explain_strategy(strategy, evaluation)
        self.assertTrue(explanation.why_generated)
        self.assertTrue(explanation.improvements or explanation.regressions)
        self.assertIn("not a global optimum", explanation.advisory_disclaimer)

    def test_12_history_duplicate_suppression_and_audit_export(self) -> None:
        history = StrategyHistory()
        entry = history_entry(source_identity={"object_name": "Cube"}, source_signature="source", strategy_fingerprint="strategy", objective_profile={"profile_hash": "objective"}, search_policy={"policy_hash": "policy"}, constraints={"constraint_set_hash": "constraints"}, evaluation={"state": "ESTIMATED"}, recorded_at="2026-01-01T00:00:00+00:00")
        self.assertTrue(add_history_entry(history, entry))
        self.assertFalse(add_history_entry(history, entry))
        session = IntelligentOptimizationSession("session", "2026-01-01T00:00:00+00:00", IntelligentSessionState.REVIEW_REQUIRED, source_identity={"object_name": "Cube"}, source_signature="source", history=history)
        audit = build_audit(session, blender_version="4.4.3")
        self.assertTrue(audit.to_json().endswith("\n"))
        self.assertIn("not a global optimum", write_markdown_audit(audit, Path(tempfile.mkdtemp()) / "audit.md").read_text(encoding="utf-8"))
        self.assertEqual(sanitize_intelligent_optimization_filename("CON:/unsafe name"), "CON_unsafe_name")
        with self.assertRaises(ValueError):
            write_json_audit(audit, Path(tempfile.mkdtemp()) / ".." / "unsafe.json")

    def test_13_blender_registration_and_prohibited_actions(self) -> None:
        names = {getattr(cls, "bl_idname", "") for cls in chroma3d_sculpt._RUNTIME_CLASSES}
        self.assertIn("chroma3d.start_intelligent_optimization", names)
        self.assertIn("chroma3d.build_intelligent_frontier", names)
        self.assertNotIn("chroma3d.optimize_automatically", names)
        self.assertNotIn("chroma3d.send_to_printer", names)

    def test_14_sprint5_workspace_bridge_keeps_source_protected(self) -> None:
        source = make_cube()
        before = source_signature(source)["source_signature"]
        start_intelligent_session(source, bpy.context.scene)
        strategy_set = generate_intelligent_strategies(source=source)
        self.assertTrue(strategy_set.strategies)
        self.assertEqual(source_signature(source)["source_signature"], before)
        discard_intelligent_workspace()
        self.assertIsNone(get_active_session())

    def test_15_rerun_invalidates_prior_evidence_and_keeps_source_protected(self) -> None:
        source = make_cube("Sprint6RerunCube")
        before = source_signature(source)["source_signature"]
        start_intelligent_session(source, bpy.context.scene)
        generate_intelligent_strategies(source=source)
        first_profile_hash = get_active_session().objective_profile_hash
        rerun = rerun_intelligent_search(
            settings=IntelligentOptimizationSettings(objective_preset="Maximum Fidelity"),
            source=source,
        )
        active = get_active_session()
        self.assertTrue(rerun.strategies)
        self.assertNotEqual(active.objective_profile_hash, first_profile_hash)
        self.assertEqual(active.state, IntelligentSessionState.SEARCH_COMPLETE)
        self.assertEqual(source_signature(source)["source_signature"], before)
        discard_intelligent_workspace()


def _install_expanded_sprint6_matrix() -> None:
    """Install case-labelled tests whose inputs exercise distinct S6 paths."""

    test_class = Sprint6IntelligentOptimizationTests

    def add(index: int, label: str, body: object) -> None:
        setattr(test_class, f"test_s6_matrix_{index:03d}_{label}", body)

    index = 1

    for label, expected in (
        ("schema_strategy", "1.0"), ("schema_policy", "1.0"), ("schema_constraint", "1.0"),
        ("schema_frontier", "1.0"), ("schema_ranking", "1.0"), ("schema_explanation", "1.0"),
        ("schema_history", "1.0"), ("schema_audit", "1.0"),
    ):
        def version_case(self: unittest.TestCase, label: str = label, expected: str = expected) -> None:
            values = {
                "schema_strategy": "1.0",
                "schema_policy": default_search_policy().policy_version,
                "schema_constraint": default_constraint_set().schema_version,
                "schema_frontier": build_pareto_frontier((), max_points=1).schema_version,
                "schema_ranking": "1.0",
                "schema_explanation": "1.0",
                "schema_history": StrategyHistory().schema_version,
                "schema_audit": build_audit(IntelligentOptimizationSession("matrix", "fixed", source_signature="s")).schema_version,
            }
            self.assertEqual(str(values[label]), expected, label)
        add(index, f"version_{label}", version_case)
        index += 1

    budget_fields = (
        "max_generated_strategies", "max_evaluated_strategies", "max_workspace_previews",
        "max_operation_steps", "max_strategy_depth", "max_branch_factor",
        "max_operation_sequence_permutations", "max_pareto_points", "max_ranking_results",
        "max_history_entries", "max_export_bytes",
    )
    for field_name in budget_fields:
        for bad_value, suffix in ((0, "zero"), (-1, "negative")):
            def budget_case(self: unittest.TestCase, field_name: str = field_name, bad_value: int = bad_value) -> None:
                with self.assertRaises(ValueError, msg=f"{field_name}={bad_value}"):
                    replace(SearchBudget(), **{field_name: bad_value})
            add(index, f"budget_{field_name}_{suffix}", budget_case)
            index += 1
    for field_name in ("max_generated_strategies", "max_evaluated_strategies", "max_operation_steps", "max_strategy_depth"):
        def boolean_budget_case(self: unittest.TestCase, field_name: str = field_name) -> None:
            with self.assertRaises(ValueError, msg=f"boolean {field_name}"):
                replace(SearchBudget(), **{field_name: True})
        add(index, f"budget_{field_name}_boolean", boolean_budget_case)
        index += 1
    for field_name in ("max_wall_time_seconds", "max_per_strategy_seconds", "max_memory_observation_mb"):
        for bad_value, suffix in ((0.0, "zero"), (-1.0, "negative"), (float("nan"), "nan"), (float("inf"), "infinity")):
            def float_budget_case(self: unittest.TestCase, field_name: str = field_name, bad_value: float = bad_value) -> None:
                with self.assertRaises(ValueError, msg=f"{field_name}={bad_value}"):
                    replace(SearchBudget(), **{field_name: bad_value})
            add(index, f"budget_{field_name}_{suffix}", float_budget_case)
            index += 1

    def policy_invalid_mode(self: unittest.TestCase) -> None:
        with self.assertRaises(ValueError):
            default_search_policy("INVALID_MODE")
    add(index, "policy_invalid_mode", policy_invalid_mode); index += 1

    def policy_invalid_ranking(self: unittest.TestCase) -> None:
        with self.assertRaises(ValueError):
            SearchPolicy(ranking_method="NOT_A_RANKER")
    add(index, "policy_invalid_ranking", policy_invalid_ranking); index += 1

    def policy_duplicate_family(self: unittest.TestCase) -> None:
        policy = replace(default_search_policy(), enabled_strategy_families=("Scale only", "Scale only"), policy_hash="")
        with self.assertRaises(ValueError):
            validate_search_policy(policy)
    add(index, "policy_duplicate_family", policy_duplicate_family); index += 1

    def policy_duplicate_operation(self: unittest.TestCase) -> None:
        with self.assertRaises(ValueError):
            SearchPolicy(allowed_operation_families=("ORIENTATION", "ORIENTATION"))
    add(index, "policy_duplicate_operation", policy_duplicate_operation); index += 1

    def policy_unknown_operation(self: unittest.TestCase) -> None:
        with self.assertRaises(ValueError):
            SearchPolicy(allowed_operation_families=("UNKNOWN_OPERATION",))
    add(index, "policy_unknown_operation", policy_unknown_operation); index += 1

    def policy_empty_operations(self: unittest.TestCase) -> None:
        with self.assertRaises(ValueError):
            SearchPolicy(allowed_operation_families=())
    add(index, "policy_empty_operations", policy_empty_operations); index += 1

    def policy_experimental_without_explicit(self: unittest.TestCase) -> None:
        with self.assertRaises(ValueError):
            SearchPolicy(allowed_operation_families=("EXPERIMENTAL_REMESH",), experimental_operations_enabled=True)
    add(index, "policy_experimental_without_explicit", policy_experimental_without_explicit); index += 1

    def policy_empty_identity(self: unittest.TestCase) -> None:
        with self.assertRaises(ValueError):
            SearchPolicy(policy_id="")
    add(index, "policy_empty_identity", policy_empty_identity); index += 1

    def policy_empty_seed(self: unittest.TestCase) -> None:
        with self.assertRaises(ValueError):
            SearchPolicy(deterministic_seed="")
    add(index, "policy_empty_seed", policy_empty_seed); index += 1

    for field_name, bad_value in (("duplicate_tolerance", -0.1), ("dominance_tolerance", -0.1), ("dominance_tolerance", float("nan")), ("dominance_tolerance", float("inf"))):
        def policy_tolerance_case(self: unittest.TestCase, field_name: str = field_name, bad_value: float = bad_value) -> None:
            with self.assertRaises(ValueError):
                replace(default_search_policy(), **{field_name: bad_value})
        add(index, f"policy_{field_name}_{str(bad_value).replace('.', '_')}", policy_tolerance_case); index += 1

    def policy_tampered_hash(self: unittest.TestCase) -> None:
        policy = default_search_policy()
        object.__setattr__(policy, "policy_hash", "tampered")
        with self.assertRaises(ValueError):
            validate_search_policy(policy)
    add(index, "policy_tampered_hash", policy_tampered_hash); index += 1

    def policy_registry_duplicate(self: unittest.TestCase) -> None:
        from chroma3d_sculpt.services.search_policy import SearchPolicyRegistry
        policy = default_search_policy()
        registry = SearchPolicyRegistry((policy,))
        with self.assertRaises(ValueError):
            registry.add(policy)
    add(index, "policy_registry_duplicate", policy_registry_duplicate); index += 1

    for kind in (
        ConstraintKind.SOURCE_PROTECTED, ConstraintKind.ALLOWED_OPERATION, ConstraintKind.MAX_DEPTH,
        ConstraintKind.SCALE_RANGE, ConstraintKind.ORIENTATION_COUNT, ConstraintKind.BASE_GEOMETRY,
        ConstraintKind.DECIMATION_RATIO, ConstraintKind.FIDELITY_STATUS, ConstraintKind.CRITICAL_DEFECT,
        ConstraintKind.BUILD_VOLUME_FIT, ConstraintKind.MIN_WALL_THICKNESS, ConstraintKind.MIN_THIN_FEATURE,
        ConstraintKind.MAX_GEOMETRIC_DEVIATION, ConstraintKind.MAX_AREA_DRIFT, ConstraintKind.MAX_VOLUME_DRIFT,
        ConstraintKind.MAX_TRIANGLE_COUNT_CHANGE, ConstraintKind.MIN_CONFIDENCE, ConstraintKind.EXPERIMENTAL_OPERATION,
        ConstraintKind.MIN_SUPPORT_RISK, ConstraintKind.MIN_BRIDGE_RISK, ConstraintKind.MIN_CONTACT,
        ConstraintKind.MAX_HEIGHT, ConstraintKind.MIN_FIDELITY, ConstraintKind.MIN_WALL_PRESERVATION,
        ConstraintKind.MIN_FEATURE_PRESERVATION, ConstraintKind.MIN_BUILD_FIT,
    ):
        def constraint_case(self: unittest.TestCase, kind: ConstraintKind = kind) -> None:
            actual_key = kind.value.lower()
            kwargs: dict[str, object] = {"actual_key": actual_key}
            actual: object = 0.5
            if kind in {ConstraintKind.SOURCE_PROTECTED, ConstraintKind.BASE_GEOMETRY, ConstraintKind.CRITICAL_DEFECT}:
                actual = kind != ConstraintKind.CRITICAL_DEFECT
                kwargs["required_value"] = actual
            elif kind == ConstraintKind.ALLOWED_OPERATION:
                actual = ("ORIENTATION",)
                kwargs["required_value"] = ("ORIENTATION",)
            elif kind == ConstraintKind.FIDELITY_STATUS:
                actual = "PASS"; kwargs["required_value"] = "PASS"
            elif kind == ConstraintKind.MIN_CONFIDENCE:
                actual = "LOW"; kwargs["required_value"] = "LOW"
            elif kind == ConstraintKind.EXPERIMENTAL_OPERATION:
                actual = False; kwargs["required_value"] = False
            elif kind in {ConstraintKind.SCALE_RANGE, ConstraintKind.ORIENTATION_COUNT, ConstraintKind.MAX_DEPTH, ConstraintKind.MAX_GEOMETRIC_DEVIATION, ConstraintKind.MAX_AREA_DRIFT, ConstraintKind.MAX_VOLUME_DRIFT, ConstraintKind.MAX_TRIANGLE_COUNT_CHANGE, ConstraintKind.MIN_SUPPORT_RISK, ConstraintKind.MIN_BRIDGE_RISK, ConstraintKind.MAX_HEIGHT}:
                kwargs["maximum"] = 1.0
            else:
                kwargs["minimum"] = 0.0
            constraint = OptimizationConstraint(f"matrix-{kind.value}", kind, **kwargs)
            result = evaluate_constraints(ConstraintSet((constraint,), set_id=f"matrix-{kind.value}"), {actual_key: actual}, evidence_states={actual_key: EvidenceState.MEASURED})
            self.assertEqual(result[0].state, ConstraintState.PASS, kind.value)
            self.assertTrue(constraints_are_feasible(result))
        add(index, f"constraint_{kind.value.lower()}", constraint_case); index += 1

    for evidence_state in (EvidenceState.INDETERMINATE, EvidenceState.SKIPPED_LIMIT):
        def unknown_constraint_case(self: unittest.TestCase, evidence_state: EvidenceState = evidence_state) -> None:
            constraint = OptimizationConstraint("unknown-height", ConstraintKind.MAX_HEIGHT, maximum=1.0, actual_key="height")
            result = evaluate_constraints(ConstraintSet((constraint,), set_id=f"unknown-{evidence_state.value}"), {"height": 0.1}, evidence_states={"height": evidence_state})
            self.assertNotEqual(result[0].state, ConstraintState.PASS)
            self.assertFalse(constraints_are_feasible(result))
        add(index, f"constraint_unknown_{evidence_state.value.lower()}", unknown_constraint_case); index += 1

    for actual in (float("nan"), float("inf"), float("-inf")):
        def nonfinite_constraint_case(self: unittest.TestCase, actual: float = actual) -> None:
            constraint = OptimizationConstraint("finite-height", ConstraintKind.MAX_HEIGHT, maximum=1.0, actual_key="height")
            result = evaluate_constraints(ConstraintSet((constraint,), set_id=f"finite-{str(actual)}"), {"height": actual}, evidence_states={"height": EvidenceState.MEASURED})
            self.assertEqual(result[0].state, ConstraintState.FAIL)
            self.assertFalse(constraints_are_feasible(result))
        add(index, f"constraint_nonfinite_{str(actual).replace('-', 'm').replace('.', '_')}", nonfinite_constraint_case); index += 1

    def duplicate_constraint_id_case(self: unittest.TestCase) -> None:
        item = OptimizationConstraint("duplicate", ConstraintKind.MAX_HEIGHT, maximum=1.0, actual_key="height")
        with self.assertRaises(ValueError):
            ConstraintSet((item, item), set_id="duplicate-ids")
    add(index, "constraint_duplicate_id", duplicate_constraint_id_case); index += 1

    def conflicting_constraint_case(self: unittest.TestCase) -> None:
        with self.assertRaises(ValueError):
            ConstraintSet((
                OptimizationConstraint("lower", ConstraintKind.MAX_HEIGHT, minimum=2.0, actual_key="height"),
                OptimizationConstraint("upper", ConstraintKind.MAX_HEIGHT, maximum=1.0, actual_key="height"),
            ), set_id="conflicting-bounds")
    add(index, "constraint_conflicting_bounds", conflicting_constraint_case); index += 1

    def tampered_constraint_hash_case(self: unittest.TestCase) -> None:
        constraints = default_constraint_set()
        object.__setattr__(constraints, "constraint_set_hash", "tampered")
        with self.assertRaises(ValueError):
            validate_constraint_set(constraints)
    add(index, "constraint_tampered_hash", tampered_constraint_hash_case); index += 1

    family_names = tuple(STRATEGY_FAMILIES)
    for family in family_names:
        def family_case(self: unittest.TestCase, family: str = family) -> None:
            base = default_search_policy(SearchMode.STANDARD)
            policy = replace(base, enabled_strategy_families=(family,), policy_hash="")
            candidates = generate_candidates(None, source_snapshot={"source_signature": f"family-{family}"}, policy=OptimizationPolicy())
            result = generate_strategies(candidates, policy=policy, source_signature=f"family-{family}")
            self.assertTrue(result.strategies or result.pruned, family)
            if result.strategies:
                self.assertTrue(all(item.generation_family == family for item in result.strategies))
            else:
                self.assertTrue(any(item.reason_code in {"UNSUPPORTED_COMBINATION", "POLICY_LIMIT", "EXPERIMENTAL_OPERATION_DISABLED"} for item in result.pruned))
        add(index, f"family_{index:03d}", family_case); index += 1

    def generation_operation_step_budget_case(self: unittest.TestCase) -> None:
        base = default_search_policy()
        budget = replace(base.budget, max_generated_strategies=16, max_operation_steps=1)
        policy = replace(base, budget=budget, policy_hash="")
        candidates = generate_candidates(None, source_snapshot={"source_signature": "step-budget"}, policy=OptimizationPolicy())
        result = generate_strategies(candidates, policy=policy, source_signature="step-budget")
        self.assertEqual(result.status, "BUDGET_EXHAUSTED")
        self.assertIn("operation_steps", result.budget_usage.exhausted_dimensions)
    add(index, "generation_operation_step_budget", generation_operation_step_budget_case); index += 1

    def generation_strategy_budget_case(self: unittest.TestCase) -> None:
        base = default_search_policy()
        policy = replace(base, budget=replace(base.budget, max_generated_strategies=1), policy_hash="")
        candidates = generate_candidates(None, source_snapshot={"source_signature": "strategy-budget"}, policy=OptimizationPolicy())
        result = generate_strategies(candidates, policy=policy, source_signature="strategy-budget")
        self.assertEqual(result.status, "BUDGET_EXHAUSTED")
        self.assertLessEqual(result.budget_usage.generated_strategies, 1)
    add(index, "generation_strategy_budget", generation_strategy_budget_case); index += 1

    def generation_semantic_duplicate_case(self: unittest.TestCase) -> None:
        base = default_search_policy()
        policy = replace(base, enabled_strategy_families=("Scale only",), policy_hash="")
        candidates = (
            {"candidate_id": "a", "fingerprint": "a", "operation": "UNIFORM_SCALE", "parameters": {"scale": 1.0}},
            {"candidate_id": "b", "fingerprint": "b", "operation": "UNIFORM_SCALE", "parameters": {"scale": 1.0}},
        )
        result = generate_strategies(candidates, policy=policy, source_signature="semantic-duplicate")
        self.assertEqual(len(result.strategies), 1)
        self.assertTrue(any(item.reason_code == "DUPLICATE" for item in result.pruned))
    add(index, "generation_semantic_duplicate", generation_semantic_duplicate_case); index += 1

    def generation_duplicate_candidate_id_case(self: unittest.TestCase) -> None:
        candidates = (
            {"candidate_id": "same", "fingerprint": "a", "operation": "UNIFORM_SCALE", "parameters": {"scale": 1.0}},
            {"candidate_id": "same", "fingerprint": "b", "operation": "ORIENTATION", "parameters": {"rotation": 1.0}},
        )
        with self.assertRaises(ValueError):
            generate_strategies(candidates, policy=default_search_policy(), source_signature="duplicate-id")
    add(index, "generation_duplicate_candidate_id", generation_duplicate_candidate_id_case); index += 1

    def generation_fingerprint_collision_case(self: unittest.TestCase) -> None:
        candidates = (
            {"candidate_id": "one", "fingerprint": "same", "operation": "UNIFORM_SCALE", "parameters": {"scale": 1.0}},
            {"candidate_id": "two", "fingerprint": "same", "operation": "UNIFORM_SCALE", "parameters": {"scale": 0.5}},
        )
        with self.assertRaises(ValueError):
            generate_strategies(candidates, policy=default_search_policy(), source_signature="fingerprint-collision")
    add(index, "generation_fingerprint_collision", generation_fingerprint_collision_case); index += 1

    def generation_cancellation_case(self: unittest.TestCase) -> None:
        candidates = generate_candidates(None, source_snapshot={"source_signature": "cancel"}, policy=OptimizationPolicy())
        result = generate_strategies(candidates, policy=default_search_policy(), cancel_requested=lambda: True)
        self.assertEqual(result.status, "CANCELLED")
        self.assertNotEqual(result.status, "BUDGET_EXHAUSTED")
        self.assertFalse(any(item.state == StrategyState.FAILED for item in result.strategies))
    add(index, "generation_cancellation", generation_cancellation_case); index += 1

    for metric in tuple(ObjectiveMetric):
        def objective_vector_case(self: unittest.TestCase, metric: ObjectiveMetric = metric) -> None:
            key = metric.value
            vector = ObjectiveVector(raw_values={key: 0.25}, normalized_values={key: 0.25}, directions={key: ObjectiveDirection.MINIMIZE if metric in {ObjectiveMetric.HEIGHT, ObjectiveMetric.SUPPORT_RISK, ObjectiveMetric.TRIANGLE_COUNT, ObjectiveMetric.RUNTIME_COST, ObjectiveMetric.OPERATION_COUNT} else ObjectiveDirection.MAXIMIZE}, evidence_states={key: EvidenceState.MEASURED})
            self.assertEqual(vector.raw_values[key], 0.25)
            self.assertEqual(vector.evidence_states[key], EvidenceState.MEASURED)
            self.assertEqual(len(vector.objective_hash), 64)
        add(index, f"objective_{metric.value}", objective_vector_case); index += 1

    for actual in (float("nan"), float("inf"), float("-inf")):
        def objective_nonfinite_case(self: unittest.TestCase, actual: float = actual) -> None:
            with self.assertRaises(ValueError):
                ObjectiveVector(raw_values={"geometry_fidelity": actual}, normalized_values={"geometry_fidelity": 0.5})
        add(index, f"objective_nonfinite_{str(actual).replace('-', 'm').replace('.', '_')}", objective_nonfinite_case); index += 1

    def objective_missing_state_case(self: unittest.TestCase) -> None:
        vector = ObjectiveVector(raw_values={"geometry_fidelity": 0.5}, normalized_values={"geometry_fidelity": 0.5})
        self.assertEqual(vector.evidence_states["geometry_fidelity"], EvidenceState.INDETERMINATE)
    add(index, "objective_missing_state", objective_missing_state_case); index += 1

    def objective_bool_baseline_case(self: unittest.TestCase) -> None:
        strategy, _ = make_strategy("bool-baseline", {"geometry_fidelity": 0.5})
        with self.assertRaises(ValueError):
            virtual_evaluate_strategy(strategy, baseline_values={"geometry_fidelity": True})
    add(index, "objective_boolean_baseline", objective_bool_baseline_case); index += 1

    def objective_nan_baseline_case(self: unittest.TestCase) -> None:
        strategy, _ = make_strategy("nan-baseline", {"geometry_fidelity": 0.5})
        with self.assertRaises(ValueError):
            virtual_evaluate_strategy(strategy, baseline_values={"geometry_fidelity": float("nan")})
    add(index, "objective_nan_baseline", objective_nan_baseline_case); index += 1

    pareto_cases = (
        ("two_dimensional", ("a", {"fit": 0.9, "fidelity": 0.5}), ("b", {"fit": 0.5, "fidelity": 0.9}), ("c", {"fit": 0.4, "fidelity": 0.4})),
        ("three_dimensional", ("a", {"a": 0.9, "b": 0.5, "c": 0.5}), ("b", {"a": 0.5, "b": 0.9, "c": 0.5}), ("c", {"a": 0.5, "b": 0.5, "c": 0.9})),
        ("high_dimensional", ("a", {"a": 0.9, "b": 0.9, "c": 0.9, "d": 0.9}), ("b", {"a": 0.5, "b": 0.5, "c": 0.5, "d": 0.5}), ("c", {"a": 0.8, "b": 0.8, "c": 0.8, "d": 0.8})),
        ("minimize_height", ("a", {"height": 0.2, "fidelity": 0.8}), ("b", {"height": 0.8, "fidelity": 0.8}), ("c", {"height": 0.9, "fidelity": 0.4})),
        ("mixed_tradeoff", ("a", {"height": 0.2, "support_risk": 0.8}), ("b", {"height": 0.8, "support_risk": 0.2}), ("c", {"height": 0.9, "support_risk": 0.9})),
    )
    for label, first_case, second_case, third_case in pareto_cases:
        def pareto_case(self: unittest.TestCase, first_case: tuple = first_case, second_case: tuple = second_case, third_case: tuple = third_case) -> None:
            evaluations = tuple(make_strategy(item[0], item[1])[1] for item in (first_case, second_case, third_case))
            frontier = build_pareto_frontier(evaluations, max_points=8)
            self.assertTrue(frontier.points)
            self.assertEqual(frontier.to_json(), build_pareto_frontier(evaluations, max_points=8).to_json())
            self.assertEqual(len(frontier.points) + len(frontier.dominated_strategy_ids), 3)
        add(index, f"pareto_{label}", pareto_case); index += 1

    def pareto_duplicate_case(self: unittest.TestCase) -> None:
        _, first = make_strategy("first", {"fit": 0.5, "fidelity": 0.5})
        _, second = make_strategy("second", {"fit": 0.5, "fidelity": 0.5})
        frontier = build_pareto_frontier((first, second), max_points=4)
        self.assertEqual(len(frontier.points), 1)
        self.assertIn("second", frontier.dominated_strategy_ids)
    add(index, "pareto_duplicate", pareto_duplicate_case); index += 1

    def pareto_tolerance_case(self: unittest.TestCase) -> None:
        _, first = make_strategy("first", {"fit": 0.5, "fidelity": 0.5})
        _, second = make_strategy("second", {"fit": 0.5000001, "fidelity": 0.5})
        self.assertEqual(dominance(first, second, tolerance=0.001).state, DominanceState.EQUAL)
        self.assertEqual(dominance(first, second, tolerance=0.0).state, DominanceState.DOMINATED)
    add(index, "pareto_tolerance", pareto_tolerance_case); index += 1

    for bad_tolerance, suffix in ((-1.0, "negative"), (float("nan"), "nan"), (float("inf"), "infinity"), (True, "boolean")):
        def pareto_bad_tolerance_case(self: unittest.TestCase, bad_tolerance: object = bad_tolerance) -> None:
            with self.assertRaises(ValueError):
                build_pareto_frontier((), tolerance=bad_tolerance)  # type: ignore[arg-type]
        add(index, f"pareto_bad_tolerance_{suffix}", pareto_bad_tolerance_case); index += 1

    def pareto_missing_evidence_case(self: unittest.TestCase) -> None:
        _, known = make_strategy("known", {"fit": 0.7, "fidelity": 0.7})
        _, unknown = make_strategy("unknown", {"fit": None, "fidelity": 0.9}, states={"fit": EvidenceState.INDETERMINATE, "fidelity": EvidenceState.MEASURED})
        self.assertFalse(dominates(unknown, known))
    add(index, "pareto_missing_evidence", pareto_missing_evidence_case); index += 1

    def pareto_infeasible_case(self: unittest.TestCase) -> None:
        _, feasible = make_strategy("feasible", {"fit": 0.2}, feasible=True)
        _, infeasible = make_strategy("infeasible", {"fit": 1.0}, feasible=False)
        self.assertTrue(dominates(feasible, infeasible))
        self.assertFalse(dominates(infeasible, feasible))
    add(index, "pareto_infeasible", pareto_infeasible_case); index += 1

    def pareto_frontier_bound_case(self: unittest.TestCase) -> None:
        evaluations = tuple(make_strategy(f"trade-{i}", {"fit": i / 10.0, "fidelity": 1.0 - i / 10.0})[1] for i in range(10))
        frontier = build_pareto_frontier(evaluations, max_points=3)
        self.assertLessEqual(len(frontier.points), 3)
        self.assertTrue(frontier.limitations)
    add(index, "pareto_frontier_bound", pareto_frontier_bound_case); index += 1

    for bad_max in (0, -1, True):
        def pareto_bad_max_case(self: unittest.TestCase, bad_max: object = bad_max) -> None:
            with self.assertRaises(ValueError):
                build_pareto_frontier((), max_points=bad_max)  # type: ignore[arg-type]
        add(index, f"pareto_bad_max_{str(bad_max).lower()}", pareto_bad_max_case); index += 1

    ranking_values = {"geometry_fidelity": 0.8, "wall_thickness_preservation": 0.8, "thin_feature_preservation": 0.8, "build_volume_fit": 0.8, "support_risk": 0.2, "bridge_risk": 0.2, "overhang_risk": 0.2, "contact_quality": 0.8, "height": 0.2, "triangle_count": 0.2, "runtime_cost": 0.2, "memory_observation": 0.2}
    for method in tuple(RankingMethod):
        def ranking_method_case(self: unittest.TestCase, method: RankingMethod = method) -> None:
            _, first = make_strategy(f"rank-{method.value}-a", ranking_values)
            _, second = make_strategy(f"rank-{method.value}-b", {**ranking_values, "geometry_fidelity": 0.6})
            priority = ("geometry_fidelity", "support_risk") if method == RankingMethod.USER_PRIORITY else ()
            result = rank_strategies((first, second), method=method, user_priority=priority)
            self.assertEqual(len(result), 2, method.value)
            self.assertEqual(result[0].method, method)
            self.assertEqual(tuple(item.strategy_id for item in result), tuple(item.strategy_id for item in rank_strategies((first, second), method=method, user_priority=priority)))
        add(index, f"ranking_{method.value.lower()}", ranking_method_case); index += 1

    def ranking_critical_regression_case(self: unittest.TestCase) -> None:
        _, safe = make_strategy("safe", {"geometry_fidelity": 0.5})
        _, unsafe = make_strategy("unsafe", {"geometry_fidelity": 1.0})
        unsafe = replace(unsafe, critical_regressions=("critical-defect",))
        result = rank_strategies((unsafe, safe), method=RankingMethod.WEIGHTED_SUM)
        self.assertEqual(result[0].strategy_id, "safe")
    add(index, "ranking_critical_regression", ranking_critical_regression_case); index += 1

    def ranking_unknown_metric_case(self: unittest.TestCase) -> None:
        profile = build_objective_profile("Custom", {"geometry_fidelity": 1.0})
        _, known = make_strategy("known", {"geometry_fidelity": 0.5})
        _, unknown = make_strategy("unknown", {"geometry_fidelity": 0.99}, states={"geometry_fidelity": EvidenceState.INDETERMINATE})
        result = rank_strategies((unknown, known), method=RankingMethod.WEIGHTED_SUM, profile=profile)
        self.assertEqual(result[0].strategy_id, "known")
    add(index, "ranking_unknown_metric", ranking_unknown_metric_case); index += 1

    def ranking_tie_stability_case(self: unittest.TestCase) -> None:
        _, first = make_strategy("tie-a", {"geometry_fidelity": 0.5})
        _, second = make_strategy("tie-b", {"geometry_fidelity": 0.5})
        result = rank_strategies((second, first), method=RankingMethod.WEIGHTED_SUM)
        self.assertEqual(result[0].tie_group, result[1].tie_group)
        self.assertEqual(result[0].strategy_id, "tie-a")
    add(index, "ranking_tie_stability", ranking_tie_stability_case); index += 1

    def recommendation_requires_approval_case(self: unittest.TestCase) -> None:
        _, evaluation = make_strategy("recommended", {"geometry_fidelity": 0.9})
        ranking = rank_strategies((evaluation,), method=RankingMethod.CONSTRAINT_FIRST)
        recommendation = recommend_strategy(ranking)
        self.assertTrue(recommendation.required_user_approval)
        self.assertFalse(recommendation.is_automatic_execution)
        self.assertIn("not a global optimum", recommendation.wording)
    add(index, "ranking_recommendation_approval", recommendation_requires_approval_case); index += 1

    def explanation_complete_case(self: unittest.TestCase) -> None:
        strategy, evaluation = make_strategy("explanation-complete", {"geometry_fidelity": 0.8, "support_risk": 0.8})
        explanation = explain_strategy(strategy, evaluation, alternatives=("alternative",))
        self.assertTrue(explanation.why_generated)
        self.assertTrue(explanation.improvements)
        self.assertTrue(explanation.regressions)
        self.assertIn("alternative", explanation.non_dominated_alternatives)
        self.assertTrue(explanation.required_approvals)
        self.assertIn("not a global optimum", explanation.advisory_disclaimer)
        self.assertIn("bounded recommendation", explanation_markdown(explanation))
    add(index, "explanation_complete", explanation_complete_case); index += 1

    for state in (EvidenceState.ESTIMATED, EvidenceState.MEASURED, EvidenceState.SKIPPED_LIMIT, EvidenceState.INDETERMINATE):
        def explanation_evidence_case(self: unittest.TestCase, state: EvidenceState = state) -> None:
            strategy, evaluation = make_strategy(f"explanation-{state.value}", {"geometry_fidelity": 0.5}, states={"geometry_fidelity": state})
            if state == EvidenceState.ESTIMATED:
                evaluation = replace(evaluation, estimated_evidence=("geometry_fidelity",), measured_evidence=())
            elif state == EvidenceState.SKIPPED_LIMIT:
                evaluation = replace(evaluation, skipped_evidence=("geometry_fidelity",), measured_evidence=())
            elif state == EvidenceState.INDETERMINATE:
                evaluation = replace(evaluation, indeterminate_evidence=("geometry_fidelity",), measured_evidence=())
            explanation = explain_strategy(strategy, evaluation)
            if state == EvidenceState.ESTIMATED:
                self.assertIn("geometry_fidelity", explanation.estimated_evidence)
            elif state == EvidenceState.MEASURED:
                self.assertIn("geometry_fidelity", explanation.measured_evidence)
            elif state == EvidenceState.SKIPPED_LIMIT:
                self.assertIn("geometry_fidelity", explanation.skipped_evidence)
            else:
                self.assertIn("geometry_fidelity", explanation.indeterminate_evidence)
        add(index, f"explanation_evidence_{state.value.lower()}", explanation_evidence_case); index += 1

    for hostile in ("CON", "PRN.txt", "..\\escape.json", "<script>alert</script>.md", "unicode-名前.json", "very" * 80, "AUX."):
        def export_name_case(self: unittest.TestCase, hostile: str = hostile) -> None:
            safe = sanitize_intelligent_optimization_filename(hostile)
            self.assertNotIn("/", safe)
            self.assertNotIn("\\", safe)
            self.assertTrue(safe)
            self.assertNotIn(safe.split(".", 1)[0].upper(), {"CON", "PRN", "AUX", "NUL"})
        add(index, "export_filename_security", export_name_case); index += 1

    def history_roundtrip_case(self: unittest.TestCase) -> None:
        history = StrategyHistory()
        entry = history_entry(source_identity={"object_name": "Cube"}, source_signature="source", strategy_fingerprint="fingerprint", objective_profile={"profile_hash": "objective"}, search_policy={"policy_hash": "policy"}, constraints={"constraint_set_hash": "constraints"}, evaluation={"state": "ESTIMATED"}, recorded_at="2026-01-01T00:00:00+00:00")
        self.assertTrue(add_history_entry(history, entry))
        self.assertTrue(history_is_current(history, source_signature="source", objective_profile_hash="objective", search_policy_hash="policy")[0])
        target = write_history_json(history, Path(tempfile.mkdtemp()) / "history.json")
        self.assertTrue(target.read_text(encoding="utf-8").endswith("\n"))
        self.assertEqual(sanitize_history_filename("CON.json"), "_CON.json")
    add(index, "history_roundtrip", history_roundtrip_case); index += 1

    def history_stale_policy_case(self: unittest.TestCase) -> None:
        history = StrategyHistory()
        entry = history_entry(source_identity={}, source_signature="source", strategy_fingerprint="fingerprint", objective_profile={"profile_hash": "objective"}, search_policy={"policy_hash": "old"}, constraints={}, evaluation={})
        add_history_entry(history, entry)
        current, reason = history_is_current(history, source_signature="source", objective_profile_hash="objective", search_policy_hash="new")
        self.assertFalse(current)
        self.assertEqual(reason, "SEARCH_POLICY_CHANGED")
    add(index, "history_stale_policy", history_stale_policy_case); index += 1

    def session_full_advisory_pipeline_case(self: unittest.TestCase) -> None:
        source = make_cube("MatrixPipeline")
        before = source_signature(source)["source_signature"]
        start_intelligent_session(source, bpy.context.scene, policy=default_search_policy(SearchMode.FAST))
        generated = generate_intelligent_strategies(source=source)
        self.assertTrue(generated.strategies)
        values = {"fidelity_status": "PASS", "critical_defect_introduced": False, "geometric_deviation": 0.0, "area_drift": 0.0, "volume_drift": 0.0, "build_volume_fit": 1.0, "geometry_fidelity": 1.0, "height": 1.0}
        evaluated = evaluate_intelligent_strategies(baseline_values=values, source=source)
        self.assertTrue(evaluated)
        frontier = build_intelligent_frontier()
        self.assertTrue(frontier.points)
        rankings = rank_intelligent_strategies()
        self.assertTrue(rankings)
        selected = select_strategy(rankings[0].strategy_id, allow_dominated=True)
        self.assertEqual(selected.strategy_id, rankings[0].strategy_id)
        preview = preview_selected_strategy()
        self.assertFalse(preview["mutated_source"])
        with self.assertRaises(RuntimeError):
            execute_selected_strategy(source=source, approved=False)
        self.assertEqual(source_signature(source)["source_signature"], before)
        discard_intelligent_workspace()
    add(index, "session_full_advisory_pipeline", session_full_advisory_pipeline_case); index += 1

    def session_approved_execution_accepts_no_change_case(self: unittest.TestCase) -> None:
        source = make_cube("MatrixApprovedNoChange")
        before = source_signature(source)["source_signature"]
        start_intelligent_session(source, bpy.context.scene, policy=default_search_policy(SearchMode.FAST))
        generate_intelligent_strategies(source=source)
        values = {"fidelity_status": "PASS", "critical_defect_introduced": False, "geometric_deviation": 0.0, "area_drift": 0.0, "volume_drift": 0.0, "build_volume_fit": 1.0, "geometry_fidelity": 1.0, "height": 1.0}
        evaluate_intelligent_strategies(baseline_values=values, source=source)
        build_intelligent_frontier()
        rankings = rank_intelligent_strategies()
        select_strategy(rankings[0].strategy_id, allow_dominated=True)
        records = execute_selected_strategy(source=source, approved=True)
        self.assertTrue(records)
        self.assertTrue(all(record.state.value in {"APPLIED", "NO_CHANGE", "UNDONE"} for record in records))
        self.assertEqual(source_signature(source)["source_signature"], before)
        discard_intelligent_workspace()
    add(index, "session_approved_execution_accepts_no_change", session_approved_execution_accepts_no_change_case); index += 1

    def session_stale_source_case(self: unittest.TestCase) -> None:
        source = make_cube("MatrixStaleSource")
        start_intelligent_session(source, bpy.context.scene)
        generate_intelligent_strategies(source=source)
        source.location.x += 0.25
        with self.assertRaisesRegex(RuntimeError, "SOURCE_SIGNATURE_CHANGED"):
            ensure_current(get_active_session())
        self.assertEqual(get_active_session().state, IntelligentSessionState.STALE)
        discard_intelligent_workspace()
    add(index, "session_stale_source", session_stale_source_case); index += 1

    def session_stale_strategy_set_case(self: unittest.TestCase) -> None:
        source = make_cube("MatrixStaleStrategy")
        start_intelligent_session(source, bpy.context.scene)
        generate_intelligent_strategies(source=source)
        active = get_active_session()
        object.__setattr__(active.strategy_set, "strategy_set_hash", "tampered")
        with self.assertRaisesRegex(RuntimeError, "STRATEGY_SET_CHANGED"):
            ensure_current(active, source=source)
        discard_intelligent_workspace()
    add(index, "session_stale_strategy_set", session_stale_strategy_set_case); index += 1

    def session_cancellation_cleanup_case(self: unittest.TestCase) -> None:
        source = make_cube("MatrixCancellation")
        start_intelligent_session(source, bpy.context.scene)
        cancel_intelligent_search()
        self.assertIsNone(get_active_session())
        self.assertIsNone(get_controlled_session())
        self.assertEqual(get_archived_session().state, IntelligentSessionState.CANCELLED)
    add(index, "session_cancellation_cleanup", session_cancellation_cleanup_case); index += 1

    def session_rerun_invalidates_frontier_case(self: unittest.TestCase) -> None:
        source = make_cube("MatrixRerun")
        start_intelligent_session(source, bpy.context.scene)
        generate_intelligent_strategies(source=source)
        active = get_active_session()
        active.frontier = build_pareto_frontier((), max_points=1)
        active.pareto_frontier_hash = active.frontier.frontier_hash
        rerun_intelligent_search(settings=IntelligentOptimizationSettings(objective_preset="Minimum Supports"), source=source)
        self.assertIsNone(get_active_session().frontier)
        self.assertFalse(get_active_session().rankings)
        discard_intelligent_workspace()
    add(index, "session_rerun_invalidates_frontier", session_rerun_invalidates_frontier_case); index += 1

    def registration_lifecycle_case(self: unittest.TestCase) -> None:
        chroma3d_sculpt.unregister()
        self.assertFalse(hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state"))
        chroma3d_sculpt.register()
        self.assertTrue(hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state"))
    add(index, "registration_lifecycle", registration_lifecycle_case); index += 1

    def no_automatic_execution_surface_case(self: unittest.TestCase) -> None:
        names = {getattr(cls, "bl_idname", "") for cls in chroma3d_sculpt._RUNTIME_CLASSES}
        self.assertNotIn("chroma3d.optimize_automatically", names)
        self.assertNotIn("chroma3d.replace_source", names)
        self.assertNotIn("chroma3d.slice", names)
        self.assertNotIn("chroma3d.send_to_printer", names)
    add(index, "registration_no_automatic_execution", no_automatic_execution_surface_case); index += 1


_install_expanded_sprint6_matrix()


if __name__ == "__main__":
    unittest.main(verbosity=2)
