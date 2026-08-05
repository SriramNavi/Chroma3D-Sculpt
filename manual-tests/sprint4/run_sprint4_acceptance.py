"""Run Dataset 1.0.0 workers, build the package, and launch Sprint 4 Blender acceptance."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]; SCRIPT_ROOT = REPOSITORY_ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path: sys.path.insert(0, str(SCRIPT_ROOT))
from find_blender import discover_blender  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--blender", type=Path); parser.add_argument("--dataset-timeout-seconds", type=int, default=900)
    parser.add_argument("--skip-dataset", action="store_true"); args = parser.parse_args(); discovery = discover_blender(args.blender)
    if discovery is None: print("Blender was not found.", file=sys.stderr); return 2
    if not args.skip_dataset:
        dataset = subprocess.run([sys.executable, str(Path(__file__).with_name("run_dataset_regression.py")), "--blender", str(discovery.executable), "--timeout-seconds", str(args.dataset_timeout_seconds)], cwd=REPOSITORY_ROOT, check=False)
        if dataset.returncode: return dataset.returncode
    package = subprocess.run([sys.executable, str(SCRIPT_ROOT / "package_extension.py")], cwd=REPOSITORY_ROOT, check=False)
    if package.returncode: return package.returncode
    runner = Path(__file__).with_name("sprint4_acceptance_runner.py"); log = Path(__file__).with_name("logs") / "blender_sprint4_acceptance.log"; log.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run([str(discovery.executable), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(runner)], cwd=REPOSITORY_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    log.write_text(completed.stdout, encoding="utf-8", newline="\n"); print(completed.stdout); print(f"Blender log: {log}"); return completed.returncode


if __name__ == "__main__": raise SystemExit(main())
