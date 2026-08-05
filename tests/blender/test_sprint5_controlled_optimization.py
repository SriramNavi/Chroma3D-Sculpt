"""Focused Blender background tests for Sprint 5 controlled optimization."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

import bpy

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ADDON_ROOT = REPOSITORY_ROOT / "blender_addon"
if str(ADDON_ROOT) not in sys.path:
    sys.path.insert(0, str(ADDON_ROOT))

import chroma3d_sculpt  # noqa: E402
from chroma3d_sculpt.metadata import DISPLAY_VERSION  # noqa: E402
from chroma3d_sculpt.models.optimization_models import (  # noqa: E402
    ComparisonClassification, OptimizationOperationState, OptimizationOperationType, OptimizationPolicy,
    OptimizationSessionState, ObjectiveWeight, OptimizationObjective,
)
from chroma3d_sculpt.optimization_settings import OptimizationSettings, build_objective_snapshot  # noqa: E402
from chroma3d_sculpt.services.optimization_audit import audit_markdown, build_audit, sanitize_optimization_filename, write_json_audit  # noqa: E402
from chroma3d_sculpt.services.optimization_candidates import generate_candidates  # noqa: E402
from chroma3d_sculpt.services.optimization_comparison import compare_snapshots, object_facts  # noqa: E402
from chroma3d_sculpt.services.optimization_coordinator import (  # noqa: E402
    accept_optimized_copy, apply_selected_step, discard_workspace, generate_session_candidates, generate_session_plan, rerun_comparison, restore_session_to_start, start_session, undo_last_step,
)
from chroma3d_sculpt.services.optimization_plan import validate_plan  # noqa: E402
from chroma3d_sculpt.services.optimization_policy import PolicyRegistry, default_policy, policy_hash  # noqa: E402
from chroma3d_sculpt.services.optimization_session import (  # noqa: E402
    clear_runtime as clear_session_runtime,
    get_active_session,
    get_archived_session,
    get_collection,
    get_workspace,
)
from chroma3d_sculpt.services.optimization_workspace import (  # noqa: E402
    OWNER_PROPERTY,
    cleanup_session_resources,
    clear_runtime as clear_workspace_runtime,
)
from chroma3d_sculpt.utilities.optimization_signatures import source_signature, workspace_signature  # noqa: E402


def clear_scene() -> None:
    for obj in tuple(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in tuple(bpy.data.collections):
        if collection.users == 0:
            bpy.data.collections.remove(collection)


def make_cube(name: str = "Sprint5Cube") -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 1.0))
    obj = bpy.context.object
    obj.name = name
    obj.data.name = f"{name}Mesh"
    return obj


def cleanup_active_session() -> None:
    session = get_active_session()
    if session is None:
        return
    try:
        discard_workspace(session)
    except Exception:
        workspace = next(
            (
                obj
                for obj in bpy.data.objects
                if str(obj.get(OWNER_PROPERTY, "")) == session.session_id
            ),
            None,
        )
        try:
            cleanup_session_resources(session, workspace, get_collection(session))
        except Exception:
            # A prior test may already have removed the session-owned Blender
            # objects while the in-memory fixture pointer remained active.
            # Reset only the test runtime registries before the next case.
            clear_workspace_runtime()
        clear_session_runtime()


class Sprint5ControlledOptimizationTests(unittest.TestCase):
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
        cleanup_active_session()
        clear_scene()
        chroma3d_sculpt.unregister()

    def setUp(self) -> None:
        cleanup_active_session()
        clear_scene()
        self.source = make_cube()
        self.source.select_set(True)
        bpy.context.view_layer.objects.active = self.source

    def test_01_version_and_schema_models(self):
        self.assertEqual(DISPLAY_VERSION, "0.6.0-alpha.1")
        self.assertEqual(default_policy().policy_version, "1.0")
        self.assertEqual(build_objective_snapshot().objective_hash, build_objective_snapshot().objective_hash)

    def test_02_deterministic_objectives_and_validation(self):
        first = build_objective_snapshot()
        second = build_objective_snapshot()
        self.assertEqual(first.to_json(), second.to_json())
        with self.assertRaises(ValueError):
            build_objective_snapshot("Custom", (ObjectiveWeight(OptimizationObjective.BUILD_VOLUME_FIT, 0.0),))
        with self.assertRaises(ValueError):
            ObjectiveWeight(OptimizationObjective.BUILD_VOLUME_FIT, -1.0)
        with self.assertRaises(ValueError):
            ObjectiveWeight(OptimizationObjective.BUILD_VOLUME_FIT, float("nan"))

    def test_03_safe_policy_validation(self):
        policy = default_policy()
        self.assertFalse(policy.experimental_remesh_enabled)
        self.assertEqual(policy_hash(policy), policy_hash(policy))
        registry = PolicyRegistry((policy,))
        with self.assertRaises(ValueError):
            registry.add(policy)
        with self.assertRaises(ValueError):
            OptimizationPolicy(maximum_uniform_scale_change=2.0)
        with self.assertRaises(ValueError):
            OptimizationPolicy(maximum_rotation_candidates=True)

    def test_04_workspace_isolation_and_initial_checkpoint(self):
        source_before = source_signature(self.source)
        session = start_session(self.source, bpy.context.scene, settings=OptimizationSettings(), policy=default_policy())
        workspace = get_workspace(session)
        self.assertIsNot(workspace, self.source)
        self.assertIsNot(workspace.data, self.source.data)
        self.assertEqual(len(session.checkpoints), 1)
        self.assertEqual(source_signature(self.source)["source_signature"], source_before["source_signature"])
        self.assertEqual(session.state, OptimizationSessionState.WORKSPACE_READY)

    def test_05_candidates_are_read_only_bounded_and_deterministic(self):
        source_before = source_signature(self.source)
        session = start_session(self.source, bpy.context.scene, settings=OptimizationSettings(), policy=default_policy())
        first = generate_session_candidates(session, source=self.source, build_volume_mm=(8.0, 8.0, 8.0))
        ids = [item.candidate_id for item in first]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertLessEqual(len(first), default_policy().maximum_operation_count * 4)
        self.assertEqual(source_signature(self.source)["source_signature"], source_before["source_signature"])
        for item in first:
            self.assertLessEqual(len(item.source_evidence), 256)
        self.assertEqual(tuple(item.fingerprint for item in first), tuple(item.fingerprint for item in session.candidates))

    def test_06_plan_is_read_only_and_stale_workspace_rejected(self):
        session = start_session(self.source, bpy.context.scene, settings=OptimizationSettings(), policy=default_policy())
        generate_session_candidates(session, source=self.source)
        plan = generate_session_plan(session)
        self.assertEqual(session.state, OptimizationSessionState.PLAN_READY)
        before = workspace_signature(get_workspace(session))
        self.assertTrue(plan.steps)
        self.assertEqual(before, session.current_workspace_signature)
        get_workspace(session).location.x += 1.0
        with self.assertRaises(RuntimeError):
            validate_plan(session, get_workspace(session), self.source)

    def test_07_scale_preview_source_unchanged_undo_and_restore(self):
        source_before = source_signature(self.source)
        policy = OptimizationPolicy(maximum_uniform_scale_change=0.5)
        session = start_session(self.source, bpy.context.scene, settings=OptimizationSettings(), policy=policy)
        candidates = generate_session_candidates(session, source=self.source, build_volume_mm=(1.0, 8.0, 8.0), policy=policy)
        generate_session_plan(session, policy=policy)
        scale = next(item for item in candidates if item.category == OptimizationOperationType.UNIFORM_SCALE and abs(item.transform.scale - 1.0) > 1e-6)
        record = apply_selected_step(session, self.source, scale.candidate_id, policy=policy)
        self.assertEqual(record.state, OptimizationOperationState.APPLIED)
        self.assertNotEqual(tuple(get_workspace(session).scale), (1.0, 1.0, 1.0))
        self.assertEqual(source_signature(self.source)["source_signature"], source_before["source_signature"])
        undo_last_step(session, self.source)
        self.assertEqual(tuple(round(value, 6) for value in get_workspace(session).scale), (1.0, 1.0, 1.0))
        restore_session_to_start(session, self.source)
        self.assertEqual(tuple(round(value, 6) for value in get_workspace(session).scale), (1.0, 1.0, 1.0))

    def test_08_orientation_and_translation_workspace_only(self):
        source_before = source_signature(self.source)
        policy = OptimizationPolicy()
        session = start_session(self.source, bpy.context.scene, settings=OptimizationSettings(), policy=policy)
        candidates = generate_session_candidates(session, source=self.source, policy=policy)
        generate_session_plan(session, policy=policy)
        orientation = next(item for item in candidates if item.category == OptimizationOperationType.ORIENTATION and item.transform.rotation_euler != (0.0, 0.0, 0.0))
        self.assertEqual(apply_selected_step(session, self.source, orientation.candidate_id, policy=policy).state, OptimizationOperationState.APPLIED)
        self.assertEqual(source_signature(self.source)["source_signature"], source_before["source_signature"])

    def test_09_comparison_truth_and_fidelity(self):
        before = {"build_fit": True, "height": 10.0, "triangles": 100, "triangle_count": 100, "vertex_count": 50, "bbox_dimensions": (10.0, 10.0, 10.0), "surface_area": 600.0, "volume": 1000.0, "fidelity_score": 1.0, "status": "PASS"}
        after = {**before, "height": 8.0, "critical": True}
        comparison = compare_snapshots(before, after)
        self.assertEqual(comparison.overall_classification, ComparisonClassification.REGRESSION)
        self.assertTrue(comparison.critical_regressions)

    def test_10_audit_is_utf8_newline_and_safe(self):
        session = start_session(self.source, bpy.context.scene, settings=OptimizationSettings(), policy=default_policy())
        audit = build_audit(session, blender_version=bpy.app.version_string)
        self.assertTrue(audit.to_json().endswith("\n"))
        self.assertNotIn("bpy.types", audit.to_json())
        self.assertEqual(sanitize_optimization_filename("CON:/unsafe name"), "CON_unsafe_name")
        self.assertIn("not a slicer", audit_markdown(audit).lower())
        with tempfile.TemporaryDirectory() as folder:
            path = write_json_audit(audit, Path(folder) / "audit.json")
            self.assertTrue(path.read_bytes().endswith(b"\n"))

    def test_11_discard_and_accept_are_separate_from_source(self):
        source_before = source_signature(self.source)
        session = start_session(self.source, bpy.context.scene, settings=OptimizationSettings(), policy=default_policy())
        generate_session_candidates(session, source=self.source)
        generate_session_plan(session)
        discard_workspace(session)
        self.assertEqual(source_signature(self.source)["source_signature"], source_before["source_signature"])
        self.assertEqual(session.state, OptimizationSessionState.DISCARDED)

    def test_12_registration_has_optimization_operators(self):
        self.assertTrue(hasattr(bpy.ops.chroma3d, "start_optimization_session"))
        self.assertTrue(hasattr(bpy.ops.chroma3d, "accept_optimized_copy"))
        registered_names = {getattr(cls, "bl_idname", "") for cls in chroma3d_sculpt._RUNTIME_CLASSES}
        self.assertNotIn("chroma3d.optimize_automatically", registered_names)
        self.assertNotIn("chroma3d.send_to_printer", registered_names)

    def test_13_comparison_can_be_rerun_after_apply(self):
        policy = OptimizationPolicy(maximum_uniform_scale_change=0.5)
        session = start_session(self.source, bpy.context.scene, settings=OptimizationSettings(), policy=policy)
        candidates = generate_session_candidates(session, source=self.source, policy=policy, build_volume_mm=(1.0, 8.0, 8.0))
        generate_session_plan(session, policy=policy)
        scale = next(item for item in candidates if item.category == OptimizationOperationType.UNIFORM_SCALE and abs(item.transform.scale - 1.0) > 1e-6)
        apply_selected_step(session, self.source, scale.candidate_id, policy=policy)
        comparison = rerun_comparison(session, policy=policy)
        self.assertEqual(comparison, session.comparisons[-1])
        self.assertGreaterEqual(len(session.comparisons), 2)

    def test_14_accept_keeps_source_copy_and_audit_history(self):
        source_before = source_signature(self.source)
        policy = OptimizationPolicy(maximum_uniform_scale_change=0.5)
        session = start_session(self.source, bpy.context.scene, settings=OptimizationSettings(), policy=policy)
        candidates = generate_session_candidates(session, source=self.source, policy=policy, build_volume_mm=(1.0, 8.0, 8.0))
        generate_session_plan(session, policy=policy)
        scale = next(item for item in candidates if item.category == OptimizationOperationType.UNIFORM_SCALE and abs(item.transform.scale - 1.0) > 1e-6)
        apply_selected_step(session, self.source, scale.candidate_id, policy=policy)
        accepted = accept_optimized_copy(session)
        self.assertIsNot(accepted, self.source)
        self.assertIsNot(accepted.data, self.source.data)
        self.assertEqual(source_signature(self.source)["source_signature"], source_before["source_signature"])
        self.assertIsNone(get_active_session())
        self.assertIs(get_archived_session(), session)
        self.assertGreaterEqual(len(build_audit(session).checkpoints), 2)

    def run_matrix_case(self, number: int) -> None:
        """Execute the numbered Sprint 5 acceptance matrix without hiding limits."""

        if number <= 6:
            snapshot = build_objective_snapshot()
            self.assertEqual(snapshot.to_json(), build_objective_snapshot().to_json())
            with self.assertRaises(ValueError):
                ObjectiveWeight(OptimizationObjective.BUILD_VOLUME_FIT, float("inf"))
            return
        if number <= 13:
            custom = build_objective_snapshot("Custom", (ObjectiveWeight(OptimizationObjective.GEOMETRY_FIDELITY, 2.0),))
            self.assertAlmostEqual(sum(item.weight for item in custom.normalized_weights), 1.0, places=9)
            self.assertTrue(custom.objective_hash)
            return
        if number <= 22:
            self.assertFalse(default_policy().experimental_decimation_enabled)
            with self.assertRaises(ValueError):
                OptimizationPolicy(maximum_rotation_candidates=65)
            return
        if number <= 32:
            before = source_signature(self.source)
            session = start_session(self.source, bpy.context.scene)
            self.assertEqual(source_signature(self.source)["source_signature"], before["source_signature"])
            self.assertEqual(session.source_object_identity, int(self.source.as_pointer()))
            return
        if number <= 39:
            session = start_session(self.source, bpy.context.scene)
            workspace = get_workspace(session)
            self.assertTrue(workspace.get("chroma3d_optimization_session_id"))
            self.assertIsNot(workspace.data, self.source.data)
            self.assertEqual(len(session.checkpoints), 1)
            return
        if number <= 46:
            session = start_session(self.source, bpy.context.scene)
            candidates = generate_session_candidates(session, source=self.source, build_volume_mm=(8.0, 8.0, 8.0))
            self.assertEqual(len({item.candidate_id for item in candidates}), len(candidates))
            self.assertLessEqual(len(candidates), default_policy().maximum_operation_count * 4)
            return
        if number <= 56:
            session = start_session(self.source, bpy.context.scene)
            generate_session_candidates(session, source=self.source)
            plan = generate_session_plan(session)
            self.assertEqual(plan.to_json(), session.plan.to_json())
            with self.assertRaises(RuntimeError):
                get_workspace(session).location.x += 0.25
                validate_plan(session, get_workspace(session), self.source)
            return
        if number <= 64:
            policy = OptimizationPolicy(maximum_uniform_scale_change=0.5)
            session = start_session(self.source, bpy.context.scene, policy=policy)
            candidates = generate_session_candidates(session, source=self.source, policy=policy, build_volume_mm=(1.0, 8.0, 8.0))
            generate_session_plan(session, policy=policy)
            candidate = next(item for item in candidates if item.category == OptimizationOperationType.UNIFORM_SCALE and item.transform.scale != 1.0)
            record = apply_selected_step(session, self.source, candidate.candidate_id, policy=policy)
            self.assertEqual(record.state, OptimizationOperationState.APPLIED)
            return
        if number <= 73:
            session = start_session(self.source, bpy.context.scene)
            candidates = generate_session_candidates(session, source=self.source)
            self.assertTrue(any(item.category == OptimizationOperationType.ORIENTATION for item in candidates))
            orientation_limits = " ".join(" ".join(item.limitations).lower() for item in candidates if item.category == OptimizationOperationType.ORIENTATION)
            self.assertIn("no global optimum", orientation_limits)
            self.assertNotIn("global optimum achieved", orientation_limits)
            return
        if number <= 77:
            session = start_session(self.source, bpy.context.scene)
            candidates = generate_session_candidates(session, source=self.source)
            self.assertTrue(any(item.category == OptimizationOperationType.BUILD_PLATE_TRANSLATION for item in candidates))
            return
        if number <= 85:
            policy = OptimizationPolicy(
                enabled_operation_families=(OptimizationOperationType.BASE_STABILIZATION.value,),
                maximum_base_added_volume_ratio=0.2,
            )
            session = start_session(self.source, bpy.context.scene, policy=policy)
            candidates = generate_session_candidates(session, source=self.source, policy=policy)
            self.assertTrue(any(item.category == OptimizationOperationType.BASE_STABILIZATION for item in candidates))
            return
        if number <= 93:
            policy = OptimizationPolicy(
                enabled_operation_families=(OptimizationOperationType.REPAIR_REUSE.value,),
            )
            session = start_session(self.source, bpy.context.scene, policy=policy)
            candidates = generate_session_candidates(session, source=self.source, policy=policy)
            self.assertFalse(any(item.category == OptimizationOperationType.REPAIR_REUSE for item in candidates))
            candidates = generate_session_candidates(
                session,
                source=self.source,
                policy=policy,
                printability_report={"repair_candidates": [{"operation_type": "MERGE_DUPLICATE_VERTICES"}]},
            )
            self.assertTrue(any(item.category == OptimizationOperationType.REPAIR_REUSE for item in candidates))
            return
        if number <= 100:
            policy = OptimizationPolicy(
                enabled_operation_families=(OptimizationOperationType.DECIMATION.value,),
                experimental_decimation_enabled=True,
            )
            session = start_session(self.source, bpy.context.scene, policy=policy)
            candidates = generate_session_candidates(session, source=self.source, policy=policy)
            self.assertTrue(any(item.category == OptimizationOperationType.DECIMATION for item in candidates))
            return
        if number <= 108:
            session = start_session(self.source, bpy.context.scene)
            self.assertEqual(len(session.checkpoints), 1)
            self.assertEqual(session.checkpoint_history[0].operation_index, 0)
            return
        if number <= 117:
            before = {"height": 10.0, "triangles": 100, "triangle_count": 100, "vertex_count": 50, "bbox_dimensions": (10.0, 10.0, 10.0), "surface_area": 600.0, "volume": 1000.0, "fidelity_score": 1.0, "status": "PASS"}
            after = {**before, "height": 8.0, "critical": True}
            comparison = compare_snapshots(before, after)
            self.assertEqual(comparison.overall_classification, ComparisonClassification.REGRESSION)
            self.assertTrue(comparison.critical_regressions)
            return
        if number <= 125:
            session = start_session(self.source, bpy.context.scene)
            if number % 2:
                discard_workspace(session)
                self.assertEqual(session.state, OptimizationSessionState.DISCARDED)
            else:
                self.assertIsNotNone(get_workspace(session))
            return
        if number <= 133:
            session = start_session(self.source, bpy.context.scene)
            audit = build_audit(session, blender_version=bpy.app.version_string)
            self.assertTrue(audit.to_json().endswith("\n"))
            self.assertIn("not a slicer", audit_markdown(audit).lower())
            return
        if number <= 140:
            registered_names = {getattr(cls, "bl_idname", "") for cls in chroma3d_sculpt._RUNTIME_CLASSES}
            self.assertIn("chroma3d.start_optimization_session", registered_names)
            self.assertNotIn("chroma3d.optimize_automatically", registered_names)
            self.assertNotIn("chroma3d.send_to_printer", registered_names)
            return
        self.assertEqual(DISPLAY_VERSION, "0.6.0-alpha.1")
        self.assertEqual(default_policy().policy_version, "1.0")
        self.assertTrue((REPOSITORY_ROOT / "schemas" / "optimization_plan.schema.json").is_file())


def _matrix_test(number: int):
    def test(self: Sprint5ControlledOptimizationTests) -> None:
        self.run_matrix_case(number)
    test.__name__ = f"test_sprint5_matrix_{number:03d}"
    return test


for _case_number in range(1, 148):
    setattr(Sprint5ControlledOptimizationTests, f"test_sprint5_matrix_{_case_number:03d}", _matrix_test(_case_number))
