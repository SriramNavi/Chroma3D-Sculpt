"""Run the retained installed-package smoke with H2-isolated report paths."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "manual-tests" / "sprint7-final" / "run_installed_package_smoke.py"
REPORTS = ROOT / "manual-tests" / "hardening" / "reports" / "h2" / "installed_smoke"
ARTIFACTS = ROOT / "manual-tests" / "hardening" / "reports" / "h2" / "installed_smoke_artifacts"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender", type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("h2_retained_installed_smoke", SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {SOURCE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.REPORTS = REPORTS
    module.ARTIFACTS = ARTIFACTS
    previous = sys.argv[:]
    try:
        sys.argv = [str(SOURCE), "--blender", str(args.blender)]
        return int(module.main())
    finally:
        sys.argv = previous


if __name__ == "__main__":
    raise SystemExit(main())
