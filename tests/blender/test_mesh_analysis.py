"""Procedural Sprint 0 tests executed by Blender's bundled Python."""

from __future__ import annotations

from pathlib import Path
import json
import sys
import unittest

import bpy

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PARENT = REPOSITORY_ROOT / "blender_addon"
if str(SOURCE_PARENT) not in sys.path:
    sys.path.insert(0, str(SOURCE_PARENT))

import chroma3d_sculpt  # noqa: E402
from chroma3d_sculpt.models.analysis_result import AnalysisSeverity  # noqa: E402
from chroma3d_sculpt.services.mesh_analyzer import analyze_mesh  # noqa: E402
from chroma3d_sculpt.services.report_generator import sanitize_report_filename  # noqa: E402


def cube_data(offset: tuple[float, float, float] = (0.0, 0.0, 0.0)):
    ox, oy, oz = offset
    vertices = [
        (-1 + ox, -1 + oy, -1 + oz),
        (1 + ox, -1 + oy, -1 + oz),
        (1 + ox, 1 + oy, -1 + oz),
        (-1 + ox, 1 + oy, -1 + oz),
        (-1 + ox, -1 + oy, 1 + oz),
        (1 + ox, -1 + oy, 1 + oz),
        (1 + ox, 1 + oy, 1 + oz),
        (-1 + ox, 1 + oy, 1 + oz),
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


class MeshAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.objects: list[bpy.types.Object] = []
        bpy.context.scene.unit_settings.system = "METRIC"
        bpy.context.scene.unit_settings.scale_length = 1.0

    def tearDown(self) -> None:
        for obj in self.objects:
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)

    def create_mesh(
        self,
        name: str,
        vertices,
        edges=(),
        faces=(),
        scale=(1.0, 1.0, 1.0),
    ) -> bpy.types.Object:
        mesh = bpy.data.meshes.new(f"{name}_Mesh")
        mesh.from_pydata(vertices, edges, faces)
        mesh.update(calc_edges=True)
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.scale = scale
        bpy.context.view_layer.update()
        self.objects.append(obj)
        return obj

    def analyze(self, obj: bpy.types.Object):
        return analyze_mesh(
            obj,
            bpy.context.scene,
            blender_version=bpy.app.version_string,
            blend_file_path=bpy.data.filepath,
        )

    @staticmethod
    def signature(obj: bpy.types.Object):
        mesh = obj.data
        return (
            obj.name,
            mesh.name,
            tuple(tuple(vertex.co) for vertex in mesh.vertices),
            tuple(tuple(edge.vertices) for edge in mesh.edges),
            tuple(tuple(polygon.vertices) for polygon in mesh.polygons),
            tuple(obj.location),
            tuple(obj.rotation_euler),
            tuple(obj.scale),
            obj.mode,
            obj.select_get(),
        )

    def test_registration_lifecycle(self) -> None:
        chroma3d_sculpt.register()
        try:
            self.assertTrue(hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state"))
            self.assertTrue(hasattr(bpy.types, "CHROMA3D_OT_analyze_mesh"))
        finally:
            chroma3d_sculpt.unregister()
        self.assertFalse(hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state"))

    def test_closed_cube_is_one_component_and_read_only(self) -> None:
        vertices, faces = cube_data()
        obj = self.create_mesh("ClosedCube", vertices, faces=faces)
        before = self.signature(obj)
        result = self.analyze(obj)
        self.assertEqual(result.severity, AnalysisSeverity.PASS)
        self.assertEqual(result.topology.connected_components, 1)
        self.assertEqual(result.topology.boundary_edges, 0)
        self.assertEqual(before, self.signature(obj))

    def test_open_cube_reports_boundary_edges(self) -> None:
        vertices, faces = cube_data()
        obj = self.create_mesh("OpenCube", vertices, faces=faces[:-1])
        self.assertGreater(self.analyze(obj).topology.boundary_edges, 0)

    def test_loose_vertex_is_detected(self) -> None:
        vertices, faces = cube_data()
        obj = self.create_mesh("LooseVertex", vertices + [(4.0, 4.0, 4.0)], faces=faces)
        self.assertEqual(self.analyze(obj).topology.loose_vertices, 1)

    def test_loose_edge_is_detected(self) -> None:
        vertices, faces = cube_data()
        obj = self.create_mesh(
            "LooseEdge",
            vertices + [(4.0, 0.0, 0.0), (5.0, 0.0, 0.0)],
            edges=[(8, 9)],
            faces=faces,
        )
        self.assertEqual(self.analyze(obj).topology.loose_edges, 1)

    def test_two_cubes_report_two_components(self) -> None:
        first_vertices, first_faces = cube_data((-3.0, 0.0, 0.0))
        second_vertices, second_faces = cube_data((3.0, 0.0, 0.0))
        shifted_faces = [tuple(index + 8 for index in face) for face in second_faces]
        obj = self.create_mesh("TwoCubes", first_vertices + second_vertices, faces=first_faces + shifted_faces)
        self.assertEqual(self.analyze(obj).topology.connected_components, 2)

    def test_potential_duplicate_vertex_is_detected(self) -> None:
        vertices, faces = cube_data()
        obj = self.create_mesh("DuplicateVertex", vertices + [vertices[0]], faces=faces)
        self.assertGreater(self.analyze(obj).topology.potential_duplicate_vertices, 0)

    def test_zero_length_edge_is_detected(self) -> None:
        vertices, faces = cube_data()
        obj = self.create_mesh(
            "ZeroLengthEdge",
            vertices + [(4.0, 0.0, 0.0), (4.0, 0.0, 0.0)],
            edges=[(8, 9)],
            faces=faces,
        )
        self.assertEqual(self.analyze(obj).topology.zero_length_edges, 1)

    def test_degenerate_face_is_detected(self) -> None:
        vertices, faces = cube_data()
        obj = self.create_mesh(
            "DegenerateFace",
            vertices + [(4.0, 0.0, 0.0), (5.0, 0.0, 0.0), (6.0, 0.0, 0.0)],
            faces=faces + [(8, 9, 10)],
        )
        self.assertEqual(self.analyze(obj).topology.degenerate_faces, 1)

    def test_unapplied_scale_creates_warning(self) -> None:
        vertices, faces = cube_data()
        obj = self.create_mesh("UnappliedScale", vertices, faces=faces, scale=(2.0, 1.0, 1.0))
        result = self.analyze(obj)
        self.assertFalse(result.transforms.scale_applied)
        self.assertEqual(result.severity, AnalysisSeverity.WARNING)

    def test_empty_mesh_fails(self) -> None:
        obj = self.create_mesh("EmptyMesh", [])
        self.assertEqual(self.analyze(obj).severity, AnalysisSeverity.FAIL)

    def test_report_serialization_and_windows_safe_name(self) -> None:
        vertices, faces = cube_data()
        obj = self.create_mesh("CON.txt", vertices, faces=faces)
        result = self.analyze(obj)
        payload = json.loads(result.to_json())
        self.assertEqual(payload["schema_version"], "2.0")
        self.assertEqual(payload["object_metadata"]["object_name"], "CON.txt")
        self.assertTrue(sanitize_report_filename(obj.name).startswith("_CON.txt_"))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MeshAnalysisTests)
    outcome = unittest.TextTestRunner(verbosity=2).run(suite)
    if not outcome.wasSuccessful():
        raise SystemExit(1)
    print(f"Chroma3D Blender tests passed: {outcome.testsRun}")
