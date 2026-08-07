"""Validate compact tracked H4 evidence before expensive final gates."""

from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
H4 = ROOT / "hardening" / "h4"


def read(name: str):
    return json.loads((H4 / name).read_text(encoding="utf-8"))


class H4EvidenceTests(unittest.TestCase):
    def test_frozen_h3_identity(self) -> None:
        value = read("H4_BASELINE_IDENTITY.json")
        self.assertEqual("ba77d12e3a7e768fdc05d542c6ea12e1a3515a0b", value["frozen_h3"]["tag_peeled_target"])
        self.assertEqual("e481d6530a8b502630d02f14b5f66a108815b33a", value["frozen_h3"]["tag_object"])
        self.assertEqual("b331ba4f9767a356c75825f1865164245d194ea81a41b39e37fe1110b56deb03", value["public_contract"]["sha256"])
        self.assertEqual("0.8.0-alpha.1", value["version"]["display_version"])

    def test_findings_use_exact_classification(self) -> None:
        value = read("H4_FINDINGS.json")
        allowed = set(value["allowed_classifications"])
        self.assertTrue(value["findings"])
        self.assertTrue(all(item["classification"] in allowed for item in value["findings"]))
        self.assertTrue(all(isinstance(item["classification"], str) for item in value["findings"]))
        self.assertEqual(0, value["unresolved_counts"]["BLOCKER"])
        self.assertEqual(0, value["unresolved_counts"]["HIGH"])

    def test_required_compact_evidence_exists(self) -> None:
        required = {
            "README.md",
            "H4_BASELINE_IDENTITY.json",
            "H4_FINDINGS.json",
            "H4_FAILURE_LOG.md",
            "H4_FIRST_FAILURE.md",
            "H4_PERSISTENCE_MATRIX.md",
        }
        self.assertFalse(required - {path.name for path in H4.iterdir() if path.is_file()})

    def test_persistence_matrix_is_fail_closed(self) -> None:
        text = (H4 / "H4_PERSISTENCE_MATRIX.md").read_text(encoding="utf-8")
        for value in (
            "PERSIST_REQUIRED", "PERSIST_SAFE", "RECOMPUTE_REQUIRED",
            "TRANSIENT_MUST_CLEAR", "STALE_MUST_REJECT", "DO_NOT_SERIALIZE",
        ):
            self.assertIn(value, text)
        self.assertIn("start a fresh operation after reload", text)


if __name__ == "__main__":
    unittest.main()
