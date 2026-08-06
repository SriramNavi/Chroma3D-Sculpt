# Sprint 7 Engineering Specification — AI Recommendation Foundation

**Specification status:** implementation-ready draft for owner approval

**Scope decision:** Outcome A — explicitly defined by the approved roadmap

**Current frozen release:** `v0.7.0-alpha.1` at `63f98b8cef68dc977f6bd8c17972303fa7e3d05e`

**Proposed implementation release:** `0.8.0-alpha.1` (proposal only; metadata remains unchanged)

**Draft contract version:** `0.1.0-draft`

Sprint 7 evaluates bounded AI-assisted recommendations without allowing a model to control Blender, define geometry correctness, create executable code, or bypass the deterministic Sprint 0–6 safety boundary. This document specifies future work; Sprint 7 runtime implementation has not started.

## 1. Milestone identity

- **Sprint:** 7.
- **Milestone name:** AI Recommendation Foundation.
- **Purpose:** translate a user's bounded intent and consented current evidence into reviewable, machine-validated recommendations that point to existing deterministic candidates or strategies.
- **Problem:** Sprint 6 can search and rank deterministic strategies, but users must express goals through fixed settings and inspect trade-offs manually. The roadmap permits a constrained assistance layer that explains and selects among existing evidence without becoming a correctness authority.
- **User value:** faster navigation of existing diagnostic, repair, preparation, and optimization choices while retaining evidence, source protection, and artist control.
- **Dependencies:** Sprint 0 registration/export; Sprint 1 identity and diagnostics; Sprint 2 safety/checkpoints; Sprint 3 printability evidence; Sprint 4 process context and limits; Sprint 5 candidates/workspaces; Sprint 6 strategies, constraints, ranking, explanations, history, and audit.
- **Release positioning:** optional alpha evaluation. The deterministic local product remains complete and usable with the assistance feature disabled or unavailable.

## 2. Normative language and requirement registry

`MUST`, `MUST NOT`, `SHOULD`, and `MAY` are normative. Every `S7-REQ-*` requirement maps to tests and an acceptance gate in [TEST_MATRIX.md](docs/sprint7/TEST_MATRIX.md).

