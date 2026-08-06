# Sprint 7 Acceptance Gates

## Gate semantics

A gate is PASS only with direct retained evidence. `WARNING` is allowed only where the gate explicitly permits it and never for source protection, consent, schema/semantic validation, allow-list, approval, rollback, secret handling, hidden network, or prohibited execution. `SKIPPED_LIMIT`, `NOT_EVALUATED`, `INDETERMINATE`, `STALE`, `CANCELLED`, `BUDGET_EXHAUSTED`, missing credentials, and provider unavailability are not PASS for a required release gate.

## Normal acceptance gates

### S7-01 — Architecture and historical boundary

PASS requires dependency direction, provider/Blender separation, optional/offline behavior, reuse of Sprint 5/6 mutation interfaces, no duplicate mutation logic, and all prior runtime regressions passing unchanged. Hard blocker: provider output can call Blender/operator/coordinator directly.

### S7-02 — Typed models, contracts, serialization, and versions

PASS requires frozen typed models; deterministic canonical serialization/hashes; all stable/draft schema and compatibility tests; duplicate/boolean/non-finite/unknown-field rejection; and unchanged current metadata before authorized release. Warning allowed only for explicitly draft compatibility questions with fail-closed behavior.

### S7-03 — Context minimization, privacy, and consent

PASS requires allow-listed bounded context, zero geometry arrays, no secrets/customer/developer paths, exact context inventory, purpose/destination/retention/cost disclosure, hash-bound consent, expiry on change, and no dispatch without consent. No warning can substitute for consent.

### S7-04 — Provider abstraction and deployment decision

PASS requires fake-provider contract coverage for capability/success/no-action/failure/timeout/cancel/late response/usage; zero hidden fallback/retry; offline local behavior; and an owner-approved deployment decision for every enabled live adapter. A release with all live adapters disabled may pass when provider-neutral contract behavior is complete and limitation is explicit.

### S7-05 — Evidence semantics, grounding, and deterministic identity

PASS requires exact evidence resolution, unknown evidence failing hard requirements, local confidence derivation, deterministic IDs/hashes, current candidate/strategy resolution, and no provider override of hard constraints/ranking truth.

### S7-06 — Structured-output and recommendation truth

PASS requires bounded strict JSON, complete structural and semantic validation, required reasons/assumptions/confidence/prerequisites/limitations/evidence, validated no-action behavior, human-review rubric approval, and no unsupported correctness/guarantee wording.

### S7-07 — Stale-state matrix

PASS requires every source/workspace/context/policy/provider/prompt/schema/candidate/strategy/profile/registry/implementation/file mismatch to mark stale, clear preview/approval, and block dispatch or execution until fresh evidence. No stale bypass is allowed.

### S7-08 — Deny-by-default operation resolution and preview

PASS requires four allowed recommendation actions only, exact current ID/fingerprint/operation/parameter-hash resolution, policy tiers, prohibited remesh/unknown operator denial, read-only preview, and zero parameter clamping or provider-minted candidates.

### S7-09 — Approval, source protection, checkpoints, comparison, acceptance

PASS requires fresh explicit approval; full before/after protected-source equality; existing independent workspace; checkpoint before each mutation; truthful comparison; accept separate copy; discard owned resources only; and reject/no-action paths with zero mutation.

### S7-10 — Cancellation, budgets, provider failures, and recovery

PASS requires all phase cancellation paths, late-response quarantine, no hidden retry/provider switch, explicit budget states, verified restore after delegated failure, and no accept from cancelled/failed/unrestored state. A provider that cannot cancel must disclose the limitation and still quarantine late output.

### S7-11 — Security and prohibited-capability audit

PASS requires adversarial prompt/output/context tests; no `eval`, `exec`, pickle, dynamic/generated code, shell/system command, unsafe URL/destination, traversal, secret exposure, hidden network, telemetry, unsupported operation, slicing/G-code/printer path, or package dependency drift. Any reachable arbitrary execution is a hard blocker.

### S7-12 — Audit, report, redaction, paths, and cleanup

PASS requires complete strict bounded JSON/Markdown records, redacted exchanges, consent/usage/timing/point-memory/stale/cancel/recovery evidence, safe filename/path tests, report failure isolation, and owned-resource cleanup evidence. Raw geometry, Blender references, secrets, or developer absolute paths are hard blockers.

### S7-13 — Performance policy and bounded modes

PASS requires centralized validated FAST/STANDARD/DEEP/CUSTOM limits, boundary/over-limit fixtures, phase timings, timeout ownership, point-memory terminology, AC-powered local release evidence, and retained first failures. Warning is allowed for documented live-provider latency variability after local gates pass; no threshold weakening.

### S7-14 — Blender registration, UI states, and accessibility

PASS requires factory-startup registration/unregistration, no import-time network, panel placement, disabled/offline/consent/progress/evidence/stale/cancel/failure/preview/approval/export/cleanup states, approval disabled until current preview, keyboard/logical grouping, readable focus, and no color-only meaning. Manual installed-panel UAT is required for release.

### S7-15 — Synthetic truth and adversarial fixtures

