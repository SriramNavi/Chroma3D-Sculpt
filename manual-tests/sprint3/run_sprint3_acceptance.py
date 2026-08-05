"""Launch the Sprint 3 acceptance runner in Blender 4.4+ background mode."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = REPOSITORY_ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from find_blender import discover_blender  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, help="Explicit path to blender.exe")
    parser.add_argument("--dataset-timeout-seconds", type=int, default=600)
    parser.add_argument("--skip-dataset", action="store_true", help="Reuse the retained dataset report.")
    args = parser.parse_args()
    discovery = discover_blender(args.blender)
    if discovery is None:
        print("Blender was not found.", file=sys.stderr)
        return 2
    if not args.skip_dataset:
        dataset_runner = Path(__file__).with_name("run_dataset_regression.py")
        dataset_command = [
            sys.executable, str(dataset_runner), "--blender", str(discovery.executable),
            "--timeout-seconds", str(args.dataset_timeout_seconds),
        ]
        dataset_completed = subprocess.run(dataset_command, cwd=REPOSITORY_ROOT, check=False)
        if dataset_completed.returncode != 0:
            print("Dataset regression completed with a failure or explicit runtime limit; acceptance will retain that limitation.")
    runner = Path(__file__).with_name("sprint3_acceptance_runner.py")
    log = Path(__file__).with_name("logs") / "blender_sprint3_acceptance.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    command = [str(discovery.executable), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(runner)]
    completed = subprocess.run(command, cwd=REPOSITORY_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    log.write_text(completed.stdout, encoding="utf-8", newline="\n")
    print(completed.stdout)
    print(f"Blender log: {log}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
