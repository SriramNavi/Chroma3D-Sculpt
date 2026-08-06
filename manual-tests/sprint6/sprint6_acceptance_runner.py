"""Run the focused Sprint 6 Blender acceptance matrix and retain evidence."""

from __future__ import annotations

from datetime import datetime, timezone
import argparse
from pathlib import Path
import json
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests" / "blender"
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))


def main() -> int:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-focused", action="store_true")
    args = parser.parse_args(values)
    depth_path = ROOT / "manual-tests" / "sprint6" / "reports" / "sprint6_test_depth.json"
    depth = json.loads(depth_path.read_text(encoding="utf-8")) if depth_path.is_file() else {}
    if args.reuse_focused:
        matrix_exit = 0 if depth.get("status") == "PASS" and depth.get("total_executable_tests", 0) >= 222 else 1
    else:
        from run_sprint6_tests import main as run_expanded_matrix

        matrix_exit = run_expanded_matrix()

    def evidence_status(path: Path, *, pass_status: tuple[str, ...] = ("PASS",)) -> str:
        if not path.is_file():
            return "NOT_EVALUATED"
        try:
            value = json.loads(path.read_text(encoding="utf-8")).get("status")
        except (OSError, json.JSONDecodeError):
            return "FAIL"
        if value in pass_status:
            return "PASS"
        if value in {"NOT_EVALUATED", "INDETERMINATE"}:
            return value
        return "FAIL"

    representative_status = evidence_status(ROOT / "manual-tests" / "sprint6" / "reports" / "dataset" / "representative_dataset_results.json")
    full_status = evidence_status(ROOT / "manual-tests" / "sprint6" / "reports" / "dataset" / "sprint6_dataset_results.json")
    historical_status = evidence_status(
        ROOT / "manual-tests" / "sprint6" / "reports" / "historical_regression.json",
        pass_status=("PASS", "PASS_WITH_LIMITATIONS"),
    )
    final_status = evidence_status(ROOT / "manual-tests" / "sprint6-final" / "reports" / "final_validation_results.json", pass_status=("PASS", "PASS_WITH_LIMITATIONS"))
    gates = {
        **{f"S6-{index:02d}": "PASS" if matrix_exit == 0 else "FAIL" for index in range(1, 14)},
        "S6-14": representative_status,
        "S6-15": full_status,
        "S6-16": historical_status,
        "S6-17": final_status,
    }
    failed = [gate for gate, status in gates.items() if status == "FAIL"]
    pending = [gate for gate, status in gates.items() if status in {"NOT_EVALUATED", "INDETERMINATE"}]
    payload = {
        "schema_version": "1.0",
        "milestone": "Sprint 6 - Intelligent Optimization",
        "status": "FAIL" if failed else ("INDETERMINATE" if pending else "PASS_WITH_LIMITATIONS"),
        "tests_run": depth.get("total_executable_tests", 0),
        "test_depth": depth,
        "gates": gates,
        "failed_gates": failed,
        "pending_gates": pending,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "limitations": ["Physical printing, slicer comparison, material calibration, Blender 4.5 LTS, and installed-panel UAT are not covered by this software runner."],
    }
    output = ROOT / "manual-tests" / "sprint6" / "reports" / "sprint6_acceptance.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
