# Sprint 7 Open Questions and Decisions

## Decision semantics

Questions below do not authorize assumptions. The safe temporary behavior is normative until the named owner records a decision. Product questions block enabling a live provider, but they do not block provider-neutral contracts, strict local validators, fake adapters, context minimization, or deny-by-default tests.

## Decisions supplied by the Sprint 7 implementation authorization

- `Q-PROD-001/Q-ENG-001`: direct user-initiated HTTPS, no backend, account, billing, telemetry, or hosted credentials.
- `Q-PROD-002`: OpenAI-first adapter behind a vendor-neutral interface; model ID is explicit and configurable.
- `Q-PROD-003/Q-ENG-002`: BYOK from `OPENAI_API_KEY` or session-only process memory; zero persistence; bounded summary-only context and per-request hash-bound consent.
- `Q-PROD-004/Q-ENG-003`: exact existing Sprint 5/6 target preview and execution delegation are included behind safe-default operations, mandatory preview, and fresh approval. Gated operations require a local policy; remesh is prohibited.
- `Q-ENG-004`: requests are stateless; no provider conversation or unfinished assistance session resumes after restart.
- `Q-UX-001`: collapsed child panel below Intelligent Optimization.
- `Q-UX-002`: hashes and bounded redacted projections only; no raw prompt/response persistence by default.
- `Q-UX-003`: deterministic Sprint 6 fallback remains available and is labeled non-provider-generated.

Live-provider model qualification, provider SLA/cost observations, privacy/legal review for production use, Blender 4.5 LTS, and installed-panel UAT remain evidence questions rather than implementation assumptions.

## Blocking product decisions

| ID | Question | Why it matters | Current evidence | Safe temporary behavior | Required owner | Decision milestone |
|---|---|---|---|---|---|---|
| Q-PROD-001 | Is Sprint 7 released as contract-only evaluation, local inference, direct BYOK, hosted service, or a subset? | Determines data boundary, consent, support and release claims. | Roadmap requires evaluation and forbids premature commitment. | `TEST_ONLY`; all live adapters disabled. | Product + engineering + privacy/security | Before S7J/live-provider work |
| Q-PROD-002 | Which provider/model/deployment versions, if any, are supported? | Structured output, cancellation, retention, cost and evaluation are version-specific. | No provider exists or is approved. | Provider interface and fake adapter only. | Product + engineering | Before enabling any adapter |
| Q-PROD-003 | What data categories and provider retention terms are acceptable? | External processing may expose customer/asset context. | PRD requires purpose-specific consent, inventory, retention and redaction. | Export only scalar summaries/evidence IDs after per-request consent; no geometry/images/names/paths; unknown retention blocks call. | Privacy/security + product | Before first development provider call |
| Q-PROD-004 | Is actionable execution included in the first Sprint 7 alpha, or recommendations/export only? | Changes safety/UAT/package scope. | Journey D permits execution only through existing operator after approval. | Implement contracts/read-only recommendation first; execution feature disabled until S7F safety gates pass. | Product + engineering | Before S7F UI exposure |

## Blocking engineering decisions

| ID | Question | Why it matters | Current evidence | Safe temporary behavior | Required owner | Decision milestone |
|---|---|---|---|---|---|---|
| Q-ENG-001 | Is an optional service/backend justified versus direct adapter/local inference? | Changes credentials, CORS/network, updates, abuse controls, logs and operations. | Technical roadmap says add backend only after privacy/cost/latency/licensing/update/support evidence. | No backend; provider-neutral interface; test adapter only. | Architecture + security + operations | S7J decision gate |
| Q-ENG-002 | Where may credentials live for an approved BYOK adapter? | Blender preferences and reports must not leak secrets. | Credentials cannot be stored in `.blend`, reports, repository or logs. | Accept no credential; adapter disabled. Evaluate OS credential store or ephemeral process input separately. | Security + desktop engineering | Before BYOK implementation |
| Q-ENG-003 | Which current candidate/strategy operations enter each allow-list tier? | Controls risk and manual approval. | Safe default candidates exist; remesh is deferred; some operations are experimental/gated. | Safe tier: scale/orientation/translation references only; gated tier disabled; remesh prohibited. | Geometry/safety owner | Before S7E completion |
| Q-ENG-004 | What persistence, if any, survives Blender restart? | Provider exchanges and unfinished workspaces need truthful recovery. | Current strategy history/session is local/exported; workspace restart persistence is limited. | No implicit resume, retry or execution; retain user-visible workspace per existing owner; exported audit only. | Architecture + UX | Before external alpha |

