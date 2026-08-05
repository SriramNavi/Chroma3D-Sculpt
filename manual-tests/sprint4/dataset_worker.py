"""Analyze one Dataset 1.0.0 STL with the fixed Sprint 4 process context."""

from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from time import perf_counter

import bpy


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ADDON_ROOT = REPOSITORY_ROOT / "blender_addon"
if str(ADDON_ROOT) not in sys.path:
    sys.path.insert(0, str(ADDON_ROOT))

from chroma3d_sculpt.feature_flags import build_feature_flags  # noqa: E402
from chroma3d_sculpt.models.printability_models import PrintabilityMode  # noqa: E402
from chroma3d_sculpt.printability_settings import PrintabilitySettings  # noqa: E402
from chroma3d_sculpt.services.advanced_preparation_coordinator import analyze_advanced_preparation  # noqa: E402
from chroma3d_sculpt.services.hardware_profile_loader import load_hardware_profile  # noqa: E402
from chroma3d_sculpt.services.material_profile_loader import load_material_profile  # noqa: E402
from chroma3d_sculpt.services.printability_baseline import baseline_record  # noqa: E402
from chroma3d_sculpt.services.process_context import compose_process_context  # noqa: E402
from chroma3d_sculpt.utilities.printability_signatures import printability_source_snapshot  # noqa: E402


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def working_set_bytes() -> int | None:
    if sys.platform != "win32":
        return None
    class ProcessMemory(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong), ("page_fault_count", ctypes.c_ulong), ("peak_working_set_size", ctypes.c_size_t),
            ("working_set_size", ctypes.c_size_t), ("quota_peak_paged_pool_usage", ctypes.c_size_t),
            ("quota_paged_pool_usage", ctypes.c_size_t), ("quota_peak_non_paged_pool_usage", ctypes.c_size_t),
            ("quota_non_paged_pool_usage", ctypes.c_size_t), ("pagefile_usage", ctypes.c_size_t), ("peak_pagefile_usage", ctypes.c_size_t),
        ]
    process = ProcessMemory(); process.cb = ctypes.sizeof(process)
    ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(process), ctypes.sizeof(process))
    return int(process.working_set_size)


def parse_args() -> argparse.Namespace:
    arguments = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--implementation-fingerprint", required=True)
    return parser.parse_args(arguments)


def write_result(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"); temporary.replace(path)


def main() -> int:
    args = parse_args(); source = args.source.resolve(); started = perf_counter(); source_hash = file_sha256(source)
    base: dict[str, object] = {
        "mesh": source.stem, "source_path": str(source), "source_sha256": source_hash,
        "implementation_fingerprint": args.implementation_fingerprint, "hardware_profile_id": "bambu_x1_carbon",
        "material_profile_id": "generic_pla", "nozzle_mm": 0.4, "layer_height_mm": 0.2,
        "build_plate_type": "TEXTURED", "support_policy": "REVIEW_REQUIRED", "performance_mode": "FAST",
        "resin_advisory_enabled": False, "blender_version": bpy.app.version_string, "completed_at": utcnow(),
    }
    try:
        imported = bpy.ops.wm.stl_import(filepath=str(source))
        if "FINISHED" not in imported: raise RuntimeError(f"STL import returned {imported}")
        objects = [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]
        if len(objects) != 1: raise RuntimeError(f"Expected one imported mesh, found {len(objects)}")
        obj = objects[0]; before = printability_source_snapshot(obj); memory_before = working_set_bytes()
        hardware = load_hardware_profile("bambu_x1_carbon"); material = load_material_profile("generic_pla")
        process = compose_process_context(hardware, material, nozzle_mm=0.4, layer_height_mm=0.2, build_plate_type="TEXTURED")
        flags = build_feature_flags(); settings = PrintabilitySettings(mode=PrintabilityMode.FAST)
        result = analyze_advanced_preparation(obj, bpy.context.scene, hardware, material, process, flags, settings, blender_version=bpy.app.version_string)
        memory_after = working_set_bytes(); after = printability_source_snapshot(obj)
        if before["printability_sha256"] != after["printability_sha256"]: raise RuntimeError("Imported source state changed during Sprint 4 analysis")
        if file_sha256(source) != source_hash: raise RuntimeError("Dataset source file hash changed")
        record = baseline_record(source.stem, source_hash, result)
        base.update({
            "worker_status": "PASS", "process_context_hash": process.context_hash, "feature_flag_hash": flags.flag_hash,
            "report_schema_version": result.report_schema_version, "score_status": result.status.value, "confidence": result.confidence.value,
            "score": result.score, "check_states": record.per_check_states, "bridge_state": result.bridge_risk.status.value,
            "bridge_risk_count": result.bridge_risk.candidate_region_count, "support_state": result.support_risk.status.value,
            "support_risk_area_mm2": result.support_risk.total_risk_area_mm2,
            "scale_interval": result.scale_recommendation.recommended_interval.to_dict(),
            "orientation_candidate_count": len(result.orientation_comparison.candidates),
            "baseline_record": record.to_dict(), "analysis_duration_seconds": result.timings["total"],
            "worker_duration_seconds": perf_counter() - started, "working_set_before_bytes": memory_before,
            "working_set_after_bytes": memory_after, "memory_observation": "Point-in-time working-set observations; not exact peak memory.",
            "source_immutable": True,
        })
        write_result(args.output, base); return 0
    except Exception as exc:
        base.update({"worker_status": "ERROR", "error": f"{type(exc).__name__}: {exc}", "worker_duration_seconds": perf_counter() - started, "source_immutable": False})
        write_result(args.output, base); raise


if __name__ == "__main__":
    raise SystemExit(main())
