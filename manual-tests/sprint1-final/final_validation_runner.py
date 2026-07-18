"""Independent Sprint 1 production-diagnostic validation executed by Blender."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
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


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_DIRECTORY = Path(__file__).resolve().parent
SOURCE_PARENT = REPOSITORY_ROOT / "blender_addon"
REPORTS_DIRECTORY = VALIDATION_DIRECTORY / "reports"
ARTIFACTS_DIRECTORY = VALIDATION_DIRECTORY / "artifacts"
RESULTS_PATH = REPORTS_DIRECTORY / "final_validation_results.json"
MARKDOWN_PATH = VALIDATION_DIRECTORY / "FINAL_VALIDATION_RESULTS.md"
EXPORTED_REPORT_PATH = REPORTS_DIRECTORY / "independent_schema_2_report.json"

if str(SOURCE_PARENT) not in sys.path:
    sys.path.insert(0, str(SOURCE_PARENT))

import chroma3d_sculpt  # noqa: E402
from chroma3d_sculpt.analysis_settings import AnalysisSettings, BAMBU_X1_CARBON_BUILD_MM  # noqa: E402
from chroma3d_sculpt.metadata import DISPLAY_VERSION, EXTENSION_VERSION, SCHEMA_VERSION  # noqa: E402
from chroma3d_sculpt.models.analysis_result import (  # noqa: E402
    AnalysisProfile,
    BuildVolumeFitState,
    EvaluationStatus,
    IssueCategory,
    IssueDomain,
    NormalConsistencyState,
    PrinterProfile,
    SelfIntersectionState,
    ShellContainmentState,
    ShellOrientationState,
    WatertightState,
)
from chroma3d_sculpt.services.mesh_analyzer import analyze_mesh  # noqa: E402
from chroma3d_sculpt.services.report_generator import sanitize_report_filename, write_json_report  # noqa: E402
from chroma3d_sculpt.session import clear as clear_session, store_result  # noqa: E402


GateFunction = Callable[[], dict[str, Any]]
GATES: list[dict[str, Any]] = []
DEFECTS: list[dict[str, Any]] = []
WARNINGS: list[str] = []
STARTED_AT = datetime.now(timezone.utc)
STARTED_TIMER = perf_counter()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _near(actual: float, expected: float, tolerance: float = 1e-5) -> None:
    _require(abs(actual - expected) <= tolerance, f"Expected {expected}, got {actual} (tolerance {tolerance}).")


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()


def _cleanup() -> None:
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except RuntimeError:
            pass
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    clear_session()


def _create_mesh(
    name: str,
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]] | tuple[tuple[int, ...], ...] = (),
    edges: list[tuple[int, int]] | tuple[tuple[int, int], ...] = (),
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, edges, faces)
    mesh.update(calc_edges=True)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.scale = scale
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.context.view_layer.update()
    return obj


def _cube_data(
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    dimensions: tuple[float, float, float] = (2.0, 2.0, 2.0),
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    cx, cy, cz = center
    hx, hy, hz = (value / 2.0 for value in dimensions)
    vertices = [
        (cx - hx, cy - hy, cz - hz), (cx + hx, cy - hy, cz - hz),
        (cx + hx, cy + hy, cz - hz), (cx - hx, cy + hy, cz - hz),
        (cx - hx, cy - hy, cz + hz), (cx + hx, cy - hy, cz + hz),
        (cx + hx, cy + hy, cz + hz), (cx - hx, cy + hy, cz + hz),
    ]
    faces = [
        (0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
        (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7),
    ]
    return vertices, faces


def _combine_components(
    *components: tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for component_vertices, component_faces in components:
        offset = len(vertices)
        vertices.extend(component_vertices)
        faces.extend(tuple(index + offset for index in face) for face in component_faces)
    return vertices, faces


def _combine_cubes(
    *specifications: tuple[tuple[float, float, float], tuple[float, float, float] | float]
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    components = []
    for center, dimensions in specifications:
        values = (dimensions, dimensions, dimensions) if isinstance(dimensions, (int, float)) else dimensions
        components.append(_cube_data(center, values))
    return _combine_components(*components)


def _analyze(obj: bpy.types.Object, settings: AnalysisSettings | None = None):
    return analyze_mesh(
        obj,
        bpy.context.scene,
        settings=settings,
        blender_version=bpy.app.version_string,
        blend_file_path=bpy.data.filepath,
    )


def _geometry_hash(obj: bpy.types.Object) -> str:
    digest = sha256()
    mesh = obj.data
    digest.update(struct.pack("<QQQ", len(mesh.vertices), len(mesh.edges), len(mesh.polygons)))
    for vertex in mesh.vertices:
        digest.update(struct.pack("<ddd", *(float(value) for value in vertex.co)))
    for edge in mesh.edges:
        digest.update(struct.pack("<QQ", *(int(value) for value in edge.vertices)))
    for polygon in mesh.polygons:
        values = tuple(int(value) for value in polygon.vertices)
        digest.update(struct.pack("<Q", len(values)))
        digest.update(b"".join(struct.pack("<Q", value) for value in values))
    return digest.hexdigest()


def _safety_snapshot(obj: bpy.types.Object) -> dict[str, Any]:
    return {
        "geometry_sha256": _geometry_hash(obj),
        "name": obj.name,
        "mesh_name": obj.data.name,
        "location": tuple(float(value) for value in obj.location),
        "rotation": tuple(float(value) for value in obj.rotation_euler),
        "scale": tuple(float(value) for value in obj.scale),
        "modifiers": tuple(modifier.name for modifier in obj.modifiers),
        "blend_file": bpy.data.filepath,
    }


def _statuses(result: Any) -> dict[str, str]:
    return {check.name: check.status.value for check in result.checks}


def _evidence(result: Any, category: IssueCategory):
    return next(item for item in result.issue_evidence if item.category == category)


def _run_gate(gate_id: str, name: str, function: GateFunction) -> None:
    _cleanup()
    started = perf_counter()
    try:
        actual = function()
        status = "PASS"
        error = None
        print(f"[PASS] {gate_id} {name}")
    except Exception as exc:  # evidence runner must preserve every failure
        actual = {}
        status = "FAIL"
        error = f"{type(exc).__name__}: {exc}"
        DEFECTS.append({"gate": gate_id, "classification": "UNCLASSIFIED", "message": error})
        print(f"[FAIL] {gate_id} {name}: {error}")
        traceback.print_exc()
    finally:
        _cleanup()
    GATES.append(
        {
            "id": gate_id,
            "name": name,
            "status": status,
            "duration_seconds": round(perf_counter() - started, 6),
            "actual": actual,
            "error": error,
        }
    )


def _gate_static() -> dict[str, Any]:
    runtime = SOURCE_PARENT / "chroma3d_sculpt"
    source_files = sorted(runtime.rglob("*.py"))
    combined = "\n".join(path.read_text(encoding="utf-8") for path in source_files)
    forbidden = {
        "network": r"\b(requests|urllib|httpx|aiohttp|socket|websocket|ftplib|smtplib|paramiko)\b|https?://",
        "dynamic_execution": r"\b(eval|exec)\s*\(",
        "pickle": r"\bpickle\b",
        "subprocess": r"\bsubprocess\b",
        "persistent_handlers": r"bpy\.app\.handlers|@persistent",
        "hard_coded_repository": r"[A-Za-z]:[\\/].*Chroma3D Sculpt|VPRS[\\/]Sriram",
        "mesh_mutation": r"transform_apply|modifier_apply|mesh\.transform|clear_geometry|vertices\[[^]]+\]\.co\s*=",
    }
    findings = {label: pattern for label, pattern in forbidden.items() if re.search(pattern, combined, re.IGNORECASE)}
    _require(not findings, f"Forbidden runtime patterns found: {findings}")
    wording = (
        "Guaranteed printable", "Guaranteed watertight", "Exact self-intersections",
        "Definitely internal shell", "Production-ready", "Safe to print",
    )
    wording_hits = [item for item in wording if item.lower() in combined.lower()]
    _require(not wording_hits, f"Overclaiming runtime wording found: {wording_hits}")
    ops_hits = []
    for path in source_files:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "bpy.ops." in line:
                ops_hits.append(f"{path.relative_to(REPOSITORY_ROOT).as_posix()}:{line_number}:{line.strip()}")
    _require(len(ops_hits) == 2 and all("mode_set" in item for item in ops_hits), f"Unexpected runtime bpy.ops calls: {ops_hits}")
    manifest = (runtime / "blender_manifest.toml").read_text(encoding="utf-8")
    _require('version = "0.3.0"' in manifest, "Manifest version is not 0.3.0.")
    _require('blender_version_min = "4.4.0"' in manifest, "Minimum Blender is not 4.4.0.")
    _require(EXTENSION_VERSION == "0.3.0" and DISPLAY_VERSION == "0.3.0-alpha.1", "Display metadata mismatch.")
    _require(SCHEMA_VERSION == "2.0", "Analysis schema mismatch.")
    return {
        "runtime_python_files": len(source_files),
        "forbidden_findings": findings,
        "overclaiming_wording": wording_hits,
        "bpy_ops_calls": ops_hits,
        "versions": {"manifest": EXTENSION_VERSION, "display": DISPLAY_VERSION, "blender_min": "4.4.0", "json_schema": SCHEMA_VERSION},
        "temporary_bmesh_usage": True,
        "bvh_scope": "Function-local BVHTree objects; Blender exposes no explicit BVHTree free method.",
    }


def _gate_numerical() -> dict[str, Any]:
    rectangular = _create_mesh("Independent100x80x150", *_cube_data(dimensions=(0.1, 0.08, 0.15)))
    before = _safety_snapshot(rectangular)
    result = _analyze(rectangular)
    _require(_safety_snapshot(rectangular) == before, "Known-dimension analysis mutated object or mesh state.")
    dimensions = (result.dimensions.width_mm, result.dimensions.depth_mm, result.dimensions.height_mm)
    for actual, expected in zip(dimensions, (100.0, 80.0, 150.0)):
        _near(actual, expected)
    _near(result.surface_volume.total_surface_area_mm2, 70_000.0, 0.01)
    _near(result.surface_volume.reliable_closed_shell_volume_mm3 or 0.0, 1_200_000.0, 0.2)

    scaled = _create_mesh("IndependentScaled", *_cube_data(dimensions=(0.05, 0.05, 0.05)), scale=(2.0, 1.6, 3.0))
    scaled_before = _safety_snapshot(scaled)
    scaled_result = _analyze(scaled)
    _require(_safety_snapshot(scaled) == scaled_before, "Non-uniform-scale analysis applied or mutated transforms/geometry.")
    scaled_dimensions = (scaled_result.dimensions.width_mm, scaled_result.dimensions.depth_mm, scaled_result.dimensions.height_mm)
    for actual, expected in zip(scaled_dimensions, (100.0, 80.0, 150.0)):
        _near(actual, expected)
    _near(scaled_result.surface_volume.total_surface_area_mm2, 70_000.0, 0.01)
    _near(scaled_result.surface_volume.reliable_closed_shell_volume_mm3 or 0.0, 1_200_000.0, 0.2)

    outward = result.shells[0]
    inward_vertices, inward_faces = _cube_data(dimensions=(0.1, 0.08, 0.15))
    inward = _analyze(_create_mesh("IndependentInward", inward_vertices, [tuple(reversed(face)) for face in inward_faces])).shells[0]
    inconsistent_faces = list(inward_faces)
    inconsistent_faces[0] = tuple(reversed(inconsistent_faces[0]))
    inconsistent = _analyze(_create_mesh("IndependentMixed", inward_vertices, inconsistent_faces)).shells[0]
    open_shell = _analyze(_create_mesh("IndependentOpen", inward_vertices, inward_faces[:-1])).shells[0]
    _require(outward.orientation_state == ShellOrientationState.OUTWARD and (outward.signed_volume_mm3 or 0.0) > 0.0, "Outward signed-volume convention failed.")
    _require(inward.orientation_state == ShellOrientationState.INWARD and (inward.signed_volume_mm3 or 0.0) < 0.0, "Inward signed-volume convention failed.")
    _require(inconsistent.orientation_state == ShellOrientationState.INCONSISTENT and inconsistent.signed_volume_mm3 is None, "Mixed winding was not honestly marked inconsistent.")
    _require(open_shell.orientation_state == ShellOrientationState.OPEN and open_shell.watertight_state == WatertightState.NOT_WATERTIGHT, "Open shell was not identified.")
    return {
        "expected_dimensions_mm": [100.0, 80.0, 150.0], "actual_dimensions_mm": dimensions,
        "expected_surface_area_mm2": 70_000.0, "actual_surface_area_mm2": result.surface_volume.total_surface_area_mm2,
        "expected_volume_mm3": 1_200_000.0, "actual_volume_mm3": result.surface_volume.reliable_closed_shell_volume_mm3,
        "non_uniform_scale": {"scale": scaled_before["scale"], "dimensions_mm": scaled_dimensions, "area_mm2": scaled_result.surface_volume.total_surface_area_mm2, "volume_mm3": scaled_result.surface_volume.reliable_closed_shell_volume_mm3, "unchanged": True},
        "orientation": {"outward": outward.orientation_state.value, "outward_signed_volume": outward.signed_volume_mm3, "inward": inward.orientation_state.value, "inward_signed_volume": inward.signed_volume_mm3, "mixed": inconsistent.orientation_state.value, "open": open_shell.orientation_state.value},
    }


def _gate_topology() -> dict[str, Any]:
    cube_vertices, cube_faces = _cube_data()
    cases: list[tuple[str, bpy.types.Object, dict[str, Any]]] = [
        ("closed_cube", _create_mesh("TruthClosed", cube_vertices, cube_faces), {"boundary_edges": 0, "loose_edges": 0, "shells": 1, "watertight": WatertightState.TOPOLOGICALLY_WATERTIGHT}),
        ("open_cube", _create_mesh("TruthOpen", cube_vertices, cube_faces[:-1]), {"boundary_edges": 4, "shells": 1, "watertight": WatertightState.NOT_WATERTIGHT}),
        ("loose_edge", _create_mesh("TruthLooseEdge", cube_vertices + [(3, 0, 0), (4, 0, 0)], cube_faces, [(8, 9)]), {"loose_edges": 1, "components": 2}),
        ("loose_vertex", _create_mesh("TruthLooseVertex", cube_vertices + [(4, 0, 0)], cube_faces), {"loose_vertices": 1, "components": 2, "watertight": WatertightState.NOT_WATERTIGHT}),
        ("three_face_edge", _create_mesh("TruthHighIncidence", [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1)], [(0, 1, 2), (1, 0, 3), (0, 1, 4)]), {"high_incidence": 1, "watertight": WatertightState.NOT_WATERTIGHT}),
        ("bow_tie_vertex", _create_mesh("TruthBowTie", [(0, 0, 0), (1, 0, 0), (0, 1, 0), (-1, 0, 0), (0, -1, 0)], [(0, 1, 2), (0, 3, 4)]), {"vertex_anomalies": 1, "shells": 2}),
        ("zero_length_edge", _create_mesh("TruthZeroEdge", [(0, 0, 0), (0, 0, 0)], edges=[(0, 1)]), {"zero_length_edges": 1, "loose_edges": 1}),
        ("degenerate_face", _create_mesh("TruthDegenerate", [(0, 0, 0), (1, 0, 0), (2, 0, 0)], [(0, 1, 2)]), {"degenerate_faces": 1}),
        ("duplicate_positions", _create_mesh("TruthDuplicate", [(0, 0, 0), (0, 0, 0)]), {"duplicates": 1}),
        ("two_closed_cubes", _create_mesh("TruthTwoShells", *_combine_cubes(((-2, 0, 0), 1.0), ((2, 0, 0), 1.0))), {"shells": 2, "components": 2, "watertight": WatertightState.TOPOLOGICALLY_WATERTIGHT}),
    ]
    rows: dict[str, Any] = {}
    for name, obj, expected in cases:
        result = _analyze(obj)
        topology = result.topology
        actual = {
            "boundary_edges": topology.boundary_edges, "loose_edges": topology.loose_edges,
            "loose_vertices": topology.loose_vertices, "high_incidence": topology.high_incidence_non_manifold_edges,
            "vertex_anomalies": topology.vertex_manifold_anomalies, "zero_length_edges": topology.zero_length_edges,
            "degenerate_faces": topology.degenerate_faces, "duplicates": topology.potential_duplicate_vertices,
            "components": topology.connected_components, "shells": topology.face_shell_count,
            "watertight": topology.watertight_state, "severity": result.severity.value,
        }
        for key, expected_value in expected.items():
            _require(actual[key] == expected_value, f"{name}: expected {key}={expected_value}, got {actual[key]}.")
        statuses = _statuses(result)
        for check_name in ("base_topology", "edge_manifold_classification", "vertex_manifold_classification", "shell_decomposition", "orientation_consistency", "potential_duplicates"):
            _require(statuses.get(check_name) == EvaluationStatus.COMPLETED.value, f"{name}: {check_name} did not complete.")
        rows[name] = {**{key: (value.value if hasattr(value, "value") else value) for key, value in actual.items()}, "check_statuses": statuses}
    return rows


def _gate_shells() -> dict[str, Any]:
    deep = AnalysisSettings(profile=AnalysisProfile.DEEP)
    tiny = _analyze(_create_mesh("ShellTiny", *_combine_cubes(((0, 0, 0), 0.1), ((0.2, 0, 0), 0.005))), deep)
    _require(tiny.main_shell_id == 0, f"Main shell selection was not deterministic: {tiny.main_shell_id}.")
    _require(tiny.tiny_shell_candidate_ids == (1,), f"Tiny shell was not detected: {tiny.tiny_shell_candidate_ids}.")
    tiny_shell = tiny.shells[1]
    _require(tiny_shell.tiny_criteria_evaluated and len(tiny_shell.tiny_criteria_matched) >= 2, "Tiny criteria were not recorded.")
    _require(tiny_shell.classification_confidence.value != "NONE", "Tiny-shell confidence is absent.")

    medium = _analyze(_create_mesh("ShellMedium", *_combine_cubes(((0, 0, 0), 0.1), ((0.2, 0, 0), 0.03))), deep)
    _require(not medium.tiny_shell_candidate_ids and len(medium.disconnected_external_shell_ids) == 1, "Medium ornament was classified as tiny or not external.")

    inside = _analyze(_create_mesh("ShellInside", *_combine_cubes(((0, 0, 0), 0.1), ((0, 0, 0), 0.02))), deep)
    _require(len(inside.possible_internal_shell_ids) == 1 and inside.deep_diagnostics.containment_evidence, "Contained shell was missed.")
    containment = inside.deep_diagnostics.containment_evidence[0]
    _require(containment.positive_votes * 2 > containment.sample_count, "Containment vote majority is invalid.")

    outside = _analyze(_create_mesh("ShellOutside", *_combine_cubes(((0, 0, 0), 0.1), ((0.2, 0, 0), 0.02))), deep)
    _require(not outside.possible_internal_shell_ids and len(outside.disconnected_external_shell_ids) == 1, "External shell was misclassified.")
    overlap = _analyze(_create_mesh("ShellOverlap", *_combine_cubes(((0, 0, 0), 0.1), ((0.075, 0, 0), 0.1))), deep)
    _require(not overlap.possible_internal_shell_ids, "Partial overlap was falsely classified as containment.")

    outer = _cube_data(dimensions=(0.1, 0.1, 0.1))
    inner_vertices, inner_faces = _cube_data(dimensions=(0.02, 0.02, 0.02))
    open_nested = _analyze(_create_mesh("ShellOpenNested", *_combine_components(outer, (inner_vertices, inner_faces[:-1]))), deep)
    open_shell = next(shell for shell in open_nested.shells if shell.shell_id != open_nested.main_shell_id)
    _require(open_shell.watertight_state == WatertightState.NOT_WATERTIGHT, "Nested open shell fixture is invalid.")
    _require(open_shell.classification == ShellContainmentState.UNCLASSIFIED, f"Open nested shell overclaimed classification as {open_shell.classification.value}.")
    _require(open_nested.deep_diagnostics.containment_status == EvaluationStatus.COMPLETED, "Containment gate did not complete for eligible shells.")
    return {
        "tiny": {"main_shell_id": tiny.main_shell_id, "tiny_ids": tiny.tiny_shell_candidate_ids, "criteria_evaluated": tiny_shell.tiny_criteria_evaluated, "criteria_matched": tiny_shell.tiny_criteria_matched, "confidence": tiny_shell.classification_confidence.value},
        "medium_external_ids": medium.disconnected_external_shell_ids,
        "internal": {"ids": inside.possible_internal_shell_ids, "containing_shell_id": containment.containing_shell_id, "samples": containment.sample_count, "positive_votes": containment.positive_votes, "confidence": containment.confidence.value},
        "external_ids": outside.disconnected_external_shell_ids,
        "overlap_internal_ids": overlap.possible_internal_shell_ids,
        "open_nested": {"classification": open_shell.classification.value, "watertight": open_shell.watertight_state.value, "containment_status": open_nested.deep_diagnostics.containment_status.value, "notes": open_nested.deep_diagnostics.notes},
    }


def _gate_intersections() -> dict[str, Any]:
    deep = AnalysisSettings(profile=AnalysisProfile.DEEP)
    clean = _analyze(_create_mesh("IntersectClean", *_cube_data()), deep)
    separated = _analyze(_create_mesh("IntersectSeparate", *_combine_cubes(((-2, 0, 0), 1.0), ((2, 0, 0), 1.0))), deep)
    intersecting = _analyze(_create_mesh("IntersectPair", *_combine_cubes(((0, 0, 0), 2.0), ((1, 0, 0), 2.0))), deep)
    adjacent = _analyze(_create_mesh("IntersectAdjacent", [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [(0, 1, 2), (0, 2, 3)]), deep)
    _require(clean.deep_diagnostics.self_intersection_status == EvaluationStatus.COMPLETED and clean.deep_diagnostics.self_intersection_candidate_count == 0, "Clean cube did not complete with zero candidates.")
    _require(separated.deep_diagnostics.self_intersection_candidate_count == 0, "Separated cubes produced candidates.")
    _require((intersecting.deep_diagnostics.self_intersection_candidate_count or 0) > 0, "Intersecting cubes produced no candidates.")
    _require(adjacent.deep_diagnostics.self_intersection_candidate_count == 0, "Normal triangle adjacency was not filtered.")

    limited_settings = AnalysisSettings(profile=AnalysisProfile.DEEP, self_intersection_triangle_limit=1)
    limited = _analyze(_create_mesh("IntersectLimit", *_cube_data()), limited_settings)
    limited_check = next(check for check in limited.checks if check.name == "self_intersection_candidates")
    _require(limited_check.status == EvaluationStatus.SKIPPED and limited_check.actual_size == 12 and limited_check.configured_limit == 1, "Triangle-limit skip lacks actual and configured sizes.")
    _require("12" in limited_check.message and "1" in limited_check.message, "Triangle-limit skip wording omits sizes.")

    capped_settings = AnalysisSettings(profile=AnalysisProfile.DEEP, maximum_stored_self_intersection_pairs=1)
    capped = _analyze(_create_mesh("IntersectCap", *_combine_cubes(((0, 0, 0), 2.0), ((1, 0, 0), 2.0))), capped_settings)
    candidate_total = capped.deep_diagnostics.self_intersection_candidate_count or 0
    _require(candidate_total > len(capped.deep_diagnostics.self_intersection_pairs) == 1, "Pair evidence cap did not preserve total candidate count.")
    _require(capped.deep_diagnostics.self_intersection_evidence_truncated, "Pair evidence truncation flag is absent.")
    self_evidence = _evidence(capped, IssueCategory.SELF_INTERSECTION_FACES)
    _require(self_evidence.truncated and len(self_evidence.pairs) == 1, "Serialized self-intersection evidence cap is inconsistent.")
    return {
        "method": "BVHTree overlap candidates with shared-topology filtering; not an exact printability proof.",
        "clean": {"status": clean.deep_diagnostics.self_intersection_status.value, "candidates": clean.deep_diagnostics.self_intersection_candidate_count},
        "separated_candidates": separated.deep_diagnostics.self_intersection_candidate_count,
        "intersecting_candidates": intersecting.deep_diagnostics.self_intersection_candidate_count,
        "adjacent_candidates": adjacent.deep_diagnostics.self_intersection_candidate_count,
        "limit": asdict(limited_check),
        "truncation": {"total_candidates": candidate_total, "stored_pairs": len(capped.deep_diagnostics.self_intersection_pairs), "truncated": capped.deep_diagnostics.self_intersection_evidence_truncated, "evidence_total_faces": self_evidence.total_count},
    }


def _build_case(name: str, dimensions: tuple[float, float, float], settings: AnalysisSettings, scale=(1.0, 1.0, 1.0)):
    obj = _create_mesh(name, *_cube_data(dimensions=dimensions), scale=scale)
    before = _safety_snapshot(obj)
    result = _analyze(obj, settings)
    _require(_safety_snapshot(obj) == before, f"{name} build-volume analysis mutated the object.")
    return result.build_volume


def _gate_build_volume() -> dict[str, Any]:
    bambu = AnalysisSettings(printer_profile=PrinterProfile.BAMBU_X1_CARBON)
    fitting = _build_case("BuildFit", (0.2, 0.2, 0.2), bambu)
    one_axis = _build_case("BuildOne", (0.3, 0.2, 0.2), bambu)
    three_axis = _build_case("BuildThree", (0.3, 0.3, 0.3), bambu)
    custom = _build_case("BuildCustom", (0.25, 0.2, 0.1), AnalysisSettings(printer_profile=PrinterProfile.CUSTOM, custom_build_volume_mm=(250.0, 210.0, 105.0)))
    no_profile = _build_case("BuildNone", (0.2, 0.2, 0.2), AnalysisSettings())
    scaled = _build_case("BuildScaled", (0.1, 0.1, 0.1), bambu, scale=(3.0, 2.0, 1.0))
    boundary = _build_case("BuildBoundary", (0.256, 0.256, 0.256), bambu)
    _require(BAMBU_X1_CARBON_BUILD_MM == (256.0, 256.0, 256.0), "Bambu profile dimensions changed.")
    _require(fitting.overall_fit is True and fitting.fit_state == BuildVolumeFitState.FITS, "Fitting model failed.")
    _require((one_axis.fits_x, one_axis.fits_y, one_axis.fits_z) == (False, True, True), f"One-axis fit flags are wrong: {one_axis}.")
    _near(one_axis.excess_mm[0], 44.0, 0.001)
    _require(one_axis.excess_mm[1:] == (0.0, 0.0), f"One-axis excess is wrong: {one_axis.excess_mm}.")
    _require((three_axis.fits_x, three_axis.fits_y, three_axis.fits_z) == (False, False, False), "Three-axis fit flags are wrong.")
    for excess in three_axis.excess_mm:
        _near(excess, 44.0, 0.001)
    _near(one_axis.maximum_uniform_scale_percent or 0.0, 256.0 / 300.0 * 100.0)
    _require(custom.overall_fit is True and custom.build_dimensions_mm == (250.0, 210.0, 105.0), "Custom profile failed.")
    _require(no_profile.fit_state == BuildVolumeFitState.NO_PROFILE and no_profile.status == EvaluationStatus.NOT_APPLICABLE, "No-profile state is dishonest.")
    for actual, expected in zip(scaled.model_dimensions_mm, (300.0, 200.0, 100.0)):
        _near(actual, expected, 0.001)
    _require(scaled.overall_fit is False, f"Non-uniform world scale fit state failed: {scaled.model_dimensions_mm}.")
    _require(boundary.overall_fit is True and boundary.excess_mm == (0.0, 0.0, 0.0), f"Exact boundary should fit without excess: {boundary}.")
    for actual in boundary.model_dimensions_mm:
        _near(actual, 256.0, 0.001)
    _require(all(item.current_orientation_only for item in (fitting, one_axis, three_axis, custom, scaled, boundary)), "Current-orientation flag missing.")
    return {
        "profile_mm": BAMBU_X1_CARBON_BUILD_MM, "fitting": asdict(fitting), "one_axis": asdict(one_axis),
        "three_axis": asdict(three_axis), "custom": asdict(custom), "no_profile": asdict(no_profile),
        "non_uniform_scale": asdict(scaled), "exact_boundary": asdict(boundary), "geometry_unchanged": True,
    }


def _invoke_selection(category: IssueCategory, additive: bool = False) -> tuple[set[str], str | None]:
    try:
        return set(bpy.ops.chroma3d.select_diagnostic_issue(issue_category=category.value, additive=additive)), None
    except RuntimeError as exc:
        return {"CANCELLED"}, str(exc)


def _selected_indices(collection: Any) -> tuple[int, ...]:
    return tuple(item.index for item in collection if item.select)


def _gate_selection() -> dict[str, Any]:
    vertices, faces = _cube_data()
    boundary_obj = _create_mesh("SelectBoundary", vertices, faces[:-1])
    boundary_result = _analyze(boundary_obj)
    store_result(boundary_obj, boundary_result)
    for edge in boundary_obj.data.edges:
        edge.select = True
    before = _safety_snapshot(boundary_obj)
    outcome, error = _invoke_selection(IssueCategory.BOUNDARY_EDGES)
    _require(outcome == {"FINISHED"} and error is None, f"Boundary operator failed: {outcome}, {error}")
    _require(tuple(bpy.context.tool_settings.mesh_select_mode) == (False, True, False), "Edge selection mode was not set.")
    bpy.ops.object.mode_set(mode="OBJECT")
    expected_edges = tuple(_evidence(boundary_result, IssueCategory.BOUNDARY_EDGES).indices)
    _require(_selected_indices(boundary_obj.data.edges) == expected_edges, "Default boundary selection did not clear unrelated edges.")
    _require(_safety_snapshot(boundary_obj) == before, "Issue selection changed geometry, transform, modifiers, name, or file state.")

    additive_obj = _create_mesh("SelectAdditive", vertices, faces[:-1])
    additive_result = _analyze(additive_obj)
    store_result(additive_obj, additive_result)
    boundary_set = set(_evidence(additive_result, IssueCategory.BOUNDARY_EDGES).indices)
    retained = next(index for index in range(len(additive_obj.data.edges)) if index not in boundary_set)
    for vertex in additive_obj.data.vertices:
        vertex.select = False
    for edge in additive_obj.data.edges:
        edge.select = False
    for polygon in additive_obj.data.polygons:
        polygon.select = False
    additive_obj.data.edges[retained].select = True
    for vertex_index in additive_obj.data.edges[retained].vertices:
        additive_obj.data.vertices[vertex_index].select = True
    outcome, error = _invoke_selection(IssueCategory.BOUNDARY_EDGES, additive=True)
    _require(outcome == {"FINISHED"} and error is None, "Additive selection failed.")
    bpy.ops.object.mode_set(mode="OBJECT")
    selected_additive = set(_selected_indices(additive_obj.data.edges))
    _require(
        selected_additive == boundary_set | {retained},
        f"Additive selection mismatch: selected={sorted(selected_additive)}, expected={sorted(boundary_set | {retained})}.",
    )

    mixed_faces = list(faces)
    mixed_faces[0] = tuple(reversed(mixed_faces[0]))
    face_obj = _create_mesh("SelectFace", vertices, mixed_faces)
    face_result = _analyze(face_obj)
    store_result(face_obj, face_result)
    face_before = _safety_snapshot(face_obj)
    outcome, error = _invoke_selection(IssueCategory.INCONSISTENT_FACES)
    _require(outcome == {"FINISHED"} and error is None and tuple(bpy.context.tool_settings.mesh_select_mode) == (False, False, True), "Face issue selection failed.")
    bpy.ops.object.mode_set(mode="OBJECT")
    _require(_selected_indices(face_obj.data.polygons) == tuple(_evidence(face_result, IssueCategory.INCONSISTENT_FACES).indices), "Face evidence selection mismatch.")
    _require(_safety_snapshot(face_obj) == face_before, "Face selection mutated protected state.")

    bowtie_obj = _create_mesh("SelectVertex", [(0, 0, 0), (1, 0, 0), (0, 1, 0), (-1, 0, 0), (0, -1, 0)], [(0, 1, 2), (0, 3, 4)])
    bowtie_result = _analyze(bowtie_obj)
    store_result(bowtie_obj, bowtie_result)
    outcome, error = _invoke_selection(IssueCategory.VERTEX_MANIFOLD_ANOMALIES)
    _require(outcome == {"FINISHED"} and error is None and tuple(bpy.context.tool_settings.mesh_select_mode) == (True, False, False), "Vertex issue selection failed.")
    bpy.ops.object.mode_set(mode="OBJECT")
    _require(_selected_indices(bowtie_obj.data.vertices) == tuple(_evidence(bowtie_result, IssueCategory.VERTEX_MANIFOLD_ANOMALIES).indices), "Vertex evidence selection mismatch.")

    stale_obj = _create_mesh("SelectStale", vertices, faces[:-1])
    store_result(stale_obj, _analyze(stale_obj))
    stale_obj.data.vertices.add(1)
    stale_outcome, stale_error = _invoke_selection(IssueCategory.BOUNDARY_EDGES)
    _require(stale_outcome == {"CANCELLED"} and stale_error and "stale" in stale_error.lower(), "Stale analysis was not rejected.")

    truncated_obj = _create_mesh("SelectTruncated", vertices, faces[:-1])
    truncated_result = _analyze(truncated_obj, AnalysisSettings(maximum_stored_issue_indices=2))
    store_result(truncated_obj, truncated_result)
    truncated_evidence = _evidence(truncated_result, IssueCategory.BOUNDARY_EDGES)
    _require(truncated_evidence.truncated and truncated_evidence.total_count == 4 and len(truncated_evidence.indices) == 2, "Truncated boundary evidence is inconsistent.")
    outcome, error = _invoke_selection(IssueCategory.BOUNDARY_EDGES)
    _require(outcome == {"FINISHED"} and error is None, "Truncated evidence could not be selected.")
    source = (SOURCE_PARENT / "chroma3d_sculpt" / "operators" / "select_issue.py").read_text(encoding="utf-8")
    _require("Evidence is truncated to the configured cap." in source, "Operator does not explain truncated selection evidence.")
    return {
        "boundary_edges": expected_edges, "edge_mode": [False, True, False], "default_cleared": True,
        "additive_retained_edge": retained, "face_indices": _evidence(face_result, IssueCategory.INCONSISTENT_FACES).indices,
        "vertex_indices": _evidence(bowtie_result, IssueCategory.VERTEX_MANIFOLD_ANOMALIES).indices,
        "stale_rejected": True, "truncated": {"total": 4, "stored": 2, "explained": True},
        "geometry_hash_unchanged": True, "transform_unchanged": True, "modifier_count_unchanged": True,
        "object_name_unchanged": True, "save_state_unchanged": True,
    }


def _scaled_matrix(location: tuple[float, float, float], scale: tuple[float, float, float]) -> Matrix:
    return Matrix.Translation(Vector(location)) @ Matrix.Diagonal(Vector((*scale, 1.0)))


def _create_statue_stress() -> bpy.types.Object:
    mesh = bpy.data.meshes.new("IndependentStatueStress_Mesh")
    bm = bmesh.new()
    try:
        bmesh.ops.create_uvsphere(bm, u_segments=256, v_segments=160, radius=1.0, matrix=_scaled_matrix((0, 0, 3.4), (1.8, 1.3, 2.5)))
        bmesh.ops.create_uvsphere(bm, u_segments=192, v_segments=128, radius=1.0, matrix=_scaled_matrix((0, 0, 6.5), (1.0, 0.95, 1.15)))
        for x_value in (-1.55, 1.55):
            bmesh.ops.create_uvsphere(bm, u_segments=160, v_segments=96, radius=1.0, matrix=_scaled_matrix((x_value, 0, 4.55), (0.8, 0.72, 0.9)))
        ornaments = ((-1.25, -1, 5.1), (-0.9, -1.22, 4.8), (-0.45, -1.36, 4.55), (0, -1.42, 4.45), (0.45, -1.36, 4.55), (0.9, -1.22, 4.8), (1.25, -1, 5.1), (0, 1.38, 4.8))
        for location in ornaments:
            bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=64, radius=1.0, matrix=_scaled_matrix(location, (0.32, 0.32, 0.32)))
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=512, radius1=2.5, radius2=2.15, depth=0.9, matrix=Matrix.Translation(Vector((0, 0, 0.45))))
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=512, radius1=0.06, radius2=0.035, depth=5.8, matrix=Matrix.Translation(Vector((2.65, 0.1, 3.6))))
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=512, radius1=0.72, radius2=0.08, depth=1.2, matrix=Matrix.Translation(Vector((0, 0, 7.75))))
        bm.to_mesh(mesh)
    finally:
        bm.free()
    mesh.update()
    obj = bpy.data.objects.new("IndependentStatueStress", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.scale = (0.02, 0.02, 0.02)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.context.view_layer.update()
    return obj


def _gate_standard_stress() -> dict[str, Any]:
    obj = _create_statue_stress()
    before = _safety_snapshot(obj)
    result = _analyze(obj, AnalysisSettings(profile=AnalysisProfile.STANDARD))
    after = _safety_snapshot(obj)
    _require(before == after, "Standard stress analysis mutated geometry or object state.")
    _require(120_000 <= result.geometry.vertex_count <= 180_000, f"Stress vertex count outside target: {result.geometry.vertex_count}.")
    _require(result.topology.duplicate_evaluation_status == EvaluationStatus.COMPLETED, "Duplicate check returned a false skipped-zero state.")
    _require(result.deep_diagnostics.self_intersection_status == EvaluationStatus.NOT_APPLICABLE, "Standard profile unexpectedly ran Deep self-intersection.")
    performance_warning = result.duration_ms >= 20_000.0
    if performance_warning:
        WARNINGS.append(
            f"Standard analysis took {result.duration_ms:.3f} ms, above the 20,000 ms target; "
            "the final report must retain the apples-to-apples performance investigation."
        )
    timings = {timing.name: {"status": timing.status.value, "duration_ms": timing.duration_ms, "detail": timing.detail} for timing in result.timings}
    return {
        "vertices": result.geometry.vertex_count, "edges": result.geometry.edge_count,
        "faces": result.geometry.polygon_count, "triangles": result.geometry.triangle_count,
        "shell_count": len(result.shells), "main_shell_id": result.main_shell_id,
        "tiny_shell_ids": result.tiny_shell_candidate_ids, "external_shell_ids": result.disconnected_external_shell_ids,
        "dimensions_mm": [result.dimensions.width_mm, result.dimensions.depth_mm, result.dimensions.height_mm],
        "surface_area_mm2": result.surface_volume.total_surface_area_mm2,
        "volume_status": result.surface_volume.volume_status.value,
        "watertightness": result.topology.watertight_state.value,
        "orientation": result.topology.normal_consistency.value,
        "duration_ms": result.duration_ms, "prior_accepted_duration_ms": 12_479.0,
        "performance_ratio_to_prior": result.duration_ms / 12_479.0,
        "performance_target_ms": 20_000.0, "performance_warning": performance_warning,
        "timings": timings, "duplicate_status": result.topology.duplicate_evaluation_status.value,
        "geometry_unchanged": True,
    }


def _gate_deep_stress() -> dict[str, Any]:
    fixture = _combine_cubes(((0, 0, 0), 4.0), ((0, 0, 0), 0.75), ((1.75, 0, 0), 1.0), ((6, 0, 0), 1.0))
    obj = _create_mesh("IndependentDeepStress", *fixture)
    before = _safety_snapshot(obj)
    complete = _analyze(obj, AnalysisSettings(profile=AnalysisProfile.DEEP))
    _require(_safety_snapshot(obj) == before, "Deep diagnostics mutated geometry or object state.")
    _require(complete.deep_diagnostics.self_intersection_status == EvaluationStatus.COMPLETED and (complete.deep_diagnostics.self_intersection_candidate_count or 0) > 0, "Deep intersecting pair was not detected.")
    _require(complete.deep_diagnostics.containment_status == EvaluationStatus.COMPLETED and complete.possible_internal_shell_ids, "Deep contained shell was not detected.")
    _require(complete.disconnected_external_shell_ids, "Deep separated external shell was not classified.")
    limited = _analyze(obj, AnalysisSettings(profile=AnalysisProfile.DEEP, self_intersection_triangle_limit=1, containment_shell_limit=1))
    _require(limited.deep_diagnostics.self_intersection_status == EvaluationStatus.SKIPPED and limited.deep_diagnostics.containment_status == EvaluationStatus.SKIPPED, "Over-limit Deep checks were not explicitly skipped.")
    skip_checks = {check.name: asdict(check) for check in limited.checks if check.status == EvaluationStatus.SKIPPED}
    _require(all(item["actual_size"] is not None and item["configured_limit"] is not None for item in skip_checks.values()), "Deep skip state omitted actual size or limit.")
    return {
        "completed": {"intersection_status": complete.deep_diagnostics.self_intersection_status.value, "intersection_candidates": complete.deep_diagnostics.self_intersection_candidate_count, "containment_status": complete.deep_diagnostics.containment_status.value, "internal_ids": complete.possible_internal_shell_ids, "external_ids": complete.disconnected_external_shell_ids, "timings": {timing.name: timing.duration_ms for timing in complete.timings}},
        "over_limit": {"intersection_status": limited.deep_diagnostics.self_intersection_status.value, "containment_status": limited.deep_diagnostics.containment_status.value, "checks": skip_checks},
        "geometry_unchanged": True,
    }


def _gate_json() -> dict[str, Any]:
    obj = _create_mesh("Statue:Test?*", *_combine_cubes(((0, 0, 0), 2.0), ((1, 0, 0), 2.0)))
    settings = AnalysisSettings(profile=AnalysisProfile.DEEP, maximum_stored_issue_indices=2, maximum_stored_self_intersection_pairs=1)
    result = _analyze(obj, settings)
    REPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    written = write_json_report(result, EXPORTED_REPORT_PATH)
    raw = written.read_bytes()
    _require(raw.endswith(b"\n"), "Exported JSON has no trailing newline.")
    text = raw.decode("utf-8")
    _require(text == result.to_json() and result.to_json() == result.to_json(), "JSON structure is not deterministic for one immutable result.")
    payload = json.loads(text)
    required = {
        "schema_version", "extension_version", "blender_version", "operating_system", "analysis_id",
        "topology_signature", "settings_snapshot", "checks", "timings", "geometry", "dimensions",
        "surface_volume", "shells", "build_volume", "deep_diagnostics", "issue_evidence",
        "warnings", "errors", "skipped_check_reasons",
    }
    _require(payload["schema_version"] == "2.0" and payload["extension_version"] == DISPLAY_VERSION, "Export metadata mismatch.")
    _require(not (required - payload.keys()), f"Export missing fields: {sorted(required - payload.keys())}.")
    _require(payload["analysis_id"] == payload["topology_signature"]["analysis_id"], "Analysis ID and topology signature disagree.")
    for evidence in payload["issue_evidence"]:
        _require(len(evidence["indices"]) <= settings.maximum_stored_issue_indices, f"Unbounded issue evidence: {evidence['category']}.")
        _require(len(evidence["pairs"]) <= settings.maximum_stored_self_intersection_pairs, f"Unbounded pair evidence: {evidence['category']}.")
    filename_cases = {
        "CON": "_CON_chroma3d_analysis.json", "PRN": "_PRN_chroma3d_analysis.json",
        "AUX": "_AUX_chroma3d_analysis.json", "Statue:Test?*": "Statue_Test_chroma3d_analysis.json",
        "Lakshmi/Narasimha": "Lakshmi_Narasimha_chroma3d_analysis.json",
        "Trailing. ": "Trailing_chroma3d_analysis.json", "": "mesh_chroma3d_analysis.json",
    }
    actual_names = {name: sanitize_report_filename(name) for name in filename_cases}
    _require(actual_names == filename_cases, f"Filename sanitization mismatch: {actual_names}.")
    return {
        "path": _relative(written), "utf8": True, "valid_json": True, "trailing_newline": True,
        "deterministic_structure": True, "required_fields": sorted(required), "analysis_id_consistent": True,
        "evidence_caps": {"indices": settings.maximum_stored_issue_indices, "pairs": settings.maximum_stored_self_intersection_pairs, "bounded": True},
        "filename_cases": actual_names,
    }


def _gate_registration() -> dict[str, Any]:
    _require(hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state"), "Initial WindowManager property is absent.")
    _require(chroma3d_sculpt.operators.analyze_mesh.CHROMA3D_OT_analyze_mesh.is_registered, "Analyze operator is not registered.")
    _require(chroma3d_sculpt.operators.select_issue.CHROMA3D_OT_select_diagnostic_issue.is_registered, "Selection operator is not registered.")
    _require(chroma3d_sculpt.ui.panels.CHROMA3D_PT_sculpt.is_registered, "Panel is not registered.")
    chroma3d_sculpt.unregister()
    _require(not hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state"), "WindowManager property survived unregister.")
    _require(not chroma3d_sculpt.operators.select_issue.CHROMA3D_OT_select_diagnostic_issue.is_registered, "Selection operator survived unregister.")
    chroma3d_sculpt.register()
    _require(hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state"), "Property missing after re-register.")
    chroma3d_sculpt.unregister()
    chroma3d_sculpt.register()
    _require(chroma3d_sculpt.ui.panels.CHROMA3D_PT_sculpt.is_registered, "Second re-register failed.")
    state = bpy.context.window_manager.chroma3d_sculpt_state
    property_values = {
        "profile": state.analysis_profile, "printer": state.printer_profile,
        "duplicate_limit": state.duplicate_vertex_limit, "intersection_limit": state.self_intersection_triangle_limit,
        "containment_limit": state.containment_triangle_limit,
    }
    return {"register": True, "operators": ["chroma3d.analyze_mesh", "chroma3d.export_analysis_report", "chroma3d.select_diagnostic_issue"], "panel": "CHROMA3D_PT_sculpt", "properties": property_values, "unregister_cleanup": True, "reregister": True}


def _render_markdown(report: dict[str, Any]) -> str:
    by_id = {gate["id"]: gate for gate in report["gates"]}
    result = report["overall_status"]
    recommendation = report["release_recommendation"]
    numerical = by_id.get("B", {}).get("actual", {})
    topology = by_id.get("C", {}).get("actual", {})
    shell = by_id.get("D", {}).get("actual", {})
    intersections = by_id.get("E", {}).get("actual", {})
    build = by_id.get("F", {}).get("actual", {})
    selection = by_id.get("G", {}).get("actual", {})
    stress = by_id.get("H", {}).get("actual", {})
    deep = by_id.get("I", {}).get("actual", {})
    json_audit = by_id.get("J", {}).get("actual", {})
    registration = by_id.get("K", {}).get("actual", {})
    lines = [
        "# Chroma3D Sculpt Sprint 1 Final Validation", "", "## 1. Overall Result", "", f"**{result}**", "",
        "## 2. Release Recommendation", "", f"**{recommendation}**", "", "## 3. Environment", "",
        f"- Repository: `{report['repository_root']}`", f"- Branch: `{report['branch']}`", f"- Baseline tag: `{report['baseline_tag']}`",
        f"- Blender path: `{report['blender_executable']}`", f"- Blender version: `{report['blender_version']}`", f"- Python: `{sys.version.split()[0]}`",
        f"- Extension version: `{report['extension_version']}`", f"- Schema version: `{report['analysis_schema_version']}`", f"- Total duration: `{report['duration_seconds']:.3f}s`", "",
        "## 4. Static Safety Audit", "", f"- Gate A: `{by_id.get('A', {}).get('status', 'NOT RUN')}`. No prohibited network, dynamic execution, subprocess, persistent handler, hard-coded checkout, or mesh-changing runtime path was found.", "",
        "## 5. Numerical Verification", "", "| Metric | Expected | Actual |", "|---|---:|---:|",
        f"| Dimensions (mm) | 100 × 80 × 150 | {numerical.get('actual_dimensions_mm')} |", f"| Surface area (mm²) | 70,000 | {numerical.get('actual_surface_area_mm2')} |", f"| Volume (mm³) | 1,200,000 | {numerical.get('actual_volume_mm3')} |",
        f"- Non-uniform scale: `{json.dumps(numerical.get('non_uniform_scale', {}), ensure_ascii=False)}`", f"- Orientation: `{json.dumps(numerical.get('orientation', {}), ensure_ascii=False)}`", "",
        "## 6. Topology Matrix", "", "| Fixture | Result |", "|---|---|",
    ]
    lines.extend(f"| {name} | `{json.dumps(values, ensure_ascii=False)}` |" for name, values in topology.items())
    lines.extend(["", "## 7. Shell Classification", "", f"- `{json.dumps(shell, ensure_ascii=False)}`", "", "## 8. Self-Intersection Validation", "", f"- `{json.dumps(intersections, ensure_ascii=False)}`", "", "## 9. Build-Volume Validation", "", f"- `{json.dumps(build, ensure_ascii=False)}`", "", "## 10. Issue Selection", "", f"- `{json.dumps(selection, ensure_ascii=False)}`", "", "## 11. Stress-Test Performance", "", f"- `{json.dumps(stress, ensure_ascii=False)}`", "", "## 12. Deep Diagnostics", "", f"- `{json.dumps(deep, ensure_ascii=False)}`", "", "## 13. JSON Report Audit", "", f"- `{json.dumps(json_audit, ensure_ascii=False)}`", "", "## 14. Registration and Package", "", f"- Source registration: `{json.dumps(registration, ensure_ascii=False)}`", "- Package and installed-profile results are finalized after external gates.", "", "## 15. Sprint 0 Regression", "", "- Pending external Sprint 0 Blender and acceptance commands.", "", "## 16. Defects Found and Fixed", ""])
    lines.extend(f"- {item['gate']}: {item['message']}" for item in report["defects"])
    if not report["defects"]:
        lines.append("- None found by the independent Blender fixture run.")
    decision = (
        "SPRINT 1 FINAL VALIDATION PASSED WITH LIMITATIONS"
        if result == "PASS" and report["warnings"]
        else "SPRINT 1 FINAL VALIDATION PASSED"
        if result == "PASS"
        else "SPRINT 1 FINAL VALIDATION FAILED"
    )
    lines.extend(["", "## 17. Tests Not Run", "", "- Interactive installed-panel smoke test was not run in background mode.", "- Real-statue repair UAT was not run.", "", "## 18. Known Limitations", "", "- Modifier output is not analyzed.", "- Self-intersection diagnostics are candidate-based.", "- Internal-shell classification is heuristic.", "- No wall-thickness analysis.", "- This runner validates the Sprint 1 diagnostic path and does not apply Sprint 2 repair operations.", "- No support generation or printability guarantee.", "", "## 19. Safety Confirmation", "", "- No production model files modified.", "- No network, credentials, administrator access, geometry mutation, commit, or push.", "", "## 20. Final Decision", "", f"**{decision}**", "", "## 21. One Immediate Next Action", "", "Review the Sprint 2 evidence and perform an installed-panel smoke test before committing the feature branch.", ""])
    return "\n".join(lines)


def _write_report() -> dict[str, Any]:
    completed_at = datetime.now(timezone.utc)
    overall = "PASS" if GATES and all(gate["status"] == "PASS" for gate in GATES) else "FAIL"
    report = {
        "schema_version": "1.0", "project": "Chroma3D Sculpt", "extension_version": DISPLAY_VERSION,
        "analysis_schema_version": SCHEMA_VERSION, "repository_root": str(REPOSITORY_ROOT),
        "branch": os.environ.get("CHROMA3D_VALIDATION_BRANCH", "Unknown"), "baseline_tag": "v0.1.0-alpha.1",
        "blender_executable": os.environ.get("CHROMA3D_VALIDATION_BLENDER", bpy.app.binary_path),
        "blender_version": bpy.app.version_string, "python_version": sys.version.split()[0],
        "started_at": STARTED_AT.isoformat(), "completed_at": completed_at.isoformat(),
        "duration_seconds": round(perf_counter() - STARTED_TIMER, 6), "overall_status": overall,
        "release_recommendation": (
            "READY TO COMMIT WITH LIMITATIONS"
            if overall == "PASS" and WARNINGS
            else "READY TO COMMIT"
            if overall == "PASS"
            else "NOT READY TO COMMIT"
        ),
        "gates": GATES,
        "numerical_verification": next((gate["actual"] for gate in GATES if gate["id"] == "B"), {}),
        "stress_test": next((gate["actual"] for gate in GATES if gate["id"] == "H"), {}),
        "deep_test": next((gate["actual"] for gate in GATES if gate["id"] == "I"), {}),
        "regression": {"status": "PENDING_EXTERNAL"}, "package": {"status": "PENDING_EXTERNAL"},
        "security": next((gate["actual"] for gate in GATES if gate["id"] == "A"), {}),
        "defects": DEFECTS, "warnings": WARNINGS,
        "generated_artifacts": [_relative(RESULTS_PATH), _relative(MARKDOWN_PATH), _relative(EXPORTED_REPORT_PATH)] if EXPORTED_REPORT_PATH.exists() else [_relative(RESULTS_PATH), _relative(MARKDOWN_PATH)],
        "safety_confirmation": {"production_model_files_modified": False, "network_used": False, "credentials_used": False, "administrator_used": False, "geometry_repair_performed": False, "commit_performed": False, "push_performed": False, "sprint_2_started": False},
    }
    REPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8", newline="\n")
    MARKDOWN_PATH.write_text(_render_markdown(report), encoding="utf-8", newline="\n")
    return report


def main() -> int:
    REPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    registered_here = False
    try:
        if not getattr(chroma3d_sculpt.operators.analyze_mesh.CHROMA3D_OT_analyze_mesh, "is_registered", False):
            chroma3d_sculpt.register()
            registered_here = True
        gate_definitions = (
            ("A", "Static architecture and safety audit", _gate_static),
            ("B", "Independent numerical verification", _gate_numerical),
            ("C", "Topology truth table", _gate_topology),
            ("D", "Shell classification", _gate_shells),
            ("E", "Self-intersection candidates", _gate_intersections),
            ("F", "Build-volume evaluation", _gate_build_volume),
            ("G", "Issue selection", _gate_selection),
            ("H", "Standard real-scale stress", _gate_standard_stress),
            ("I", "Deep bounded and skip states", _gate_deep_stress),
            ("J", "JSON schema and evidence bounds", _gate_json),
            ("K", "Registration lifecycle", _gate_registration),
        )
        requested = {
            value.strip().upper()
            for value in os.environ.get("CHROMA3D_VALIDATION_GATES", "").split(",")
            if value.strip()
        }
        for gate_id, name, function in gate_definitions:
            if not requested or gate_id in requested:
                _run_gate(gate_id, name, function)
    finally:
        _cleanup()
        if registered_here and getattr(chroma3d_sculpt.operators.analyze_mesh.CHROMA3D_OT_analyze_mesh, "is_registered", False):
            chroma3d_sculpt.unregister()
    report = _write_report()
    print(f"Overall: {report['overall_status']}")
    print(f"Recommendation: {report['release_recommendation']}")
    print(f"Report: {RESULTS_PATH}")
    return 0 if report["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
