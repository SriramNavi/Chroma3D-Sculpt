"""Blender-free regression tests for H2 private structural simplifications."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "blender_addon" / "chroma3d_sculpt" / "services" / "printability_statistics.py"
SPEC = importlib.util.spec_from_file_location("h2_printability_statistics", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load printability statistics helper")
STATISTICS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STATISTICS)


class StructuralSimplificationTests(unittest.TestCase):
    def test_empty_percentiles_preserve_empty_evidence(self) -> None:
        self.assertEqual(STATISTICS.percentiles([]), {})

    def test_percentile_labels_and_rounding_are_frozen(self) -> None:
        values = [4.0, 1.0, 2.0, 3.0]
        self.assertEqual(
            STATISTICS.percentiles(values),
            {"p05": 1.0, "p25": 2.0, "p50": 3.0, "p75": 3.0, "p95": 4.0},
        )
        self.assertEqual(values, [4.0, 1.0, 2.0, 3.0])

    def test_single_value_populates_every_frozen_label(self) -> None:
        self.assertEqual(
            STATISTICS.percentiles([2.5]),
            {"p05": 2.5, "p25": 2.5, "p50": 2.5, "p75": 2.5, "p95": 2.5},
        )


if __name__ == "__main__":
    unittest.main()
