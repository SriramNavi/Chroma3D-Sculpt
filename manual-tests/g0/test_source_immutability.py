from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from _support import PROJECT_ROOT
from backends.base import ExecutionPolicy, GenerationRequest
from backends.fake import FakeGeneratorBackend
from build_corpus import SMOKE3, build
from common import read_json, sha256_file


class SourceImmutabilityTests(unittest.TestCase):
    def test_corpus_build_and_fake_generation_do_not_mutate_sources(self) -> None:
        dataset = PROJECT_ROOT / ".validation-assets" / "dataset"
        manifest = read_json(dataset / "manifests" / "statue_dataset_manifest.json")
        assets = {item["unique_id"]: item for item in manifest["assets"]}
        sources = [dataset / "raw" / assets[case_id]["stored_filename"] for case_id in SMOKE3]
        before = {path: sha256_file(path) for path in sources}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build(dataset, root / "corpus", root / "missing-index.json")
            request = GenerationRequest(
                case_id=SMOKE3[0], track="A", input_paths=(sources[0],), dry_run=False,
                parameters={"fake_mode": "success"}, seed=0,
            )
            job = FakeGeneratorBackend(ExecutionPolicy()).submit(request, root / "raw")
            self.assertEqual(job.status, "PASS")
            self.assertNotEqual(job.artifact_path.resolve(), sources[0].resolve())
        self.assertEqual(before, {path: sha256_file(path) for path in sources})


if __name__ == "__main__":
    unittest.main()
