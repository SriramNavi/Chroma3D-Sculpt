from __future__ import annotations

import unittest

from _support import tetrahedron
from evaluate_geometry import align_and_compare
from mesh_io import Mesh


class AlignmentTests(unittest.TestCase):
    def test_translation_rotation_and_uniform_scale_are_deterministic(self) -> None:
        ground_truth = tetrahedron()
        generated = Mesh(
            tuple((10.0 + 3.0 * y, -4.0 - 3.0 * x, 7.0 + 3.0 * z) for x, y, z in ground_truth.vertices),
            ground_truth.faces,
        )
        first, _, _ = align_and_compare(ground_truth, generated)
        second, _, _ = align_and_compare(ground_truth, generated)
        self.assertEqual(first, second)
        self.assertEqual(first["method"], "bounded_24_orientation_uniform_scale_v1")
        self.assertAlmostEqual(first["normalized_symmetric_chamfer"], 0.0, places=12)
        self.assertAlmostEqual(first["uniform_scale"], 1.0 / 3.0)

    def test_zero_diagonal_is_alignment_indeterminate(self) -> None:
        degenerate = Mesh(((0.0, 0.0, 0.0),) * 3, ((0, 1, 2),))
        with self.assertRaisesRegex(ValueError, "ALIGNMENT_INDETERMINATE"):
            align_and_compare(tetrahedron(), degenerate)


if __name__ == "__main__":
    unittest.main()
