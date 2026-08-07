"""Run the bounded existing adversarial matrix used by H4 qualification."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import unittest
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
TESTS = ROOT / "tests" / "blender"

CASES = {
    "invalid_object": "test_sprint2_repair.Sprint2RepairTests.test_03_invalid_object_rejected",
    "duplicate_repair_session": "test_sprint2_repair.Sprint2RepairTests.test_05_second_session_rejected",
    "stale_workspace": "test_sprint2_repair.Sprint2RepairTests.test_10_workspace_modification_invalidates_plan",
    "stale_source": "test_sprint2_repair.Sprint2RepairTests.test_11_source_modification_invalidates_session",
    "stale_settings": "test_sprint2_repair.Sprint2RepairTests.test_12_settings_change_invalidates_plan",
    "invalid_candidate_mapping": "test_sprint2_repair.Sprint2RepairTests.test_37_stale_tiny_mapping_rejected",
    "unsupported_hole_candidate": "test_sprint2_repair.Sprint2RepairTests.test_40_large_hole_rejected",
    "ambiguous_boundary": "test_sprint2_repair.Sprint2RepairTests.test_41_branched_boundary_rejected",
    "operation_raises_midway": "test_sprint2_repair.Sprint2RepairTests.test_45_failed_operation_restores_checkpoint",
    "rollback_cleanup": "test_sprint2_repair.Sprint2RepairTests.test_48b_rollback_discards_workspace_diagnostic_report",
    "source_identity_change": "test_sprint2_repair.Sprint2RepairTests.test_55_source_mesh_custom_property_invalidates_session",
    "checkpoint_creation_failure": "test_sprint2_repair.Sprint2RepairTests.test_57_checkpoint_creation_failure_is_audited_without_mutation",
    "optimization_stale_workspace": "test_sprint5_controlled_optimization.Sprint5ControlledOptimizationTests.test_06_plan_is_read_only_and_stale_workspace_rejected",
    "optimization_restore": "test_sprint5_controlled_optimization.Sprint5ControlledOptimizationTests.test_07_scale_preview_source_unchanged_undo_and_restore",
    "optimization_discard_accept": "test_sprint5_controlled_optimization.Sprint5ControlledOptimizationTests.test_11_discard_and_accept_are_separate_from_source",
    "credential_redaction": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_07_credential_redaction",
    "credential_not_persistent": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_10_no_credential_persistence_fields",
    "mock_provider_only": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_16_mock_openai_transport",
    "provider_timeout": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_17_timeout_classification",
    "provider_cancellation": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_18_cancellation_monotonic",
    "provider_response_too_large": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_19_response_size_limit",
    "provider_content_type": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_20_invalid_content_type_contract",
    "provider_host_allow_list": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_21_redirect_and_host_allow_list",
    "malformed_provider_json": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_22_malformed_json_matrix",
    "invalid_recommendation_ids": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_24_unknown_ids_rejected",
    "path_url_code_injection": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_28_code_shell_path_url_rejected",
    "illegal_assistance_transition": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_35_illegal_state_transitions",
    "assistance_stale_source": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_36_stale_source",
    "assistance_stale_policy": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_37_stale_policy_clears_preview",
    "cancel_revokes_approval": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_39_approval_revocation_on_cancel",
    "approval_requires_preview": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_41_approval_requires_preview",
    "credential_absent_from_reports": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_48_credential_absent_from_reports",
    "delegated_failure_restores": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_55_delegated_failure_restores_without_source_mutation",
    "bounded_retry": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_57_one_explicit_retry_and_zero_automatic_retries",
    "cancel_validated_evidence": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_58_cancel_validated_evidence_revokes_actions",
    "context_policy_mismatch": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_59_context_policy_mismatch_is_rejected",
    "raw_transport_shortcut": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_61_raw_rest_output_text_shortcut_rejected",
    "atomic_report_and_extension": "test_sprint7_ai_recommendation.Sprint7AIRecommendationTests.test_62_report_writes_are_atomic_and_html_is_rejected",
}


def _arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(values)


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.passed: list[str] = []

    def addSuccess(self, test: unittest.case.TestCase) -> None:  # noqa: N802
        super().addSuccess(test)
        self.passed.append(test.id())


def main() -> int:
    args = _arguments()
    if str(TESTS) not in sys.path:
        sys.path.insert(0, str(TESTS))
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite(loader.loadTestsFromName(name) for name in CASES.values())
    runner = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult)
    result = runner.run(suite)
    passed_ids = set(getattr(result, "passed", ()))
    records = []
    for scenario, test_name in CASES.items():
        records.append({
            "scenario": scenario,
            "test": test_name,
            "status": "PASS" if any(item.endswith(test_name) or item == test_name for item in passed_ids) else "FAIL",
            "classification": "EXPECTED_BEHAVIOR",
            "source_unchanged_required": scenario not in {"credential_redaction", "credential_not_persistent", "provider_content_type", "provider_host_allow_list", "malformed_provider_json", "path_url_code_injection", "credential_absent_from_reports", "raw_transport_shortcut", "atomic_report_and_extension"},
        })
    passed = result.wasSuccessful() and result.testsRun == len(CASES) and all(item["status"] == "PASS" for item in records)
    payload = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if passed else "FAIL",
        "scenario_count": len(CASES),
        "tests_run": result.testsRun,
        "passed_count": len(passed_ids),
        "failures": [test.id() for test, _ in result.failures],
        "errors": [test.id() for test, _ in result.errors],
        "records": records,
        "live_provider_calls": 0,
        "limitations": ["Mock/fake provider boundaries only; no live provider request is performed."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(args.output)
    print(json.dumps({
        "status": payload["status"],
        "scenarios": len(CASES),
        "passed": len(passed_ids),
        "failures": payload["failures"],
        "errors": payload["errors"],
    }, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
