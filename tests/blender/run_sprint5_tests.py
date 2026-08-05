"""Run only the Sprint 5 Blender background test module."""

from pathlib import Path
import sys
import unittest

TEST_DIRECTORY = Path(__file__).resolve().parent
if str(TEST_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(TEST_DIRECTORY))

suite = unittest.defaultTestLoader.loadTestsFromName("test_sprint5_controlled_optimization")
outcome = unittest.TextTestRunner(verbosity=2).run(suite)
if not outcome.wasSuccessful():
    raise SystemExit(1)
print(f"Sprint 5 Blender tests passed: {outcome.testsRun}")
