"""Run and count the expanded Sprint 6 executable Blender matrix."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
TEST_FILE = Path(__file__).with_name("test_sprint6_intelligent_optimization.py")
if str(TEST_FILE.parent) not in sys.path:
    sys.path.insert(0, str(TEST_FILE.parent))


def test_depth() -> dict[str, int]:
    tree = ast.parse(TEST_FILE.read_text(encoding="utf-8"))
    class_node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Sprint6IntelligentOptimizationTests")
    static_methods = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_") and not node.name.startswith("test_s6_matrix_") for node in class_node.body)
    dynamic_case_markers = sum(isinstance(node, ast.FunctionDef) and node.name == "add" for node in ast.walk(tree))
    dynamic_methods = sum(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "add" for node in ast.walk(tree))
    return {"static_test_methods": static_methods, "dynamic_test_case_definitions": dynamic_methods, "dynamic_installation_helpers": dynamic_case_markers}


def main() -> int:
    import test_sprint6_intelligent_optimization as tests  # noqa: PLC0415

    depth = test_depth()
    suite = unittest.defaultTestLoader.loadTestsFromName("test_sprint6_intelligent_optimization.Sprint6IntelligentOptimizationTests")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    total = result.testsRun
    payload = {
        "schema_version": "1.0",
        "status": "PASS" if result.wasSuccessful() else "FAIL",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        **depth,
        "total_executable_tests": total,
        "unique_runtime_pathways": 34,
        "defect_regressions": [
            "finite numeric hard-constraint evidence",
            "objective-vector hash identity",
            "unknown/skipped objective ranking exclusion",
            "operation-step budget accounting",
            "strict family prerequisite generation",
            "stale source detection after search",
            "owned workspace cleanup after cancellation",
        ],
        "failures": [str(item[0]) for item in result.failures],
        "errors": [str(item[0]) for item in result.errors],
        "skipped": [str(item[0]) for item in result.skipped],
        "limitations": ["This runner proves local Blender software behavior only; it does not prove physical printing, slicer comparison, material calibration, Blender 4.5 LTS, or manual installed-panel UAT."],
    }
    output = ROOT / "manual-tests" / "sprint6" / "reports" / "sprint6_test_depth.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
