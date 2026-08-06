# Sprint 7 Test Matrix

Implementation evidence is produced by `tests/blender/run_sprint7_tests.py`, the Sprint 7 dataset workers, normal acceptance runner, and independent final runner. Automated provider cases use only mocked transports and the in-process fake provider; live provider calls remain outside this matrix.

Current executable evidence is `62/62` focused Sprint 7 tests and `813/813` combined Blender tests on Blender 4.4.3. Test counts are reported as evidence, not substituted for gate-specific results.

## Strategy

Tests are layered so provider-independent safety can be proven without credentials or network. Unit tests use pure Python and fake adapters; Blender background tests cover integration with current sessions and deterministic execution; live-provider checks are a separate release condition only if that provider is enabled. A failed first run is retained, fixes require a reproduced defect, and thresholds or assertions are never weakened to manufacture a pass.

## Minimum executable test inventory

The floor is behavior-derived, not a marketing count:

- **42 distinct static/unit test methods:** one for each major contract/parser/context/state/security/resolution/report behavior, including all 32 normative requirements.
- **28 parameterized case groups:** every enum, boundary, malformed numeric/string/JSON form, allow-list tier, evidence state, state transition family, stale reason, and cancellation phase named below.
- **14 unique runtime pathways:** start/offline; consent/reject; valid fake response; no-action; stale-before-dispatch; stale-after-response; injection reject; unknown candidate reject; preview/reject; preview/execute/compare/accept; preview/execute/restore; cancel-before; cancel-in-flight/late-response; export/report-failure recovery.
- **Independent final gates:** `S7F-A` onward run through separate fixtures/entry points and do not import expected outputs from the focused tests.

Generated combinations do not replace distinct pathways. A parameterized loop counts once unless it drives materially different runtime state.

## Category matrix

| Category | Required cases | Evidence |
|---|---|---|
| Version/contracts | Draft/runtime versions; provider/prompt/policy/schema compatibility; current metadata unchanged; draft schemas absent from package | Pure tests + package audit |
| Models/serialization | Frozen models, canonical JSON/hash, round-trip, unknown fields, bounded arrays/strings, no Blender objects | Pure tests |
| Invalid values | Missing fields, duplicate IDs/keys, wrong types, empty IDs, invalid hashes/enums/Unicode/control content | Parameterized pure tests |
| Boolean-as-number | Every integer/number field receives `true` and `false` and is rejected before coercion | Parameterized pure tests |
| NaN/infinity | Parser `NaN`, `Infinity`, `-Infinity`; constructed `float` non-finite; exponent overflow | Parser/model/schema semantic tests |
| Deterministic IDs | Same canonical input/output gives same hash; changed policy/context/provider/schema/output changes identity; timestamps excluded only where specified | Pure tests |
| Context/privacy | Allow-listed fields only, zero geometry arrays, redaction, consent scope/expiry, limits, path/name stripping, stale source | Pure + Blender integration |
| Provider abstraction | Fake success/no-action/malformed/timeout/cancel/late output/usage; capabilities; unsupported retention/cancel modes; no fallback | Contract tests |
| State transitions | Every legal transition, representative illegal transitions, terminal behavior, approval revocation | Table-driven pure tests |
| Stale state | Source, workspace, context, policy, provider, prompt, schema, candidate, strategy, profile, registry, implementation, file-state mismatch | Pure + Blender integration |
| Cancellation | Before dispatch, in flight, after return/before validation, preview, between operations, late response, cleanup | Fake adapter + Blender integration |
| Budget exhaustion | Intent/context/output bytes, evidence/recommendation counts, local time, provider timeout, usage/cost observation, report size | Parameterized tests |
| Algorithm truth | Context allow-list, strict decode, evidence grounding, local confidence, no-action, canonical parameter echo | Truth fixtures |
| Ranking/selection truth | Existing current candidate/strategy exact resolution; unknown/stale/mismatched/dominated references; provider rank cannot override hard constraints | Pure + Sprint 6 fixture |
| Source protection | Snapshot matrix across request/validation/preview/execution/cancel/fail/export/cleanup | Blender fixtures |
| Workspace/checkpoints | Delegation only, checkpoint-before-mutation, no duplicated operation path, restore verification | Blender integration |
| Rollback/cleanup | Provider fail leaves no workspace; execution fail restores; discard removes only owned resources; cleanup failure retained | Blender integration |
| Reporting | Complete fields, explicit states, redaction, bounded text, hashes/usage/timings, point-memory wording, safe filenames/paths | Pure + filesystem tests |
| Security | Injection corpus, arbitrary operator/code/shell/URL/path attempts, unsafe deserialization/imports, secrets, hidden network, oversized data | Static + adversarial runtime tests |
| Registration/UI | Class registration, disabled/offline state, consent state, stale/cancel/failure display, approval disabled until preview, no import-time network | Blender factory-startup + manual UAT |
| Installed package | Exact ZIP scope, install/remove/factory startup, local workflows without credentials/network, draft schema exclusion | Package/install gate |
| Dataset | Synthetic truth; representative 10 mutation/non-mutation matrix; full 27 nondestructive context/validation workflow | Resumable per-model workers |
| Historical compatibility | All prior background tests and acceptance chain; frozen reports unchanged | Historical runners |
| Performance | Phase timing, configured caps, timeout owner, environment record, point observations, cancel responsiveness | Dedicated fixtures |