## Calibration questions

| ID | Question | Why it matters | Current evidence | Safe temporary behavior | Required owner | Decision milestone |
|---|---|---|---|---|---|---|
| Q-CAL-001 | What context/output/latency/cost limits fit real operator tasks? | Provisional bounds may be too tight or expensive. | No Sprint 7 runtime/provider measurements. | Use `PERFORMANCE_POLICY.md` provisional maxima; classify failures honestly; do not weaken. | Performance + product | After fake baseline, before release thresholds |
| Q-CAL-002 | What evaluation-set score permits `HIGH` product confidence? | Model confidence is not product confidence. | Human-review rubric is a roadmap gate; no results exist. | Cap at `LOW`/`UNKNOWN` outside approved evaluation set; unknown evidence blocks hard rules. | Product + domain + QA | Before live recommendations |
| Q-CAL-003 | What provider usage/cost observation is reliable enough to display? | Provider estimates may differ from billed usage. | Hosted accounting is deferred to commercial evaluation. | Label as estimate/provider-reported; do not bill or enforce paid quota. | Product + operations | S7J/Sprint 10 boundary |

## UX questions

| ID | Question | Why it matters | Current evidence | Safe temporary behavior | Required owner | Decision milestone |
|---|---|---|---|---|---|---|
| Q-UX-001 | Should assistance be a child panel or separate tab? | Affects hierarchy without changing safety. | Existing workflow ends in Intelligent Optimization panel. | Child panel below Intelligent Optimization, collapsed/disabled by default. | Product design + Blender UX | Before S7G |
| Q-UX-002 | How much redacted prompt/response text should audit show? | Debuggability conflicts with privacy. | Audit is required; raw provider bodies are not. | Hashes plus bounded user-reviewed redacted summaries; raw body in memory only and discarded by default. | UX + privacy + support | Before report schema promotion |
| Q-UX-003 | How are provider outage and offline fallback worded? | Must not imply deterministic workflows are unavailable. | Local core must remain offline. | “AI Recommendation unavailable; local Chroma3D tools remain available.” | UX + support | Before S7G manual UAT |

## Future research

| ID | Question | Safe boundary | Owner | Milestone |
|---|---|---|---|---|
| Q-RES-001 | Can a local model meet quality/performance/privacy goals? | Same strict contracts, no Blender/control access, no automatic execution. | Research + security | Post-contract evaluation |
| Q-RES-002 | How should adversarial/evaluation sets evolve without storing sensitive prompts? | Sanitized synthetic/permissioned records with provenance and retention. | QA + privacy | S7H onward |
| Q-RES-003 | Which recommendation tasks produce measurable operator value? | Measure accepted/rejected/no-action quality; no telemetry without separate opt-in policy. | Product research | Internal UAT |
| Q-RES-004 | Reference-image/vision assistance? | Explicitly Sprint 8; do not implement in Sprint 7. | Product/domain/privacy | Sprint 8 decision |

## Deferred manual and physical validation

- Manual installed-panel UAT for the generated Sprint 7 package.
- Blender 4.5 LTS compatibility.
- Live provider development/production behavior until authorized.
- Real slicer comparison, FDM/resin material calibration, and physical printing.
- Cultural/iconographic correctness review and reference-image rights work (later milestones).

These remain `NOT RUN` and cannot be converted into software PASS claims.
