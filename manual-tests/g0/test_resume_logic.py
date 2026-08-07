from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import _support

assert _support.GENERATIVE_ROOT.is_dir()
from common import cache_identity, evaluation_cache_identity, reusable_record, sha256_file


class ResumeLogicTests(unittest.TestCase):
    def _identity(self, **changes):
        values = {
            "case_hash": "a" * 64, "backend_id": "fake_generator",
            "model_version": "fake-generator-1.0", "adapter_version": "1.0.0",
            "parameter_hash": "b" * 64, "attempt": 1, "seed": 0,
            "seed_semantics": "SUPPORTED_PROVIDER_SEED", "quality_mode": "provider_default",
            "evaluator_version": "cgb-geometry-evaluator-1.0.0",
            "evaluation_settings_hash": "c" * 64,
        }
        values.update(changes)
        return cache_identity(**values)

    def test_cache_reuse_requires_identity_and_artifact_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "raw" / "fixture.obj"
            artifact.parent.mkdir()
            artifact.write_text("fixture", encoding="utf-8")
            _, identity = self._identity()
            record = {
                "cache_identity": identity, "status": "PASS",
                "raw_artifact_path": "raw/fixture.obj", "raw_artifact_sha256": sha256_file(artifact),
            }
            record["evaluation_cache_identity"] = evaluation_cache_identity(
                artifact_sha256=record["raw_artifact_sha256"],
                evaluator_version=identity["evaluator_version"],
                evaluation_settings_hash=identity["evaluation_settings_hash"],
            )
            self.assertTrue(reusable_record(record, identity, root))
            artifact.write_text("changed", encoding="utf-8")
            self.assertFalse(reusable_record(record, identity, root))

    def test_any_identity_change_invalidates_cache(self) -> None:
        _, identity = self._identity()
        record = {"cache_identity": identity, "status": "NOT_RUN"}
        _, changed = self._identity(attempt=2)
        self.assertFalse(reusable_record(record, changed, Path(".")))

    def test_failed_generation_is_retained_but_never_reused(self) -> None:
        _, identity = self._identity()
        record = {"cache_identity": identity, "status": "GENERATION_FAILED"}
        self.assertFalse(reusable_record(record, identity, Path(".")))

    def test_missing_evaluation_identity_never_reuses_old_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "fixture.obj"
            artifact.write_text("fixture", encoding="utf-8")
            _, identity = self._identity()
            record = {
                "cache_identity": identity, "status": "PASS",
                "raw_artifact_path": "fixture.obj", "raw_artifact_sha256": sha256_file(artifact),
            }
            self.assertFalse(reusable_record(record, identity, root))


if __name__ == "__main__":
    unittest.main()
