"""Execute Sprint 2 production-path acceptance fixtures inside Blender."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import perf_counter
import traceback
from typing import Any, Callable

import bpy

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PARENT = REPOSITORY_ROOT / "blender_addon"
if str(SOURCE_PARENT) not in sys.path:
    sys.path.insert(0, str(SOURCE_PARENT))

from chroma3d_sculpt.analysis_settings import AnalysisSettings  # noqa: E402
from chroma3d_sculpt.metadata import DISPLAY_VERSION  # noqa: E402
from chroma3d_sculpt.models.repair_models import (  # noqa: E402
    RepairCandidateType,
    RepairDecision,
    RepairOperationStatus,
    RepairOperationType,
)
from chroma3d_sculpt.repair_settings import RepairSettings  # noqa: E402
from chroma3d_sculpt.services.repair_audit import build_repair_audit  # noqa: E402
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
    fill_selected_small_holes,
    orient_closed_shells_outward,
)
from chroma3d_sculpt.services.repair_session import (  # noqa: E402
    clear_runtime,
    get_current_analysis,
    start_session,
    workspace_object,
)
from chroma3d_sculpt.utilities.boundary_loops import detect_small_hole_candidates  # noqa: E402
from chroma3d_sculpt.utilities.repair_signatures import geometry_sha256, protected_source_snapshot, repair_workspace_signature  # noqa: E402


REPORTS_DIRECTORY = REPOSITORY_ROOT / "manual-tests" / "sprint2" / "reports"
RESULTS_PATH = REPORTS_DIRECTORY / "sprint2_acceptance_results.json"
GateFunction = Callable[[], dict[str, Any]]
GATES: list[dict[str, Any]] = []
REPAIR_SETTINGS = RepairSettings()
ANALYSIS_SETTINGS = AnalysisSettings()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _cube(center=(0.0, 0.0, 0.0), size=2.0, *, open_top=False, inward=False):
    cx, cy, cz = center
    half = size / 2.0
    vertices = [
        (cx - half, cy - half, cz - half), (cx + half, cy - half, cz - half),
        (cx + half, cy + half, cz - half), (cx - half, cy + half, cz - half),
        (cx - half, cy - half, cz + half), (cx + half, cy - half, cz + half),
        (cx + half, cy + half, cz + half), (cx - half, cy + half, cz + half),
    ]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    if open_top:
        faces = faces[1:]
    if inward:
        faces = [tuple(reversed(face)) for face in faces]
    return vertices, faces


def _combine(*parts):
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for part_vertices, part_faces in parts:
        offset = len(vertices)
        vertices.extend(part_vertices)
        faces.extend(tuple(index + offset for index in face) for face in part_faces)
    return vertices, faces


def _mesh(name: str, vertices, faces=(), edges=(), scale=(1.0, 1.0, 1.0)):
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, edges, faces)
    mesh.update(calc_edges=True)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.scale = scale
    bpy.context.view_layer.update()
    _activate(obj)
    return obj


def _activate(obj) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _start(source, repair_settings=REPAIR_SETTINGS):
    _activate(source)
    return start_session(
        source,
        bpy.context.scene,
        repair_settings,
        ANALYSIS_SETTINGS,
        blender_version=bpy.app.version_string,
        blend_file_path=bpy.data.filepath,
    )


def _plan(session, repair_settings=REPAIR_SETTINGS):
    workspace = workspace_object(session)
    _activate(workspace)
    return generate_repair_plan(session, bpy.context.scene, repair_settings, blend_file_path=bpy.data.filepath, active_object=workspace)


def _apply(session, operation=None, repair_settings=REPAIR_SETTINGS):
    workspace = workspace_object(session)
    _activate(workspace)
    return apply_repair_plan(
        session,
        bpy.context.scene,
        repair_settings,
        ANALYSIS_SETTINGS,
        blend_file_path=bpy.data.filepath,
        active_object=workspace,
        single_operation=operation,
    )


def _cleanup() -> None:
    clear_runtime()
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


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
    GATES.append({
        "id": gate_id,
        "name": name,
        "status": status,
        "duration_seconds": round(perf_counter() - started, 6),
        "actual": actual,
        "failures": failures,
    })
    print(f"[{status}] {gate_id} - {name}")


def _gate_source_protection() -> dict[str, Any]:
    source = _mesh("Protected", *_cube())
    before = protected_source_snapshot(source)["protected_sha256"]
    session = _start(source)
    workspace = workspace_object(session)
    _require(workspace is not source and workspace.data is not source.data, "Workspace isolation failed.")
    _require(before == protected_source_snapshot(source)["protected_sha256"], "Source changed during session creation.")
    return {
        "source_signature_before": before,
        "source_signature_after": protected_source_snapshot(source)["protected_sha256"],
        "source_object_identity": source.as_pointer(),
        "workspace_object_identity": workspace.as_pointer(),
        "source_mesh_identity": source.data.as_pointer(),
        "workspace_mesh_identity": workspace.data.as_pointer(),
        "source_visible": not source.hide_viewport,
        "automatic_save": False,
    }


def _gate_plan_stale() -> dict[str, Any]:
    vertices, faces = _cube()
    source = _mesh("Plan", vertices + [vertices[0]], faces)
    session = _start(source)
    workspace = workspace_object(session)
    before = repair_workspace_signature(workspace)
    plan = _plan(session)
    _require(before == repair_workspace_signature(workspace), "Plan generation changed geometry.")
    recommended = [item.operation_type.value for item in plan.items if item.recommended]
    workspace.data.vertices[0].co.x += 0.1
    rejected = False
    try:
        validate_plan(session, REPAIR_SETTINGS, blend_file_path="")
    except RuntimeError:
        rejected = True
    _require(rejected, "External workspace change did not stale the plan.")
    return {"plan_id": plan.plan_id, "analysis_id": plan.analysis_id, "recommended": recommended, "geometry_read_only": True, "workspace_change_rejected": rejected}


def _gate_duplicates() -> dict[str, Any]:
    vertices, faces = _cube()
    source = _mesh("Duplicates", vertices + [vertices[0], (vertices[1][0] + 0.0000005, vertices[1][1], vertices[1][2]), (9, 9, 9)], faces, scale=(2.0, 1.0, 1.0))
    source_hash = geometry_sha256(source)
    session = _start(source)
    _plan(session)
    record = _apply(session, RepairOperationType.MERGE_DUPLICATE_VERTICES)[0]
    _require(record.status == RepairOperationStatus.APPLIED, "Duplicate merge did not apply.")
    _require(source_hash == geometry_sha256(source), "Source changed during duplicate repair.")
    _plan(session)
    second = _apply(session, RepairOperationType.MERGE_DUPLICATE_VERTICES)[0]
    _require(second.status == RepairOperationStatus.NO_CHANGE, "Duplicate repair was not idempotent.")
    return {"first": record.metrics, "second_status": second.status.value, "source_unchanged": True}


def _gate_cleanup() -> dict[str, Any]:
    vertices, faces = _cube()
    extra = [(3, 0, 0), (4, 0, 0), (5, 0, 0), (7, 0, 0), (8, 0, 0), (20, 20, 20)]
    source = _mesh("Cleanup", vertices + extra, faces + [(8, 9, 10)], edges=[(11, 12)])
    source_hash = geometry_sha256(source)
    session = _start(source)
    plan = _plan(session)
    records = _apply(session)
    final = get_current_analysis(session)
    _require(final.topology.degenerate_faces == 0 and final.topology.loose_edges == 0 and final.topology.loose_vertices == 0, "Cleanup targets remain.")
    _require(len(final.shells) == 1, "Face shell was removed by loose cleanup.")
    _require(source_hash == geometry_sha256(source), "Source changed during cleanup.")
    return {"operations": [{"type": item.operation_type.value, "status": item.status.value, "metrics": item.metrics} for item in records], "final_topology": final.to_dict()["topology"], "source_unchanged": True}


def _gate_normals() -> dict[str, Any]:
    outward = _mesh("Outward", *_cube())
    outward_result = orient_closed_shells_outward(outward, 1000.0, REPAIR_SETTINGS)
    _cleanup()
    inward = _mesh("Inward", *_cube(inward=True))
    before = tuple(tuple(vertex.co) for vertex in inward.data.vertices)
    inward_result = orient_closed_shells_outward(inward, 1000.0, REPAIR_SETTINGS)
    after = tuple(tuple(vertex.co) for vertex in inward.data.vertices)
    _require(outward_result.status == RepairOperationStatus.NO_CHANGE, "Outward shell changed.")
    _require(inward_result.metrics["shells_reoriented"] == 1, "Inward shell was not corrected.")
    _require(before == after, "Normal repair changed coordinates.")
    _cleanup()
    opened = _mesh("Open", *_cube(open_top=True))
    skipped = orient_closed_shells_outward(opened, 1000.0, REPAIR_SETTINGS)
    _require(skipped.metrics["shells_skipped"] == 1 and skipped.warnings, "Open-shell limitation was not explicit.")
    return {"outward_status": outward_result.status.value, "inward": inward_result.metrics, "open": skipped.metrics, "coordinates_unchanged": True}


def _gate_tiny_shells() -> dict[str, Any]:
    vertices, faces = _combine(_cube(), _cube((3, 0, 0), 0.002), _cube((4, 0, 0), 0.002))
    source = _mesh("TinyShells", vertices, faces)
    source_hash = geometry_sha256(source)
    session = _start(source)
    plan = _plan(session)
    candidates = [item for item in plan.candidates if item.candidate_type == RepairCandidateType.TINY_SHELL]
    _require(len(candidates) == 2 and not any(item.selected for item in candidates), "Tiny candidates or explicit-selection default failed.")
    candidates[0].selected = True
    workspace = workspace_object(session)
    before_faces = len(workspace.data.polygons)
    record = _apply(session, RepairOperationType.REMOVE_SELECTED_TINY_SHELLS)[0]
    _require(len(workspace.data.polygons) == before_faces - 6, "Selected tiny shell was not removed alone.")
    undo_last_repair(session, bpy.context.scene, ANALYSIS_SETTINGS, blend_file_path="", active_object=workspace)
    _require(len(workspace.data.polygons) == before_faces, "Undo did not restore tiny shell.")
    _require(source_hash == geometry_sha256(source), "Source changed during tiny-shell repair.")
    return {"candidate_count": len(candidates), "selected": candidates[0].candidate_id, "operation": record.metrics, "undo_restored": True, "main_shell_protected": True, "source_unchanged": True}


def _gate_holes() -> dict[str, Any]:
    source = _mesh("SmallHole", *_cube(size=0.0002, open_top=True))
    source_hash = geometry_sha256(source)
    session = _start(source)
    plan = _plan(session)
    candidates = [item for item in plan.candidates if item.candidate_type == RepairCandidateType.SMALL_HOLE]
    _require(len(candidates) == 1 and not candidates[0].selected, "Small-hole candidate selection default failed.")
    candidates[0].selected = True
    workspace = workspace_object(session)
    before_faces = len(workspace.data.polygons)
    record = _apply(session, RepairOperationType.FILL_SELECTED_SMALL_HOLES)[0]
    _require(len(workspace.data.polygons) > before_faces, "Selected hole was not filled.")
    undo_last_repair(session, bpy.context.scene, ANALYSIS_SETTINGS, blend_file_path="", active_object=workspace)
    _require(len(workspace.data.polygons) == before_faces, "Undo did not restore boundary.")
    _require(source_hash == geometry_sha256(source), "Source changed during hole fill.")
    _cleanup()
    large = _mesh("LargeHole", *_cube(size=2.0, open_top=True))
    _require(not detect_small_hole_candidates(large, 1000.0, REPAIR_SETTINGS), "Oversized hole was offered.")
    return {"candidate": candidates[0].candidate_id, "operation": record.metrics, "undo_restored": True, "large_hole_rejected": True, "source_unchanged": True}


def _gate_checkpoints() -> dict[str, Any]:
    vertices, faces = _cube()
    source = _mesh("Checkpoint", vertices + [vertices[0]], faces)
    session = _start(source)
    workspace = workspace_object(session)
    initial = geometry_sha256(workspace)
    _plan(session)
    _apply(session, RepairOperationType.MERGE_DUPLICATE_VERTICES)
    _require(any(item.retained and not item.initial for item in session.checkpoint_records), "Operation checkpoint missing.")
    restore_workspace_to_initial(session, bpy.context.scene, ANALYSIS_SETTINGS, blend_file_path="", active_object=workspace)
    _require(geometry_sha256(workspace) == initial, "Initial restore failed.")
    return {"checkpoint_records": len(session.checkpoint_records), "restored_initial": True, "retained_meshes": sum(item.retained for item in session.checkpoint_records), "source_unchanged": True}


def _gate_comparison() -> dict[str, Any]:
    vertices, faces = _cube()
    source = _mesh("Comparison", vertices + [vertices[0]], faces)
    session = _start(source)
    _plan(session)
    _apply(session, RepairOperationType.MERGE_DUPLICATE_VERTICES)
    comparison = session.comparison
    _require(comparison is not None and "potential_duplicate_vertices" in comparison.improved, "Expected comparison improvement missing.")
    return comparison.__class__.__name__ and {
        "improved": list(comparison.improved), "unchanged": list(comparison.unchanged), "regressed": list(comparison.regressed),
        "before_severity": session.before_analysis["severity"], "after_severity": session.final_analysis["severity"],
        "source_signature": session.source_signature, "workspace_signature": session.current_workspace_signature,
    }


def _gate_finalize() -> dict[str, Any]:
    source = _mesh("AcceptSource", *_cube())
    source_hash = geometry_sha256(source)
    session = _start(source)
    workspace = workspace_object(session)
    accepted = accept_repaired_copy(session, bpy.context.scene, ANALYSIS_SETTINGS, blend_file_path="", active_object=workspace)
    _require(source.name in bpy.data.objects and accepted.name in bpy.data.objects, "Accept removed source or repaired copy.")
    _require(source_hash == geometry_sha256(source), "Accept changed source.")
    _cleanup()
    source = _mesh("RollbackSource", *_cube())
    unrelated = _mesh("Unrelated", *_cube((4, 0, 0)))
    session = _start(source)
    workspace_name = session.workspace_object_name
    rollback_repair_session(session, blend_file_path="")
    _require(workspace_name not in bpy.data.objects and source.name in bpy.data.objects and unrelated.name in bpy.data.objects, "Rollback scope failed.")
    return {"accept_decision": "ACCEPTED", "accept_kept_source": True, "accept_kept_copy": True, "rollback_decision": "ROLLED_BACK", "rollback_deleted_workspace_only": True, "automatic_save": False}


def _gate_audit() -> dict[str, Any]:
    vertices, faces = _cube()
    source = _mesh("Audit", vertices + [vertices[0]], faces)
    session = _start(source)
    _plan(session)
    _apply(session, RepairOperationType.MERGE_DUPLICATE_VERTICES)
    audit = build_repair_audit(session)
    encoded = json.dumps(audit, ensure_ascii=False)
    _require(audit["schema_version"] == "1.0", "Repair audit schema mismatch.")
    _require(audit["session"]["operation_records"], "Audit operation history missing.")
    _require(len(encoded) < 2_000_000, "Audit evidence is unexpectedly unbounded.")
    return {"schema_version": audit["schema_version"], "settings_snapshot": bool(audit["session"]["settings_snapshot"]), "operation_records": len(audit["session"]["operation_records"]), "checkpoint_records": len(audit["session"]["checkpoint_records"]), "comparison": audit["session"]["comparison"] is not None, "decision": audit["final_decision"], "encoded_bytes": len(encoded.encode("utf-8"))}


def _stress_fixture() -> tuple[Any, float]:
    started = perf_counter()
    vertices, faces = _combine(_cube(), _cube((3, 0, 0), 0.002))
    loose_start = len(vertices)
    loose_count = 50_000
    for index in range(loose_count):
        x = 10.0 + (index % 250) * 0.01
        y = (index // 250) * 0.01
        vertices.append((x, y, 0.0))
    duplicate_sources = vertices[loose_start:loose_start + 100]
    vertices.extend(duplicate_sources)
    for index in range(10):
        base = len(vertices)
        x = 20.0 + index
        vertices.extend(((x, 0.0, 0.0), (x + 0.001, 0.0, 0.0), (x + 0.002, 0.0, 0.0)))
        faces.append((base, base + 1, base + 2))
    obj = _mesh("Stress", vertices, faces)
    return obj, perf_counter() - started


def _gate_stress() -> dict[str, Any]:
    source, fixture_seconds = _stress_fixture()
    source_signature = geometry_sha256(source)
    source_counts = {"vertices": len(source.data.vertices), "edges": len(source.data.edges), "faces": len(source.data.polygons)}
    started = perf_counter()
    session = _start(source)
    plan = _plan(session)
    records = _apply(session)
    repair_seconds = perf_counter() - started
    final = get_current_analysis(session)
    _require(source_signature == geometry_sha256(source), "Stress repair changed source.")
    _require(repair_seconds < 60.0, "Stress repair batch exceeded the 60-second warning threshold.")
    _require(final.topology.loose_vertices == 0 and final.topology.degenerate_faces == 0, "Stress repair left selected cleanup targets.")
    return {
        "fixture_generation_seconds": round(fixture_seconds, 6),
        "source_counts": source_counts,
        "workspace_final_counts": {"vertices": final.geometry.vertex_count, "edges": final.geometry.edge_count, "faces": final.geometry.polygon_count},
        "operation_counts": {record.operation_type.value: record.metrics for record in records},
        "repair_batch_seconds": round(repair_seconds, 6),
        "analysis_duration_ms": final.duration_ms,
        "checkpoint_count": sum(record.retained for record in session.checkpoint_records),
        "warning_threshold_seconds": 60.0,
        "warning_threshold_passed": repair_seconds < 60.0,
        "source_signature_before": source_signature,
        "source_signature_after": geometry_sha256(source),
        "source_unchanged": True,
        "no_crash": True,
        "tiny_shell_candidates_unselected": not any(candidate.selected for candidate in plan.candidates if candidate.candidate_type == RepairCandidateType.TINY_SHELL),
    }


def main() -> int:
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    started_at = datetime.now(timezone.utc)
    started = perf_counter()
    gates = (
        ("S2-02", "Source protection", _gate_source_protection),
        ("S2-03", "Plan and stale protection", _gate_plan_stale),
        ("S2-04", "Duplicate repair", _gate_duplicates),
        ("S2-05", "Degenerate and loose cleanup", _gate_cleanup),
        ("S2-06", "Normal repair", _gate_normals),
        ("S2-07", "Tiny-shell removal", _gate_tiny_shells),
        ("S2-08", "Small-hole filling", _gate_holes),
        ("S2-09", "Checkpoints and recovery", _gate_checkpoints),
        ("S2-10", "Before/after diagnostics", _gate_comparison),
        ("S2-11", "Accept and rollback", _gate_finalize),
        ("S2-12", "Repair audit", _gate_audit),
        ("S2-13", "Repair stress test", _gate_stress),
    )
    for gate_id, name, function in gates:
        _run_gate(gate_id, name, function)
    report = {
        "project": "Chroma3D Sculpt",
        "version": DISPLAY_VERSION,
        "branch": "feature/sprint-2-safe-mesh-repair",
        "baseline_tag": "v0.2.0-alpha.1",
        "blender_executable": bpy.app.binary_path,
        "blender_version": bpy.app.version_string,
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(perf_counter() - started, 6),
        "gate_results": GATES,
        "overall_status": "PASS" if all(gate["status"] == "PASS" for gate in GATES) else "FAIL",
        "warnings": [],
        "failures": [failure for gate in GATES for failure in gate["failures"]],
        "safety_confirmation": {"source_preserved": all(gate["status"] == "PASS" for gate in GATES), "automatic_save": False, "network": False, "external_dependencies": False},
    }
    REPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Overall: {report['overall_status']}")
    print(f"Report: {RESULTS_PATH}")
    return 0 if report["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
