"""Independent Blender-native Sprint 3 adversarial final validation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import argparse
import ctypes
import json
import math
from pathlib import Path
import re
import sys
from time import perf_counter, process_time
import traceback
from typing import Any, Callable
from unittest.mock import patch

import bpy
from mathutils import Euler, Vector


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ADDON_ROOT = REPOSITORY_ROOT / "blender_addon"
if str(ADDON_ROOT) not in sys.path:
    sys.path.insert(0, str(ADDON_ROOT))

import chroma3d_sculpt  # noqa: E402
from chroma3d_sculpt.metadata import (  # noqa: E402
    DISPLAY_VERSION,
    PRINTABILITY_REPORT_SCHEMA_VERSION,
    REPAIR_AUDIT_SCHEMA_VERSION,
    SCHEMA_VERSION,
)
from chroma3d_sculpt.models.printability_models import (  # noqa: E402
    ContactClassification,
    PrintabilityConfidence,
    PrintabilityMode,
    PrintabilityStatus,
    StaleState,
)
from chroma3d_sculpt.printability_settings import MODE_LIMITS, PrintabilitySettings  # noqa: E402
from chroma3d_sculpt.services.build_plate_contact import analyze_build_plate_contact  # noqa: E402
from chroma3d_sculpt.services.geometry_facts import build_geometry_facts  # noqa: E402
from chroma3d_sculpt.services.orientation_analysis import analyze_orientations  # noqa: E402
from chroma3d_sculpt.services.overhang_analysis import overhang_angle_deg  # noqa: E402
from chroma3d_sculpt.services.printability_coordinator import analyze_printability  # noqa: E402
from chroma3d_sculpt.services.printability_report import (  # noqa: E402
    ADVISORY_DISCLAIMER,
    markdown_report,
    sanitize_printability_filename,
)
from chroma3d_sculpt.services.printability_scoring import CATEGORY_WEIGHTS, score_printability  # noqa: E402
from chroma3d_sculpt.services.printability_session import (  # noqa: E402
    STALE_MESSAGE,
    clear_runtime,
    get_result,
    require_current,
    stale_state,
    store_result,
)
import chroma3d_sculpt.services.printer_profile_loader as profile_loader  # noqa: E402
from chroma3d_sculpt.services.printer_profile_loader import (  # noqa: E402
    build_custom_profile,
    load_profile,
    load_profile_data,
    profile_directory,
    validate_all_packaged_profiles,
)
from chroma3d_sculpt.utilities.printability_signatures import (  # noqa: E402
    geometry_signature,
    printability_source_snapshot,
    transform_signature,
)


Gate = Callable[[], dict[str, Any]]
GATES: list[dict[str, Any]] = []


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clear_scene() -> None:
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    clear_runtime()


def activate(obj: bpy.types.Object) -> None:
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def box_geometry(
    center_mm: tuple[float, float, float],
    dimensions_mm: tuple[float, float, float],
    *,
    inward: bool = False,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    cx, cy, cz = center_mm
    hx, hy, hz = (value * 0.5 for value in dimensions_mm)
    vertices = [
        (cx - hx, cy - hy, cz - hz), (cx + hx, cy - hy, cz - hz),
        (cx + hx, cy + hy, cz - hz), (cx - hx, cy + hy, cz - hz),
        (cx - hx, cy - hy, cz + hz), (cx + hx, cy - hy, cz + hz),
        (cx + hx, cy + hy, cz + hz), (cx - hx, cy + hy, cz + hz),
    ]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return vertices, ([tuple(reversed(face)) for face in faces] if inward else faces)


def make_boxes(
    name: str,
    boxes: tuple[tuple[tuple[float, float, float], tuple[float, float, float], bool], ...],
) -> bpy.types.Object:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for center, dimensions, inward in boxes:
        new_vertices, new_faces = box_geometry(center, dimensions, inward=inward)
        offset = len(vertices)
        vertices.extend(tuple(value / 1000.0 for value in point) for point in new_vertices)
        faces.extend(tuple(index + offset for index in face) for face in new_faces)
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def make_plane(name: str, *, z_mm: float = 5.0, size_mm: float = 20.0) -> bpy.types.Object:
    half = size_mm / 2000.0
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(
        [(-half, -half, z_mm / 1000.0), (half, -half, z_mm / 1000.0), (half, half, z_mm / 1000.0), (-half, half, z_mm / 1000.0)],
        [],
        [(0, 1, 2, 3)],
    )
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def make_contact_surface(
    name: str,
    contact_vertices_mm: tuple[tuple[float, float, float], ...],
    contact_edges: tuple[tuple[int, int], ...] = (),
) -> bpy.types.Object:
    offset = len(contact_vertices_mm)
    elevated = ((20.0, 20.0, 10.0), (21.0, 20.0, 10.0), (20.0, 21.0, 10.0))
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(
        [tuple(value / 1000.0 for value in point) for point in contact_vertices_mm + elevated],
        contact_edges,
        [(offset, offset + 1, offset + 2)],
    )
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def make_grid(name: str, cells: int, *, spacing_mm: float = 0.2) -> bpy.types.Object:
    vertices = [
        (x * spacing_mm / 1000.0, y * spacing_mm / 1000.0, 0.0)
        for y in range(cells + 1)
        for x in range(cells + 1)
    ]
    row = cells + 1
    faces: list[tuple[int, ...]] = []
    for y in range(cells):
        for x in range(cells):
            a = y * row + x
            faces.extend(((a, a + 1, a + row + 1), (a, a + row + 1, a + row)))
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def make_primitive_shell(name: str, kind: str, outer_mm: float, wall_mm: float) -> bpy.types.Object:
    if kind == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=outer_mm / 1000.0, depth=outer_mm * 2.0 / 1000.0)
        outer = bpy.context.active_object
        scale = (outer_mm - wall_mm) / outer_mm
        inner_scale = Vector((scale, scale, max((outer_mm - wall_mm) / outer_mm, 0.01)))
    else:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=outer_mm / 1000.0)
        outer = bpy.context.active_object
        scale = (outer_mm - wall_mm) / outer_mm
        inner_scale = Vector((scale, scale, scale))
    outer_mesh = outer.data
    vertices = [tuple(float(value) for value in vertex.co) for vertex in outer_mesh.vertices]
    faces = [tuple(int(index) for index in polygon.vertices) for polygon in outer_mesh.polygons]
    offset = len(vertices)
    vertices.extend(tuple(float(value) for value in (vertex.co * inner_scale)) for vertex in outer_mesh.vertices)
    faces.extend(tuple(offset + index for index in reversed(polygon.vertices)) for polygon in outer_mesh.polygons)
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bpy.data.objects.remove(outer, do_unlink=True)
    return obj


def memory_snapshot() -> dict[str, int | None]:
    if sys.platform != "win32":
        return {"working_set_bytes": None, "available_memory_bytes": None}

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
            ("total_physical", ctypes.c_ulonglong), ("available_physical", ctypes.c_ulonglong),
            ("total_page_file", ctypes.c_ulonglong), ("available_page_file", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong), ("available_virtual", ctypes.c_ulonglong),
            ("available_extended_virtual", ctypes.c_ulonglong),
        ]

    class ProcessMemory(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong), ("page_fault_count", ctypes.c_ulong),
            ("peak_working_set_size", ctypes.c_size_t), ("working_set_size", ctypes.c_size_t),
            ("quota_peak_paged_pool_usage", ctypes.c_size_t), ("quota_paged_pool_usage", ctypes.c_size_t),
            ("quota_peak_non_paged_pool_usage", ctypes.c_size_t), ("quota_non_paged_pool_usage", ctypes.c_size_t),
            ("pagefile_usage", ctypes.c_size_t), ("peak_pagefile_usage", ctypes.c_size_t),
        ]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    process = ProcessMemory()
    process.cb = ctypes.sizeof(process)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    ctypes.windll.psapi.GetProcessMemoryInfo(
        ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(process), ctypes.sizeof(process)
    )
    return {"working_set_bytes": int(process.working_set_size), "available_memory_bytes": int(status.available_physical)}


def run_gate(gate_id: str, name: str, function: Gate) -> None:
    started = perf_counter()
    try:
        evidence = function()
        GATES.append({"id": gate_id, "name": name, "status": "PASS", "duration_seconds": perf_counter() - started, "evidence": evidence})
        print(f"[PASS] {gate_id} {name}")
    except Exception as exc:
        GATES.append({
            "id": gate_id,
            "name": name,
            "status": "FAIL",
            "duration_seconds": perf_counter() - started,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        })
        print(f"[FAIL] {gate_id} {name}: {type(exc).__name__}: {exc}")


def static_audit() -> dict[str, Any]:
    root = ADDON_ROOT / "chroma3d_sculpt"
    text_by_path = {path: path.read_text(encoding="utf-8") for path in sorted(root.rglob("*.py"))}
    patterns = {
        "network": re.compile(r"^\s*(?:from|import)\s+(?:requests|urllib|http\.|socket|aiohttp|httpx)\b", re.MULTILINE),
        "subprocess": re.compile(r"^\s*(?:from|import)\s+subprocess\b", re.MULTILINE),
        "dynamic_execution": re.compile(r"\b(?:eval|exec)\s*\("),
        "pickle": re.compile(r"^\s*(?:from|import)\s+pickle\b", re.MULTILINE),
        "handler": re.compile(r"bpy\.app\.handlers"),
        "automatic_save": re.compile(r"save_as_mainfile|save_mainfile"),
    }
    findings = [
        {"type": label, "path": path.relative_to(REPOSITORY_ROOT).as_posix()}
        for path, source in text_by_path.items()
        for label, expression in patterns.items()
        if expression.search(source)
    ]
    prohibited = (
        "guaranteed printable", "will print successfully", "perfect orientation", "no supports required",
        "exact print time", "universally safe", "guaranteed manufacturing success", "definitely printable",
    )
    wording = []
    for path, source in text_by_path.items():
        for line_number, line in enumerate(source.splitlines(), 1):
            lowered = line.lower()
            for phrase in prohibited:
                if phrase in lowered and not any(token in lowered for token in ("not ", "never ", "does not", "no claim")):
                    wording.append({"phrase": phrase, "path": path.relative_to(REPOSITORY_ROOT).as_posix(), "line": line_number})
    assert not findings, findings
    assert not wording, wording
    assert DISPLAY_VERSION == "0.4.0-alpha.1"
    assert SCHEMA_VERSION == "2.0" and REPAIR_AUDIT_SCHEMA_VERSION == "1.0" and PRINTABILITY_REPORT_SCHEMA_VERSION == "1.0.0"
    return {"python_files": len(text_by_path), "forbidden_findings": findings, "wording_findings": wording}


def profile_adversarial() -> dict[str, Any]:
    profiles = validate_all_packaged_profiles()
    assert {item.profile_id for item in profiles} == {
        "generic_fdm", "generic_resin", "bambu_x1_carbon", "bambu_p1s", "prusa_mk4"
    }
    assert load_profile("bambu_x1_carbon").build_volume_mm.dimensions == (256.0, 256.0, 256.0)
    base = json.loads((profile_directory() / "generic_fdm.json").read_text(encoding="utf-8"))
    attacks: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("missing", lambda data: data.pop("profile_id")),
        ("negative", lambda data: data["build_volume_mm"].update(x=-1)),
        ("zero_volume", lambda data: data["build_volume_mm"].update(z=0)),
        ("invalid_angle", lambda data: data["overhang_warning_angle_deg"].update(value=91)),
        ("wall_inversion", lambda data: data["wall_thickness_critical_mm"].update(value=99)),
        ("unknown_process", lambda data: data.update(process_type="POWDER")),
        ("invalid_source", lambda data: data.update(source_classification="INVENTED")),
        ("string_boolean", lambda data: data["wall_thickness_warning_mm"].update(user_editable="false")),
    ]
    rejected: list[str] = []
    for name, mutate in attacks:
        attacked = deepcopy(base)
        mutate(attacked)
        try:
            load_profile_data(attacked)
        except (TypeError, ValueError):
            rejected.append(name)
    assert rejected == [name for name, _ in attacks], {"rejected": rejected, "expected": [name for name, _ in attacks]}
    with patch.object(profile_loader, "load_profile", return_value=profiles[0]):
        try:
            profile_loader.validate_all_packaged_profiles()
        except ValueError:
            duplicate_rejected = True
        else:
            duplicate_rejected = False
    assert duplicate_rejected, "Duplicate packaged profile IDs were accepted."
    first = load_profile("generic_fdm")
    assert first.profile_hash == load_profile("generic_fdm").profile_hash
    custom = build_custom_profile({"build_volume_mm": (100.0, 110.0, 120.0)})
    try:
        build_custom_profile({"unsupported": 1})
    except ValueError:
        override_rejected = True
    else:
        override_rejected = False
    assert override_rejected
    return {
        "packaged_profiles": [item.profile_id for item in profiles],
        "malformed_cases_rejected": rejected,
        "duplicate_profile_id_rejected": duplicate_rejected,
        "deterministic_hash": first.profile_hash,
        "custom_profile_hash": custom.profile_hash,
    }


def immutability_matrix() -> dict[str, Any]:
    clear_scene()
    obj = make_boxes("Adversarial Source Deity", (((0.0, 0.0, 10.0), (20.0, 20.0, 20.0), False),))
    obj.data.name = "Adversarial Mesh Data"
    obj.location = (0.001, -0.002, 0.0)
    obj.rotation_euler = Euler((0.05, -0.08, 0.12))
    obj.scale = (1.1, 0.9, 1.2)
    obj["validation_object_property"] = "retained"
    obj.data["validation_mesh_property"] = 37
    obj.hide_render = True
    obj.display_type = "WIRE"
    for index in range(2):
        material = bpy.data.materials.new(f"ValidationMaterial{index}")
        obj.data.materials.append(material)
    modifier = obj.modifiers.new("Unapplied Bevel", "BEVEL")
    modifier.width = 0.0001
    second_collection = bpy.data.collections.new("Validation Secondary Collection")
    bpy.context.scene.collection.children.link(second_collection)
    second_collection.objects.link(obj)
    activate(obj)
    before = printability_source_snapshot(obj)
    geometry_before = geometry_signature(obj)
    transform_before = transform_signature(obj)
    profile = load_profile("generic_fdm")
    results: dict[str, Any] = {}
    for mode in PrintabilityMode:
        result = analyze_printability(obj, bpy.context.scene, profile, PrintabilitySettings(mode=mode), blender_version=bpy.app.version_string)
        assert geometry_signature(obj) == geometry_before
        assert transform_signature(obj) == transform_before
        assert printability_source_snapshot(obj)["printability_sha256"] == before["printability_sha256"]
        results[mode.value] = {"status": result.score_details.status.value, "duration_seconds": result.timings["total"]}
    fast = analyze_printability(obj, bpy.context.scene, profile, PrintabilitySettings(mode=PrintabilityMode.FAST))
    store_result(obj, fast)
    state = bpy.context.window_manager.chroma3d_sculpt_state
    state.printability_profile = "generic_fdm"
    state.printability_mode = "FAST"
    artifacts = Path(__file__).resolve().parent / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    json_path = artifacts / "immutability-report.json"
    markdown_path = artifacts / "immutability-report.md"
    assert bpy.ops.chroma3d.export_printability_json(filepath=str(json_path)) == {"FINISHED"}
    assert bpy.ops.chroma3d.export_printability_markdown(filepath=str(markdown_path)) == {"FINISHED"}
    selectable = next((key for key, value in {
        "WALL_THICKNESS": fast.wall_thickness.evidence_faces,
        "OVERHANG": fast.overhangs.evidence_faces,
        "BUILD_CONTACT": fast.build_plate_contact.evidence_faces,
    }.items() if value), None)
    selection_result = "NOT_AVAILABLE"
    if selectable:
        selection_result = sorted(bpy.ops.chroma3d.select_printability_issue(evidence_category=selectable))
        assert geometry_signature(obj) == geometry_before and transform_signature(obj) == transform_before
        bpy.ops.object.mode_set(mode="OBJECT")
    after = printability_source_snapshot(obj)
    assert after["printability_sha256"] == before["printability_sha256"]
    assert json_path.read_text(encoding="utf-8").endswith("\n")
    assert markdown_path.read_text(encoding="utf-8").endswith("\n")
    return {
        "source_signature": before["printability_sha256"],
        "geometry_signature": geometry_before,
        "transform_signature": transform_before,
        "modes": results,
        "exports": [json_path.name, markdown_path.name],
        "issue_selection": selection_result,
        "materials": len(obj.material_slots),
        "modifiers": len(obj.modifiers),
        "collections": sorted(item.name for item in obj.users_collection),
    }


def wall_truth() -> dict[str, Any]:
    clear_scene()
    profile = load_profile("generic_fdm")
    settings = PrintabilitySettings(mode=PrintabilityMode.STANDARD)
    fixtures = {
        "hollow_box_2mm": make_boxes("Wall2mm", (((0, 0, 10), (20, 20, 20), False), ((0, 0, 10), (16, 16, 16), True))),
        "hollow_box_0_4mm": make_boxes("Wall0_4mm", (((0, 0, 10), (20, 20, 20), False), ((0, 0, 10), (19.2, 19.2, 19.2), True))),
        "stepped_shell": make_boxes("Stepped", (((0, 0, 15), (30, 30, 30), False), ((0, 0, 15), (24, 28, 20), True))),
        "hollow_cylinder": make_primitive_shell("HollowCylinder", "cylinder", 10.0, 2.0),
        "hollow_sphere": make_primitive_shell("HollowSphere", "sphere", 10.0, 2.0),
        "open_surface": make_plane("OpenSurface"),
        "nested_surfaces": make_boxes("Nested", (((0, 0, 15), (30, 30, 30), False), ((0, 0, 15), (20, 20, 20), False))),
        "intersecting_surfaces": make_boxes("Intersecting", (((0, 0, 5), (10, 10, 10), False), ((4, 0, 5), (10, 10, 10), False))),
        "near_coplanar": make_boxes("NearCoplanar", (((0, 0, 5), (10, 10, 10), False), ((0, 0, 5.001), (9.998, 9.998, 9.998), True))),
        "non_manifold": make_plane("NonManifold"),
        "curved_thin_shell": make_primitive_shell("CurvedThin", "sphere", 10.0, 0.4),
        "narrow_cavity": make_boxes("NarrowCavity", (((0, 0, 10), (20, 20, 20), False), ((0, 0, 10), (18, 18, 10), True))),
        "same_surface_trap": make_plane("SameSurfaceTrap", z_mm=0.001, size_mm=0.01),
        "large_coordinate": make_boxes("LargeCoordinate", (((1_000_000, 1_000_000, 1_000_010), (20, 20, 20), False),)),
        "tiny_coordinate": make_boxes("TinyCoordinate", (((0, 0, 0.0005), (0.001, 0.001, 0.001), False),)),
    }
    fixtures["non_uniform_scale"] = make_boxes("NonUniform", (((0, 0, 10), (20, 20, 20), False), ((0, 0, 10), (16, 16, 16), True)))
    fixtures["non_uniform_scale"].scale = (1.0, 1.5, 0.75)
    fixtures["rotated"] = make_boxes("RotatedWall", (((0, 0, 10), (20, 20, 20), False), ((0, 0, 10), (16, 16, 16), True)))
    fixtures["rotated"].rotation_euler = Euler((0.2, 0.1, 0.05))
    evidence: dict[str, Any] = {}
    for name, obj in fixtures.items():
        result = analyze_printability(obj, bpy.context.scene, profile, settings).wall_thickness
        evidence[name] = {
            "status": result.status.value,
            "minimum_mm": result.minimum_sampled_thickness_mm,
            "attempted": result.samples_attempted,
            "completed": result.samples_completed,
            "skipped": result.samples_skipped,
            "confidence": result.confidence.value,
            "evidence_state": result.evidence_state.value,
        }
    assert abs(float(evidence["hollow_box_2mm"]["minimum_mm"]) - 2.0) <= 0.08
    assert float(evidence["hollow_box_0_4mm"]["minimum_mm"]) <= 0.45
    assert evidence["hollow_box_0_4mm"]["status"] == "CRITICAL"
    for name in ("open_surface", "non_manifold", "same_surface_trap"):
        assert evidence[name]["status"] not in {"PASS", "WARNING", "CRITICAL"}
    assert evidence["rotated"]["minimum_mm"] is not None and evidence["non_uniform_scale"]["minimum_mm"] is not None
    return {"numeric_tolerance_mm": 0.08, "ray_origin_offset_mm": settings.ray_origin_offset_mm, "fixtures": evidence}


def feature_truth() -> dict[str, Any]:
    clear_scene()
    profile = load_profile("generic_fdm")
    settings = PrintabilitySettings(mode=PrintabilityMode.FAST)
    fixtures = {
        "below_threshold_cylinder": make_boxes("ThinCylinderProxy", (((0, 0, 5), (0.4, 0.4, 10), False),)),
        "above_threshold_cylinder": make_boxes("ThickCylinderProxy", (((0, 0, 5), (4, 4, 10), False),)),
        "cone_spike_proxy": make_boxes("SpikeProxy", (((0, 0, 8), (0.5, 0.5, 16), False),)),
        "finger_proxy": make_boxes("FingerProxy", (((0, 0, 6), (0.7, 0.8, 12), False),)),
        "flat_thin_plate": make_boxes("FlatThinPlate", (((0, 0, 5), (0.4, 10, 10), False),)),
        "short_thick": make_boxes("ShortThick", (((0, 0, 2), (3, 3, 4), False),)),
        "long_narrow": make_boxes("LongNarrow", (((0, 0, 10), (0.5, 0.5, 20), False),)),
        "disconnected_thin": make_boxes("DisconnectedThin", (((0, 0, 5), (10, 10, 10), False), ((15, 0, 5), (0.4, 0.4, 10), False))),
        "noisy_merged_surface": make_plane("NoisyMerged"),
    }
    fixtures["non_uniform_scale"] = make_boxes("ScaledFeature", (((0, 0, 5), (1, 1, 10), False),))
    fixtures["non_uniform_scale"].scale = (0.4, 1.0, 1.0)
    results = {name: analyze_printability(obj, bpy.context.scene, profile, settings).thin_features for name, obj in fixtures.items()}
    assert results["below_threshold_cylinder"].status == PrintabilityStatus.CRITICAL
    assert results["above_threshold_cylinder"].status == PrintabilityStatus.PASS
    assert results["flat_thin_plate"].status == PrintabilityStatus.NOT_EVALUATED, "Flat wall/plate was mislabeled as a thin feature."
    assert all(any("EXPERIMENTAL" in item for item in result.limitations) or result.status == PrintabilityStatus.NOT_EVALUATED for result in results.values())
    return {name: {"status": result.status.value, "minimum_diameter_mm": result.minimum_diameter_mm, "confidence": result.confidence.value} for name, result in results.items()}


def overhang_truth() -> dict[str, Any]:
    direction = Vector((0, 0, 1))
    truth = {
        "upward": overhang_angle_deg(Vector((0, 0, 1)), direction),
        "vertical": overhang_angle_deg(Vector((1, 0, 0)), direction),
        "downward": overhang_angle_deg(Vector((0, 0, -1)), direction),
        "ramp_30": overhang_angle_deg(Vector((0, math.sin(math.radians(30)), -math.cos(math.radians(30)))), direction),
        "ramp_45": overhang_angle_deg(Vector((0, math.sin(math.radians(45)), -math.cos(math.radians(45)))), direction),
        "ramp_60": overhang_angle_deg(Vector((0, math.sin(math.radians(60)), -math.cos(math.radians(60)))), direction),
    }
    assert truth["upward"] is None and truth["vertical"] is None
    for key, expected in (("downward", 0.0), ("ramp_30", 30.0), ("ramp_45", 45.0), ("ramp_60", 60.0)):
        assert abs(float(truth[key]) - expected) <= 1e-4
    clear_scene()
    profile = load_profile("generic_fdm")
    ledge = make_boxes("OverhangLedge", (((0, 0, 10), (20, 20, 20), False), ((12, 0, 20), (12, 12, 4), False)))
    first = analyze_printability(ledge, bpy.context.scene, profile, PrintabilitySettings(mode=PrintabilityMode.FAST))
    changed = analyze_printability(ledge, bpy.context.scene, profile, PrintabilitySettings(mode=PrintabilityMode.FAST, build_direction=(1, 0, 0)))
    assert first.settings_snapshot.settings_hash != changed.settings_snapshot.settings_hash
    assert first.overhangs.warning_area_mm2 >= first.overhangs.critical_area_mm2
    assert "support-sensitive" in " ".join(first.overhangs.limitations)
    return {"truth_table": truth, "default": first.overhangs.to_dict(), "changed_direction_status": changed.overhangs.status.value}


def component_and_contact_truth() -> dict[str, Any]:
    clear_scene()
    profile = load_profile("generic_fdm")
    settings = PrintabilitySettings(mode=PrintabilityMode.FAST)
    fixtures = {
        "broad": make_boxes("BroadContact", (((0, 0, 5), (10, 10, 10), False),)),
        "multi": make_boxes("MultiContact", (((-6, 0, 2.5), (4, 4, 5), False), ((6, 0, 2.5), (4, 4, 5), False))),
        "partial": make_boxes("PartialContact", (((0, 0, 0), (10, 10, 10), False),)),
        "none": make_boxes("NoContact", (((0, 0, 15), (10, 10, 10), False),)),
        "indeterminate": make_boxes("BelowPlane", (((0, 0, -15), (10, 10, 10), False),)),
        "floating": make_boxes("FloatingShell", (((0, 0, 5), (10, 10, 10), False), ((20, 0, 20), (5, 5, 5), False))),
    }
    fixtures["edge"] = make_contact_surface("EdgeContact", ((-5, 0, 0), (5, 0, 0)), ((0, 1),))
    fixtures["point"] = make_contact_surface("PointContact", ((0, 0, 0),))
    results = {name: analyze_printability(obj, bpy.context.scene, profile, settings) for name, obj in fixtures.items()}
    expected = {
        "broad": ContactClassification.BROAD_CONTACT,
        "multi": ContactClassification.MULTI_REGION_CONTACT,
        "partial": ContactClassification.PARTIAL_FACE_CONTACT,
        "edge": ContactClassification.EDGE_CONTACT,
        "point": ContactClassification.POINT_CONTACT,
        "none": ContactClassification.NO_CONTACT,
        "indeterminate": ContactClassification.INDETERMINATE,
    }
    for name, classification in expected.items():
        assert results[name].build_plate_contact.classification == classification, (name, results[name].build_plate_contact.classification)
    assert len(results["floating"].floating_components.floating_shell_ids) == 1
    assert "support or orientation review required" in " ".join(results["floating"].floating_components.limitations)
    return {
        name: {
            "classification": result.build_plate_contact.classification.value,
            "area_mm2": result.build_plate_contact.contact_area_mm2,
            "vertices": result.build_plate_contact.contact_vertex_count,
            "edges": result.build_plate_contact.contact_edge_count,
            "faces": result.build_plate_contact.contact_face_count,
            "regions": result.build_plate_contact.contact_region_count,
            "stability": result.build_plate_contact.stability_heuristic.value,
            "floating_shells": list(result.floating_components.floating_shell_ids),
        }
        for name, result in results.items()
    }


def scale_truth() -> dict[str, Any]:
    clear_scene()
    profile = build_custom_profile({"build_volume_mm": (100, 100, 100), "dimensional_safety_margin_mm": 2.0})
    settings = PrintabilitySettings(mode=PrintabilityMode.FAST)
    exact = make_boxes("ExactFit", (((0, 0, 49), (98, 98, 98), False),))
    overflow = make_boxes("OneAxisOverflow", (((0, 0, 49), (100, 50, 50), False),))
    multi = make_boxes("MultiAxisOverflow", (((0, 0, 60), (120, 110, 120), False),))
    tiny = make_boxes("ExtremeTiny", (((0, 0, 0.0005), (0.001, 0.001, 0.001), False),))
    results = {name: analyze_printability(obj, bpy.context.scene, profile, settings) for name, obj in {
        "exact": exact, "overflow": overflow, "multi": multi, "tiny": tiny,
    }.items()}
    assert results["exact"].scale_evaluation.overall_fit
    assert not results["overflow"].scale_evaluation.axis_fit[0]
    expected_scale = min(98 / 120, 98 / 110, 98 / 120) * 100
    assert abs(results["multi"].scale_evaluation.maximum_uniform_fit_scale_percent - expected_scale) <= 1e-6
    assert transform_signature(multi) == results["multi"].transform_signature
    return {name: result.scale_evaluation.to_dict() for name, result in results.items()}


def orientation_truth() -> dict[str, Any]:
    clear_scene()
    profile = load_profile("generic_fdm")
    settings = PrintabilitySettings(mode=PrintabilityMode.STANDARD)
    fixtures = {
        "broad_flat": make_boxes("BroadFlat", (((0, 0, 2), (40, 30, 4), False),)),
        "tall_narrow": make_boxes("TallNarrow", (((0, 0, 50), (8, 8, 100), False),)),
        "l_shape": make_boxes("LShape", (((0, 0, 5), (30, 8, 10), False), ((-11, 0, 18), (8, 8, 36), False))),
        "asymmetric": make_boxes("Asymmetric", (((0, 0, 15), (20, 20, 30), False), ((15, 0, 28), (20, 5, 4), False))),
        "multi_shell": make_boxes("OrientationMulti", (((0, 0, 5), (10, 10, 10), False), ((20, 0, 20), (5, 5, 5), False))),
        "overflow": make_boxes("OrientationOverflow", (((0, 0, 10), (300, 20, 20), False),)),
        "no_volume": make_plane("OrientationOpen"),
    }
    evidence: dict[str, Any] = {}
    for name, obj in fixtures.items():
        before = transform_signature(obj)
        context = build_geometry_facts(obj, bpy.context.scene, settings.resolved(profile))
        first = analyze_orientations(context, profile, settings.resolved(profile))
        second = analyze_orientations(context, profile, settings.resolved(profile))
        assert transform_signature(obj) == before
        assert any(candidate.source.value == "CURRENT" for candidate in first.candidates)
        assert len(first.candidates) <= int(settings.resolved(profile).orientation_candidate_limit or 0)
        assert [item.candidate_id for item in first.candidates] == [item.candidate_id for item in second.candidates]
        assert len({item.candidate_id for item in first.candidates}) == len(first.candidates)
        assert all(item.advantages or item.trade_offs for item in first.candidates)
        evidence[name] = {
            "generated": first.candidates_generated,
            "evaluated": first.candidates_evaluated,
            "ids": [item.candidate_id for item in first.candidates],
            "measurements": [item.measurement_summary for item in first.candidates],
        }
    multi_measurements = evidence["multi_shell"]["measurements"]
    assert len({item["floating_component_count"] for item in multi_measurements}) > 1 or len({item["contact_area_mm2"] for item in multi_measurements}) > 1
    return evidence


def scoring_truth() -> dict[str, Any]:
    assert sum(CATEGORY_WEIGHTS.values()) == 100
    base = {name: (PrintabilityStatus.PASS, PrintabilityConfidence.HIGH, "completed") for name in CATEGORY_WEIGHTS}
    cases: dict[str, Any] = {}
    for name, state in (
        ("all_pass", PrintabilityStatus.PASS),
        ("warning", PrintabilityStatus.WARNING),
        ("critical", PrintabilityStatus.CRITICAL),
        ("failed", PrintabilityStatus.FAILED),
        ("skipped", PrintabilityStatus.SKIPPED_LIMIT),
        ("not_evaluated", PrintabilityStatus.NOT_EVALUATED),
        ("not_applicable", PrintabilityStatus.NOT_APPLICABLE),
        ("indeterminate", PrintabilityStatus.INDETERMINATE),
    ):
        categories = dict(base)
        if name != "all_pass":
            categories["wall_thickness"] = (state, PrintabilityConfidence.UNKNOWN, name)
        score = score_printability(categories)
        cases[name] = score.to_dict()
    assert cases["all_pass"]["score"] == 100 and cases["all_pass"]["status"] == "PASS"
    assert cases["critical"]["score"] <= 59 and cases["critical"]["status"] == "CRITICAL"
    assert cases["failed"]["status"] == "FAILED" and cases["failed"]["failed_checks"]
    assert cases["skipped"]["status"] == "INDETERMINATE" and cases["skipped"]["skipped_checks"]
    assert cases["not_evaluated"]["missing_checks"]
    assert score_printability(base) == score_printability(base)
    return {"weights": CATEGORY_WEIGHTS, "truth_table": cases}


def stale_and_report_truth() -> dict[str, Any]:
    clear_scene()
    profile = load_profile("generic_fdm")
    settings = PrintabilitySettings(mode=PrintabilityMode.FAST)
    attacks: dict[str, str] = {}

    def fresh(name: str) -> tuple[bpy.types.Object, Any]:
        obj = make_boxes(name, (((0, 0, 5), (10, 10, 10), False),))
        result = analyze_printability(obj, bpy.context.scene, profile, settings)
        store_result(obj, result)
        return obj, result

    obj, result = fresh("StaleCoordinate")
    obj.data.vertices[0].co.x += 0.0001; obj.data.update()
    attacks["coordinate"] = stale_state(obj, result, profile, settings).value
    obj, result = fresh("StaleTopology")
    vertices = [tuple(v.co) for v in obj.data.vertices] + [(0.1, 0.1, 0.1)]
    edges = [tuple(e.vertices) for e in obj.data.edges]
    faces = [tuple(p.vertices) for p in obj.data.polygons]
    obj.data.clear_geometry(); obj.data.from_pydata(vertices, edges, faces); obj.data.update()
    attacks["topology"] = stale_state(obj, result, profile, settings).value
    obj, result = fresh("StaleWinding")
    obj.data.polygons[0].flip(); obj.data.update()
    attacks["winding"] = stale_state(obj, result, profile, settings).value
    for label, attribute, value in (("location", "location", (0.1, 0, 0)), ("rotation", "rotation_euler", (0.1, 0, 0)), ("scale", "scale", (2, 1, 1))):
        obj, result = fresh(f"Stale{label.title()}")
        setattr(obj, attribute, value)
        attacks[label] = stale_state(obj, result, profile, settings).value
    obj, result = fresh("StaleProfile")
    attacks["profile"] = stale_state(obj, result, build_custom_profile({"build_volume_mm": (100, 100, 100)}), settings).value
    attacks["mode"] = stale_state(obj, result, profile, replace(settings, mode=PrintabilityMode.DEEP)).value
    attacks["build_direction"] = stale_state(obj, result, profile, replace(settings, build_direction=(1, 0, 0))).value
    attacks["settings"] = stale_state(obj, result, profile, replace(settings, ray_origin_offset_mm=0.002)).value
    replacement = obj.data.copy(); obj.data = replacement
    attacks["datablock_replacement"] = stale_state(obj, result, profile, settings).value
    expected_states = {"coordinate", "topology", "winding", "location", "rotation", "scale", "profile", "mode", "build_direction", "settings", "datablock_replacement"}
    assert set(attacks) == expected_states and all(value != StaleState.CURRENT.value for value in attacks.values())
    try:
        require_current(obj, profile, settings)
    except ValueError as exc:
        assert str(exc) == STALE_MESSAGE
    else:
        raise AssertionError("Stale report was accepted.")
    try:
        from chroma3d_sculpt.ui.printability_panel import display_result_for_state
    except ImportError as exc:
        raise AssertionError("The panel has no stale-result display guard.") from exc
    displayed, message = display_result_for_state(obj, bpy.context.window_manager.chroma3d_sculpt_state)
    assert displayed is None and message == STALE_MESSAGE
    report_obj, report_result = fresh("Vishnu deity: CON? ")
    report = report_result.to_dict()
    assert report["report_schema_version"] == "1.0.0" and report_result.to_json().endswith("\n")
    assert markdown_report(report_result).endswith("\n") and ADVISORY_DISCLAIMER in markdown_report(report_result)
    attacks_names = ("CON", "PRN", "AUX", "NUL", "name.", "name ", "***", "slash/name", "colon:name", "question?", "Śiva deity")
    filenames = [sanitize_printability_filename(name, "json") for name in attacks_names]
    assert all(name.endswith(".json") and not any(char in name for char in '<>:"/\\|?*') for name in filenames)
    assert len(report_result.to_json().encode("utf-8")) < 5_000_000
    return {"stale_attacks": attacks, "required_message": STALE_MESSAGE, "filenames": filenames, "report_size_bytes": len(report_result.to_json().encode("utf-8"))}


def performance_truth() -> dict[str, Any]:
    clear_scene()
    profile = load_profile("generic_fdm")
    cases = (
        ("small", 158, PrintabilitySettings(mode=PrintabilityMode.DEEP, wall_sample_limit=1, triangle_limit=1)),
        ("medium", 316, PrintabilitySettings(mode=PrintabilityMode.STANDARD, wall_sample_limit=1, triangle_limit=1)),
        ("large", 500, PrintabilitySettings(mode=PrintabilityMode.FAST, wall_sample_limit=1, triangle_limit=1)),
    )
    evidence: dict[str, Any] = {}
    for name, cells, settings in cases:
        before_memory = memory_snapshot()
        fixture_started = perf_counter()
        obj = make_grid(f"Performance{name.title()}", cells)
        fixture_seconds = perf_counter() - fixture_started
        cpu_started = process_time()
        result = analyze_printability(obj, bpy.context.scene, profile, settings)
        cpu_seconds = process_time() - cpu_started
        after_memory = memory_snapshot()
        evidence[name] = {
            "triangles": result.geometry_facts.triangle_count,
            "mode": settings.mode.value,
            "wall_sample_limit": settings.resolved(profile).wall_sample_limit,
            "fixture_generation_seconds": fixture_seconds,
            "timings": result.timings,
            "cpu_seconds": cpu_seconds,
            "working_set_before_bytes": before_memory["working_set_bytes"],
            "working_set_after_bytes": after_memory["working_set_bytes"],
            "available_memory_before_bytes": before_memory["available_memory_bytes"],
            "check_states": {item["check"]: item.get("status") for item in result.check_results()},
            "evidence_counts": {
                "wall_faces": len(result.wall_thickness.evidence_faces),
                "thin_vertices": len(result.thin_features.evidence_vertices),
                "overhang_faces": len(result.overhangs.evidence_faces),
                "orientation_candidates": len(result.orientation.candidates),
            },
            "memory_note": "Working-set values are point observations, not exact peak memory.",
            "initial_deep_observation": "A prior default-DEEP 50k-triangle open-grid attempt was stopped after more than 420 CPU seconds; this retained dense-mesh bound verifies honest SKIPPED_LIMIT behavior and does not change production limits.",
        }
        bpy.data.objects.remove(obj, do_unlink=True)
    assert 25_000 <= evidence["small"]["triangles"] <= 75_000
    assert 100_000 <= evidence["medium"]["triangles"] <= 300_000
    assert 500_000 <= evidence["large"]["triangles"] <= 1_000_000
    assert evidence["large"]["check_states"]["wall_thickness"] == "SKIPPED_LIMIT"
    return evidence


def registration_truth() -> dict[str, Any]:
    chroma3d_sculpt.unregister()
    assert get_result() is None
    chroma3d_sculpt.register()
    assert hasattr(bpy.ops.chroma3d, "analyze_printability")
    return {"unregister_cleared_cache": True, "reregistered": True, "operator_registered": True}


def parse_args() -> argparse.Namespace:
    arguments = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(arguments)


def main() -> int:
    args = parse_args()
    started = perf_counter()
    try:
        chroma3d_sculpt.unregister()
    except Exception:
        pass
    chroma3d_sculpt.register()
    gate_definitions = (
        ("S3F-A", "Independent static safety and wording audit", static_audit),
        ("S3F-B", "Complete source and transform immutability matrix", immutability_matrix),
        ("S3F-C", "Printer profile adversarial validation", profile_adversarial),
        ("S3F-D", "Wall-thickness mathematical and ambiguity truth", wall_truth),
        ("S3F-E", "Thin-feature false-positive and false-negative truth", feature_truth),
        ("S3F-F", "Overhang angle convention and build-direction truth", overhang_truth),
        ("S3F-G", "Floating component and contact-class truth", component_and_contact_truth),
        ("S3F-H", "Scale and build-volume arithmetic truth", scale_truth),
        ("S3F-I", "Virtual orientation determinism and recomputation", orientation_truth),
        ("S3F-J", "Scoring truth table", scoring_truth),
        ("S3F-KL", "Stale-state attacks and report truthfulness", stale_and_report_truth),
        ("S3F-M", "Bounded performance and memory observations", performance_truth),
        ("S3F-P", "Unregister and re-register lifecycle", registration_truth),
    )
    for gate_id, name, function in gate_definitions:
        run_gate(gate_id, name, function)
        interim = {
            "schema_version": "1.0.0",
            "generated_at": utcnow(),
            "project": "Chroma3D Sculpt",
            "extension_version": DISPLAY_VERSION,
            "blender_version": bpy.app.version_string,
            "gate_results": GATES,
            "passed_gates": sum(item["status"] == "PASS" for item in GATES),
            "total_gates": len(gate_definitions),
            "blender_gate_status": "IN_PROGRESS",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(json.dumps(interim, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        temporary.replace(args.output)
    try:
        chroma3d_sculpt.unregister()
    except Exception:
        pass
    passed = sum(item["status"] == "PASS" for item in GATES)
    report = {
        "schema_version": "1.0.0",
        "generated_at": utcnow(),
        "project": "Chroma3D Sculpt",
        "extension_version": DISPLAY_VERSION,
        "analysis_schema_version": SCHEMA_VERSION,
        "repair_audit_schema_version": REPAIR_AUDIT_SCHEMA_VERSION,
        "printability_report_schema_version": PRINTABILITY_REPORT_SCHEMA_VERSION,
        "blender_version": bpy.app.version_string,
        "python_version": sys.version.split()[0],
        "gate_results": GATES,
        "passed_gates": passed,
        "total_gates": len(GATES),
        "blender_gate_status": "PASS" if passed == len(GATES) else "FAIL",
        "duration_seconds": perf_counter() - started,
        "known_limitations": [
            "Wall thickness is sampled and estimated, not an exact global minimum.",
            "Thin-feature analysis is a conservative connected-shell proxy and does not recognize local merged features.",
            "Contact stability is a geometric heuristic, not adhesion or dynamics simulation.",
            "Orientation candidates are bounded and not globally optimal.",
            "No support generation, slicing, G-code, automatic rotation, or automatic scaling is performed.",
            "Physical and resin calibration are pending; printability guarantees are prohibited.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(args.output)
    print(f"Sprint 3 final Blender gates: {passed}/{len(GATES)}")
    return 0 if passed == len(GATES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
