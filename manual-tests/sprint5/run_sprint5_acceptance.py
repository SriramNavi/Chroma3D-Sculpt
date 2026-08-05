"""Run focused Sprint 5 acceptance in Blender after compilation and packaging."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))
from find_blender import discover_blender  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path)
    args = parser.parse_args()
    discovery = discover_blender(args.blender)
    if discovery is None:
        print("Blender was not found.", file=sys.stderr)
        return 2
    checks = [
        [sys.executable, "-m", "compileall", "-q", "blender_addon", "scripts", "tests", "manual-tests"],
        [sys.executable, str(SCRIPT_ROOT / "package_extension.py")],
    ]
    for command in checks:
        if subprocess.run(command, cwd=ROOT, check=False).returncode:
            return 1
    runner = Path(__file__).with_name("sprint5_acceptance_runner.py")
    log = Path(__file__).with_name("logs") / "blender_sprint5_acceptance.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run([str(discovery.executable), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(runner)], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    log.write_text(completed.stdout, encoding="utf-8", newline="\n")
    print(completed.stdout)
    print(f"Blender log: {log}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
