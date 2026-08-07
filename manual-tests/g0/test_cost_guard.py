from __future__ import annotations

from decimal import Decimal
import unittest

import _support
from backends.base import BenchmarkPolicyError, CostEstimate, ExecutionPolicy
from backends.registry import backend_registry
from common import read_json
from run_benchmark import _authorize_commercial_stage


class CostGuardTests(unittest.TestCase):
    def test_default_policy_is_zero_spend_and_network_disabled(self) -> None:
        policy = ExecutionPolicy()
        self.assertEqual(policy.max_spend_usd, Decimal("0"))
        self.assertEqual(policy.max_live_jobs, 0)
        self.assertFalse(policy.allow_live_provider_calls)
        self.assertFalse(policy.allow_model_downloads)
        self.assertFalse(policy.allow_cloud_gpu)

    def test_live_call_is_blocked_before_transport(self) -> None:
        backend = backend_registry(ExecutionPolicy())["meshy"]
        with self.assertRaises(BenchmarkPolicyError) as caught:
            backend._authorize(CostEstimate("KNOWN", Decimal("0")))  # type: ignore[attr-defined]
        self.assertEqual(caught.exception.classification, "SPEND_NOT_AUTHORIZED")

    def test_unknown_cost_requires_separate_owner_authorization(self) -> None:
        policy = ExecutionPolicy(
            max_spend_usd=Decimal("50"), max_live_jobs=2,
            allow_live_provider_calls=True, allow_unknown_cost=False,
        )
        with self.assertRaises(BenchmarkPolicyError) as caught:
            policy.authorize_live_stage(jobs=1, estimate=CostEstimate("UNKNOWN", None))
        self.assertEqual(caught.exception.classification, "BUDGET_AUTHORIZATION_REQUIRED")

    def test_bounded_known_cost_may_be_authorized(self) -> None:
        policy = ExecutionPolicy(
            max_spend_usd=Decimal("5"), max_live_jobs=2,
            allow_live_provider_calls=True,
        )
        policy.authorize_live_stage(jobs=2, estimate=CostEstimate("KNOWN", Decimal("4")))

    def test_commercial_stage_unknown_cost_blocks_before_submit(self) -> None:
        policy = ExecutionPolicy(
            max_spend_usd=Decimal("50"), max_live_jobs=3,
            allow_live_provider_calls=True, allow_unknown_cost=False,
        )
        backend = backend_registry(policy)["meshy"]
        corpus = read_json(_support.GENERATIVE_ROOT / "corpus" / "manifest.json")
        cases = {case["case_id"]: case for case in corpus["cases"]}
        with self.assertRaises(BenchmarkPolicyError) as caught:
            _authorize_commercial_stage(
                backend=backend, cases=cases,
                case_ids=["statue-asad-al-lat"], track="A", policy=policy, dry_run=False,
            )
        self.assertEqual(caught.exception.classification, "BUDGET_AUTHORIZATION_REQUIRED")


if __name__ == "__main__":
    unittest.main()
