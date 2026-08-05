"""Run one non-destructive Sprint 5 Dataset 1.0.0 worker in Blender."""

from __future__ import annotations

import argparse
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

from chroma3d_sculpt.optimization_settings import build_objective_snapshot  # noqa: E402
from chroma3d_sculpt.services.optimization_candidates import generate_candidates  # noqa: E402
from chroma3d_sculpt.services.optimization_comparison import compare_objects  # noqa: E402
from chroma3d_sculpt.services.optimization_coordinator import (  # noqa: E402
    apply_selected_step,
    discard_workspace,
    generate_session_candidates,
    generate_session_plan,
    start_session,
)
from chroma3d_sculpt.services.optimization_policy import default_policy, policy_hash  # noqa: E402
from chroma3d_sculpt.services.optimization_session import get_workspace  # noqa: E402
from chroma3d_sculpt.utilities.optimization_signatures import IMPLEMENTATION_FINGERPRINT, source_signature  # noqa: E402


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clear_scene() -> None:
    for obj in tuple(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in tuple(bpy.data.collections):
        if collection.users == 0:
            bpy.data.collections.remove(collection)


def parse_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--implementation-fingerprint", required=True)
    parser.add_argument("--mutation", action="store_true", help="Exercise one bounded workspace-only mutation before discard.")
    return parser.parse_args(raw)


def write_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    args = parse_args(); source_path = args.source.resolve(); started = perf_counter(); source_sha = file_sha256(source_path); session = None
    base: dict[str, object] = {
        "mesh": source_path.stem, "source_path": str(source_path), "source_sha256": source_sha,
        "implementation_fingerprint": args.implementation_fingerprint, "runtime_implementation_fingerprint": IMPLEMENTATION_FINGERPRINT,
        "dataset_version": "1.0.0", "blender_version": bpy.app.version_string, "completed_at": utcnow(),
    }
    try:
        clear_scene()
        result = bpy.ops.wm.stl_import(filepath=str(source_path))
        if "FINISHED" not in result:
            raise RuntimeError(f"STL import returned {result}")
        objects = [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]
        if len(objects) != 1:
            raise RuntimeError(f"Expected one imported mesh, found {len(objects)}")
        source = objects[0]
        before = source_signature(source)
        policy = default_policy(); objectives = build_objective_snapshot(); process_context_hash = sha256(b"Sprint5-Dataset-Process-Context-1.0").hexdigest(); feature_flag_hash = sha256(b"Sprint5-Dataset-Feature-Flags-1.0").hexdigest()
        session = start_session(source, bpy.context.scene, policy=policy, process_context_hash=process_context_hash, feature_flag_hash=feature_flag_hash)
        candidates = generate_session_candidates(session, source=source, policy=policy, build_volume_mm=(256.0, 256.0, 256.0))
        plan = generate_session_plan(session, policy=policy)
        comparison = compare_objects(source, get_workspace(session), build_volume_mm=(256.0, 256.0, 256.0), objectives=objectives)
        candidate_hash = sha256(json.dumps([item.to_dict() for item in candidates], sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        mutation_result: dict[str, object] = {"status": "NOT_RUN"}
        if args.mutation:
            orientation = next(
                (
                    item
                    for item in candidates
                    if item.category.value == "ORIENTATION"
                    and any(abs(float(value)) > 1e-6 for value in item.transform.rotation_euler)
                ),
                None,
            )
            if orientation is None:
                raise RuntimeError("Representative mutation requires a bounded non-zero orientation candidate.")
            record = apply_selected_step(session, source, orientation.candidate_id, approved=True, policy=policy)
            if record.state.value not in {"APPLIED", "FAILED", "NO_CHANGE"}:
                raise RuntimeError(f"Representative mutation returned unexpected state {record.state.value}.")
            mutation_result = {"status": record.state.value, "candidate_id": orientation.candidate_id, "source_immutable_during_preview": True}
        discard_workspace(session)
        after = source_signature(source)
        if before["source_signature"] != after["source_signature"]:
            raise RuntimeError("Dataset source signature changed during non-destructive workflow")
        if file_sha256(source_path) != source_sha:
            raise RuntimeError("Dataset source file hash changed")
        base.update({
            "worker_status": "PASS", "workflow_mode": "representative_mutation" if args.mutation else "full_non_destructive", "process_context_hash": process_context_hash, "feature_flag_hash": feature_flag_hash,
            "policy_hash": policy_hash(policy), "objective_hash": objectives.objective_hash, "candidate_set_hash": candidate_hash,
            "candidate_count": len(candidates), "plan_count": len(plan.steps), "comparison": comparison.to_dict(),
            "source_signature_before": before["source_signature"], "source_signature_after": after["source_signature"],
            "source_immutable": True, "timing_seconds": round(perf_counter() - started, 6),
            "mutation": mutation_result,
            "skipped_or_indeterminate": list(comparison.skipped_checks) + list(comparison.indeterminate_checks),
        })
        write_atomic(args.output, base); clear_scene(); return 0
    except Exception as exc:
        base.update({"worker_status": "ERROR", "error": f"{type(exc).__name__}: {exc}", "source_immutable": False, "timing_seconds": round(perf_counter() - started, 6)})
        write_atomic(args.output, base)
        try:
            if session is not None:
                discard_workspace(session)
        except Exception:
            pass
        clear_scene(); raise


if __name__ == "__main__":
    raise SystemExit(main())
