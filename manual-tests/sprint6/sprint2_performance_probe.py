"""Run the unchanged Sprint 2 S2F-I fixture alone inside factory Blender."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
from time import perf_counter
import traceback

import bpy


ROOT = Path(__file__).resolve().parents[2]
SPRINT2_RUNNER = ROOT / "manual-tests" / "sprint2-final" / "final_validation_runner.py"


def _arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(values)


def _load_runner():
    spec = importlib.util.spec_from_file_location("chroma3d_sprint2_final_probe", SPRINT2_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load Sprint 2 runner: {SPRINT2_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    args = _arguments()
    started = perf_counter()
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "gate": "S2F-I",
        "fixture": "unchanged realistic surface repair stress",
        "status": "FAIL",
        "threshold_seconds": 60.0,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "blender_version": bpy.app.version_string,
    }
    module = None
    registered = False
    try:
        module = _load_runner()
        module._reset_scene()
        bpy.context.scene.unit_settings.system = "METRIC"
        bpy.context.scene.unit_settings.length_unit = "MILLIMETERS"
        bpy.context.scene.unit_settings.scale_length = 1.0
        module.addon.register()
        registered = True
        metrics = module._gate_realistic_stress()
        payload.update({
            "status": "PASS",
            "metrics": metrics,
            "source_immutability": metrics.get("source_unchanged") is True,
        })
    except Exception as exc:
        payload.update({
            "error": f"{type(exc).__name__}: {exc}",
            "traceback_tail": traceback.format_exc()[-4000:],
        })
    finally:
        if module is not None:
            try:
                module._reset_scene()
            except Exception:
                pass
            if registered:
                try:
                    module.addon.unregister()
                except Exception:
                    pass
        payload["elapsed_seconds"] = round(perf_counter() - started, 6)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(json.dumps({
            "gate": payload["gate"],
            "status": payload["status"],
            "elapsed_seconds": payload["elapsed_seconds"],
            "repair_batch_seconds": payload.get("metrics", {}).get("repair_batch_seconds") if isinstance(payload.get("metrics"), dict) else None,
            "output": str(args.output),
        }, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
