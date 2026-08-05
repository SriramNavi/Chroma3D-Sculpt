"""Generate one Bambu X1 Carbon engine-evidence pair in isolated Blender."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

import bpy


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ADDON_ROOT = REPOSITORY_ROOT / "blender_addon"
if str(ADDON_ROOT) not in sys.path:
    sys.path.insert(0, str(ADDON_ROOT))

from chroma3d_sculpt.models.printability_models import PrintabilityMode  # noqa: E402
from chroma3d_sculpt.printability_settings import PrintabilitySettings  # noqa: E402
from chroma3d_sculpt.services.printability_coordinator import analyze_printability  # noqa: E402
from chroma3d_sculpt.services.printability_report import write_printability_json, write_printability_markdown  # noqa: E402
from chroma3d_sculpt.services.printer_profile_loader import load_profile  # noqa: E402
from chroma3d_sculpt.utilities.printability_signatures import printability_source_snapshot  # noqa: E402


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--implementation-fingerprint", required=True)
    return parser.parse_args(values)


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    source_hash = file_sha256(source)
    payload: dict[str, object] = {
        "status": "FAIL", "source_path": str(source), "source_sha256": source_hash,
        "implementation_fingerprint": args.implementation_fingerprint,
        "profile_id": "bambu_x1_carbon", "mode": "FAST", "blender_version": bpy.app.version_string,
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
            obj, bpy.context.scene, load_profile("bambu_x1_carbon"),
            PrintabilitySettings(mode=PrintabilityMode.FAST), blender_version=bpy.app.version_string,
        )
        after = printability_source_snapshot(obj)
        if before["printability_sha256"] != after["printability_sha256"]:
            raise RuntimeError("Source changed during physical prediction analysis")
        if file_sha256(source) != source_hash:
            raise RuntimeError("Dataset source hash changed")
        write_printability_json(result, args.output_json)
        write_printability_markdown(result, args.output_markdown)
        payload.update({
            "status": "PASS", "score": result.score_details.score,
            "score_status": result.score_details.status.value,
            "confidence": result.score_details.confidence.value,
            "check_states": {item["check"]: item.get("status", "UNKNOWN") for item in result.check_results()},
            "critical_risks": [item.message for item in result.risk_items if item.state.value == "CRITICAL"],
            "warning_risks": [item.message for item in result.risk_items if item.state.value == "WARNING"],
            "skipped_checks": [item["check"] for item in result.score_details.skipped_checks + result.score_details.missing_checks + result.score_details.failed_checks],
            "analysis_duration_seconds": result.timings["total"], "source_immutable": True,
        })
    except Exception as exc:
        payload["error"] = f"{type(exc).__name__}: {exc}"
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.metadata.with_suffix(args.metadata.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(args.metadata)
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
