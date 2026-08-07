"""Shared path/bootstrap helpers for the standalone G0 unittest suite."""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATIVE_ROOT = PROJECT_ROOT / "benchmarks" / "generative"
TOOLS_ROOT = GENERATIVE_ROOT / "tools"
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"

for path in (GENERATIVE_ROOT, TOOLS_ROOT, SCRIPTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def tetrahedron():
    from mesh_io import Mesh

    return Mesh(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        ((0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)),
    )