| ID | Requirement |
|---|---|
| S7-REQ-001 | The assistance layer MUST be optional and MUST NOT block any Sprint 0–6 local workflow. |
| S7-REQ-002 | Context extraction MUST be explicit, purpose-specific, consented, allow-listed, bounded, and local before an approved provider boundary is invoked. |
| S7-REQ-003 | Context MUST contain JSON-safe summaries and evidence references only; raw geometry arrays, Blender references, file contents, images, customer names, and developer absolute paths are prohibited. |
| S7-REQ-004 | Only current evidence whose source and dependency hashes validate MAY enter a request; stale, failed, skipped, or indeterminate facts remain labeled and cannot be promoted to truth. |
| S7-REQ-005 | Provider access MUST use one replaceable interface with explicit capability, privacy, retention, cost, timeout, cancellation, and failure declarations. No provider is selected by this specification. |
| S7-REQ-006 | Provider output MUST be treated as untrusted data and accepted only after bounded decoding and complete Draft 2020-12 schema, semantic, evidence-link, allow-list, and parameter validation. |
| S7-REQ-007 | JSON parsing MUST reject duplicate keys, booleans-as-numbers, NaN, infinity, excessive depth/size/counts, unknown fields, unknown enums, and invalid Unicode/control content where prohibited. |
| S7-REQ-008 | A recommendation MUST include reasons, assumptions, confidence, unmet prerequisites, limitations, evidence links, provider-exchange identity, and a clear advisory disclaimer. |
| S7-REQ-009 | Unknown evidence MUST NOT satisfy a hard safety requirement, authorize an operation, or raise recommendation confidence. |
| S7-REQ-010 | Actionable recommendations MUST resolve to an existing current Sprint 5 candidate or Sprint 6 strategy by exact ID and fingerprint; a model MUST NOT mint a candidate, operation implementation, or parameter set. |
| S7-REQ-011 | The initial allow-list MAY resolve `UNIFORM_SCALE`, `ORIENTATION`, and `BUILD_PLATE_TRANSLATION`; `BASE_STABILIZATION`, `REPAIR_REUSE`, `DECIMATION`, and `COMBINED_SCALE_ORIENTATION` remain policy-gated; `EXPERIMENTAL_REMESH` is prohibited in Sprint 7. |
| S7-REQ-012 | The deterministic translator MUST compare the recommendation's operation and canonical parameter echo to the referenced candidate/strategy and reject any mismatch; it MUST NOT clamp or repair model-authored values silently. |
| S7-REQ-013 | Recommendation generation and validation MUST be read-only. Preview MUST occur before approval, and preview MUST NOT itself authorize execution. |
| S7-REQ-014 | Execution MUST require a fresh explicit confirmation naming the selected recommendation and resolved deterministic plan; rejection and cancellation MUST execute nothing. |
| S7-REQ-015 | Any approved mutation MUST delegate to the existing Sprint 5/6 isolated workspace, checkpoint, stale-validation, comparison, restore, accept-copy, and discard interfaces. No mutation logic may be duplicated. |
| S7-REQ-016 | The protected source object, mesh, transforms, state, and signature MUST remain unchanged; acceptance MUST retain a separate copy and MUST NOT replace or delete the source. |
| S7-REQ-017 | Source, context, policy, provider contract, prompt template, schema, candidate/strategy, operation allow-list, profile, performance registry, implementation, and blend-file identities MUST participate in stale-state decisions as applicable. |
| S7-REQ-018 | Any bound-state change MUST invalidate derived recommendation, preview, and approval state; stale work requires a new context snapshot and provider exchange. |
| S7-REQ-019 | Cancellation MUST be monotonic, honored before provider dispatch, after provider return, and at every existing safe execution boundary; late provider responses MUST be retained only as cancelled audit evidence and never applied. |
| S7-REQ-020 | Provider, parse, validation, preview, checkpoint, execution, comparison, report, and cleanup failures MUST be distinct, truthful states with bounded recovery behavior. |
| S7-REQ-021 | Audit and reports MUST record consent, redacted prompt/request/response summaries, identities, validation decisions, approvals, operations, outcomes, stale/cancellation events, timings, usage/cost observations, warnings, and limitations without secrets or raw assets. |
| S7-REQ-022 | Credentials MUST never be stored in `.blend` data, reports, prompts, logs, preferences exported by the feature, or repository files; presence checks are boolean/redacted. |
| S7-REQ-023 | The feature MUST perform no hidden network activity. Destination, provider, data categories, purpose, retention statement, estimated cost/usage, and cancellation limitations MUST be visible before consent. |
| S7-REQ-024 | Safe path and filename handling MUST reject traversal, device names, unsafe deserialization, `eval`, `exec`, `pickle`, generated Python, shell commands, downloaded binaries, and model-authored URLs or destinations. |
| S7-REQ-025 | FAST, STANDARD, DEEP, and bounded CUSTOM modes MUST use centralized limits and retain `SKIPPED_LIMIT`, `BUDGET_EXHAUSTED`, and partial evidence honestly. |
| S7-REQ-026 | Provider timeouts, local wall time, output size, context size, recommendation count, evidence count, retry count, and report size MUST be bounded; timeout or budget failure cannot trigger an unapproved provider fallback. |
| S7-REQ-027 | Recommendation identity MUST be deterministic from canonical validated inputs and outputs; provider nondeterminism MUST be recorded rather than hidden, and there is no automatic learning or policy mutation. |
| S7-REQ-028 | The UI MUST expose consent, progress, evidence, assumptions, limitations, stale/cancel/failure states, preview, explicit approval, rejection, export, cleanup, and offline fallback without color-only meaning. |
| S7-REQ-029 | Reports and draft schemas MUST be versioned, bounded, JSON-safe, strict by default, and contain no raw Blender references or geometry arrays. |
| S7-REQ-030 | Synthetic truth, adversarial security, representative 10-model, full 27-model, historical regression, installed-package, and independent final gates MUST pass before release; physical printing and slicer work remain separate and cannot be inferred. |
| S7-REQ-031 | The implementation MUST preserve current version/package behavior until an authorized release workflow and MUST keep draft schemas out of the extension package. |
| S7-REQ-032 | No recommendation may claim geometry correctness, global optimality, cultural/iconographic correctness, guaranteed printability, manufacturing success, or direct high-quality sculpt generation. |

## 3. Scope

### 3.1 In scope

- A provider-neutral request/response contract and a backend/BYOK/hosted decision gate.
- A minimal consented context inventory derived from current local evidence.
- Natural-language intent mapped to strict recommendation JSON.
- Evidence grounding, confidence and prerequisite validation.
- Exact references to existing Sprint 5 candidates or Sprint 6 strategies.
- A deny-by-default operation policy, parameter-echo verification, preview, confirmation, rejection, cancellation, audit, redaction, and offline fallback.
- Test-only fake providers and recorded fixtures; no live provider is required for contract implementation.
- Optional future delegation to already implemented deterministic execution after every local safety gate passes.

### 3.2 Required for release

All requirements, `S7-01` through the final normal gate, and `S7F-A` onward must pass. The owner must approve a provider/deployment decision or explicitly release contract-only functionality with provider access disabled. The feature must remain optional and the local fallback must pass without credentials or network.

### 3.3 Optional and experimental

- A local model adapter is an optional future provider and has the same contract and security obligations.
- Live BYOK or hosted adapters are experimental until the decision gate passes.
- Provider-reported token/usage/cost values are observations, not trusted billing records.
- DEEP mode is evaluation depth, not permission for larger data categories or weaker privacy.

