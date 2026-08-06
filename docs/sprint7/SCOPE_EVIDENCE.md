# Sprint 7 Scope Evidence

## Decision

**Outcome A — Sprint 7 is explicitly defined.** `TECHNICAL_ROADMAP.md` names **Sprint 7 — AI Recommendation Foundation** and supplies an objective, scope, and gates. `PRODUCT_REQUIREMENTS.md` provides the matching user journey and `FR-AI-001` through `FR-AI-010`. The selected scope is therefore explicit; it is not inferred from Sprint numbering or from Sprint 6's name.

## Evidence table

| Source | Section | Exact intent | Sprint 7 relevance | Confidence |
|---|---|---|---|---|
| `TECHNICAL_ROADMAP.md` | Sprint 7 — AI Recommendation Foundation | Evaluate bounded AI-assisted recommendations without model control of Blender or geometry correctness. | Names milestone and primary boundary. | EXPLICIT |
| `TECHNICAL_ROADMAP.md` | Sprint 7 Scope | Backend decision gate; provider abstraction; versioned prompt-to-JSON; minimal consented context; operation allow-list; reasons/confidence/prerequisites/evidence; preview/confirmation/cancel/audit; BYOK/hosted evaluation. | Defines complete directly supported core. | EXPLICIT |
| `TECHNICAL_ROADMAP.md` | Sprint 7 Gates | Threat/privacy/provider contracts, structured-output evaluation, deny-by-default operations, injection tests, consent UI, offline fallback, usage/cost model and human review must pass. | Defines release evidence. | EXPLICIT |
| `PRODUCT_REQUIREMENTS.md` | Journey D | Analyze, extract bounded context, request structured recommendation, validate schema/allow-list, show deterministic command/impact, approve, execute existing operator, record result. | Defines user journey and reuse requirement. | EXPLICIT |
| `PRODUCT_REQUIREMENTS.md` | FR-AI-001–007, FR-AI-010 | Structured commands, consented context, explainable output, allow-listed deterministic operations, preview/approval, audit/redaction, provider abstraction, no arbitrary execution. | Normative functional scope. | EXPLICIT |
| `PRODUCT_REQUIREMENTS.md` | FR-AI-008 | Evaluate BYOK and hosted options without premature commitment. | Decision gate, not an approved deployment. | EXPLICIT |
| `PRODUCT_REQUIREMENTS.md` | NFR-SEC/PRIV/OFF/DET/LOG/REC | No hidden network/dynamic execution; explicit upload consent/inventory/retention/redaction; local core offline; deterministic operations and bounded evidence. | Non-functional constraints. | EXPLICIT |
| `PRODUCT_REQUIREMENTS.md` | SR-004–012 | Revalidate state; deny unknown operations; no code/shell; disclose network; preserve uncertainty; recovery/cancel; never auto-apply AI. | Safety invariants. | EXPLICIT |
| `VISION.md` | Product identity/principles | Constrained recommendations become reviewable allow-listed deterministic operations; prefer deterministic operations; no arbitrary generated code. | Product-level intent and non-goal. | EXPLICIT |
| `TECHNICAL_ROADMAP.md` | Architecture Evolution | Local extension remains authoritative; optional service receives minimal consented data and fails without blocking local workflows. | Establishes provider/service dependency direction. | EXPLICIT |
| `TECHNICAL_ROADMAP.md` | Build versus Buy | Own deterministic allow-list/safety; integrate LLM/vision APIs only after provider/security evaluation. | Provider abstraction and ownership boundary. | EXPLICIT |
| `ARCHITECTURE.md` | Intelligent/Controlled Optimization | Sprint 6 search is read-only and delegates all mutations to Sprint 5 workspaces/checkpoints; no auto-execution. | Existing interfaces Sprint 7 must reuse. | EXPLICIT |
| `REPAIR_SAFETY.md` | Source/checkpoint/approval/audit contracts | Source immutable, workspace independent, explicit approval, checkpoint before mutation, truthful audit. | Permanent mutation boundary. | EXPLICIT |
| `PROJECT_RULES.md` / `AGENTS.md` | Sprint 5/6 policy | Unknown evidence never passes; workspace-only execution; no source replacement/slicer/G-code/physical/global-optimum claims. | Permanent compatibility and non-goals. | EXPLICIT |
| `ROADMAP.md` | Sprint 7 and later phases | Sprint 7 not started; later phases include bounded AI-assisted planning/authoring. | Confirms status but not detailed scope. | STRONGLY_IMPLIED |
| `TECHNICAL_ROADMAP.md` | Sprint 8 | Reference images/vision and culturally sensitive suggestion evaluation. | Must not be pulled into Sprint 7. | EXPLICIT |
| `TECHNICAL_ROADMAP.md` | Sprint 9 | Procedural and text-guided creation from governed assets/rules. | Must not be pulled into Sprint 7. | EXPLICIT |
| `TECHNICAL_ROADMAP.md` | Sprint 10 | Licensing, billing/commercial provider support and release operations. | Commercial service is deferred. | EXPLICIT |
| Sprint 3–6 evidence limitations | Acceptance/final summaries | Physical prints, slicer comparison, material calibration, Blender 4.5 LTS and some manual panel UAT remain unrun. | Cannot be claimed or used as AI training/correctness truth. | EXPLICIT |
| Existing provider/library code | Repository inventory | No Sprint 7 provider, runtime, schema, branch, tag, path, or package asset existed at preflight. | Confirms greenfield specification boundary only. | EXPLICIT |

## Dependencies available

- Stable JSON-safe typed-model and deterministic-hash patterns.
- Current diagnostic, printability, preparation, optimization, and strategy evidence with explicit states and hashes.
- Sprint 5 candidate/plan/workspace/checkpoint/comparison/accept/discard services.
- Sprint 6 strategy, constraint, frontier, ranking, explanation, history, cancellation, and audit services.
- Local profiles, central performance registry, report exporters, dataset workers, package/security validators, and 27-model rights-cleared corpus.

## Product gaps addressed

Sprint 6 exposes deterministic trade-offs but has no bounded natural-language intent contract, provider abstraction, consented context boundary, structured-output validator, prompt-injection threat model, or AI-specific audit/redaction model. Sprint 7 fills those gaps without changing geometry algorithms.

## Explicit non-goals and later milestones

- Sprint 8 owns reference-image and vision assistance.
- Sprint 9 owns procedural/text-guided creation and governed rule packs.
- Sprint 10/commercial evaluation owns hosted usage accounting, billing, licensing, and production service operations.
- Support generation, hollowing, drain holes, slicing, G-code, printer control, arbitrary code, hidden network, source replacement, physical claims, global optimum, and print guarantees remain prohibited.

## Ambiguities retained as owner decisions

The roadmap does not choose provider/model, local versus remote inference, backend versus direct provider, BYOK versus hosted credentials, retention terms, production quota/cost policy, or precise evaluation thresholds. These do not block provider-neutral contracts or offline test implementation. They block enabling a live provider for release and are recorded in `OPEN_QUESTIONS.md`.
