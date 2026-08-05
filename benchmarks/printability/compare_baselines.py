"""Compare two baseline manifests through the Blender-native comparator."""

from __future__ import annotations

import json
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]; ADDON_ROOT = REPOSITORY_ROOT / "blender_addon"
if str(ADDON_ROOT) not in sys.path: sys.path.insert(0, str(ADDON_ROOT))
from chroma3d_sculpt.services.printability_baseline import compare_baseline_manifests  # noqa: E402

def main() -> int:
    if len(sys.argv) < 3: raise SystemExit("Usage (inside Blender): compare_baselines.py BASELINE CURRENT [OUTPUT]")
    baseline = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")); current = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    comparisons = compare_baseline_manifests(baseline, current); output = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("baseline_comparison.json")
    output.write_text(json.dumps([item.to_dict() for item in comparisons], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    failed = sum(item.state.value == "FAIL" for item in comparisons); print(f"Compared {len(comparisons)} records; failures: {failed}"); return 1 if failed else 0
if __name__ == "__main__": raise SystemExit(main())
