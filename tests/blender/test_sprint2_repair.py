"""Procedural Sprint 2 safety and controlled-repair tests under Blender 4.4+."""

from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile
import unittest

import bpy

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PARENT = REPOSITORY_ROOT / "blender_addon"
if str(SOURCE_PARENT) not in sys.path:
    sys.path.insert(0, str(SOURCE_PARENT))

from chroma3d_sculpt.analysis_settings import AnalysisSettings  # noqa: E402
from chroma3d_sculpt.models.repair_models import (  # noqa: E402
    RepairCandidateType,
    RepairDecision,
    RepairOperationStatus,
    RepairOperationType,
    RepairPlanStatus,
    RepairSessionStatus,
)
from chroma3d_sculpt.repair_settings import RepairSettings  # noqa: E402
from chroma3d_sculpt.services.mesh_analyzer import analyze_mesh  # noqa: E402
import chroma3d_sculpt.services.repair_coordinator as repair_coordinator_module  # noqa: E402
from chroma3d_sculpt.services.repair_audit import (  # noqa: E402
    build_repair_audit,
    sanitize_repair_audit_filename,
    write_repair_audit,
)
from chroma3d_sculpt.services.repair_coordinator import (  # noqa: E402
    accept_repaired_copy,
    apply_repair_plan,
    generate_repair_plan,
    restore_workspace_to_initial,
    rollback_repair_session,
    undo_last_repair,
    validate_plan,
)
from chroma3d_sculpt.services.repair_operations import (  # noqa: E402
    collapse_zero_length_edges,
    degenerate_face_indices,
    duplicate_clusters,
    fill_selected_small_holes,
    merge_duplicate_vertices,
    orient_closed_shells_outward,
    remove_degenerate_faces,
    remove_loose_geometry,
    remove_selected_tiny_shells,
    repair_normal_consistency,
    tiny_shell_candidates,
)
from chroma3d_sculpt.services.repair_session import (  # noqa: E402
    clear_runtime,
    get_active_session,
    get_audit_session,
    get_current_analysis,
    start_session,
    workspace_object,
)
from chroma3d_sculpt.utilities.boundary_loops import detect_small_hole_candidates  # noqa: E402
from chroma3d_sculpt.utilities.repair_signatures import (  # noqa: E402
    geometry_sha256,
    protected_source_snapshot,
    repair_workspace_signature,
)


