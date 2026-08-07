from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from _support import PROJECT_ROOT
from build_corpus import CORE10, SMOKE3, build
from common import read_json, sha256_file, stable_hash


class ManifestIdentityTests(unittest.TestCase):
    def test_rights_cleared_full27_and_existing_subsets(self) -> None:
        dataset = PROJECT_ROOT / ".validation-assets" / "dataset"
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "corpus"
            manifest = build(dataset, output, Path(temporary) / "missing-render-index.json")
            self.assertEqual(manifest["case_count"], 27)
            self.assertEqual(manifest["source_dataset_version"], "1.0.0")
            self.assertTrue(manifest["rights_cleared"])
            self.assertEqual(manifest["source_mutation_count"], 0)
            self.assertEqual(read_json(output / "smoke3.json")["case_ids"], list(SMOKE3))
            self.assertEqual(read_json(output / "core10.json")["case_ids"], list(CORE10))
            self.assertEqual(read_json(output / "full27.json")["case_count"], 27)
            for case in manifest["cases"]:
                self.assertEqual(len(case["source_sha256"]), 64)
                self.assertTrue(case["rights_or_provenance"]["license"])
                without_hash = {key: value for key, value in case.items() if key != "case_hash"}
                self.assertEqual(case["case_hash"], stable_hash(without_hash))

    def test_manifest_sources_match_locked_bytes(self) -> None:
        dataset = PROJECT_ROOT / ".validation-assets" / "dataset"
        source_manifest = read_json(dataset / "manifests" / "statue_dataset_manifest.json")
        for asset in source_manifest["assets"]:
            source = dataset / "raw" / asset["stored_filename"]
            self.assertEqual(sha256_file(source), asset["checksum_sha256"])


if __name__ == "__main__":
    unittest.main()
