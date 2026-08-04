from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
from time import perf_counter, process_time
from typing import Any, Callable


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATASET_MANIFEST_PATH = (
    REPOSITORY_ROOT
    / "datasets"
    / "statues"
    / "manifests"
    / "statue_dataset_manifest.json"
)
GOLDEN_ROOT = REPOSITORY_ROOT / "benchmarks" / "golden"
LATEST_REGRESSION_PATH = (
    REPOSITORY_ROOT
    / "manual-tests"
    / "benchmarks"
    / "latest_regression_report.json"
)
VERIFY_SCRIPT = Path(__file__).with_name("verify_golden_baseline.py")
DEFAULT_BLENDER = Path(r"D:\Softwares\Design\Blender\blender.exe")

BENCHMARK_VERSION = "1.0.0"
EXPECTED_DATASET_VERSION = "1.0.0"
EXPECTED_SOFTWARE_VERSION = "0.3.0-alpha.1"

TIMING_CLASS_THRESHOLDS = (
    ("Tiny", 25_000),
    ("Small", 100_000),
    ("Medium", 250_000),
    ("Large", 500_000),
    ("Huge", 1_000_000),
    ("Extreme", None),
)
TIMING_WARNING_RATIO = 1.5
TIMING_WARNING_ABSOLUTE_SECONDS = 1.0
TIMING_FAIL_RATIO = 2.0
TIMING_FAIL_ABSOLUTE_SECONDS = 5.0

REQUIRED_SUBDIRECTORIES = (
    "raw",
    "reports",
    "timings",
    "statistics",
    "comparisons",
    "manifests",
    "thumbnails",
)

VOLATILE_KEYS = {
    "analysis_id",
    "analysis_duration_ms",
    "analyzed_at",
    "candidate_id",
    "captured_active_identity",
    "captured_selected_identities",
    "checkpoint_id",
    "completed_at",
    "created_at",
    "duration_ms",
    "ended_at",
    "exported_at",
    "initial_checkpoint_id",
    "initial_workspace_signature",
    "mesh_datablock_identity",
    "mesh_identity",
    "object_identity",
    "operation_id",
    "plan_id",
    "process_id",
    "protected_sha256",
    "restored_at",
    "session_id",
    "source_mesh_identity",
    "source_object_identity",
    "source_protection_signature",
    "source_signature",
    "started_at",
    "undone_at",
    "workspace_mesh_identity",
    "workspace_object_identity",
    "workspace_signature",
    "final_workspace_signature",
    "current_workspace_signature",
    "current_analysis_id",
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _schema_descriptor(value: Any, path: str = "$") -> list[str]:
    if isinstance(value, dict):
        lines = [f"{path}:object"]
        for key in sorted(value):
            lines.extend(_schema_descriptor(value[key], f"{path}.{key}"))
        return lines
    if isinstance(value, list):
        lines = [f"{path}:array"]
        item_lines: set[str] = set()
        for item in value:
            item_lines.update(_schema_descriptor(item, f"{path}[]"))
        lines.extend(sorted(item_lines))
        return lines
    if value is None:
        value_type = "null"
    elif isinstance(value, bool):
        value_type = "boolean"
    elif isinstance(value, int):
        value_type = "integer"
    elif isinstance(value, float):
        value_type = "number"
    elif isinstance(value, str):
        value_type = "string"
    else:
        value_type = type(value).__name__
    return [f"{path}:{value_type}"]


def _schema_fingerprint(value: Any) -> str:
    return _stable_hash(_schema_descriptor(value))


def _timing_class(triangle_count: int) -> str:
    for label, maximum in TIMING_CLASS_THRESHOLDS:
        if maximum is None or triangle_count < maximum:
            return label
    raise AssertionError("unreachable timing classification")


def _mesh_classifications(asset: dict[str, Any]) -> list[str]:
    category = str(asset.get("category", "")).lower()
    text = " ".join(
        [
            str(asset.get("title", "")),
            str(asset.get("subject", "")),
            str(asset.get("author", "")),
            str(asset.get("original_filename", "")),
            " ".join(str(item) for item in asset.get("notes", [])),
        ]
    ).lower()
    classifications: list[str] = []

    if any(
        marker in text
        for marker in (
            "museum",
            "smithsonian",
            "nationalmuseum",
            "minneapolis institute",
            "scan the world",
        )
    ):
        classifications.append("Museum Scan")
    if any(
        marker in text
        for marker in (
            "photogrammetry",
            "structured-light",
            "laser scan",
            "outdoor sculpture scan",
            "public-sculpture scan",
            "weathered religious stone scan",
            "monument scan",
        )
    ):
        classifications.append("Photogrammetry")
    if "thingiverse" in text:
        classifications.append("Printable STL")
    if int(asset["triangle_count"]) >= 500_000:
        classifications.append("High-detail sculpture")
    if category in {"bust", "head"}:
        classifications.append("Bust")
    if category in {"full_statue", "figure_group", "deity_group"}:
        classifications.append("Full statue")
    if category == "temple_guardian":
        classifications.append("Guardian")
    if category in {
        "monument_reconstruction",
        "ornamental_stone",
        "temple_monument",
        "functional_sculpture",
    }:
        classifications.append("Architectural carving")
    if any(
        marker in text
        for marker in ("lion", "cat", "buffalo", "komainu", "bastet")
    ):
        classifications.append("Animal")
    if category in {
        "bust",
        "deity_group",
        "figure_group",
        "figurine",
        "fragment",
        "full_statue",
        "head",
    } and "bastet" not in text:
        classifications.append("Human")
    if not classifications:
        classifications.append("Other")
    return list(dict.fromkeys(classifications))


def _artifact_paths(root: Path, mesh_id: str) -> dict[str, Path]:
    return {
        "analysis": root / "raw" / f"{mesh_id}_analysis.json",
        "repair_audit": root / "raw" / f"{mesh_id}_repair_audit.json",
        "rollback_audit": root / "raw" / f"{mesh_id}_rollback_audit.json",
        "golden": root / "raw" / f"{mesh_id}_golden.json",
        "comparison": root / "comparisons" / f"{mesh_id}_comparison.json",
        "timings": root / "timings" / f"{mesh_id}_timings.json",
        "report": root / "reports" / f"{mesh_id}_benchmark_report.json",
        "log": root / "reports" / f"{mesh_id}_blender.log",
    }


def _ensure_directories(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_SUBDIRECTORIES:
        (root / name).mkdir(parents=True, exist_ok=True)


def _load_dataset_manifest() -> dict[str, Any]:
    manifest = _read_json(DATASET_MANIFEST_PATH)
    if manifest.get("dataset_version") != EXPECTED_DATASET_VERSION:
        raise RuntimeError(
            f"Dataset version must be {EXPECTED_DATASET_VERSION}, "
            f"found {manifest.get('dataset_version')!r}."
        )
    assets = manifest.get("assets", [])
    if manifest.get("asset_count") != 27 or len(assets) != 27:
        raise RuntimeError("Golden baseline requires exactly 27 manifest assets.")
    if manifest.get("validated_asset_count") != 27:
        raise RuntimeError("All 27 assets must be validated before benchmarking.")
    if manifest.get("validation_rejected_asset_count") != 0:
        raise RuntimeError("Dataset validation failures block golden generation.")
    return manifest


def _asset_by_id(manifest: dict[str, Any], mesh_id: str) -> dict[str, Any]:
    for asset in manifest["assets"]:
        if asset["unique_id"] == mesh_id:
            return asset
    raise KeyError(f"Unknown mesh ID: {mesh_id}")


def _process_memory() -> dict[str, int | None]:
    result: dict[str, int | None] = {
        "working_set_bytes": None,
        "peak_working_set_bytes": None,
        "private_usage_bytes": None,
    }
    if os.name != "nt":
        return result
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(counters)
        ok = psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(),
            ctypes.byref(counters),
            counters.cb,
        )
        if ok:
            result = {
                "working_set_bytes": int(counters.WorkingSetSize),
                "peak_working_set_bytes": int(counters.PeakWorkingSetSize),
                "private_usage_bytes": int(counters.PrivateUsage),
            }
    except (AttributeError, OSError, TypeError, ValueError):
        pass
    return result


def _windows_machine_details() -> dict[str, Any]:
    details: dict[str, Any] = {
        "logical_cpu_count": os.cpu_count(),
        "total_physical_memory_bytes": None,
        "available_physical_memory_bytes": None,
        "power_line_status": "UNKNOWN",
        "battery_percent": None,
    }
    if os.name != "nt":
        return details
    try:
        import ctypes
        from ctypes import wintypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        memory = MEMORYSTATUSEX()
        memory.dwLength = ctypes.sizeof(memory)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            details["total_physical_memory_bytes"] = int(memory.ullTotalPhys)
            details["available_physical_memory_bytes"] = int(memory.ullAvailPhys)

        class SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [
                ("ACLineStatus", ctypes.c_ubyte),
                ("BatteryFlag", ctypes.c_ubyte),
                ("BatteryLifePercent", ctypes.c_ubyte),
                ("SystemStatusFlag", ctypes.c_ubyte),
                ("BatteryLifeTime", wintypes.DWORD),
                ("BatteryFullLifeTime", wintypes.DWORD),
            ]

        power = SYSTEM_POWER_STATUS()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(power)):
            details["power_line_status"] = {
                0: "OFFLINE",
                1: "ONLINE",
                255: "UNKNOWN",
            }.get(int(power.ACLineStatus), "UNKNOWN")
            if int(power.BatteryLifePercent) != 255:
                details["battery_percent"] = int(power.BatteryLifePercent)
    except (AttributeError, OSError, TypeError, ValueError):
        pass
    return details


