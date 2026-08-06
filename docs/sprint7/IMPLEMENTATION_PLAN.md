# Sprint 7 Implementation Plan

**Execution status:** implemented in the current `0.8.0-alpha.1` worktree; see `IMPLEMENTATION_STATUS.md` and retained acceptance results. This file preserves the planned sequence for traceability.

## Boundary

This sequence is retained as the implementation trace. S7A-I and the local/package portions of S7K are implemented; S7J live-provider qualification and publication/manual-UAT portions of S7K remain separate authorization gates.

## S7A — Contracts, policy, and settings

- **Expected files:** `models/assistance_models.py`, `services/assistance_policy.py`, runtime schemas promoted from approved drafts, targeted tests, central `performance_registry.py` additions.
- **Dependencies:** approved schema compatibility and compiled maxima; no provider choice.
- **Entry:** specification accepted.
- **Exit:** frozen models/enums, canonical serialization/hashes, strict settings/policy validation, all invalid numeric/type/ID cases pass.
- **Tests:** S7-02 model/serialization/limits subset.
- **Risks:** accidental schema over-flexibility; boolean/non-finite coercion; version ambiguity.
- **Codex complexity:** medium.
- **Expensive validation:** none; pure tests only.

## S7B — Context, privacy, and consent core

- **Expected files:** `services/assistance_context.py`, `services/assistance_redaction.py`, consent models/tests, no UI yet.
- **Dependencies:** S7A and current Sprint 1–6 report projections.
- **Entry:** field/data-category allow-list approved.
- **Exit:** deterministic minimized manifest/payload, zero geometry/reference/secret/path leakage, stale checks and bounded truncation truth.
- **Tests:** context golden files, forbidden canaries, consent expiry and dataset manifest dry fixtures.
- **Risks:** accidental inclusion through generic serialization; stale/hash gaps.
- **Codex complexity:** high.
- **Expensive validation:** targeted Blender snapshots only after pure tests.

## S7C — Provider-neutral interface and fake adapters

- **Expected files:** `services/assistance_provider.py`, `services/providers/fake.py`, request/response envelopes and tests.
- **Dependencies:** S7A/B; owner need not select a live provider.
- **Entry:** provider capability contract approved.
- **Exit:** success/no-action/failure/timeout/cancel/late-response/usage behavior passes with zero hidden retries/fallback/network.
- **Tests:** deterministic fake/recorded adapters and network-spy tests.
- **Risks:** coupling provider semantics to product state; non-cancellable transports.
- **Codex complexity:** medium.
- **Expensive validation:** none; network prohibited in default suite.

## S7D — Strict output, grounding, and local confidence

- **Expected files:** `services/assistance_decoder.py`, `assistance_grounding.py`, `assistance_confidence.py`, adversarial fixtures.
- **Dependencies:** S7A–C.
- **Entry:** draft recommendation schema approved.
- **Exit:** bounded strict JSON; full structural/semantic/evidence validation; no-action; deterministic IDs; human-review rubric fixtures.
- **Tests:** malformed JSON, injection, evidence graph, confidence and prohibited-claim corpus.
- **Risks:** accepting schema-valid but semantically unsupported output; model confidence leakage.
- **Codex complexity:** high.
- **Expensive validation:** independent adversarial run, no Blender corpus.

## S7E — Action policy, state/session, and cancellation

- **Expected files:** `services/assistance_action_resolver.py`, `assistance_session.py`, `assistance_coordinator.py` (read-only phases), tests.
- **Dependencies:** S7A–D and stable Sprint 5/6 interfaces.
- **Entry:** operation tier policy approved.
- **Exit:** exact candidate/strategy resolution, canonical parameter match, complete state/stale/cancel/budget behavior, no mutation path yet.
- **Tests:** all transition/stale/operation/cancel matrices.
- **Risks:** stale approval; silent parameter repair; provider output influencing control flow.
- **Codex complexity:** high.
- **Expensive validation:** targeted Blender current-ID snapshots.

## S7F — Blender preview and delegated safety integration

