"""Measure bounded representative product operations without changing runtime code."""

from __future__ import annotations

import argparse
import ctypes
import gc
import io
import json
import os
from pathlib import Path
import sys
import time
import unittest

import bpy


ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "blender_addon"
TESTS = ROOT / "tests" / "blender"


def _arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(values)


def _working_set() -> int | None:
    if os.name != "nt":
        return None
    try:
        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return int(counters.WorkingSetSize)
    except (AttributeError, OSError, ValueError):
        return None
    return None


def _clear_scene() -> None:
    for item in tuple(bpy.data.objects):
        bpy.data.objects.remove(item, do_unlink=True)
    for item in tuple(bpy.data.meshes):
        if item.users == 0:
            bpy.data.meshes.remove(item)


def _sphere(name: str, subdivisions: int):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions, radius=0.01)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = f"{name}Mesh"
    return obj


def _triangles(obj) -> int:
    return sum(max(0, len(polygon.vertices) - 2) for polygon in obj.data.polygons)


def _timed(records: list[dict[str, object]], operation: str, mode: str, input_size: dict[str, object], action):
    gc.collect()
    before = _working_set()
    started = time.perf_counter()
    value = action()
    elapsed = time.perf_counter() - started
    after = _working_set()
    records.append({
        "operation": operation,
        "mode": mode,
        "input_size": input_size,
        "elapsed_seconds": round(elapsed, 9),
        "working_set_before_bytes": before,
        "working_set_after_bytes": after,
        "working_set_delta_bytes": after - before if before is not None and after is not None else None,
        "status": "PASS",
    })
    return value


def _run_tests(names: tuple[str, ...]) -> None:
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in names)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    if not result.wasSuccessful():
        raise RuntimeError(f"representative tests failed: failures={len(result.failures)} errors={len(result.errors)}")