def _machine_information(blender_version: str) -> dict[str, Any]:
    info = {
        "operating_system": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "hostname": platform.node(),
        "python_version": platform.python_version(),
        "blender_version": blender_version,
        **_windows_machine_details(),
    }
    fingerprint_fields = {
        key: info.get(key)
        for key in (
            "operating_system",
            "machine",
            "processor",
            "logical_cpu_count",
            "total_physical_memory_bytes",
            "blender_version",
        )
    }
    info["machine_fingerprint"] = _stable_hash(fingerprint_fields)
    return info


def _expect_finished(label: str, result: Any) -> None:
    if not isinstance(result, set) or "FINISHED" not in result:
        raise RuntimeError(f"{label} returned {sorted(result) if result else result!r}")


def _measure(
    phases: dict[str, Any],
    label: str,
    callback: Callable[[], Any],
) -> Any:
    memory_before = _process_memory()
    wall_started = perf_counter()
    cpu_started = process_time()
    outcome = callback()
    cpu_seconds = process_time() - cpu_started
    wall_seconds = perf_counter() - wall_started
    memory_after = _process_memory()
    phases[label] = {
        "wall_seconds": round(wall_seconds, 6),
        "cpu_seconds": round(cpu_seconds, 6),
        "memory_before": memory_before,
        "memory_after": memory_after,
    }
    return outcome


def _analysis_metrics(report: dict[str, Any]) -> dict[str, Any]:
    geometry = report.get("geometry", {})
    topology = report.get("topology", {})
    surface_volume = report.get("surface_volume", {})
    build_volume = report.get("build_volume", {})
    dimensions = report.get("dimensions", {})
    shell_count = report.get("shell_count")
    if shell_count is None:
        shell_count = len(report.get("shells", []))
    return {
        "vertex_count": geometry.get("vertex_count"),
        "edge_count": geometry.get("edge_count"),
        "face_count": geometry.get("polygon_count"),
        "triangle_count": geometry.get("triangle_count"),
        "bounding_box_dimensions_mm": [
            dimensions.get("width_mm"),
            dimensions.get("depth_mm"),
            dimensions.get("height_mm"),
        ],
        "shell_count": shell_count,
        "connected_components": topology.get("connected_components"),
        "boundary_edges": topology.get("boundary_edges"),
        "non_manifold_edges": topology.get("non_manifold_edges"),
        "potential_duplicate_vertices": topology.get(
            "potential_duplicate_vertices"
        ),
        "degenerate_faces": topology.get("degenerate_faces"),
        "loose_vertices": topology.get("loose_vertices"),
        "loose_edges": topology.get("loose_edges"),
        "zero_length_edges": topology.get("zero_length_edges"),
        "surface_area_mm2": surface_volume.get("total_surface_area_mm2"),
        "reliable_volume_mm3": surface_volume.get(
            "reliable_closed_shell_volume_mm3"
        ),
        "orientation": topology.get("normal_consistency"),
        "watertightness": topology.get("watertight_state"),
        "build_volume_result": build_volume.get("fit_state"),
        "severity": report.get("severity"),
        "analysis_duration_ms": report.get("duration_ms"),
        "warning_count": len(report.get("warnings", [])),
        "error_count": len(report.get("errors", [])),
    }