### 3.4 Out of scope, deferred, and prohibited

| Class | Items |
|---|---|
| Out of scope | Reference-image/vision workflows (Sprint 8), procedural/text-guided creation (Sprint 9), licensing/billing/marketplace/commercial service (Sprint 10), training/fine-tuning, RAG/vector stores, telemetry, accounts, collaboration. |
| Deferred decision | Backend versus direct provider boundary, BYOK versus hosted credentials, supported providers/models, retention terms, legal/privacy review, production quotas and price policy. |
| Deferred evidence | Physical printing, slicer comparison, material calibration, cultural/domain recommendation evaluation, Blender 4.5 LTS, and manual provider-specific production proof. |
| Prohibited | Arbitrary code, shell/system commands, model-authored URLs, raw geometry upload, hidden network, automatic execution/acceptance/source replacement, unsupported operations, `EXPERIMENTAL_REMESH`, supports, hollowing, drain holes, slicing, G-code, printer control, global-optimum or print-success claims. |

## 4. Personas and user workflows

### 4.1 Primary personas

- **Chroma3D operator:** wants a grounded explanation of which current strategy best matches a task.
- **Technical mesh specialist:** wants inspectable evidence and precise reasons to accept or reject a suggestion.
- **Studio owner/privacy approver:** decides whether any external provider boundary is allowed and which data categories may leave the machine.

### 4.2 Advisory-only recommendation

Entry: a selected mesh has current diagnostic/printability/optimization evidence and no active mutation. The user enters bounded intent, chooses a mode, reviews the exact context manifest and destination, and consents. The system snapshots hashes, builds a minimized request, invokes an approved provider or test adapter, strictly validates the response, grounds every link, and shows recommendations or a safe no-action result. The user may reject, cancel, export, or start a separate preview. No geometry is changed.

### 4.3 Preview and optional execution

The user selects one validated recommendation. The system revalidates all hashes, resolves an existing candidate/strategy, invokes the existing read-only preview, and displays operation identity, canonical parameters, expected effects, evidence, limitations, and required approvals. A second explicit confirmation is required. Approved execution uses only the Sprint 5/6 workspace and checkpoints. Comparison follows. Accept retains a separate copy; discard removes only owned resources. Source protection is continuous and all actions are reversible through existing checkpoint/restore boundaries.

### 4.4 Cancellation, recovery, and export

Cancellation before dispatch makes no call. Cancellation during an in-flight provider request records the request as cancelling, attempts adapter cancellation if supported, ignores any late result, and moves to `CANCELLED`. Cancellation during deterministic execution is honored only at documented safe operation boundaries; the existing coordinator restores on failure. Export writes bounded JSON/Markdown audit to a user-selected safe local path. A report failure does not change scene state or erase the in-memory audit.

### 4.5 Mutation classification

| Stage | Virtual/read-only | Workspace required | Approval | Reversible | Source protected |
|---|---:|---:|---:|---:|---:|
| Context, request, validation, recommendation | Yes | No | Consent for provider call | Cancel/discard evidence | Yes |
| Recommendation preview | Yes | Existing session may be required | Selection only | Yes | Yes |
| Deterministic execution | No | Yes, Sprint 5-owned | Fresh explicit confirmation | Checkpoint/restore/undo | Yes |
| Accept | No source mutation | Existing workspace | Explicit | Source retained; accepted copy is ordinary scene data | Yes |
| Discard/cleanup | Owned-resource mutation only | Yes | Explicit or failed-session policy | Source unaffected | Yes |

## 5. Architecture

Dependency direction is `UI -> assistance operators -> assistance coordinator -> pure validation/context/provider interfaces -> existing Sprint 5/6 coordinators -> typed models/utilities`. Provider adapters MUST NOT import Blender APIs. Provider output MUST never call existing operators directly.

| Layer | Future responsibility | Reused interface/boundary |
|---|---|---|
| Pure model | Frozen dataclasses/enums, canonical serialization, finite numeric validation, IDs and hashes | Sprint 5/6 `DeterministicModel`, `plain_value`, `stable_hash` patterns; no raw Blender references |
| Deterministic service | Context allow-list, policy validation, schema/semantic validation, evidence grounding, exact candidate/strategy resolution, recommendation identity | Sprint 1 signatures; Sprint 4 process/profile hashes; Sprint 6 constraint/evidence semantics |
| Provider interface | `capabilities()`, `prepare()`, `invoke()`, `cancel()`, `normalize_usage()`, `health()` with typed envelopes; fake adapter first | New replaceable boundary; no geometry or operator access |
| Blender integration | Snapshot active object/session IDs, display consent and results, delegate preview/execution | Existing analysis/session APIs and Sprint 6 `preview_selected_strategy`, `execute_selected_strategy` only after validation |
| Session/state | State machine, cancellation token, stale reasons, consent record, bounded exchange history | Sprint 5/6 source/workspace/session identities and stale checks |
| Profiles/settings | Assistance policy and mode limits with provenance/version/hash | `performance_registry.py`; existing printer/material/process/optimization/search policy hashes |
| Report/export | Strict JSON/Markdown projection, redaction, safe filename/path, bounded audit | Existing report/audit patterns and UTF-8 newline-terminated files |
| Acceptance/evidence | Fake-provider truth set, adversarial inputs, dataset runners, independent gates | Existing Sprint 0–6 regression/package/dataset infrastructure |

