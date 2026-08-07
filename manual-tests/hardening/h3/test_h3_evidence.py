"""Fast integrity tests for tracked H3 architecture evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
H3 = ROOT / "hardening" / "h3"


def read(name: str):
    return json.loads((H3 / name).read_text(encoding="utf-8"))


class H3EvidenceTests(unittest.TestCase):
    def test_baseline_h2_artifacts_remain_byte_identical(self):
        baseline = read("H3_BASELINE_IDENTITY.json")
        for item in baseline["h2_artifacts"].values():
            if not isinstance(item, dict) or "path" not in item:
                continue
            digest = hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest()
            self.assertEqual(digest, item["sha256"])

    def test_complexity_ledger_is_complete(self):
        ledger = read("H3_COMPLEXITY_LEDGER.json")
        self.assertEqual(ledger["status"], "PASS")
        self.assertEqual(ledger["target_count"], 35)
        self.assertEqual(ledger["priority_counts"], {"CRITICAL_REVIEW_PRIORITY": 7, "HIGH_REVIEW_PRIORITY": 28})
        self.assertEqual(len(ledger["selected_targets"]), 3)
        self.assertTrue(all(item["disposition"] for item in ledger["entries"]))

    def test_selected_complexity_decreased(self):
        before = {item["selected_symbol"]: item["selected_symbol_metrics"] for item in read("H3_COMPLEXITY_LEDGER.json")["entries"] if item["selected_symbol"]}
        after = {item["selected_symbol"]: item["selected_symbol_metrics"] for item in read("H3_COMPLEXITY_AFTER.json")["entries"] if item["selected_symbol"]}
        for symbol in ("repair_normal_consistency", "request_recommendations", "_analyze"):
            self.assertLess(after[symbol]["loc"], before[symbol]["loc"])
            self.assertLess(after[symbol]["branch_count_estimate"], before[symbol]["branch_count_estimate"])

    def test_behavioral_equivalence_is_green(self):
        evidence = read("H3_BEHAVIORAL_EQUIVALENCE.json")
        self.assertEqual(evidence["before"]["status"], "PASS")
        self.assertEqual(evidence["after"]["status"], "PASS")
        self.assertEqual(evidence["comparison"]["status"], "PASS")
        self.assertEqual(evidence["comparison"]["public_or_behavioral_differences"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
