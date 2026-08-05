"""Independent Sprint 4 Blender-native adversarial gates S4F-A through S4F-P."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import ctypes
import html
import json
import math
import os
import re
import sys
import tempfile
from time import perf_counter
import traceback
from unittest.mock import patch
import zipfile
import runpy

import bpy


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ADDON_ROOT = REPOSITORY_ROOT / "blender_addon"
TEST_ROOT = REPOSITORY_ROOT / "tests" / "blender"
REPORT_ROOT = Path(__file__).resolve().parent / "reports"
REPORT_PATH = REPORT_ROOT / "blender_gate_results.json"
INITIAL_FAILURE_PATH = REPORT_ROOT / "initial_failure_results.json"
PACKAGE_PATH = REPOSITORY_ROOT / "dist" / "chroma3d_sculpt-0.5.0-alpha.1.zip"
_METADATA = runpy.run_path(str(ADDON_ROOT / "chroma3d_sculpt" / "metadata.py"))
PACKAGE_PATH = REPOSITORY_ROOT / "dist" / f"chroma3d_sculpt-{_METADATA['DISPLAY_VERSION']}.zip"
if str(ADDON_ROOT) not in sys.path:
    sys.path.insert(0, str(ADDON_ROOT))
if str(TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_ROOT))

import chroma3d_sculpt  # noqa: E402
from chroma3d_sculpt.feature_flags import build_feature_flags  # noqa: E402
from chroma3d_sculpt.metadata import DISPLAY_VERSION, PERFORMANCE_REGISTRY_VERSION  # noqa: E402
from chroma3d_sculpt.models.advanced_preparation_models import RegressionState  # noqa: E402
from chroma3d_sculpt.models.printability_models import PrintabilityMode, PrintabilityStatus, StaleState  # noqa: E402
from chroma3d_sculpt.performance_registry import limit_for, limit_for_size  # noqa: E402
from chroma3d_sculpt.printability_settings import PrintabilitySettings  # noqa: E402
from chroma3d_sculpt.services.advanced_preparation_coordinator import analyze_advanced_preparation  # noqa: E402
from chroma3d_sculpt.services.advanced_preparation_report import (  # noqa: E402
    preparation_markdown,
    sanitize_preparation_filename,
    write_batch_json,
    write_batch_markdown,
    write_preparation_json,
    write_preparation_markdown,
)
from chroma3d_sculpt.services.advanced_preparation_session import preparation_stale_state  # noqa: E402
from chroma3d_sculpt.services.advanced_scale import NO_FEASIBLE_RECOMMENDED_SCALE  # noqa: E402
from chroma3d_sculpt.services.batch_preparation import analyze_preparation_batch  # noqa: E402
from chroma3d_sculpt.services.batch_preparation_session import batch_is_stale, store_batch_result  # noqa: E402
from chroma3d_sculpt.services.bridge_risk import analyze_bridge_risk  # noqa: E402
from chroma3d_sculpt.services.geometry_facts import build_geometry_facts  # noqa: E402
from chroma3d_sculpt.services.hardware_profile_loader import (  # noqa: E402
    build_custom_hardware_profile,
    load_hardware_profile,
    validate_all_hardware_profiles,
)
from chroma3d_sculpt.services.material_profile_loader import (  # noqa: E402
    build_custom_material_profile,
    load_material_profile,
    load_material_profile_data,
    material_profile_directory,
    validate_all_material_profiles,
)
from chroma3d_sculpt.services.printability_baseline import (  # noqa: E402
    baseline_record,
    compare_baseline_manifests,
    compare_records,
    generate_baseline_manifest,
    implementation_fingerprint,
    verify_baseline_manifest,
    write_baseline_manifest,
)
from chroma3d_sculpt.services.process_context import compose_process_context, legacy_profile_for_context  # noqa: E402
from chroma3d_sculpt.services.regression_dashboard import dashboard_html, dashboard_summary, write_dashboard  # noqa: E402
from chroma3d_sculpt.utilities.printability_signatures import (  # noqa: E402
    geometry_signature,
    printability_source_snapshot,
    transform_signature,
)


GATES: list[dict[str, object]] = []
FIXTURES: dict[str, object] = {}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _require(condition: object, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _reject(function, *args, **kwargs) -> str:
    try:
        function(*args, **kwargs)
    except (KeyError, TypeError, ValueError) as exc:
        return f"{type(exc).__name__}: {exc}"
    raise AssertionError(f"Expected {function.__name__} to reject adversarial input.")


def _run_gate(gate_id: str, name: str, function) -> None:
    started = perf_counter()
    try:
        evidence = function()
        GATES.append(
            {
                "gate_id": gate_id,
                "name": name,
                "status": "PASS",
                "duration_seconds": round(perf_counter() - started, 6),
                "evidence": evidence,
            }
        )
    except Exception as exc:  # noqa: BLE001 - the audit must preserve every failure class
        GATES.append(
            {
                "gate_id": gate_id,
                "name": name,
                "status": "FAIL",
                "duration_seconds": round(perf_counter() - started, 6),
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
                "evidence": {},
            }
        )


def _clear_scene() -> None:
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def _activate(obj: bpy.types.Object) -> None:
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _make_boxes(
    name: str,
    boxes: tuple[tuple[tuple[float, float, float], tuple[float, float, float], bool], ...],
) -> bpy.types.Object:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    base_faces = (
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    )
    for center, dimensions, reverse in boxes:
        cx, cy, cz = center
        hx, hy, hz = (value / 2.0 for value in dimensions)
        offset = len(vertices)
        vertices.extend(
            (
                (cx - hx, cy - hy, cz - hz),
                (cx + hx, cy - hy, cz - hz),
                (cx + hx, cy + hy, cz - hz),
                (cx - hx, cy + hy, cz - hz),
                (cx - hx, cy - hy, cz + hz),
                (cx + hx, cy - hy, cz + hz),
                (cx + hx, cy + hy, cz + hz),
                (cx - hx, cy + hy, cz + hz),
            )
        )
        for face in base_faces:
            ordered = tuple(reversed(face)) if reverse else face
            faces.append(tuple(offset + index for index in ordered))
    vertices = [tuple(value / 1000.0 for value in point) for point in vertices]
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _make_open_plane(name: str, *, z: float = 10.0) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(((-0.005, -0.005, z / 1000.0), (0.005, -0.005, z / 1000.0), (0.005, 0.005, z / 1000.0), (-0.005, 0.005, z / 1000.0)), (), ((0, 1, 2, 3),))
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _make_grid(name: str, x_cells: int, y_cells: int) -> bpy.types.Object:
    vertices = [(float(x) * 0.0001, float(y) * 0.0001, 0.0) for y in range(y_cells + 1) for x in range(x_cells + 1)]
    stride = x_cells + 1
    faces = []
    for y in range(y_cells):
        row = y * stride
        for x in range(x_cells):
            a = row + x
            faces.append((a, a + 1, a + stride + 1, a + stride))
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(vertices, (), faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _custom_properties(owner: object) -> dict[str, str]:
    try:
        return {str(key): repr(owner[key]) for key in sorted(owner.keys()) if key != "_RNA_UI"}
    except (AttributeError, ReferenceError, TypeError):
        return {}


def _independent_snapshot(obj: bpy.types.Object) -> dict[str, object]:
    return {
        "source": printability_source_snapshot(obj, bpy.data.filepath),
        "geometry": geometry_signature(obj),
        "transform": transform_signature(obj),
        "winding": tuple(tuple(polygon.vertices) for polygon in obj.data.polygons),
        "modifiers": tuple((item.name, item.type, item.show_viewport, item.show_render) for item in obj.modifiers),
        "materials": tuple(material.name if material else None for material in obj.data.materials),
        "collections": tuple(sorted(collection.name for collection in obj.users_collection)),
        "object_properties": _custom_properties(obj),
        "mesh_properties": _custom_properties(obj.data),
        "visibility": (obj.hide_get(), obj.hide_viewport, obj.hide_render),
    }


def _working_set_bytes() -> int | None:
    if os.name != "nt":
        return None

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    if not ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
        return None
    return int(counters.WorkingSetSize)


def _setup_fixtures() -> None:
    _clear_scene()
    hardware = load_hardware_profile("bambu_x1_carbon")
    material = load_material_profile("generic_pla")
    process = compose_process_context(
        hardware,
        material,
        nozzle_mm=0.4,
        layer_height_mm=0.2,
        build_plate_type="TEXTURED",
    )
    flags = build_feature_flags()
    settings = PrintabilitySettings(mode=PrintabilityMode.FAST)
    cube = _make_boxes("FinalCube", (((0.0, 0.0, 5.0), (10.0, 10.0, 10.0), False),))
    thin = _make_boxes("FinalThin", (((0.0, 0.0, 5.0), (0.4, 0.4, 10.0), False),))
    oversize = _make_boxes("FinalOversize", (((0.0, 0.0, 20.0), (300.0, 0.4, 40.0), False),))
    floating = _make_boxes(
        "FinalFloating",
        (
            ((0.0, 0.0, 5.0), (10.0, 10.0, 10.0), False),
            ((20.0, 0.0, 22.5), (5.0, 5.0, 5.0), False),
        ),
    )
    bridge = _make_boxes(
        "FinalBridge",
        (
            ((-8.0, 0.0, 5.0), (4.0, 8.0, 10.0), False),
            ((8.0, 0.0, 5.0), (4.0, 8.0, 10.0), False),
            ((0.0, 0.0, 11.0), (20.0, 6.0, 2.0), False),
        ),
    )
    cantilever = _make_boxes(
        "FinalCantilever",
        (
            ((-8.0, 0.0, 5.0), (4.0, 8.0, 10.0), False),
            ((0.0, 0.0, 11.0), (20.0, 6.0, 2.0), False),
        ),
    )
    open_shell = _make_open_plane("FinalOpenShell")
    hollow = _make_boxes(
        "FinalHollow",
        (
            ((0.0, 0.0, 10.0), (20.0, 20.0, 20.0), False),
            ((0.0, 0.0, 10.0), (16.0, 16.0, 16.0), True),
        ),
    )
    cube_result = analyze_advanced_preparation(cube, bpy.context.scene, hardware, material, process, flags, settings)
    FIXTURES.update(locals())


def _geometry_context(obj: bpy.types.Object, process=None, settings=None):
    active_process = process or FIXTURES["process"]
    active_settings = settings or FIXTURES["settings"]
    return build_geometry_facts(obj, bpy.context.scene, active_settings.resolved(legacy_profile_for_context(active_process)))


def _gate_a() -> dict[str, object]:
    cube = FIXTURES["cube"]
    hardware = FIXTURES["hardware"]
    material = FIXTURES["material"]
    process = FIXTURES["process"]
    flags = FIXTURES["flags"]
    before = _independent_snapshot(cube)
    mode_results = {}
    with tempfile.TemporaryDirectory(prefix="chroma3d-s4f-a-") as directory:
        root = Path(directory)
        for mode in PrintabilityMode:
            result = analyze_advanced_preparation(
                cube,
                bpy.context.scene,
                hardware,
                material,
                process,
                flags,
                PrintabilitySettings(mode=mode),
            )
            mode_results[mode.value] = result.status.value
        result = analyze_advanced_preparation(cube, bpy.context.scene, hardware, material, process, flags, FIXTURES["settings"])
        write_preparation_json(result, root / "object.json")
        write_preparation_markdown(result, root / "object.md")
        batch = analyze_preparation_batch(
            [cube, FIXTURES["floating"]],
            bpy.context.scene,
            hardware,
            material,
            process,
            flags,
            FIXTURES["settings"],
        )
        write_batch_json(batch, root / "batch.json")
        write_batch_markdown(batch, root / "batch.md")
        records = (
            baseline_record("cube", "a" * 64, result),
            baseline_record("floating", "b" * 64, analyze_advanced_preparation(FIXTURES["floating"], bpy.context.scene, hardware, material, process, flags, FIXTURES["settings"])),
        )
        baseline = generate_baseline_manifest(
            records,
            process,
            flags,
            blender_version=bpy.app.version_string,
            dataset_manifest_sha256="c" * 64,
            golden_manifest_sha256="d" * 64,
            generated_at="2026-08-05T00:00:00Z",
        )
        write_baseline_manifest(baseline, root / "baseline.json")
        comparisons = compare_baseline_manifests(baseline, deepcopy(baseline))
        page = dashboard_html(
            comparisons,
            software_version=DISPLAY_VERSION,
            dataset_version="1.0.0",
            baseline_version="1.0.0",
            profile_context=process.context_hash,
            generated_at="fixed",
            evidence_links=("baseline.json",),
            model_records=tuple(baseline["records"]),
        )
        write_dashboard(page, root / "dashboard.html")
        _require(len(list(root.iterdir())) == 6, "Explicit local export set is incomplete.")
    _require(before == _independent_snapshot(cube), "Analysis/export/batch/baseline/dashboard changed protected source state.")

    _activate(cube)
    state = bpy.context.window_manager.chroma3d_sculpt_state
    state.printability_profile = "bambu_x1_carbon"
    state.printability_mode = "FAST"
    _require(bpy.ops.chroma3d.analyze_printability() == {"FINISHED"}, "Printability analysis operator failed.")
    source_before_selection = _independent_snapshot(cube)
    selection_result = bpy.ops.chroma3d.select_printability_issue(evidence_category="BUILD_CONTACT")
    _require(selection_result in ({"FINISHED"}, {"CANCELLED"}), "Issue-selection operator returned an invalid state.")
    if cube.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    _require(source_before_selection == _independent_snapshot(cube), "Issue selection changed protected source data.")
    return {"modes": mode_results, "selection_result": sorted(selection_result), "source_immutable": True}


def _gate_b() -> dict[str, object]:
    import chroma3d_sculpt.services.material_profile_loader as loader

    base = json.loads((material_profile_directory() / "generic_pla.json").read_text(encoding="utf-8"))
    attacks = {}
    mutations = {
        "boolean_number": ("wall_thickness_multiplier", True),
        "nan": ("thin_feature_multiplier", float("nan")),
        "infinity": ("bridge_risk_modifier", float("inf")),
        "negative": ("overhang_risk_modifier", -1.0),
        "zero": ("wall_thickness_multiplier", 0.0),
        "invalid_source": ("source_classification", "MANUFACTURER_SPECIFIC"),
    }
    for name, (field, value) in mutations.items():
        payload = deepcopy(base)
        payload[field] = value
        attacks[name] = _reject(load_material_profile_data, payload)
    payload = deepcopy(base)
    payload["nozzle_range_mm"] = [1.0, 0.2]
    attacks["reversed_range"] = _reject(load_material_profile_data, payload)
    payload = deepcopy(base)
    payload["source_references"] = ["SRC-001", "SRC-001"]
    attacks["duplicate_provenance"] = _reject(load_material_profile_data, payload)
    payload = deepcopy(base)
    payload["unexpected"] = "closed"
    attacks["unknown_field"] = _reject(load_material_profile_data, payload)
    payload = deepcopy(base)
    payload["profile_id"] = "wrong_profile"
    with tempfile.TemporaryDirectory(prefix="chroma3d-profile-") as directory:
        path = Path(directory) / "generic_pla.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with patch.object(loader, "material_profile_directory", return_value=Path(directory)):
            attacks["file_id_mismatch"] = _reject(loader.load_material_profile, "generic_pla")
    attacks["hardware_boolean"] = _reject(build_custom_hardware_profile, {"build_volume_mm": [True, 200.0, 200.0]})
    attacks["cross_process"] = _reject(
        compose_process_context,
        FIXTURES["hardware"],
        load_material_profile("generic_resin_material"),
        nozzle_mm=0.4,
        layer_height_mm=0.2,
        build_plate_type="TEXTURED",
    )
    hardware = validate_all_hardware_profiles()
    material = validate_all_material_profiles()
    _require(len({item.profile_id for item in hardware}) == len(hardware), "Duplicate hardware IDs accepted.")
    _require(len({item.profile_id for item in material}) == len(material), "Duplicate material IDs accepted.")
    return {"attacks_rejected": attacks, "hardware_profiles": len(hardware), "material_profiles": len(material)}


def _gate_c() -> dict[str, object]:
    hardware = FIXTURES["hardware"]
    material = FIXTURES["material"]
    process = FIXTURES["process"]
    duplicate = compose_process_context(hardware, material, nozzle_mm=0.4, layer_height_mm=0.2, build_plate_type="TEXTURED")
    _require(process.to_dict() == duplicate.to_dict(), "Process composition is not deterministic.")
    overridden = compose_process_context(
        hardware,
        material,
        nozzle_mm=0.4,
        layer_height_mm=0.2,
        build_plate_type="TEXTURED",
        support_policy="ASSUME_UNSUPPORTED",
        user_overrides={"wall_thickness_warning_mm": 1.3},
    )
    _require(overridden.threshold_provenance["wall_thickness_warning_mm"]["origin"] == "USER_OVERRIDE", "Override provenance was lost.")
    _require(overridden.support_policy == "ASSUME_UNSUPPORTED", "Support-policy snapshot was lost.")
    _reject(compose_process_context, hardware, material, nozzle_mm=True, layer_height_mm=0.2, build_plate_type="TEXTURED")
    _reject(compose_process_context, hardware, material, nozzle_mm=0.3, layer_height_mm=0.2, build_plate_type="TEXTURED")
    _reject(compose_process_context, hardware, material, nozzle_mm=0.4, layer_height_mm=9.0, build_plate_type="TEXTURED")
    _reject(build_feature_flags, {"resin_advisory": True})
    return {
        "context_hash": process.context_hash,
        "deterministic": True,
        "override_hash_changed": overridden.context_hash != process.context_hash,
        "build_plate": process.build_plate_type,
    }


def _gate_d() -> dict[str, object]:
    process = FIXTURES["process"]
    mode = PrintabilityMode.FAST
    bridge_context = _geometry_context(FIXTURES["bridge"])
    bridge = analyze_bridge_risk(bridge_context, process, mode)
    again = analyze_bridge_risk(bridge_context, process, mode)
    cantilever = analyze_bridge_risk(_geometry_context(FIXTURES["cantilever"]), process, mode)
    cube = analyze_bridge_risk(_geometry_context(FIXTURES["cube"]), process, mode)
    open_shell = analyze_bridge_risk(_geometry_context(FIXTURES["open_shell"]), process, mode)
    angled = analyze_bridge_risk(bridge_context, process, mode, (0.0, 0.2, 1.0))
    _require(bridge.candidate_region_count > 0, "Two-sided bridge fixture was not detected.")
    _require(all(item.supporting_side_count == 2 for item in bridge.regions), "Bridge supporting-side count is untruthful.")
    _require(cantilever.candidate_region_count == 0, "One-sided cantilever was mislabeled as a bridge.")
    _require(cube.candidate_region_count == 0, "Build-plate-supported generic overhang was mislabeled as a bridge.")
    _require(len(bridge.evidence_faces) <= limit_for(mode, bridge_context.facts.triangle_count, "bridge_risk").maximum_region_evidence, "Bridge evidence is unbounded.")
    normalized = lambda result: [item.to_dict() | {"duration_seconds": 0.0} for item in result.regions]
    _require(normalized(bridge) == normalized(again), "Bridge analysis is not idempotent.")
    _require(open_shell.status != PrintabilityStatus.FAILED and angled.status != PrintabilityStatus.FAILED, "Adversarial bridge geometry caused failure.")
    _require("guarantee" not in " ".join(bridge.limitations).lower(), "Bridge result makes a success guarantee.")
    return {"bridge_regions": bridge.candidate_region_count, "cantilever_regions": cantilever.candidate_region_count, "bounded": True}


def _gate_e() -> dict[str, object]:
    floating = analyze_advanced_preparation(
        FIXTURES["floating"], bpy.context.scene, FIXTURES["hardware"], FIXTURES["material"], FIXTURES["process"], FIXTURES["flags"], FIXTURES["settings"]
    ).support_risk
    bridge = analyze_advanced_preparation(
        FIXTURES["bridge"], bpy.context.scene, FIXTURES["hardware"], FIXTURES["material"], FIXTURES["process"], FIXTURES["flags"], FIXTURES["settings"]
    ).support_risk
    disabled = analyze_advanced_preparation(
        FIXTURES["cube"],
        bpy.context.scene,
        FIXTURES["hardware"],
        FIXTURES["material"],
        FIXTURES["process"],
        build_feature_flags({"support_risk": False}),
        FIXTURES["settings"],
    ).support_risk
    identifiers = [item.region_id for item in floating.regions]
    _require(len(identifiers) == len(set(identifiers)), "Support-risk regions are duplicated.")
    _require(0.0 <= floating.total_risk_area_percent <= 100.0, "Support-risk percentage is outside 0-100.")
    _require(floating.total_risk_area_mm2 >= 0.0, "Support-risk area is negative.")
    _require(disabled.status == PrintabilityStatus.NOT_EVALUATED, "Disabled support risk silently evaluated.")
    wording = " ".join(item.message for item in floating.regions).lower()
    _require("supports required" not in wording, "Support wording makes a definitive supports-required claim.")
    _require(any("BRIDGE" in [reason.value for reason in item.reason_categories] for item in bridge.regions), "Bridge support reason was lost.")
    return {"regions": floating.region_count, "area_percent": floating.total_risk_area_percent, "disabled": disabled.status.value}


def _gate_f() -> dict[str, object]:
    resin_hardware = load_hardware_profile("generic_resin")
    resin_material = load_material_profile("generic_resin_material")
    resin_process = compose_process_context(
        resin_hardware,
        resin_material,
        nozzle_mm=0.05,
        layer_height_mm=0.05,
        build_plate_type="RESIN_PLATFORM",
    )
    resin_flags = build_feature_flags({"resin_advisory": True}, allow_experimental=True)
    closed = analyze_advanced_preparation(FIXTURES["hollow"], bpy.context.scene, resin_hardware, resin_material, resin_process, resin_flags, FIXTURES["settings"])
    opened = analyze_advanced_preparation(FIXTURES["open_shell"], bpy.context.scene, resin_hardware, resin_material, resin_process, resin_flags, FIXTURES["settings"])
    fdm = FIXTURES["cube_result"].resin_advisory
    _require(fdm.status == PrintabilityStatus.NOT_EVALUATED, "FDM resin-disabled state was evaluated.")
    _require(all(item.get("classification") == "EXPERIMENTAL" for item in closed.resin_advisory.checks.values()), "Resin checks lost experimental labeling.")
    _require(any(item.get("state") in {"NOT_EVALUATED", "INDETERMINATE"} for item in opened.resin_advisory.checks.values()) or opened.resin_advisory.confidence.value == "LOW", "Insufficient resin evidence was overclaimed.")
    text = (" ".join(closed.resin_advisory.limitations) + json.dumps(closed.resin_advisory.to_dict())).lower()
    for phrase in ("suction force", "drainage guarantee", "hollowing performed", "drain hole created", "resin support generated"):
        _require(phrase not in text, f"Resin advisory overclaim present: {phrase}")
    _require("suction" in text and "peel-force" in text and "not" in text, "Resin limitations do not explicitly disclaim force simulation.")
    return {"closed": closed.resin_advisory.status.value, "open": opened.resin_advisory.status.value, "fdm": fdm.status.value}


def _gate_g() -> dict[str, object]:
    thin = analyze_advanced_preparation(FIXTURES["thin"], bpy.context.scene, FIXTURES["hardware"], FIXTURES["material"], FIXTURES["process"], FIXTURES["flags"], FIXTURES["settings"]).scale_recommendation
    oversize = analyze_advanced_preparation(FIXTURES["oversize"], bpy.context.scene, FIXTURES["hardware"], FIXTURES["material"], FIXTURES["process"], FIXTURES["flags"], FIXTURES["settings"]).scale_recommendation
    nozzle_process = compose_process_context(FIXTURES["hardware"], FIXTURES["material"], nozzle_mm=0.6, layer_height_mm=0.2, build_plate_type="TEXTURED")
    nozzle = analyze_advanced_preparation(FIXTURES["thin"], bpy.context.scene, FIXTURES["hardware"], FIXTURES["material"], nozzle_process, FIXTURES["flags"], FIXTURES["settings"]).scale_recommendation
    _require(oversize.recommended_interval.state == NO_FEASIBLE_RECOMMENDED_SCALE, "Infeasible scale interval was hidden or clamped.")
    _require(thin.minimum_wall_preserving_scale_percent is not None and thin.minimum_feature_preserving_scale_percent is not None, "Wall/feature scale bounds are missing.")
    _require(nozzle.to_dict() != thin.to_dict(), "Nozzle change did not affect scale mathematics.")
    _require(transform_signature(FIXTURES["oversize"]) == FIXTURES["oversize_result"].transform_signature if "oversize_result" in FIXTURES else True, "Scale recommendation changed the object transform.")
    return {"thin_interval": thin.recommended_interval.to_dict(), "oversize_interval": oversize.recommended_interval.to_dict()}


def _gate_h() -> dict[str, object]:
    result = FIXTURES["cube_result"].orientation_comparison
    candidates = result.candidates
    identifiers = [item["candidate_id"] for item in candidates]
    ranks = [item["deterministic_rank"] for item in candidates]
    strategies = {strategy for item in candidates for strategy in item["strategies"]}
    _require(identifiers and len(identifiers) == len(set(identifiers)), "Orientation candidates are missing or duplicated.")
    _require(ranks == list(range(1, len(ranks) + 1)), "Orientation ordering is not deterministic.")
    _require(set(result.pareto_candidate_ids) <= set(identifiers), "Pareto set references an unknown candidate.")
    for strategy in ("current_orientation", "contact_maximizing", "bridge_risk_minimizing", "support_risk_minimizing", "height_minimizing"):
        _require(strategy in strategies, f"Orientation strategy missing: {strategy}")
    _require(any("not" in item.lower() and "optimal" in item.lower() for item in result.limitations), "Orientation result implies global optimality.")
    return {"candidate_count": len(candidates), "pareto_count": len(result.pareto_candidate_ids), "strategies": sorted(strategies)}


def _gate_i() -> dict[str, object]:
    cube = FIXTURES["cube"]
    result = FIXTURES["cube_result"]
    kwargs = dict(
        scene=bpy.context.scene,
        hardware=FIXTURES["hardware"],
        material=FIXTURES["material"],
        process=FIXTURES["process"],
        flags=FIXTURES["flags"],
        settings=FIXTURES["settings"],
    )
    one = analyze_preparation_batch([cube], resume_results={cube.name: result}, **kwargs)
    _require(one.object_results[0]["resumed"] is True, "Current batch result did not resume.")
    original = cube.data.vertices[0].co.copy()
    try:
        cube.data.vertices[0].co.x += 0.125
        cube.data.update()
        changed = analyze_preparation_batch([cube], resume_results={cube.name: result}, **kwargs)
        _require(changed.object_results[0]["resumed"] is False, "Batch resumed stale source evidence after geometry mutation.")
    finally:
        cube.data.vertices[0].co = original
        cube.data.update()
    replacement_source = _make_boxes("DeletedResume", (((0.0, 0.0, 5.0), (8.0, 8.0, 8.0), False),))
    previous = analyze_advanced_preparation(replacement_source, **kwargs)
    name = replacement_source.name
    bpy.data.objects.remove(replacement_source, do_unlink=True)
    replacement = _make_boxes(name, (((0.0, 0.0, 5.0), (9.0, 9.0, 9.0), False),))
    replaced = analyze_preparation_batch([replacement], resume_results={name: previous}, **kwargs)
    _require(replaced.object_results[0]["resumed"] is False, "Batch resumed a deleted object's stale result.")
    partial = analyze_preparation_batch([cube, object()], resume_results={cube.name: result}, **kwargs)
    cancelled = analyze_preparation_batch([cube], cancelled=lambda: True, **kwargs)
    empty = analyze_preparation_batch([], **kwargs)
    limit = limit_for_size("FAST", "Medium", "batch_analysis").maximum_batch_size
    excessive = analyze_preparation_batch([cube] * (limit + 1), **kwargs)
    _require(partial.failed_count == 1 and partial.completed_count == 1, "Partial batch failure was not isolated.")
    _require(cancelled.state.value == "CANCELLED", "Batch cancellation state is untruthful.")
    _require(empty.state.value == "FAILED" and excessive.state.value == "FAILED", "Empty/limit batch did not fail closed.")
    store_batch_result(one)
    _require(batch_is_stale([cube], FIXTURES["process"], FIXTURES["flags"]) is False, "Current stored batch is stale.")
    return {"current_resume": True, "stale_resume": False, "partial_failures": partial.failed_count, "batch_limit": limit}


def _gate_j() -> dict[str, object]:
    baseline_path = REPOSITORY_ROOT / "benchmarks" / "printability" / "baseline_manifest.json"
    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    verify_baseline_manifest(payload)
    records = payload["records"]
    identifiers = [item["model_id"] for item in records]
    dataset = json.loads((REPOSITORY_ROOT / "datasets" / "statues" / "manifests" / "statue_dataset_manifest.json").read_text(encoding="utf-8"))
    source_hashes = {item["unique_id"]: item["checksum_sha256"] for item in dataset["assets"]}
    _require(len(records) == 27 and len(set(identifiers)) == 27, "Canonical baseline is not 27 unique records.")
    _require(all(source_hashes.get(item["model_id"]) == item["source_sha256"] for item in records), "Canonical source SHA mismatch.")
    _require(payload["software"]["implementation_fingerprint"] == implementation_fingerprint(), "Canonical implementation fingerprint is stale.")
    context_hash = payload["process_context"]["context_hash"]
    flag_hash = payload["feature_flags"]["flag_hash"]
    _require(all(item["process_context_hash"] == context_hash for item in records), "Baseline record context hash mismatch.")
    _require(all(item["feature_flags"]["flag_hash"] == flag_hash for item in records), "Baseline record feature hash mismatch.")
    adversarial = deepcopy(payload)
    adversarial["records"][0]["process_context_hash"] = "0" * 64
    _reject(verify_baseline_manifest, adversarial)
    adversarial = deepcopy(payload)
    adversarial["records"][0]["feature_flags"]["flag_hash"] = "0" * 64
    _reject(verify_baseline_manifest, adversarial)
    return {"records": len(records), "implementation_fingerprint": implementation_fingerprint(), "context_hash": context_hash, "feature_hash": flag_hash}


def _gate_k() -> dict[str, object]:
    baseline = deepcopy(FIXTURES["baseline"]) if "baseline" in FIXTURES else generate_baseline_manifest(
        (baseline_record("cube", "a" * 64, FIXTURES["cube_result"]),),
        FIXTURES["process"],
        FIXTURES["flags"],
        blender_version=bpy.app.version_string,
        dataset_manifest_sha256="b" * 64,
        golden_manifest_sha256="c" * 64,
        generated_at="fixed",
    )
    record = deepcopy(baseline["records"][0])
    exact = compare_records(record, deepcopy(record))
    numeric = deepcopy(record)
    numeric["support_risk_areas"]["area_mm2"] += max(0.1, abs(float(record["support_risk_areas"]["area_mm2"])) * 0.1)
    warning = compare_records(record, numeric)
    failed = deepcopy(record)
    failed["per_check_states"]["bridge_risk"] = "FAILED"
    failure = compare_records(record, failed)
    removed = deepcopy(failed)
    removed["per_check_states"]["bridge_risk"] = "PASS"
    review = compare_records(failed, removed)
    context = deepcopy(record)
    context["process_context_hash"] = "0" * 64
    context_failure = compare_records(record, context)
    skipped = deepcopy(record)
    skipped["per_check_states"]["bridge_risk"] = "SKIPPED_LIMIT"
    skipped_failure = compare_records(record, skipped)
    mismatch = deepcopy(baseline)
    mismatch["baseline_version"] = "9.0.0"
    _reject(compare_baseline_manifests, baseline, mismatch)
    states = (exact.state, warning.state, failure.state, review.state)
    _require(states == (RegressionState.PASS, RegressionState.WARNING, RegressionState.FAIL, RegressionState.REVIEW_REQUIRED), "Comparator classifications are incomplete or untruthful.")
    _require(context_failure.state == RegressionState.FAIL and skipped_failure.state == RegressionState.FAIL, "Context/skipped regression was ignored.")
    return {"classifications": [item.value for item in states], "version_mismatch": "REJECTED", "context_mismatch": context_failure.state.value}


def _gate_l() -> dict[str, object]:
    hostile_name = '<script>alert("x")</script>/..\\CON:Î»' + "z" * 300
    comparison = replace(
        compare_baseline_manifests(
            generate_baseline_manifest(
                (baseline_record("safe", "a" * 64, FIXTURES["cube_result"]),),
                FIXTURES["process"],
                FIXTURES["flags"],
                blender_version=bpy.app.version_string,
                dataset_manifest_sha256="b" * 64,
                golden_manifest_sha256="c" * 64,
                generated_at="fixed",
            ),
            generate_baseline_manifest(
                (baseline_record("safe", "a" * 64, FIXTURES["cube_result"]),),
                FIXTURES["process"],
                FIXTURES["flags"],
                blender_version=bpy.app.version_string,
                dataset_manifest_sha256="b" * 64,
                golden_manifest_sha256="c" * 64,
                generated_at="fixed",
            ),
        )[0],
        model_id=hostile_name,
        summary="<img src=x onerror=alert(1)>",
    )
    kwargs = dict(
        software_version="<version>",
        dataset_version="1.0.0",
        baseline_version="1.0.0",
        profile_context="C:\\developer\\checkout",
        generated_at="fixed",
        evidence_links=("baseline.json", "../escape.json", "https://example.invalid/x", "javascript:alert(1)"),
    )
    page = dashboard_html((comparison,), **kwargs)
    _require("<script>alert" not in page and "<img src=x" not in page, "Dashboard did not escape hostile evidence.")
    _require("https://example.invalid" not in page and "javascript:" not in page, "Dashboard retained a remote or executable evidence link.")
    _require('href="../escape.json"' not in page, "Dashboard retained a traversal evidence link.")
    _require("C:\\developer\\checkout" not in page, "Dashboard exposed an absolute developer path.")
    _require(page == dashboard_html((comparison,), **kwargs), "Dashboard output is not deterministic.")
    _require("cdn" not in page.lower() and "@import" not in page.lower(), "Dashboard has an external dependency.")
    _require("No raw mesh payload" in page, "Dashboard raw-payload limitation is absent.")
    filename = sanitize_preparation_filename(hostile_name, "json")
    _require("/" not in filename and "\\" not in filename and len(filename) <= 160, "Report filename sanitizer is unsafe or unbounded.")
    return {"escaped": True, "local_links_only": True, "filename": filename, "bytes": len(page.encode("utf-8"))}


def _gate_m() -> dict[str, object]:
    obj = _make_boxes("FinalStale", (((0.0, 0.0, 5.0), (10.0, 10.0, 10.0), False),))
    hardware = FIXTURES["hardware"]
    material = FIXTURES["material"]
    process = FIXTURES["process"]
    flags = FIXTURES["flags"]
    settings = FIXTURES["settings"]
    result = analyze_advanced_preparation(obj, bpy.context.scene, hardware, material, process, flags, settings)
    checks = {}
    checks["hardware"] = preparation_stale_state(obj, result, load_hardware_profile("bambu_p1s"), material, process, flags, settings)
    checks["material"] = preparation_stale_state(obj, result, hardware, load_material_profile("generic_petg"), process, flags, settings)
    for name, kwargs in {
        "nozzle": {"nozzle_mm": 0.6, "layer_height_mm": 0.2, "build_plate_type": "TEXTURED"},
        "layer": {"nozzle_mm": 0.4, "layer_height_mm": 0.3, "build_plate_type": "TEXTURED"},
        "plate": {"nozzle_mm": 0.4, "layer_height_mm": 0.2, "build_plate_type": "SMOOTH"},
        "support_policy": {"nozzle_mm": 0.4, "layer_height_mm": 0.2, "build_plate_type": "TEXTURED", "support_policy": "ASSUME_SUPPORTED"},
    }.items():
        changed = compose_process_context(hardware, material, **kwargs)
        checks[name] = preparation_stale_state(obj, result, hardware, material, changed, flags, settings)
    checks["flags"] = preparation_stale_state(obj, result, hardware, material, process, build_feature_flags({"bridge_risk": False}), settings)
    checks["performance"] = preparation_stale_state(obj, replace(result, performance_registry_version="stale"), hardware, material, process, flags, settings)
    changed_settings = PrintabilitySettings(mode=PrintabilityMode.FAST, build_direction=(0.0, 1.0, 0.0))
    checks["build_direction"] = preparation_stale_state(obj, result, hardware, material, process, flags, changed_settings)
    original_location = obj.location.copy()
    obj.location.x += 0.1
    checks["transform"] = preparation_stale_state(obj, result, hardware, material, process, flags, settings)
    obj.location = original_location
    original_vertex = obj.data.vertices[0].co.copy()
    obj.data.vertices[0].co.x += 0.1
    obj.data.update()
    checks["geometry"] = preparation_stale_state(obj, result, hardware, material, process, flags, settings)
    obj.data.vertices[0].co = original_vertex
    obj.data.update()
    original_mesh = obj.data
    obj.data = original_mesh.copy()
    checks["mesh_identity"] = preparation_stale_state(obj, result, hardware, material, process, flags, settings)
    obj.data = original_mesh
    bpy.data.meshes.remove(next(mesh for mesh in bpy.data.meshes if mesh.name.startswith(original_mesh.name) and mesh != original_mesh), do_unlink=True)
    _require(all(value != StaleState.CURRENT for value in checks.values()), f"Stale attack was accepted: {checks}")
    baseline = generate_baseline_manifest(
        (baseline_record("stale", "a" * 64, result),), process, flags,
        blender_version=bpy.app.version_string, dataset_manifest_sha256="b" * 64, golden_manifest_sha256="c" * 64, generated_at="fixed",
    )
    changed_baseline = deepcopy(baseline)
    changed_baseline["baseline_version"] = "0.0.0"
    _reject(compare_baseline_manifests, baseline, changed_baseline)
    return {name: state.value for name, state in checks.items()} | {"baseline_identity": "REJECTED"}


def _gate_n() -> dict[str, object]:
    chroma3d_sculpt.unregister()
    first_clean = not hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state") and not hasattr(bpy.types, "CHROMA3D_PT_advanced_preparation")
    chroma3d_sculpt.register()
    registered = hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state") and hasattr(bpy.types, "CHROMA3D_PT_advanced_preparation")
    chroma3d_sculpt.unregister()
    final_clean = not hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state") and not hasattr(bpy.types, "CHROMA3D_PT_advanced_preparation")
    chroma3d_sculpt.register()
    _require(first_clean and registered and final_clean, "Register/unregister/re-register leaked Blender properties or panels.")
    return {"first_unregister_clean": first_clean, "registered": registered, "final_unregister_clean": final_clean, "installed_package": "WRAPPER_PENDING"}


def _gate_o() -> dict[str, object]:
    fixtures = (("50k", 250, 100), ("200k", 500, 200), ("500k", 500, 500))
    observations = []
    for label, x_cells, y_cells in fixtures:
        generated = perf_counter()
        obj = _make_grid(f"Perf{label}", x_cells, y_cells)
        generation_seconds = perf_counter() - generated
        triangles = sum(max(0, len(face.vertices) - 2) for face in obj.data.polygons)
        source_before = printability_source_snapshot(obj)
        memory_before = _working_set_bytes()
        started = perf_counter()
        result = analyze_advanced_preparation(
            obj, bpy.context.scene, FIXTURES["hardware"], FIXTURES["material"], FIXTURES["process"], FIXTURES["flags"], FIXTURES["settings"]
        )
        wall_seconds = perf_counter() - started
        memory_after = _working_set_bytes()
        _require(printability_source_snapshot(obj)["printability_sha256"] == source_before["printability_sha256"], f"{label} performance fixture source changed.")
        observations.append(
            {
                "fixture": label,
                "triangles": triangles,
                "fixture_generation_seconds": round(generation_seconds, 6),
                "analysis_wall_seconds": round(wall_seconds, 6),
                "per_check_timings": result.timings,
                "working_set_before_bytes": memory_before,
                "working_set_after_bytes": memory_after,
                "memory_label": "point working-set observations; not exact peak memory",
                "skipped_states": [item for item in result.skipped_checks],
                "source_immutable": True,
            }
        )
        bpy.data.objects.remove(obj, do_unlink=True)
    targets = [50_000, 200_000, 500_000]
    _require(all(item["triangles"] == target for item, target in zip(observations, targets)), "Synthetic triangle targets are incorrect.")
    return {"observations": observations, "limits_unchanged": True}


def _gate_p() -> dict[str, object]:
    _require(PACKAGE_PATH.is_file(), "Sprint 4 package is missing.")
    findings = []
    forbidden_parts = ("tests/", "manual-tests/", "__pycache__/", ".pyc", ".env", "dataset", "dashboard/")
    secret_patterns = (re.compile(r"gh[opsu]_[A-Za-z0-9_]{20,}"), re.compile(r"AKIA[0-9A-Z]{16}"))
    with zipfile.ZipFile(PACKAGE_PATH) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        for name in names:
            lowered = name.lower()
            if any(part in lowered for part in forbidden_parts):
                findings.append(f"forbidden path: {name}")
            if re.search(r"(^|/)[A-Za-z]:[/\\]", name) or name.startswith(("/", "\\")):
                findings.append(f"absolute path: {name}")
            if name.endswith((".py", ".json", ".toml", ".md")):
                source = archive.read(name).decode("utf-8", errors="replace")
                if any(pattern.search(source) for pattern in secret_patterns):
                    findings.append(f"secret-like content: {name}")
        _require("blender_manifest.toml" in names, "Package manifest is missing.")
        _require(any(name.endswith("schemas/material_profile.schema.json") for name in names), "Material schema is missing.")
        _require(any("profiles/materials/generic_pla.json" in name for name in names), "Material profiles are missing.")
    _require(not findings, f"Package audit findings: {findings}")
    return {
        "path": str(PACKAGE_PATH.relative_to(REPOSITORY_ROOT)),
        "file_count": len(names),
        "size_bytes": PACKAGE_PATH.stat().st_size,
        "sha256": sha256(PACKAGE_PATH.read_bytes()).hexdigest(),
        "archive_findings": findings,
        "native_and_repository_validators": "WRAPPER_PENDING",
    }


def main() -> int:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    started = perf_counter()
    started_at = _utcnow()
    try:
        try:
            chroma3d_sculpt.unregister()
        except Exception:
            pass
        chroma3d_sculpt.register()
        _setup_fixtures()
        FIXTURES["oversize_result"] = analyze_advanced_preparation(
            FIXTURES["oversize"], bpy.context.scene, FIXTURES["hardware"], FIXTURES["material"], FIXTURES["process"], FIXTURES["flags"], FIXTURES["settings"]
        )
        FIXTURES["baseline"] = generate_baseline_manifest(
            (baseline_record("cube", "a" * 64, FIXTURES["cube_result"]),),
            FIXTURES["process"], FIXTURES["flags"], blender_version=bpy.app.version_string,
            dataset_manifest_sha256="b" * 64, golden_manifest_sha256="c" * 64, generated_at="fixed",
        )
        for gate_id, name, function in (
            ("S4F-A", "Source and transform immutability", _gate_a),
            ("S4F-B", "Strict hardware/material profile validation", _gate_b),
            ("S4F-C", "Process-context truth", _gate_c),
            ("S4F-D", "Bridge-risk adversarial truth", _gate_d),
            ("S4F-E", "Support-risk adversarial truth", _gate_e),
            ("S4F-F", "Resin advisory truth", _gate_f),
            ("S4F-G", "Scale recommendation mathematics", _gate_g),
            ("S4F-H", "Orientation comparison truth", _gate_h),
            ("S4F-I", "Batch isolation and resumability", _gate_i),
            ("S4F-J", "Baseline integrity", _gate_j),
            ("S4F-K", "Comparator truth", _gate_k),
            ("S4F-L", "HTML dashboard security and truth", _gate_l),
            ("S4F-M", "Stale-state attacks", _gate_m),
            ("S4F-N", "Registration and installed package", _gate_n),
            ("S4F-O", "Performance and limit behavior", _gate_o),
            ("S4F-P", "Packaging and security", _gate_p),
        ):
            _run_gate(gate_id, name, function)
    finally:
        try:
            _clear_scene()
            chroma3d_sculpt.unregister()
        except Exception as exc:  # noqa: BLE001
            GATES.append({"gate_id": "S4F-CLEANUP", "name": "Final cleanup", "status": "FAIL", "error": f"{type(exc).__name__}: {exc}", "evidence": {}})
    passed = sum(item["status"] == "PASS" for item in GATES if str(item["gate_id"]).startswith("S4F-") and item["gate_id"] != "S4F-CLEANUP")
    payload = {
        "schema_version": "1.0",
        "generated_at": _utcnow(),
        "started_at": started_at,
        "blender_version": bpy.app.version_string,
        "extension_version": DISPLAY_VERSION,
        "overall_status": "PASS" if passed == 16 and len(GATES) == 16 else "FAIL",
        "passed_gates": passed,
        "total_gates": 16,
        "duration_seconds": round(perf_counter() - started, 6),
        "gates": GATES,
    }
    _atomic_json(REPORT_PATH, payload)
    if payload["overall_status"] != "PASS" and not INITIAL_FAILURE_PATH.exists():
        _atomic_json(INITIAL_FAILURE_PATH, payload)
    print(f"Sprint 4 independent Blender gates: {payload['overall_status']} ({passed}/16)")
    print(f"Evidence: {REPORT_PATH}")
    return 0 if payload["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
