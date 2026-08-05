"""Generate Printability Baseline 1.0.0 from validated Sprint 4 dataset workers.

Run this script with Blender 4.4+ in background mode. It never loads or changes
the source meshes; it consumes only retained worker records and their hashes.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

import bpy


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]; ADDON_ROOT = REPOSITORY_ROOT / "blender_addon"
if str(ADDON_ROOT) not in sys.path: sys.path.insert(0, str(ADDON_ROOT))
from chroma3d_sculpt.feature_flags import build_feature_flags  # noqa: E402
from chroma3d_sculpt.models.advanced_preparation_models import PrintabilityBaselineRecord  # noqa: E402
from chroma3d_sculpt.services.hardware_profile_loader import load_hardware_profile  # noqa: E402
from chroma3d_sculpt.services.material_profile_loader import load_material_profile  # noqa: E402
from chroma3d_sculpt.services.printability_baseline import generate_baseline_manifest, write_baseline_manifest  # noqa: E402
from chroma3d_sculpt.services.process_context import compose_process_context  # noqa: E402


def file_sha(path: Path) -> str: return sha256(path.read_bytes()).hexdigest()
def main() -> int:
    report = json.loads((REPOSITORY_ROOT / "manual-tests" / "sprint4" / "reports" / "dataset_regression.json").read_text(encoding="utf-8"))
    if report.get("status") != "PASS" or report.get("completed_meshes") != 27: raise RuntimeError("A complete validated 27-model Sprint 4 dataset report is required.")
    records = []
    for worker in report["results"]:
        raw = dict(worker["baseline_record"]); raw["orientation_candidates"] = tuple(raw["orientation_candidates"]); raw["limitations"] = tuple(raw["limitations"])
        records.append(PrintabilityBaselineRecord(**raw))
    hardware = load_hardware_profile("bambu_x1_carbon"); material = load_material_profile("generic_pla")
    process = compose_process_context(hardware, material, nozzle_mm=0.4, layer_height_mm=0.2, build_plate_type="TEXTURED")
    dataset_manifest = REPOSITORY_ROOT / "datasets" / "statues" / "manifests" / "statue_dataset_manifest.json"
    golden_manifest = REPOSITORY_ROOT / "benchmarks" / "golden" / "manifests" / "golden_manifest.json"
    baseline = generate_baseline_manifest(records, process, build_feature_flags(), blender_version=bpy.app.version_string,
        dataset_manifest_sha256=file_sha(dataset_manifest), golden_manifest_sha256=file_sha(golden_manifest), status="VALIDATED", generated_at=report["updated_at"])
    output = Path(__file__).with_name("baseline_manifest.json"); write_baseline_manifest(baseline, output); print(f"Baseline records: {len(records)} -> {output}"); return 0
if __name__ == "__main__": raise SystemExit(main())