def _metric_deltas(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    deltas: dict[str, Any] = {}
    for key in (
        "vertex_count",
        "edge_count",
        "face_count",
        "triangle_count",
        "shell_count",
        "connected_components",
        "boundary_edges",
        "non_manifold_edges",
        "potential_duplicate_vertices",
        "degenerate_faces",
        "loose_vertices",
        "loose_edges",
        "zero_length_edges",
        "surface_area_mm2",
        "reliable_volume_mm3",
    ):
        left = before.get(key)
        right = after.get(key)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            deltas[key] = right - left
        else:
            deltas[key] = None
    deltas["orientation_changed"] = (
        before.get("orientation") != after.get("orientation")
    )
    deltas["severity_changed"] = before.get("severity") != after.get("severity")
    return deltas


def _worker_arguments() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--mesh-id", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args(raw)


def _run_blender_worker(mesh_id: str, output_root: Path) -> int:
    import bpy

    addon_parent = REPOSITORY_ROOT / "blender_addon"
    if str(addon_parent) not in sys.path:
        sys.path.insert(0, str(addon_parent))

    import chroma3d_sculpt
    from chroma3d_sculpt.metadata import (
        DISPLAY_VERSION,
        REPAIR_AUDIT_SCHEMA_VERSION,
        SCHEMA_VERSION,
    )
    from chroma3d_sculpt.models.repair_models import plain_value
    from chroma3d_sculpt.services.repair_session import (
        get_active_session,
        get_current_analysis,
    )
    from chroma3d_sculpt.session import get_result

    manifest = _load_dataset_manifest()
    asset = _asset_by_id(manifest, mesh_id)
    paths = _artifact_paths(output_root, mesh_id)
    _ensure_directories(output_root)
    raw_path = REPOSITORY_ROOT / asset["stored_path"]
    metadata_path = (
        REPOSITORY_ROOT / "datasets" / "statues" / "metadata" / f"{mesh_id}.json"
    )
    thumbnail_path = REPOSITORY_ROOT / asset["thumbnail_path"]
    source_hash_before = _sha256(raw_path)
    if source_hash_before != asset["checksum_sha256"]:
        raise RuntimeError(f"Source SHA-256 mismatch before import: {mesh_id}")

    total_wall_started = perf_counter()
    total_cpu_started = process_time()
    phases: dict[str, Any] = {}
    lifecycle: dict[str, Any] = {}
    initial_memory = _process_memory()

    chroma3d_sculpt.register()
    try:
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)

        imported_result = _measure(
            phases,
            "import",
            lambda: bpy.ops.wm.stl_import(filepath=str(raw_path)),
        )
        _expect_finished("STL import", imported_result)
        imported = [
            obj for obj in bpy.context.selected_objects if obj.type == "MESH"
        ]
        if len(imported) != 1:
            raise RuntimeError(
                f"Expected one imported mesh object, found {len(imported)}."
            )
        source = imported[0]
        source.name = mesh_id
        source.data.name = f"{mesh_id}_mesh"
        bpy.context.view_layer.objects.active = source

        analysis_operator = _measure(
            phases,
            "analysis",
            lambda: bpy.ops.chroma3d.analyze_mesh(),
        )
        _expect_finished("analysis operator", analysis_operator)
        initial_result = get_result(source)
        if initial_result is None:
            raise RuntimeError("Production analysis operator stored no report.")
        export_analysis = _measure(
            phases,
            "analysis_export",
            lambda: bpy.ops.chroma3d.export_analysis_report(
                filepath=str(paths["analysis"])
            ),
        )
        _expect_finished("analysis export operator", export_analysis)
        initial_analysis = _read_json(paths["analysis"])

        start_result = _measure(
            phases,
            "repair_session_start",
            lambda: bpy.ops.chroma3d.start_repair_session(),
        )
        _expect_finished("start repair session operator", start_result)
        plan_result = _measure(
            phases,
            "repair_plan_initial",
            lambda: bpy.ops.chroma3d.generate_repair_plan(),
        )
        _expect_finished("initial repair plan operator", plan_result)
        session = get_active_session()
        if session is None or session.plan is None:
            raise RuntimeError("Production plan operator created no active plan.")
        initial_plan = plain_value(session.plan)
        initial_selected_operations = [
            item["operation_type"]
            for item in initial_plan["items"]
            if item["selected"]
        ]
        lifecycle["initial_selected_operations"] = initial_selected_operations

        if initial_selected_operations:
            apply_initial = _measure(
                phases,
                "repair_apply_initial",
                lambda: bpy.ops.chroma3d.apply_repair_plan(),
            )
            _expect_finished("initial repair apply operator", apply_initial)
            session = get_active_session()
            assert session is not None
            if any(record.status.value == "APPLIED" for record in session.operation_records):
                undo_result = _measure(
                    phases,
                    "repair_undo",
                    lambda: bpy.ops.chroma3d.undo_last_repair(),
                )
                _expect_finished("undo repair operator", undo_result)
                lifecycle["undo"] = {"executed": True, "status": "FINISHED"}
            else:
                lifecycle["undo"] = {
                    "executed": False,
                    "status": "NOT_APPLICABLE",
                    "reason": "All selected production operations reported no geometry change.",
                }
        else:
            lifecycle["undo"] = {
                "executed": False,
                "status": "NOT_APPLICABLE",
                "reason": "The production repair plan selected no operations.",
            }

        restore_result = _measure(
            phases,
            "repair_restore",
            lambda: bpy.ops.chroma3d.restore_repair_workspace(),
        )
        _expect_finished("restore workspace operator", restore_result)
        lifecycle["restore"] = {"executed": True, "status": "FINISHED"}

        canonical_plan_result = _measure(
            phases,
            "repair_plan_canonical",
            lambda: bpy.ops.chroma3d.generate_repair_plan(),
        )
        _expect_finished("canonical repair plan operator", canonical_plan_result)
        session = get_active_session()
        if session is None or session.plan is None:
            raise RuntimeError("Canonical production plan was not retained.")
        canonical_plan = plain_value(session.plan)
        canonical_selected_operations = [
            item["operation_type"]
            for item in canonical_plan["items"]
            if item["selected"]
        ]
        lifecycle["canonical_selected_operations"] = canonical_selected_operations

        if canonical_selected_operations:
            apply_canonical = _measure(
                phases,
                "repair_apply_canonical",
                lambda: bpy.ops.chroma3d.apply_repair_plan(),
            )
            _expect_finished("canonical repair apply operator", apply_canonical)
            lifecycle["canonical_apply"] = {
                "executed": True,
                "status": "FINISHED",
            }
        else:
            lifecycle["canonical_apply"] = {
                "executed": False,
                "status": "NOT_APPLICABLE",
                "reason": "The production repair plan selected no operations.",
            }

        session = get_active_session()
        if session is None:
            raise RuntimeError("Repair session ended before comparison capture.")
        final_result = get_current_analysis(session)
        if final_result is None:
            raise RuntimeError("No production after-repair analysis is available.")
        after_analysis = final_result.to_dict()
        production_comparison = (
            plain_value(session.comparison)
            if session.comparison is not None
            else {
                "status": "NOT_APPLICABLE",
                "reason": "No production repair operation was selected.",
            }
        )

        accept_result = _measure(
            phases,
            "repair_accept",
            lambda: bpy.ops.chroma3d.accept_repaired_copy(),
        )
        _expect_finished("accept repaired copy operator", accept_result)
        lifecycle["accept"] = {"executed": True, "status": "FINISHED"}
        export_audit = _measure(
            phases,
            "repair_audit_export",
            lambda: bpy.ops.chroma3d.export_repair_audit(
                filepath=str(paths["repair_audit"])
            ),
        )
        _expect_finished("repair audit export operator", export_audit)
        repair_audit = _read_json(paths["repair_audit"])

        for obj in bpy.context.selected_objects:
            obj.select_set(False)
        source.select_set(True)
        bpy.context.view_layer.objects.active = source
        rollback_start = _measure(
            phases,
            "rollback_probe_start",
            lambda: bpy.ops.chroma3d.start_repair_session(),
        )
        _expect_finished("rollback probe start operator", rollback_start)
        rollback_plan_result = _measure(
            phases,
            "rollback_probe_plan",
            lambda: bpy.ops.chroma3d.generate_repair_plan(),
        )
        _expect_finished("rollback probe plan operator", rollback_plan_result)
        rollback_session = get_active_session()
        if rollback_session is None or rollback_session.plan is None:
            raise RuntimeError("Rollback probe did not retain its production plan.")
        rollback_plan = plain_value(rollback_session.plan)
        rollback_result = _measure(
            phases,
            "repair_rollback",
            lambda: bpy.ops.chroma3d.rollback_repair_session(),
        )
        _expect_finished("rollback repair operator", rollback_result)
        lifecycle["rollback"] = {
            "executed": True,
            "status": "FINISHED",
            "scope": "Separate no-mutation production session on the protected source.",
        }
        export_rollback_audit = _measure(
            phases,
            "rollback_audit_export",
            lambda: bpy.ops.chroma3d.export_repair_audit(
                filepath=str(paths["rollback_audit"])
            ),
        )
        _expect_finished("rollback audit export operator", export_rollback_audit)
        rollback_audit = _read_json(paths["rollback_audit"])

        source_hash_after = _sha256(raw_path)
        if source_hash_after != source_hash_before:
            raise RuntimeError(f"Source mesh bytes changed during benchmark: {mesh_id}")

        total_wall_seconds = perf_counter() - total_wall_started
        total_cpu_seconds = process_time() - total_cpu_started
        final_memory = _process_memory()
        timings = {
            "schema_version": "1.0",
            "mesh_id": mesh_id,
            "timing_class": _timing_class(int(asset["triangle_count"])),
            "triangle_count": int(asset["triangle_count"]),
            "phases": phases,
            "production_analysis_duration_ms": initial_analysis["duration_ms"],
            "production_after_repair_analysis_duration_ms": after_analysis[
                "duration_ms"
            ],
            "canonical_repair_wall_seconds": phases.get(
                "repair_apply_canonical", {}
            ).get("wall_seconds", 0.0),
            "canonical_repair_cpu_seconds": phases.get(
                "repair_apply_canonical", {}
            ).get("cpu_seconds", 0.0),
            "total_wall_seconds": round(total_wall_seconds, 6),
            "total_cpu_seconds": round(total_cpu_seconds, 6),
            "initial_process_memory": initial_memory,
            "final_process_memory": final_memory,
            "peak_working_set_bytes": max(
                [
                    int(initial_memory.get("peak_working_set_bytes") or 0),
                    int(final_memory.get("peak_working_set_bytes") or 0),
                    *[
                        int(
                            phase.get("memory_after", {}).get(
                                "peak_working_set_bytes"
                            )
                            or 0
                        )
                        for phase in phases.values()
                    ],
                ]
            ),
            "measurement_notes": [
                "Wall time uses time.perf_counter().",
                "CPU time uses time.process_time() for the Blender process.",
                "Memory uses Windows process working-set counters sampled at phase boundaries; peak working set is the OS process high-water mark.",
                "Each mesh executes in a fresh Blender --factory-startup process.",
            ],
        }
        _write_json(paths["timings"], timings)

        before_metrics = _analysis_metrics(initial_analysis)
        after_metrics = _analysis_metrics(after_analysis)
        comparison = {
            "schema_version": "1.0",
            "mesh_id": mesh_id,
            "production_comparison": production_comparison,
            "before_metrics": before_metrics,
            "after_metrics": after_metrics,
            "metric_deltas": _metric_deltas(before_metrics, after_metrics),
        }
        _write_json(paths["comparison"], comparison)

        operation_records = repair_audit["session"].get("operation_records", [])
        warning_values = [
            *initial_analysis.get("warnings", []),
            *after_analysis.get("warnings", []),
            *repair_audit["session"].get("warnings", []),
            *rollback_audit["session"].get("warnings", []),
        ]
        warnings = list(dict.fromkeys(str(item) for item in warning_values))
        limitations = list(
            dict.fromkeys(
                [
                    *repair_audit.get("known_limitations", []),
                    *rollback_audit.get("known_limitations", []),
                    "Golden timing values are machine- and power-state-specific.",
                    "The baseline uses the production Standard analysis profile and default production repair settings.",
                    "Candidate-based destructive repair, normal consistency repair, and outward orientation remain unselected unless the production plan selects them by default.",
                    "The accepted audit is the canonical repair outcome; rollback is recorded in a separate production no-mutation session because accept and rollback are mutually exclusive decisions.",
                ]
            )
        )
        hashes = {
            "source_mesh_sha256": source_hash_before,
            "dataset_manifest_sha256": _sha256(DATASET_MANIFEST_PATH),
            "metadata_sha256": _sha256(metadata_path),
            "thumbnail_sha256": _sha256(thumbnail_path),
            "analysis_report_sha256": _sha256(paths["analysis"]),
            "repair_audit_sha256": _sha256(paths["repair_audit"]),
            "rollback_audit_sha256": _sha256(paths["rollback_audit"]),
            "comparison_sha256": _sha256(paths["comparison"]),
            "timings_sha256": _sha256(paths["timings"]),
        }
        machine = _machine_information(bpy.app.version_string)
        schema_fingerprints = {
            "analysis_report": _schema_fingerprint(initial_analysis),
            "after_analysis": _schema_fingerprint(after_analysis),
            "repair_audit": _schema_fingerprint(repair_audit),
            "rollback_audit": _schema_fingerprint(rollback_audit),
            "comparison": _schema_fingerprint(comparison),
            "timings": _schema_fingerprint(timings),
        }
        golden = {
            "golden_schema_version": "1.0",
            "benchmark_version": BENCHMARK_VERSION,
            "benchmark_date_utc": _utcnow(),
            "dataset_version": manifest["dataset_version"],
            "software_version": DISPLAY_VERSION,
            "analysis_schema_version": SCHEMA_VERSION,
            "repair_audit_schema_version": REPAIR_AUDIT_SCHEMA_VERSION,
            "mesh_id": mesh_id,
            "timing_class": _timing_class(int(asset["triangle_count"])),
            "mesh_classifications": _mesh_classifications(asset),
            "mesh_metadata": asset,
            "machine_information": machine,
            "analysis_report": initial_analysis,
            "after_repair_analysis": after_analysis,
            "repair_plan": {
                "initial": initial_plan,
                "canonical": canonical_plan,
                "rollback_probe": rollback_plan,
            },
            "repair_report": repair_audit,
            "rollback_report": rollback_audit,
            "comparison": comparison,
            "timings": timings,
            "lifecycle_actions": lifecycle,
            "operation_count": len(operation_records),
            "warnings": warnings,
            "limitations": limitations,
            "hashes": hashes,
            "schema_fingerprints": schema_fingerprints,
            "validation": {
                "status": "PASS",
                "source_hash_matches_metadata": (
                    source_hash_before == asset["checksum_sha256"]
                ),
                "source_hash_unchanged": source_hash_after == source_hash_before,
                "analysis_exported_by_production_operator": True,
                "repair_audit_exported_by_production_operator": True,
                "rollback_audit_exported_by_production_operator": True,
                "all_lifecycle_operator_results_finished": True,
                "errors": [],
            },
        }
        _write_json(paths["golden"], golden)
        report = {
            "mesh_id": mesh_id,
            "status": "PASS",
            "timing_class": golden["timing_class"],
            "mesh_classifications": golden["mesh_classifications"],
            "triangle_count": int(asset["triangle_count"]),
            "severity_before": before_metrics["severity"],
            "severity_after": after_metrics["severity"],
            "selected_operations": canonical_selected_operations,
            "operation_record_count": len(operation_records),
            "warning_count": len(warnings),
            "total_wall_seconds": timings["total_wall_seconds"],
            "total_cpu_seconds": timings["total_cpu_seconds"],
            "peak_working_set_bytes": timings["peak_working_set_bytes"],
            "artifacts": {
                key: (
                    path.relative_to(REPOSITORY_ROOT).as_posix()
                    if path.is_relative_to(REPOSITORY_ROOT)
                    else path.relative_to(output_root).as_posix()
                )
                for key, path in paths.items()
                if key != "log"
            },
        }
        _write_json(paths["report"], report)
        print(
            "GOLDEN_PASS "
            f"{mesh_id} {asset['triangle_count']}t "
            f"{timings['total_wall_seconds']:.3f}s "
            f"{len(canonical_selected_operations)} selected "
            f"{len(warnings)} warnings"
        )
        return 0
    finally:
        chroma3d_sculpt.unregister()