PASS requires every truth family in `DATASET_AND_FIXTURE_PLAN.md`, including malformed JSON, injection, evidence conflicts, operation tiers, state/recovery, secret/path and limit boundaries. Expected rejection counts as PASS only with zero side effects and the exact denial reason.

### S7-16 — Representative 10-model workflow

PASS requires 10/10 nondestructive fake-provider context/recommendation runs, zero timeouts/unclassified failures/source mutations/geometry payloads, bounded reports, and deterministic fingerprints. If release enables delegated mutation, the approved representative operation-tier subset must also pass source/workspace/checkpoint/restore/accept/discard truth.

### S7-17 — Full 27-model workflow

PASS requires 27/27 nondestructive workers, zero source mutations, zero geometry payloads, zero unclassified failures/timeouts, valid resumability/fingerprints, bounded context/report size, and no live-provider or physical inference.

### S7-18 — Historical compatibility and offline operation

PASS requires all Sprint 0–6 test/acceptance runners appropriate to the affected runtime, unchanged frozen evidence, local diagnostics/repair/printability/preparation/optimization without credentials/network, and explicit retained prior limitations.

### S7-19 — Exact package and installed-extension smoke

PASS requires repository package validation, exact ZIP inventory/checksum, draft-schema/test/evidence/secret/dependency exclusion, clean factory-startup install/register/workflow/export/remove, disabled-provider offline behavior, and no residual preference/credential/profile/workspace data outside declared ownership.

### S7-20 — Documentation, release identity, and Git hygiene

PASS requires specification/implementation docs matching behavior, no unsupported claims, approved version/release notes only during authorized publication, clean staged scope, no generated machine evidence/bytecode/secrets, traceable commit/tag/package identity, and no Sprint 8 work.

## Allowed limitations

- Physical printing, slicer comparison, material calibration, cultural/iconographic correctness, Blender 4.5 LTS, and provider production-SLA evidence may remain explicitly `NOT RUN` unless the release scope separately requires them.
- Live providers may remain disabled; contract-only alpha evaluation must say so visibly.
- Provider latency/cost/availability may be environment-sensitive observations; local deterministic safety remains mandatory.
- A sampled memory value is labeled a point observation, not peak memory.

## Hard blockers

Any source mutation, missing checkpoint before mutation, unverified rollback, stale/unknown hard-requirement pass, hidden network, missing consent, secret/raw asset exposure, model-authored executable path, unsupported operation, bypassed preview/approval, automatic acceptance/source replacement, unbounded input/output, missing traceability, package drift, or correctness/print guarantee blocks release.

## Independent final gates

These are adversarial and independent from focused unit tests.

| Gate | Independent proof | Exact PASS requirement |
|---|---|---|
| S7F-A | Architecture/source mutation audit | No provider-to-Blender callable path; source unchanged across all final scenarios |
| S7F-B | Context exfiltration audit | Forbidden-field canaries, geometry arrays, secrets and paths never leave allow-list; consent hash matches payload |
| S7F-C | Prompt-injection attack set | Every policy/destination/allow-list/approval override attempt denied with zero side effect |
| S7F-D | Structured-output parser attacks | Duplicate/non-finite/over-depth/over-size/prose/unknown-field payloads all rejected |
| S7F-E | Evidence-grounding truth | Missing/stale/unknown/conflicting evidence never becomes actionable or raises confidence |
| S7F-F | Candidate/strategy resolution attacks | Unknown IDs, fingerprint/operation/parameter mismatches and prohibited remesh all denied |
| S7F-G | Preview/approval separation | No path reaches execution without current preview and fresh bound approval |
| S7F-H | Cancellation/late response | All phases cancel safely; late output is quarantined and cannot be previewed/executed |
| S7F-I | Checkpoint/rollback fault injection | Pre-mutation checkpoint required; injected failure restores and verifies or blocks permanently |
| S7F-J | Accept/discard/cleanup ownership | Accept retains separate copy/source; discard/cleanup touches owned resources only |
| S7F-K | Audit/redaction/path security | Complete truthful bounded record, no secrets/raw data/absolute developer paths/traversal |
| S7F-L | Offline/provider outage | Sprint 0–6 local workflows and disabled assistance remain usable without network/credentials |
| S7F-M | Bounded performance | Boundary fixtures honor count/byte/time limits; no hidden retry/fallback; no threshold weakening |
| S7F-N | Registration/UI/package | Exact package installs under factory startup; all critical UI states work; drafts/tests absent |
| S7F-O | Representative dataset | 10/10 exact pass with zero source mutation/geometry payload/timeout/unclassified failure |
| S7F-P | Full dataset | 27/27 exact pass under nondestructive fake-provider path with resumable fingerprint truth |
| S7F-Q | Historical chain | All required Sprint 0–6 gates pass and frozen evidence files remain unchanged |
| S7F-R | First-failure/release audit | Initial failures retained, fixes regression-tested, approved provider/release decisions present, Git scope clean |

## Specification milestone status

These gates define future implementation acceptance. They are **NOT RUN** in this specification-only task.
