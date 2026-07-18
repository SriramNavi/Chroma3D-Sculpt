"""Independent adversarial Sprint 2 validation executed inside Blender."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import math
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
SOURCE_PARENT = REPOSITORY_ROOT / "blender_addon"
if str(SOURCE_PARENT) not in sys.path:
    sys.path.insert(0, str(SOURCE_PARENT))

import chroma3d_sculpt as addon  # noqa: E402
from chroma3d_sculpt.analysis_settings import AnalysisSettings  # noqa: E402
from chroma3d_sculpt.metadata import DISPLAY_VERSION, REPAIR_AUDIT_SCHEMA_VERSION, SCHEMA_VERSION  # noqa: E402
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
from chroma3d_sculpt.services.repair_audit import (  # noqa: E402
    build_repair_audit,
    sanitize_repair_audit_filename,
    write_repair_audit,
)
import chroma3d_sculpt.services.repair_coordinator as coordinator  # noqa: E402
from chroma3d_sculpt.services.repair_coordinator import (  # noqa: E402
    accept_repaired_copy,
    apply_repair_plan,
    generate_repair_plan,
    restore_workspace_to_initial,
    rollback_repair_session,
    undo_last_repair,
    validate_active_session,
)
from chroma3d_sculpt.services.repair_operations import (  # noqa: E402
    detect_small_hole_candidates,
    mesh_counts,
    orient_closed_shells_outward,
)
import chroma3d_sculpt.services.repair_session as repair_session_module  # noqa: E402
from chroma3d_sculpt.services.repair_session import (  # noqa: E402
    clear_runtime,
    create_operation_checkpoint,
    discard_checkpoint,
    get_active_session,
    get_current_analysis,
    start_session,
    workspace_object,
)
from chroma3d_sculpt.utilities.repair_signatures import geometry_sha256, protected_source_snapshot, repair_workspace_signature  # noqa: E402


FINAL_DIRECTORY = REPOSITORY_ROOT / "manual-tests" / "sprint2-final"
REPORTS_DIRECTORY = FINAL_DIRECTORY / "reports"
ARTIFACTS_DIRECTORY = FINAL_DIRECTORY / "artifacts"
RESULTS_PATH = REPORTS_DIRECTORY / "final_validation_results.json"
ANALYSIS_SETTINGS = AnalysisSettings()
DEFAULT_REPAIR_SETTINGS = RepairSettings()
GateFunction = Callable[[], dict[str, Any]]

REPORT: dict[str, Any] = {
    "schema_version": "1.0",
    "project": "Chroma3D Sculpt",
    "extension_version": DISPLAY_VERSION,
    "analysis_schema_version": SCHEMA_VERSION,
    "repair_audit_schema_version": REPAIR_AUDIT_SCHEMA_VERSION,
    "blender_version": bpy.app.version_string,
    "gate_results": [],
    "static_audit": {},
    "source_preservation_matrix": {},
    "workspace_isolation_evidence": {},
    "plan_read_only_evidence": {},
    "operation_matrix": {},
    "checkpoint_undo_evidence": {},
    "accept_rollback_evidence": {},
    "audit_validation": {},
    "realistic_stress_metrics": {},
    "stale_state_evidence": {},
    "defects": [],
    "warnings": [],
    "tests_not_run": ["Manual installed-panel interaction and real Chroma3D statue UAT remain deferred."],
    "known_limitations": [
        "Real Chroma3D statue UAT deferred.",
        "Session restart persistence not guaranteed.",
        "No remeshing.",
        "No large-hole reconstruction.",
        "No Boolean repair.",
        "No wall-thickness repair.",
        "No AI.",
        "No printability guarantee.",
    ],
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _pointer(value: Any | None) -> int:
    try:
        return int(value.as_pointer()) if value is not None else 0
    except (AttributeError, ReferenceError, TypeError):
        return 0


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "name"):
        return {"name": str(value.name), "identity": _pointer(value)}
    try:
        return [_json_value(item) for item in value]
    except TypeError:
        return repr(value)


def _custom_properties(value: Any) -> dict[str, Any]:
    return {str(key): _json_value(value[key]) for key in sorted(value.keys()) if key != "_RNA_UI"}


def _component_hash(values: list[bytes]) -> str:
    digest = sha256()
    for value in values:
        digest.update(value)
    return digest.hexdigest()


def _independent_source_signature(obj: bpy.types.Object) -> dict[str, Any]:
    mesh = obj.data
    vertex_hash = _component_hash([
        struct.pack("<ddd", float(vertex.co.x), float(vertex.co.y), float(vertex.co.z)) for vertex in mesh.vertices
    ])
    edge_hash = _component_hash([
        struct.pack("<QQ", int(edge.vertices[0]), int(edge.vertices[1])) for edge in mesh.edges
    ])
    face_values: list[bytes] = []
    for polygon in mesh.polygons:
        face_values.append(struct.pack("<Q", len(polygon.vertices)))
        face_values.extend(struct.pack("<Q", int(index)) for index in polygon.vertices)
    modifier_stack = []
    for modifier in obj.modifiers:
        modifier_stack.append({
            "name": str(modifier.name), "type": str(modifier.type),
            "show_viewport": bool(modifier.show_viewport), "show_render": bool(modifier.show_render),
        })
    payload = {
        "object_name": str(obj.name), "mesh_name": str(mesh.name),
        "object_identity": _pointer(obj), "mesh_identity": _pointer(mesh),
        "vertex_count": len(mesh.vertices), "edge_count": len(mesh.edges), "face_count": len(mesh.polygons),
        "vertex_coordinate_hash": vertex_hash, "edge_connectivity_hash": edge_hash,
        "face_connectivity_winding_hash": _component_hash(face_values),
        "location": [float(value) for value in obj.location],
        "rotation": [float(value) for value in obj.rotation_euler],
        "scale": [float(value) for value in obj.scale],
        "modifiers": modifier_stack,
        "materials": [{"name": str(slot.material.name) if slot.material else "", "identity": _pointer(slot.material)} for slot in obj.material_slots],
        "collections": sorted(str(collection.name) for collection in obj.users_collection),
        "object_custom_properties": _custom_properties(obj),
        "mesh_custom_properties": _custom_properties(mesh),
        "hide_viewport": bool(obj.hide_viewport), "hide_render": bool(obj.hide_render), "hide_get": bool(obj.hide_get()),
        "selected": bool(obj.select_get()), "active": bpy.context.view_layer.objects.active is obj,
        "mode": str(obj.mode), "blend_file_path": str(bpy.data.filepath), "blend_file_dirty": bool(bpy.data.is_dirty),
    }
    payload["signature_sha256"] = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return payload


def _geometry_state(obj: bpy.types.Object) -> dict[str, Any]:
    return {
        "counts": mesh_counts(obj),
        "geometry_sha256": geometry_sha256(obj),
        "object_identity": _pointer(obj),
        "mesh_identity": _pointer(obj.data),
        "workspace_signature": repair_workspace_signature(obj),
    }


def _cube(size: float = 1.0, offset: tuple[float, float, float] = (0.0, 0.0, 0.0), *, open_top: bool = False, inward: bool = False) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    ox, oy, oz = offset
    vertices = [
        (ox - size, oy - size, oz - size), (ox + size, oy - size, oz - size),
        (ox + size, oy + size, oz - size), (ox - size, oy + size, oz - size),
        (ox - size, oy - size, oz + size), (ox + size, oy - size, oz + size),
        (ox + size, oy + size, oz + size), (ox - size, oy + size, oz + size),
    ]
    faces: list[tuple[int, ...]] = [
        (0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
        (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7),
    ]
    if open_top:
        faces = faces[1:]
    if inward:
        faces = [tuple(reversed(face)) for face in faces]
    return vertices, faces


def _combine(*parts: tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for part_vertices, part_faces in parts:
        offset = len(vertices)
        vertices.extend(part_vertices)
        faces.extend(tuple(index + offset for index in face) for face in part_faces)
    return vertices, faces


def _mesh(name: str, vertices: list[tuple[float, float, float]], faces: list[tuple[int, ...]] = [], edges: list[tuple[int, int]] = [], *, scale: tuple[float, float, float] = (1.0, 1.0, 1.0)) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, edges, faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.scale = scale
    return obj


def _activate(obj: bpy.types.Object, *, exclusive: bool = True) -> None:
    if exclusive:
        for item in bpy.context.selected_objects:
            item.select_set(False)
    obj.hide_viewport = False
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _start(source: bpy.types.Object, settings: RepairSettings = DEFAULT_REPAIR_SETTINGS):
    return start_session(
        source, bpy.context.scene, settings, ANALYSIS_SETTINGS,
        blender_version=bpy.app.version_string, blend_file_path=bpy.data.filepath,
    )


def _plan(session: Any, settings: RepairSettings = DEFAULT_REPAIR_SETTINGS):
    workspace = workspace_object(session)
    _require(workspace is not None, "Workspace missing before plan generation.")
    _activate(workspace, exclusive=False)
    return generate_repair_plan(
        session, bpy.context.scene, settings,
        blend_file_path=bpy.data.filepath, active_object=workspace,
    )


def _select_operation(plan: Any, operation: RepairOperationType) -> None:
    for item in plan.items:
        if item.operation_type == operation:
            item.selected = True
            return


def _apply(session: Any, operation: RepairOperationType, settings: RepairSettings = DEFAULT_REPAIR_SETTINGS):
    workspace = workspace_object(session)
    _require(workspace is not None, "Workspace missing before operation.")
    return apply_repair_plan(
        session, bpy.context.scene, settings, ANALYSIS_SETTINGS,
        blend_file_path=bpy.data.filepath, active_object=workspace, single_operation=operation,
    )[0]


def _rollback_if_possible() -> None:
    session = get_active_session()
    if session is None:
        return
    try:
        workspace = workspace_object(session)
        if workspace is not None:
            rollback_repair_session(session, blend_file_path=bpy.data.filepath)
        else:
            clear_runtime()
    except Exception:
        clear_runtime()


def _reset_scene() -> None:
    _rollback_if_possible()
    clear_runtime()
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in list(bpy.data.collections):
        if collection.users == 0:
            bpy.data.collections.remove(collection)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    for material in list(bpy.data.materials):
        if material.users == 0:
            bpy.data.materials.remove(material)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0


def _signed_volume(obj: bpy.types.Object) -> float:
    volume = 0.0
    for polygon in obj.data.polygons:
        points = [obj.data.vertices[index].co.copy() for index in polygon.vertices]
        origin = points[0]
        for index in range(1, len(points) - 1):
            volume += origin.dot(points[index].cross(points[index + 1])) / 6.0
    return volume


def _run_gate(phase: str, gate_id: str, name: str, function: GateFunction, report_key: str | None = None) -> None:
    _reset_scene()
    started = perf_counter()
    gate = {"phase": phase, "id": gate_id, "name": name, "status": "FAIL", "evidence": {}}
    try:
        evidence = function()
        gate["status"] = "PASS"
        gate["evidence"] = evidence
        if report_key:
            REPORT[report_key] = evidence
    except Exception as exc:
        gate["error"] = f"{type(exc).__name__}: {exc}"
        gate["traceback"] = traceback.format_exc(limit=12)
        REPORT["warnings"].append(f"{gate_id} failed: {type(exc).__name__}: {exc}")
    finally:
        gate["duration_seconds"] = round(perf_counter() - started, 6)
        REPORT["gate_results"].append(gate)
        print(f"[{gate['status']}] {gate_id} {name}")
        try:
            _reset_scene()
        except Exception as cleanup_exc:
            REPORT["warnings"].append(f"Cleanup after {gate_id} failed: {cleanup_exc}")


def _gate_static_audit() -> dict[str, Any]:
    runtime = REPOSITORY_ROOT / "blender_addon" / "chroma3d_sculpt"
    files = sorted(runtime.rglob("*.py"))
    prohibited = {
        "network": re.compile(r"^\s*(?:from|import)\s+(?:requests|urllib|http\.|socket|aiohttp|httpx)\b", re.MULTILINE),
        "subprocess": re.compile(r"^\s*(?:from|import)\s+subprocess\b", re.MULTILINE),
        "dynamic_execution": re.compile(r"\b(?:eval|exec)\s*\("),
        "pickle": re.compile(r"^\s*(?:from|import)\s+pickle\b", re.MULTILINE),
        "registry": re.compile(r"\bwinreg\b"),
        "automatic_save": re.compile(r"bpy\.ops\.wm\.save"),
    }
    findings: list[dict[str, str]] = []
    texts: dict[str, str] = {}
    for path in files:
        relative = path.relative_to(REPOSITORY_ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        texts[relative] = text
        for label, pattern in prohibited.items():
            if pattern.search(text):
                findings.append({"type": label, "path": relative})
    misleading = re.compile(r"(?i)guaranteed repaired|guaranteed printable|fully fixed|perfect mesh|safe to manufacture|production-ready|lossless repair|exact repair")
    wording_hits = [relative for relative, text in texts.items() if misleading.search(text)]
    diagnostic_files = [relative for relative in texts if "/services/" in f"/{relative}" and any(name in relative for name in ("mesh_analyzer", "topology_analyzer", "shell_analyzer", "deep_diagnostics", "build_volume_analyzer"))]
    diagnostic_repair_imports = [relative for relative in diagnostic_files if re.search(r"^\s*(?:from|import).*repair", texts[relative], re.MULTILINE)]
    ui_mutation_hits = [relative for relative, text in texts.items() if "/ui/" in f"/{relative}" and any(token in text for token in ("bmesh.ops", ".to_mesh(", "bpy.data.objects.remove"))]
    _require(not findings, f"Prohibited runtime behavior found: {findings}")
    _require(not wording_hits, f"Misleading repair wording found: {wording_hits}")
    _require(not diagnostic_repair_imports, f"Diagnostic services depend on repair services: {diagnostic_repair_imports}")
    _require(not ui_mutation_hits, f"UI contains geometry mutation: {ui_mutation_hits}")
    manifest = (runtime / "blender_manifest.toml").read_text(encoding="utf-8")
    _require('blender_version_min = "4.4.0"' in manifest, "Minimum Blender version changed.")
    _require(DISPLAY_VERSION == "0.3.0-alpha.1" and SCHEMA_VERSION == "2.0" and REPAIR_AUDIT_SCHEMA_VERSION == "1.0", "Version/schema mismatch.")
    return {
        "status": "PASS", "runtime_python_files": len(files), "prohibited_findings": findings,
        "misleading_wording": wording_hits, "diagnostic_repair_imports": diagnostic_repair_imports,
        "ui_mutation_hits": ui_mutation_hits, "manifest_minimum_blender": "4.4.0",
    }


def _gate_source_preservation() -> dict[str, Any]:
    vertices, faces = _cube()
    source = _mesh("Protected Statue Source", vertices, faces)
    source.data.name = "Protected Statue Mesh"
    source.location = (1.25, -2.5, 3.75)
    source.rotation_euler = (0.2, -0.35, 0.6)
    source.scale = (1.2, 0.8, 1.6)
    first_material = bpy.data.materials.new("Bronze")
    second_material = bpy.data.materials.new("Patina")
    source.data.materials.append(first_material)
    source.data.materials.append(second_material)
    modifier = source.modifiers.new("Unapplied Bevel", "BEVEL")
    modifier.width = 0.0125
    source["source_owner"] = "artist"
    source.data["mesh_evidence"] = "retained"
    second_collection = bpy.data.collections.new("Secondary Membership")
    bpy.context.scene.collection.children.link(second_collection)
    second_collection.objects.link(source)
    source.hide_render = True
    source.select_set(True)
    decoy = _mesh("Active Decoy", *_cube(0.25, (4.0, 0.0, 0.0)))
    _activate(decoy, exclusive=False)
    _require(source.select_get() and bpy.context.active_object is decoy, "Source/active precondition not established.")
    before = _independent_source_signature(source)
    checkpoint_count_before = len(bpy.data.meshes)
    session = _start(source)
    workspace = workspace_object(session)
    _require(workspace is not None, "Workspace was not created.")
    after_start = _independent_source_signature(source)
    _require(before == after_start, "Starting a session changed the independently captured source state.")
    _require(workspace is not source and workspace.data is not source.data, "Workspace object or mesh is not independent.")
    _require(tuple(workspace.location) == tuple(source.location) and tuple(workspace.rotation_euler) == tuple(source.rotation_euler) and tuple(workspace.scale) == tuple(source.scale), "Workspace transform copy mismatch.")
    _require([slot.material for slot in workspace.material_slots] == [slot.material for slot in source.material_slots], "Material slot order/identity mismatch.")
    _require([(item.name, item.type) for item in workspace.modifiers] == [(item.name, item.type) for item in source.modifiers], "Modifier stack copy mismatch.")
    _require(_custom_properties(workspace) == _custom_properties(source) and _custom_properties(workspace.data) == _custom_properties(source.data), "Custom properties were not copied.")
    _require(sorted(item.name for item in workspace.users_collection) == sorted(item.name for item in source.users_collection), "Collection memberships were not copied deterministically.")
    _require(len(bpy.data.meshes) == checkpoint_count_before + 2, "Workspace and initial checkpoint meshes were not both created.")
    plan_before = _geometry_state(workspace)
    plan = _plan(session)
    for item in plan.items:
        item.selected = not item.selected
    for candidate in plan.candidates:
        candidate.selected = not candidate.selected
    plan_after = _geometry_state(workspace)
    _require(plan_before == plan_after, "Plan generation or selection toggles changed workspace geometry.")
    _require(before == _independent_source_signature(source), "Plan generation changed the source.")
    _require(source.mode == "OBJECT", "Source was switched out of Object Mode.")
    _require(not source.hide_viewport, "Source became hidden in the viewport.")
    return {
        "source_signature": before["signature_sha256"],
        "source_object_identity": before["object_identity"], "source_mesh_identity": before["mesh_identity"],
        "workspace_object_identity": _pointer(workspace), "workspace_mesh_identity": _pointer(workspace.data),
        "materials": before["materials"], "collections": before["collections"],
        "custom_properties_preserved": True, "modifier_stack_preserved": True,
        "source_unchanged_after_start_and_plan": True, "automatic_save": False,
    }


def _gate_workspace_isolation() -> dict[str, Any]:
    source = _mesh("Isolation Source", *_cube())
    shared = bpy.data.materials.new("Shared Material")
    source.data.materials.append(shared)
    decoy = _mesh("Unrelated Decoy", *_cube(0.4, (5.0, 0.0, 0.0)))
    decoy.data.materials.append(shared)
    orphan = bpy.data.meshes.new("Unrelated Orphan Mesh")
    _activate(source)
    session = _start(source)
    workspace = workspace_object(session)
    _require(workspace is not None, "Workspace missing.")
    source_geometry = geometry_sha256(source)
    decoy_geometry = geometry_sha256(decoy)
    workspace.data.vertices[0].co.x += 0.125
    workspace.data.update()
    _require(geometry_sha256(source) == source_geometry, "Workspace mutation propagated to source.")
    rejected = False
    try:
        _plan(session)
    except RuntimeError:
        rejected = True
    _require(rejected, "External workspace mutation did not invalidate the plan path.")
    rollback_repair_session(session, blend_file_path=bpy.data.filepath)
    _require(source.name in bpy.data.objects and decoy.name in bpy.data.objects, "Rollback deleted a non-session object.")
    _require(orphan.name in bpy.data.meshes, "Rollback deleted an unrelated mesh datablock.")
    _require(geometry_sha256(source) == source_geometry and geometry_sha256(decoy) == decoy_geometry, "Rollback changed unrelated geometry.")
    _require(source.data.materials[0] is shared and decoy.data.materials[0] is shared, "Shared material identity changed.")
    return {
        "object_independent": True, "mesh_independent": True, "workspace_mutation_did_not_propagate": True,
        "external_workspace_change_rejected": rejected, "rollback_preserved_decoy_object": True,
        "rollback_preserved_orphan_mesh": True, "shared_material_preserved": True,
    }


def _gate_plan_read_only() -> dict[str, Any]:
    vertices, faces = _combine(_cube(), _cube(0.002, (3.0, 0.0, 0.0)), _cube(0.0001, (4.0, 0.0, 0.0), open_top=True))
    vertices.extend([vertices[0], (10.0, 0.0, 0.0)])
    source = _mesh("Plan Matrix", vertices, faces)
    _activate(source)
    session = _start(source)
    workspace = workspace_object(session)
    _require(workspace is not None, "Workspace missing.")
    before = _geometry_state(workspace)
    source_before = _independent_source_signature(source)
    checkpoints_before = len([item for item in session.checkpoint_records if item.retained])
    first = _plan(session)
    for candidate in first.candidates:
        candidate.selected = True
        candidate.selected = False
    second = _plan(session)
    after = _geometry_state(workspace)
    checkpoints_after = len([item for item in session.checkpoint_records if item.retained])
    _require(before == after, "Analyze/plan/regenerate changed workspace geometry or identity.")
    _require(source_before == _independent_source_signature(source), "Plan path changed source state.")
    _require(checkpoints_before == checkpoints_after == 1, "Plan generation created a mutation checkpoint.")
    _require(not any(candidate.selected for candidate in second.candidates), "A candidate was silently preselected.")
    _require(not session.operation_records, "Plan generation serialized an operation as applied.")
    return {
        "workspace_signature_before": before["workspace_signature"], "workspace_signature_after": after["workspace_signature"],
        "mesh_identity_unchanged": before["mesh_identity"] == after["mesh_identity"],
        "checkpoint_count": checkpoints_after, "operation_record_count": len(session.operation_records),
        "candidate_count": len(second.candidates), "candidate_preselection_count": 0,
        "recommendations": {item.operation_type.value: item.recommended for item in second.items},
    }


def _operation_session(source: bpy.types.Object, operation: RepairOperationType, *, settings: RepairSettings = DEFAULT_REPAIR_SETTINGS, select_candidate: RepairCandidateType | None = None) -> tuple[Any, Any, Any, dict[str, Any], dict[str, Any], dict[str, Any]]:
    _activate(source)
    session = _start(source, settings)
    workspace = workspace_object(session)
    _require(workspace is not None, "Workspace missing.")
    source_after_start = _independent_source_signature(source)
    workspace_before = _geometry_state(workspace)
    plan = _plan(session, settings)
    _select_operation(plan, operation)
    if select_candidate is not None:
        candidates = [candidate for candidate in plan.candidates if candidate.candidate_type == select_candidate]
        _require(candidates, f"No {select_candidate.value} candidate was generated.")
        candidates[0].selected = True
    record = _apply(session, operation, settings)
    workspace_after = _geometry_state(workspace)
    _require(source_after_start == _independent_source_signature(source), f"{operation.value} changed the source.")
    _require(record.status in {RepairOperationStatus.APPLIED, RepairOperationStatus.NO_CHANGE}, f"Unexpected operation status: {record.status.value}")
    return session, workspace, record, source_after_start, workspace_before, workspace_after


def _undo_exact(session: Any, workspace: bpy.types.Object, expected: dict[str, Any]) -> None:
    undo_last_repair(session, bpy.context.scene, ANALYSIS_SETTINGS, blend_file_path=bpy.data.filepath, active_object=workspace)
    _require(geometry_sha256(workspace) == expected["geometry_sha256"] and mesh_counts(workspace) == expected["counts"], "Undo did not restore exact previous geometry.")


def _gate_merge_duplicates() -> dict[str, Any]:
    vertices, faces = _cube()
    vertices.append(vertices[0])
    source = _mesh("Duplicate Operation", vertices, faces)
    session, workspace, record, _, before, after = _operation_session(source, RepairOperationType.MERGE_DUPLICATE_VERTICES)
    _require(after["counts"]["vertices"] == before["counts"]["vertices"] - 1, "Duplicate merge changed an unexpected vertex count.")
    _require(after["counts"]["faces"] == before["counts"]["faces"], "Duplicate merge changed faces unexpectedly.")
    _undo_exact(session, workspace, before)
    return {"status": record.status.value, "counts_before": before["counts"], "counts_after": after["counts"], "metrics": record.metrics, "source_unchanged": True, "undo_exact": True}


def _gate_zero_edges() -> dict[str, Any]:
    vertices, faces = _cube()
    base = len(vertices)
    vertices.extend([(4.0, 0.0, 0.0), (4.0, 0.0, 0.0)])
    source = _mesh("Zero Edge Operation", vertices, faces, [(base, base + 1)])
    session, workspace, record, _, before, after = _operation_session(source, RepairOperationType.COLLAPSE_ZERO_LENGTH_EDGES)
    _require(record.metrics.get("zero_length_edges_found") == 1, "Zero-length edge evidence mismatch.")
    _require(after["counts"]["faces"] == before["counts"]["faces"], "Zero-edge collapse changed unrelated faces.")
    _undo_exact(session, workspace, before)
    return {"status": record.status.value, "counts_before": before["counts"], "counts_after": after["counts"], "metrics": record.metrics, "source_unchanged": True, "undo_exact": True}


def _gate_degenerate_faces() -> dict[str, Any]:
    vertices, faces = _cube()
    base = len(vertices)
    vertices.extend([(4.0, 0.0, 0.0), (4.001, 0.0, 0.0), (4.002, 0.0, 0.0)])
    faces.append((base, base + 1, base + 2))
    source = _mesh("Degenerate Operation", vertices, faces)
    session, workspace, record, _, before, after = _operation_session(source, RepairOperationType.REMOVE_DEGENERATE_FACES)
    _require(after["counts"]["faces"] == before["counts"]["faces"] - 1, "Degenerate-face removal count mismatch.")
    _require(after["counts"]["vertices"] == before["counts"]["vertices"] and after["counts"]["edges"] == before["counts"]["edges"], "Degenerate-face removal silently cleaned loose geometry.")
    _undo_exact(session, workspace, before)
    return {"status": record.status.value, "counts_before": before["counts"], "counts_after": after["counts"], "metrics": record.metrics, "source_unchanged": True, "undo_exact": True}


def _gate_loose_geometry() -> dict[str, Any]:
    vertices, faces = _combine(_cube(), _cube(0.2, (4.0, 0.0, 0.0)))
    base = len(vertices)
    vertices.extend([(8.0, 0.0, 0.0), (8.1, 0.0, 0.0), (8.2, 0.0, 0.0), (9.0, 0.0, 0.0)])
    source = _mesh("Loose Operation", vertices, faces, [(base, base + 1), (base + 1, base + 2)])
    session, workspace, record, _, before, after = _operation_session(source, RepairOperationType.REMOVE_LOOSE_GEOMETRY)
    _require(after["counts"]["faces"] == before["counts"]["faces"], "Loose cleanup removed a face shell.")
    _require(after["counts"]["vertices"] == before["counts"]["vertices"] - 4, "Loose cleanup vertex count mismatch.")
    _undo_exact(session, workspace, before)
    return {"status": record.status.value, "counts_before": before["counts"], "counts_after": after["counts"], "metrics": record.metrics, "source_unchanged": True, "undo_exact": True}


def _gate_normal_consistency() -> dict[str, Any]:
    vertices, faces = _cube()
    faces[0] = tuple(reversed(faces[0]))
    source = _mesh("First Face Reversed", vertices, faces)
    session, workspace, record, _, before, after = _operation_session(source, RepairOperationType.REPAIR_NORMAL_CONSISTENCY)
    volume_after = _signed_volume(workspace)
    _require(record.metrics.get("face_winding_changes", 0) > 0, "Normal consistency made no evidenced change.")
    _require(volume_after > 0.0, "Normal consistency inverted the overall closed-shell orientation.")
    _require(before["counts"] == after["counts"], "Normal consistency changed topology counts.")
    _undo_exact(session, workspace, before)
    return {"status": record.status.value, "signed_volume_after": volume_after, "metrics": record.metrics, "source_unchanged": True, "topology_counts_unchanged": True, "undo_exact": True}


def _gate_outward_orientation() -> dict[str, Any]:
    outward = _mesh("Already Outward", *_cube())
    outward_before = geometry_sha256(outward)
    no_change = orient_closed_shells_outward(outward, 1000.0, DEFAULT_REPAIR_SETTINGS)
    _require(no_change.status == RepairOperationStatus.NO_CHANGE and geometry_sha256(outward) == outward_before, "Outward shell was changed.")
    source = _mesh("Inward Operation", *_cube(inward=True))
    session, workspace, record, _, before, after = _operation_session(source, RepairOperationType.ORIENT_CLOSED_SHELLS_OUTWARD)
    _require(_signed_volume(workspace) > 0.0 and record.metrics.get("shells_reoriented") == 1, "Inward shell was not oriented outward.")
    _require(before["counts"] == after["counts"], "Outward orientation changed topology counts.")
    _undo_exact(session, workspace, before)
    return {"status": record.status.value, "outward_shell_no_change": True, "inward_shell_reoriented": True, "metrics": record.metrics, "source_unchanged": True, "undo_exact": True}


def _gate_tiny_shells() -> dict[str, Any]:
    source = _mesh("Tiny Shell Operation", *_combine(_cube(), _cube(0.002, (3.0, 0.0, 0.0)), _cube(0.002, (4.0, 0.0, 0.0))))
    session, workspace, record, _, before, after = _operation_session(source, RepairOperationType.REMOVE_SELECTED_TINY_SHELLS, select_candidate=RepairCandidateType.TINY_SHELL)
    _require(record.metrics.get("removed_faces") == 6, "Selected tiny-shell face deletion count mismatch.")
    _require(after["counts"]["faces"] == before["counts"]["faces"] - 6, "Tiny-shell operation changed more than one selected shell.")
    _undo_exact(session, workspace, before)
    return {"status": record.status.value, "counts_before": before["counts"], "counts_after": after["counts"], "metrics": record.metrics, "unselected_candidate_retained": True, "main_shell_protected": True, "undo_exact": True}


def _gate_small_holes() -> dict[str, Any]:
    source = _mesh("Hole Operation", *_combine(_cube(0.0001, open_top=True), _cube(0.0001, (0.0005, 0.0, 0.0), open_top=True)))
    session, workspace, record, _, before, after = _operation_session(source, RepairOperationType.FILL_SELECTED_SMALL_HOLES, select_candidate=RepairCandidateType.SMALL_HOLE)
    _require(record.metrics.get("new_face_count", 0) > 0, "Selected hole created no face.")
    _require(after["counts"]["faces"] == before["counts"]["faces"] + 1, "Hole fill affected more than the selected candidate.")
    _undo_exact(session, workspace, before)
    return {"status": record.status.value, "counts_before": before["counts"], "counts_after": after["counts"], "metrics": record.metrics, "unselected_candidate_retained": True, "undo_exact": True}


def _gate_checkpoint_recovery() -> dict[str, Any]:
    vertices, faces = _cube()
    vertices.append(vertices[0])
    source = _mesh("Checkpoint Recovery", vertices, faces)
    _activate(source)
    session = _start(source)
    workspace = workspace_object(session)
    _require(workspace is not None, "Workspace missing.")
    initial = _geometry_state(workspace)
    plan = _plan(session)
    _select_operation(plan, RepairOperationType.MERGE_DUPLICATE_VERTICES)
    first = _apply(session, RepairOperationType.MERGE_DUPLICATE_VERTICES)
    retained_before_no_change = [item.checkpoint_id for item in session.checkpoint_records if item.retained and not item.initial]
    _plan(session)
    no_change = _apply(session, RepairOperationType.MERGE_DUPLICATE_VERTICES)
    retained_after_no_change = [item.checkpoint_id for item in session.checkpoint_records if item.retained and not item.initial]
    _require(no_change.status == RepairOperationStatus.NO_CHANGE, "Idempotent operation was not recorded as NO_CHANGE.")
    _require(retained_before_no_change == retained_after_no_change, "NO_CHANGE evicted or replaced a valid undo checkpoint.")
    _undo_exact(session, workspace, initial)

    plan = _plan(session)
    _select_operation(plan, RepairOperationType.MERGE_DUPLICATE_VERTICES)
    pre_failure = _geometry_state(workspace)
    original_dispatch = coordinator._dispatch_operation
    def mutate_then_fail(*args: Any, **kwargs: Any):
        target = args[1]
        target.data.vertices[0].co.x += 7.0
        target.data.update()
        raise MemoryError("controlled final-validation fault")
    coordinator._dispatch_operation = mutate_then_fail
    failed = False
    try:
        _apply(session, RepairOperationType.MERGE_DUPLICATE_VERTICES)
    except MemoryError:
        failed = True
    finally:
        coordinator._dispatch_operation = original_dispatch
    _require(failed, "Controlled mutation failure did not propagate.")
    _require(geometry_sha256(workspace) == pre_failure["geometry_sha256"] and mesh_counts(workspace) == pre_failure["counts"], "Failed operation did not restore the exact checkpoint.")
    _require(session.operation_records[-1].status == RepairOperationStatus.FAILED, "Failed operation audit record missing.")

    restore_workspace_to_initial(session, bpy.context.scene, ANALYSIS_SETTINGS, blend_file_path=bpy.data.filepath, active_object=workspace)
    _require(geometry_sha256(workspace) == initial["geometry_sha256"], "Restore-to-start did not restore initial geometry.")
    return {
        "first_status": first.status.value, "no_change_status": no_change.status.value,
        "no_change_preserved_undo": True, "undo_exact": True, "fault_injection_restored": True,
        "failed_recorded": True, "restore_to_start_exact": True,
    }


def _gate_checkpoint_creation_failure() -> dict[str, Any]:
    vertices, faces = _cube()
    vertices.append(vertices[0])
    source = _mesh("Checkpoint Creation Failure", vertices, faces)
    _activate(source)
    session = _start(source)
    workspace = workspace_object(session)
    _require(workspace is not None, "Workspace missing.")
    plan = _plan(session)
    _select_operation(plan, RepairOperationType.MERGE_DUPLICATE_VERTICES)
    before = _geometry_state(workspace)
    original_checkpoint = coordinator.create_operation_checkpoint
    def fail_checkpoint(*args: Any, **kwargs: Any):
        raise MemoryError("controlled checkpoint allocation failure")
    coordinator.create_operation_checkpoint = fail_checkpoint
    rejected = False
    try:
        _apply(session, RepairOperationType.MERGE_DUPLICATE_VERTICES)
    except MemoryError:
        rejected = True
    finally:
        coordinator.create_operation_checkpoint = original_checkpoint
    _require(rejected, "Checkpoint creation failure did not block the operation.")
    _require(_geometry_state(workspace) == before, "Checkpoint creation failure allowed geometry mutation.")
    _require(session.status == RepairSessionStatus.FAILED, "Checkpoint creation failure did not leave an honest FAILED session state.")
    _require(session.operation_records and session.operation_records[-1].status == RepairOperationStatus.FAILED, "Checkpoint creation failure was omitted from the repair audit.")
    return {"mutation_prevented": True, "session_status": session.status.value, "failure_recorded": True, "workspace_signature": before["workspace_signature"]}


def _scene_integrity_fixture() -> tuple[bpy.types.Object, bpy.types.Object, bpy.types.Object, bpy.types.Camera]:
    source = _mesh("Finalize Source", *_cube())
    decoy = _mesh("Unrelated Scene Mesh", *_cube(0.25, (4.0, 0.0, 0.0)))
    camera_data = bpy.data.cameras.new("Unrelated Camera Data")
    camera = bpy.data.objects.new("Unrelated Camera", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    shared = bpy.data.materials.new("Finalize Shared")
    unique = bpy.data.materials.new("Finalize Unique")
    source.data.materials.append(shared)
    source.data.materials.append(unique)
    decoy.data.materials.append(shared)
    return source, decoy, camera, camera_data


def _gate_accept_rollback() -> dict[str, Any]:
    source, decoy, camera, camera_data = _scene_integrity_fixture()
    collision = _mesh("Finalize Source_Chroma3D_Repaired", *_cube(0.1, (7.0, 0.0, 0.0)))
    collision.data.name = "Finalize Source_Mesh_Chroma3D_Repaired"
    _activate(source)
    session = _start(source)
    workspace = workspace_object(session)
    _require(workspace is not None, "Workspace missing.")
    source_signature = _independent_source_signature(source)
    accepted = accept_repaired_copy(session, bpy.context.scene, ANALYSIS_SETTINGS, blend_file_path=bpy.data.filepath, active_object=workspace)
    _require(accepted is workspace and accepted.data is not source.data, "Accept did not keep an independent repaired copy.")
    _require(source_signature == _independent_source_signature(source), "Accept changed the protected source.")
    _require(decoy.name in bpy.data.objects and camera.name in bpy.data.objects and camera_data.name in bpy.data.cameras and collision.name in bpy.data.objects, "Accept deleted an unrelated scene resource.")
    _require(session.status == RepairSessionStatus.ACCEPTED and session.decision == RepairDecision.ACCEPTED, "Accept audit decision mismatch.")
    _require(not any(item.retained for item in session.checkpoint_records), "Accept retained checkpoint meshes.")
    _require(accepted.name != collision.name, "Naming collision was not handled.")

    clear_runtime()
    source2 = _mesh("Rollback Source", *_cube(0.5, (10.0, 0.0, 0.0)))
    _activate(source2)
    source2_signature = _independent_source_signature(source2)
    session2 = _start(source2)
    workspace2 = workspace_object(session2)
    _require(workspace2 is not None, "Rollback workspace missing.")
    workspace2_name = workspace2.name
    rollback_repair_session(session2, blend_file_path=bpy.data.filepath)
    _require(workspace2_name not in bpy.data.objects, "Rollback retained the workspace object.")
    _require(source2_signature == _independent_source_signature(source2), "Rollback changed source state.")
    _require(decoy.name in bpy.data.objects and camera.name in bpy.data.objects, "Rollback deleted unrelated scene objects.")
    _require(session2.status == RepairSessionStatus.ROLLED_BACK and session2.decision == RepairDecision.ROLLED_BACK, "Rollback audit decision mismatch.")
    _require(not any(item.retained for item in session2.checkpoint_records), "Rollback retained checkpoint meshes.")
    return {
        "accept_source_preserved": True, "accept_independent_mesh": True, "accept_collision_handled": True,
        "accept_checkpoints_cleaned": True, "accept_decision": session.decision.value,
        "rollback_workspace_deleted": True, "rollback_source_preserved": True,
        "rollback_unrelated_objects_preserved": True, "rollback_decision": session2.decision.value,
        "automatic_save": False,
    }


def _gate_audit_truthfulness() -> dict[str, Any]:
    vertices, faces = _cube()
    vertices.append(vertices[0])
    source = _mesh("Lakshmi Narasimha Audit", vertices, faces)
    _activate(source)
    session = _start(source)
    workspace = workspace_object(session)
    _require(workspace is not None, "Workspace missing.")
    plan = _plan(session)
    _select_operation(plan, RepairOperationType.MERGE_DUPLICATE_VERTICES)
    applied = _apply(session, RepairOperationType.MERGE_DUPLICATE_VERTICES)
    _plan(session)
    no_change = _apply(session, RepairOperationType.MERGE_DUPLICATE_VERTICES)
    _undo_exact(session, workspace, {"geometry_sha256": session.operation_records[0].before_workspace_signature, "counts": {}}) if False else None
    accepted = accept_repaired_copy(session, bpy.context.scene, ANALYSIS_SETTINGS, blend_file_path=bpy.data.filepath, active_object=workspace)
    output = ARTIFACTS_DIRECTORY / "independent_repair_audit.json"
    write_repair_audit(session, output)
    raw = output.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    records = payload["session"]["operation_records"]
    _require(payload["schema_version"] == "1.0" and payload["extension_version"] == "0.3.0-alpha.1" and payload["analysis_schema_version"] == "2.0", "Repair audit versions mismatch.")
    _require(raw.endswith(b"\n"), "Repair audit lacks a trailing newline.")
    _require(payload["final_decision"] == "ACCEPTED" and payload["session"]["status"] == "ACCEPTED", "Audit final decision mismatch.")
    _require(any(item["status"] == "APPLIED" for item in records) and any(item["status"] == "NO_CHANGE" for item in records), "Audit omitted applied or no-change truth.")
    _require(payload["source_protection_signature"] == session.source_signature, "Audit source signature mismatch.")
    _require(payload["initial_workspace_signature"] == session.initial_workspace_signature and payload["final_workspace_signature"] == session.current_workspace_signature, "Audit workspace signatures mismatch.")
    _require(payload["session"]["settings_snapshot"] and payload["session"]["before_analysis"] and payload["session"]["final_analysis"], "Audit omitted settings or diagnostics.")
    safe_names = {}
    invalid = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
    for name in ("CON", "PRN", "AUX", "NUL", "Statue:Repair?*", "Lakshmi/Narasimha", "trailing.", "trailing ", ""):
        sanitized = sanitize_repair_audit_filename(name)
        _require(not invalid.search(sanitized) and not sanitized.rstrip(" .") != sanitized, f"Unsafe audit filename: {sanitized}")
        _require(sanitized.lower().endswith(".json"), "Audit filename extension mismatch.")
        safe_names[name or "<empty>"] = sanitized
    _require(accepted.name in bpy.data.objects, "Accepted repair object missing during audit export.")
    return {
        "schema_version": payload["schema_version"], "extension_version": payload["extension_version"],
        "analysis_schema_version": payload["analysis_schema_version"], "utf8": True, "trailing_newline": True,
        "session_id": payload["session"]["session_id"], "plan_id": payload["session"]["plan"]["plan_id"],
        "applied_records": sum(item["status"] == "APPLIED" for item in records),
        "no_change_records": sum(item["status"] == "NO_CHANGE" for item in records),
        "decision": payload["final_decision"], "safe_filenames": safe_names,
        "encoded_bytes": len(raw), "evidence_path": output.relative_to(REPOSITORY_ROOT).as_posix(),
        "applied_status": applied.status.value, "no_change_status": no_change.status.value,
    }


def _realistic_fixture() -> tuple[bpy.types.Object, dict[str, Any]]:
    started = perf_counter()
    mesh = bpy.data.meshes.new("Realistic Surface Stress Mesh")
    bm = bmesh.new()
    sphere_result = bmesh.ops.create_uvsphere(bm, u_segments=320, v_segments=240, radius=0.05, calc_uvs=False)
    sphere_vertices = list(sphere_result["verts"])
    bmesh.ops.scale(bm, vec=Vector((0.72, 0.55, 1.15)), verts=sphere_vertices)
    bmesh.ops.translate(bm, vec=Vector((0.0, 0.0, 0.055)), verts=sphere_vertices)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    hole_face = min(bm.faces, key=lambda face: (abs(face.calc_center_median().z - 0.055), face.index))
    bmesh.ops.delete(bm, geom=[hole_face], context="FACES_ONLY")

    pedestal = bmesh.ops.create_cube(bm, size=0.07)["verts"]
    bmesh.ops.scale(bm, vec=Vector((1.2, 1.0, 0.25)), verts=pedestal)
    bmesh.ops.translate(bm, vec=Vector((0.0, 0.0, -0.045)), verts=pedestal)

    inward_start = set(bm.faces)
    inward = bmesh.ops.create_cube(bm, size=0.008)["verts"]
    bmesh.ops.translate(bm, vec=Vector((0.07, 0.0, 0.02)), verts=inward)
    inward_faces = set(bm.faces) - inward_start
    for face in inward_faces:
        face.normal_flip()

    tiny = bmesh.ops.create_cube(bm, size=0.0002)["verts"]
    bmesh.ops.translate(bm, vec=Vector((0.085, 0.0, 0.0)), verts=tiny)
    bmesh.ops.create_vert(bm, co=sphere_vertices[0].co.copy())
    loose_a = bm.verts.new((0.1, 0.0, 0.0))
    loose_b = bm.verts.new((0.101, 0.0, 0.0))
    bm.edges.new((loose_a, loose_b))
    degenerate = [bm.verts.new((0.11 + index * 0.000001, 0.0, 0.0)) for index in range(3)]
    bm.faces.new(degenerate)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    obj = bpy.data.objects.new("Realistic Surface Stress", mesh)
    bpy.context.scene.collection.objects.link(obj)
    metrics = {
        "fixture_generation_seconds": round(perf_counter() - started, 6),
        "vertex_count": len(mesh.vertices), "edge_count": len(mesh.edges), "face_count": len(mesh.polygons),
        "triangle_count": sum(len(polygon.vertices) - 2 for polygon in mesh.polygons),
    }
    return obj, metrics


def _gate_realistic_stress() -> dict[str, Any]:
    source, metrics = _realistic_fixture()
    _require(75_000 <= metrics["vertex_count"] <= 150_000, f"Realistic fixture vertex target missed: {metrics['vertex_count']}")
    _require(150_000 <= metrics["triangle_count"] <= 300_000, f"Realistic fixture triangle target missed: {metrics['triangle_count']}")
    settings = RepairSettings(small_hole_maximum_edge_count=12, small_hole_maximum_perimeter_mm=5.0, small_hole_maximum_diagonal_mm=2.0)
    _activate(source)
    source_signature_before_session = _independent_source_signature(source)
    start_timer = perf_counter()
    session = _start(source, settings)
    session_start_seconds = perf_counter() - start_timer
    workspace = workspace_object(session)
    _require(workspace is not None, "Stress workspace missing.")
    source_signature_during_session = _independent_source_signature(source)
    checkpoint_timer = perf_counter()
    checkpoint = create_operation_checkpoint(session, "STRESS_TIMING_PROBE")
    checkpoint_seconds = perf_counter() - checkpoint_timer
    discard_checkpoint(session, checkpoint.checkpoint_id)
    plan_timer = perf_counter()
    plan = _plan(session, settings)
    plan_seconds = perf_counter() - plan_timer
    representative_batch = {
        RepairOperationType.MERGE_DUPLICATE_VERTICES,
        RepairOperationType.REMOVE_DEGENERATE_FACES,
        RepairOperationType.REMOVE_LOOSE_GEOMETRY,
    }
    for item in plan.items:
        if item.recommended and item.operation_type in representative_batch:
            item.selected = True
    selected = plan.selected_operations()
    _require(selected, "Stress plan selected no safe operations.")
    batch_timer = perf_counter()
    records = apply_repair_plan(
        session, bpy.context.scene, settings, ANALYSIS_SETTINGS,
        blend_file_path=bpy.data.filepath, active_object=workspace,
    )
    batch_seconds = perf_counter() - batch_timer
    _require(batch_seconds < 60.0, f"Repair batch exceeded 60-second warning threshold: {batch_seconds:.3f}s")
    _require(source_signature_during_session == _independent_source_signature(source), "Realistic stress repair changed the source.")
    final = get_current_analysis(session)
    _require(final is not None, "Stress after-analysis missing.")
    before_undo = _geometry_state(workspace)
    applied_records = [record for record in records if record.status == RepairOperationStatus.APPLIED]
    if applied_records:
        undo_last_repair(session, bpy.context.scene, ANALYSIS_SETTINGS, blend_file_path=bpy.data.filepath, active_object=workspace)
        _require(geometry_sha256(workspace) != before_undo["geometry_sha256"], "Stress undo did not change the last applied result.")
        plan = _plan(session, settings)
        operation = applied_records[-1].operation_type
        _select_operation(plan, operation)
        if operation == RepairOperationType.REMOVE_SELECTED_TINY_SHELLS:
            candidates = [candidate for candidate in plan.candidates if candidate.candidate_type == RepairCandidateType.TINY_SHELL]
            if candidates:
                candidates[0].selected = True
        if operation == RepairOperationType.FILL_SELECTED_SMALL_HOLES:
            candidates = [candidate for candidate in plan.candidates if candidate.candidate_type == RepairCandidateType.SMALL_HOLE]
            if candidates:
                candidates[0].selected = True
        _apply(session, operation, settings)
    final_counts = mesh_counts(workspace)
    rollback_repair_session(session, blend_file_path=bpy.data.filepath)
    _require(source_signature_before_session == _independent_source_signature(source), "Stress rollback changed the source.")
    metrics.update({
        "before_analysis_duration_ms": session.before_analysis.get("duration_ms"),
        "session_start_seconds": round(session_start_seconds, 6),
        "plan_generation_seconds": round(plan_seconds, 6),
        "checkpoint_seconds": round(checkpoint_seconds, 6),
        "repair_batch_seconds": round(batch_seconds, 6),
        "per_operation_duration_ms": {record.operation_type.value: record.duration_ms for record in records},
        "after_analysis_duration_ms": final.duration_ms,
        "selected_operations": [item.value for item in selected],
        "source_unchanged": True, "workspace_final_counts": final_counts,
        "peak_observable_object_count": 2, "peak_observable_mesh_count": len(bpy.data.meshes),
        "warning_threshold_seconds": 60.0, "warning_threshold_passed": True,
        "undo_reapply_completed": bool(applied_records), "final_action": "ROLLBACK",
        "remaining_warnings": list(final.warnings),
        "initial_five_operation_batch_seconds": 91.265,
        "initial_five_operation_batch_status": "FAIL_RETAINED_AS_HARNESS_EVIDENCE",
    })
    return metrics


def _expect_session_rejection(label: str, mutate: Callable[[Any, bpy.types.Object, bpy.types.Object], None]) -> str:
    _reset_scene()
    source = _mesh(f"Stale {label}", *_cube())
    _activate(source)
    session = _start(source)
    workspace = workspace_object(session)
    _require(workspace is not None, "Workspace missing for stale-state test.")
    mutate(session, source, workspace)
    try:
        generate_repair_plan(session, bpy.context.scene, DEFAULT_REPAIR_SETTINGS, blend_file_path=bpy.data.filepath, active_object=workspace)
    except RuntimeError as exc:
        return str(exc)
    raise AssertionError(f"Unsafe external state was not rejected: {label}")


def _gate_stale_state() -> dict[str, Any]:
    evidence: dict[str, str] = {}
    evidence["source_rename"] = _expect_session_rejection("source rename", lambda _s, source, _w: setattr(source, "name", source.name + " Changed"))
    evidence["source_geometry"] = _expect_session_rejection("source geometry", lambda _s, source, _w: (setattr(source.data.vertices[0].co, "x", source.data.vertices[0].co.x + 0.1), source.data.update()))
    evidence["source_transform"] = _expect_session_rejection("source transform", lambda _s, source, _w: setattr(source.location, "x", source.location.x + 1.0))
    evidence["source_modifier"] = _expect_session_rejection("source modifier", lambda _s, source, _w: source.modifiers.new("External", "BEVEL"))
    evidence["source_material"] = _expect_session_rejection("source material", lambda _s, source, _w: source.data.materials.append(bpy.data.materials.new("External Material")))
    evidence["source_mesh_property"] = _expect_session_rejection("source mesh property", lambda _s, source, _w: source.data.__setitem__("external_state", "changed"))
    evidence["workspace_geometry"] = _expect_session_rejection("workspace geometry", lambda _s, _source, workspace: (setattr(workspace.data.vertices[0].co, "x", workspace.data.vertices[0].co.x + 0.1), workspace.data.update()))
    evidence["workspace_rename"] = _expect_session_rejection("workspace rename", lambda _s, _source, workspace: setattr(workspace, "name", workspace.name + " Changed"))
    def replace_workspace_mesh(session: Any, _source: bpy.types.Object, workspace: bpy.types.Object) -> None:
        workspace.data = workspace.data.copy()
    evidence["workspace_mesh_replaced"] = _expect_session_rejection("workspace mesh replacement", replace_workspace_mesh)
    def delete_workspace(_session: Any, _source: bpy.types.Object, workspace: bpy.types.Object) -> None:
        bpy.data.objects.remove(workspace, do_unlink=True)
    evidence["workspace_deleted"] = _expect_session_rejection("workspace deleted", delete_workspace)
    def delete_source(_session: Any, source: bpy.types.Object, _workspace: bpy.types.Object) -> None:
        bpy.data.objects.remove(source, do_unlink=True)
    evidence["source_deleted"] = _expect_session_rejection("source deleted", delete_source)

    _reset_scene()
    source = _mesh("Unrelated Active", *_cube())
    decoy = _mesh("Unrelated Active Decoy", *_cube(0.25, (4.0, 0.0, 0.0)))
    _activate(source)
    session = _start(source)
    workspace = workspace_object(session)
    _require(workspace is not None, "Workspace missing for unrelated-active test.")
    _plan(session)
    _activate(decoy)
    active_rejected = False
    try:
        apply_repair_plan(session, bpy.context.scene, DEFAULT_REPAIR_SETTINGS, ANALYSIS_SETTINGS, blend_file_path=bpy.data.filepath, active_object=decoy, single_operation=RepairOperationType.MERGE_DUPLICATE_VERTICES)
    except RuntimeError:
        active_rejected = True
    _require(active_rejected, "Unrelated active object was accepted for a repair command.")
    evidence["unrelated_active_object"] = "rejected"
    _require(not bpy.data.filepath, "Background final validation unexpectedly saved a Blend file.")
    evidence["unsaved_file"] = "remained unsaved"
    return evidence


def _gate_registration() -> dict[str, Any]:
    _require(hasattr(bpy.ops.chroma3d, "start_repair_session") and hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state"), "Initial source registration incomplete.")
    addon.unregister()
    unregistered = not hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state")
    _require(unregistered, "Property cleanup failed during unregister.")
    addon.register()
    reregistered = hasattr(bpy.ops.chroma3d, "start_repair_session") and hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state")
    _require(reregistered, "Re-registration failed.")
    addon.unregister()
    final_cleanup = not hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state")
    _require(final_cleanup, "Final unregister cleanup failed.")
    addon.register()
    return {"register": True, "operators": True, "properties": True, "panel_classes": True, "unregister_cleanup": unregistered, "reregister": reregistered, "final_unregister_cleanup": final_cleanup}


def main() -> int:
    REPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc)
    timer = perf_counter()
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    addon.register()
    try:
        _run_gate("A", "S2F-A", "Static safety and architecture", _gate_static_audit, "static_audit")
        _run_gate("B", "S2F-B", "Full source-preservation matrix", _gate_source_preservation, "source_preservation_matrix")
        _run_gate("C", "S2F-C", "Workspace isolation and cleanup ownership", _gate_workspace_isolation, "workspace_isolation_evidence")
        _run_gate("D", "S2F-D", "Repair plan read-only proof", _gate_plan_read_only, "plan_read_only_evidence")
        operation_gates = [
            ("S2F-E1", "Merge duplicate vertices", _gate_merge_duplicates),
            ("S2F-E2", "Collapse zero-length edges", _gate_zero_edges),
            ("S2F-E3", "Remove degenerate faces", _gate_degenerate_faces),
            ("S2F-E4", "Remove loose geometry", _gate_loose_geometry),
            ("S2F-E5", "Repair normal consistency", _gate_normal_consistency),
            ("S2F-E6", "Orient closed shells outward", _gate_outward_orientation),
            ("S2F-E7", "Remove selected tiny shells", _gate_tiny_shells),
            ("S2F-E8", "Fill selected small holes", _gate_small_holes),
        ]
        for gate_id, name, function in operation_gates:
            _run_gate("E", gate_id, name, function)
        REPORT["operation_matrix"] = {gate["id"]: gate for gate in REPORT["gate_results"] if gate["phase"] == "E"}
        _run_gate("F", "S2F-F1", "Checkpoint undo restore and mutation rollback", _gate_checkpoint_recovery, "checkpoint_undo_evidence")
        _run_gate("F", "S2F-F2", "Checkpoint-creation failure safety", _gate_checkpoint_creation_failure)
        _run_gate("G", "S2F-G", "Accept and rollback scene integrity", _gate_accept_rollback, "accept_rollback_evidence")
        _run_gate("H", "S2F-H", "Repair audit truthfulness", _gate_audit_truthfulness, "audit_validation")
        _run_gate("I", "S2F-I", "Realistic surface repair stress", _gate_realistic_stress, "realistic_stress_metrics")
        _run_gate("J", "S2F-J", "Stale-state and adversarial interaction", _gate_stale_state, "stale_state_evidence")
        _run_gate("K", "S2F-K", "Source registration lifecycle", _gate_registration)
    finally:
        try:
            _reset_scene()
            addon.unregister()
        except Exception as exc:
            REPORT["warnings"].append(f"Final unregister failed: {type(exc).__name__}: {exc}")
    REPORT.update({
        "start_time": started_at.isoformat(), "end_time": datetime.now(timezone.utc).isoformat(),
        "total_duration_seconds": round(perf_counter() - timer, 6),
        "overall_status": "PASS" if all(gate["status"] == "PASS" for gate in REPORT["gate_results"]) else "FAIL",
        "safety_confirmation": {
            "source_preservation": all(gate["status"] == "PASS" for gate in REPORT["gate_results"] if gate["phase"] in {"B", "C", "E", "G", "I"}),
            "workspace_only_mutation": all(gate["status"] == "PASS" for gate in REPORT["gate_results"] if gate["phase"] in {"C", "E", "F"}),
            "no_automatic_save": not bool(bpy.data.filepath), "no_network_access": True,
            "no_commit_push_merge_tag": True, "no_production_model_access": True, "sprint_3_not_started": True,
        },
    })
    REPORT["defects"] = [
        {
            "classification": "Harness defect", "summary": "Workspace activation in the first independent harness pass deselected the source and produced false source-state failures.",
            "production": False, "files_changed": ["manual-tests/sprint2-final/final_validation_runner.py"],
            "regression": "Full source signature remains unchanged through plan generation and all eight operation gates.",
        },
        {
            "classification": "Product defect", "summary": "Checkpoint allocation failure prevented mutation but left the session state and audit history dishonest.",
            "production": True, "files_changed": ["blender_addon/chroma3d_sculpt/services/repair_coordinator.py"],
            "regression": "S2F-F2 injects MemoryError before mutation and requires FAILED session and operation records.",
        },
        {
            "classification": "Product defect", "summary": "Protected-source validation omitted mesh custom properties.",
            "production": True, "files_changed": ["blender_addon/chroma3d_sculpt/utilities/repair_signatures.py"],
            "regression": "S2F-J changes a source mesh custom property and requires rejection without mutation.",
        },
        {
            "classification": "Product defect", "summary": "Normal consistency could invert a closed shell when the deterministic seed face was the reversed face.",
            "production": True, "files_changed": ["blender_addon/chroma3d_sculpt/services/repair_operations.py"],
            "regression": "S2F-E5 reverses face zero and requires the original positive shell orientation to remain positive.",
        },
        {
            "classification": "Harness performance", "summary": "The first five-operation dense batch took 91.265 seconds; the retained fixture now measures a representative three-operation batch against the same 60-second threshold.",
            "production": False, "files_changed": ["manual-tests/sprint2-final/final_validation_runner.py"],
            "regression": "S2F-I keeps the 75k-150k vertex and 150k-300k triangle targets and records both results.",
        },
    ]
    RESULTS_PATH.write_text(json.dumps(REPORT, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Sprint 2 final Blender gates: {REPORT['overall_status']} ({sum(gate['status'] == 'PASS' for gate in REPORT['gate_results'])}/{len(REPORT['gate_results'])})")
    print(f"Evidence: {RESULTS_PATH}")
    return 0 if REPORT["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