Mutation logic, checkpoints, comparisons, accept, discard, and cleanup MUST remain in Sprint 5/6. Sprint 7 adds no second execution engine.

## 6. State machine

### 6.1 States

`INITIAL`, `LOADING`, `READY`, `ANALYZING`, `EVIDENCE_AVAILABLE`, `STALE`, `PREVIEWING`, `APPROVAL_REQUIRED`, `EXECUTING`, `CANCELLING`, `CANCELLED`, `FAILED`, `RESTORED`, `ACCEPTED`, `DISCARDED`, `EXPORTED`, and `FINALIZED`.

- `ANALYZING` means context construction/provider exchange/response validation; it does not mean geometry analysis by a model.
- `EVIDENCE_AVAILABLE` requires a validated current recommendation set, including a valid `NO_ACTION` outcome.
- `RESTORED` is reachable only when delegated mutation failed or was cancelled after a checkpoint and restore was verified.

### 6.2 Legal transitions

| From | Event | To | Guard/effect |
|---|---|---|---|
| INITIAL | start | LOADING | Valid mesh/session and local policy |
| LOADING | current bounded context ready | READY | Context hash and consent manifest exist |
| LOADING | invalid/missing context | FAILED | No provider call |
| READY | consent and request | ANALYZING | Provider/deployment policy enabled and budget available |
| READY | cancel | CANCELLED | No provider call |
| ANALYZING | response fully validates | EVIDENCE_AVAILABLE | Store untrusted/raw hash and validated projection separately |
| ANALYZING | cancel requested | CANCELLING | Adapter cancellation requested once |
| ANALYZING | timeout/parse/provider/validation failure | FAILED | No preview or operation |
| CANCELLING | adapter ends or response arrives | CANCELLED | Late response cannot validate into actionable state |
| EVIDENCE_AVAILABLE | any bound hash changes | STALE | Clear preview and approval |
| EVIDENCE_AVAILABLE | select current actionable recommendation | PREVIEWING | Resolve exact existing candidate/strategy |
| EVIDENCE_AVAILABLE | reject/no-action/export | DISCARDED or EXPORTED | No mutation |
| PREVIEWING | current preview succeeds | APPROVAL_REQUIRED | Show canonical plan and limitations |
| PREVIEWING | mismatch/stale/failure | STALE or FAILED | No execution |
| APPROVAL_REQUIRED | explicit approve | EXECUTING | Revalidate all hashes; delegate to Sprint 5/6 |
| APPROVAL_REQUIRED | reject | DISCARDED | No execution |
| APPROVAL_REQUIRED | bound state changes | STALE | Approval revoked |
| EXECUTING | comparison ready | EVIDENCE_AVAILABLE | Execution evidence replaces recommendation-only view |
| EXECUTING | cancel at safe boundary | CANCELLING | Existing coordinator owns safe stop |
| EXECUTING | failure and verified rollback | RESTORED | No accept permitted until review |
| RESTORED | export/discard | EXPORTED or DISCARDED | Retain honest failure audit |
| EVIDENCE_AVAILABLE | accept separate copy | ACCEPTED | Existing accept-copy guard passes |
| EVIDENCE_AVAILABLE | discard workspace | DISCARDED | Owned resources only |
| Any terminal evidence state | export | EXPORTED | Export cannot change scene/session truth |
| ACCEPTED/DISCARDED/EXPORTED/CANCELLED/FAILED | close | FINALIZED | Release owned transient state safely |

All transitions not listed are illegal. In particular, `READY -> EXECUTING`, `ANALYZING -> APPROVAL_REQUIRED`, `STALE -> PREVIEWING`, `CANCELLED -> EXECUTING`, `FAILED -> ACCEPTED`, and any transition caused solely by provider output are rejected.

## 7. Data models

All runtime models are proposed frozen typed models; all report projections are JSON-safe copies. Draft schemas are under `schemas/sprint7-draft/` and are not extension assets.

