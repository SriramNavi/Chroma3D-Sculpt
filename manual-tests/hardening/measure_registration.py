"""Measure extension import and repeated registration lifecycle in factory Blender."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
import time

import bpy


ROOT = Path(__file__).resolve().parents[2]
ADDON_ROOT = ROOT / "blender_addon"


def _arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=3)
    return parser.parse_args(values)


def _handlers() -> dict[str, int]:
    result = {}
    for name in dir(bpy.app.handlers):
        value = getattr(bpy.app.handlers, name)
        if isinstance(value, list):
            result[name] = len(value)
    return result


def _owned_resources() -> dict[str, int]:
    owner_keys = {"chroma3d_optimization_session_id", "chroma3d_repair_session_id"}
    return {
        "objects": sum(any(key in item for key in owner_keys) or "Chroma3D" in item.name for item in bpy.data.objects),
        "meshes": sum("Chroma3D" in item.name for item in bpy.data.meshes),
        "collections": sum(bool(item.get("chroma3d_optimization_owned_collection")) or "Chroma3D" in item.name for item in bpy.data.collections),
    }


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "minimum_seconds": round(min(values), 9),
        "median_seconds": round(statistics.median(values), 9),
        "maximum_seconds": round(max(values), 9),
    }


def main() -> int:
    args = _arguments()
    if args.iterations < 2 or args.iterations > 10:
        raise ValueError("iterations must be between 2 and 10")
    sys.path.insert(0, str(ADDON_ROOT))
    started = time.perf_counter()
    import chroma3d_sculpt  # noqa: PLC0415
    import_seconds = time.perf_counter() - started

    expected_classes = len(chroma3d_sculpt.PROPERTY_CLASSES) + len(chroma3d_sculpt._RUNTIME_CLASSES)
    iterations = []
    for index in range(args.iterations):
        before = {"handlers": _handlers(), "owned_resources": _owned_resources()}
        started = time.perf_counter()
        chroma3d_sculpt.register()
        register_seconds = time.perf_counter() - started
        registered_count = sum(bool(getattr(item, "is_registered", False)) for item in (*chroma3d_sculpt.PROPERTY_CLASSES, *chroma3d_sculpt._RUNTIME_CLASSES))
        during = {"handlers": _handlers(), "owned_resources": _owned_resources()}
        started = time.perf_counter()
        chroma3d_sculpt.unregister()
        unregister_seconds = time.perf_counter() - started
        after = {"handlers": _handlers(), "owned_resources": _owned_resources()}
        iterations.append({
            "iteration": index + 1,
            "register_seconds": round(register_seconds, 9),
            "unregister_seconds": round(unregister_seconds, 9),
            "registered_class_count": registered_count,
            "before": before,
            "during": during,
            "after": after,
            "handlers_restored": before["handlers"] == after["handlers"],
            "owned_resources_restored": before["owned_resources"] == after["owned_resources"],
        })
    register_values = [item["register_seconds"] for item in iterations]
    unregister_values = [item["unregister_seconds"] for item in iterations]
    status = "PASS" if all(item["handlers_restored"] and item["owned_resources_restored"] for item in iterations) and all(item["registered_class_count"] == expected_classes for item in iterations) else "FAIL"
    payload = {
        "schema_version": "1.0.0",
        "status": status,
        "blender_version": bpy.app.version_string,
        "factory_startup": True,
        "iterations": iterations,
        "extension_import_seconds": round(import_seconds, 9),
        "register": _summary(register_values),
        "unregister": _summary(unregister_values),
        "expected_class_count": expected_classes,
        "class_count_reliably_measured": True,
        "limitations": ["Wall-clock startup timings include OS, filesystem, and Python cache noise; use min/median/max as comparison evidence, not a precise universal startup claim."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": status, "import_seconds": payload["extension_import_seconds"], "register": payload["register"], "unregister": payload["unregister"], "classes": expected_classes}, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
