"""Validate one bounded H2 suspicious-import removal batch."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
REPORT_ROOT = ROOT / "manual-tests" / "hardening" / "reports" / "h2" / "removal_batches"
BLENDER_DEFAULT = Path(r"D:\Softwares\Design\Blender\blender.exe")
FOCUSED_RUNNER = Path(__file__).resolve().with_name("run_focused_blender_tests.py")


def _run(command: list[str], name: str, timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command, cwd=ROOT, capture_output=True, check=False, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        timed_out = True
    log_path = REPORT_ROOT / "logs" / f"{name}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        stdout + ("\n" if stdout and stderr else "") + stderr,
        encoding="utf-8", newline="\n",
    )
    return {
        "returncode": returncode,
        "timed_out": timed_out,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "log": log_path.relative_to(ROOT).as_posix(),
        "stdout_tail": stdout.splitlines()[-8:],
        "stderr_tail": stderr.splitlines()[-8:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", required=True)
    parser.add_argument("--file", action="append", required=True)
    parser.add_argument("--test", action="append", required=True)
    parser.add_argument("--blender", type=Path, default=BLENDER_DEFAULT)
    args = parser.parse_args()
    if not 1 <= len(args.file) <= 3:
        parser.error("each H2 removal batch must contain 1-3 source files")
    missing = [value for value in (*args.file, *args.test) if not (ROOT / value).is_file()]
    if missing:
        parser.error("missing files: " + ", ".join(missing))
    if not args.blender.is_file():
        parser.error(f"Blender not found: {args.blender}")

    results: dict[str, Any] = {}
    results["compile"] = _run(
        [sys.executable, "-m", "py_compile", *args.file], f"{args.batch}_compile", 120,
    )
    results["analyzer_tests"] = _run(
        [
            sys.executable, "-m", "unittest",
            "manual-tests/hardening/h2/test_suspicious_reference_analyzer.py",
            "manual-tests/hardening/h2/test_structural_simplification.py",
        ],
        f"{args.batch}_analyzer_tests", 120,
    )
    blender_results = []
    for index, test in enumerate(args.test, 1):
        blender_results.append(_run([
            str(args.blender), "--background", "--factory-startup", "--python-exit-code", "1",
            "--python", str(FOCUSED_RUNNER), "--", test,
        ], f"{args.batch}_blender_{index}", 900))
    results["blender"] = blender_results
    results["diff_check"] = _run(["git", "diff", "--check"], f"{args.batch}_diff_check", 120)

    passed = all(
        result["returncode"] == 0
        for result in (results["compile"], results["analyzer_tests"], results["diff_check"], *blender_results)
    )
    report = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "batch": args.batch,
        "files": args.file,
        "focused_tests": args.test,
        "source_geometry_mutated_by_harness": False,
        "results": results,
        "status": "PASS" if passed else "FAIL",
    }
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_ROOT / f"{args.batch}.json"
    temporary = report_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(report_path)
    print(json.dumps({
        "batch": args.batch,
        "status": report["status"],
        "files": len(args.file),
        "blender_tests": len(blender_results),
        "blender_elapsed_seconds": round(sum(item["elapsed_seconds"] for item in blender_results), 6),
        "report": report_path.relative_to(ROOT).as_posix(),
    }, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