| Model | Classification | Required content/reuse |
|---|---|---|
| `AssistanceSettings` | Runtime/internal | Mode, context categories, provider adapter ID, consent requirement, limits, redaction policy, retention policy reference, policy/provenance/hash |
| `AssistanceSession` | Runtime/internal | Session/state IDs, source/context/policy/provider/schema/implementation hashes, cancellation token, recommendation IDs, stale reasons, delegated Sprint 5/6 session ID |
| `ContextManifest` | Runtime + report + draft schema | Data-category inventory, bounded evidence references, omitted categories, consent, source identity/hash, profile/settings hashes, limitations |
| `EvidenceLink` | Stable draft schema + UI projection | Evidence ID/type/state/confidence/provenance/source report hash; never a Blender reference |
| `RecommendationCandidate` | Runtime + report | Rank, advisory action, existing candidate/strategy ID and fingerprint, reason, assumptions, confidence, prerequisites, evidence links, limitations |
| `ValidatedRecommendation` | Runtime + report + draft schema | Provider response hash, schema validation, semantic validation, resolved identities, actionable state, warnings |
| `ResolvedPlan` | Internal-only | Exact existing plan/strategy reference, canonical operation list/parameters, approval requirements; reuses Sprint 5/6 models rather than serializing new mutation logic |
| `OperationReference` | Internal + report projection | Existing operation enum/version/candidate ID/parameter hash; not a callable or command string |
| `CheckpointReference` | Internal/report reference | Existing Sprint 5 checkpoint ID/signature only; no mesh contents |
| `ComparisonReference` | Internal/report reference | Existing Sprint 5 comparison ID/hash/states/limitations |
| `ProviderContract` | Runtime + draft schema | Adapter ID/version, deployment class, capabilities, destination, data classes, retention, timeout/cancel/usage semantics, availability |
| `ProviderExchange` | Runtime + report + draft schema | Request/response hashes, timestamps, status, bounded sizes, usage/cost observations, errors; redacted text only in audit projection |
| `CancellationRecord` | Runtime + report | Request time, observed phase, adapter acknowledgement, safe-boundary result, late-response disposition |
| `StaleReason` | Stable enum | Source, workspace, context, policy, provider, prompt, schema, candidate/strategy, profile, registry, implementation, blend-file, or external-change mismatch |
| `AssistanceError` | Runtime + report | Code, phase, safe message, retriable flag, cause class, recovery action; no secrets/raw provider body |
| `PerformanceMetrics` | Runtime + report | Monotonic local phases, provider duration, bytes/counts, point memory observations, timeout owner, environment |
| `AssistanceAudit` | Report + draft schema | Complete bounded truthful trail, warnings, limitations, disclaimer |
| `AssistanceReport` | Stable public draft schema | User-facing validated recommendation/evidence/session summary; excludes raw provider body by default |

IDs are lowercase namespace-prefixed UUIDs or lowercase SHA-256 hashes as defined by each draft schema. Hashes use canonical UTF-8 JSON with sorted object keys, preserved list order, no NaN/infinity, and no insignificant whitespace. Booleans are never accepted where an integer/number is required.

## 8. Evidence semantics

| State | Meaning | Hard requirement | Ranking/selection effect |
|---|---|---:|---|
| `PASS` | Required deterministic validation completed and satisfied | May satisfy | Positive only with provenance |
| `WARNING` | Completed with reviewable concern | No, unless requirement explicitly permits warning | Penalize/disclose |
| `FAIL` | Completed and violated | Blocks | Exclude actionable recommendation |
| `SKIPPED_LIMIT` | Not run because a declared limit was reached | Never | Unknown/penalize; do not infer zero |
| `NOT_EVALUATED` | Check not requested/available | Never | Unknown |
| `INDETERMINATE` | Evidence cannot decide | Never | Unknown; cannot raise confidence |
| `NOT_APPLICABLE` | Check is irrelevant under validated preconditions | Only when requirement itself is inapplicable | Neutral with reason |
| `STALE` | Bound evidence no longer matches | Never | Invalidate recommendation/preview/approval |
| `CANCELLED` | Work intentionally stopped | Never | No actionable output |
| `BUDGET_EXHAUSTED` | Declared time/count/size/cost budget ended | Never | Preserve completed partial evidence; no hidden retry |

Provider confidence is an untrusted claim. Product confidence is derived locally from schema validity, current evidence coverage, unresolved prerequisites, provider evaluation evidence, and limitations. It is `HIGH`, `MEDIUM`, `LOW`, or `UNKNOWN`; `HIGH` cannot be produced when any required evidence is warning/unknown or when the provider/model is outside its approved evaluation set. Estimated evidence must be labeled `ESTIMATED`; provider claims never upgrade it to `MEASURED`.

## 9. Algorithms

### 9.1 Bounded context extraction

- **Inputs:** current source/session identity, selected context categories, current Sprint 1–6 reports, mode limits, consent policy.
- **Output:** canonical `ContextManifest` and minimized JSON payload.
- **Method:** validate report identities; filter through a fixed field allow-list; retain summaries, scalar metrics, enumerated states, bounded evidence IDs, and hashes; sort stable maps/IDs; record omitted/truncated fields; hash manifest and payload.
- **Bounds/complexity:** `O(R + E log E)` for report fields/evidence references; never traverse mesh geometry; zero exported vertices/edges/faces/triangles.
- **Skip/failure:** reject stale identity; mark optional unavailable categories; stop with `SKIPPED_LIMIT` if bounded evidence cannot be represented without silently dropping a required item.
- **Evidence/tests:** golden manifests, forbidden-field scans, consent matrix, deterministic hash, stale matrix, max-size fixtures.

