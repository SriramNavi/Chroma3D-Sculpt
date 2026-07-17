"""Execute Sprint 1 acceptance fixtures through production code inside Blender."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import struct
import subprocess
import sys
from time import perf_counter
import traceback
from typing import Any, Callable

import bmesh
import bpy
from mathutils import Matrix, Vector

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PARENT = REPOSITORY_ROOT / "blender_addon"
if str(SOURCE_PARENT) not in sys.path:
    sys.path.insert(0, str(SOURCE_PARENT))

import chroma3d_sculpt  # noqa: E402
from chroma3d_sculpt.analysis_settings import AnalysisSettings  # noqa: E402
from chroma3d_sculpt.metadata import DISPLAY_VERSION  # noqa: E402
from chroma3d_sculpt.models.analysis_result import (  # noqa: E402
    AnalysisProfile,
    BuildVolumeFitState,
    EvaluationStatus,
    IssueCategory,
    PrinterProfile,
    SelfIntersectionState,
    ShellContainmentState,
    ShellOrientationState,
    WatertightState,
)
from chroma3d_sculpt.services.mesh_analyzer import analyze_mesh  # noqa: E402
from chroma3d_sculpt.session import store_result  # noqa: E402

REPORTS_DIRECTORY = REPOSITORY_ROOT / "manual-tests" / "sprint1" / "reports"
RESULTS_PATH = REPORTS_DIRECTORY / "sprint1_acceptance_results.json"
GateFunction = Callable[[], dict[str, Any]]
OBJECTS: list[bpy.types.Object] = []
GATES: list[dict[str, Any]] = []


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _cube_data(center=(0.0, 0.0, 0.0), size=2.0):
    cx, cy, cz = center
    half = size / 2.0
    vertices = [
        (cx - half, cy - half, cz - half), (cx + half, cy - half, cz - half),
        (cx + half, cy + half, cz - half), (cx - half, cy + half, cz - half),
        (cx - half, cy - half, cz + half), (cx + half, cy - half, cz + half),
        (cx + half, cy + half, cz + half), (cx - half, cy + half, cz + half),
    ]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return vertices, faces


def _combine_cubes(*specifications):
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for center, size in specifications:
        cube_vertices, cube_faces = _cube_data(center, size)
        offset = len(vertices)
        vertices.extend(cube_vertices)
        faces.extend(tuple(index + offset for index in face) for face in cube_faces)
    return vertices, faces


def _create_mesh(name: str, vertices, faces=(), edges=(), scale=(1.0, 1.0, 1.0)):
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
    OBJECTS.append(obj)
    return obj


def _analyze(obj, settings=None):
    return analyze_mesh(
        obj,
        bpy.context.scene,
        settings=settings,
        blender_version=bpy.app.version_string,
        blend_file_path=bpy.data.filepath,
    )


def _geometry_hash(obj) -> str:
    digest = sha256()
    for vertex in obj.data.vertices:
        digest.update(struct.pack("<ddd", *tuple(float(value) for value in vertex.co)))
    for edge in obj.data.edges:
        digest.update(struct.pack("<II", *tuple(int(value) for value in edge.vertices)))
    for polygon in obj.data.polygons:
        digest.update(struct.pack("<I", len(polygon.vertices)))
        for index in polygon.vertices:
            digest.update(struct.pack("<I", int(index)))
    return digest.hexdigest()


def _cleanup() -> None:
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for obj in list(OBJECTS):
        mesh = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        OBJECTS.remove(obj)


def _run_gate(gate_id: str, name: str, function: GateFunction) -> None:
    started = perf_counter()
    status = "PASS"
    failures: list[str] = []
    try:
        actual = function()
    except Exception as exc:
        traceback.print_exc()
        status = "FAIL"
        failures.append(f"{type(exc).__name__}: {exc}")
        actual = {}
    finally:
        _cleanup()
    gate = {
        "id": gate_id,
        "name": name,
        "status": status,
        "duration_seconds": round(perf_counter() - started, 6),
        "actual": actual,
        "failures": failures,
    }
    GATES.append(gate)
    print(f"[{status}] {gate_id} - {name}")


def _gate_topology() -> dict[str, Any]:
    closed = _analyze(_create_mesh("S1Closed", *_cube_data()))
    vertices, faces = _cube_data()
    opened = _analyze(_create_mesh("S1Open", vertices, faces[:-1]))
    nonmanifold = _analyze(_create_mesh("S1NonManifold", [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1)], [(0, 1, 2), (1, 0, 3), (0, 1, 4)]))
    _require(closed.topology.watertight_state == WatertightState.TOPOLOGICALLY_WATERTIGHT, "Closed cube was not watertight.")
    _require(opened.topology.watertight_state == WatertightState.NOT_WATERTIGHT, "Open cube was not rejected.")
    _require(nonmanifold.topology.high_incidence_non_manifold_edges > 0, "High-incidence edge was missed.")
    serialized = closed.to_json().lower()
    _require("guaranteed printable" not in serialized and "safe to manufacture" not in serialized, "False guarantee wording found.")
    return {
        "closed": closed.topology.watertight_state.value,
        "open": opened.topology.watertight_state.value,
        "high_incidence_edges": nonmanifold.topology.high_incidence_non_manifold_edges,
    }


def _gate_metrics() -> dict[str, Any]:
    cube = _analyze(_create_mesh("S1Metrics", *_cube_data()))
    scaled_obj = _create_mesh("S1ScaledMetrics", *_cube_data(), scale=(2.0, 3.0, 4.0))
    scale_before = tuple(scaled_obj.scale)
    scaled = _analyze(scaled_obj)
    _require(abs(cube.surface_volume.total_surface_area_mm2 - 24_000_000.0) <= 1.0, "Known area mismatch.")
    _require(abs((cube.surface_volume.reliable_closed_shell_volume_mm3 or 0.0) - 8_000_000_000.0) <= 1.0, "Known volume mismatch.")
    _require(abs((scaled.surface_volume.reliable_closed_shell_volume_mm3 or 0.0) - 192_000_000_000.0) <= 10.0, "Scaled volume mismatch.")
    _require(tuple(scaled_obj.scale) == scale_before, "Scale was applied or changed.")
    return {
        "cube_area_mm2": cube.surface_volume.total_surface_area_mm2,
        "cube_volume_mm3": cube.surface_volume.reliable_closed_shell_volume_mm3,
        "scaled_dimensions_mm": scaled.shells[0].dimensions_mm,
        "scaled_volume_mm3": scaled.surface_volume.reliable_closed_shell_volume_mm3,
    }


def _gate_orientation() -> dict[str, Any]:
    vertices, faces = _cube_data()
    outward_obj = _create_mesh("S1Outward", vertices, faces)
    inward_obj = _create_mesh("S1Inward", vertices, [tuple(reversed(face)) for face in faces])
    inconsistent_obj = _create_mesh("S1Inconsistent", vertices, [tuple(reversed(faces[0]))] + faces[1:])
    hashes = {obj.name: _geometry_hash(obj) for obj in (outward_obj, inward_obj, inconsistent_obj)}
    outward, inward, inconsistent = (_analyze(outward_obj), _analyze(inward_obj), _analyze(inconsistent_obj))
    _require(outward.shells[0].orientation_state == ShellOrientationState.OUTWARD, "Outward cube sign mismatch.")
    _require(inward.shells[0].orientation_state == ShellOrientationState.INWARD, "Inward cube sign mismatch.")
    _require(inconsistent.shells[0].orientation_state == ShellOrientationState.INCONSISTENT, "Reversed face was missed.")
    _require(all(hashes[obj.name] == _geometry_hash(obj) for obj in (outward_obj, inward_obj, inconsistent_obj)), "Face winding changed.")
    return {"outward": "OUTWARD", "inward": "INWARD", "one_reversed_face": "INCONSISTENT", "geometry_unchanged": True}


def _gate_shells() -> dict[str, Any]:
    tiny = _analyze(_create_mesh("S1Tiny", *_combine_cubes(((0, 0, 0), 2), ((3, 0, 0), 0.002))))
    medium = _analyze(_create_mesh("S1Medium", *_combine_cubes(((0, 0, 0), 2), ((3, 0, 0), 0.5))))
    _require(tiny.main_shell_id is not None and len(tiny.tiny_shell_candidate_ids) == 1, "Tiny shell classification failed.")
    _require(not medium.tiny_shell_candidate_ids and len(medium.disconnected_external_shell_ids) == 1, "Medium ornament was misclassified.")
    return {
        "shell_count": len(tiny.shells),
        "main_shell_id": tiny.main_shell_id,
        "tiny_shell_ids": tiny.tiny_shell_candidate_ids,
        "medium_external_ids": medium.disconnected_external_shell_ids,
    }


def _gate_containment() -> dict[str, Any]:
    deep = AnalysisSettings(profile=AnalysisProfile.DEEP)
    inside = _analyze(_create_mesh("S1Inside", *_combine_cubes(((0, 0, 0), 4), ((0, 0, 0), 1))), deep)
    outside = _analyze(_create_mesh("S1Outside", *_combine_cubes(((0, 0, 0), 4), ((5, 0, 0), 1))), deep)
    overlap = _analyze(_create_mesh("S1Overlap", *_combine_cubes(((0, 0, 0), 2), ((1.5, 0, 0), 1))), deep)
    limited = _analyze(_create_mesh("S1ContainLimit", *_combine_cubes(((0, 0, 0), 4), ((0, 0, 0), 1))), AnalysisSettings(profile=AnalysisProfile.DEEP, containment_shell_limit=1))
    _require(len(inside.possible_internal_shell_ids) == 1, "Internal cube was not classified.")
    _require(not outside.possible_internal_shell_ids and not overlap.possible_internal_shell_ids, "False containment result.")
    _require(limited.deep_diagnostics.containment_status == EvaluationStatus.SKIPPED, "Containment limit did not skip.")
    evidence = inside.deep_diagnostics.containment_evidence[0]
    return {
        "internal_ids": inside.possible_internal_shell_ids,
        "confidence": evidence.confidence.value,
        "votes": [evidence.positive_votes, evidence.sample_count],
        "outside_internal_ids": outside.possible_internal_shell_ids,
        "overlap_internal_ids": overlap.possible_internal_shell_ids,
        "limit_status": limited.deep_diagnostics.containment_status.value,
    }


def _gate_intersections() -> dict[str, Any]:
    deep = AnalysisSettings(profile=AnalysisProfile.DEEP, maximum_stored_self_intersection_pairs=1)
    intersecting = _analyze(_create_mesh("S1Intersect", *_combine_cubes(((0, 0, 0), 2), ((1, 0, 0), 2))), deep)
    separate = _analyze(_create_mesh("S1Separate", *_combine_cubes(((-3, 0, 0), 2), ((3, 0, 0), 2))), deep)
    limited = _analyze(_create_mesh("S1SelfLimit", *_cube_data()), AnalysisSettings(profile=AnalysisProfile.DEEP, self_intersection_triangle_limit=1))
    _require(intersecting.deep_diagnostics.self_intersection_state == SelfIntersectionState.CANDIDATES_DETECTED, "Intersection candidate missed.")
    _require(separate.deep_diagnostics.self_intersection_state == SelfIntersectionState.NO_CANDIDATES_DETECTED, "Separated cubes produced candidates.")
    _require(limited.deep_diagnostics.self_intersection_status == EvaluationStatus.SKIPPED, "Triangle limit did not skip.")
    return {
        "intersecting_candidates": intersecting.deep_diagnostics.self_intersection_candidate_count,
        "stored_pairs": intersecting.deep_diagnostics.self_intersection_pairs,
        "truncated": intersecting.deep_diagnostics.self_intersection_evidence_truncated,
        "separate_state": separate.deep_diagnostics.self_intersection_state.value,
        "limit_state": limited.deep_diagnostics.self_intersection_state.value,
    }


def _gate_build_volume() -> dict[str, Any]:
    pass_result = _analyze(_create_mesh("S1BuildPass", *_cube_data(size=0.2)), AnalysisSettings(printer_profile=PrinterProfile.BAMBU_X1_CARBON))
    fail_result = _analyze(_create_mesh("S1BuildFail", *_cube_data(size=0.2), scale=(2, 1, 1)), AnalysisSettings(printer_profile=PrinterProfile.BAMBU_X1_CARBON))
    custom = _analyze(_create_mesh("S1CustomBuild", *_cube_data(size=0.2)), AnalysisSettings(printer_profile=PrinterProfile.CUSTOM, custom_build_volume_mm=(250, 210, 205)))
    _require(pass_result.build_volume.fit_state == BuildVolumeFitState.FITS, "Bambu pass failed.")
    _require(fail_result.build_volume.fit_state == BuildVolumeFitState.DOES_NOT_FIT and not fail_result.build_volume.fits_x, "Axis overflow failed.")
    _require(custom.build_volume.fit_state == BuildVolumeFitState.FITS, "Custom profile failed.")
    return {
        "bambu_pass": pass_result.build_volume.to_dict() if hasattr(pass_result.build_volume, "to_dict") else pass_result.to_dict()["build_volume"],
        "one_axis_fail": fail_result.to_dict()["build_volume"],
        "custom": custom.to_dict()["build_volume"],
    }


def _gate_selection() -> dict[str, Any]:
    vertices, faces = _cube_data()
    obj = _create_mesh("S1Select", vertices, faces[:-1])
    before = _geometry_hash(obj)
    transform_before = (tuple(obj.location), tuple(obj.rotation_euler), tuple(obj.scale), len(obj.modifiers))
    result = _analyze(obj)
    store_result(obj, result)
    outcome = bpy.ops.chroma3d.select_diagnostic_issue(issue_category=IssueCategory.BOUNDARY_EDGES.value)
    selected_mode = obj.mode
    if obj.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    _require("FINISHED" in outcome and selected_mode == "EDIT", "Boundary evidence selection failed.")
    _require(before == _geometry_hash(obj), "Selection changed geometry.")
    _require(transform_before == (tuple(obj.location), tuple(obj.rotation_euler), tuple(obj.scale), len(obj.modifiers)), "Selection changed transform or modifiers.")
    obj.data.vertices.add(1)
    stale_rejected = False
    try:
        bpy.ops.chroma3d.select_diagnostic_issue(issue_category=IssueCategory.BOUNDARY_EDGES.value)
    except RuntimeError as exc:
        stale_rejected = "Analysis is stale" in str(exc)
    _require(stale_rejected, "Stale analysis was not rejected.")
    return {"operator_result": sorted(outcome), "selected_mode": selected_mode, "geometry_unchanged": True, "transform_unchanged": True, "stale_rejected": True}


def _scaled_matrix(location, scale):
    return Matrix.Translation(Vector(location)) @ Matrix.Diagonal(Vector((*scale, 1.0)))


def _create_statue_mesh():
    mesh = bpy.data.meshes.new("Sprint1StatueStress_Mesh")
    bm = bmesh.new()
    try:
        bmesh.ops.create_uvsphere(bm, u_segments=256, v_segments=160, radius=1.0, matrix=_scaled_matrix((0, 0, 3.4), (1.8, 1.3, 2.5)))
        bmesh.ops.create_uvsphere(bm, u_segments=192, v_segments=128, radius=1.0, matrix=_scaled_matrix((0, 0, 6.5), (1.0, 0.95, 1.15)))
        for x_value in (-1.55, 1.55):
            bmesh.ops.create_uvsphere(bm, u_segments=160, v_segments=96, radius=1.0, matrix=_scaled_matrix((x_value, 0, 4.55), (0.8, 0.72, 0.9)))
        for location in ((-1.25, -1, 5.1), (-0.9, -1.22, 4.8), (-0.45, -1.36, 4.55), (0, -1.42, 4.45), (0.45, -1.36, 4.55), (0.9, -1.22, 4.8), (1.25, -1, 5.1), (0, 1.38, 4.8)):
            bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=64, radius=1.0, matrix=_scaled_matrix(location, (0.32, 0.32, 0.32)))
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=512, radius1=2.5, radius2=2.15, depth=0.9, matrix=Matrix.Translation(Vector((0, 0, 0.45))))
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=512, radius1=0.12, radius2=0.08, depth=5.8, matrix=Matrix.Translation(Vector((2.65, 0.1, 3.6))))
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=512, radius1=0.72, radius2=0.08, depth=1.2, matrix=Matrix.Translation(Vector((0, 0, 7.75))))
        bm.to_mesh(mesh)
    finally:
        bm.free()
    mesh.update()
    obj = bpy.data.objects.new("Sprint1StatueStress", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.context.view_layer.update()
    OBJECTS.append(obj)
    return obj


def _gate_stress() -> dict[str, Any]:
    obj = _create_statue_mesh()
    before = _geometry_hash(obj)
    result = _analyze(obj)
    _require(100_000 <= result.geometry.vertex_count <= 200_000, f"Stress vertex count {result.geometry.vertex_count} outside target.")
    _require(before == _geometry_hash(obj), "Stress analysis changed geometry.")
    return {
        "vertices": result.geometry.vertex_count,
        "edges": result.geometry.edge_count,
        "faces": result.geometry.polygon_count,
        "triangles": result.geometry.triangle_count,
        "shells": len(result.shells),
        "duration_ms": result.duration_ms,
        "timings": {timing.name: timing.duration_ms for timing in result.timings},
        "surface_area_mm2": result.surface_volume.total_surface_area_mm2,
        "volume_status": result.surface_volume.volume_status.value,
        "topology_state": result.topology.watertight_state.value,
        "issue_counts": {item.category.value: item.total_count for item in result.issue_evidence},
        "deep_states": [result.deep_diagnostics.self_intersection_status.value, result.deep_diagnostics.containment_status.value],
        "geometry_unchanged": True,
        "performance_warning": result.duration_ms > 20_000.0,
        "sprint0_baseline_duration_ms": 5377.0,
    }


def _gate_deep_bounded() -> dict[str, Any]:
    obj = _create_mesh("S1DeepBounded", *_combine_cubes(((0, 0, 0), 4), ((0, 0, 0), 1), ((3, 0, 0), 2)))
    before = _geometry_hash(obj)
    complete = _analyze(obj, AnalysisSettings(profile=AnalysisProfile.DEEP))
    skipped = _analyze(obj, AnalysisSettings(profile=AnalysisProfile.DEEP, self_intersection_triangle_limit=1, containment_shell_limit=1))
    _require(complete.deep_diagnostics.self_intersection_status == EvaluationStatus.COMPLETED, "Bounded self-intersection check did not complete.")
    _require(complete.deep_diagnostics.containment_status == EvaluationStatus.COMPLETED, "Bounded containment did not complete.")
    _require(skipped.deep_diagnostics.self_intersection_status == EvaluationStatus.SKIPPED and skipped.deep_diagnostics.containment_status == EvaluationStatus.SKIPPED, "Limit skip was not explicit.")
    _require(before == _geometry_hash(obj), "Deep checks changed geometry.")
    return {"complete_states": [complete.deep_diagnostics.self_intersection_status.value, complete.deep_diagnostics.containment_status.value], "skip_states": [skipped.deep_diagnostics.self_intersection_status.value, skipped.deep_diagnostics.containment_status.value], "geometry_unchanged": True}


def _gate_report() -> dict[str, Any]:
    result = _analyze(_create_mesh("S1Report", *_cube_data()))
    payload = json.loads(result.to_json())
    required = {"analysis_id", "analysis_profile", "settings_snapshot", "topology_signature", "surface_volume", "shells", "build_volume", "deep_diagnostics", "issue_evidence", "timings", "skipped_check_reasons"}
    missing = sorted(required - payload.keys())
    _require(payload["schema_version"] == "2.0" and not missing, f"Schema 2.0 missing fields: {missing}")
    _require(result.to_json().endswith("\n"), "JSON lacks trailing newline.")
    return {"schema_version": payload["schema_version"], "required_fields_present": sorted(required), "trailing_newline": True, "extension_version": payload["extension_version"]}


def _gate_registration() -> dict[str, Any]:
    initial = hasattr(bpy.types, "CHROMA3D_OT_select_diagnostic_issue")
    chroma3d_sculpt.unregister()
    after_unregister = hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state")
    chroma3d_sculpt.register()
    after_reregister = hasattr(bpy.types, "CHROMA3D_OT_select_diagnostic_issue")
    _require(initial and not after_unregister and after_reregister, "Registration lifecycle failed.")
    return {"initial": initial, "after_unregister_property": after_unregister, "after_reregister": after_reregister}


def main() -> int:
    REPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    started_at = _utc_now()
    started_timer = perf_counter()
    chroma3d_sculpt.register()
    try:
        _run_gate("S1-01", "Sprint 0 regression", _gate_registration)
        _run_gate("S1-02", "Topological watertightness", _gate_topology)
        _run_gate("S1-03", "Physical metrics", _gate_metrics)
        _run_gate("S1-04", "Orientation", _gate_orientation)
        _run_gate("S1-05", "Shell classification", _gate_shells)
        _run_gate("S1-06", "Internal-shell heuristic", _gate_containment)
        _run_gate("S1-07", "Self-intersection candidates", _gate_intersections)
        _run_gate("S1-08", "Build-volume checks", _gate_build_volume)
        _run_gate("S1-09", "Issue selection", _gate_selection)
        _run_gate("S1-10", "Standard stress test", _gate_stress)
        _run_gate("S1-11", "Deep bounded diagnostics", _gate_deep_bounded)
        _run_gate("S1-12", "Report and package", _gate_report)
    finally:
        _cleanup()
        chroma3d_sculpt.unregister()
    completed_at = _utc_now()
    try:
        branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=REPOSITORY_ROOT, text=True).strip()
    except (OSError, subprocess.SubprocessError):
        branch = "Unknown"
    payload = {
        "schema_version": "1.0",
        "project": "Chroma3D Sculpt",
        "version": DISPLAY_VERSION,
        "branch": branch,
        "baseline_tag": "v0.1.0-alpha.1",
        "blender_executable": bpy.app.binary_path,
        "blender_version": bpy.app.version_string,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_seconds": round(perf_counter() - started_timer, 6),
        "overall_status": "FAIL" if any(gate["status"] == "FAIL" for gate in GATES) else "PASS",
        "gate_results": GATES,
        "warnings": [],
        "failures": [failure for gate in GATES for failure in gate["failures"]],
        "defects_fixed": [],
        "evidence_files": ["manual-tests/sprint1/reports/sprint1_acceptance_results.json", "manual-tests/sprint1/logs/blender_sprint1_acceptance.log"],
        "tests_not_run": ["Interactive visual smoke test of the Blender sidebar panel."],
        "known_limitations": ["Modifier output is not analyzed.", "Self-intersection results are candidates.", "Internal-shell classification is heuristic.", "Wall thickness and repair are not implemented.", "Printability is not guaranteed."],
        "safety_confirmation": {"geometry_repair": False, "network": False, "external_dependencies": False, "credentials": False, "administrator_privileges": False, "outside_repository_writes": False, "commit": False, "push": False, "sprint_2_started": False},
    }
    RESULTS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return 0 if payload["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
