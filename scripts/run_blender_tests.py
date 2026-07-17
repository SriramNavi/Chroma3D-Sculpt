"""Run all Blender unittest fixtures inside a factory-startup Blender process."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

from _project import REPOSITORY_ROOT
from find_blender import discover_blender


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, help="Explicit path to blender.exe")
    args = parser.parse_args()
    discovery = discover_blender(args.blender)
    if discovery is None:
        print("Blender was not found. Set BLENDER_EXECUTABLE or pass --blender.", file=sys.stderr)
        return 2

    test_file = REPOSITORY_ROOT / "tests" / "blender" / "run_all_tests.py"
    command = [
        str(discovery.executable),
        "--background",
        "--factory-startup",
        "--python-exit-code",
        "1",
        "--python",
        str(test_file),
    ]
    print(f"Blender: {discovery.executable} ({discovery.version})")
    print(f"Test file: {test_file}")
    completed = subprocess.run(command, cwd=REPOSITORY_ROOT, check=False)
    if completed.returncode:
        print(f"Blender background tests failed with exit code {completed.returncode}.", file=sys.stderr)
        return completed.returncode
    print("Blender background tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
