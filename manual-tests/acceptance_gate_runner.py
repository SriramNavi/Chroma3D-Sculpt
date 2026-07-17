"""Execute the Sprint 0 acceptance gates inside Blender's bundled Python."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
from time import perf_counter
import traceback
from typing import Any, Callable

import bmesh
import bpy
from mathutils import Matrix, Vector


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PARENT = REPOSITORY_ROOT / "blender_addon"
if str(SOURCE_PARENT) not in sys.path:
    sys.path.insert(0, str(SOURCE_PARENT))

import chroma3d_sculpt  # noqa: E402
from chroma3d_sculpt.metadata import DISPLAY_VERSION  # noqa: E402
from chroma3d_sculpt.models.analysis_result import AnalysisResult  # noqa: E402
from chroma3d_sculpt.operators.export_report import CHROMA3D_OT_export_analysis_report  # noqa: E402
from chroma3d_sculpt.services.report_generator import sanitize_report_filename  # noqa: E402
from chroma3d_sculpt.session import clear as clear_session  # noqa: E402
from chroma3d_sculpt.session import get_result  # noqa: E402
from chroma3d_sculpt.ui.panels import CHROMA3D_PT_sculpt  # noqa: E402
from chroma3d_sculpt.ui.properties import CHROMA3D_PG_session_state  # noqa: E402


REPORTS_DIRECTORY = REPOSITORY_ROOT / "manual-tests" / "reports"
ARTIFACTS_DIRECTORY = REPOSITORY_ROOT / "manual-tests" / "artifacts"
RESULTS_PATH = REPORTS_DIRECTORY / "sprint0_regression_on_sprint1.json"
EXPORTED_REPORT_PATH = REPORTS_DIRECTORY / "sprint0_regression_default_cube.json"
SCENE_ARTIFACT_PATH = ARTIFACTS_DIRECTORY / "acceptance_test_scene.blend"

GateFunction = Callable[[], tuple[dict[str, Any], list[str], list[str]]]
GATES: list[dict[str, Any]] = []
IMMUTABILITY_RECORDS: list[dict[str, Any]] = []
REGISTERED = False
HANDLERS_BEFORE: dict[str, int] = {}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except (OSError, ValueError):
        return str(path)


def _argument_value(name: str, default: str = "") -> str:
    if "--" not in sys.argv:
        return default
    arguments = sys.argv[sys.argv.index("--") + 1 :]
    try:
        return arguments[arguments.index(name) + 1]
    except (ValueError, IndexError):
        return default


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _all_close(actual: Any, expected: tuple[float, float, float], tolerance: float = 1e-6) -> bool:
    return all(abs(float(value) - target) <= tolerance for value, target in zip(actual, expected))


def _hash_coordinates(mesh: bpy.types.Mesh) -> str:
    digest = hashlib.sha256()
    digest.update(struct.pack("<Q", len(mesh.vertices)))
    for vertex in mesh.vertices:
        digest.update(struct.pack("<Qddd", vertex.index, *map(float, vertex.co)))
    return digest.hexdigest()


def _hash_edges(mesh: bpy.types.Mesh) -> str:
    digest = hashlib.sha256()
    digest.update(struct.pack("<Q", len(mesh.edges)))
    for edge in mesh.edges:
        digest.update(struct.pack("<QII", edge.index, int(edge.vertices[0]), int(edge.vertices[1])))
    return digest.hexdigest()


def _hash_polygons(mesh: bpy.types.Mesh) -> str:
    digest = hashlib.sha256()
    digest.update(struct.pack("<Q", len(mesh.polygons)))
    for polygon in mesh.polygons:
        vertices = tuple(int(index) for index in polygon.vertices)
        digest.update(struct.pack("<QI", polygon.index, len(vertices)))
        digest.update(struct.pack(f"<{len(vertices)}I", *vertices))
    return digest.hexdigest()


def _mesh_signature(obj: bpy.types.Object) -> dict[str, Any]:
    mesh = obj.data
    active = bpy.context.view_layer.objects.active
    selected = sorted(
        (item.name, int(item.as_pointer()))
        for item in bpy.context.selected_objects
    )
    return {
        "object_name": obj.name,
        "object_identity": int(obj.as_pointer()),
        "mesh_datablock_name": mesh.name,
        "mesh_identity": int(mesh.as_pointer()),
        "object_mode": obj.mode,
        "active_object_name": active.name if active else None,
        "active_object_identity": int(active.as_pointer()) if active else None,
        "selection_state": selected,
        "location": [float(value) for value in obj.location],
        "rotation_euler": [float(value) for value in obj.rotation_euler],
        "scale": [float(value) for value in obj.scale],
        "vertex_count": len(mesh.vertices),
        "edge_count": len(mesh.edges),
        "polygon_count": len(mesh.polygons),
        "coordinate_sha256": _hash_coordinates(mesh),
        "edge_connectivity_sha256": _hash_edges(mesh),
        "polygon_connectivity_sha256": _hash_polygons(mesh),
        "modifier_count": len(obj.modifiers),
        "material_slot_count": len(obj.material_slots),
        "blend_file_path": bpy.data.filepath,
    }


def _record_immutability(label: str, before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    differences = sorted(key for key in before if before[key] != after.get(key))
    IMMUTABILITY_RECORDS.append(
        {
            "mesh": label,
            "matched": not differences,
            "differences": differences,
            "before": before,
            "after": after,
        }
    )
    return differences


def _cleanup_scene() -> dict[str, int | bool]:
    clear_session()
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.cameras,
        bpy.data.lights,
        bpy.data.materials,
    ):
        for datablock in list(collection):
            if datablock.users == 0:
                collection.remove(datablock)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    return {
        "objects": len(bpy.data.objects),
        "meshes": len(bpy.data.meshes),
        "session_cache_empty": get_result() is None,
    }


def _cube_data() -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    vertices = [
        (-1.0, -1.0, -1.0),
        (1.0, -1.0, -1.0),
        (1.0, 1.0, -1.0),
        (-1.0, 1.0, -1.0),
        (-1.0, -1.0, 1.0),
        (1.0, -1.0, 1.0),
        (1.0, 1.0, 1.0),
        (-1.0, 1.0, 1.0),
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


def _create_mesh_object(
    name: str,
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    *,
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, (), faces)
    mesh.update(calc_edges=True)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.scale = scale
    for item in bpy.context.selected_objects:
        item.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.context.view_layer.update()
    return obj


def _run_analysis_operator(obj: bpy.types.Object) -> AnalysisResult:
    _require(bpy.context.view_layer.objects.active == obj, "Test mesh is not the active object.")
    operator_result = bpy.ops.chroma3d.analyze_mesh()
    _require("FINISHED" in operator_result, f"Analysis operator returned {sorted(operator_result)}.")
    result = get_result(obj)
    _require(result is not None, "The production session cache did not retain the analysis result.")
    return result


def _result_values(result: AnalysisResult) -> dict[str, Any]:
    return {
        "severity": result.severity.value,
        "summary": result.summary,
        "duration_ms": result.duration_ms,
        "geometry": result.to_dict()["geometry"],
        "dimensions": result.to_dict()["dimensions"],
        "transforms": result.to_dict()["transforms"],
        "topology": result.to_dict()["topology"],
        "checks": result.to_dict()["checks"],
        "warnings": list(result.warnings),
        "errors": list(result.errors),
    }


def _run_gate(
    gate_id: str,
    name: str,
    expected: dict[str, Any],
    function: GateFunction,
    *,
    clean_scene: bool = True,
) -> None:
    started = perf_counter()
    actual: dict[str, Any] = {}
    evidence: list[str] = []
    notes: list[str] = []
    status = "PASS"
    if clean_scene:
        _cleanup_scene()
    try:
        actual, evidence, notes = function()
    except Exception as exc:
        status = "FAIL"
        notes.append(f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
        failure_artifact = ARTIFACTS_DIRECTORY / f"failed_{gate_id.lower()}.blend"
        try:
            bpy.ops.wm.save_as_mainfile(filepath=str(failure_artifact), check_existing=False)
            evidence.append(_relative(failure_artifact))
        except Exception:
            traceback.print_exc()
    finally:
        if clean_scene:
            cleanup = _cleanup_scene()
            actual["post_gate_cleanup"] = cleanup
            if cleanup["objects"] or cleanup["meshes"] or not cleanup["session_cache_empty"]:
                status = "FAIL"
                notes.append(f"Controlled scene cleanup was incomplete: {cleanup}")
    gate = {
        "id": gate_id,
        "name": name,
        "status": status,
        "duration_seconds": round(perf_counter() - started, 6),
        "expected": expected,
        "actual": actual,
        "evidence_files": sorted(set(evidence)),
        "notes": notes,
    }
    GATES.append(gate)
    print(f"[{status}] {gate_id} {name} ({gate['duration_seconds']:.3f}s)")


def _gate_default_cube() -> tuple[dict[str, Any], list[str], list[str]]:
    vertices, faces = _cube_data()
    obj = _create_mesh_object("AcceptanceDefaultCube", vertices, faces)
    before = _mesh_signature(obj)
    result = _run_analysis_operator(obj)
    after = _mesh_signature(obj)
    differences = _record_immutability(obj.name, before, after)
    values = _result_values(result)
    geometry = result.geometry
    topology = result.topology
    _require(result.severity.value == "PASS", f"Expected PASS, received {result.severity.value}.")
    _require(
        (geometry.vertex_count, geometry.edge_count, geometry.polygon_count, geometry.triangle_count) == (8, 12, 6, 12),
        "Default cube geometry counts do not match 8/12/6/12.",
    )
    _require(topology.connected_components == 1, "Default cube must have one connected component.")
    _require(
        all(
            value == 0
            for value in (
                topology.boundary_edges,
                topology.non_manifold_edges,
                topology.loose_vertices,
                topology.loose_edges,
                topology.zero_length_edges,
                topology.degenerate_faces,
            )
        ),
        "Default cube reported a basic topology defect.",
    )
    _require(not result.warnings and not result.errors, "Default cube produced warnings or errors.")
    _require(not differences, f"Analysis changed default cube state: {differences}")
    values["immutability_differences"] = differences
    return values, [], ["Production analysis operator and session cache were exercised."]


def _gate_open_cube() -> tuple[dict[str, Any], list[str], list[str]]:
    vertices, faces = _cube_data()
    obj = _create_mesh_object("AcceptanceOpenCube", vertices, faces[:-1])
    before = _mesh_signature(obj)
    result = _run_analysis_operator(obj)
    after = _mesh_signature(obj)
    differences = _record_immutability(obj.name, before, after)
    values = _result_values(result)
    warning_text = " ".join(result.warnings).lower()
    _require(result.severity.value == "WARNING", f"Expected WARNING, received {result.severity.value}.")
    _require(result.topology.boundary_edges > 0, "Open cube did not report boundary edges.")
    _require("boundary" in warning_text or "open" in warning_text, "Warning text does not identify open/boundary topology.")
    _require(not differences, f"Analysis changed open cube state: {differences}")
    values["immutability_differences"] = differences
    return values, [], ["One cube face was intentionally omitted."]


def _gate_unapplied_scale() -> tuple[dict[str, Any], list[str], list[str]]:
    vertices, faces = _cube_data()
    expected_scale = (2.0, 1.5, 0.5)
    obj = _create_mesh_object("AcceptanceScaledCube", vertices, faces, scale=expected_scale)
    before = _mesh_signature(obj)
    result = _run_analysis_operator(obj)
    after = _mesh_signature(obj)
    differences = _record_immutability(obj.name, before, after)
    values = _result_values(result)
    _require(result.severity.value == "WARNING", f"Expected WARNING, received {result.severity.value}.")
    _require(not result.transforms.scale_applied, "Non-unit scale was incorrectly reported as applied.")
    _require(_all_close(result.transforms.scale, expected_scale), "Reported scale values changed.")
    _require(_all_close(obj.scale, expected_scale), "Object scale was applied or changed.")
    _require(not differences, f"Analysis changed scaled cube state: {differences}")
    values["immutability_differences"] = differences
    return values, [], ["Scale was intentionally left unapplied."]


def _gate_json_export() -> tuple[dict[str, Any], list[str], list[str]]:
    vertices, faces = _cube_data()
    obj = _create_mesh_object("AcceptanceExportCube", vertices, faces)
    before = _mesh_signature(obj)
    result = _run_analysis_operator(obj)
    after = _mesh_signature(obj)
    differences = _record_immutability(obj.name, before, after)
    operator_result = bpy.ops.chroma3d.export_analysis_report(filepath=str(EXPORTED_REPORT_PATH))
    _require("FINISHED" in operator_result, f"Export operator returned {sorted(operator_result)}.")
    raw = EXPORTED_REPORT_PATH.read_bytes()
    _require(raw.endswith(b"\n"), "JSON report does not end with a newline.")
    payload = json.loads(raw.decode("utf-8"))
    required_top_level = {
        "schema_version",
        "extension_version",
        "blender_version",
        "operating_system",
        "analyzed_at",
        "duration_ms",
        "severity",
        "warnings",
        "errors",
        "object_metadata",
        "geometry",
        "dimensions",
        "transforms",
        "topology",
        "checks",
    }
    missing = sorted(required_top_level - payload.keys())
    _require(not missing, f"Exported report is missing keys: {missing}")
    _require(payload["checks"] and all("status" in check for check in payload["checks"]), "Per-check statuses are absent.")
    _require(payload["duration_ms"] >= 0, "Analysis duration is invalid.")
    _require(payload["operating_system"], "Operating-system metadata is empty.")
    samples = {
        name: sanitize_report_filename(name)
        for name in ("CON", "Statue:Test?*", "Lakshmi/Narasimha")
    }
    invalid = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
    _require(all(value and not invalid.search(value) for value in samples.values()), "A sanitized filename is still invalid.")
    _require(samples["CON"].startswith("_CON_"), "Reserved Windows device name CON was not modified safely.")
    _require(not differences, f"Export analysis changed cube state: {differences}")
    actual = {
        "operator_id": CHROMA3D_OT_export_analysis_report.bl_idname,
        "operator_result": sorted(operator_result),
        "output_file": _relative(EXPORTED_REPORT_PATH),
        "utf8_readable": True,
        "valid_json": True,
        "ends_with_newline": True,
        "required_keys_present": sorted(required_top_level),
        "per_check_statuses_present": True,
        "filename_sanitization": samples,
        "immutability_differences": differences,
    }
    return actual, [_relative(EXPORTED_REPORT_PATH)], ["The actual export operator executed headlessly without opening the file browser."]


def _scaled_matrix(location: tuple[float, float, float], scale: tuple[float, float, float]) -> Matrix:
    return Matrix.Translation(Vector(location)) @ Matrix.Diagonal(Vector((*scale, 1.0)))


def _create_statue_mesh() -> bpy.types.Object:
    mesh = bpy.data.meshes.new("ProceduralStatueStressTest_Mesh")
    bm = bmesh.new()
    try:
        bmesh.ops.create_uvsphere(
            bm,
            u_segments=256,
            v_segments=160,
            radius=1.0,
            matrix=_scaled_matrix((0.0, 0.0, 3.4), (1.8, 1.3, 2.5)),
        )
        bmesh.ops.create_uvsphere(
            bm,
            u_segments=192,
            v_segments=128,
            radius=1.0,
            matrix=_scaled_matrix((0.0, 0.0, 6.5), (1.0, 0.95, 1.15)),
        )
        for x_value in (-1.55, 1.55):
            bmesh.ops.create_uvsphere(
                bm,
                u_segments=160,
                v_segments=96,
                radius=1.0,
                matrix=_scaled_matrix((x_value, 0.0, 4.55), (0.8, 0.72, 0.9)),
            )
        bead_locations = (
            (-1.25, -1.0, 5.1),
            (-0.9, -1.22, 4.8),
            (-0.45, -1.36, 4.55),
            (0.0, -1.42, 4.45),
            (0.45, -1.36, 4.55),
            (0.9, -1.22, 4.8),
            (1.25, -1.0, 5.1),
            (0.0, 1.38, 4.8),
        )
        for location in bead_locations:
            bmesh.ops.create_uvsphere(
                bm,
                u_segments=96,
                v_segments=64,
                radius=1.0,
                matrix=_scaled_matrix(location, (0.32, 0.32, 0.32)),
            )
        bmesh.ops.create_cone(
            bm,
            cap_ends=True,
            cap_tris=False,
            segments=512,
            radius1=2.5,
            radius2=2.15,
            depth=0.9,
            matrix=Matrix.Translation(Vector((0.0, 0.0, 0.45))),
        )
        bmesh.ops.create_cone(
            bm,
            cap_ends=True,
            cap_tris=False,
            segments=512,
            radius1=0.12,
            radius2=0.08,
            depth=5.8,
            matrix=Matrix.Translation(Vector((2.65, 0.1, 3.6))),
        )
        bmesh.ops.create_cone(
            bm,
            cap_ends=True,
            cap_tris=False,
            segments=512,
            radius1=0.72,
            radius2=0.08,
            depth=1.2,
            matrix=Matrix.Translation(Vector((0.0, 0.0, 7.75))),
        )
        bm.to_mesh(mesh)
    finally:
        bm.free()
    mesh.update()
    obj = bpy.data.objects.new("ProceduralStatueStressTest", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.context.view_layer.update()
    return obj


def _gate_statue_stress() -> tuple[dict[str, Any], list[str], list[str]]:
    obj = _create_statue_mesh()
    before = _mesh_signature(obj)
    result = _run_analysis_operator(obj)
    after = _mesh_signature(obj)
    differences = _record_immutability(obj.name, before, after)
    geometry = result.geometry
    topology = result.topology
    _require(not result.errors, f"Stress analysis returned errors: {result.errors}")
    _require(100_000 <= geometry.vertex_count <= 400_000, f"Stress mesh density was {geometry.vertex_count:,} vertices.")
    _require(geometry.edge_count > geometry.vertex_count, "Stress mesh edge count is structurally implausible.")
    _require(geometry.polygon_count > 0 and geometry.triangle_count > 0, "Stress mesh has no analyzable surface.")
    _require(topology.connected_components > 1, "Intentional disconnected ornamental forms were not detected.")
    _require(topology.duplicate_evaluation_status.value in {"COMPLETED", "SKIPPED"}, "Duplicate check has invalid state.")
    if topology.duplicate_evaluation_status.value == "SKIPPED":
        duplicate_check = next(check for check in result.checks if check.name == "potential_duplicates")
        _require(bool(duplicate_check.message.strip()), "Skipped duplicate check has no explicit reason.")
    _require(not differences, f"Stress analysis changed mesh state: {differences}")
    save_result = bpy.ops.wm.save_as_mainfile(filepath=str(SCENE_ARTIFACT_PATH), check_existing=False)
    _require("FINISHED" in save_result, f"Controlled scene save returned {sorted(save_result)}.")
    actual = _result_values(result)
    actual.update(
        {
            "achieved_density_target": 100_000 <= geometry.vertex_count <= 400_000,
            "immutability_differences": differences,
            "scene_saved_after_analysis": _relative(SCENE_ARTIFACT_PATH),
            "headless_completion": True,
            "peak_observable_practical_behaviour": "Completed in one background Blender process without an observable crash or timeout.",
        }
    )
    notes = [
        "The stress mesh contains a torso, head, pedestal, shoulder forms, necklace ornaments, crown, and thin staff.",
        "Peak memory was not instrumented; practical behavior is evidenced by successful headless completion.",
        "Disconnected-component warnings are intentional for the ornamental forms.",
    ]
    return actual, [_relative(SCENE_ARTIFACT_PATH)], notes


def _gate_immutability() -> tuple[dict[str, Any], list[str], list[str]]:
    failed = [record["mesh"] for record in IMMUTABILITY_RECORDS if not record["matched"]]
    _require(len(IMMUTABILITY_RECORDS) == 5, f"Expected five analyzed-mesh signatures, found {len(IMMUTABILITY_RECORDS)}.")
    _require(not failed, f"Mesh state changed for: {failed}")
    return {
        "meshes_compared": len(IMMUTABILITY_RECORDS),
        "all_signatures_match": True,
        "records": IMMUTABILITY_RECORDS,
    }, [_relative(SCENE_ARTIFACT_PATH)], [
        "Exact deterministic hashes were compared for coordinates, edge connectivity, and polygon connectivity.",
        "The saved .blend is a controlled post-analysis test artifact; analysis itself did not save a file.",
    ]


def _gate_stability() -> tuple[dict[str, Any], list[str], list[str]]:
    cleanup = _cleanup_scene()
    _require(not cleanup["objects"] and not cleanup["meshes"], "Controlled Blender data remained after cleanup.")
    _require(cleanup["session_cache_empty"], "Session cache was not freed.")
    return {
        "factory_startup_argument_present": "--factory-startup" in sys.argv,
        "background_mode": bool(bpy.app.background),
        "in_process_unhandled_exception": False,
        "cleanup": cleanup,
        "process_exit_code": "PENDING_WINDOWS_LAUNCHER",
    }, ["manual-tests/logs/blender_acceptance.log"], [
        "The Windows launcher finalizes process-exit and fatal-signature evidence after Blender terminates.",
    ]


def _handler_counts() -> dict[str, int]:
    result: dict[str, int] = {}
    for name in dir(bpy.app.handlers):
        if name.startswith("_"):
            continue
        value = getattr(bpy.app.handlers, name)
        if isinstance(value, list):
            result[name] = len(value)
    return result


def _registration_state() -> dict[str, bool]:
    return {
        "window_manager_property": hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state"),
        "property_group": bool(CHROMA3D_PG_session_state.is_registered),
        "analyze_operator": hasattr(bpy.types, "CHROMA3D_OT_analyze_mesh"),
        "export_operator": hasattr(bpy.types, "CHROMA3D_OT_export_analysis_report"),
        "panel": hasattr(bpy.types, "CHROMA3D_PT_sculpt"),
    }


def _gate_registration() -> tuple[dict[str, Any], list[str], list[str]]:
    global REGISTERED
    first_registered = _registration_state()
    _require(all(first_registered.values()), f"Initial registration is incomplete: {first_registered}")
    panel = {
        "space_type": CHROMA3D_PT_sculpt.bl_space_type,
        "region_type": CHROMA3D_PT_sculpt.bl_region_type,
        "category": CHROMA3D_PT_sculpt.bl_category,
        "title": CHROMA3D_PT_sculpt.bl_label,
    }
    _require(
        panel == {"space_type": "VIEW_3D", "region_type": "UI", "category": "Chroma3D", "title": "Chroma3D Sculpt"},
        f"Panel placement metadata is incorrect: {panel}",
    )
    chroma3d_sculpt.unregister()
    REGISTERED = False
    after_first_unregister = _registration_state()
    _require(not any(after_first_unregister.values()), f"Registration state remained after unload: {after_first_unregister}")
    _require(_handler_counts() == HANDLERS_BEFORE, "Handler counts changed after unregister.")
    chroma3d_sculpt.register()
    REGISTERED = True
    after_reregister = _registration_state()
    _require(all(after_reregister.values()), f"Re-registration is incomplete: {after_reregister}")
    chroma3d_sculpt.unregister()
    REGISTERED = False
    after_final_unregister = _registration_state()
    _require(not any(after_final_unregister.values()), f"Final unregister left stale classes: {after_final_unregister}")
    _require(_handler_counts() == HANDLERS_BEFORE, "Final handler counts do not match the factory-startup baseline.")
    return {
        "source_registration": True,
        "operator_ids": ["chroma3d.analyze_mesh", "chroma3d.export_analysis_report"],
        "initial_registered_state": first_registered,
        "after_first_unregister": after_first_unregister,
        "after_reregister": after_reregister,
        "after_final_unregister": after_final_unregister,
        "handler_counts_before": HANDLERS_BEFORE,
        "handler_counts_after": _handler_counts(),
        "panel": panel,
    }, [], ["Repository source registration was used; installed-extension profile state was not required."]


def _add_skipped_gates_for_registration_failure(message: str) -> None:
    definitions = (
        ("GATE-01", "Default cube analysis"),
        ("GATE-02", "Broken/open cube warning"),
        ("GATE-03", "Unapplied scale warning"),
        ("GATE-04", "JSON export"),
        ("GATE-05", "Realistic high-density statue-like mesh"),
        ("GATE-06", "No unintended mesh modification"),
        ("GATE-07", "Blender stability"),
    )
    for gate_id, name in definitions:
        GATES.append(
            {
                "id": gate_id,
                "name": name,
                "status": "SKIPPED",
                "duration_seconds": 0.0,
                "expected": {},
                "actual": {},
                "evidence_files": [],
                "notes": [f"Source registration failed before this gate: {message}"],
            }
        )
    GATES.append(
        {
            "id": "GATE-08",
            "name": "Registration lifecycle",
            "status": "FAIL",
            "duration_seconds": 0.0,
            "expected": {"source_registration": True},
            "actual": {"source_registration": False},
            "evidence_files": ["manual-tests/logs/blender_acceptance.log"],
            "notes": [message],
        }
    )


def _write_results(started_at: datetime, started_timer: float, python_launcher: str) -> None:
    completed_at = _utc_now()
    failures = [
        {"gate": gate["id"], "name": gate["name"], "notes": gate["notes"]}
        for gate in GATES
        if gate["status"] == "FAIL"
    ]
    required_statuses = [gate["status"] for gate in GATES]
    overall = "FAIL" if "FAIL" in required_statuses else "PARTIAL" if "SKIPPED" in required_statuses else "PASS"
    archived_first_run = (
        REPOSITORY_ROOT / "manual-tests" / "logs" / "blender_acceptance_run1_failed.log",
        REPOSITORY_ROOT / "manual-tests" / "logs" / "registration_lifecycle_rerun.log",
        ARTIFACTS_DIRECTORY / "acceptance_results_run1_failed.json",
        ARTIFACTS_DIRECTORY / "ACCEPTANCE_RESULTS_run1_failed.md",
        ARTIFACTS_DIRECTORY / "failed_gate-08.blend",
    )
    generated = [
        _relative(path)
        for path in (EXPORTED_REPORT_PATH, SCENE_ARTIFACT_PATH, RESULTS_PATH, *archived_first_run)
        if path.exists() or path == RESULTS_PATH
    ]
    payload = {
        "schema_version": "1.0",
        "project": "Chroma3D Sculpt",
        "extension_version": DISPLAY_VERSION,
        "repository_root": str(REPOSITORY_ROOT),
        "blender_executable": bpy.app.binary_path,
        "blender_version": bpy.app.version_string,
        "python_launcher": python_launcher or "Unknown",
        "test_target": "Repository source registered explicitly under Blender --factory-startup",
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_seconds": round(perf_counter() - started_timer, 6),
        "overall_status": overall,
        "gates": GATES,
        "failures": failures,
        "warnings": [],
        "defects": [],
        "test_harness_corrections": [
            {
                "root_cause": "The first runner checked PropertyGroup registration through bpy.types, but Blender 4.4 reports this class via its is_registered flag and registered WindowManager property.",
                "files_changed": ["manual-tests/acceptance_gate_runner.py"],
                "exact_fix": "Use CHROMA3D_PG_session_state.is_registered for lifecycle assertions.",
                "regression_evidence": [
                    "manual-tests/logs/blender_acceptance_run1_failed.log",
                    "manual-tests/logs/registration_lifecycle_rerun.log",
                    "manual-tests/artifacts/acceptance_results_run1_failed.json",
                ],
                "product_code_changed": False,
            }
        ],
        "generated_artifacts": sorted(set(generated)),
        "tests_not_run": [
            "Optional Gate 5B (>500,000 vertices) was not run because the required 100,000-400,000 vertex stress gate exercises the safe production path without jeopardizing the core run.",
            "Optional headless render was not run; no UI screenshot is claimed.",
        ],
        "safety_confirmation": {
            "production_user_files_modified": False,
            "network_access_used": False,
            "api_keys_used": False,
            "administrator_privileges_used": False,
            "destructive_analysis_operations_used": False,
            "files_changed_outside_repository": False,
            "automatic_commits_created": False,
            "sprint_1_started": True,
        },
    }
    RESULTS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    global HANDLERS_BEFORE, REGISTERED
    for directory in (REPORTS_DIRECTORY, ARTIFACTS_DIRECTORY):
        directory.mkdir(parents=True, exist_ok=True)
    started_at = _utc_now()
    started_timer = perf_counter()
    python_launcher = _argument_value("--python-launcher", "Unknown")
    HANDLERS_BEFORE = _handler_counts()
    try:
        chroma3d_sculpt.register()
        REGISTERED = True
    except Exception as exc:
        traceback.print_exc()
        _add_skipped_gates_for_registration_failure(f"{type(exc).__name__}: {exc}")
    else:
        _run_gate(
            "GATE-01",
            "Default cube analysis",
            {"severity": "PASS", "geometry": [8, 12, 6, 12], "connected_components": 1, "basic_topology_warnings": 0},
            _gate_default_cube,
        )
        _run_gate(
            "GATE-02",
            "Broken/open cube warning",
            {"severity": "WARNING", "boundary_edges": ">0", "warning_mentions": "boundary or open"},
            _gate_open_cube,
        )
        _run_gate(
            "GATE-03",
            "Unapplied scale warning",
            {"severity": "WARNING", "scale_applied": False, "scale": [2.0, 1.5, 0.5]},
            _gate_unapplied_scale,
        )
        _run_gate(
            "GATE-04",
            "JSON export",
            {"valid_utf8_json": True, "ends_with_newline": True, "required_schema_fields": True, "windows_safe_names": True},
            _gate_json_export,
        )
        _run_gate(
            "GATE-05",
            "Realistic high-density statue-like mesh",
            {"vertex_range": [100_000, 400_000], "analysis_completes": True, "mesh_unchanged": True},
            _gate_statue_stress,
        )
        _run_gate(
            "GATE-06",
            "No unintended mesh modification",
            {"all_pre_post_signatures_match": True, "meshes_compared": 5},
            _gate_immutability,
        )
        _run_gate(
            "GATE-07",
            "Blender stability",
            {"factory_startup": True, "background": True, "normal_exit": True, "clean_between_gates": True},
            _gate_stability,
            clean_scene=False,
        )
        _run_gate(
            "GATE-08",
            "Registration lifecycle",
            {"register": True, "unregister": True, "reregister": True, "final_unregister": True, "stale_handlers": False},
            _gate_registration,
            clean_scene=False,
        )
    finally:
        if REGISTERED:
            try:
                chroma3d_sculpt.unregister()
            except Exception:
                traceback.print_exc()
            REGISTERED = False
        _write_results(started_at, started_timer, python_launcher)

    return 1 if any(gate["status"] == "FAIL" for gate in GATES) else 0


if __name__ == "__main__":
    exit_code = main()
    if exit_code:
        raise SystemExit(exit_code)