### 9.2 Request construction and provider dispatch

- **Inputs:** user intent, manifest/payload hashes, immutable prompt template ID/version, provider contract, mode budget, consent record.
- **Output:** typed provider request or fail-closed error.
- **Method:** treat user intent/context as quoted untrusted data; construct a fixed instruction envelope demanding one strict JSON object; include allowed action enum and IDs, never callables; record destination/data classes; dispatch once through the adapter after consent.
- **Bounds:** input length/count/bytes, one provider request by default, zero automatic provider fallback, bounded timeout and output bytes.
- **Failure modes:** unavailable adapter, missing credentials, expired consent, unsupported capability, timeout, cancellation, cost budget; no hidden retries.
- **Deterministic identity:** request hash excludes volatile transport headers but includes canonical content, contract/template/policy hashes, mode, and consent scope.

### 9.3 Bounded strict JSON decoding

- **Inputs:** provider bytes and declared content type.
- **Output:** parsed plain JSON object plus raw response hash.
- **Method:** enforce byte limit before decode; strict UTF-8; reject BOM/control policy violations; use duplicate-key detection and `parse_constant` rejection; enforce maximum nesting/nodes/string lengths; require exactly one object and no prose/code fences; then validate against the draft schema.
- **Complexity:** `O(B)` time and space within byte/node caps.
- **Failures:** malformed/trailing JSON, duplicate fields, non-finite numbers, booleans as numbers, unknown fields/enums, over-limit content; all become non-actionable `FAIL`.

### 9.4 Semantic grounding and confidence derivation

- **Inputs:** schema-valid response, context manifest, evidence registry, current candidate/strategy sets, policy.
- **Output:** `ValidatedRecommendation` set or validated `NO_ACTION`.
- **Method:** resolve every evidence ID and fingerprint; verify current state and allowed evidence state; ensure reasons do not cite absent facts; verify prerequisites; derive local confidence from the weakest required evidence and evaluation-set coverage; retain unsupported statements as limitations or reject when material.
- **Bounds/complexity:** hash maps yield `O(C + L)` for candidates and links; recommendation/evidence counts are mode-bounded.
- **Truth rule:** provider prose cannot establish geometry, cultural, iconographic, print, or manufacturing correctness.

### 9.5 Deny-by-default action resolution

- **Inputs:** grounded recommendation, current Sprint 5 candidate/Sprint 6 strategy registry, operation policy and hashes.
- **Output:** exact `ResolvedPlan` or rejection.
- **Method:** action enum is one of `NO_ACTION`, `REQUEST_FRESH_ANALYSIS`, `RECOMMEND_EXISTING_CANDIDATE`, `RECOMMEND_EXISTING_STRATEGY`; resolve exact ID/fingerprint; compare operation and canonical parameter hash; confirm allow-list tier and approval prerequisites; return an immutable reference to the existing plan.
- **Bounds:** no more operations than the referenced existing bounded plan; no provider-created loops, URLs, scripts, filenames, operator IDs, or arbitrary parameters.
- **Failure:** unknown/mismatched/stale/disallowed/experimental reference rejects the entire actionable recommendation. Values are never silently corrected.

### 9.6 Preview, approval, and delegated execution

- **Inputs:** current resolved plan, source/session signatures, fresh explicit approval.
- **Output:** existing preview/operation/comparison/audit records.
- **Method:** revalidate all identities; call existing Sprint 6 preview; display canonical plan; on separately captured approval delegate existing execution; checkpoint each mutation; compare; accept separate copy or discard.
- **Failure/recovery:** existing Sprint 5 rollback is authoritative. A failed restore blocks further action and records `FAILED`, never `PASS`.

### 9.7 Cancellation and budget handling

- **Inputs:** monotonic cancellation token, active phase, local/provider/execution budget usage.
- **Output:** terminal/partial state and cancellation record.
- **Method:** check before/after each phase and safe execution boundary; request adapter cancellation once; quarantine late output; retain completed evidence; clear approval on cancel/stale.
- **Limit:** cancellation never expands cleanup ownership or authorizes source changes.

## 10. Safety model

The Sprint 2 [Repair Safety Contract](REPAIR_SAFETY.md) and Sprint 5/6 boundaries remain authoritative for mutation. Additional Sprint 7 invariants are:

