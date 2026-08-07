"""Blender worker measuring raw versus isolated Chroma3D conditioning evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

import bpy


ROOT = Path(__file__).resolve().parents[3]
ADDON = ROOT / "blender_addon"
if str(ADDON) not in sys.path:
    sys.path.insert(0, str(ADDON))

from chroma3d_sculpt.analysis_settings import AnalysisSettings  # noqa: E402
from chroma3d_sculpt.repair_settings import RepairSettings  # noqa: E402
from chroma3d_sculpt.services.mesh_analyzer import analyze_mesh  # noqa: E402
from chroma3d_sculpt.services.repair_coordinator import apply_repair_plan, generate_repair_plan, rollback_repair_session  # noqa: E402
from chroma3d_sculpt.services.repair_session import get_current_analysis, start_session  # noqa: E402
from chroma3d_sculpt.utilities.repair_signatures import protected_source_is_current  # noqa: E402


WORKER_VERSION = "cgb-conditioning-worker-1.0.0"


def _arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--conditioned-output", type=Path, required=True)
    parser.add_argument("--metrics-output", type=Path, required=True)
    return parser.parse_args(values)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _import(path: Path):
    for item in tuple(bpy.data.objects):
        bpy.data.objects.remove(item, do_unlink=True)
    if path.suffix.lower() == ".stl":
        bpy.ops.wm.stl_import(filepath=str(path))
    elif path.suffix.lower() == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    elif path.suffix.lower() == ".ply":
        bpy.ops.wm.ply_import(filepath=str(path))
    else:
        raise ValueError(f"Unsupported conditioning artifact format: {path.suffix}")
    source = bpy.context.object
    if source is None or source.type != "MESH":
        raise RuntimeError("Conditioning import did not produce an active mesh.")
    return source


def _summary(result) -> dict[str, object]:
    payload = result.to_dict()
    topology = payload["topology"]
    issue_count = len(payload.get("warnings", [])) + len(payload.get("errors", []))
    return {
        "analysis_id": payload["analysis_id"], "severity": payload["severity"],
        "analysis_duration_ms": payload["duration_ms"], "geometry": payload["geometry"],
        "topology": topology, "surface_volume": payload["surface_volume"],
        "repair_issue_count": issue_count,
        "printability_state": "PASS_WITH_LIMITATIONS" if topology["watertight_state"] == "TOPOLOGICALLY_WATERTIGHT" else "REVIEW_REQUIRED",
        "warnings": payload.get("warnings", []), "errors": payload.get("errors", []),
        "skipped_check_reasons": payload.get("skipped_check_reasons", []),
    }


def _write_ascii_stl(obj, output: Path) -> None:
    mesh = obj.data
    mesh.calc_loop_triangles()
    matrix = obj.matrix_world
    lines = ["solid cgb_conditioned"]
    for triangle in mesh.loop_triangles:
        vertices = [matrix @ mesh.vertices[index].co for index in triangle.vertices]
        normal = (vertices[1] - vertices[0]).cross(vertices[2] - vertices[0]).normalized()
        lines.append(f"  facet normal {normal.x:.9g} {normal.y:.9g} {normal.z:.9g}")
        lines.append("    outer loop")
        for vertex in vertices:
            lines.append(f"      vertex {vertex.x:.9g} {vertex.y:.9g} {vertex.z:.9g}")
        lines.extend(("    endloop", "  endfacet"))
    lines.append("endsolid cgb_conditioned")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")


def main() -> int:
    args = _arguments()
    source_file_hash_before = _sha(args.source)
    timer = perf_counter()
    session = None
    try:
        source = _import(args.source)
        raw_result = analyze_mesh(source, bpy.context.scene, settings=AnalysisSettings(), blender_version=bpy.app.version_string, blend_file_path="")
        if raw_result.errors:
            raise RuntimeError("Raw Chroma3D analysis failed: " + "; ".join(raw_result.errors))
        repair_settings, analysis_settings = RepairSettings(), AnalysisSettings()
        session = start_session(
            source, bpy.context.scene, repair_settings, analysis_settings,
            blender_version=bpy.app.version_string, blend_file_path="",
        )
        workspace = next(item for item in bpy.data.objects if item.as_pointer() == session.workspace_object_identity)
        bpy.context.view_layer.objects.active = workspace
        workspace.select_set(True)
        plan = generate_repair_plan(session, bpy.context.scene, repair_settings, blend_file_path="", active_object=workspace)
        operations = tuple(item.value for item in plan.selected_operations())
        applied = ()
        if operations:
            applied = apply_repair_plan(
                session, bpy.context.scene, repair_settings, analysis_settings,
                blend_file_path="", active_object=workspace,
            )
        conditioned_result = get_current_analysis(session)
        if conditioned_result is None or conditioned_result.errors:
            raise RuntimeError("Conditioned Chroma3D analysis is unavailable.")
        _write_ascii_stl(workspace, args.conditioned_output)
        raw_summary, conditioned_summary = _summary(raw_result), _summary(conditioned_result)
        source_current = protected_source_is_current(source, session.source_snapshot, "")
        payload = {
            "schema_version": "1.0.0", "worker_version": WORKER_VERSION, "status": "PASS" if source_current else "ANALYSIS_FAILED",
            "blender_version": bpy.app.version_string, "source_file_sha256_before": source_file_hash_before,
            "source_file_sha256_after": _sha(args.source), "source_immutable": source_current and _sha(args.source) == source_file_hash_before,
            "raw_metrics": raw_summary, "conditioned_metrics": conditioned_summary,
            "selected_operations": list(operations),
            "operation_records": [{"operation": item.operation_type.value, "status": item.status.value} for item in applied],
            "conditioning_issue_reduction": int(raw_summary["repair_issue_count"]) - int(conditioned_summary["repair_issue_count"]),
            "conditioning_health_delta": {
                "boundary_edges": int(raw_summary["topology"]["boundary_edges"]) - int(conditioned_summary["topology"]["boundary_edges"]),
                "non_manifold_edges": int(raw_summary["topology"]["non_manifold_edges"]) - int(conditioned_summary["topology"]["non_manifold_edges"]),
                "connected_components": int(raw_summary["topology"]["connected_components"]) - int(conditioned_summary["topology"]["connected_components"]),
            },
            "conditioning_runtime_seconds": round(perf_counter() - timer, 6),
            "conditioned_artifact_format": "stl", "conditioned_artifact_sha256": _sha(args.conditioned_output),
            "limitations": [
                "Software-only Chroma3D diagnostics and safe repair plan on an isolated workspace.",
                "No slicer, G-code, physical print, manufacturing guarantee, or automatic candidate selection.",
            ],
        }
    except Exception as exc:
        payload = {
            "schema_version": "1.0.0", "worker_version": WORKER_VERSION, "status": "ANALYSIS_FAILED",
            "error_class": type(exc).__name__, "error": str(exc),
            "source_file_sha256_before": source_file_hash_before,
            "source_file_sha256_after": _sha(args.source),
        }
    finally:
        if session is not None:
            try:
                rollback_repair_session(session, blend_file_path="")
            except Exception as rollback_exc:
                payload["rollback_error"] = f"{type(rollback_exc).__name__}: {rollback_exc}"
                payload["status"] = "ANALYSIS_FAILED"
    args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