## Parameterized boundary groups

1. Evidence states: all ten states in positive/negative hard-requirement positions.
2. Confidence: `HIGH`, `MEDIUM`, `LOW`, `UNKNOWN`, unknown enum and provider overclaim.
3. Modes: FAST/STANDARD/DEEP/CUSTOM min/max/below/above/bool/non-finite.
4. JSON: duplicate key, trailing data, prose fence, invalid UTF-8, BOM, control character, over-depth, over-nodes, over-bytes.
5. Numbers: zero/min/max/above/below, booleans, strings, NaN/infinities, exponent overflow.
6. IDs/hashes: valid lowercase UUID/SHA-256, missing, wrong length, uppercase, collision fixture, mismatched fingerprint.
7. Recommendation actions: four allowed actions plus unknown/case-variant/model-authored operator.
8. Operation policy: safe-default, gated-enabled, gated-disabled, prohibited remesh, unknown operation.
9. Candidate/strategy status: current, missing, stale, wrong source, wrong policy, wrong parameter hash, hard-infeasible.
10. Cancellation phase: pre-dispatch, in-flight, returned, validation, preview, execution boundary, post-terminal.
11. Provider contract: test/local/BYOK/hosted; retention declared/unknown; cancellation supported/unsupported; usage present/absent.
12. Paths: relative filename, nested chosen folder, `..`, UNC/device/reserved names, alternate separators, long name, null byte.

## Requirement traceability