1. Model output is untrusted data, never control flow.
2. A recommendation selects only an existing current deterministic object by exact identity.
3. No provider adapter imports Blender or calls an operator/coordinator.
4. Consent is scoped to one declared payload/destination/purpose and expires when any of those change.
5. Provider response, validation, preview, and approval are separate state transitions.
6. Approval is revoked by any stale event or changed recommendation.
7. Provider failure does not block deterministic local workflows and cannot cause a provider switch without new consent.
8. Raw provider data is bounded and not persisted by default; audit retains hashes and redacted summaries.
9. No credential, raw asset, geometry array, or developer path enters context, logs, reports, or `.blend` state.
10. Cleanup removes only Sprint 7 transient data and existing session-owned workspace resources through their owners.

## 11. Performance modes

Detailed provenance and release measurement rules are in [PERFORMANCE_POLICY.md](docs/sprint7/PERFORMANCE_POLICY.md). Initial values are `PROVISIONAL_PROJECT_DEFAULT`, not provider guarantees or release PASS thresholds.

| Mode | Geometry exported | Max recommendation candidates | Max evidence links | Local wall-time warning | Provider worker timeout | Memory observation |
|---|---:|---:|---:|---:|---:|---|
| FAST | 0 triangles | 4 | 64 | 5 s | 15 s | phase-boundary point observations |
| STANDARD | 0 triangles | 8 | 256 | 15 s | 45 s | phase-boundary point observations |
| DEEP | 0 triangles | 16 | 1,024 | 45 s | 120 s | phase-boundary point observations |
| CUSTOM | 0 triangles | 1–32 | 1–2,048 | 1–60 s | 1–180 s | same; values validated against maxima |

Existing diagnostic/strategy triangle, sample, and candidate limits remain owned by `performance_registry.py`; Sprint 7 consumes their outputs and does not raise them. `BUDGET_EXHAUSTED` and `SKIPPED_LIMIT` preserve completed evidence. A worker timeout ends that exchange; it never changes provider, retries, or executes a partial response.

## 12. Profiles and settings

No new printer/material profile is required. Sprint 7 reuses immutable snapshots and hashes for printer, material, composed process, feature flags, Sprint 5 optimization policy/objectives/candidates, Sprint 6 search policy/constraints/strategy set/frontier/ranking, and performance registry.

The new `AssistancePolicy` is a local versioned profile with deployment state (`DISABLED`, `TEST_ONLY`, `APPROVED_LOCAL`, `APPROVED_BYOK`, `APPROVED_HOSTED`), context-category allow-list, action tiers, mode limits, provider contract reference, consent/redaction/retention settings, prompt/schema versions, and provenance. Unknown fields, duplicate IDs, invalid hashes, booleans-as-numbers, non-finite numbers, unsafe mode values, hidden provider enablement, or prohibited operations fail closed. Custom policies must record owner, rationale, base policy/version, changes, review status, and hash; they cannot exceed compiled maxima or enable a provider/operation without explicit approval.

## 13. Blender UI contract

The future panel belongs below Intelligent Optimization in the existing Chroma3D sidebar and is labeled **AI Recommendation (Optional)**. It contains:

- provider/deployment status, offline availability, privacy/retention summary, and credential-presence status (never credential value);
- intent input with character counter, mode, bounded context-category toggles, and **Review Context & Consent**;
- a context manifest showing included/omitted categories, record counts, destination, purpose, retention, estimated usage/cost status, and consent checkbox;
- **Request Recommendation**, progress phase, elapsed time, cancellation availability, and budget/timeout status;
- bounded recommendation list with confidence, reasons, assumptions, unmet prerequisites, evidence states/links, limitations, and `NO_ACTION` state;
- **Reject**, **Preview Existing Candidate/Strategy**, and **Export Audit**;
- preview box with resolved IDs/fingerprints, canonical operations/parameters, workspace/source status, warnings, and **Approve Deterministic Execution**;
- existing comparison/accept-copy/discard actions after delegated execution.

Stale state disables preview/approval and requires **Refresh Context**. Cancellation is visible and cannot be represented as failure or success. Focus order follows workflow, controls use descriptive labels, warnings are text plus icon (not color-only), long strings wrap/truncate with detail view, and reduced UI density does not hide limitations.

## 14. Reports and draft schemas

Draft schemas are `0.1.0-draft`, strict by default, and intentionally excluded from packaging:

- `assistance_policy.schema.json`
- `context_manifest.schema.json`
- `provider_exchange.schema.json`
- `ai_recommendation.schema.json`
- `assistance_session.schema.json`
- `assistance_report.schema.json`
- `assistance_audit.schema.json`

Reports include schema/software version; environment; source identity/signature; settings and profile/policy/provider/prompt/schema/implementation hashes; consent; bounded context inventory; redacted intent/exchange hashes; evidence states, confidence, provenance, limitations, skipped checks, stale/cancellation events, usage/cost observations, monotonic runtime phases, point memory observations, approvals, resolved operations, checkpoints/comparisons by reference, recovery/cleanup, audit trail, and disclaimers. They exclude raw Blender references, geometry arrays, credentials, raw assets, full absolute developer paths, and unbounded provider bodies.

