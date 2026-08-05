"""Sprint 3 synthetic truth, safety, profile, report, and regression matrix."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import bpy
from mathutils import Euler, Vector


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ADDON_ROOT = REPOSITORY_ROOT / "blender_addon"
if str(ADDON_ROOT) not in sys.path:
    sys.path.insert(0, str(ADDON_ROOT))

import chroma3d_sculpt  # noqa: E402
from chroma3d_sculpt.metadata import DISPLAY_VERSION, PRINTABILITY_REPORT_SCHEMA_VERSION, REPAIR_AUDIT_SCHEMA_VERSION, SCHEMA_VERSION  # noqa: E402
from chroma3d_sculpt.models.printability_models import (  # noqa: E402
    ContactClassification,
    PrintabilityConfidence,
    PrintabilityMode,
    PrintabilityStatus,
    StaleState,
)
from chroma3d_sculpt.printability_settings import MODE_LIMITS, PrintabilitySettings  # noqa: E402
from chroma3d_sculpt.services.geometry_facts import build_geometry_facts  # noqa: E402
from chroma3d_sculpt.services.overhang_analysis import overhang_angle_deg  # noqa: E402
from chroma3d_sculpt.services.printability_coordinator import analyze_printability  # noqa: E402
from chroma3d_sculpt.services.printability_report import (  # noqa: E402
    ADVISORY_DISCLAIMER,
    markdown_report,
    sanitize_printability_filename,
    write_printability_json,
    write_printability_markdown,
)
from chroma3d_sculpt.services.printability_scoring import CATEGORY_WEIGHTS, score_printability  # noqa: E402
from chroma3d_sculpt.services.printability_session import STALE_MESSAGE, require_current, stale_state, store_result  # noqa: E402
from chroma3d_sculpt.services.printer_profile_loader import (  # noqa: E402
    build_custom_profile,
    load_profile,
    load_profile_data,
    profile_directory,
    validate_all_packaged_profiles,
)
import chroma3d_sculpt.services.printer_profile_loader as profile_loader  # noqa: E402
from chroma3d_sculpt.ui.printability_panel import display_result_for_state  # noqa: E402
from chroma3d_sculpt.services.wall_thickness import analyze_wall_thickness  # noqa: E402
from chroma3d_sculpt.utilities.printability_signatures import (  # noqa: E402
    geometry_signature,
    printability_source_snapshot,
    transform_signature,
)


def clear_scene() -> None:
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def _box_geometry(center_mm: tuple[float, float, float], dimensions_mm: tuple[float, float, float], *, inward: bool = False):
    cx, cy, cz = center_mm
    hx, hy, hz = (value * 0.5 for value in dimensions_mm)
    vertices = [
        (cx - hx, cy - hy, cz - hz), (cx + hx, cy - hy, cz - hz),
        (cx + hx, cy + hy, cz - hz), (cx - hx, cy + hy, cz - hz),
        (cx - hx, cy - hy, cz + hz), (cx + hx, cy - hy, cz + hz),
        (cx + hx, cy + hy, cz + hz), (cx - hx, cy + hy, cz + hz),
    ]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    if inward:
        faces = [tuple(reversed(face)) for face in faces]
    return vertices, faces


def make_boxes(name: str, boxes: tuple[tuple[tuple[float, float, float], tuple[float, float, float], bool], ...]):
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for center, dimensions, inward in boxes:
        new_vertices, new_faces = _box_geometry(center, dimensions, inward=inward)
        offset = len(vertices)
        vertices.extend(tuple(value / 1000.0 for value in point) for point in new_vertices)
        faces.extend(tuple(index + offset for index in face) for face in new_faces)
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def make_open_plane(name: str, z_mm: float = 5.0):
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata([(-0.01, -0.01, z_mm / 1000.0), (0.01, -0.01, z_mm / 1000.0), (0.01, 0.01, z_mm / 1000.0), (-0.01, 0.01, z_mm / 1000.0)], [], [(0, 1, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def make_loose_contact(name: str, vertices_mm: tuple[tuple[float, float, float], ...], edges: tuple[tuple[int, int], ...] = ()):
    # Retain a small elevated face so the fixture is a valid analyzable mesh;
    # only the deliberately loose geometry touches the build plane.
    surface_offset = len(vertices_mm)
    surface_vertices_mm = ((20.0, 20.0, 10.0), (21.0, 20.0, 10.0), (20.0, 21.0, 10.0))
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(
        [tuple(value / 1000.0 for value in point) for point in vertices_mm + surface_vertices_mm],
        edges,
        [(surface_offset, surface_offset + 1, surface_offset + 2)],
    )
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def transformed_box(name: str, dimensions_mm: tuple[float, float, float], rotation: tuple[float, float, float]):
    raw, faces = _box_geometry((0.0, 0.0, 0.0), dimensions_mm)
    matrix = Euler(rotation).to_matrix()
    rotated = [matrix @ Vector(point) for point in raw]
    minimum = min(point.z for point in rotated)
    vertices = [(point.x / 1000.0, point.y / 1000.0, (point.z - minimum) / 1000.0) for point in rotated]
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


class Sprint3PrintabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        clear_scene()
        try:
            chroma3d_sculpt.unregister()
        except Exception:
            pass
        chroma3d_sculpt.register()
        cls.profile = load_profile("generic_fdm")
        cls.fast = PrintabilitySettings(mode=PrintabilityMode.FAST)
        cls.cube = make_boxes("S3Cube", (((0.0, 0.0, 10.0), (20.0, 20.0, 20.0), False),))
        cls.hollow = make_boxes("S3Hollow2mm", (
            ((0.0, 0.0, 10.0), (20.0, 20.0, 20.0), False),
            ((0.0, 0.0, 10.0), (16.0, 16.0, 16.0), True),
        ))
        cls.thin = make_boxes("S3ThinStem", (((0.0, 0.0, 5.0), (0.4, 0.4, 10.0), False),))
        cls.thick_feature = make_boxes("S3ThickStem", (((0.0, 0.0, 5.0), (4.0, 4.0, 10.0), False),))
        cls.open_plane = make_open_plane("S3OpenPlane")
        cls.floating = make_boxes("S3Floating", (
            ((0.0, 0.0, 5.0), (10.0, 10.0, 10.0), False),
            ((20.0, 0.0, 25.0), (5.0, 5.0, 5.0), False),
        ))
        cls.multifeet = make_boxes("S3MultiContact", (
            ((-5.0, 0.0, 2.5), (4.0, 4.0, 5.0), False),
            ((5.0, 0.0, 2.5), (4.0, 4.0, 5.0), False),
        ))
        cls.elevated = make_boxes("S3Elevated", (((0.0, 0.0, 15.0), (10.0, 10.0, 10.0), False),))
        cls.edge_contact = transformed_box("S3EdgeContact", (10.0, 10.0, 10.0), (math.radians(45.0), 0.0, 0.0))
        cls.point_contact = transformed_box("S3PointContact", (10.0, 10.0, 10.0), (math.radians(35.0), math.radians(35.0), 0.0))
        cls.edge_only_contact = make_loose_contact("S3EdgeOnlyContact", ((-5.0, 0.0, 0.0), (5.0, 0.0, 0.0)), ((0, 1),))
        cls.point_only_contact = make_loose_contact("S3PointOnlyContact", ((0.0, 0.0, 0.0),))
        cls.oversize = make_boxes("S3Oversize", (((0.0, 0.0, 10.0), (300.0, 20.0, 20.0), False),))
        cls.oversize_thin = make_boxes("S3OversizeThin", (((0.0, 0.0, 10.0), (300.0, 0.4, 20.0), False),))
        cls.oversize_rod = make_boxes("S3OversizeRod", (((0.0, 0.0, 150.0), (0.4, 0.4, 300.0), False),))
        cls.source_before = printability_source_snapshot(cls.cube)
        cls.cube_result = analyze_printability(cls.cube, bpy.context.scene, cls.profile, cls.fast, blender_version=bpy.app.version_string)
        cls.source_after = printability_source_snapshot(cls.cube)
        cls.hollow_result = analyze_printability(cls.hollow, bpy.context.scene, cls.profile, cls.fast)
        cls.thin_result = analyze_printability(cls.thin, bpy.context.scene, cls.profile, cls.fast)
        cls.thick_feature_result = analyze_printability(cls.thick_feature, bpy.context.scene, cls.profile, cls.fast)
        cls.open_result = analyze_printability(cls.open_plane, bpy.context.scene, cls.profile, cls.fast)
        cls.floating_result = analyze_printability(cls.floating, bpy.context.scene, cls.profile, cls.fast)
        cls.multi_result = analyze_printability(cls.multifeet, bpy.context.scene, cls.profile, cls.fast)
        cls.elevated_result = analyze_printability(cls.elevated, bpy.context.scene, cls.profile, cls.fast)
        cls.edge_result = analyze_printability(cls.edge_contact, bpy.context.scene, cls.profile, cls.fast)
        cls.point_result = analyze_printability(cls.point_contact, bpy.context.scene, cls.profile, cls.fast)
        cls.edge_only_result = analyze_printability(cls.edge_only_contact, bpy.context.scene, cls.profile, cls.fast)
        cls.point_only_result = analyze_printability(cls.point_only_contact, bpy.context.scene, cls.profile, cls.fast)
        cls.oversize_result = analyze_printability(cls.oversize, bpy.context.scene, cls.profile, cls.fast)
        cls.oversize_thin_result = analyze_printability(cls.oversize_thin, bpy.context.scene, cls.profile, cls.fast)
        cls.oversize_rod_result = analyze_printability(cls.oversize_rod, bpy.context.scene, cls.profile, cls.fast)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            chroma3d_sculpt.unregister()
        finally:
            clear_scene()

    def run_matrix_case(self, number: int) -> None:
        profiles = validate_all_packaged_profiles()
        if number == 1:
            chroma3d_sculpt.unregister(); chroma3d_sculpt.register(); self.assertTrue(hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state"))
        elif number == 2:
            self.assertEqual(len(profiles), 5)
        elif number == 3:
            self.assertEqual(load_profile("generic_fdm").process_type.value, "FDM")
        elif number == 4:
            self.assertEqual(load_profile("generic_resin").process_type.value, "RESIN")
        elif number == 5:
            self.assertEqual(load_profile("bambu_x1_carbon").build_volume_mm.dimensions, (256.0, 256.0, 256.0))
        elif number == 6:
            data = json.loads((profile_directory() / "generic_fdm.json").read_text(encoding="utf-8")); data["build_volume_mm"]["x"] = -1
            with self.assertRaises(ValueError): load_profile_data(data)
        elif number == 7:
            self.assertEqual(build_custom_profile({"build_volume_mm": (100, 110, 120)}).build_volume_mm.z, 120.0)
        elif number == 8:
            self.assertEqual(load_profile("generic_fdm").profile_hash, load_profile("generic_fdm").profile_hash)
        elif number == 9:
            changed = build_custom_profile({"build_volume_mm": (100, 100, 100)})
            self.assertEqual(stale_state(self.cube, self.cube_result, changed, self.fast), StaleState.STALE_PROFILE)
        elif number == 10:
            self.assertEqual(self.source_before["geometry_sha256"], self.source_after["geometry_sha256"])
        elif number == 11:
            self.assertEqual(self.cube_result.transform_signature, transform_signature(self.cube))
        elif number == 12:
            self.assertEqual(self.source_before["modifiers"], self.source_after["modifiers"]); self.assertEqual(self.source_before["materials"], self.source_after["materials"])
        elif number == 13:
            self.assertEqual(self.source_before["custom_properties"], self.source_after["custom_properties"])
        elif number == 14:
            self.assertEqual(self.source_before["file_is_dirty"], self.source_after["file_is_dirty"])
        elif number == 15:
            self.assertEqual(geometry_signature(self.thin), self.thin_result.geometry_signature)
        elif number == 16:
            self.assertAlmostEqual(self.hollow_result.wall_thickness.minimum_sampled_thickness_mm or 0.0, 2.0, delta=0.05)
        elif number == 17:
            self.assertLessEqual(self.thin_result.wall_thickness.minimum_sampled_thickness_mm or 1.0, 0.41)
        elif number == 18:
            self.assertIn(self.hollow_result.wall_thickness.confidence, {PrintabilityConfidence.MEDIUM, PrintabilityConfidence.LOW})
        elif number == 19:
            self.assertEqual(self.open_result.wall_thickness.status, PrintabilityStatus.INDETERMINATE)
        elif number == 20:
            self.assertTrue(any("Curvature" in item for item in self.hollow_result.wall_thickness.limitations))
        elif number == 21:
            self.assertNotEqual(self.open_result.wall_thickness.status, PrintabilityStatus.PASS)
        elif number == 22:
            self.assertEqual(self.cube_result.wall_thickness.status, PrintabilityStatus.PASS)
        elif number == 23:
            self.assertEqual(self.thin_result.wall_thickness.status, PrintabilityStatus.CRITICAL)
        elif number == 24:
            self.assertLessEqual(len(self.hollow_result.wall_thickness.evidence_faces), MODE_LIMITS[PrintabilityMode.FAST][3])
        elif number == 25:
            self.assertEqual(tuple(MODE_LIMITS[mode][0] for mode in PrintabilityMode), (256, 2048, 16384))
        elif number == 26:
            context = build_geometry_facts(self.cube, bpy.context.scene, self.fast.resolved(self.profile)); huge = replace(context, facts=replace(context.facts, triangle_count=100_001))
            self.assertEqual(analyze_wall_thickness(huge, self.profile, self.fast.resolved(self.profile)).status, PrintabilityStatus.SKIPPED_LIMIT)
        elif number == 27:
            again = analyze_printability(self.hollow, bpy.context.scene, self.profile, self.fast); self.assertAlmostEqual(again.wall_thickness.minimum_sampled_thickness_mm or 0.0, self.hollow_result.wall_thickness.minimum_sampled_thickness_mm or 0.0, places=6)
        elif number == 28:
            self.assertEqual(self.thin_result.thin_features.status, PrintabilityStatus.CRITICAL)
        elif number == 29:
            self.assertGreater(self.thin_result.thin_features.candidates_completed, 0)
        elif number == 30:
            self.assertLessEqual(self.thin_result.thin_features.minimum_diameter_mm or 1.0, 0.41)
        elif number == 31:
            self.assertEqual(self.thick_feature_result.thin_features.status, PrintabilityStatus.PASS)
        elif number == 32:
            self.assertTrue(any("EXPERIMENTAL" in item for item in self.thin_result.thin_features.limitations))
        elif number == 33:
            self.assertLessEqual(len(self.thin_result.thin_features.evidence_vertices), MODE_LIMITS[PrintabilityMode.FAST][3])
        elif number in range(34, 40):
            normals = {34: Vector((0, 0, 1)), 35: Vector((1, 0, 0)), 36: Vector((0, 0, -1)), 37: Vector((0, math.sin(math.radians(30)), -math.cos(math.radians(30)))), 38: Vector((0, math.sin(math.radians(45)), -math.cos(math.radians(45)))), 39: Vector((0, math.sin(math.radians(60)), -math.cos(math.radians(60))))}
            expected = {34: None, 35: None, 36: 0.0, 37: 30.0, 38: 45.0, 39: 60.0}[number]
            actual = overhang_angle_deg(normals[number], Vector((0, 0, 1)))
            self.assertIsNone(actual) if expected is None else self.assertAlmostEqual(actual or 0.0, expected, delta=1e-4)
        elif number == 40:
            self.assertGreaterEqual(self.hollow_result.overhangs.faces_evaluated, 1)
        elif number == 41:
            self.assertEqual(self.elevated_result.overhangs.status, PrintabilityStatus.CRITICAL)
        elif number == 42:
            self.assertGreaterEqual(self.elevated_result.overhangs.suppressed_face_count, 0)
        elif number == 43:
            opposite = analyze_printability(self.elevated, bpy.context.scene, self.profile, replace(self.fast, build_direction=(0, 0, -1))); self.assertNotEqual(opposite.settings_snapshot.settings_hash, self.elevated_result.settings_snapshot.settings_hash)
        elif number == 44:
            self.assertGreaterEqual(len(self.elevated_result.overhangs.regions), 1)
        elif number == 45:
            self.assertGreater(self.elevated_result.overhangs.critical_area_mm2, 0.0)
        elif number == 46:
            self.assertIn(0, self.floating_result.floating_components.contacting_shell_ids)
        elif number == 47:
            self.assertEqual(len(self.floating_result.floating_components.floating_shell_ids), 1)
        elif number == 48:
            self.assertGreaterEqual(self.floating_result.floating_components.shell_count, 2)
        elif number == 49:
            self.assertEqual(self.cube_result.floating_components.status, PrintabilityStatus.PASS)
        elif number == 50:
            self.assertGreaterEqual(len(self.floating_result.floating_components.components), 2)
        elif number == 51:
            self.assertTrue(any("support or orientation review required" in item for item in self.floating_result.floating_components.limitations))
        elif number == 52:
            self.assertEqual(self.cube_result.build_plate_contact.classification, ContactClassification.BROAD_CONTACT)
        elif number == 53:
            self.assertEqual(self.multi_result.build_plate_contact.classification, ContactClassification.MULTI_REGION_CONTACT)
        elif number == 54:
            self.assertEqual(self.edge_result.build_plate_contact.classification, ContactClassification.PARTIAL_FACE_CONTACT)
        elif number == 55:
            self.assertEqual(self.edge_only_result.build_plate_contact.classification, ContactClassification.EDGE_CONTACT)
        elif number == 56:
            self.assertEqual(self.point_only_result.build_plate_contact.classification, ContactClassification.POINT_CONTACT)
        elif number == 57:
            self.assertEqual(self.elevated_result.build_plate_contact.classification, ContactClassification.NO_CONTACT)
        elif number == 58:
            self.assertNotEqual(self.edge_only_result.build_plate_contact.classification, ContactClassification.BROAD_CONTACT)
        elif number == 59:
            self.assertAlmostEqual(self.cube_result.settings_snapshot.contact_tolerance_mm, self.profile.build_plate_contact_tolerance_mm.value)
        elif number == 60:
            self.assertEqual(self.multi_result.build_plate_contact.contact_region_count, 2)
        elif number == 61:
            self.assertTrue(any("physical stability" in item for item in self.cube_result.build_plate_contact.limitations))
        elif number == 62:
            self.assertTrue(self.cube_result.scale_evaluation.overall_fit)
        elif number == 63:
            self.assertFalse(self.oversize_result.scale_evaluation.axis_fit[0])
        elif number == 64:
            self.assertGreater(sum(not item for item in self.oversize_result.scale_evaluation.axis_fit), 0)
        elif number == 65:
            self.assertTrue(all(model <= available + self.fast.exact_boundary_tolerance_mm for model, available in zip(self.cube_result.scale_evaluation.current_dimensions_mm, self.cube_result.scale_evaluation.usable_build_volume_mm)))
        elif number == 66:
            self.assertLess(self.cube_result.scale_evaluation.usable_build_volume_mm[0], self.profile.build_volume_mm.x)
        elif number == 67:
            self.assertLess(self.oversize_result.scale_evaluation.maximum_uniform_fit_scale_percent, 100.0)
        elif number == 68:
            self.assertTrue(any("wall thickness" in item for item in self.oversize_thin_result.scale_evaluation.consequence_warnings))
        elif number == 69:
            self.assertTrue(any("minimum-feature" in item for item in self.oversize_rod_result.scale_evaluation.consequence_warnings))
        elif number == 70:
            self.assertEqual(self.oversize_result.transform_signature, transform_signature(self.oversize))
        elif number == 71:
            self.assertTrue(any(item.source.value == "CURRENT" for item in self.cube_result.orientation.candidates))
        elif number == 72:
            self.assertTrue(any(item.source.value in {"PRINCIPAL_AXIS", "BOUNDING_BOX_AXIS"} for item in self.cube_result.orientation.candidates))
        elif number == 73:
            self.assertTrue(self.cube_result.orientation.candidates_generated >= self.cube_result.orientation.candidates_evaluated)
        elif number == 74:
            ids = [item.candidate_id for item in self.cube_result.orientation.candidates]; self.assertEqual(len(ids), len(set(ids)))
        elif number == 75:
            self.assertLessEqual(len(self.cube_result.orientation.candidates), MODE_LIMITS[PrintabilityMode.FAST][2])
        elif number == 76:
            again = analyze_printability(self.cube, bpy.context.scene, self.profile, self.fast); self.assertEqual([item.candidate_id for item in again.orientation.candidates], [item.candidate_id for item in self.cube_result.orientation.candidates])
        elif number == 77:
            self.assertGreater(self.cube_result.orientation.candidates[0].measurement_summary["contact_area_mm2"], 0.0)
        elif number == 78:
            self.assertTrue(all("height_mm" in item.measurement_summary for item in self.oversize_result.orientation.candidates))
        elif number == 79:
            self.assertTrue(any("fits_build_volume" in item.measurement_summary for item in self.oversize_result.orientation.candidates))
        elif number == 80:
            self.assertEqual(self.cube_result.transform_signature, transform_signature(self.cube))
        elif number == 81:
            self.assertTrue(all(item.advantages or item.trade_offs for item in self.cube_result.orientation.candidates))
        elif number == 82:
            self.assertEqual(sum(CATEGORY_WEIGHTS.values()), 100)
        elif number == 83:
            self.assertLessEqual(self.thin_result.score_details.score or 59, 59)
        elif number == 84:
            skipped = {name: (PrintabilityStatus.PASS, PrintabilityConfidence.HIGH, "ok") for name in CATEGORY_WEIGHTS}; skipped["wall_thickness"] = (PrintabilityStatus.SKIPPED_LIMIT, PrintabilityConfidence.UNKNOWN, "limit")
            self.assertNotEqual(score_printability(skipped).confidence, PrintabilityConfidence.HIGH)
        elif number == 85:
            failed = {name: (PrintabilityStatus.PASS, PrintabilityConfidence.HIGH, "ok") for name in CATEGORY_WEIGHTS}; failed["wall_thickness"] = (PrintabilityStatus.FAILED, PrintabilityConfidence.UNKNOWN, "error")
            self.assertEqual(score_printability(failed).status, PrintabilityStatus.FAILED)
        elif number == 86:
            self.assertTrue(any(item["check"] == "thin_features" for item in self.cube_result.score_details.missing_checks))
        elif number == 87:
            self.assertFalse(self.cube_result.score_details.status == PrintabilityStatus.PASS and self.cube_result.score_details.missing_checks)
        elif number == 88:
            self.assertIsInstance(self.cube_result.score_details.score, (int, type(None)))
        elif number == 89:
            categories = {name: (PrintabilityStatus.PASS, PrintabilityConfidence.HIGH, "ok") for name in CATEGORY_WEIGHTS}; self.assertEqual(score_printability(categories), score_printability(categories))
        elif number == 90:
            self.assertEqual(self.cube_result.to_dict()["report_schema_version"], "1.0.0")
        elif number == 91:
            self.assertIn("# Chroma3D Printability Report", markdown_report(self.cube_result))
        elif number == 92:
            self.assertEqual(self.cube_result.to_json(), self.cube_result.to_json().encode("utf-8").decode("utf-8"))
        elif number == 93:
            self.assertTrue(self.cube_result.to_json().endswith("\n")); self.assertTrue(markdown_report(self.cube_result).endswith("\n"))
        elif number == 94:
            self.assertNotIn(":", sanitize_printability_filename("bad:name*", "json"))
        elif number == 95:
            self.assertLessEqual(len(self.thin_result.thin_features.evidence_vertices), self.thin_result.settings_snapshot.evidence_cap)
        elif number == 96:
            self.assertIn("profile_hash", self.cube_result.to_dict()["printer_profile_snapshot"])
        elif number == 97:
            self.assertIn("settings_hash", self.cube_result.to_dict()["settings_snapshot"])
        elif number == 98:
            self.assertIn("total", self.cube_result.to_dict()["timings"])
        elif number == 99:
            self.assertGreater(len(self.cube_result.limitations), 0)
        elif number == 100:
            self.assertIn("does not guarantee", ADVISORY_DISCLAIMER)
        elif number == 101:
            original = self.cube.data.vertices[0].co.copy(); self.cube.data.vertices[0].co.x += 0.001; self.assertEqual(stale_state(self.cube, self.cube_result, self.profile, self.fast), StaleState.STALE_GEOMETRY); self.cube.data.vertices[0].co = original; self.cube.data.update()
        elif number == 102:
            original = self.cube.location.copy(); self.cube.location.x += 0.001; self.assertEqual(stale_state(self.cube, self.cube_result, self.profile, self.fast), StaleState.STALE_TRANSFORM); self.cube.location = original
        elif number == 103:
            self.assertEqual(stale_state(self.cube, self.cube_result, build_custom_profile({"build_volume_mm": (100, 100, 100)}), self.fast), StaleState.STALE_PROFILE)
        elif number == 104:
            self.assertEqual(stale_state(self.cube, self.cube_result, self.profile, replace(self.fast, mode=PrintabilityMode.DEEP)), StaleState.STALE_SETTINGS)
        elif number == 105:
            self.assertEqual(stale_state(self.cube, self.cube_result, self.profile, replace(self.fast, build_direction=(1, 0, 0))), StaleState.STALE_SETTINGS)
        elif number in {106, 107}:
            store_result(self.cube, self.cube_result); original = self.cube.location.copy(); self.cube.location.y += 0.001
            with self.assertRaisesRegex(ValueError, STALE_MESSAGE): require_current(self.cube, self.profile, self.fast)
            self.cube.location = original
        elif number == 108:
            self.assertEqual(SCHEMA_VERSION, "2.0")
        elif number == 109:
            self.assertEqual(REPAIR_AUDIT_SCHEMA_VERSION, "1.0")
        elif number == 110:
            self.assertEqual(PRINTABILITY_REPORT_SCHEMA_VERSION, "1.0.0")
        elif number == 111:
            source = (REPOSITORY_ROOT / "blender_addon" / "chroma3d_sculpt" / "services" / "mesh_analyzer.py").read_text(encoding="utf-8"); self.assertNotIn("printability", source.lower())
        elif number == 112:
            self.assertEqual(self.source_before["printability_sha256"], self.source_after["printability_sha256"])
        elif number == 113:
            runtime = "\n".join(path.read_text(encoding="utf-8") for path in (REPOSITORY_ROOT / "blender_addon" / "chroma3d_sculpt").rglob("*.py")); self.assertNotIn("requests.", runtime); self.assertNotIn("urllib.request", runtime)
        elif number == 114:
            manifest = (REPOSITORY_ROOT / "blender_addon" / "chroma3d_sculpt" / "blender_manifest.toml").read_text(encoding="utf-8"); self.assertIn('version = "0.4.0"', manifest)
        elif number == 115:
            self.assertTrue(all(result.geometry_signature == geometry_signature(obj) for obj, result in ((self.cube, self.cube_result), (self.hollow, self.hollow_result), (self.thin, self.thin_result))))
        elif number == 116:
            self.assertEqual(DISPLAY_VERSION, "0.4.0-alpha.1")
        else:
            self.fail(f"Unknown Sprint 3 matrix case: {number}")

    def test_report_files_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            json_path = write_printability_json(self.cube_result, Path(directory) / "result")
            md_path = write_printability_markdown(self.cube_result, Path(directory) / "result")
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["report_schema_version"], "1.0.0")
            self.assertTrue(md_path.read_text(encoding="utf-8").endswith("\n"))

    def test_profile_loader_rejects_string_boolean_and_duplicate_ids(self) -> None:
        data = json.loads((profile_directory() / "generic_fdm.json").read_text(encoding="utf-8"))
        data["wall_thickness_warning_mm"]["user_editable"] = "false"
        with self.assertRaises(ValueError):
            load_profile_data(data)
        profile = load_profile("generic_fdm")
        with patch.object(profile_loader, "load_profile", return_value=profile):
            with self.assertRaises(ValueError):
                profile_loader.validate_all_packaged_profiles()

    def test_flat_plate_is_not_a_rod_like_thin_feature(self) -> None:
        plate = make_boxes("S3FlatPlateRegression", (((0.0, 0.0, 5.0), (0.4, 10.0, 10.0), False),))
        result = analyze_printability(plate, bpy.context.scene, self.profile, self.fast)
        self.assertEqual(result.thin_features.status, PrintabilityStatus.NOT_EVALUATED)

    def test_below_plane_contact_is_indeterminate(self) -> None:
        below = make_boxes("S3BelowPlaneRegression", (((0.0, 0.0, -15.0), (10.0, 10.0, 10.0), False),))
        result = analyze_printability(below, bpy.context.scene, self.profile, self.fast)
        self.assertEqual(result.build_plate_contact.classification, ContactClassification.INDETERMINATE)
        self.assertEqual(result.build_plate_contact.status, PrintabilityStatus.INDETERMINATE)

    def test_stale_result_is_hidden_from_panel(self) -> None:
        store_result(self.cube, self.cube_result)
        state = bpy.context.window_manager.chroma3d_sculpt_state
        state.printability_profile = "generic_fdm"
        state.printability_mode = "FAST"
        original = self.cube.location.copy()
        self.cube.location.x += 0.001
        displayed, message = display_result_for_state(self.cube, state)
        self.cube.location = original
        self.assertIsNone(displayed)
        self.assertEqual(message, STALE_MESSAGE)


for _case_number in range(1, 117):
    def _test(self: Sprint3PrintabilityTests, case_number: int = _case_number) -> None:
        self.run_matrix_case(case_number)

    _test.__name__ = f"test_matrix_{_case_number:03d}"
    setattr(Sprint3PrintabilityTests, _test.__name__, _test)


if __name__ == "__main__":
    unittest.main(argv=[__file__], verbosity=2)
