from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from _support import tetrahedron
from blind_review import anonymize
from evaluate_geometry import evaluate_geometry, geometry_health
from evaluate_silhouettes import evaluate_silhouettes
from generate_report import PROJECT_DEFAULT, generate, pareto_frontier, validate_weights
from mesh_io import Mesh, load_mesh


class GeometryMetricTests(unittest.TestCase):
    def test_identical_mesh_has_exact_primary_fidelity(self) -> None:
        mesh = tetrahedron()
        result = evaluate_geometry(mesh, mesh)
        fidelity = result["shape_fidelity"]
        self.assertEqual(result["status"], "PASS")
        self.assertAlmostEqual(fidelity["normalized_symmetric_chamfer"], 0.0, places=12)
        self.assertEqual(fidelity["f_score"], {"1_percent": 1.0, "2_percent": 1.0, "5_percent": 1.0})
        self.assertAlmostEqual(result["silhouette"]["mean_iou"], 1.0)
        self.assertEqual(result["detail"]["status"], "EXPERIMENTAL")
        self.assertFalse(result["detail"]["included_in_primary_ranking"])

    def test_health_and_mesh_import_are_explicit(self) -> None:
        health = geometry_health(tetrahedron())
        self.assertEqual(health["watertightness"], "TOPOLOGICALLY_WATERTIGHT")
        self.assertEqual(health["boundary_edges"], 0)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "tetra.obj"
            path.write_text(
                "v 0 0 0\nv 1 0 0\nv 0 1 0\nv 0 0 1\n"
                "f 1 3 2\nf 1 2 4\nf 2 3 4\nf 3 1 4\n",
                encoding="utf-8",
            )
            self.assertEqual(len(load_mesh(path).faces), 4)

    def test_silhouette_iou_detects_shape_difference(self) -> None:
        mesh = tetrahedron()
        changed = Mesh(mesh.vertices + ((2.0, 2.0, 2.0),), mesh.faces + ((1, 2, 4),))
        result = evaluate_silhouettes(mesh, changed, resolution=64)
        self.assertLess(result["mean_iou"], 1.0)
        self.assertIn("worst_view_iou", result)

    def test_report_keeps_dimensions_primary_and_fake_out_of_pareto(self) -> None:
        run = {
            "run_id": "fixture", "attempts": [{
                "backend_id": "fake_generator", "case_id": "case", "attempt": 1,
                "status": "PASS", "raw_metrics": evaluate_geometry(tetrahedron(), tetrahedron()),
                "latency": {"end_to_end_seconds": 0.1}, "estimated_cost_usd": 0,
                "conditioning": {"status": "NOT_RUN"},
            }],
        }
        result = generate(run)
        self.assertEqual(result["primary_truth"], "RAW_DIMENSIONS_AND_STATUSES")
        self.assertEqual(result["pareto_frontier"], [])
        self.assertTrue(result["no_model_winner_declared"])
        self.assertEqual(result["winner_declarations"], {})

    def test_pareto_and_weight_validation_are_fail_closed(self) -> None:
        rows = [
            {"result_id": "strong", "dimensions": {"shape_fidelity": 90, "latency": 2}},
            {"result_id": "weak", "dimensions": {"shape_fidelity": 80, "latency": 3}},
        ]
        self.assertEqual(pareto_frontier(rows), ["strong"])
        validate_weights(PROJECT_DEFAULT)
        for invalid in (
            {**PROJECT_DEFAULT, "shape_fidelity": float("nan")},
            {**PROJECT_DEFAULT, "shape_fidelity": -1},
            {key: value for key, value in PROJECT_DEFAULT.items() if key != "cost"},
        ):
            with self.assertRaises(ValueError):
                validate_weights(invalid)

    def test_blind_review_hides_provider_until_reveal(self) -> None:
        packet, reveal = anonymize(
            [{"backend_id": "meshy", "provider": "Meshy", "model_version": "meshy-6", "case_id": "case"}],
            salt="fixture-salt",
        )
        self.assertEqual(packet["human_evaluation"], "NOT_RUN")
        self.assertNotIn("provider", packet["entries"][0])
        token = packet["entries"][0]["backend_token"]
        self.assertEqual(reveal["tokens"][token]["backend_id"], "meshy")


if __name__ == "__main__":
    unittest.main()