## 15. Security and privacy

- Local deterministic work remains available offline; assistance is disabled safely when its approved provider is unavailable.
- Context minimization is allow-list based; consent is informed, granular, single-purpose, and hash-bound.
- Prompt injection is assumed possible. Prompt text, scene names, evidence strings, and provider output are all untrusted; none may alter policy, schemas, destinations, allow-lists, or approval requirements.
- Output handling is strict, size-bounded, deny-by-default, and separated from execution.
- Safe local export uses user-selected paths, canonical `Path` handling, collision-safe names, and traversal/device-name rejection.
- No `eval`, `exec`, dynamic imports, pickle, shell, downloaded code/binaries, provider-authored URLs, secrets, telemetry, or hidden logging.
- Default retention is in-memory session data plus explicitly exported redacted audit. Any provider retention is displayed before consent and must be approved by the decision gate.

## 16. Failure and recovery

| Failure | Required behavior |
|---|---|
| Invalid source/unsupported geometry | Fail before context/provider; preserve source; offer deterministic diagnostics where applicable |
| Invalid/missing profile or policy | Fail closed; identify field/provenance; no implicit default enabling network/action |
| Stale evidence or deleted/replaced object/datablock | Mark `STALE`; clear preview/approval; require fresh local evidence/context |
| Provider unavailable/timeout/rate or budget limit | Record phase-specific state; no hidden retry/switch; local workflows remain available |
| Cancellation | Quarantine late response; execute nothing; retain bounded cancellation record |
| Malformed/injected/oversized response | Reject entire response; no partial executable extraction |
| Checkpoint creation failure | Existing coordinator blocks mutation; recommendation remains advisory only |
| Partial mutation/operation failure | Existing checkpoint restore; record whether restore verified; block accept if not |
| Comparison failure | Do not infer improvement; state `INDETERMINATE`/`FAIL`; allow restore/discard/export |
| Report failure | Preserve scene/session truth; expose safe error; retry only user-selected export |
| Cleanup failure | Preserve source; list owned residue by safe identity; do not delete unrelated resources |
| Blender restart | No implicit provider retry or execution; unfinished session is non-resumable unless a future approved persistence contract exists; workspace follows existing Sprint 5 policy |

## 17. Historical compatibility

| Sprint | Relationship | Compatibility requirement |
|---|---|---|
| Sprint 0 | Consumes registration/export conventions | Leaves version, manifest, core panel registration and packaging unchanged until implementation release |
| Sprint 1 | Consumes source identity, current diagnostic evidence and explicit states | Never reclassifies or mutates diagnostic truth |
| Sprint 2 | Consumes safety, repair candidates, checkpoints, rollback, audit | No repair selection without existing eligible explicit candidate and approval |
| Sprint 3 | Consumes printability reports/profiles and virtual recommendations | Keeps advisory/no-guarantee boundary and physical calibration limitations |
| Sprint 4 | Consumes composed process/profile/feature/performance hashes | No support/resin/slicer automation; provenance remains visible |
| Sprint 5 | Resolves existing candidates/plans and delegates workspace execution | No duplicate mutation logic; accept/discard/source protection unchanged |
| Sprint 6 | Resolves existing strategies/frontier/ranking/explanations/history | AI does not replace deterministic ranking truth or claim broader optimality |

Historical schemas remain unchanged. Sprint 7 adds versioned additive contracts and adapters. Unsupported old reports are `NOT_EVALUATED` or require regeneration; they are never silently upgraded.

## 18. Release and acceptance boundary

The future implementation is releasable only after [ACCEPTANCE_GATES.md](docs/sprint7/ACCEPTANCE_GATES.md) passes, owner decisions are recorded, the live provider boundary (if any) has direct development-environment evidence, and the exact package passes security/install gates. Provider-independent contracts may be implemented with adapters disabled. No current metadata, package, tag, or frozen Sprint 6 evidence changes in this specification milestone.

## 19. Research basis

Repository sources and confidence are recorded in [SCOPE_EVIDENCE.md](docs/sprint7/SCOPE_EVIDENCE.md). Narrow external primary sources and supported claims are recorded in [RESEARCH_SOURCES.md](docs/sprint7/RESEARCH_SOURCES.md). External guidance informs threat/validation planning but does not override the repository's stricter local, source-protecting boundary.

## 20. Specification decision

**SPRINT 7 SPECIFICATION ACCEPTED WITH OPEN QUESTIONS**

The core milestone is explicit and implementation can begin safely with provider-neutral contracts, strict validators, a test-only adapter, and deployment disabled. Live provider/backend/BYOK/hosted choices remain owner decisions with the safe temporary behavior documented in [OPEN_QUESTIONS.md](docs/sprint7/OPEN_QUESTIONS.md).
