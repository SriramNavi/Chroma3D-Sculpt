"""Generate the dependency-free local HTML dashboard inside Blender."""

from __future__ import annotations

import json
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]; ADDON_ROOT = REPOSITORY_ROOT / "blender_addon"
if str(ADDON_ROOT) not in sys.path: sys.path.insert(0, str(ADDON_ROOT))
from chroma3d_sculpt.services.printability_baseline import compare_baseline_manifests  # noqa: E402
from chroma3d_sculpt.services.regression_dashboard import dashboard_html, write_dashboard  # noqa: E402

def main() -> int:
    baseline_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("baseline_manifest.json")
    current_path = Path(sys.argv[2]) if len(sys.argv) > 2 else baseline_path; baseline = json.loads(baseline_path.read_text(encoding="utf-8")); current = json.loads(current_path.read_text(encoding="utf-8"))
    process = current["process_context"]
    profile_context = f"{process['hardware_profile']['profile_id']} + {process['material_profile']['profile_id']} + {process['context_hash']}"
    html = dashboard_html(compare_baseline_manifests(baseline, current), software_version=current["software"]["extension_version"], dataset_version=current["dataset"]["version"], baseline_version=current["baseline_version"], profile_context=profile_context, generated_at=current["generated_at"], evidence_links=("../baseline_manifest.json",), model_records=tuple(current["records"]))
    output = Path(__file__).with_name("dashboard") / "printability_regression.html"; write_dashboard(html, output); print(output); return 0
if __name__ == "__main__": raise SystemExit(main())