def cube_data(size: float = 1.0, offset=(0.0, 0.0, 0.0), *, open_top: bool = False, inward: bool = False):
    ox, oy, oz = offset
    vertices = [
        (ox - size, oy - size, oz - size),
        (ox + size, oy - size, oz - size),
        (ox + size, oy + size, oz - size),
        (ox - size, oy + size, oz - size),
        (ox - size, oy - size, oz + size),
        (ox + size, oy - size, oz + size),
        (ox + size, oy + size, oz + size),
        (ox - size, oy + size, oz + size),
    ]
    faces = [
        (0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
        (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7),
    ]
    if open_top:
        faces = faces[1:]
    if inward:
        faces = [tuple(reversed(face)) for face in faces]
    return vertices, faces


def combine(*parts):
    vertices = []
    faces = []
    for part_vertices, part_faces in parts:
        offset = len(vertices)
        vertices.extend(part_vertices)
        faces.extend(tuple(index + offset for index in face) for face in part_faces)
    return vertices, faces


class Sprint2RepairTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_runtime()
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in list(bpy.data.meshes):
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        bpy.context.scene.unit_settings.system = "METRIC"
        bpy.context.scene.unit_settings.scale_length = 1.0
        self.repair = RepairSettings()
        self.analysis = AnalysisSettings()

    def tearDown(self) -> None:
        clear_runtime()
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for mesh in list(bpy.data.meshes):
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)

    def create(self, name, vertices, faces=(), edges=(), scale=(1.0, 1.0, 1.0)):
        mesh = bpy.data.meshes.new(f"{name}_Mesh")
        mesh.from_pydata(vertices, edges, faces)
        mesh.update(calc_edges=True)
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.scale = scale
        bpy.context.view_layer.update()
        return obj

    def create_cube(self, name="Cube", **kwargs):
        vertices, faces = cube_data(**kwargs)
        return self.create(name, vertices, faces)

    def activate(self, obj):
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

    def start(self, obj, settings=None):
        self.activate(obj)
        return start_session(
            obj,
            bpy.context.scene,
            settings or self.repair,
            self.analysis,
            blender_version=bpy.app.version_string,
            blend_file_path=bpy.data.filepath,
        )

    def plan(self, session, settings=None):
        workspace = workspace_object(session)
        self.activate(workspace)
        return generate_repair_plan(
            session,
            bpy.context.scene,
            settings or self.repair,
            blend_file_path=bpy.data.filepath,
            active_object=workspace,
        )

    def apply_one(self, session, operation, settings=None):
        workspace = workspace_object(session)
        self.activate(workspace)
        return apply_repair_plan(
            session,
            bpy.context.scene,
            settings or self.repair,
            self.analysis,
            blend_file_path=bpy.data.filepath,
            active_object=workspace,
            single_operation=operation,
        )[0]

    # Session safety
    def test_01_start_creates_independent_object_and_mesh(self):
        source = self.create_cube()
        session = self.start(source)
        workspace = workspace_object(session)
        self.assertIsNot(workspace, source)
        self.assertIsNot(workspace.data, source.data)

    def test_02_source_signature_remains_unchanged_at_start(self):
        source = self.create_cube()
        before = protected_source_snapshot(source)["protected_sha256"]
        self.start(source)
        self.assertEqual(before, protected_source_snapshot(source)["protected_sha256"])

    def test_03_invalid_object_rejected(self):
        with self.assertRaises(ValueError):
            start_session(None, bpy.context.scene, self.repair, self.analysis, blender_version=bpy.app.version_string, blend_file_path="")

    def test_04_empty_mesh_rejected(self):
        source = self.create("Empty", [])
        with self.assertRaises(ValueError):
            self.start(source)

    def test_05_second_session_rejected(self):
        self.start(self.create_cube("First"))
        with self.assertRaises(RuntimeError):
            self.start(self.create_cube("Second", offset=(4.0, 0.0, 0.0)))

    def test_06_workspace_preserves_transform_material_and_modifier(self):
        source = self.create_cube()
        source.scale = (2.0, 1.0, 0.5)
        source.modifiers.new("Mirror", "MIRROR")
        material = bpy.data.materials.new("Material")
        source.data.materials.append(material)
        workspace = workspace_object(self.start(source))
        self.assertEqual(tuple(workspace.scale), tuple(source.scale))
        self.assertEqual(len(workspace.modifiers), 1)
        self.assertEqual(workspace.material_slots[0].material, material)

    # Plan and stale protection
    def test_07_plan_generation_changes_no_geometry(self):
        source = self.create_cube()
        session = self.start(source)
        workspace = workspace_object(session)
        before = repair_workspace_signature(workspace)
        self.plan(session)
        self.assertEqual(before, repair_workspace_signature(workspace))

    def test_08_plan_recommends_only_evidenced_operations(self):
        source = self.create_cube()
        plan = self.plan(self.start(source))
        recommended = [item for item in plan.items if item.recommended]
        self.assertEqual(recommended, [])

    def test_09_tiny_shells_and_holes_are_not_preselected(self):
        vertices, faces = combine(cube_data(), cube_data(0.001, (3.0, 0.0, 0.0)), cube_data(0.0001, (5.0, 0.0, 0.0), open_top=True))
        plan = self.plan(self.start(self.create("Candidates", vertices, faces)))
        self.assertTrue(any(candidate.candidate_type == RepairCandidateType.TINY_SHELL for candidate in plan.candidates))
        self.assertFalse(any(candidate.selected for candidate in plan.candidates))

    def test_10_workspace_modification_invalidates_plan(self):
        session = self.start(self.create_cube())
        self.plan(session)
        workspace_object(session).data.vertices[0].co.x += 0.1
        with self.assertRaises(RuntimeError):
            validate_plan(session, self.repair, blend_file_path="")

    def test_11_source_modification_invalidates_session(self):
        source = self.create_cube()
        session = self.start(source)
        self.plan(session)
        source.data.vertices[0].co.x += 0.1
        with self.assertRaisesRegex(RuntimeError, "protected source changed"):
            validate_plan(session, self.repair, blend_file_path="")

    def test_12_settings_change_invalidates_plan(self):
        session = self.start(self.create_cube())
        self.plan(session)
        changed = RepairSettings(merge_distance_mm=0.002)
        with self.assertRaises(RuntimeError):
            validate_plan(session, changed, blend_file_path="")

    # Duplicate merge
    def _duplicate_fixture(self, delta=0.0, scale=(1.0, 1.0, 1.0)):
        vertices, faces = cube_data()
        return self.create("Duplicates", vertices + [(vertices[0][0] + delta, vertices[0][1], vertices[0][2])], faces, scale=scale)

    def test_13_exact_duplicate_merge(self):
        obj = self._duplicate_fixture()
        outcome = merge_duplicate_vertices(obj, 1000.0, self.repair)
        self.assertEqual(outcome.status, RepairOperationStatus.APPLIED)
        self.assertEqual(outcome.metrics["vertices_merged"], 1)

    def test_14_near_duplicate_within_tolerance(self):
        obj = self._duplicate_fixture(0.0000005)
        self.assertEqual(len(duplicate_clusters(obj, 1000.0, self.repair.merge_distance_mm)), 1)

    def test_15_outside_tolerance_vertex_preserved(self):
        obj = self._duplicate_fixture(0.000002)
        self.assertEqual(len(duplicate_clusters(obj, 1000.0, self.repair.merge_distance_mm)), 0)

    def test_16_cell_boundary_duplicate(self):
        vertices, faces = cube_data()
        obj = self.create("Boundary", vertices + [(0.00000099, 0, 0), (0.00000101, 0, 0)], faces)
        self.assertTrue(any({8, 9}.issubset(cluster) for cluster in duplicate_clusters(obj, 1000.0, self.repair.merge_distance_mm)))

    def test_17_non_uniform_scale_duplicate(self):
        obj = self._duplicate_fixture(0.0000004, scale=(2.0, 1.0, 1.0))
        self.assertEqual(len(duplicate_clusters(obj, 1000.0, self.repair.merge_distance_mm)), 1)

    def test_18_duplicate_merge_is_idempotent(self):
        obj = self._duplicate_fixture()
        merge_duplicate_vertices(obj, 1000.0, self.repair)
        self.assertEqual(merge_duplicate_vertices(obj, 1000.0, self.repair).status, RepairOperationStatus.NO_CHANGE)

    def test_19_duplicate_repair_preserves_source(self):
        source = self._duplicate_fixture()
        before = protected_source_snapshot(source)["protected_sha256"]
        session = self.start(source)
        self.plan(session)
        self.apply_one(session, RepairOperationType.MERGE_DUPLICATE_VERTICES)
        self.assertEqual(before, protected_source_snapshot(source)["protected_sha256"])

    # Zero-length, degenerate, and loose cleanup
    def test_20_zero_length_edge_collapse(self):
        vertices, faces = cube_data()
        obj = self.create("Zero", vertices + [(3, 0, 0), (3, 0, 0)], faces, edges=[(8, 9)])
        self.assertEqual(collapse_zero_length_edges(obj, 1000.0, self.repair).metrics["vertices_collapsed"], 1)

    def test_21_multiple_zero_edges_and_idempotence(self):
        vertices, faces = cube_data()
        obj = self.create("Zeros", vertices + [(3, 0, 0)] * 3, faces, edges=[(8, 9), (9, 10)])
        outcome = collapse_zero_length_edges(obj, 1000.0, self.repair)
        self.assertEqual(outcome.metrics["vertices_collapsed"], 2)
        self.assertEqual(collapse_zero_length_edges(obj, 1000.0, self.repair).status, RepairOperationStatus.NO_CHANGE)

    def test_22_face_with_zero_edge_remains_valid_after_collapse(self):
        vertices, faces = cube_data()
        extra = [(3, 0, 0), (3, 0, 0), (4, 0, 0), (3, 1, 0)]
        obj = self.create("FaceZero", vertices + extra, faces + [(8, 9, 10, 11)])
        collapse_zero_length_edges(obj, 1000.0, self.repair)
        self.assertGreaterEqual(len(obj.data.polygons), len(faces))

    def test_23_zero_area_face_removed_without_hidden_cleanup(self):
        vertices, faces = cube_data()
        obj = self.create("Degenerate", vertices + [(3, 0, 0), (4, 0, 0), (5, 0, 0)], faces + [(8, 9, 10)])
        outcome = remove_degenerate_faces(obj, 1000.0, self.repair)
        self.assertEqual(outcome.metrics["faces_removed"], 1)
        self.assertEqual(len(obj.data.vertices), 11)

    def test_24_small_valid_face_preserved(self):
        vertices, faces = cube_data()
        obj = self.create("SmallValid", vertices + [(3, 0, 0), (3.001, 0, 0), (3, 0.001, 0)], faces + [(8, 9, 10)])
        self.assertEqual(degenerate_face_indices(obj, 1000.0, self.repair.degenerate_face_area_tolerance_mm2), ())

    def test_25_degenerate_threshold_honors_non_uniform_scale(self):
        vertices, faces = cube_data()
        obj = self.create("ScaledDegenerate", vertices + [(3, 0, 0), (3.00000001, 0, 0), (3, 0.00000001, 0)], faces + [(8, 9, 10)], scale=(2, 0.5, 1))
        self.assertEqual(len(degenerate_face_indices(obj, 1000.0, self.repair.degenerate_face_area_tolerance_mm2)), 1)

    def test_26_loose_edge_vertex_and_wire_chain_removed(self):
        vertices, faces = cube_data()
        obj = self.create("Loose", vertices + [(3, 0, 0), (4, 0, 0), (5, 0, 0), (9, 9, 9)], faces, edges=[(8, 9), (9, 10)])
        outcome = remove_loose_geometry(obj, 1000.0, self.repair)
        self.assertGreaterEqual(outcome.metrics["loose_edges_removed"], 2)
        self.assertEqual(len(obj.data.vertices), 8)

    def test_27_disconnected_face_shell_preserved_by_loose_cleanup(self):
        vertices, faces = combine(cube_data(), cube_data(0.5, (4, 0, 0)))
        obj = self.create("Shells", vertices, faces)
        before = len(obj.data.polygons)
        remove_loose_geometry(obj, 1000.0, self.repair)
        self.assertEqual(len(obj.data.polygons), before)

    def test_28_loose_cleanup_is_idempotent(self):
        obj = self.create_cube()
        self.assertEqual(remove_loose_geometry(obj, 1000.0, self.repair).status, RepairOperationStatus.NO_CHANGE)

    # Normals
    def test_29_inconsistent_face_repaired(self):
        vertices, faces = cube_data()
        faces[0] = tuple(reversed(faces[0]))
        obj = self.create("Inconsistent", vertices, faces)
        outcome = repair_normal_consistency(obj, 1000.0, self.repair)
        result = analyze_mesh(obj, bpy.context.scene)
        self.assertEqual(result.topology.normal_consistency.value, "CONSISTENT")
        self.assertTrue(outcome.metrics["vertex_coordinates_unchanged"])

    def test_30_inward_cube_oriented_outward(self):
        obj = self.create_cube("Inward", inward=True)
        outcome = orient_closed_shells_outward(obj, 1000.0, self.repair)
        self.assertEqual(outcome.metrics["shells_reoriented"], 1)
        self.assertEqual(analyze_mesh(obj, bpy.context.scene).shells[0].orientation_state.value, "OUTWARD")

    def test_31_outward_cube_unchanged(self):
        obj = self.create_cube()
        self.assertEqual(orient_closed_shells_outward(obj, 1000.0, self.repair).status, RepairOperationStatus.NO_CHANGE)

    def test_32_open_shell_is_skipped_honestly(self):
        obj = self.create_cube(open_top=True)
        outcome = orient_closed_shells_outward(obj, 1000.0, self.repair)
        self.assertGreater(outcome.metrics["shells_skipped"], 0)
        self.assertTrue(outcome.warnings)

    def test_33_normal_repairs_preserve_coordinates(self):
        obj = self.create_cube(inward=True)
        before = tuple(tuple(vertex.co) for vertex in obj.data.vertices)
        orient_closed_shells_outward(obj, 1000.0, self.repair)
        self.assertEqual(before, tuple(tuple(vertex.co) for vertex in obj.data.vertices))

    def test_33b_non_manifold_normal_component_skipped_explicitly(self):
        obj = self.create(
            "NonManifoldNormals",
            [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1)],
            [(0, 1, 2), (1, 0, 3), (0, 1, 4)],
        )
        outcome = repair_normal_consistency(obj, 1000.0, self.repair)
        self.assertEqual(outcome.metrics["components_skipped"], 1)
        self.assertTrue(outcome.warnings)

    # Tiny shells and holes
    def _tiny_fixture(self):
        vertices, faces = combine(cube_data(), cube_data(0.001, (3.0, 0.0, 0.0)))
        return self.create("TinyFixture", vertices, faces)

    def test_34_tiny_candidate_list_excludes_main_shell(self):
        obj = self._tiny_fixture()
        result = analyze_mesh(obj, bpy.context.scene)
        candidates = tiny_shell_candidates(obj, 1000.0, result, self.repair)
        self.assertEqual(len(candidates), 1)
        self.assertNotEqual(candidates[0].shell_id, result.main_shell_id)

    def test_35_medium_ornament_not_offered(self):
        vertices, faces = combine(cube_data(), cube_data(0.1, (3.0, 0.0, 0.0)))
        obj = self.create("Medium", vertices, faces)
        result = analyze_mesh(obj, bpy.context.scene)
        self.assertEqual(tiny_shell_candidates(obj, 1000.0, result, self.repair), ())

    def test_36_selected_tiny_shell_removed_unselected_retained(self):
        vertices, faces = combine(cube_data(), cube_data(0.001, (3.0, 0, 0)), cube_data(0.001, (4.0, 0, 0)))
        obj = self.create("TwoTiny", vertices, faces)
        result = analyze_mesh(obj, bpy.context.scene)
        candidates = tiny_shell_candidates(obj, 1000.0, result, self.repair)
        outcome = remove_selected_tiny_shells(obj, 1000.0, self.repair, (candidates[0],), result)
        self.assertEqual(outcome.metrics["removed_faces"], 6)
        self.assertEqual(len(obj.data.polygons), 12)

    def test_37_stale_tiny_mapping_rejected(self):
        obj = self._tiny_fixture()
        result = analyze_mesh(obj, bpy.context.scene)
        candidate = tiny_shell_candidates(obj, 1000.0, result, self.repair)[0]
        obj.data.vertices[-1].co.x += 0.1
        current = analyze_mesh(obj, bpy.context.scene)
        with self.assertRaises(ValueError):
            remove_selected_tiny_shells(obj, 1000.0, self.repair, (candidate,), current)

    def _small_hole_fixture(self, size=0.0001):
        return self.create_cube("SmallHole", size=size, open_top=True)

    def test_38_small_bounded_hole_detected(self):
        self.assertEqual(len(detect_small_hole_candidates(self._small_hole_fixture(), 1000.0, self.repair)), 1)

    def test_39_selected_small_hole_filled(self):
        obj = self._small_hole_fixture()
        candidate = detect_small_hole_candidates(obj, 1000.0, self.repair)[0]
        outcome = fill_selected_small_holes(obj, 1000.0, self.repair, (candidate,))
        self.assertGreater(outcome.metrics["new_face_count"], 0)
        self.assertEqual(detect_small_hole_candidates(obj, 1000.0, self.repair), ())

    def test_40_large_hole_rejected(self):
        obj = self.create_cube("LargeHole", size=1.0, open_top=True)
        self.assertEqual(detect_small_hole_candidates(obj, 1000.0, self.repair), ())
        rejected = detect_small_hole_candidates(obj, 1000.0, self.repair, include_rejected=True)
        self.assertTrue(rejected[0].rejection_reason)

    def test_41_branched_boundary_rejected(self):
        obj = self.create("Branched", [(0, 0, 0), (0.0001, 0, 0), (0, 0.0001, 0), (-0.0001, 0, 0), (0, -0.0001, 0)], [(0, 1, 2), (0, 3, 4)])
        candidates = detect_small_hole_candidates(obj, 1000.0, self.repair, include_rejected=True)
        self.assertTrue(any("branched" in item.rejection_reason.lower() for item in candidates))

    def test_42_unselected_hole_remains(self):
        obj = self._small_hole_fixture()
        outcome = fill_selected_small_holes(obj, 1000.0, self.repair, ())
        self.assertEqual(outcome.status, RepairOperationStatus.NO_CHANGE)
        self.assertEqual(len(detect_small_hole_candidates(obj, 1000.0, self.repair)), 1)

    def test_42b_coincident_hole_mappings_are_rejected_as_ambiguous(self):
        vertices, faces = combine(cube_data(0.0001, open_top=True), cube_data(0.0001, open_top=True))
        obj = self.create("CoincidentHoles", vertices, faces)
        candidates = detect_small_hole_candidates(obj, 1000.0, self.repair)
        self.assertEqual(len(candidates), 2)
        self.assertNotEqual(candidates[0].candidate_id, candidates[1].candidate_id)
        before = geometry_sha256(obj)
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            fill_selected_small_holes(obj, 1000.0, self.repair, (candidates[0],))
        self.assertEqual(geometry_sha256(obj), before)

    # Checkpoints and finalization
    def test_43_checkpoint_created_before_operation_and_undo_restores(self):
        source = self._duplicate_fixture()
        session = self.start(source)
        self.plan(session)
        workspace = workspace_object(session)
        initial_count = len(workspace.data.vertices)
        self.apply_one(session, RepairOperationType.MERGE_DUPLICATE_VERTICES)
        self.assertLess(len(workspace.data.vertices), initial_count)
        undo_last_repair(session, bpy.context.scene, self.analysis, blend_file_path="", active_object=workspace)
        self.assertEqual(len(workspace.data.vertices), initial_count)

    def test_44_restore_initial_workspace(self):
        source = self._duplicate_fixture()
        session = self.start(source)
        self.plan(session)
        workspace = workspace_object(session)
        initial = geometry_sha256(workspace)
        self.apply_one(session, RepairOperationType.MERGE_DUPLICATE_VERTICES)
        restore_workspace_to_initial(session, bpy.context.scene, self.analysis, blend_file_path="", active_object=workspace)
        self.assertEqual(geometry_sha256(workspace), initial)
        self.assertIsNone(session.plan)

    def test_45_failed_operation_restores_checkpoint(self):
        source = self._tiny_fixture()
        session = self.start(source)
        plan = self.plan(session)
        workspace = workspace_object(session)
        candidate = next(item for item in plan.candidates if item.candidate_type == RepairCandidateType.TINY_SHELL)
        candidate.selected = True
        candidate.mapping_sha256 = "stale"
        before = geometry_sha256(workspace)
        with self.assertRaises(ValueError):
            self.apply_one(session, RepairOperationType.REMOVE_SELECTED_TINY_SHELLS)
        self.assertEqual(geometry_sha256(workspace), before)

    def test_46_history_depth_evicts_oldest_checkpoint(self):
        settings = RepairSettings(maximum_repair_checkpoints=1)
        vertices, faces = cube_data()
        source = self.create(
            "History",
            vertices + [vertices[0], (3, 0, 0), (4, 0, 0), (5, 0, 0)],
            faces + [(9, 10, 11)],
        )
        session = self.start(source, settings)
        self.plan(session, settings)
        self.apply_one(session, RepairOperationType.MERGE_DUPLICATE_VERTICES, settings)
        self.plan(session, settings)
        self.apply_one(session, RepairOperationType.REMOVE_DEGENERATE_FACES, settings)
        retained = [item for item in session.checkpoint_records if item.retained and not item.initial]
        self.assertEqual(len(retained), 1)

    def test_47_accept_keeps_original_and_repaired_copy(self):
        source = self.create_cube()
        before = protected_source_snapshot(source)["protected_sha256"]
        session = self.start(source)
        workspace = workspace_object(session)
        accepted = accept_repaired_copy(session, bpy.context.scene, self.analysis, blend_file_path="", active_object=workspace)
        self.assertIn(source.name, bpy.data.objects)
        self.assertIn(accepted.name, bpy.data.objects)
        self.assertEqual(before, protected_source_snapshot(source)["protected_sha256"])
        self.assertEqual(session.decision, RepairDecision.ACCEPTED)

    def test_48_rollback_deletes_workspace_only(self):
        source = self.create_cube()
        unrelated = self.create_cube("Unrelated", offset=(5, 0, 0))
        session = self.start(source)
        workspace_name = session.workspace_object_name
        rollback_repair_session(session, blend_file_path="")
        self.assertNotIn(workspace_name, bpy.data.objects)
        self.assertIn(source.name, bpy.data.objects)
        self.assertIn(unrelated.name, bpy.data.objects)
        self.assertEqual(session.status, RepairSessionStatus.ROLLED_BACK)

    def test_49_accept_clears_checkpoint_meshes(self):
        session = self.start(self.create_cube())
        workspace = workspace_object(session)
        accept_repaired_copy(session, bpy.context.scene, self.analysis, blend_file_path="", active_object=workspace)
        self.assertFalse(any(record.retained for record in session.checkpoint_records))

    # Audit and regression
    def test_50_repair_audit_schema_and_trailing_newline(self):
        session = self.start(self.create_cube())
        with tempfile.TemporaryDirectory() as directory:
            path = write_repair_audit(session, Path(directory) / "audit.json")
            text = path.read_text(encoding="utf-8")
            payload = json.loads(text)
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertTrue(text.endswith("\n"))

    def test_51_audit_contains_settings_operations_comparison_and_decision(self):
        source = self._duplicate_fixture()
        session = self.start(source)
        self.plan(session)
        self.apply_one(session, RepairOperationType.MERGE_DUPLICATE_VERTICES)
        payload = build_repair_audit(session)
        data = payload["session"]
        self.assertIn("settings_snapshot", data)
        self.assertTrue(data["operation_records"])
        self.assertIsNotNone(data["comparison"])
        self.assertEqual(payload["final_decision"], "PENDING")

    def test_52_windows_safe_audit_filename(self):
        filename = sanitize_repair_audit_filename("CON:bad?.obj")
        self.assertNotIn(":", filename)
        self.assertNotIn("?", filename)
        self.assertTrue(filename.endswith("_chroma3d_repair_audit.json"))

    def test_53_analysis_schema_remains_2(self):
        self.assertEqual(analyze_mesh(self.create_cube(), bpy.context.scene).schema_version, "2.0")

    def test_54_analysis_path_remains_geometry_read_only(self):
        obj = self.create_cube()
        before = repair_workspace_signature(obj)
        analyze_mesh(obj, bpy.context.scene)
        self.assertEqual(before, repair_workspace_signature(obj))

    def test_55_source_mesh_custom_property_invalidates_session(self):
        source = self.create_cube()
        session = self.start(source)
        source.data["external_state"] = "changed"
        with self.assertRaisesRegex(RuntimeError, "protected source changed"):
            generate_repair_plan(
                session,
                bpy.context.scene,
                self.repair,
                blend_file_path="",
                active_object=workspace_object(session),
            )

    def test_56_normal_consistency_preserves_closed_shell_orientation_when_seed_is_reversed(self):
        vertices, faces = cube_data()
        faces[0] = tuple(reversed(faces[0]))
        obj = self.create("SeedReversed", vertices, faces)

        def signed_volume(target):
            total = 0.0
            for polygon in target.data.polygons:
                points = [target.data.vertices[index].co.copy() for index in polygon.vertices]
                origin = points[0]
                for index in range(1, len(points) - 1):
                    total += origin.dot(points[index].cross(points[index + 1])) / 6.0
            return total

        self.assertGreater(signed_volume(obj), 0.0)
        outcome = repair_normal_consistency(obj, 1000.0, self.repair)
        self.assertEqual(outcome.status, RepairOperationStatus.APPLIED)
        self.assertGreater(signed_volume(obj), 0.0)

    def test_57_checkpoint_creation_failure_is_audited_without_mutation(self):
        vertices, faces = cube_data()
        source = self.create("CheckpointFailure", vertices + [vertices[0]], faces)
        session = self.start(source)
        self.plan(session)
        workspace = workspace_object(session)
        before = geometry_sha256(workspace)
        original = repair_coordinator_module.create_operation_checkpoint

        def fail_checkpoint(*_args, **_kwargs):
            raise MemoryError("controlled checkpoint failure")

        repair_coordinator_module.create_operation_checkpoint = fail_checkpoint
        try:
            with self.assertRaises(MemoryError):
                self.apply_one(session, RepairOperationType.MERGE_DUPLICATE_VERTICES)
        finally:
            repair_coordinator_module.create_operation_checkpoint = original
        self.assertEqual(before, geometry_sha256(workspace))
        self.assertEqual(session.status, RepairSessionStatus.FAILED)
        self.assertEqual(session.operation_records[-1].status, RepairOperationStatus.FAILED)
        self.assertEqual(session.operation_records[-1].checkpoint_id, "")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Sprint2RepairTests)
    outcome = unittest.TextTestRunner(verbosity=2).run(suite)
    if not outcome.wasSuccessful():
        raise SystemExit(1)
    print(f"Sprint 2 Blender tests passed: {outcome.testsRun}")