- **Expected files:** assistance operators/coordinator adapter, targeted registration, integration tests; no duplicated geometry services.
- **Dependencies:** S7E; Sprint 5/6 safety interfaces unchanged.
- **Entry:** read-only gates pass; source/workspace safety review approved.
- **Exit:** current preview, fresh approval, delegated execution, checkpoint/restore/comparison/accept-copy/discard and source-immutability matrices pass.
- **Tests:** source/workspace/checkpoint fault injection and unique runtime pathways.
- **Risks:** bypass through operator UI; cleanup ownership; unrecoverable workspace failure.
- **Codex complexity:** very high.
- **Expensive validation:** focused Blender background tests; no corpus until stable.

## S7G — Reports, audit, safe export, and UI

- **Expected files:** `services/assistance_audit.py`, report generator, assistance panel/operators/properties/registration, user docs.
- **Dependencies:** S7A–F.
- **Entry:** state and execution contracts stable.
- **Exit:** strict bounded redacted JSON/Markdown, safe paths, complete UI states, disabled/offline experience and accessible manual-flow checklist.
- **Tests:** report/security/path; factory registration; panel state automation where practical.
- **Risks:** secret/raw response leakage; UI conflating recommendation and approval.
- **Codex complexity:** high.
- **Expensive validation:** installed-panel manual UAT after package exists.

## S7H — Focused, security, and performance evidence

- **Expected files:** `tests/test_sprint7_*.py`, `manual-tests/sprint7/` runners/fixtures/results, retained first-failure records.
- **Dependencies:** S7A–G complete.
- **Entry:** focused implementation review passes.
- **Exit:** test floor/pathways, S7-01–S7-15, performance boundary fixtures and independent S7F-A–S7F-M pass.
- **Tests:** all categories in `TEST_MATRIX.md`.
- **Risks:** testing implementation with shared expected logic; threshold weakening.
- **Codex complexity:** very high.
- **Expensive validation:** Blender suite and independent adversarial/security runs.

## S7I — Dataset and historical validation

- **Expected files:** resumable per-model worker/parent wrappers and human result summaries; machine output ignored.
- **Dependencies:** S7H and frozen dataset manifests.
- **Entry:** no focused/security/source-safety failures.
- **Exit:** representative 10/10, full 27/27, historical compatibility and final S7F-O–S7F-Q evidence pass exactly.
- **Tests:** nondestructive fake-provider corpus first; mutation subset only if release enables it.
- **Risks:** long workers, stale fingerprints, treating identity-only evidence as workflow proof.
- **Codex complexity:** high.
- **Expensive validation:** 10/27 model workers and all historical Blender acceptance chains.

## S7J — Provider decision and optional adapter qualification

- **Expected files:** approved decision record, one adapter behind the interface if authorized, provider evaluation fixtures/results, privacy/security documentation.
- **Dependencies:** S7C/D/H; owner decisions Q-PROD-001–003/Q-ENG-001.
- **Entry:** explicit provider/deployment authorization and development credentials; local contracts already pass.
- **Exit:** direct evidence for data/retention/cost/latency/timeout/cancel/structured-output behavior and fallback; or recorded decision to ship adapters disabled.
- **Tests:** development-provider only; secrets redacted; one clear blocker stops provider-dependent work.
- **Risks:** privacy/cost/terms drift, provider nondeterminism, outage.
- **Codex complexity:** high and externally blocked until authorization.
- **Expensive validation:** bounded live evaluation only if authorized.

## S7K — Final audit, package, and publication

- **Expected files:** final results, package/install evidence, approved metadata/release docs during a separate publication task.
- **Dependencies:** S7A–J and all gates.
- **Entry:** no hard blocker; owner approves release scope and provider status.
- **Exit:** S7-16–S7-20 and S7F-N–S7F-R pass; exact package installed/removed; clean reviewed Git scope; no Sprint 8 work.
- **Tests:** package/native/factory-startup/install/manual UAT/release audit.
- **Risks:** package includes drafts/tests/secrets; version/tag mismatch; unsupported release claims.
- **Codex complexity:** high.
- **Expensive validation:** exact package smoke and complete final chain.

## Sequence and stop conditions

S7A→S7B→S7C can proceed without a provider decision. S7D/E use only fake adapters. S7F begins only after local deny-by-default review. S7J is optional/blocked until explicit authority and can resolve to adapters disabled. Stop immediately on source mutation, arbitrary execution reachability, consent bypass, secret/raw-asset leakage, unverified rollback, or unsupported roadmap expansion.
