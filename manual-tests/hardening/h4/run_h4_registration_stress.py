"""Stress Chroma3D registration, failed-start rollback, and unload cleanup."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import bpy


ROOT = Path(__file__).resolve().parents[3]
ADDON_ROOT = ROOT / "blender_addon"


def _arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=5)
    return parser.parse_args(values)


def _handlers() -> dict[str, int]:
    return {
        name: len(value)
        for name in dir(bpy.app.handlers)
        if isinstance((value := getattr(bpy.app.handlers, name)), list)
    }


def _owned_resources() -> dict[str, int]:
    owner_keys = {"chroma3d_optimization_session_id", "chroma3d_repair_session_id"}
    return {
        "objects": sum(any(key in item for key in owner_keys) or "Chroma3D" in item.name for item in bpy.data.objects),
        "meshes": sum("Chroma3D" in item.name for item in bpy.data.meshes),
        "collections": sum(bool(item.get("chroma3d_optimization_owned_collection")) or "Chroma3D" in item.name for item in bpy.data.collections),
    }


def _class_state(addon: Any) -> dict[str, Any]:
    classes = (*addon.PROPERTY_CLASSES, *addon._RUNTIME_CLASSES)
    registered = [item.__name__ for item in classes if bool(getattr(item, "is_registered", False))]
    return {
        "expected_count": len(classes),
        "registered_count": len(registered),
        "registered_classes": registered,
        "window_manager_property": hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state"),
    }


def _seed_runtime(addon: Any) -> None:
    from chroma3d_sculpt import session
    from chroma3d_sculpt.services import advanced_preparation_session
    from chroma3d_sculpt.services import ai_assistance_coordinator
    from chroma3d_sculpt.services import ai_assistance_session
    from chroma3d_sculpt.services import ai_credentials
    from chroma3d_sculpt.services import batch_preparation_session
    from chroma3d_sculpt.services import intelligent_optimization_session
    from chroma3d_sculpt.services import optimization_session
    from chroma3d_sculpt.services import printability_session
    from chroma3d_sculpt.services import provider_registry
    from chroma3d_sculpt.services import repair_session
    from chroma3d_sculpt.services.provider_transport import CancellationToken

    marker = object()
    session._reports[901] = marker
    session._latest_key = 901
    printability_session._results[902] = marker
    printability_session._latest_key = 902
    advanced_preparation_session._results[903] = marker
    advanced_preparation_session._latest_key = 903
    batch_preparation_session._current = marker
    repair_session._active_session = marker
    repair_session._archived_session = marker
    repair_session._current_analysis = marker
    optimization_session._active_session = marker
    optimization_session._archived_session = marker
    optimization_session._session_workspaces["h4"] = marker
    optimization_session._session_collections["h4"] = marker
    intelligent_optimization_session._active = marker
    intelligent_optimization_session._archived = marker
    intelligent_optimization_session._controlled_session = marker
    intelligent_optimization_session._runtime_profiles["h4"] = marker
    intelligent_optimization_session._runtime_policies["h4"] = marker
    ai_assistance_session._active = marker
    ai_assistance_session._archived = marker
    ai_assistance_session._tokens["h4"] = CancellationToken()
    ai_assistance_coordinator._contexts["h4"] = marker
    ai_assistance_coordinator._policies["h4"] = marker
    ai_assistance_coordinator._limits["h4"] = marker
    ai_assistance_coordinator._providers["h4"] = marker
    ai_assistance_coordinator._targets["h4"] = marker
    ai_assistance_coordinator._goals["h4"] = "marker"
    ai_credentials.set_session_key("h4-test-credential-never-report")
    provider_registry.register_provider("h4-test", marker)


def _runtime_clean() -> dict[str, Any]:
    from chroma3d_sculpt import session
    from chroma3d_sculpt.services import advanced_preparation_session
    from chroma3d_sculpt.services import ai_assistance_coordinator
    from chroma3d_sculpt.services import ai_assistance_session
    from chroma3d_sculpt.services import ai_credentials
    from chroma3d_sculpt.services import batch_preparation_session
    from chroma3d_sculpt.services import intelligent_optimization_session
    from chroma3d_sculpt.services import optimization_session
    from chroma3d_sculpt.services import printability_session
    from chroma3d_sculpt.services import provider_registry
    from chroma3d_sculpt.services import repair_session

    checks = {
        "analysis_cache": not session._reports and session._latest_key is None,
        "printability_cache": not printability_session._results and printability_session._latest_key is None,
        "preparation_cache": not advanced_preparation_session._results and advanced_preparation_session._latest_key is None,
        "batch_cache": batch_preparation_session._current is None,
        "repair_session": all(value is None for value in (repair_session._active_session, repair_session._archived_session, repair_session._current_analysis)) and not repair_session._checkpoint_meshes,
        "optimization_session": all(value is None for value in (optimization_session._active_session, optimization_session._archived_session)) and not optimization_session._session_workspaces and not optimization_session._session_collections,
        "intelligent_session": all(value is None for value in (intelligent_optimization_session._active, intelligent_optimization_session._archived, intelligent_optimization_session._controlled_session)) and not intelligent_optimization_session._runtime_profiles and not intelligent_optimization_session._runtime_policies,
        "assistance_session": ai_assistance_session._active is None and ai_assistance_session._archived is None and not ai_assistance_session._tokens,
        "assistance_coordinator": not any((ai_assistance_coordinator._contexts, ai_assistance_coordinator._policies, ai_assistance_coordinator._limits, ai_assistance_coordinator._providers, ai_assistance_coordinator._targets, ai_assistance_coordinator._goals)),
        "credential": ai_credentials.resolve_key({}) == (None, "NOT_CONFIGURED"),
        "provider_registry": provider_registry.available_provider_ids() == ("openai",),
    }
    return {"passed": all(checks.values()), "checks": checks}


def _bounded_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[:500]


def main() -> int:
    args = _arguments()
    if not 3 <= args.iterations <= 10:
        raise ValueError("iterations must be between 3 and 10")
    sys.path.insert(0, str(ADDON_ROOT))
    import chroma3d_sculpt

    baseline_handlers = _handlers()
    baseline_resources = _owned_resources()
    findings: list[dict[str, str]] = []
    cycles: list[dict[str, Any]] = []

    duplicate_error = ""
    try:
        chroma3d_sculpt.register()
        chroma3d_sculpt.register()
    except Exception as exc:  # deliberate adversarial boundary
        duplicate_error = _bounded_error(exc)
        findings.append({
            "id": "H4-F001",
            "classification": "HIGH",
            "title": "Duplicate register call is not safely idempotent",
            "evidence": duplicate_error,
        })
    finally:
        chroma3d_sculpt.unregister()
    duplicate = {
        "status": "PASS" if not duplicate_error else "FAIL",
        "error": duplicate_error,
        "after": _class_state(chroma3d_sculpt),
    }

    injected_error = ""
    original_register_class = bpy.utils.register_class
    counter = 0

    def injected_register_class(cls: Any) -> None:
        nonlocal counter
        counter += 1
        if counter == 5:
            raise RuntimeError("H4 injected registration failure")
        original_register_class(cls)

    bpy.utils.register_class = injected_register_class
    try:
        chroma3d_sculpt.register()
    except Exception as exc:  # expected injection
        injected_error = _bounded_error(exc)
    finally:
        bpy.utils.register_class = original_register_class
    injected_after = _class_state(chroma3d_sculpt)
    injected_clean = (
        bool(injected_error)
        and injected_after["registered_count"] == 0
        and not injected_after["window_manager_property"]
    )
    if not injected_clean:
        findings.append({
            "id": "H4-F002",
            "classification": "HIGH",
            "title": "Failed registration leaves partial Blender state",
            "evidence": json.dumps(injected_after, sort_keys=True),
        })
    chroma3d_sculpt.unregister()
    injected = {
        "status": "PASS" if injected_clean else "FAIL",
        "injected_error": injected_error,
        "state_before_explicit_cleanup": injected_after,
    }

    for index in range(args.iterations):
        chroma3d_sculpt.register()
        during = _class_state(chroma3d_sculpt)
        _seed_runtime(chroma3d_sculpt)
        chroma3d_sculpt.unregister()
        after = _class_state(chroma3d_sculpt)
        cleanup = _runtime_clean()
        item = {
            "iteration": index + 1,
            "during": during,
            "after": after,
            "handlers_restored": _handlers() == baseline_handlers,
            "owned_resources_restored": _owned_resources() == baseline_resources,
            "runtime_cleanup": cleanup,
        }
        item["passed"] = (
            during["registered_count"] == during["expected_count"]
            and during["window_manager_property"]
            and after["registered_count"] == 0
            and not after["window_manager_property"]
            and item["handlers_restored"]
            and item["owned_resources_restored"]
            and cleanup["passed"]
        )
        cycles.append(item)

    chroma3d_sculpt.register()
    usable_after_cycles = _class_state(chroma3d_sculpt)
    chroma3d_sculpt.unregister()
    final_state = _class_state(chroma3d_sculpt)
    status = "PASS" if not findings and all(item["passed"] for item in cycles) and final_state["registered_count"] == 0 else "FAIL"
    payload = {
        "schema_version": "1.0.0",
        "status": status,
        "blender_version": bpy.app.version_string,
        "factory_startup": True,
        "duplicate_registration": duplicate,
        "failed_start_cleanup": injected,
        "cycles": cycles,
        "usable_after_cycles": usable_after_cycles,
        "final_state": final_state,
        "findings": findings,
        "no_handlers_or_timers_declared": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(args.output)
    print(json.dumps({
        "status": status,
        "cycles_passed": sum(item["passed"] for item in cycles),
        "cycles_total": len(cycles),
        "findings": [item["id"] for item in findings],
    }, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
