"""Exercise bounded lifecycle paths and compare owned resources before/after."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

import bpy


ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "blender_addon"


def _arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=3)
    return parser.parse_args(values)


def _handlers() -> dict[str, int]:
    return {name: len(value) for name in dir(bpy.app.handlers) if isinstance((value := getattr(bpy.app.handlers, name)), list)}


def _cache_sizes(modules) -> dict[str, int]:
    result = {}
    for module in modules:
        for name, value in vars(module).items():
            if name.startswith("_") and isinstance(value, (dict, list, set)):
                result[f"{module.__name__}.{name}"] = len(value)
    return dict(sorted(result.items()))


def _snapshot(classes, modules) -> dict[str, object]:
    return {
        "objects": len(bpy.data.objects),
        "meshes": len(bpy.data.meshes),
        "collections": len(bpy.data.collections),
        "handlers": _handlers(),
        "registered_classes": sum(bool(getattr(item, "is_registered", False)) for item in classes),
        "cache_sizes": _cache_sizes(modules),
    }


def _clear_scene() -> None:
    for item in tuple(bpy.data.objects):
        bpy.data.objects.remove(item, do_unlink=True)
    for item in tuple(bpy.data.meshes):
        if item.users == 0:
            bpy.data.meshes.remove(item)
    for item in tuple(bpy.data.collections):
        if item.users == 0:
            bpy.data.collections.remove(item)


def _cube(name: str):
    bpy.ops.mesh.primitive_cube_add(size=0.02, location=(0.0, 0.0, 0.01))
    obj = bpy.context.object
    obj.name = name
    obj.data.name = f"{name}Mesh"
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return obj


def main() -> int:
    args = _arguments()
    if args.iterations < 2 or args.iterations > 10:
        raise ValueError("iterations must be between 2 and 10")
    sys.path.insert(0, str(ADDON))
    import chroma3d_sculpt  # noqa: PLC0415
    import chroma3d_sculpt.session as diagnostic_session  # noqa: PLC0415
    import chroma3d_sculpt.services.ai_assistance_session as ai_session  # noqa: PLC0415
    import chroma3d_sculpt.services.intelligent_optimization_session as intelligent_session  # noqa: PLC0415
    import chroma3d_sculpt.services.optimization_session as optimization_session  # noqa: PLC0415
    import chroma3d_sculpt.services.optimization_workspace as optimization_workspace  # noqa: PLC0415
    import chroma3d_sculpt.services.printability_session as printability_session  # noqa: PLC0415
    import chroma3d_sculpt.services.provider_registry as provider_registry  # noqa: PLC0415
    import chroma3d_sculpt.services.repair_session as repair_session  # noqa: PLC0415
    from chroma3d_sculpt.analysis_settings import AnalysisSettings  # noqa: PLC0415
    from chroma3d_sculpt.models.ai_assistance_models import AssistanceState  # noqa: PLC0415
    from chroma3d_sculpt.models.printability_models import PrintabilityMode  # noqa: PLC0415
    from chroma3d_sculpt.printability_settings import PrintabilitySettings  # noqa: PLC0415
    from chroma3d_sculpt.repair_settings import RepairSettings  # noqa: PLC0415
    from chroma3d_sculpt.services.ai_assistance_session import archive_session, create_session, request_cancellation  # noqa: PLC0415
    from chroma3d_sculpt.services.intelligent_optimization_session import start_intelligent_session  # noqa: PLC0415
    from chroma3d_sculpt.services.mesh_analyzer import analyze_mesh  # noqa: PLC0415
    from chroma3d_sculpt.services.optimization_session import discard_workspace, start_session as start_optimization  # noqa: PLC0415
    from chroma3d_sculpt.services.printability_coordinator import analyze_printability  # noqa: PLC0415
    from chroma3d_sculpt.services.printer_profile_loader import load_profile  # noqa: PLC0415
    from chroma3d_sculpt.services.repair_coordinator import rollback_repair_session  # noqa: PLC0415
    from chroma3d_sculpt.services.repair_session import start_session as start_repair  # noqa: PLC0415
    from chroma3d_sculpt.utilities.optimization_signatures import source_signature  # noqa: PLC0415

    modules = (diagnostic_session, repair_session, printability_session, optimization_session, optimization_workspace, intelligent_session, ai_session, provider_registry)
    classes = (*chroma3d_sculpt.PROPERTY_CLASSES, *chroma3d_sculpt._RUNTIME_CLASSES)
    records = []
    failures = []
    findings = []

    def exercise(name: str, action) -> None:
        before = _snapshot(classes, modules)
        try:
            detail = action() or {}
            after = _snapshot(classes, modules)
            restored = before == after
            classification = "EXPECTED_RETENTION" if detail.get("expected_retention") or restored else "SUSPICIOUS_RETENTION"
            records.append({"scenario": name, "before": before, "after": after, "restored": restored, "classification": classification, "detail": detail})
            if not restored and not detail.get("expected_retention"):
                findings.append(f"{name}: resource snapshot did not restore")
        except Exception as exc:
            failures.append(f"{name}: {type(exc).__name__}: {exc}")

    try:
        _clear_scene()
        for index in range(args.iterations):
            exercise(f"register_unregister_{index + 1}", lambda: (chroma3d_sculpt.register(), chroma3d_sculpt.unregister(), {})[-1])
        chroma3d_sculpt.register()
        source = _cube("H0LifecycleSource")
        source_before = source_signature(source)["source_signature"]

        def diagnostics():
            result = analyze_mesh(source, bpy.context.scene, blender_version=bpy.app.version_string, blend_file_path="")
            diagnostic_session.store_result(source, result)
            diagnostic_session.clear()
        exercise("diagnostic_session", diagnostics)

        def repair():
            session = start_repair(source, bpy.context.scene, RepairSettings(), AnalysisSettings(), blender_version=bpy.app.version_string, blend_file_path="")
            rollback_repair_session(session, blend_file_path="")
            repair_session.clear_runtime()
        exercise("repair_workspace_create_discard", repair)

        def printability():
            result = analyze_printability(source, bpy.context.scene, load_profile("generic_fdm"), PrintabilitySettings(mode=PrintabilityMode.FAST), blender_version=bpy.app.version_string)
            printability_session.store_result(source, result)
            printability_session.clear_runtime()
        exercise("printability_session", printability)

        def optimization():
            session = start_optimization(source, bpy.context.scene, blend_file_path="")
            discard_workspace(session, blend_file_path="")
            optimization_session.clear_runtime()
            optimization_workspace.clear_runtime()
        exercise("optimization_workspace_create_discard", optimization)

        def intelligent():
            start_intelligent_session(source, bpy.context.scene, blend_file_path="")
            controlled = intelligent_session.get_controlled_session()
            if controlled is not None:
                discard_workspace(controlled, blend_file_path="")
            intelligent_session.clear_runtime()
            optimization_session.clear_runtime()
            optimization_workspace.clear_runtime()
        exercise("intelligent_optimization_session", intelligent)

        def assistance():
            session = create_session(source_identity={"object": source.name}, source_signature_hash=source_before)
            request_cancellation(session)
            if session.state == AssistanceState.CANCELLED:
                archive_session(session)
            ai_session.clear_runtime()
            provider_registry.reset_test_providers()
        exercise("ai_assistance_session_cancel_discard", assistance)

        def temporary_files():
            with tempfile.TemporaryDirectory(prefix="chroma3d-h0-") as folder:
                path = Path(folder) / "probe.json"
                path.write_text("{}\n", encoding="utf-8", newline="\n")
                if not path.is_file():
                    raise RuntimeError("temporary write missing")
        exercise("temporary_file_create_cleanup", temporary_files)

        if source_signature(source)["source_signature"] != source_before:
            failures.append("protected source signature changed")
        bpy.data.objects.remove(source, do_unlink=True)
        chroma3d_sculpt.unregister()
    except Exception as exc:
        failures.append(f"lifecycle setup: {type(exc).__name__}: {exc}")
    finally:
        try:
            if hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state"):
                chroma3d_sculpt.unregister()
        except Exception as exc:
            failures.append(f"unregister cleanup: {type(exc).__name__}: {exc}")
        _clear_scene()

    status = "PASS" if not failures else "FAIL"
    payload = {
        "schema_version": "1.0.0",
        "status": status,
        "blender_version": bpy.app.version_string,
        "iterations": args.iterations,
        "records": records,
        "classification_counts": {name: sum(item["classification"] == name for item in records) for name in ("CONFIRMED_LEAK", "LIKELY_LEAK", "SUSPICIOUS_RETENTION", "EXPECTED_RETENTION", "INCONCLUSIVE")},
        "protected_source_unchanged": not any("protected source" in item for item in failures),
        "failures": failures,
        "findings": findings,
        "limitations": ["Counts are bounded process-local observations. Expected Blender/global caches are distinguished from session-owned resources; continuous heap profiling is not performed."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": status, "records": len(records), "failures": failures, "findings": findings}, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