| Requirement ID | Behavior | Unit test | Integration test | Acceptance gate |
|---|---|---|---|---|
| S7-REQ-001 | Optional/offline local workflows | `test_disabled_policy_is_noop` | `offline_prior_workflows` | S7-01, S7-18 |
| S7-REQ-002 | Consented bounded allow-listed context | `test_context_consent_matrix` | `context_snapshot_blender` | S7-03 |
| S7-REQ-003 | No raw geometry/references/paths | `test_context_forbidden_fields` | `dataset_context_inventory` | S7-03, S7-14 |
| S7-REQ-004 | Current explicit evidence only | `test_evidence_state_grounding` | `stale_source_before_request` | S7-05, S7-07 |
| S7-REQ-005 | Replaceable declared provider interface | `test_provider_contract_matrix` | `fake_adapter_lifecycle` | S7-04 |
| S7-REQ-006 | Full untrusted-output validation | `test_validation_pipeline_order` | `injected_response_rejected` | S7-06, S7-11 |
| S7-REQ-007 | Strict JSON/types/limits | `test_strict_decoder_matrix` | `oversized_provider_output` | S7-02, S7-06 |
| S7-REQ-008 | Explainable bounded recommendation | `test_recommendation_required_evidence` | `valid_fake_recommendation` | S7-06 |
| S7-REQ-009 | Unknown never passes hard rules | `test_unknown_hard_requirement` | `unknown_fidelity_blocks_preview` | S7-05 |
| S7-REQ-010 | Existing candidate/strategy identity only | `test_exact_resolution_matrix` | `resolve_current_sprint6_strategy` | S7-05, S7-08 |
| S7-REQ-011 | Allow-list tiers/remesh prohibition | `test_operation_policy_matrix` | `gated_candidate_preview` | S7-08, S7-11 |
| S7-REQ-012 | Exact parameter echo/no clamping | `test_parameter_hash_mismatch_rejected` | `provider_parameter_tamper` | S7-08 |
| S7-REQ-013 | Read-only recommendation/preview | `test_preview_requires_no_approval` | `preview_immutability` | S7-08, S7-09 |
| S7-REQ-014 | Fresh explicit approval/reject | `test_approval_token_binding` | `reject_executes_nothing` | S7-09 |
| S7-REQ-015 | Existing execution path only | `test_execution_delegate_contract` | `delegated_strategy_execution` | S7-01, S7-09 |
| S7-REQ-016 | Protected source/separate copy | `test_source_snapshot_contract` | `accept_copy_source_matrix` | S7-09, S7-14 |
| S7-REQ-017 | Complete stale fingerprints | `test_dependency_hash_registry` | `stale_reason_matrix` | S7-07 |
| S7-REQ-018 | Stale invalidates derived state | `test_stale_clears_preview_approval` | `change_policy_after_preview` | S7-07 |
| S7-REQ-019 | Monotonic cancellation/late quarantine | `test_cancellation_state_matrix` | `late_response_quarantined` | S7-10 |
| S7-REQ-020 | Truthful failures/recovery | `test_error_phase_taxonomy` | `failure_restore_matrix` | S7-10, S7-12 |
| S7-REQ-021 | Complete redacted audit | `test_audit_required_fields` | `end_to_end_audit_export` | S7-12 |
| S7-REQ-022 | No credential persistence | `test_secret_redaction_matrix` | `blend_report_log_secret_scan` | S7-11, S7-12 |
| S7-REQ-023 | No hidden network/full disclosure | `test_dispatch_requires_disclosure_consent` | `network_spy_offline_startup` | S7-03, S7-04, S7-11 |
| S7-REQ-024 | Path/deserialization/code safety | `test_security_payload_matrix` | `safe_export_paths` | S7-11, S7-12 |
| S7-REQ-025 | Central modes/honest limit states | `test_mode_limit_validation` | `budget_exhaustion_path` | S7-13 |
| S7-REQ-026 | Bounded time/size/retry/fallback | `test_budget_matrix` | `timeout_no_fallback` | S7-04, S7-10, S7-13 |
| S7-REQ-027 | Deterministic identity/no learning | `test_identity_dependency_matrix` | `repeat_fake_exchange` | S7-02, S7-05 |
| S7-REQ-028 | Complete accessible UI states | `test_ui_state_projection` | `panel_state_smoke` | S7-14 |
| S7-REQ-029 | Strict bounded reports/schemas | `test_all_schema_and_report_contracts` | `report_round_trip` | S7-02, S7-12 |
| S7-REQ-030 | Full validation story | `test_gate_manifest_complete` | `dataset_and_historical_runners` | S7-15–S7-19 |
| S7-REQ-031 | Version/package/draft exclusion | `test_release_identity_unchanged` | `package_scope_audit` | S7-18, S7-20 |
| S7-REQ-032 | No unsupported correctness claims | `test_prohibited_claims` | `ui_report_wording_scan` | S7-06, S7-11 |

## Defect-regression policy

- Preserve the first failing input/output/hash and environment before changing code.
- Add the smallest deterministic regression fixture reproducing the defect.
- Fix only reproduced product defects; do not relax expected truth, safety gates, limits, or wording.
- Classify provider outage/rate/cost/retention mismatch separately from local product defects.
- Retain `SKIPPED_LIMIT`, `INDETERMINATE`, `CANCELLED`, and `BUDGET_EXHAUSTED`; never convert them to PASS.
- A live-provider result cannot replace fake-provider contract tests or independent local security proof.
