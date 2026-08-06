"""Smoke-test the installed Sprint 5 extension in an isolated Blender profile."""

from __future__ import annotations

import json
import os
from pathlib import Path

import bpy


OUTPUT = Path(__file__).with_name("artifacts") / "installed_package_smoke.json"


def clear_scene() -> None:
    for obj in tuple(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in tuple(bpy.data.collections):
        if collection.users == 0:
            bpy.data.collections.remove(collection)


def main() -> int:
    evidence: dict[str, object] = {"status": "FAIL", "checks": {}}
    try:
        expected_version = os.environ.get("CHROMA3D_EXPECTED_VERSION", "")
        import bl_ext.user_default.chroma3d_sculpt as addon
        from bl_ext.user_default.chroma3d_sculpt.metadata import DISPLAY_VERSION
        from bl_ext.user_default.chroma3d_sculpt.services.optimization_coordinator import (
            discard_workspace,
            generate_session_candidates,
            generate_session_plan,
            start_session,
        )

        clear_scene()
        if not hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state"):
            addon.register()
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 1.0))
        source = bpy.context.object
        session = start_session(source, bpy.context.scene)
        candidates = generate_session_candidates(session, source=source)
        plan = generate_session_plan(session)
        discard_workspace(session)
        evidence["checks"] = {
            "version": bool(expected_version) and DISPLAY_VERSION == expected_version,
            "optimization_operator": hasattr(bpy.ops.chroma3d, "start_optimization_session"),
            "candidate_generation": len(candidates) > 0,
            "plan_generation": len(plan.steps) > 0,
            "discard_completed": session.state.value == "DISCARDED",
        }
        evidence["status"] = "PASS" if all(evidence["checks"].values()) else "FAIL"
    except Exception as exc:
        evidence["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        clear_scene()
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0 if evidence["status"] == "PASS" else 1


raise SystemExit(main())
