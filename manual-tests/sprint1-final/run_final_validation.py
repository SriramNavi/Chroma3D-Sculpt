"""Launch the independent Sprint 1 validation runner in factory-startup Blender."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_DIRECTORY = Path(__file__).resolve().parent
SCRIPTS_DIRECTORY = REPOSITORY_ROOT / "scripts"
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from find_blender import discover_blender  # noqa: E402


DEFAULT_BLENDER = Path(r"D:\Softwares\Design\Blender\blender.exe")
RUNNER_PATH = VALIDATION_DIRECTORY / "final_validation_runner.py"
LOG_PATH = VALIDATION_DIRECTORY / "logs" / "blender_final_validation.log"


def _branch() -> str:
    completed = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "Unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, help="Path to blender.exe")
    args = parser.parse_args()

    requested = args.blender
    if requested is None and DEFAULT_BLENDER.is_file():
        requested = DEFAULT_BLENDER
    discovery = discover_blender(requested)
    if discovery is None:
        print("Blender was not found. Pass --blender or configure project discovery.", file=sys.stderr)
        return 2

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["CHROMA3D_VALIDATION_BRANCH"] = _branch()
    environment["CHROMA3D_VALIDATION_BLENDER"] = str(discovery.executable)
    command = [
        str(discovery.executable),
        "--background",
        "--factory-startup",
        "--python-exit-code",
        "1",
        "--python",
        str(RUNNER_PATH),
    ]
    completed = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    log_text = completed.stdout
    if completed.stderr:
        log_text += "\n[stderr]\n" + completed.stderr
    LOG_PATH.write_text(log_text, encoding="utf-8", newline="\n")

    summary_lines = [
        line
        for line in completed.stdout.splitlines()
        if line.startswith(("[PASS]", "[FAIL]", "Overall:", "Recommendation:", "Report:"))
    ]
    print(f"Blender: {discovery.executable} ({discovery.version})")
    print("\n".join(summary_lines[-20:]))
    print(f"Log: {LOG_PATH}")
    if completed.returncode:
        print(f"Final validation failed with exit code {completed.returncode}.", file=sys.stderr)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
