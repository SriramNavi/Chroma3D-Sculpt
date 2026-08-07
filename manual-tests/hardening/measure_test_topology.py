"""Count the current cumulative Blender test topology without executing tests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import unittest

import bpy


ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = ROOT / "tests" / "blender"
MODULES = {
    "Sprint 0": "test_mesh_analysis",
    "Sprint 1": "test_sprint1_diagnostics",
    "Sprint 2": "test_sprint2_repair",
    "Sprint 3": "test_sprint3_printability",
    "Sprint 4": "test_sprint4_advanced_preparation",
    "Sprint 5": "test_sprint5_controlled_optimization",
    "Sprint 6": "test_sprint6_intelligent_optimization",
    "Sprint 7": "test_sprint7_ai_recommendation",
}


def main() -> int:
    values = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(values)
    sys.path.insert(0, str(TEST_ROOT))
    counts = {}
    for sprint, module in MODULES.items():
        suite = unittest.defaultTestLoader.loadTestsFromName(module)
        counts[sprint] = suite.countTestCases()
    payload = {
        "schema_version": "1.0.0",
        "status": "PASS",
        "blender_version": bpy.app.version_string,
        "counts": counts,
        "combined_count": sum(counts.values()),
        "definition": "Current cumulative test modules loaded by the combined Blender discovery suite.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
