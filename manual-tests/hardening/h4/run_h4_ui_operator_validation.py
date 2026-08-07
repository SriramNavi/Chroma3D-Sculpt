"""Exercise bounded operator poll and missing-context safety in Blender."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import bpy


ROOT = Path(__file__).resolve().parents[3]
ADDON_ROOT = ROOT / "blender_addon"
MESH_REQUIRED = {
    "chroma3d.analyze_mesh",
    "chroma3d.analyze_printability",
    "chroma3d.analyze_advanced_preparation",
    "chroma3d.start_repair_session",
    "chroma3d.start_optimization_session",
    "chroma3d.start_intelligent_optimization",
}
SAFE_EXECUTION_PROBES = (*sorted(MESH_REQUIRED), "chroma3d.start_ai_assistance")


def _arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(values)


def _clear_scene() -> None:
    for item in tuple(bpy.data.objects):
        bpy.data.objects.remove(item, do_unlink=True)


def _poll(classes: tuple[type, ...], label: str) -> list[dict[str, Any]]:
    records = []
    for cls in classes:
        try:
            namespace, name = cls.bl_idname.split(".", 1)
            value = bool(getattr(getattr(bpy.ops, namespace), name).poll())
            records.append({"operator": cls.bl_idname, "context": label, "poll": value, "error": ""})
        except Exception as exc:
            records.append({"operator": cls.bl_idname, "context": label, "poll": None, "error": f"{type(exc).__name__}: {exc}"[:500]})
    return records


def _invoke(bl_idname: str) -> dict[str, Any]:
    namespace, name = bl_idname.split(".", 1)
    try:
        result = set(getattr(getattr(bpy.ops, namespace), name)())
        safe = result == {"CANCELLED"}
        return {"operator": bl_idname, "result": sorted(result), "disabled_by_poll": False, "safe": safe, "error": ""}
    except RuntimeError as exc:
        message = str(exc)
        disabled = "poll() failed" in message or "context is incorrect" in message
        bounded_cancel = (
            bl_idname == "chroma3d.start_ai_assistance"
            and message.startswith("Error: Enable AI Assistance first")
            and "Traceback" not in message
            and len(message) <= 256
        )
        return {"operator": bl_idname, "result": [], "disabled_by_poll": disabled, "safe": disabled or bounded_cancel, "error": message[:500]}
    except Exception as exc:
        return {"operator": bl_idname, "result": [], "disabled_by_poll": False, "safe": False, "error": f"{type(exc).__name__}: {exc}"[:500]}


def main() -> int:
    args = _arguments()
    sys.path.insert(0, str(ADDON_ROOT))
    import chroma3d_sculpt

    chroma3d_sculpt.register()
    operator_classes = tuple(
        cls for cls in chroma3d_sculpt._RUNTIME_CLASSES
        if issubclass(cls, bpy.types.Operator)
    )
    ids = [cls.bl_idname for cls in operator_classes]
    _clear_scene()
    no_object_poll = _poll(operator_classes, "NO_ACTIVE_OBJECT")
    no_object_probes = [_invoke(value) for value in SAFE_EXECUTION_PROBES]
    empty = bpy.data.objects.new("H4 Wrong Type", None)
    bpy.context.collection.objects.link(empty)
    bpy.context.view_layer.objects.active = empty
    empty.select_set(True)
    wrong_type_poll = _poll(operator_classes, "WRONG_OBJECT_TYPE")
    wrong_type_probes = [_invoke(value) for value in SAFE_EXECUTION_PROBES]
    mesh_required_failures = [
        item for item in (*no_object_poll, *wrong_type_poll)
        if item["operator"] in MESH_REQUIRED and item["poll"] is not False
    ]
    poll_errors = [item for item in (*no_object_poll, *wrong_type_poll) if item["error"]]
    probe_failures = [item for item in (*no_object_probes, *wrong_type_probes) if not item["safe"]]
    state = bpy.context.window_manager.chroma3d_sculpt_state
    bounded_status = all(len(getattr(state, name)) <= 1024 for name in (
        "last_analysis", "repair_last_result", "optimization_last_result",
        "intelligent_optimization_last_result", "ai_assistance_last_result",
    ))
    unique_ids = len(ids) == len(set(ids))
    no_automatic_execution = not any(
        value in chroma3d_sculpt.register.__code__.co_names
        for value in ("execute_approved", "apply_selected_step", "apply_repair_plan")
    )
    chroma3d_sculpt.unregister()
    _clear_scene()
    passed = all((not poll_errors, not mesh_required_failures, not probe_failures, unique_ids, bounded_status, no_automatic_execution))
    payload = {
        "schema_version": "1.0.0",
        "status": "PASS" if passed else "FAIL",
        "operator_count": len(operator_classes),
        "unique_operator_ids": unique_ids,
        "poll_checks": len(no_object_poll) + len(wrong_type_poll),
        "poll_errors": poll_errors,
        "mesh_required_poll_failures": mesh_required_failures,
        "execution_probe_count": len(no_object_probes) + len(wrong_type_probes),
        "execution_probe_failures": probe_failures,
        "bounded_status_text": bounded_status,
        "no_automatic_execution_from_registration": no_automatic_execution,
        "contexts": ["NO_ACTIVE_OBJECT", "WRONG_OBJECT_TYPE"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(args.output)
    print(json.dumps({
        "status": payload["status"], "operators": len(operator_classes),
        "poll_checks": payload["poll_checks"], "execution_probes": payload["execution_probe_count"],
        "failures": len(poll_errors) + len(mesh_required_failures) + len(probe_failures),
    }, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
