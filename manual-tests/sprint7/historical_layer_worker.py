"""Discover one historical Blender test module without relying on its __main__."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests" / "blender"
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
filename = args[args.index("--test-file") + 1]
suite = unittest.defaultTestLoader.discover(str(TESTS), pattern=filename)
result = unittest.TextTestRunner(verbosity=1).run(suite)
print(f"HISTORICAL_LAYER_TESTS={result.testsRun}")
raise SystemExit(0 if result.wasSuccessful() else 1)