def _git_value(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _run_worker_process(
    blender: Path,
    mesh_id: str,
    output_root: Path,
    *,
    timeout_seconds: int,
) -> dict[str, Any]:
    command = [
        str(blender),
        "--background",
        "--factory-startup",
        "--python-exit-code",
        "1",
        "--python",
        str(Path(__file__).resolve()),
        "--",
        "--worker",
        "--mesh-id",
        mesh_id,
        "--output-root",
        str(output_root),
    ]
    started = perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        stderr += f"\nTimed out after {timeout_seconds} seconds."
    return {
        "command": subprocess.list2cmdline(command),
        "exit_code": exit_code,
        "duration_seconds": round(perf_counter() - started, 6),
        "stdout": stdout,
        "stderr": stderr,
        "stdout_tail": "\n".join(stdout.strip().splitlines()[-12:]),
        "stderr_tail": "\n".join(stderr.strip().splitlines()[-12:]),
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _summary_statistics(goldens: list[dict[str, Any]]) -> dict[str, Any]:
    total_wall = [float(item["timings"]["total_wall_seconds"]) for item in goldens]
    total_cpu = [float(item["timings"]["total_cpu_seconds"]) for item in goldens]
    analysis_ms = [
        float(item["timings"]["production_analysis_duration_ms"])
        for item in goldens
    ]
    repair_wall = [
        float(item["timings"]["canonical_repair_wall_seconds"])
        for item in goldens
    ]
    memory = [int(item["timings"]["peak_working_set_bytes"]) for item in goldens]
    timing_distribution = Counter(item["timing_class"] for item in goldens)
    classification_distribution: Counter[str] = Counter()
    severity_before: Counter[str] = Counter()
    severity_after: Counter[str] = Counter()
    operation_status: Counter[str] = Counter()
    operation_type: Counter[str] = Counter()
    selected_operations: Counter[str] = Counter()
    warning_total = 0
    for item in goldens:
        classification_distribution.update(item["mesh_classifications"])
        severity_before.update([item["analysis_report"]["severity"]])
        severity_after.update([item["after_repair_analysis"]["severity"]])
        selected_operations.update(
            item["lifecycle_actions"]["canonical_selected_operations"]
        )
        warning_total += len(item["warnings"])
        for record in item["repair_report"]["session"].get(
            "operation_records", []
        ):
            operation_status.update([record["status"]])
            operation_type.update([record["operation_type"]])

    def numeric(values: list[float]) -> dict[str, float]:
        return {
            "minimum": round(min(values), 6),
            "median": round(float(statistics.median(values)), 6),
            "mean": round(float(statistics.mean(values)), 6),
            "p95": round(_percentile(values, 0.95), 6),
            "maximum": round(max(values), 6),
            "total": round(sum(values), 6),
        }

    return {
        "schema_version": "1.0",
        "mesh_count": len(goldens),
        "triangle_count": numeric(
            [float(item["mesh_metadata"]["triangle_count"]) for item in goldens]
        ),
        "timing_class_distribution": dict(
            sorted(timing_distribution.items())
        ),
        "mesh_classification_distribution": dict(
            sorted(classification_distribution.items())
        ),
        "severity_before_distribution": dict(sorted(severity_before.items())),
        "severity_after_distribution": dict(sorted(severity_after.items())),
        "selected_operation_distribution": dict(
            sorted(selected_operations.items())
        ),
        "repair_operation_status_distribution": dict(
            sorted(operation_status.items())
        ),
        "repair_operation_type_distribution": dict(
            sorted(operation_type.items())
        ),
        "warning_total": warning_total,
        "wall_seconds": numeric(total_wall),
        "cpu_seconds": numeric(total_cpu),
        "analysis_duration_ms": numeric(analysis_ms),
        "canonical_repair_wall_seconds": numeric(repair_wall),
        "peak_working_set_bytes": numeric([float(item) for item in memory]),
    }


def _manifest_entry(root: Path, golden: dict[str, Any]) -> dict[str, Any]:
    mesh_id = golden["mesh_id"]
    paths = _artifact_paths(root, mesh_id)
    artifact_hashes = {
        key: {
            "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for key, path in paths.items()
        if key != "log" and path.is_file()
    }
    thumbnail_name = Path(golden["mesh_metadata"]["thumbnail_path"]).name
    thumbnail_path = root / "thumbnails" / thumbnail_name
    artifact_hashes["thumbnail"] = {
        "path": thumbnail_path.relative_to(REPOSITORY_ROOT).as_posix(),
        "sha256": _sha256(thumbnail_path),
        "size_bytes": thumbnail_path.stat().st_size,
    }
    return {
        "mesh_id": mesh_id,
        "title": golden["mesh_metadata"]["title"],
        "source_path": golden["mesh_metadata"]["stored_path"],
        "source_sha256": golden["hashes"]["source_mesh_sha256"],
        "metadata_sha256": golden["hashes"]["metadata_sha256"],
        "thumbnail_sha256": golden["hashes"]["thumbnail_sha256"],
        "triangle_count": golden["mesh_metadata"]["triangle_count"],
        "vertex_count": golden["mesh_metadata"]["vertex_count"],
        "timing_class": golden["timing_class"],
        "mesh_classifications": golden["mesh_classifications"],
        "analysis_severity": golden["analysis_report"]["severity"],
        "after_repair_severity": golden["after_repair_analysis"]["severity"],
        "selected_operations": golden["lifecycle_actions"][
            "canonical_selected_operations"
        ],
        "operation_record_count": golden["operation_count"],
        "warning_count": len(golden["warnings"]),
        "total_wall_seconds": golden["timings"]["total_wall_seconds"],
        "total_cpu_seconds": golden["timings"]["total_cpu_seconds"],
        "peak_working_set_bytes": golden["timings"]["peak_working_set_bytes"],
        "schema_fingerprints": golden["schema_fingerprints"],
        "validation_status": golden["validation"]["status"],
        "artifacts": artifact_hashes,
    }


def _markdown_summary(
    goldens: list[dict[str, Any]],
    stats: dict[str, Any],
) -> str:
    rows = []
    for item in sorted(goldens, key=lambda value: value["mesh_id"]):
        selected = item["lifecycle_actions"]["canonical_selected_operations"]
        rows.append(
            "| "
            + " | ".join(
                [
                    f"`{item['mesh_id']}`",
                    f"{int(item['mesh_metadata']['triangle_count']):,}",
                    item["timing_class"],
                    ", ".join(item["mesh_classifications"]),
                    item["analysis_report"]["severity"],
                    str(len(selected)),
                    f"{item['timings']['production_analysis_duration_ms'] / 1000:.3f}",
                    f"{item['timings']['canonical_repair_wall_seconds']:.3f}",
                    str(len(item["warnings"])),
                ]
            )
            + " |"
        )
    timing_rows = "\n".join(
        f"| {label} | {stats['timing_class_distribution'].get(label, 0)} |"
        for label, _ in TIMING_CLASS_THRESHOLDS
    )
    operation_rows = "\n".join(
        f"| {key} | {value} |"
        for key, value in stats["repair_operation_status_distribution"].items()
    ) or "| None | 0 |"
    return f"""# Golden Benchmark Baseline Summary

## Outcome

- Benchmark version: `{BENCHMARK_VERSION}`
- Dataset version: `{EXPECTED_DATASET_VERSION}`
- Chroma3D version: `{EXPECTED_SOFTWARE_VERSION}`
- Meshes benchmarked: {len(goldens)}
- Failed meshes: 0
- Stored warnings: {stats["warning_total"]}
- Total wall time: {stats["wall_seconds"]["total"]:.3f} seconds
- Total Blender CPU time: {stats["cpu_seconds"]["total"]:.3f} seconds
- Peak observed process working set: {stats["peak_working_set_bytes"]["maximum"] / (1024 ** 3):.3f} GiB

The stored warnings are production diagnostic evidence. They are not benchmark
execution failures.

## Per-mesh Results

| Mesh | Triangles | Timing class | Mesh classification | Before severity | Selected operations | Analysis s | Repair s | Warnings |
| --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

## Timing Distribution

| Class | Meshes |
| --- | ---: |
{timing_rows}

Triangle thresholds are Tiny `<25k`, Small `<100k`, Medium `<250k`, Large
`<500k`, Huge `<1m`, and Extreme `>=1m`.

## Repair Statistics

| Operation outcome | Records |
| --- | ---: |
{operation_rows}

The canonical plan uses production defaults. Candidate-based destructive
operations and orientation changes remain unselected unless the production
plan selects them through its normal UI state.

## Known Limitations

- Timings are authoritative only as a reference for this recorded machine,
  Blender version, power state, and one-fresh-process-per-mesh execution model.
- Peak memory is the Windows process high-water mark, sampled at phase
  boundaries; it is not a line-by-line allocator trace.
- Standard diagnostics are benchmarked. Deep self-intersection heuristics are
  outside Sprint 2.6.
- A production repair plan can legitimately select no operation. Such a mesh
  records an honest not-applicable comparison rather than a fabricated repair.
- Geometry still requires human review; the baseline is regression evidence,
  not a printability guarantee.
"""


def _golden_readme() -> str:
    return f"""# Chroma3D Golden Benchmark Baseline

This directory is the permanent regression reference generated from all 27
validated statue meshes in dataset `{EXPECTED_DATASET_VERSION}` using Chroma3D
`{EXPECTED_SOFTWARE_VERSION}` production operators.

## Reproduce and compare

```powershell
py manual-tests\\benchmarks\\run_golden_benchmark.py --compare `
  --blender "D:\\Softwares\\Design\\Blender\\blender.exe"
```

Verify stored files and hashes without rerunning Blender:

```powershell
py manual-tests\\benchmarks\\verify_golden_baseline.py
```

The generator runs each mesh in a fresh Blender `--factory-startup` process and
uses only the existing production flow:

`Analysis -> Repair Plan -> Repair -> Comparison -> Accept/Audit`

Undo and restore are exercised before the canonical apply. Rollback is exercised
in a second normal production session because accept and rollback are mutually
exclusive final decisions. Raw statue files are never modified.

## Layout

- `raw/`: production analysis JSON, accepted/rollback repair audits, and one
  self-contained `*_golden.json` truth record per mesh.
- `comparisons/`: production before/after comparison plus metric deltas.
- `timings/`: wall, Blender CPU, phase, and process-memory measurements.
- `statistics/`: aggregate distributions and repair/timing statistics.
- `reports/`: concise per-mesh reports, retained Blender logs, and the summary.
- `manifests/golden_manifest.json`: authoritative corpus and artifact index.
- `thumbnails/`: byte-identical identification copies from dataset 1.0.0.

## Regression rules

### PASS

- Source, metadata, and thumbnail hashes match.
- Dataset/software/schema versions match.
- Analysis topology, shell, issue, orientation, severity, warning, and
  deterministic report values match after volatile IDs/timestamps are removed.
- Repair plan selection, operation order/outcomes/metrics, comparison, audit,
  undo/restore/accept/rollback evidence, and after-repair topology match.
- Timing remains below the warning threshold.

### WARNING

- The machine fingerprint differs, so timing evidence is not directly
  comparable.
- On the same machine, a timed phase is at least
  `{TIMING_WARNING_RATIO:.1f}x` and at least
  `{TIMING_WARNING_ABSOLUTE_SECONDS:.1f}s` slower than its golden value, while
  remaining below the fail threshold.

### FAIL

- A source, metadata, thumbnail, stored artifact, or topology hash differs.
- Shell, duplicate, boundary, non-manifold, degenerate, loose-geometry,
  connected-component, orientation, severity, warning, or other deterministic
  analysis evidence changes.
- Selected repairs, repair outcomes, operation metrics/order, comparison,
  accepted audit, rollback audit, or source-preservation evidence changes.
- A JSON schema fingerprint or declared schema/software/dataset version changes.
- On the same machine, a timed phase is at least
  `{TIMING_FAIL_RATIO:.1f}x` and at least
  `{TIMING_FAIL_ABSOLUTE_SECONDS:.1f}s` slower than its golden value.

Timing improvements do not fail. Any intentional product/schema/dataset change
requires explicit review and a new benchmark version; never silently overwrite
this baseline.
"""


def _finalize_baseline(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    goldens = []
    for asset in sorted(manifest["assets"], key=lambda item: item["unique_id"]):
        mesh_id = asset["unique_id"]
        golden_path = _artifact_paths(root, mesh_id)["golden"]
        if not golden_path.is_file():
            raise RuntimeError(f"Missing golden truth file: {golden_path}")
        golden = _read_json(golden_path)
        if golden["validation"]["status"] != "PASS":
            raise RuntimeError(f"Golden truth is not PASS: {mesh_id}")
        goldens.append(golden)
        source_thumbnail = REPOSITORY_ROOT / asset["thumbnail_path"]
        target_thumbnail = root / "thumbnails" / source_thumbnail.name
        if target_thumbnail.exists():
            if _sha256(target_thumbnail) != _sha256(source_thumbnail):
                raise RuntimeError(
                    f"Existing golden thumbnail differs: {target_thumbnail.name}"
                )
        else:
            shutil.copyfile(source_thumbnail, target_thumbnail)

    machine_fingerprints = {
        item["machine_information"]["machine_fingerprint"] for item in goldens
    }
    if len(machine_fingerprints) != 1:
        raise RuntimeError("Per-mesh machine fingerprints are inconsistent.")
    software_versions = {item["software_version"] for item in goldens}
    if software_versions != {EXPECTED_SOFTWARE_VERSION}:
        raise RuntimeError(
            f"Unexpected software versions in golden files: {software_versions}"
        )

    stats = _summary_statistics(goldens)
    stats_path = root / "statistics" / "golden_statistics.json"
    _write_json(stats_path, stats)
    per_mesh_path = root / "reports" / "golden_per_mesh_summary.json"
    _write_json(
        per_mesh_path,
        {
            "benchmark_version": BENCHMARK_VERSION,
            "mesh_count": len(goldens),
            "entries": [
                _read_json(_artifact_paths(root, item["mesh_id"])["report"])
                for item in goldens
            ],
        },
    )
    _write_text(root / "BENCHMARK_SUMMARY.md", _markdown_summary(goldens, stats))
    _write_text(root / "README.md", _golden_readme())

    entries = [_manifest_entry(root, item) for item in goldens]
    machine = goldens[0]["machine_information"]
    power_states = Counter(
        item["machine_information"].get("power_line_status", "UNKNOWN")
        for item in goldens
    )
    golden_manifest = {
        "golden_manifest_schema_version": "1.0",
        "benchmark_version": BENCHMARK_VERSION,
        "dataset_version": manifest["dataset_version"],
        "dataset_manifest_sha256": _sha256(DATASET_MANIFEST_PATH),
        "software_version": EXPECTED_SOFTWARE_VERSION,
        "analysis_schema_version": goldens[0]["analysis_schema_version"],
        "repair_audit_schema_version": goldens[0][
            "repair_audit_schema_version"
        ],
        "mesh_count": len(entries),
        "benchmark_date_utc": _utcnow(),
        "source_git_commit": _git_value("rev-parse", "HEAD"),
        "source_git_tag": _git_value("describe", "--tags", "--exact-match"),
        "machine_information": machine,
        "power_state_distribution": dict(sorted(power_states.items())),
        "execution_model": (
            "One fresh Blender --background --factory-startup process per mesh; "
            "production operators and default production settings only."
        ),
        "timing_class_thresholds": {
            label: (
                {"triangle_count_less_than": maximum}
                if maximum is not None
                else {"triangle_count_at_least": 1_000_000}
            )
            for label, maximum in TIMING_CLASS_THRESHOLDS
        },
        "regression_thresholds": {
            "timing_warning_ratio": TIMING_WARNING_RATIO,
            "timing_warning_absolute_seconds": TIMING_WARNING_ABSOLUTE_SECONDS,
            "timing_fail_ratio": TIMING_FAIL_RATIO,
            "timing_fail_absolute_seconds": TIMING_FAIL_ABSOLUTE_SECONDS,
        },
        "statistics": {
            "path": stats_path.relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": _sha256(stats_path),
        },
        "summary_report": {
            "path": (
                root / "BENCHMARK_SUMMARY.md"
            ).relative_to(REPOSITORY_ROOT).as_posix(),
            "sha256": _sha256(root / "BENCHMARK_SUMMARY.md"),
        },
        "benchmark_entries": entries,
    }
    _write_json(root / "manifests" / "golden_manifest.json", golden_manifest)
    return golden_manifest


def _scrub_volatile(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _scrub_volatile(item)
            for key, item in sorted(value.items())
            if key not in VOLATILE_KEYS and key != "timings"
        }
    if isinstance(value, list):
        return [_scrub_volatile(item) for item in value]
    return value


def _diff_values(
    expected: Any,
    actual: Any,
    *,
    path: str = "$",
    limit: int = 100,
) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []

    def visit(left: Any, right: Any, current: str) -> None:
        if len(differences) >= limit:
            return
        if type(left) is not type(right):
            differences.append(
                {
                    "path": current,
                    "expected_type": type(left).__name__,
                    "actual_type": type(right).__name__,
                }
            )
            return
        if isinstance(left, dict):
            for key in sorted(set(left) | set(right)):
                child = f"{current}.{key}"
                if key not in left:
                    differences.append({"path": child, "expected": "<missing>", "actual": right[key]})
                elif key not in right:
                    differences.append({"path": child, "expected": left[key], "actual": "<missing>"})
                else:
                    visit(left[key], right[key], child)
                if len(differences) >= limit:
                    return
            return
        if isinstance(left, list):
            if len(left) != len(right):
                differences.append(
                    {
                        "path": current,
                        "expected_length": len(left),
                        "actual_length": len(right),
                    }
                )
                return
            for index, (left_item, right_item) in enumerate(zip(left, right)):
                visit(left_item, right_item, f"{current}[{index}]")
                if len(differences) >= limit:
                    return
            return
        if left != right:
            differences.append({"path": current, "expected": left, "actual": right})

    visit(expected, actual, path)
    return differences


def _timing_regressions(
    expected: dict[str, Any],
    actual: dict[str, Any],
    *,
    same_machine: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    phase_names = sorted(
        set(expected["timings"]["phases"]) & set(actual["timings"]["phases"])
    )
    comparisons = {
        f"phase:{name}": (
            float(expected["timings"]["phases"][name]["wall_seconds"]),
            float(actual["timings"]["phases"][name]["wall_seconds"]),
        )
        for name in phase_names
    }
    comparisons["total"] = (
        float(expected["timings"]["total_wall_seconds"]),
        float(actual["timings"]["total_wall_seconds"]),
    )
    comparisons["production_analysis"] = (
        float(expected["timings"]["production_analysis_duration_ms"]) / 1000.0,
        float(actual["timings"]["production_analysis_duration_ms"]) / 1000.0,
    )
    for name, (baseline, observed) in comparisons.items():
        if baseline <= 0:
            continue
        ratio = observed / baseline
        delta = observed - baseline
        record = {
            "metric": name,
            "baseline_seconds": round(baseline, 6),
            "observed_seconds": round(observed, 6),
            "ratio": round(ratio, 6),
            "delta_seconds": round(delta, 6),
        }
        if (
            ratio >= TIMING_FAIL_RATIO
            and delta >= TIMING_FAIL_ABSOLUTE_SECONDS
            and same_machine
        ):
            failures.append(record)
        elif (
            ratio >= TIMING_WARNING_RATIO
            and delta >= TIMING_WARNING_ABSOLUTE_SECONDS
        ):
            warnings.append(record)
    return warnings, failures


def _compare_golden(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if expected["mesh_id"] != actual["mesh_id"]:
        failures.append(
            {
                "type": "MESH_ID_MISMATCH",
                "expected": expected["mesh_id"],
                "actual": actual["mesh_id"],
            }
        )
    for key in (
        "benchmark_version",
        "dataset_version",
        "software_version",
        "analysis_schema_version",
    "repair_audit_schema_version",
    ):
        if expected.get(key) != actual.get(key):
            failures.append(
                {
                    "type": "VERSION_MISMATCH",
                    "field": key,
                    "expected": expected.get(key),
                    "actual": actual.get(key),
                }
            )
    for key in ("source_mesh_sha256", "metadata_sha256", "thumbnail_sha256"):
        if expected["hashes"].get(key) != actual["hashes"].get(key):
            failures.append(
                {
                    "type": "HASH_MISMATCH",
                    "field": key,
                    "expected": expected["hashes"].get(key),
                    "actual": actual["hashes"].get(key),
                }
            )
    for key, expected_fingerprint in expected["schema_fingerprints"].items():
        if expected_fingerprint != actual["schema_fingerprints"].get(key):
            failures.append(
                {
                    "type": "JSON_SCHEMA_REGRESSION",
                    "artifact": key,
                    "expected": expected_fingerprint,
                    "actual": actual["schema_fingerprints"].get(key),
                }
            )

    for label, expected_value, actual_value in (
        (
            "analysis",
            expected["analysis_report"],
            actual["analysis_report"],
        ),
        (
            "after_repair_analysis",
            expected["after_repair_analysis"],
            actual["after_repair_analysis"],
        ),
        (
            "repair",
            expected["repair_report"],
            actual["repair_report"],
        ),
        (
            "rollback",
            expected["rollback_report"],
            actual["rollback_report"],
        ),
        (
            "comparison",
            expected["comparison"],
            actual["comparison"],
        ),
        (
            "repair_plan",
            expected["repair_plan"],
            actual["repair_plan"],
        ),
        (
            "lifecycle",
            expected["lifecycle_actions"],
            actual["lifecycle_actions"],
        ),
    ):
        differences = _diff_values(
            _scrub_volatile(expected_value),
            _scrub_volatile(actual_value),
        )
        if differences:
            failures.append(
                {
                    "type": f"{label.upper()}_REGRESSION",
                    "difference_count": len(differences),
                    "differences": differences[:25],
                }
            )

    same_machine = (
        expected["machine_information"]["machine_fingerprint"]
        == actual["machine_information"]["machine_fingerprint"]
    )
    if not same_machine:
        warnings.append(
            {
                "type": "MACHINE_MISMATCH",
                "message": "Timing is not directly comparable across machine fingerprints.",
                "expected": expected["machine_information"]["machine_fingerprint"],
                "actual": actual["machine_information"]["machine_fingerprint"],
            }
        )
    timing_warnings, timing_failures = _timing_regressions(
        expected,
        actual,
        same_machine=same_machine,
    )
    warnings.extend(
        {"type": "TIMING_WARNING", **record} for record in timing_warnings
    )
    failures.extend(
        {"type": "TIMING_FAILURE", **record} for record in timing_failures
    )
    status = "FAIL" if failures else "WARNING" if warnings else "PASS"
    return {
        "mesh_id": expected["mesh_id"],
        "status": status,
        "failures": failures,
        "warnings": warnings,
    }


def _self_check(root: Path) -> int:
    manifest_path = root / "manifests" / "golden_manifest.json"
    if not manifest_path.is_file():
        print(f"FAIL missing golden manifest: {manifest_path}")
        return 1
    manifest = _read_json(manifest_path)
    results = []
    for entry in manifest["benchmark_entries"]:
        golden_path = REPOSITORY_ROOT / entry["artifacts"]["golden"]["path"]
        golden = _read_json(golden_path)
        results.append(_compare_golden(golden, golden))
    failures = [item for item in results if item["status"] != "PASS"]
    if failures:
        print(f"FAIL regression comparator self-check: {len(failures)} failures")
        return 1
    print(f"PASS regression comparator self-check: {len(results)}/{len(results)}")
    return 0


def _generate(
    blender: Path,
    root: Path,
    *,
    resume: bool,
    regenerate: bool,
    mesh_ids: list[str],
    timeout_seconds: int,
) -> int:
    if not blender.is_file():
        raise FileNotFoundError(f"Blender executable not found: {blender}")
    manifest = _load_dataset_manifest()
    assets = sorted(manifest["assets"], key=lambda item: item["unique_id"])
    if mesh_ids:
        requested = set(mesh_ids)
        unknown = requested - {item["unique_id"] for item in assets}
        if unknown:
            raise ValueError(f"Unknown mesh IDs: {sorted(unknown)}")
        assets = [item for item in assets if item["unique_id"] in requested]
    if (
        root == GOLDEN_ROOT
        and (root / "manifests" / "golden_manifest.json").exists()
        and not regenerate
    ):
        raise RuntimeError(
            "The permanent golden manifest already exists; generation refuses "
            "to overwrite it without the explicit --regenerate-baseline flag."
        )
    _ensure_directories(root)

    completed: list[str] = []
    failures: list[dict[str, Any]] = []
    for index, asset in enumerate(assets, start=1):
        mesh_id = asset["unique_id"]
        paths = _artifact_paths(root, mesh_id)
        if resume and paths["golden"].is_file():
            existing = _read_json(paths["golden"])
            if (
                existing.get("validation", {}).get("status") == "PASS"
                and existing.get("hashes", {}).get("source_mesh_sha256")
                == asset["checksum_sha256"]
            ):
                completed.append(mesh_id)
                print(f"[{index:02d}/{len(assets):02d}] SKIP {mesh_id} (validated)")
                continue
        print(
            f"[{index:02d}/{len(assets):02d}] RUN  {mesh_id} "
            f"({asset['triangle_count']:,} triangles, "
            f"{_timing_class(int(asset['triangle_count']))})",
            flush=True,
        )
        result = _run_worker_process(
            blender,
            mesh_id,
            root,
            timeout_seconds=timeout_seconds,
        )
        log_text = (
            f"$ {result['command']}\n"
            f"[exit={result['exit_code']} duration={result['duration_seconds']}s]\n"
            f"{result['stdout']}"
        )
        if result["stderr"]:
            log_text += f"\n[stderr]\n{result['stderr']}"
        _write_text(paths["log"], log_text)
        if result["exit_code"] == 0 and paths["golden"].is_file():
            completed.append(mesh_id)
            report = _read_json(paths["report"])
            print(
                f"[{index:02d}/{len(assets):02d}] PASS {mesh_id} "
                f"{report['total_wall_seconds']:.3f}s "
                f"{report['operation_record_count']} operation records "
                f"{report['warning_count']} warnings",
                flush=True,
            )
        else:
            failures.append(
                {
                    "mesh_id": mesh_id,
                    "exit_code": result["exit_code"],
                    "stdout_tail": result["stdout_tail"],
                    "stderr_tail": result["stderr_tail"],
                    "log_path": paths["log"].relative_to(
                        REPOSITORY_ROOT
                    ).as_posix(),
                }
            )
            print(
                f"[{index:02d}/{len(assets):02d}] FAIL {mesh_id} "
                f"exit={result['exit_code']}",
                flush=True,
            )
    _write_json(
        root / "reports" / "generation_status.json",
        {
            "benchmark_version": BENCHMARK_VERSION,
            "generated_at_utc": _utcnow(),
            "requested_mesh_count": len(assets),
            "completed_mesh_count": len(completed),
            "failed_mesh_count": len(failures),
            "completed_meshes": completed,
            "failures": failures,
        },
    )
    if failures:
        print(
            f"Golden generation incomplete: {len(completed)} completed, "
            f"{len(failures)} failed. Re-run with --generate --resume."
        )
        return 1
    if len(assets) != 27:
        print(
            f"Partial worker run completed for {len(assets)} mesh(es); "
            "the permanent manifest was not finalized."
        )
        return 0
    golden_manifest = _finalize_baseline(root, manifest)
    print(
        "Golden baseline generated: "
        f"{golden_manifest['mesh_count']} meshes, "
        f"{root / 'manifests' / 'golden_manifest.json'}"
    )
    return 0


def _compare(
    blender: Path,
    root: Path,
    *,
    timeout_seconds: int,
    mesh_ids: list[str],
) -> int:
    if not blender.is_file():
        raise FileNotFoundError(f"Blender executable not found: {blender}")
    baseline_manifest_path = root / "manifests" / "golden_manifest.json"
    if not baseline_manifest_path.is_file():
        raise FileNotFoundError(
            f"Golden manifest not found: {baseline_manifest_path}"
        )
    baseline_manifest = _read_json(baseline_manifest_path)
    entries = baseline_manifest["benchmark_entries"]
    if mesh_ids:
        requested = set(mesh_ids)
        entries = [item for item in entries if item["mesh_id"] in requested]
        found = {item["mesh_id"] for item in entries}
        if found != requested:
            raise ValueError(f"Unknown mesh IDs: {sorted(requested - found)}")

    results = []
    with tempfile.TemporaryDirectory(prefix="chroma3d-golden-regression-") as temp:
        actual_root = Path(temp)
        for index, entry in enumerate(entries, start=1):
            mesh_id = entry["mesh_id"]
            print(
                f"[{index:02d}/{len(entries):02d}] COMPARE {mesh_id}",
                flush=True,
            )
            worker = _run_worker_process(
                blender,
                mesh_id,
                actual_root,
                timeout_seconds=timeout_seconds,
            )
            if worker["exit_code"] != 0:
                result = {
                    "mesh_id": mesh_id,
                    "status": "FAIL",
                    "failures": [
                        {
                            "type": "EXECUTION_FAILURE",
                            "exit_code": worker["exit_code"],
                            "stdout_tail": worker["stdout_tail"],
                            "stderr_tail": worker["stderr_tail"],
                        }
                    ],
                    "warnings": [],
                }
            else:
                expected_path = REPOSITORY_ROOT / entry["artifacts"]["golden"]["path"]
                actual_path = _artifact_paths(actual_root, mesh_id)["golden"]
                result = _compare_golden(
                    _read_json(expected_path),
                    _read_json(actual_path),
                )
            results.append(result)
            print(
                f"[{index:02d}/{len(entries):02d}] {result['status']} {mesh_id}",
                flush=True,
            )

    status_counts = Counter(item["status"] for item in results)
    overall = (
        "FAIL"
        if status_counts["FAIL"]
        else "WARNING"
        if status_counts["WARNING"]
        else "PASS"
    )
    report = {
        "regression_report_schema_version": "1.0",
        "benchmark_version": baseline_manifest["benchmark_version"],
        "generated_at_utc": _utcnow(),
        "overall_status": overall,
        "mesh_count": len(results),
        "status_counts": dict(sorted(status_counts.items())),
        "results": results,
    }
    _write_json(LATEST_REGRESSION_PATH, report)
    print(
        f"Golden regression {overall}: {len(results)} meshes; "
        f"{LATEST_REGRESSION_PATH}"
    )
    return 1 if overall == "FAIL" else 0


def _host_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate or rerun the Chroma3D 27-mesh Golden Benchmark Baseline "
            "through production Blender operators."
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--generate",
        action="store_true",
        help="Generate the permanent baseline when it does not already exist.",
    )
    mode.add_argument(
        "--compare",
        action="store_true",
        help="Rerun and compare against the stored baseline (default).",
    )
    mode.add_argument(
        "--verify-only",
        action="store_true",
        help="Run stored-baseline verification without Blender.",
    )
    mode.add_argument(
        "--self-check",
        action="store_true",
        help="Exercise the regression comparator against the baseline itself.",
    )
    parser.add_argument("--blender", type=Path, default=DEFAULT_BLENDER)
    parser.add_argument("--baseline-root", type=Path, default=GOLDEN_ROOT)
    parser.add_argument("--mesh-id", action="append", default=[])
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume a partial generation without overwriting validated meshes.",
    )
    parser.add_argument(
        "--regenerate-baseline",
        action="store_true",
        help=(
            "Explicitly replace an existing same-version baseline. Use only "
            "after reviewed benchmark-harness correction or versioned refresh."
        ),
    )
    parser.add_argument(
        "--mesh-timeout-seconds",
        type=int,
        default=7200,
        help="Per-mesh Blender timeout; default 7200 seconds.",
    )
    return parser.parse_args()


def main() -> int:
    if "--worker" in sys.argv:
        arguments = _worker_arguments()
        return _run_blender_worker(
            arguments.mesh_id,
            arguments.output_root.resolve(),
        )

    arguments = _host_arguments()
    baseline_root = arguments.baseline_root.resolve()
    if arguments.verify_only:
        completed = subprocess.run(
            [sys.executable, str(VERIFY_SCRIPT), "--baseline-root", str(baseline_root)],
            cwd=REPOSITORY_ROOT,
            check=False,
        )
        return completed.returncode
    if arguments.self_check:
        return _self_check(baseline_root)
    if arguments.generate:
        return _generate(
            arguments.blender.resolve(),
            baseline_root,
            resume=arguments.resume,
            regenerate=arguments.regenerate_baseline,
            mesh_ids=arguments.mesh_id,
            timeout_seconds=arguments.mesh_timeout_seconds,
        )
    return _compare(
        arguments.blender.resolve(),
        baseline_root,
        timeout_seconds=arguments.mesh_timeout_seconds,
        mesh_ids=arguments.mesh_id,
    )


if __name__ == "__main__":
    raise SystemExit(main())