def main() -> int:
    args = _arguments()
    sys.path[:0] = [str(ADDON), str(TESTS)]
    import chroma3d_sculpt  # noqa: PLC0415
    from chroma3d_sculpt.analysis_settings import AnalysisSettings  # noqa: PLC0415
    from chroma3d_sculpt.models.ai_assistance_models import ConfidenceClassification, EvidenceReference, EvidenceState  # noqa: PLC0415
    from chroma3d_sculpt.models.optimization_models import OptimizationPolicy  # noqa: PLC0415
    from chroma3d_sculpt.models.printability_models import PrintabilityMode  # noqa: PLC0415
    from chroma3d_sculpt.printability_settings import PrintabilitySettings  # noqa: PLC0415
    from chroma3d_sculpt.repair_settings import RepairSettings  # noqa: PLC0415
    from chroma3d_sculpt.services.advanced_preparation_coordinator import analyze_advanced_preparation  # noqa: PLC0415
    from chroma3d_sculpt.services.assistance_context import build_context_manifest  # noqa: PLC0415
    from chroma3d_sculpt.feature_flags import build_feature_flags  # noqa: PLC0415
    from chroma3d_sculpt.services.hardware_profile_loader import load_hardware_profile  # noqa: PLC0415
    from chroma3d_sculpt.services.material_profile_loader import load_material_profile  # noqa: PLC0415
    from chroma3d_sculpt.services.mesh_analyzer import analyze_mesh  # noqa: PLC0415
    from chroma3d_sculpt.services.optimization_candidates import generate_candidates  # noqa: PLC0415
    from chroma3d_sculpt.services.optimization_comparison import compare_snapshots  # noqa: PLC0415
    from chroma3d_sculpt.services.pareto_frontier import build_pareto_frontier  # noqa: PLC0415
    from chroma3d_sculpt.services.printability_coordinator import analyze_printability  # noqa: PLC0415
    from chroma3d_sculpt.services.printer_profile_loader import load_profile  # noqa: PLC0415
    from chroma3d_sculpt.services.process_context import compose_process_context  # noqa: PLC0415
    from chroma3d_sculpt.services.repair_coordinator import rollback_repair_session  # noqa: PLC0415
    from chroma3d_sculpt.services.repair_session import start_session as start_repair_session  # noqa: PLC0415
    from chroma3d_sculpt.services.search_policy import default_search_policy  # noqa: PLC0415
    from chroma3d_sculpt.services.strategy_evaluator import virtual_evaluate_strategy  # noqa: PLC0415
    from chroma3d_sculpt.services.strategy_generator import generate_strategies  # noqa: PLC0415
    from chroma3d_sculpt.services.strategy_ranker import rank_strategies  # noqa: PLC0415
    from chroma3d_sculpt.ai_assistance_settings import default_assistance_policy, limits_for_mode  # noqa: PLC0415
    from chroma3d_sculpt.utilities.optimization_signatures import source_signature  # noqa: PLC0415

    records: list[dict[str, object]] = []
    failures: list[str] = []
    protected_source_unchanged = True
    size_specs = (("small", 1), ("medium", 3), ("large", 5))
    try:
        _clear_scene()
        profile = load_profile("generic_fdm")
        geometry = []
        for label, subdivisions in size_specs:
            obj = _sphere(f"H0_{label}", subdivisions)
            geometry.append((label, obj, _triangles(obj)))
        for label, obj, triangles in geometry:
            before = source_signature(obj)["source_signature"]
            _timed(records, "diagnostics", "STANDARD", {"size": label, "triangles": triangles}, lambda obj=obj: analyze_mesh(obj, bpy.context.scene, blender_version=bpy.app.version_string, blend_file_path=""))
            protected_source_unchanged &= source_signature(obj)["source_signature"] == before
            _timed(records, "printability", "FAST", {"size": label, "triangles": triangles}, lambda obj=obj: analyze_printability(obj, bpy.context.scene, profile, PrintabilitySettings(mode=PrintabilityMode.FAST), blender_version=bpy.app.version_string))
            protected_source_unchanged &= source_signature(obj)["source_signature"] == before
            if label != "large":
                _timed(records, "printability", "STANDARD", {"size": label, "triangles": triangles}, lambda obj=obj: analyze_printability(obj, bpy.context.scene, profile, PrintabilitySettings(mode=PrintabilityMode.STANDARD), blender_version=bpy.app.version_string))
                protected_source_unchanged &= source_signature(obj)["source_signature"] == before

        small = geometry[0][1]
        before = source_signature(small)["source_signature"]
        repair = _timed(
            records, "repair_workspace_create_and_discard", "CHECKPOINTED", {"size": "small", "triangles": geometry[0][2]},
            lambda: start_repair_session(small, bpy.context.scene, RepairSettings(), AnalysisSettings(), blender_version=bpy.app.version_string, blend_file_path=""),
        )
        rollback_repair_session(repair, blend_file_path="")
        protected_source_unchanged &= source_signature(small)["source_signature"] == before

        hardware = load_hardware_profile("bambu_x1_carbon")
        material = load_material_profile("generic_pla")
        process = compose_process_context(hardware, material, nozzle_mm=0.4, layer_height_mm=0.2, build_plate_type="TEXTURED")
        flags = build_feature_flags()
        medium = geometry[1][1]
        before = source_signature(medium)["source_signature"]
        _timed(records, "advanced_preparation", "FAST", {"size": "medium", "triangles": geometry[1][2]}, lambda: analyze_advanced_preparation(medium, bpy.context.scene, hardware, material, process, flags, PrintabilitySettings(mode=PrintabilityMode.FAST)))
        protected_source_unchanged &= source_signature(medium)["source_signature"] == before

        def controlled():
            candidates = generate_candidates(None, source_snapshot={"source_signature": "h0-source"}, policy=OptimizationPolicy())
            before_snapshot = {"build_fit": True, "height": 10.0, "triangle_count": 100, "vertex_count": 50, "bbox_dimensions": (10.0, 10.0, 10.0), "surface_area": 600.0, "volume": 1000.0, "fidelity_score": 1.0, "status": "PASS"}
            compare_snapshots(before_snapshot, {**before_snapshot, "height": 8.0})
            return candidates
        candidates = _timed(records, "controlled_optimization_candidate_generation_comparison", "STANDARD", {"candidate_input": "bounded synthetic snapshot", "triangles": None}, controlled)

        def intelligent():
            policy = default_search_policy()
            strategies = generate_strategies(candidates, policy=policy, source_signature="h0-source")
            evaluations = tuple(virtual_evaluate_strategy(item, policy=policy, baseline_values={"fidelity_status": "PASS", "critical_defect_introduced": False, "geometric_deviation": 0.0, "area_drift": 0.0, "volume_drift": 0.0, "build_volume_fit": 1.0, "geometry_fidelity": 1.0, "height": 1.0}) for item in strategies.strategies)
            frontier = build_pareto_frontier(evaluations, max_points=policy.budget.max_pareto_points)
            rank_strategies(tuple(item for item in evaluations if item.strategy_id in {point.strategy_id for point in frontier.points}))
            return strategies
        strategies = _timed(records, "intelligent_optimization_strategy_generation_ranking", "STANDARD", {"candidate_count": len(candidates), "triangles": None}, intelligent)

        evidence = (EvidenceReference("local:h0", "LOCAL_BASELINE", EvidenceState.PASS, ConfidenceClassification.HIGH, "a" * 64, ("h0",), (), True),)
        _timed(records, "ai_context_building", "STANDARD", {"evidence_count": len(evidence), "strategy_count": len(strategies.strategies), "triangles": 0}, lambda: build_context_manifest(source_signature_hash="a" * 64, object_display_name="H0", policy=default_assistance_policy(enabled=True), limits=limits_for_mode("STANDARD"), user_goal="Review existing local strategy.", evidence=evidence, strategy_ids=tuple(item.strategy_id for item in strategies.strategies[:8]), consent_approved=True, consent_timestamp="2026-08-07T00:00:00+00:00"))

        _timed(records, "offline_recommendation", "STANDARD", {"test_cases": 1, "triangles": 12}, lambda: _run_tests(("test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_33_offline_fallback_not_provider_generated",)))
        _timed(records, "report_export", "JSON_AND_MARKDOWN", {"test_cases": 2, "triangles": 0}, lambda: _run_tests(("test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_46_json_report", "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_47_markdown_report")))
    except Exception as exc:
        failures.append(f"{type(exc).__name__}: {exc}")
    finally:
        try:
            if hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state"):
                chroma3d_sculpt.unregister()
        except Exception as exc:
            failures.append(f"cleanup: {type(exc).__name__}: {exc}")
        _clear_scene()

    status = "PASS" if not failures and protected_source_unchanged else "FAIL"
    payload = {
        "schema_version": "1.0.0",
        "status": status,
        "blender_version": bpy.app.version_string,
        "records": records,
        "protected_source_unchanged": protected_source_unchanged,
        "failures": failures,
        "working_set_definition": "Point working-set observations immediately before and after each operation; not continuously sampled peak memory.",
        "limitations": [
            "Timings are local wall-clock baselines and include fixture/setup costs where noted.",
            "No full corpus, live provider, slicer, printer, physical print, or Blender 4.5 run is performed.",
            "Working-set observations are not peak-memory measurements.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": status, "records": len(records), "failures": failures, "protected_source_unchanged": protected_source_unchanged}, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
