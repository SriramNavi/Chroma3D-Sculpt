"""Run the retained lifecycle worker with H4-specific fail-closed checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BLENDER = Path(r"D:\Softwares\Design\Blender\blender.exe")
WORKER = ROOT / "manual-tests" / "hardening" / "measure_resource_lifecycle.py"
LOG = ROOT / "manual-tests" / "hardening" / "h4" / "logs" / "lifecycle.log"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, default=DEFAULT_BLENDER)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=5)
    args = parser.parse_args()
    completed = subprocess.run(
        [
            str(args.blender), "--background", "--factory-startup", "--python-exit-code", "1",
            "--python", str(WORKER), "--", "--output", str(args.output.resolve()),
            "--iterations", str(args.iterations),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(completed.stdout + "\n--- STDERR ---\n" + completed.stderr, encoding="utf-8", newline="\n")
    report = json.loads(args.output.read_text(encoding="utf-8")) if args.output.is_file() else {}
    counts = report.get("classification_counts", {})
    passed = all((
        completed.returncode == 0,
        report.get("status") == "PASS",
        report.get("protected_source_unchanged") is True,
        counts.get("CONFIRMED_LEAK") == 0,
        counts.get("LIKELY_LEAK") == 0,
        counts.get("SUSPICIOUS_RETENTION") == 0,
        not report.get("failures"),
        not report.get("findings"),
    ))
    print(json.dumps({
        "status": "PASS" if passed else "FAIL",
        "records": len(report.get("records", ())),
        "classification_counts": counts,
        "protected_source_unchanged": report.get("protected_source_unchanged"),
    }, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
