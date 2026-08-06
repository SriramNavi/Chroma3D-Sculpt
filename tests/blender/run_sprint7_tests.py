"""Run the focused Sprint 7 Blender suite and retain compact depth evidence."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
TEST_FILE = Path(__file__).with_name("test_sprint7_ai_recommendation.py")
if str(TEST_FILE.parent) not in sys.path:
    sys.path.insert(0, str(TEST_FILE.parent))


def main() -> int:
    tree = ast.parse(TEST_FILE.read_text(encoding="utf-8"))
    node = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == "Sprint7AIRecommendationTests")
    static_methods = sum(isinstance(item, ast.FunctionDef) and item.name.startswith("test_") for item in node.body)
    suite = unittest.defaultTestLoader.loadTestsFromName("test_sprint7_ai_recommendation.Sprint7AIRecommendationTests")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    payload = {
        "schema_version": "1.0.0", "status": "PASS" if result.wasSuccessful() else "FAIL",
        "recorded_at": datetime.now(timezone.utc).isoformat(), "static_test_methods": static_methods,
        "total_executable_tests": result.testsRun, "live_provider_calls": 0,
        "failures": [str(item[0]) for item in result.failures], "errors": [str(item[0]) for item in result.errors],
        "limitations": ["Provider-independent software evidence only; live provider, slicer and physical printing are not tested."],
    }
    target = ROOT / "manual-tests" / "sprint7" / "reports" / "sprint7_test_depth.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0 if result.wasSuccessful() and static_methods >= 42 else 1


if __name__ == "__main__":
    raise SystemExit(main())
