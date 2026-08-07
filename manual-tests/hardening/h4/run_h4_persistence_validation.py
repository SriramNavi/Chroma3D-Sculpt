"""Validate save/reload behavior for Chroma3D transient and persistent state."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
ADDON_ROOT = ROOT / "blender_addon"
DEFAULT_BLENDER = Path(r"D:\Softwares\Design\Blender\blender.exe")

TRANSIENT_EXACT = {
    "analyzed_object_name",
    "severity",
    "last_analysis",
    "selected_issue_index",
    "printability_object_name",
    "printability_status",
    "printability_confidence",
    "printability_last_result",
    "printability_state",
    "preparation_state",
    "preparation_status",
    "preparation_confidence",
    "preparation_last_result",
    "preparation_batch_status",
    "preparation_batch_summary",
    "preparation_baseline_path",
    "preparation_dashboard_path",
    "repair_session_status",
    "repair_plan_status",
    "repair_source_name",
    "repair_workspace_name",
    "repair_analysis_id",
    "repair_last_result",
    "repair_tiny_shell_candidates",
    "repair_selected_tiny_shell_index",
    "repair_small_hole_candidates",
    "repair_selected_small_hole_index",
    "optimization_state",
    "optimization_source_name",
    "optimization_workspace_name",
    "optimization_plan_status",
    "optimization_last_result",
    "optimization_selected_candidate_id",
    "intelligent_optimization_state",
    "intelligent_optimization_last_result",
    "intelligent_optimization_selected_strategy_id",
    "ai_assistance_state",
    "ai_assistance_last_result",
    "ai_assistance_consent",
    "ai_assistance_selected_recommendation_id",
}
RECOMPUTE_EXACT = {
    "total_issues",
    "degenerate_faces",
    "non_manifold_edges",
    "boundary_edges",
    "loose_vertices",
    "intersecting_face_pairs",
    "flipped_normal_faces",
}
RUNTIME_CLASSIFICATIONS = {
    "accepted_copy_provenance": "PERSIST_REQUIRED",
    "analysis_result": "RECOMPUTE_REQUIRED",
    "advanced_preparation_result": "RECOMPUTE_REQUIRED",
    "printability_result": "RECOMPUTE_REQUIRED",
    "session_id": "STALE_MUST_REJECT",
    "workspace_id": "STALE_MUST_REJECT",
    "source_fingerprint": "STALE_MUST_REJECT",
    "candidate_id": "STALE_MUST_REJECT",
    "strategy_id": "STALE_MUST_REJECT",
    "preview": "STALE_MUST_REJECT",
    "approval": "STALE_MUST_REJECT",
    "checkpoint_state": "STALE_MUST_REJECT",
    "temporary_datablock_reference": "TRANSIENT_MUST_CLEAR",
    "operator_progress": "TRANSIENT_MUST_CLEAR",
    "cancellation_state": "TRANSIENT_MUST_CLEAR",
    "error_status_text": "TRANSIENT_MUST_CLEAR",
    "api_key": "DO_NOT_SERIALIZE",
    "credential_characters": "DO_NOT_SERIALIZE",
    "provider_exchange": "DO_NOT_SERIALIZE",
    "raw_provider_response": "DO_NOT_SERIALIZE",
    "geometry_arrays": "DO_NOT_SERIALIZE",
    "file_bytes": "DO_NOT_SERIALIZE",
}


def _arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, default=DEFAULT_BLENDER)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", choices=("create", "reload"))
    parser.add_argument("--blend-file", type=Path)
    parser.add_argument("--worker-output", type=Path)
    return parser.parse_args(values)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def _classification(field: str) -> str:
    lowered = field.lower()
    if any(token in lowered for token in ("api_key", "credential", "provider_exchange", "raw_response", "secret")):
        return "DO_NOT_SERIALIZE"
    if field in RECOMPUTE_EXACT or field.startswith("has_") or field.endswith("_count") or field.endswith("_counts"):
        return "RECOMPUTE_REQUIRED"
    if field in TRANSIENT_EXACT:
        return "TRANSIENT_MUST_CLEAR"
    if any(token in lowered for token in ("session_id", "workspace_id", "fingerprint", "candidate_id", "strategy_id", "recommendation_id", "approval", "checkpoint_id", "progress", "cancellation")):
        return "STALE_MUST_REJECT"
    return "PERSIST_SAFE"


def _registry_state() -> dict[str, bool]:
    from chroma3d_sculpt import session
    from chroma3d_sculpt.services import advanced_preparation_session
    from chroma3d_sculpt.services import ai_assistance_coordinator
    from chroma3d_sculpt.services import ai_assistance_session
    from chroma3d_sculpt.services import batch_preparation_session
    from chroma3d_sculpt.services import intelligent_optimization_session
    from chroma3d_sculpt.services import optimization_session
    from chroma3d_sculpt.services import optimization_workspace
    from chroma3d_sculpt.services import printability_session
    from chroma3d_sculpt.services import repair_session

    return {
        "analysis": not session._reports and session._latest_key is None,
        "printability": not printability_session._results and printability_session._latest_key is None,
        "preparation": not advanced_preparation_session._results and advanced_preparation_session._latest_key is None,
        "batch": batch_preparation_session._current is None,
        "repair": repair_session._active_session is None and repair_session._archived_session is None and repair_session._current_analysis is None and not repair_session._checkpoint_meshes,
        "optimization": optimization_session._active_session is None and optimization_session._archived_session is None and not optimization_session._session_workspaces and not optimization_session._session_collections,
        "optimization_checkpoints": not optimization_workspace._checkpoint_meshes and not optimization_workspace._checkpoint_transforms and not optimization_workspace._checkpoint_names,
        "intelligent": intelligent_optimization_session._active is None and intelligent_optimization_session._archived is None and intelligent_optimization_session._controlled_session is None and not intelligent_optimization_session._runtime_profiles and not intelligent_optimization_session._runtime_policies,
        "assistance": ai_assistance_session._active is None and ai_assistance_session._archived is None and not ai_assistance_session._tokens,
        "assistance_context": not any((ai_assistance_coordinator._contexts, ai_assistance_coordinator._policies, ai_assistance_coordinator._limits, ai_assistance_coordinator._providers, ai_assistance_coordinator._targets, ai_assistance_coordinator._goals)),
    }


def _worker(args: argparse.Namespace) -> int:
    import bpy

    if args.blend_file is None or args.worker_output is None:
        raise ValueError("worker paths are required")
    sys.path.insert(0, str(ADDON_ROOT))
    import chroma3d_sculpt
    from chroma3d_sculpt.services import ai_credentials

    chroma3d_sculpt.register()
    state = bpy.context.window_manager.chroma3d_sculpt_state
    fields = sorted(chroma3d_sculpt.SESSION_STATE_CLASS.__annotations__)
    classifications = {field: _classification(field) for field in fields}
    if args.worker == "create":
        transient_values = {
            "analyzed_object_name": "H4_TRANSIENT_ANALYSIS",
            "last_analysis": "H4_TRANSIENT_RESULT",
            "repair_session_status": "ACTIVE",
            "repair_source_name": "H4_TRANSIENT_SOURCE",
            "repair_workspace_name": "H4_TRANSIENT_WORKSPACE",
            "repair_analysis_id": "H4_TRANSIENT_ANALYSIS_ID",
            "optimization_state": "ACTIVE",
            "optimization_source_name": "H4_TRANSIENT_OPT_SOURCE",
            "optimization_workspace_name": "H4_TRANSIENT_OPT_WORKSPACE",
            "optimization_selected_candidate_id": "H4_TRANSIENT_CANDIDATE",
            "intelligent_optimization_state": "READY",
            "intelligent_optimization_selected_strategy_id": "H4_TRANSIENT_STRATEGY",
            "ai_assistance_state": "PREVIEW_READY",
            "ai_assistance_consent": True,
            "ai_assistance_selected_recommendation_id": "H4_TRANSIENT_RECOMMENDATION",
        }
        for name, value in transient_values.items():
            setattr(state, name, value)
        fake_key = "h4-" + secrets.token_hex(24)
        ai_credentials.set_session_key(fake_key)
        bpy.ops.mesh.primitive_cube_add()
        source = bpy.context.active_object
        source.name = "H4 Persistence Source"
        before_vertices = len(source.data.vertices)
        args.blend_file.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(args.blend_file))
        blend_bytes = args.blend_file.read_bytes()
        payload = {
            "status": "PASS",
            "fields": fields,
            "classifications": classifications,
            "transient_values": sorted(transient_values),
            "credential_absent_from_blend": fake_key.encode("utf-8") not in blend_bytes,
            "source_vertices": before_vertices,
            "blend_bytes": len(blend_bytes),
        }
    else:
        defaults = {name: getattr(state, name) for name in TRANSIENT_EXACT if name in fields and not name.endswith("candidates")}
        default_failures = {
            name: value
            for name, value in defaults.items()
            if value not in ("", 0, False, "NOT_RUN", "NOT_STARTED", "NOT_GENERATED", "INITIAL", -1)
        }
        source = bpy.data.objects.get("H4 Persistence Source")
        registry = _registry_state()
        credential, credential_source = ai_credentials.resolve_key({})
        payload = {
            "status": "PASS" if not default_failures and all(registry.values()) and credential is None and source is not None and len(source.data.vertices) == 8 else "FAIL",
            "fields": fields,
            "classifications": classifications,
            "default_failures": default_failures,
            "runtime_registries_clean": registry,
            "credential_configured": credential is not None,
            "credential_source": credential_source,
            "source_present": source is not None,
            "source_vertices": len(source.data.vertices) if source is not None else None,
        }
    chroma3d_sculpt.unregister()
    _write_json(args.worker_output, payload)
    print(json.dumps({"status": payload["status"], "worker": args.worker}, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


def _run(command: list[str], log: Path, timeout: int = 180) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(completed.stdout + "\n--- STDERR ---\n" + completed.stderr, encoding="utf-8", newline="\n")
    return {"returncode": completed.returncode, "log": log.relative_to(ROOT).as_posix()}


def _host(args: argparse.Namespace) -> int:
    if not args.blender.is_file():
        raise FileNotFoundError(f"Blender not found: {args.blender}")
    reports = args.output.parent
    logs = ROOT / "manual-tests" / "hardening" / "h4" / "logs"
    blend_file = reports / "persistence_roundtrip.blend"
    create_output = reports / "persistence_create.json"
    reload_output = reports / "persistence_reload.json"
    common = ["--background", "--factory-startup", "--python-exit-code", "1"]
    create = _run([
        str(args.blender), *common, "--python", str(Path(__file__).resolve()), "--",
        "--worker", "create", "--blend-file", str(blend_file), "--worker-output", str(create_output),
        "--output", str(args.output),
    ], logs / "persistence_create.log")
    reload_run = {"returncode": None, "not_run_reason": "create failed"}
    if create["returncode"] == 0 and blend_file.is_file():
        reload_run = _run([
            str(args.blender), "--background", "--factory-startup", str(blend_file),
            "--python-exit-code", "1", "--python", str(Path(__file__).resolve()), "--",
            "--worker", "reload", "--blend-file", str(blend_file), "--worker-output", str(reload_output),
            "--output", str(args.output),
        ], logs / "persistence_reload.log")
    created = json.loads(create_output.read_text(encoding="utf-8")) if create_output.is_file() else {}
    reloaded = json.loads(reload_output.read_text(encoding="utf-8")) if reload_output.is_file() else {}
    fields = created.get("fields", ())
    property_classifications = created.get("classifications", {})
    classifications = {
        **{f"property:{key}": value for key, value in property_classifications.items()},
        **{f"runtime:{key}": value for key, value in RUNTIME_CLASSIFICATIONS.items()},
    }
    counts = {name: sum(value == name for value in classifications.values()) for name in (
        "PERSIST_REQUIRED", "PERSIST_SAFE", "RECOMPUTE_REQUIRED", "TRANSIENT_MUST_CLEAR", "STALE_MUST_REJECT", "DO_NOT_SERIALIZE",
    )}
    passed = all((
        create["returncode"] == 0,
        reload_run.get("returncode") == 0,
        created.get("credential_absent_from_blend") is True,
        reloaded.get("status") == "PASS",
        len(fields) == len(property_classifications),
        not set(classifications.values()) - set(counts),
    ))
    payload = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if passed else "FAIL",
        "property_field_count": len(fields),
        "runtime_item_count": len(RUNTIME_CLASSIFICATIONS),
        "classified_item_count": len(classifications),
        "classification_counts": counts,
        "classifications": classifications,
        "create": {key: created.get(key) for key in ("status", "credential_absent_from_blend", "source_vertices", "blend_bytes")},
        "reload": {key: reloaded.get(key) for key in ("status", "default_failures", "runtime_registries_clean", "credential_configured", "credential_source", "source_present", "source_vertices")},
        "runs": {"create": create, "reload": reload_run},
        "source_mutation_count": 0 if reloaded.get("source_vertices") == created.get("source_vertices") == 8 else 1,
        "limitations": ["WindowManager UI preferences are session-scoped in the current product; H4 requires transient safety, not preference persistence migration."],
    }
    _write_json(args.output, payload)
    print(json.dumps({"status": payload["status"], "fields": len(fields), "classification_counts": counts}, sort_keys=True))
    return 0 if passed else 1


def main() -> int:
    args = _arguments()
    return _worker(args) if args.worker else _host(args)


if __name__ == "__main__":
    raise SystemExit(main())
