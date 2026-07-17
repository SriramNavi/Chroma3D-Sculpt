"""Discover and run every Blender background unittest fixture."""

from pathlib import Path
import sys
import unittest


TEST_DIRECTORY = Path(__file__).resolve().parent
if str(TEST_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(TEST_DIRECTORY))

suite = unittest.defaultTestLoader.discover(str(TEST_DIRECTORY), pattern="test_*.py")
outcome = unittest.TextTestRunner(verbosity=2).run(suite)
if not outcome.wasSuccessful():
    raise SystemExit(1)
print(f"Chroma3D Blender tests passed: {outcome.testsRun}")
