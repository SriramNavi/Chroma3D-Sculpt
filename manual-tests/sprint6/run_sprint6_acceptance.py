"""Launch the Sprint 6 acceptance runner in factory-startup Blender."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--reuse-focused", action="store_true")
    args = parser.parse_args()
    runner = ROOT / "manual-tests" / "sprint6" / "sprint6_acceptance_runner.py"
    command = [str(args.blender), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(runner)]
    if args.reuse_focused:
        command.extend(["--", "--reuse-focused"])
    return subprocess.run(command, cwd=ROOT, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
