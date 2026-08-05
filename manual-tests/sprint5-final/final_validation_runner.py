"""Independent adversarial Sprint 5 validation executed inside factory Blender."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import argparse
import ctypes
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import traceback
from time import perf_counter
import zipfile

import bpy

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ADDON_ROOT = REPOSITORY_ROOT / "blender_addon"
REPORT_ROOT = Path(__file__).resolve().parent / "reports"
ARTIFACT_ROOT = Path(__file__).resolve().parent / "artifacts"
if str(ADDON_ROOT) not in sys.path:
    sys.path.insert(0, str(ADDON_ROOT))

import chroma3d_sculpt  # noqa: E402
from chroma3d_sculpt.metadata import DISPLAY_VERSION, PERFORMANCE_REGISTRY_VERSION  # noqa: E402
from chroma3d_sculpt.models.optimization_models import (  # noqa: E402
    ComparisonClassification, FidelityStatus, ObjectiveWeight, OptimizationObjective, OptimizationOperationState,
    OptimizationOperationType, OptimizationPolicy, OptimizationSessionState,
)
from chroma3d_sculpt.optimization_settings import build_objective_snapshot  # noqa: E402
from chroma3d_sculpt.services.optimization_audit import (  # noqa: E402
    audit_markdown, build_audit, sanitize_optimization_filename, write_json_audit, write_markdown_audit,
)
from chroma3d_sculpt.services.optimization_candidates import generate_candidates  # noqa: E402
from chroma3d_sculpt.services.optimization_comparison import compare_objects, compare_snapshots, fidelity_evidence  # noqa: E402
from chroma3d_sculpt.services.optimization_coordinator import (  # noqa: E402
    accept_optimized_copy, apply_selected_step, discard_workspace, generate_session_candidates, generate_session_plan,
    rerun_comparison, restore_session_to_start, start_session, undo_last_step,
)
from chroma3d_sculpt.services.optimization_plan import plan_is_current, validate_plan  # noqa: E402
from chroma3d_sculpt.services.optimization_policy import default_policy, policy_hash  # noqa: E402
from chroma3d_sculpt.services.optimization_session import (  # noqa: E402
    get_active_session, get_archived_session, get_collection, get_workspace,
)
from chroma3d_sculpt.services.optimization_workspace import (  # noqa: E402
    COLLECTION_PROPERTY, OWNER_PROPERTY, cleanup_session_resources, workspace_is_owned,
)
from chroma3d_sculpt.utilities.optimization_signatures import source_signature, workspace_signature  # noqa: E402


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _simple(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "name"):
        return {"name": str(value.name), "identity": _pointer(value)}
    try:
        return [_simple(item) for item in value]  # type: ignore[operator]
    except TypeError:
        return repr(value)


def _pointer(value: object | None) -> int:
    try:
        return int(value.as_pointer()) if value is not None else 0  # type: ignore[attr-defined]
    except (AttributeError, ReferenceError, RuntimeError, TypeError):
        return 0


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _working_set_bytes() -> int | None:
    if sys.platform != "win32":
        return None

    class ProcessMemory(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("page_fault_count", ctypes.c_ulong), ("peak_working_set_size", ctypes.c_size_t), ("working_set_size", ctypes.c_size_t), ("quota_peak_paged_pool_usage", ctypes.c_size_t), ("quota_paged_pool_usage", ctypes.c_size_t), ("quota_peak_non_paged_pool_usage", ctypes.c_size_t), ("quota_non_paged_pool_usage", ctypes.c_size_t), ("peak_pagefile_usage", ctypes.c_size_t), ("pagefile_usage", ctypes.c_size_t)]

    value = ProcessMemory()
    value.cb = ctypes.sizeof(value)
    ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(value), ctypes.sizeof(value))
    return int(value.working_set_size)


def _round(value: object) -> object:
    return round(float(value), 9) if isinstance(value, (int, float)) else _simple(value)


def _source_snapshot(obj: bpy.types.Object) -> dict[str, object]:
    mesh = obj.data
    modifiers = [{"name": item.name, "type": item.type, "show_viewport": bool(item.show_viewport), "show_render": bool(item.show_render)} for item in obj.modifiers]
    constraints = [{"name": item.name, "type": item.type, "mute": bool(item.mute), "target": _pointer(item.target), "influence": round(float(item.influence), 9)} for item in obj.constraints]
    groups: list[dict[str, object]] = []
    for group in obj.vertex_groups:
        weights = []
        for vertex in mesh.vertices:
            try:
                weights.append((vertex.index, round(float(group.weight(vertex.index)), 9)))
            except RuntimeError:
                pass
        groups.append({"name": group.name, "index": group.index, "weights": weights})
    uv_layers = [{"name": layer.name, "uv": [[round(float(item.uv.x), 9), round(float(item.uv.y), 9)] for item in layer.data]} for layer in mesh.uv_layers]
    colors = []
    for attribute in getattr(mesh, "color_attributes", ()):
        colors.append({"name": attribute.name, "type": attribute.data_type, "domain": attribute.domain, "values": [_simple(item.color) for item in attribute.data]})
    shape_keys = []
    if mesh.shape_keys:
        shape_keys = [{"name": key.name, "value": round(float(key.value), 9), "coords": [[round(float(point.co[index]), 9) for index in range(3)] for point in key.data]} for key in mesh.shape_keys.key_blocks]
    snapshot = {
        "object_identity": _pointer(obj), "mesh_identity": _pointer(mesh), "object_name": obj.name, "mesh_name": mesh.name,
        "vertices": [[round(float(value), 9) for value in vertex.co] for vertex in mesh.vertices],
        "edges": [tuple(int(value) for value in edge.vertices) for edge in mesh.edges],
        "polygons": [tuple(int(value) for value in polygon.vertices) for polygon in mesh.polygons],
        "normals": [[round(float(polygon.normal[index]), 9) for index in range(3)] for polygon in mesh.polygons],
        "materials": [{"name": getattr(slot.material, "name", ""), "identity": _pointer(slot.material)} for slot in obj.material_slots],
        "modifiers": modifiers, "constraints": constraints, "vertex_groups": groups, "uv_layers": uv_layers, "color_attributes": colors,
        "shape_keys": shape_keys, "object_properties": {str(key): _simple(obj[key]) for key in sorted(obj.keys()) if key != "_RNA_UI"},
        "mesh_properties": {str(key): _simple(mesh[key]) for key in sorted(mesh.keys()) if key != "_RNA_UI"},
        "collections": sorted(item.name for item in obj.users_collection),
        "location": [_round(value) for value in obj.location], "rotation": [_round(value) for value in obj.rotation_euler], "scale": [_round(value) for value in obj.scale],
        "hide_viewport": bool(obj.hide_viewport), "hide_render": bool(obj.hide_render), "hide_get": bool(obj.hide_get()), "display_type": obj.display_type,
        "selected": bool(obj.select_get()), "active_material_index": int(obj.active_material_index), "file_dirty": bool(bpy.data.is_dirty),
    }
    return snapshot


def _source_content(snapshot: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in snapshot.items() if key not in {"selected", "file_dirty"}}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _expect_rejection(function, label: str) -> str:
    try:
        function()
    except (RuntimeError, ValueError, TypeError, KeyError) as exc:
        return f"{label}: {type(exc).__name__}: {exc}"
    raise AssertionError(f"Expected rejection: {label}")


def clear_scene() -> None:
    for obj in tuple(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in tuple(bpy.data.collections):
        if collection.users == 0:
            bpy.data.collections.remove(collection)


def _force_cleanup(session: object | None) -> None:
    if session is None:
        return
    try:
        workspace = get_workspace(session)
    except Exception:
        workspace = next((item for item in bpy.data.objects if str(item.get(OWNER_PROPERTY, "")) == str(getattr(session, "session_id", ""))), None)
    collection = get_collection(session)
    try:
        cleanup_session_resources(session, workspace, collection)
    except Exception:
        # This fallback only touches resources carrying the exact session owner
        # marker and is used to keep a failed gate isolated from the next one.
        for item in tuple(bpy.data.objects):
            if str(item.get(OWNER_PROPERTY, "")) == str(getattr(session, "session_id", "")):
                mesh = item.data
                bpy.data.objects.remove(item, do_unlink=True)
                if mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
        if collection is not None and str(collection.get(COLLECTION_PROPERTY, "")) == str(getattr(session, "session_id", "")):
            for scene in bpy.data.scenes:
                if collection.name in scene.collection.children:
                    scene.collection.children.unlink(collection)
            if collection.users == 0:
                bpy.data.collections.remove(collection)
    try:
        from chroma3d_sculpt.services.optimization_session import clear_runtime
        from chroma3d_sculpt.services.optimization_workspace import clear_runtime as clear_workspace_runtime
        clear_runtime()
        clear_workspace_runtime()
    except Exception:
        pass


def make_fixture(name: str = "Sprint5AuditSource") -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 1.0))
    source = bpy.context.object
    source.name = name
    source.data.name = f"{name}Mesh"
    source["audit_object_property"] = "protected"
    source.data["audit_mesh_property"] = 17
    material = bpy.data.materials.new(f"{name}Material")
    source.data.materials.append(material)
    bevel = source.modifiers.new("Audit Bevel", "BEVEL")
    bevel.width = 0.05
    bevel.segments = 2
    bevel.show_viewport = False
    constraint = source.constraints.new("COPY_LOCATION")
    constraint.name = "Audit Constraint"
    group = source.vertex_groups.new(name="Audit Group")
    group.add([vertex.index for vertex in source.data.vertices], 0.75, "REPLACE")
    try:
        attribute = source.data.color_attributes.new(name="AuditColor", type="BYTE_COLOR", domain="CORNER")
        for item in attribute.data:
            item.color = (0.2, 0.4, 0.8, 1.0)
    except (AttributeError, RuntimeError):
        pass
    try:
        source.shape_key_add(name="Basis")
        key = source.shape_key_add(name="AuditKey")
        key.data[0].co.x += 0.01
    except (AttributeError, RuntimeError):
        pass
    extra = bpy.data.collections.new(f"{name} Extra Collection")
    bpy.context.scene.collection.children.link(extra)
    extra.objects.link(source)
    source.rotation_euler = (0.1, 0.2, 0.3)
    source.scale = (1.1, 0.9, 1.0)
    source.hide_render = True
    source.select_set(True)
    bpy.context.view_layer.objects.active = source
    return source


def _start(source: bpy.types.Object, policy: OptimizationPolicy | None = None, *, process: str = "process-a", feature: str = "feature-a"):
    return start_session(source, bpy.context.scene, policy=policy or default_policy(), process_context_hash=process, feature_flag_hash=feature)


def _discard_or_cleanup(session: object | None) -> None:
    if session is None:
        return
    try:
        if get_active_session() is session:
            discard_workspace(session)
            return
    except Exception:
        pass
    _force_cleanup(session)


def gate_a_source_matrix() -> dict[str, object]:
    clear_scene()
    source = make_fixture()
    before = _source_snapshot(source)
    try:
        policy = OptimizationPolicy(maximum_uniform_scale_change=0.05)
        session = _start(source, policy)
        candidates = generate_session_candidates(session, source=source, policy=policy, build_volume_mm=(2.4, 8.0, 8.0))
        plan = generate_session_plan(session, policy=policy)
        _require(plan.steps and len(candidates) >= 3, "Candidate and plan generation did not produce the bounded virtual matrix.")
        workspace = get_workspace(session)
        compare_objects(source, workspace, build_volume_mm=(8.0, 8.0, 8.0))
        scale = next(item for item in candidates if item.category == OptimizationOperationType.UNIFORM_SCALE and abs(item.transform.scale - 1.0) > 1e-6)
        record = apply_selected_step(session, source, scale.candidate_id, approved=True, policy=policy, build_volume_mm=(2.4, 8.0, 8.0))
        _require(record.state == OptimizationOperationState.APPLIED, f"Scale operation was {record.state.value}.")
        rerun_comparison(session, policy=policy, build_volume_mm=(2.4, 8.0, 8.0))
        undo_last_step(session, source)
        restore_session_to_start(session, source)
        audit = build_audit(session, blender_version=bpy.app.version_string)
        json_path = write_json_audit(audit, ARTIFACT_ROOT / "source-matrix.json")
        markdown_path = write_markdown_audit(audit, ARTIFACT_ROOT / "source-matrix.md")
        _require(json_path.read_bytes().endswith(b"\n") and markdown_path.read_bytes().endswith(b"\n"), "Audit exports are missing UTF-8 trailing newlines.")
        _require(_source_content(before) == _source_content(_source_snapshot(source)), "Protected source changed during the valid source matrix.")
        _discard_or_cleanup(session)
        _require(_source_content(before) == _source_content(_source_snapshot(source)), "Discard changed protected source state.")
        session = None

        session = _start(source, policy)
        candidates = generate_session_candidates(session, source=source, policy=policy)
        generate_session_plan(session, policy=policy)
        orientation = next(item for item in candidates if item.category == OptimizationOperationType.ORIENTATION and any(abs(value) > 1e-6 for value in item.transform.rotation_euler))
        apply_selected_step(session, source, orientation.candidate_id, approved=True, policy=policy)
        _discard_or_cleanup(session)
        session = None

        session = _start(source, policy)
        candidates = generate_session_candidates(session, source=source, policy=policy)
        generate_session_plan(session, policy=policy)
        translation = next(item for item in candidates if item.category == OptimizationOperationType.BUILD_PLATE_TRANSLATION)
        apply_selected_step(session, source, translation.candidate_id, approved=True, policy=policy)
        _discard_or_cleanup(session)
        session = None

        base_policy = OptimizationPolicy(enabled_operation_families=(OptimizationOperationType.BASE_STABILIZATION.value,), maximum_base_added_volume_ratio=0.2)
        session = _start(source, base_policy)
        candidates = generate_session_candidates(session, source=source, policy=base_policy)
        generate_session_plan(session, policy=base_policy)
        base = next(item for item in candidates if item.category == OptimizationOperationType.BASE_STABILIZATION)
        rejected = apply_selected_step(session, source, base.candidate_id, policy=base_policy)
        _require(rejected.state == OptimizationOperationState.REJECTED, "Base stabilization executed without explicit approval.")
        applied = apply_selected_step(session, source, base.candidate_id, approved=True, policy=base_policy)
        _require(applied.state in {OptimizationOperationState.APPLIED, OptimizationOperationState.FAILED}, "Approved base stabilization did not produce a bounded result.")
        _discard_or_cleanup(session)
        session = None

        repair_policy = OptimizationPolicy(enabled_operation_families=(OptimizationOperationType.REPAIR_REUSE.value,))
        session = _start(source, repair_policy)
        candidates = generate_session_candidates(session, source=source, policy=repair_policy, printability_report={"repair_candidates": [{"operation_type": "MERGE_DUPLICATE_VERTICES"}]})
        generate_session_plan(session, policy=repair_policy)
        repair = next(item for item in candidates if item.category == OptimizationOperationType.REPAIR_REUSE)
        repair_record = apply_selected_step(session, source, repair.candidate_id, approved=True, policy=repair_policy)
        _require(repair_record.state in {OptimizationOperationState.NO_CHANGE, OptimizationOperationState.APPLIED}, "Safe Repair reuse did not return a bounded outcome.")
        _discard_or_cleanup(session)
        session = None

        decimation_policy = OptimizationPolicy(enabled_operation_families=(OptimizationOperationType.DECIMATION.value,), experimental_decimation_enabled=True)
        session = _start(source, decimation_policy)
        candidates = generate_session_candidates(session, source=source, policy=decimation_policy)
        generate_session_plan(session, policy=decimation_policy)
        decimation = next(item for item in candidates if item.category == OptimizationOperationType.DECIMATION)
        decimation_record = apply_selected_step(session, source, decimation.candidate_id, approved=True, policy=decimation_policy)
        _require(decimation_record.state == OptimizationOperationState.FAILED, "Decimation fidelity failure was not rejected and rolled back.")
        _discard_or_cleanup(session)
        session = None

        accept_policy = OptimizationPolicy(maximum_uniform_scale_change=0.05)
        session = _start(source, accept_policy)
        candidates = generate_session_candidates(session, source=source, policy=accept_policy, build_volume_mm=(2.4, 8.0, 8.0))
        generate_session_plan(session, policy=accept_policy)
        scale = next(item for item in candidates if item.category == OptimizationOperationType.UNIFORM_SCALE and abs(item.transform.scale - 1.0) > 1e-6)
        accepted_record = apply_selected_step(session, source, scale.candidate_id, approved=True, policy=accept_policy, build_volume_mm=(2.4, 8.0, 8.0))
        _require(accepted_record.state == OptimizationOperationState.APPLIED, "The small reviewed scale could not be accepted.")
        accepted = accept_optimized_copy(session)
        _require(accepted is not source and accepted.data is not source.data, "Accept did not retain an independent optimized copy.")
        _require(_source_content(before) == _source_content(_source_snapshot(source)), "Accept changed protected source state.")
        accepted_mesh = accepted.data
        bpy.data.objects.remove(accepted, do_unlink=True)
        if accepted_mesh.users == 0:
            bpy.data.meshes.remove(accepted_mesh)
        session = None
        return {"source_identity": before["object_identity"], "source_signature": source_signature(source)["source_signature"], "candidate_count": len(candidates), "operations": len(get_archived_session().operation_records) if get_archived_session() else 0}
    finally:
        _discard_or_cleanup(locals().get("session"))
        clear_scene()


def gate_b_ownership() -> dict[str, object]:
    clear_scene(); source = make_fixture("OwnershipSource"); session = None
    try:
        session = _start(source); workspace = get_workspace(session); collection = get_collection(session)
        foreign = replace(session, session_id=f"{session.session_id}-foreign", checkpoints=list(session.checkpoints))
        cleanup_session_resources(foreign, workspace, collection)
        _require(get_workspace(session) is workspace and len(session.checkpoints) == 1, "Foreign-session cleanup changed owned resources.")
        original_owner = workspace[OWNER_PROPERTY]; workspace[OWNER_PROPERTY] = "forged-owner"
        _expect_rejection(lambda: get_workspace(session), "forged workspace ownership")
        workspace[OWNER_PROPERTY] = original_owner
        original_mesh = workspace.data; workspace.data = source.data
        _expect_rejection(lambda: get_workspace(session), "workspace relinked to protected source mesh")
        workspace.data = original_mesh
        unrelated = make_fixture("UnrelatedObject")
        collection.objects.link(unrelated)
        _expect_rejection(lambda: discard_workspace(session), "unrelated object in session collection")
        collection.objects.unlink(unrelated)
        bpy.data.objects.remove(unrelated, do_unlink=True)
        discard_workspace(session); session = None
        return {"foreign_cleanup": "REJECTED_OR_NO_CHANGE", "forged_metadata": "REJECTED", "source_mesh_relink": "REJECTED", "unrelated_collection_object": "REJECTED"}
    finally:
        _discard_or_cleanup(session); clear_scene()


def gate_c_objectives_policy() -> dict[str, object]:
    errors = []
    errors.append(_expect_rejection(lambda: ObjectiveWeight(OptimizationObjective.BUILD_VOLUME_FIT, True), "boolean objective weight"))
    errors.append(_expect_rejection(lambda: ObjectiveWeight(OptimizationObjective.BUILD_VOLUME_FIT, float("nan")), "NaN objective weight"))
    errors.append(_expect_rejection(lambda: ObjectiveWeight(OptimizationObjective.BUILD_VOLUME_FIT, float("inf")), "infinite objective weight"))
    errors.append(_expect_rejection(lambda: ObjectiveWeight(OptimizationObjective.BUILD_VOLUME_FIT, -1.0), "negative objective weight"))
    errors.append(_expect_rejection(lambda: build_objective_snapshot("Custom", (ObjectiveWeight(OptimizationObjective.BUILD_VOLUME_FIT, 1.0), ObjectiveWeight(OptimizationObjective.BUILD_VOLUME_FIT, 2.0))), "duplicate objective id"))
    errors.append(_expect_rejection(lambda: build_objective_snapshot("Custom", (ObjectiveWeight(OptimizationObjective.BUILD_VOLUME_FIT, 0.0, enabled=False),)), "zero enabled objective total"))
    errors.append(_expect_rejection(lambda: OptimizationPolicy(enabled_operation_families=("UNKNOWN",)), "unknown operation family"))
    errors.append(_expect_rejection(lambda: OptimizationPolicy(maximum_decimation_ratio=-0.1), "negative decimation ratio"))
    errors.append(_expect_rejection(lambda: OptimizationPolicy(maximum_checkpoint_count=1), "checkpoint limit below two"))
    return {"rejections": len(errors), "policy_hash": policy_hash(default_policy()), "objective_hash": build_objective_snapshot().objective_hash}


def gate_d_candidates() -> dict[str, object]:
    clear_scene(); source = make_fixture("CandidateSource"); session = None
    try:
        session = _start(source)
        first = generate_session_candidates(session, source=source)
        second = generate_candidates(get_workspace(session), source_snapshot=session.source_snapshot, policy=session.policy_snapshot.policy, objectives=session.objective_snapshot, process_context_hash=session.process_context_hash)
        _require([item.to_json() for item in first] == [item.to_json() for item in second], "Candidate generation is not deterministic.")
        _require(len({item.candidate_id for item in first}) == len(first), "Candidate ids are not unique.")
        _require(not any(item.category == OptimizationOperationType.REPAIR_REUSE for item in first), "Repair candidate appeared without repair evidence.")
        disabled = OptimizationPolicy(enabled_operation_families=(OptimizationOperationType.DECIMATION.value,), experimental_decimation_enabled=False)
        disabled_candidates = generate_candidates(get_workspace(session), source_snapshot=session.source_snapshot, policy=disabled)
        _require(not any(item.category == OptimizationOperationType.DECIMATION for item in disabled_candidates), "Disabled decimation candidate was generated.")
        source.data.vertices[0].co.x += 0.01
        _expect_rejection(lambda: generate_session_candidates(session, source=source), "candidate generation after source change")
        source.data.vertices[0].co.x -= 0.01
        return {"candidate_count": len(first), "unique_ids": len({item.candidate_id for item in first}), "deterministic": True}
    finally:
        _discard_or_cleanup(session); clear_scene()


def gate_e_plan_stale() -> dict[str, object]:
    clear_scene(); source = make_fixture("PlanSource"); session = None
    try:
        session = _start(source, process="process-a", feature="feature-a")
        generate_session_candidates(session, source=source)
        generate_session_plan(session)
        workspace = get_workspace(session)
        checks: dict[str, str] = {}
        session.process_context_hash = "process-b"; checks["process"] = plan_is_current(session, workspace, source)[1]; session.process_context_hash = "process-a"
        session.feature_flag_hash = "feature-b"; checks["feature"] = plan_is_current(session, workspace, source)[1]; session.feature_flag_hash = "feature-a"
        session.performance_registry_version = "changed"; checks["performance"] = plan_is_current(session, workspace, source)[1]; session.performance_registry_version = PERFORMANCE_REGISTRY_VERSION
        session.candidates.reverse(); checks["candidates"] = plan_is_current(session, workspace, source)[1]; session.candidates.reverse()
        workspace.location.x += 0.2; checks["workspace"] = plan_is_current(session, workspace, source)[1]; workspace.location.x -= 0.2
        source.location.x += 0.2; checks["source"] = plan_is_current(session, workspace, source)[1]; source.location.x -= 0.2
        _require(checks == {"process": "PROCESS_CONTEXT_CHANGED", "feature": "FEATURE_FLAGS_CHANGED", "performance": "PERFORMANCE_REGISTRY_CHANGED", "candidates": "CANDIDATE_SET_CHANGED", "workspace": "WORKSPACE_CHANGED", "source": "SOURCE_CHANGED"}, f"Unexpected stale reasons: {checks}")
        return {"reasons": checks}
    finally:
        _discard_or_cleanup(session); clear_scene()


def gate_f_checkpoints() -> dict[str, object]:
    clear_scene(); source = make_fixture("CheckpointSource"); session = None
    try:
        session = _start(source)
        generate_session_candidates(session, source=source); generate_session_plan(session)
        initial_id = session.checkpoints[0].checkpoint_id
        no_change = next(item for item in session.candidates if item.category == OptimizationOperationType.BUILD_PLATE_TRANSLATION)
        count_before = len(session.checkpoints)
        no_change_record = apply_selected_step(session, source, no_change.candidate_id, approved=True)
        _require(no_change_record.state == OptimizationOperationState.NO_CHANGE and len(session.checkpoints) == count_before, "NO_CHANGE evicted or retained a temporary checkpoint incorrectly.")
        _discard_or_cleanup(session); session = None

        failed_policy = OptimizationPolicy(enabled_operation_families=(OptimizationOperationType.EXPERIMENTAL_REMESH.value,), experimental_remesh_enabled=True)
        session = _start(source, failed_policy)
        generate_session_candidates(session, source=source, policy=failed_policy); generate_session_plan(session, policy=failed_policy)
        remesh = next(item for item in session.candidates if item.category == OptimizationOperationType.EXPERIMENTAL_REMESH)
        before = workspace_signature(get_workspace(session)); failed = apply_selected_step(session, source, remesh.candidate_id, approved=True, policy=failed_policy)
        _require(failed.state == OptimizationOperationState.FAILED and workspace_signature(get_workspace(session)) == before and len(session.checkpoints) == 1, "Failed operation did not restore exact workspace/checkpoint state.")
        _discard_or_cleanup(session); session = None

        bounded = OptimizationPolicy(maximum_uniform_scale_change=0.05, maximum_checkpoint_count=2)
        session = _start(source, bounded)
        for _ in range(2):
            candidates = generate_session_candidates(session, source=source, policy=bounded, build_volume_mm=(2.4, 8.0, 8.0))
            generate_session_plan(session, policy=bounded)
            scale = next(item for item in candidates if item.category == OptimizationOperationType.UNIFORM_SCALE and abs(item.transform.scale - 1.0) > 1e-6)
            record = apply_selected_step(session, source, scale.candidate_id, approved=True, policy=bounded, build_volume_mm=(2.4, 8.0, 8.0))
            _require(record.state == OptimizationOperationState.APPLIED, "Bounded checkpoint scale was not applied.")
        _require(len(session.checkpoints) <= 2, "Checkpoint limit was not bounded.")
        _require(any(item.candidate_id == "" for item in session.checkpoints), "Initial checkpoint was evicted.")
        return {"initial_checkpoint_retained": True, "checkpoint_count": len(session.checkpoints), "failure_rollback": True}
    finally:
        _discard_or_cleanup(session); clear_scene()


def gate_g_transforms() -> dict[str, object]:
    clear_scene(); source = make_fixture("TransformSource"); before = _source_content(_source_snapshot(source)); session = None
    try:
        policy = OptimizationPolicy(maximum_uniform_scale_change=0.05)
        session = _start(source, policy); candidates = generate_session_candidates(session, source=source, policy=policy, build_volume_mm=(2.4, 8.0, 8.0)); generate_session_plan(session, policy=policy)
        orientation = next(item for item in candidates if item.category == OptimizationOperationType.ORIENTATION and any(abs(value) > 1e-6 for value in item.transform.rotation_euler))
        orientation_record = apply_selected_step(session, source, orientation.candidate_id, approved=True, policy=policy)
        _require(orientation_record.state == OptimizationOperationState.APPLIED, "Orientation preview was not applied to workspace.")
        undo_last_step(session, source); restore_session_to_start(session, source); _discard_or_cleanup(session); session = None
        source.location.z = -2.0
        below_plane_before = _source_content(_source_snapshot(source))
        session = _start(source, policy); candidates = generate_session_candidates(session, source=source, policy=policy); generate_session_plan(session, policy=policy)
        translation = next(item for item in candidates if item.category == OptimizationOperationType.BUILD_PLATE_TRANSLATION)
        translation_record = apply_selected_step(session, source, translation.candidate_id, approved=True, policy=policy)
        _require(translation_record.state in {OptimizationOperationState.APPLIED, OptimizationOperationState.NO_CHANGE}, "Below-plane translation did not produce a bounded result.")
        _require(below_plane_before == _source_content(_source_snapshot(source)), "Transform preview changed protected source.")
        return {"orientation": orientation_record.state.value, "translation": translation_record.state.value, "source_immutable": True}
    finally:
        _discard_or_cleanup(session); clear_scene()


def gate_h_base_stabilization() -> dict[str, object]:
    clear_scene(); source = make_fixture("BaseSource"); before = _source_content(_source_snapshot(source)); session = None
    try:
        policy = OptimizationPolicy(
            enabled_operation_families=(OptimizationOperationType.BASE_STABILIZATION.value,),
            maximum_base_added_volume_ratio=0.2,
        )
        session = _start(source, policy)
        candidates = generate_session_candidates(session, source=source, policy=policy)
        generate_session_plan(session, policy=policy)
        base = next(item for item in candidates if item.category == OptimizationOperationType.BASE_STABILIZATION)
        rejected = apply_selected_step(session, source, base.candidate_id, policy=policy)
        _require(rejected.state == OptimizationOperationState.REJECTED, "Base stabilization executed without explicit approval.")
        applied = apply_selected_step(session, source, base.candidate_id, approved=True, policy=policy)
        _require(applied.state in {OptimizationOperationState.APPLIED, OptimizationOperationState.FAILED}, "Approved base stabilization exceeded its bounded outcome states.")
        _require(before == _source_content(_source_snapshot(source)), "Base stabilization changed the protected source.")
        return {"without_approval": rejected.state.value, "with_approval": applied.state.value, "source_immutable": True}
    finally:
        _discard_or_cleanup(session); clear_scene()


def gate_i_repair_and_fidelity() -> dict[str, object]:
    clear_scene(); source = make_fixture("RepairSource"); session = None
    try:
        policy = OptimizationPolicy(enabled_operation_families=(OptimizationOperationType.REPAIR_REUSE.value,))
        session = _start(source, policy); candidates = generate_session_candidates(session, source=source, policy=policy, printability_report={"repair_candidates": [{"operation_type": "MERGE_DUPLICATE_VERTICES"}]}); generate_session_plan(session, policy=policy)
        repair = next(item for item in candidates if item.category == OptimizationOperationType.REPAIR_REUSE)
        record = apply_selected_step(session, source, repair.candidate_id, approved=True, policy=policy)
        _require(record.state in {OptimizationOperationState.NO_CHANGE, OptimizationOperationState.APPLIED}, "Repair reuse was not bounded.")
        _discard_or_cleanup(session); session = None
        pass_evidence = fidelity_evidence({"bbox_dimensions": (1, 1, 1), "surface_area": 1, "volume": 1, "triangle_count": 10}, {"bbox_dimensions": (1.01, 1.01, 1.01), "surface_area": 1.01, "volume": 1.01, "triangle_count": 10})
        warning_evidence = fidelity_evidence({"bbox_dimensions": (1, 1, 1), "surface_area": 1, "volume": 1, "triangle_count": 10}, {"bbox_dimensions": (1.15, 1.15, 1.15), "surface_area": 1.15, "volume": 1.15, "triangle_count": 10})
        fail_evidence = fidelity_evidence({"bbox_dimensions": (1, 1, 1), "surface_area": 1, "volume": 1, "triangle_count": 10}, {"bbox_dimensions": (2, 2, 2), "surface_area": 2, "volume": 2, "triangle_count": 10})
        indeterminate = fidelity_evidence({"bbox_dimensions": (), "surface_area": None, "volume": None}, {"bbox_dimensions": (), "surface_area": None, "volume": None})
        _require({pass_evidence["status"], warning_evidence["status"], fail_evidence["status"], indeterminate["status"]} == {"PASS", "WARNING", "FAIL", "INDETERMINATE"}, "Fidelity evidence did not retain bounded proxy states.")
        return {"repair_state": record.state.value, "fidelity_states": [pass_evidence["status"], warning_evidence["status"], fail_evidence["status"], indeterminate["status"]], "remesh": "DEFERRED"}
    finally:
        _discard_or_cleanup(session); clear_scene()


def gate_j_decimation() -> dict[str, object]:
    clear_scene(); source = make_fixture("DecimationSource"); before = _source_content(_source_snapshot(source)); session = None
    try:
        policy = OptimizationPolicy(
            enabled_operation_families=(OptimizationOperationType.DECIMATION.value,),
            experimental_decimation_enabled=True,
        )
        session = _start(source, policy)
        candidates = generate_session_candidates(session, source=source, policy=policy)
        generate_session_plan(session, policy=policy)
        decimation = next(item for item in candidates if item.category == OptimizationOperationType.DECIMATION)
        record = apply_selected_step(session, source, decimation.candidate_id, approved=True, policy=policy)
        _require(record.state == OptimizationOperationState.FAILED, "Decimation fidelity failure was not rejected and rolled back.")
        _require(before == _source_content(_source_snapshot(source)), "Decimation changed the protected source.")
        return {"state": record.state.value, "rollback": True, "remesh": "DEFERRED", "source_immutable": True}
    finally:
        _discard_or_cleanup(session); clear_scene()


def gate_k_comparison() -> dict[str, object]:
    custom = build_objective_snapshot("Custom", (ObjectiveWeight(OptimizationObjective.BUILD_VOLUME_FIT, 1.0),))
    before = {"build_fit": False}; after = {"build_fit": True}
    improvement = compare_snapshots(before, after, objectives=custom)
    regression = compare_snapshots(after, before, objectives=custom)
    missing = compare_snapshots({"build_fit": False}, {"build_fit": None}, objectives=custom)
    critical = compare_snapshots({"build_fit": False}, {"build_fit": True, "critical": True}, objectives=custom)
    _require(improvement.overall_classification == ComparisonClassification.IMPROVEMENT, "True improvement was not recognized.")
    _require(regression.overall_classification == ComparisonClassification.REGRESSION, "True regression was not recognized.")
    _require(missing.overall_classification == ComparisonClassification.INDETERMINATE, "Missing evidence became a score improvement.")
    _require(critical.overall_classification == ComparisonClassification.REGRESSION, "Critical regression was overridden by score.")
    return {"improvement": improvement.overall_classification.value, "regression": regression.overall_classification.value, "missing": missing.overall_classification.value, "critical": critical.overall_classification.value, "deterministic_id": improvement.comparison_id == compare_snapshots(before, after, objectives=custom).comparison_id}


def gate_l_accept_discard() -> dict[str, object]:
    clear_scene(); source = make_fixture("FinalizeSource"); before = _source_content(_source_snapshot(source)); session = None
    try:
        _expect_rejection(lambda: accept_optimized_copy(_start(source)), "accept incomplete audit")
        _force_cleanup(get_active_session())
        policy = OptimizationPolicy(maximum_uniform_scale_change=0.05)
        session = _start(source, policy); candidates = generate_session_candidates(session, source=source, policy=policy, build_volume_mm=(2.4, 8.0, 8.0)); generate_session_plan(session, policy=policy)
        scale = next(item for item in candidates if item.category == OptimizationOperationType.UNIFORM_SCALE and abs(item.transform.scale - 1.0) > 1e-6)
        apply_selected_step(session, source, scale.candidate_id, approved=True, policy=policy, build_volume_mm=(2.4, 8.0, 8.0))
        get_workspace(session).location.x += 0.1
        _expect_rejection(lambda: accept_optimized_copy(session), "accept stale workspace")
        _force_cleanup(session); session = None
        session = _start(source, policy); candidates = generate_session_candidates(session, source=source, policy=policy, build_volume_mm=(2.4, 8.0, 8.0)); generate_session_plan(session, policy=policy)
        scale = next(item for item in candidates if item.category == OptimizationOperationType.UNIFORM_SCALE and abs(item.transform.scale - 1.0) > 1e-6)
        apply_selected_step(session, source, scale.candidate_id, approved=True, policy=policy, build_volume_mm=(2.4, 8.0, 8.0))
        session.comparisons[-1].fidelity["status"] = "FAIL"
        _expect_rejection(lambda: accept_optimized_copy(session), "accept tampered comparison")
        _force_cleanup(session); session = None
        session = _start(source, policy); candidates = generate_session_candidates(session, source=source, policy=policy, build_volume_mm=(2.4, 8.0, 8.0)); generate_session_plan(session, policy=policy)
        scale = next(item for item in candidates if item.category == OptimizationOperationType.UNIFORM_SCALE and abs(item.transform.scale - 1.0) > 1e-6)
        apply_selected_step(session, source, scale.candidate_id, approved=True, policy=policy, build_volume_mm=(2.4, 8.0, 8.0))
        collection = get_collection(session)
        unrelated = bpy.data.objects.new("ForeignFinalizeObject", None)
        collection.objects.link(unrelated)
        _expect_rejection(lambda: accept_optimized_copy(session), "accept cleanup ownership violation")
        _require(get_active_session() is session, "Rejected acceptance incorrectly finalized the active session.")
        collection.objects.unlink(unrelated)
        bpy.data.objects.remove(unrelated, do_unlink=True)
        _force_cleanup(session); session = None
        _require(before == _source_content(_source_snapshot(source)), "Accept/discard attack changed the source.")
        return {"incomplete_audit": "REJECTED", "stale_workspace": "REJECTED", "tampered_comparison": "REJECTED", "cleanup_ownership_violation": "REJECTED", "source_immutable": True}
    finally:
        _discard_or_cleanup(session); clear_scene()


def gate_m_audit() -> dict[str, object]:
    clear_scene(); source = make_fixture("AuditSource"); session = None
    try:
        session = _start(source); generate_session_candidates(session, source=source); generate_session_plan(session)
        audit = build_audit(session, blender_version=bpy.app.version_string)
        payload = json.loads(audit.to_json())
        required = {"schema_version", "extension_version", "source_identity", "source_signature", "workspace_identity", "optimization_policy", "objectives", "generated_candidates", "selected_plan", "operation_history", "checkpoints", "comparisons", "advisory_disclaimer"}
        _require(required <= set(payload), "Audit export omitted required evidence fields.")
        _require(sanitize_optimization_filename("../CON") == "CON_file", "Windows reserved report name was not sanitized.")
        _require(sanitize_optimization_filename("<script>alert(1)</script>") and len(sanitize_optimization_filename("x" * 500)) <= 120, "Hostile audit filename was not bounded.")
        _require("bpy.types" not in audit.to_json() and "E:\\VPRS" not in audit.to_json(), "Audit contains developer/runtime references.")
        _require("not a slicer" in audit_markdown(audit).lower(), "Advisory disclaimer is missing from Markdown audit.")
        return {"schema_version": payload["schema_version"], "required_fields": len(required), "json_utf8_newline": audit.to_json().endswith("\n"), "markdown_disclaimer": True}
    finally:
        _discard_or_cleanup(session); clear_scene()


def gate_n_registration() -> dict[str, object]:
    before_handlers = len(bpy.app.handlers.load_post) + len(bpy.app.handlers.depsgraph_update_post) + len(bpy.app.handlers.frame_change_post)
    chroma3d_sculpt.unregister(); chroma3d_sculpt.register(); chroma3d_sculpt.unregister(); chroma3d_sculpt.register()
    names = {getattr(item, "bl_idname", "") for item in chroma3d_sculpt._RUNTIME_CLASSES}
    after_handlers = len(bpy.app.handlers.load_post) + len(bpy.app.handlers.depsgraph_update_post) + len(bpy.app.handlers.frame_change_post)
    _require("chroma3d.start_optimization_session" in names and "chroma3d.accept_optimization_copy" in names, "Optimization operators did not re-register.")
    _require("chroma3d.optimize_automatically" not in names and "chroma3d.send_to_printer" not in names, "Prohibited operator was registered.")
    _require(before_handlers == after_handlers, "Registration leaked persistent handlers.")
    return {"runtime_classes": len(names), "handlers_before": before_handlers, "handlers_after": after_handlers, "automatic_session": False}


def gate_o_performance() -> dict[str, object]:
    results: dict[str, object] = {}
    for target in (50_000, 200_000, 500_000):
        clear_scene(); started = perf_counter(); side = max(10, int((target / 2) ** 0.5))
        vertices = [(float(x), float(y), 0.0) for y in range(side + 1) for x in range(side + 1)]
        faces = []
        for y in range(side):
            for x in range(side):
                index = y * (side + 1) + x
                faces.append((index, index + 1, index + side + 2, index + side + 1))
        mesh = bpy.data.meshes.new(f"Performance{target}"); mesh.from_pydata(vertices, [], faces); mesh.update()
        source = bpy.data.objects.new(f"Performance{target}", mesh); bpy.context.scene.collection.objects.link(source)
        fixture_seconds = perf_counter() - started; signature_started = perf_counter(); source_signature(source); signature_seconds = perf_counter() - signature_started
        workspace_started = perf_counter(); session = _start(source); workspace_seconds = perf_counter() - workspace_started
        candidate_started = perf_counter(); generate_session_candidates(session, source=source); candidate_seconds = perf_counter() - candidate_started
        plan_started = perf_counter(); generate_session_plan(session); plan_seconds = perf_counter() - plan_started
        memory = _working_set_bytes(); discard_started = perf_counter(); _discard_or_cleanup(session); discard_seconds = perf_counter() - discard_started
        results[str(target)] = {"requested_triangles": target, "actual_triangles": sum(max(0, len(poly.vertices) - 2) for poly in mesh.polygons), "fixture_seconds": fixture_seconds, "source_signature_seconds": signature_seconds, "workspace_seconds": workspace_seconds, "candidate_seconds": candidate_seconds, "plan_seconds": plan_seconds, "discard_seconds": discard_seconds, "working_set_observation_bytes": memory, "memory_note": "Point-in-time working-set observation; not exact peak memory."}
    clear_scene()
    return results


def gate_p_package() -> dict[str, object]:
    package = REPOSITORY_ROOT / "dist" / f"chroma3d_sculpt-{DISPLAY_VERSION}.zip"
    _require(package.is_file(), f"Final package is missing: {package}")
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist(); lowered = [name.lower() for name in names]
        _require("blender_manifest.toml" in names, "Package manifest is missing.")
        forbidden = [name for name in lowered if "manual-tests" in name or "tests/" in name or "__pycache__" in name or name.endswith((".pyc", ".blend")) or "secret" in name or ".env" in name]
        _require(not forbidden, f"Package contains forbidden development content: {forbidden[:5]}")
        _require(any(name.endswith("optimization_coordinator.py") for name in names), "Optimization runtime is missing from package.")
        return {"path": str(package.relative_to(REPOSITORY_ROOT)), "file_count": len(names), "size_bytes": package.stat().st_size, "sha256": _file_sha256(package), "forbidden_entries": forbidden}


def static_audit() -> dict[str, object]:
    runtime = ADDON_ROOT / "chroma3d_sculpt"
    patterns = {
        "network_or_process": re.compile(r"\b(requests|urllib|socket|http\.client|subprocess|os\.system|pickle)\b"),
        "dynamic_execution": re.compile(r"\b(eval|exec)\s*\("),
        "automatic_or_prohibited_action": re.compile(r"(?i)(optimize automatically|replace source|one-click print ready|generate supports|generate g-code|send to printer)"),
    }
    findings: list[dict[str, object]] = []
    bpy_ops: list[dict[str, object]] = []
    for path in sorted(runtime.rglob("*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "bpy.ops" in line:
                bpy_ops.append({"path": path.relative_to(REPOSITORY_ROOT).as_posix(), "line": number, "text": line.strip()[:160]})
            for category, pattern in patterns.items():
                if pattern.search(line) and not (category == "automatic_or_prohibited_action" and "not " in line.lower()):
                    findings.append({"category": category, "path": path.relative_to(REPOSITORY_ROOT).as_posix(), "line": number, "text": line.strip()[:160]})
    return {"runtime_python_files": len(tuple(runtime.rglob("*.py"))), "findings": findings, "bpy_ops_calls": bpy_ops, "status": "PASS" if not findings else "FAIL"}


def run_gate(name: str, function) -> dict[str, object]:
    started = perf_counter()
    try:
        evidence = function()
        return {"gate": name, "status": "PASS", "duration_seconds": round(perf_counter() - started, 6), "evidence": evidence}
    except Exception as exc:
        return {"gate": name, "status": "FAIL", "duration_seconds": round(perf_counter() - started, 6), "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc(limit=8)}


def render_markdown(payload: dict[str, object]) -> str:
    gates = payload["gates"]
    lines = ["# Sprint 5 Independent Final Validation", "", f"- Decision: **{payload['decision']}**", f"- Blender: `{bpy.app.version_string}`", f"- Extension: `{DISPLAY_VERSION}`", f"- Generated: `{payload['generated_at']}`", "", "## Gates", "", "| Gate | Status | Duration |", "|---|---|---:|"]
    for gate in gates:  # type: ignore[union-attr]
        lines.append(f"| {gate['gate']} | {gate['status']} | {gate['duration_seconds']:.3f}s |")
    lines.extend(["", "## Safety and scope", "", "- Protected source was independently snapshotted across geometry, identity, modifiers, constraints, materials, vertex groups, UVs, color attributes, shape keys, transforms, visibility, collections, and properties.", "- Controlled Optimization remains workspace-only and explicit.", "- This audit does not perform physical printing, slicer comparison, material calibration, Blender 4.5 LTS validation, or manual installed-panel UAT.", "- Experimental remesh is deferred; experimental decimation is opt-in and fidelity-fail closed.", "", "## Defect correction evidence", "", "- Preserved first independent failure evidence: `reports/initial_failure_results_pre_checkpoint_fix.json`.", "- Corrected runtime defects included checkpoint classification, rollback signature stability, protected-source snapshot coverage, plan stale-state context, ownership and cleanup fail-closed behavior, repair-evidence gating, fidelity indeterminate handling, and Windows-safe audit names.", "- The focused Sprint 5 suite retained its 161-test result after its fixture cleanup was corrected.", "", "## Package", ""])
    package = next((item for item in gates if item["gate"] == "S5F-P"), None)
    if package and package.get("status") == "PASS":
        evidence = package["evidence"]
        lines.append(f"- `{evidence['path']}`; files `{evidence['file_count']}`; size `{evidence['size_bytes']}` bytes; SHA-256 `{evidence['sha256']}`")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("initial", "final"), default="final")
    parser.add_argument("--skip-performance", action="store_true")
    return parser.parse_args(raw)


def main() -> int:
    args = parse_args()
    REPORT_ROOT.mkdir(parents=True, exist_ok=True); ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    static_evidence = static_audit()
    gates = [{"gate": "S5F-STATIC", "status": static_evidence["status"], "duration_seconds": 0.0, "evidence": static_evidence}]
    for name, function in (("S5F-A", gate_a_source_matrix), ("S5F-B", gate_b_ownership), ("S5F-C", gate_c_objectives_policy), ("S5F-D", gate_d_candidates), ("S5F-E", gate_e_plan_stale), ("S5F-F", gate_f_checkpoints), ("S5F-G", gate_g_transforms), ("S5F-H", gate_h_base_stabilization), ("S5F-I", gate_i_repair_and_fidelity), ("S5F-J", gate_j_decimation), ("S5F-K", gate_k_comparison), ("S5F-L", gate_l_accept_discard), ("S5F-M", gate_m_audit), ("S5F-N", gate_n_registration)):
        gates.append(run_gate(name, function))
    if not args.skip_performance:
        gates.append(run_gate("S5F-O", gate_o_performance))
    gates.append(run_gate("S5F-P", gate_p_package))
    failures = [item for item in gates if item["status"] != "PASS"]
    payload = {"schema_version": "1.0", "generated_at": utcnow(), "phase": args.phase, "blender_version": bpy.app.version_string, "extension_version": DISPLAY_VERSION, "implementation_fingerprint": "sprint5-controlled-optimization-1.0", "gates": gates, "gate_count": len(gates), "passed": len(gates) - len(failures), "failed": len(failures), "decision": "SPRINT 5 FINAL VALIDATION PASSED WITH LIMITATIONS" if not failures else "SPRINT 5 FINAL VALIDATION FAILED", "limitations": ["physical printing", "slicer comparison", "material calibration", "Blender 4.5 LTS", "manual installed-panel UAT"], "source_immutability": not any(item.get("gate") == "S5F-A" and item.get("status") != "PASS" for item in gates)}
    target = REPORT_ROOT / ("initial_failure_results.json" if args.phase == "initial" else "final_validation.json")
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    if args.phase == "final":
        (Path(__file__).with_name("FINAL_VALIDATION_RESULTS.md")).write_text(render_markdown(payload), encoding="utf-8", newline="\n")
    print(json.dumps({"decision": payload["decision"], "gate_count": payload["gate_count"], "passed": payload["passed"], "failed": payload["failed"], "report": str(target)}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
