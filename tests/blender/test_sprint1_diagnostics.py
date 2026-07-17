"""Procedural Sprint 1 production-diagnostic tests in Blender 4.4."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import struct
import sys
import unittest

import bpy

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PARENT = REPOSITORY_ROOT / "blender_addon"
if str(SOURCE_PARENT) not in sys.path:
    sys.path.insert(0, str(SOURCE_PARENT))

import chroma3d_sculpt  # noqa: E402
from chroma3d_sculpt.analysis_settings import AnalysisSettings  # noqa: E402
from chroma3d_sculpt.models.analysis_result import (  # noqa: E402
    AnalysisProfile,
    AnalysisSeverity,
    BuildVolumeFitState,
    EvaluationStatus,
    IssueCategory,
    NormalConsistencyState,
    PrinterProfile,
    SelfIntersectionState,
    ShellContainmentState,
    ShellOrientationState,
    WatertightState,
)
from chroma3d_sculpt.services.mesh_analyzer import analyze_mesh  # noqa: E402
from chroma3d_sculpt.session import store_result  # noqa: E402


def cube_data(
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    size: float = 2.0,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    cx, cy, cz = center
    half = size / 2.0
    vertices = [
        (cx - half, cy - half, cz - half),
        (cx + half, cy - half, cz - half),
        (cx + half, cy + half, cz - half),
        (cx - half, cy + half, cz - half),
        (cx - half, cy - half, cz + half),
        (cx + half, cy - half, cz + half),
        (cx + half, cy + half, cz + half),
        (cx - half, cy + half, cz + half),
    ]
    faces = [
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    ]
    return vertices, faces


def combine_cubes(*specifications: tuple[tuple[float, float, float], float]):
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for center, size in specifications:
        cube_vertices, cube_faces = cube_data(center, size)
        offset = len(vertices)
        vertices.extend(cube_vertices)
        faces.extend(tuple(index + offset for index in face) for face in cube_faces)
    return vertices, faces


class Sprint1DiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not getattr(chroma3d_sculpt.operators.analyze_mesh.CHROMA3D_OT_analyze_mesh, "is_registered", False):
            chroma3d_sculpt.register()

    @classmethod
    def tearDownClass(cls) -> None:
        chroma3d_sculpt.unregister()

    def setUp(self) -> None:
        self.objects: list[bpy.types.Object] = []
        bpy.context.scene.unit_settings.system = "METRIC"
        bpy.context.scene.unit_settings.scale_length = 1.0
        if bpy.context.object and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

    def tearDown(self) -> None:
        if bpy.context.object and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for obj in self.objects:
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)

    def create_mesh(self, name, vertices, faces=(), edges=(), scale=(1.0, 1.0, 1.0)):
        mesh = bpy.data.meshes.new(f"{name}_Mesh")
        mesh.from_pydata(vertices, edges, faces)
        mesh.update(calc_edges=True)
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.scale = scale
        bpy.context.view_layer.update()
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        self.objects.append(obj)
        return obj

    def analyze(self, obj, settings=None):
        return analyze_mesh(
            obj,
            bpy.context.scene,
            settings=settings,
            blender_version=bpy.app.version_string,
            blend_file_path=bpy.data.filepath,
        )

    @staticmethod
    def geometry_hash(obj) -> str:
        digest = sha256()
        for vertex in obj.data.vertices:
            digest.update(struct.pack("<ddd", *tuple(float(value) for value in vertex.co)))
        for edge in obj.data.edges:
            digest.update(struct.pack("<II", *tuple(int(value) for value in edge.vertices)))
        for polygon in obj.data.polygons:
            digest.update(bytes(tuple(int(value) for value in polygon.vertices)))
        return digest.hexdigest()

    def test_01_closed_outward_cube(self):
        obj = self.create_mesh("Outward", *cube_data())
        result = self.analyze(obj)
        self.assertEqual(result.topology.watertight_state, WatertightState.TOPOLOGICALLY_WATERTIGHT)
        self.assertEqual(result.shells[0].orientation_state, ShellOrientationState.OUTWARD)

    def test_02_open_cube(self):
        vertices, faces = cube_data()
        obj = self.create_mesh("Open", vertices, faces=faces[:-1])
        result = self.analyze(obj)
        self.assertEqual(result.topology.watertight_state, WatertightState.NOT_WATERTIGHT)
        self.assertEqual(result.shells[0].orientation_state, ShellOrientationState.OPEN)

    def test_03_high_incidence_edge(self):
        obj = self.create_mesh(
            "HighIncidence",
            [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1)],
            faces=[(0, 1, 2), (1, 0, 3), (0, 1, 4)],
        )
        self.assertGreater(self.analyze(obj).topology.high_incidence_non_manifold_edges, 0)

    def test_04_bow_tie_vertex_anomaly(self):
        obj = self.create_mesh(
            "BowTie",
            [(0, 0, 0), (1, 0, 0), (0, 1, 0), (-1, 0, 0), (0, -1, 0)],
            faces=[(0, 1, 2), (0, 3, 4)],
        )
        result = self.analyze(obj)
        self.assertGreater(result.topology.vertex_manifold_anomalies, 0)

    def test_05_fully_inward_cube(self):
        vertices, faces = cube_data()
        obj = self.create_mesh("Inward", vertices, faces=[tuple(reversed(face)) for face in faces])
        self.assertEqual(self.analyze(obj).shells[0].orientation_state, ShellOrientationState.INWARD)

    def test_06_one_reversed_face(self):
        vertices, faces = cube_data()
        obj = self.create_mesh("ReversedFace", vertices, faces=[tuple(reversed(faces[0]))] + faces[1:])
        result = self.analyze(obj)
        self.assertEqual(result.topology.normal_consistency, NormalConsistencyState.INCONSISTENT)
        self.assertEqual(result.shells[0].orientation_state, ShellOrientationState.INCONSISTENT)

    def test_07_two_separated_closed_cubes(self):
        obj = self.create_mesh("TwoCubes", *combine_cubes(((-3, 0, 0), 2), ((3, 0, 0), 2)))
        result = self.analyze(obj)
        self.assertEqual(len(result.shells), 2)
        self.assertEqual(sum(shell.classification == ShellContainmentState.MAIN_SHELL for shell in result.shells), 1)

    def test_08_large_plus_tiny_cube(self):
        obj = self.create_mesh("Tiny", *combine_cubes(((0, 0, 0), 2), ((3, 0, 0), 0.002)))
        result = self.analyze(obj)
        self.assertEqual(len(result.tiny_shell_candidate_ids), 1)

    def test_09_medium_external_ornament_not_tiny(self):
        obj = self.create_mesh("Medium", *combine_cubes(((0, 0, 0), 2), ((3, 0, 0), 0.5)))
        result = self.analyze(obj)
        self.assertFalse(result.tiny_shell_candidate_ids)
        self.assertEqual(len(result.disconnected_external_shell_ids), 1)

    def test_10_closed_cube_inside_larger_cube(self):
        obj = self.create_mesh("Inside", *combine_cubes(((0, 0, 0), 4), ((0, 0, 0), 1)))
        result = self.analyze(obj, AnalysisSettings(profile=AnalysisProfile.DEEP))
        self.assertEqual(len(result.possible_internal_shell_ids), 1)
        self.assertTrue(result.deep_diagnostics.containment_evidence)

    def test_11_closed_cube_outside_larger_cube(self):
        obj = self.create_mesh("Outside", *combine_cubes(((0, 0, 0), 4), ((5, 0, 0), 1)))
        result = self.analyze(obj, AnalysisSettings(profile=AnalysisProfile.DEEP))
        self.assertFalse(result.possible_internal_shell_ids)

    def test_12_overlapping_not_contained(self):
        obj = self.create_mesh("Overlap", *combine_cubes(((0, 0, 0), 2), ((1.5, 0, 0), 1)))
        result = self.analyze(obj, AnalysisSettings(profile=AnalysisProfile.DEEP))
        self.assertFalse(result.possible_internal_shell_ids)

    def test_13_intersecting_cubes(self):
        obj = self.create_mesh("Intersecting", *combine_cubes(((0, 0, 0), 2), ((1, 0, 0), 2)))
        result = self.analyze(obj, AnalysisSettings(profile=AnalysisProfile.DEEP))
        self.assertEqual(result.deep_diagnostics.self_intersection_state, SelfIntersectionState.CANDIDATES_DETECTED)
        self.assertGreater(result.deep_diagnostics.self_intersection_candidate_count or 0, 0)

    def test_14_non_intersecting_disconnected_cubes(self):
        obj = self.create_mesh("Separate", *combine_cubes(((-3, 0, 0), 2), ((3, 0, 0), 2)))
        result = self.analyze(obj, AnalysisSettings(profile=AnalysisProfile.DEEP))
        self.assertEqual(result.deep_diagnostics.self_intersection_state, SelfIntersectionState.NO_CANDIDATES_DETECTED)

    def test_15_known_cube_surface_area(self):
        obj = self.create_mesh("Area", *cube_data(size=2))
        self.assertAlmostEqual(self.analyze(obj).surface_volume.total_surface_area_mm2, 24_000_000.0, delta=1.0)

    def test_16_known_cube_volume(self):
        obj = self.create_mesh("Volume", *cube_data(size=2))
        self.assertAlmostEqual(self.analyze(obj).surface_volume.reliable_closed_shell_volume_mm3 or 0.0, 8_000_000_000.0, delta=1.0)

    def test_17_non_uniform_scale_metrics(self):
        obj = self.create_mesh("Scaled", *cube_data(size=2), scale=(2.0, 3.0, 4.0))
        result = self.analyze(obj)
        self.assertEqual(tuple(round(value) for value in result.shells[0].dimensions_mm), (4000, 6000, 8000))
        self.assertAlmostEqual(result.surface_volume.reliable_closed_shell_volume_mm3 or 0.0, 192_000_000_000.0, delta=10.0)

    def test_18_build_volume_pass(self):
        obj = self.create_mesh("BuildPass", *cube_data(size=0.2))
        result = self.analyze(obj, AnalysisSettings(printer_profile=PrinterProfile.BAMBU_X1_CARBON))
        self.assertEqual(result.build_volume.fit_state, BuildVolumeFitState.FITS)

    def test_19_build_volume_one_axis_fail(self):
        obj = self.create_mesh("BuildFail", *cube_data(size=0.2), scale=(2.0, 1.0, 1.0))
        result = self.analyze(obj, AnalysisSettings(printer_profile=PrinterProfile.BAMBU_X1_CARBON))
        self.assertFalse(result.build_volume.fits_x)
        self.assertTrue(result.build_volume.fits_y)

    def test_20_custom_build_volume(self):
        obj = self.create_mesh("CustomBuild", *cube_data(size=0.2))
        settings = AnalysisSettings(printer_profile=PrinterProfile.CUSTOM, custom_build_volume_mm=(250, 210, 205))
        self.assertEqual(self.analyze(obj, settings).build_volume.fit_state, BuildVolumeFitState.FITS)

    def test_21_self_intersection_limit_skip(self):
        obj = self.create_mesh("SelfLimit", *cube_data())
        settings = AnalysisSettings(profile=AnalysisProfile.DEEP, self_intersection_triangle_limit=1)
        result = self.analyze(obj, settings)
        self.assertEqual(result.deep_diagnostics.self_intersection_status, EvaluationStatus.SKIPPED)
        self.assertIsNone(result.deep_diagnostics.self_intersection_candidate_count)

    def test_22_containment_limit_skip(self):
        obj = self.create_mesh("ContainLimit", *combine_cubes(((0, 0, 0), 4), ((0, 0, 0), 1)))
        settings = AnalysisSettings(profile=AnalysisProfile.DEEP, containment_shell_limit=1)
        result = self.analyze(obj, settings)
        self.assertEqual(result.deep_diagnostics.containment_status, EvaluationStatus.SKIPPED)

    def test_23_issue_evidence_truncation(self):
        vertices, faces = cube_data()
        obj = self.create_mesh("Truncated", vertices, faces=faces[:-1])
        result = self.analyze(obj, AnalysisSettings(maximum_stored_issue_indices=2))
        evidence = next(item for item in result.issue_evidence if item.category == IssueCategory.BOUNDARY_EDGES)
        self.assertGreater(evidence.total_count, len(evidence.indices))
        self.assertTrue(evidence.truncated)

    def test_24_stale_analysis_rejection(self):
        vertices, faces = cube_data()
        obj = self.create_mesh("Stale", vertices, faces=faces[:-1])
        store_result(obj, self.analyze(obj))
        obj.data.vertices.add(1)
        with self.assertRaisesRegex(RuntimeError, "Analysis is stale"):
            bpy.ops.chroma3d.select_diagnostic_issue(issue_category=IssueCategory.BOUNDARY_EDGES.value)

    def test_25_boundary_edge_issue_selection(self):
        vertices, faces = cube_data()
        obj = self.create_mesh("BoundarySelect", vertices, faces=faces[:-1])
        store_result(obj, self.analyze(obj))
        outcome = bpy.ops.chroma3d.select_diagnostic_issue(issue_category=IssueCategory.BOUNDARY_EDGES.value)
        self.assertIn("FINISHED", outcome)
        self.assertEqual(obj.mode, "EDIT")

    def test_26_face_issue_selection(self):
        vertices, faces = cube_data()
        obj = self.create_mesh("FaceSelect", vertices, faces=[tuple(reversed(faces[0]))] + faces[1:])
        store_result(obj, self.analyze(obj))
        outcome = bpy.ops.chroma3d.select_diagnostic_issue(issue_category=IssueCategory.INCONSISTENT_FACES.value)
        self.assertIn("FINISHED", outcome)

    def test_27_geometry_immutability_during_analysis(self):
        obj = self.create_mesh("ImmutableAnalysis", *cube_data())
        before = self.geometry_hash(obj)
        self.analyze(obj, AnalysisSettings(profile=AnalysisProfile.DEEP))
        self.assertEqual(before, self.geometry_hash(obj))

    def test_28_geometry_immutability_during_selection(self):
        vertices, faces = cube_data()
        obj = self.create_mesh("ImmutableSelection", vertices, faces=faces[:-1])
        before = self.geometry_hash(obj)
        transform = (tuple(obj.location), tuple(obj.rotation_euler), tuple(obj.scale), len(obj.modifiers))
        store_result(obj, self.analyze(obj))
        bpy.ops.chroma3d.select_diagnostic_issue(issue_category=IssueCategory.BOUNDARY_EDGES.value)
        self.assertEqual(before, self.geometry_hash(obj))
        self.assertEqual(transform, (tuple(obj.location), tuple(obj.rotation_euler), tuple(obj.scale), len(obj.modifiers)))

    def test_29_json_schema_2_serialization(self):
        obj = self.create_mesh("Schema", *cube_data())
        payload = json.loads(self.analyze(obj).to_json())
        self.assertEqual(payload["schema_version"], "2.0")
        for key in ("analysis_id", "settings_snapshot", "shells", "build_volume", "timings", "issue_evidence"):
            self.assertIn(key, payload)

    def test_30_registration_unregistration_reregistration(self):
        chroma3d_sculpt.unregister()
        self.assertFalse(hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state"))
        chroma3d_sculpt.register()
        self.assertTrue(hasattr(bpy.types, "CHROMA3D_OT_select_diagnostic_issue"))

    def test_31_sprint0_compatibility_fields(self):
        obj = self.create_mesh("Compatibility", *cube_data())
        payload = self.analyze(obj).to_dict()
        for key in ("geometry", "dimensions", "transforms", "topology", "checks", "warnings", "errors"):
            self.assertIn(key, payload)
        self.assertIn("connected_components", payload["topology"])

    def test_32_empty_mesh_failure(self):
        obj = self.create_mesh("Empty", [])
        self.assertEqual(self.analyze(obj).severity, AnalysisSeverity.FAIL)

    def test_33_standard_disables_deep_diagnostics(self):
        obj = self.create_mesh("Standard", *cube_data())
        result = self.analyze(obj)
        self.assertEqual(result.deep_diagnostics.self_intersection_status, EvaluationStatus.NOT_APPLICABLE)
        self.assertEqual(result.deep_diagnostics.containment_status, EvaluationStatus.NOT_APPLICABLE)

    def test_34_deep_diagnostics_run_honestly(self):
        obj = self.create_mesh("Deep", *cube_data())
        result = self.analyze(obj, AnalysisSettings(profile=AnalysisProfile.DEEP))
        self.assertIn(result.deep_diagnostics.self_intersection_status, {EvaluationStatus.COMPLETED, EvaluationStatus.SKIPPED})
        self.assertIn(result.deep_diagnostics.containment_status, {EvaluationStatus.COMPLETED, EvaluationStatus.SKIPPED})

    def test_35_no_profile_build_state(self):
        obj = self.create_mesh("NoProfile", *cube_data())
        self.assertEqual(self.analyze(obj).build_volume.status, EvaluationStatus.NOT_APPLICABLE)

    def test_36_open_tiny_shell_candidate_without_volume(self):
        large_vertices, large_faces = cube_data()
        tiny_vertices = [(3, 0, 0), (3.001, 0, 0), (3, 0.001, 0)]
        obj = self.create_mesh("OpenTiny", large_vertices + tiny_vertices, faces=large_faces + [(8, 9, 10)])
        result = self.analyze(obj)
        tiny = next(shell for shell in result.shells if shell.shell_id != result.main_shell_id)
        self.assertTrue(tiny.tiny_shell_candidate)
        self.assertIsNone(tiny.absolute_volume_mm3)

    def test_37_open_nested_shell_remains_unclassified(self):
        outer_vertices, outer_faces = cube_data(size=4)
        inner_vertices, inner_faces = cube_data(size=1)
        offset = len(outer_vertices)
        vertices = outer_vertices + inner_vertices
        faces = outer_faces + [tuple(index + offset for index in face) for face in inner_faces[:-1]]
        obj = self.create_mesh("OpenNested", vertices, faces)
        result = self.analyze(obj, AnalysisSettings(profile=AnalysisProfile.DEEP))
        open_shell = next(shell for shell in result.shells if shell.shell_id != result.main_shell_id)
        self.assertEqual(open_shell.watertight_state, WatertightState.NOT_WATERTIGHT)
        self.assertEqual(open_shell.classification, ShellContainmentState.UNCLASSIFIED)
        self.assertNotIn(open_shell.shell_id, result.disconnected_external_shell_ids)
        self.assertIn("remained unclassified", result.deep_diagnostics.notes[1])

    def test_38_exact_build_boundary_tolerates_float32_coordinates(self):
        obj = self.create_mesh("ExactBuildBoundary", *cube_data(size=0.256))
        result = self.analyze(
            obj,
            AnalysisSettings(printer_profile=PrinterProfile.BAMBU_X1_CARBON),
        )
        self.assertEqual(result.build_volume.fit_state, BuildVolumeFitState.FITS)
        self.assertEqual(result.build_volume.excess_mm, (0.0, 0.0, 0.0))
        self.assertEqual(result.build_volume.maximum_uniform_scale_percent, 100.0)

    def test_39_loose_vertex_prevents_global_watertightness(self):
        vertices, faces = cube_data()
        obj = self.create_mesh("LooseVertexWatertightness", vertices + [(4, 0, 0)], faces)
        result = self.analyze(obj)
        self.assertEqual(result.topology.loose_vertices, 1)
        self.assertEqual(result.topology.watertight_state, WatertightState.NOT_WATERTIGHT)


if __name__ == "__main__":
    outcome = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Sprint1DiagnosticTests))
    if not outcome.wasSuccessful():
        raise SystemExit(1)
