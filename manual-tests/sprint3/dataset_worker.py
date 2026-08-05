"""Analyze one Dataset 1.0.0 STL in an isolated Blender process."""

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

from chroma3d_sculpt.models.printability_models import PrintabilityMode  # noqa: E402
from chroma3d_sculpt.printability_settings import PrintabilitySettings  # noqa: E402
from chroma3d_sculpt.services.printability_coordinator import analyze_printability  # noqa: E402
from chroma3d_sculpt.services.printer_profile_loader import load_profile  # noqa: E402
from chroma3d_sculpt.utilities.printability_signatures import printability_source_snapshot  # noqa: E402


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--implementation-fingerprint", required=True)
    return parser.parse_args(arguments)


def write_result(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    started = perf_counter()
    base: dict[str, object] = {
        "mesh": source.stem,
        "source_path": str(source),
        "source_sha256": file_sha256(source),
        "implementation_fingerprint": args.implementation_fingerprint,
        "profile_id": "generic_fdm",
        "performance_mode": "FAST",
        "blender_version": bpy.app.version_string,
        "completed_at": utcnow(),
    }
    try:
        imported = bpy.ops.wm.stl_import(filepath=str(source))
        if "FINISHED" not in imported:
            raise RuntimeError(f"STL import returned {imported}")
        objects = [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]
        if len(objects) != 1:
            raise RuntimeError(f"Expected one imported mesh, found {len(objects)}")
        obj = objects[0]
        before = printability_source_snapshot(obj)
        result = analyze_printability(
            obj,
            bpy.context.scene,
            load_profile("generic_fdm"),
            PrintabilitySettings(mode=PrintabilityMode.FAST),
            blender_version=bpy.app.version_string,
        )
        after = printability_source_snapshot(obj)
        if before["printability_sha256"] != after["printability_sha256"]:
            raise RuntimeError("Imported source state changed during printability analysis")
        if file_sha256(source) != base["source_sha256"]:
            raise RuntimeError("Dataset source file hash changed")
        base.update({
            "worker_status": "PASS",
            "score_status": result.score_details.status.value,
            "confidence": result.score_details.confidence.value,
            "score": result.score_details.score,
            "check_states": {item["check"]: item.get("status", "UNKNOWN") for item in result.check_results()},
            "analysis_duration_seconds": result.timings["total"],
            "worker_duration_seconds": perf_counter() - started,
            "source_immutable": True,
        })
        write_result(args.output, base)
        return 0
    except Exception as exc:
        base.update({
            "worker_status": "ERROR",
            "error": f"{type(exc).__name__}: {exc}",
            "worker_duration_seconds": perf_counter() - started,
            "source_immutable": False,
        })
        write_result(args.output, base)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
