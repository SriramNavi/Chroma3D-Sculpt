# Chroma3D Sculpt — Technical Roadmap

## Roadmap Principles

- Diagnostics precede repair; repair decisions must refer to completed evidence.
- Safe, reversible repair precedes optimization or automated creation.
- Real-model evidence precedes AI recommendations and commercial claims.
- The deterministic geometry core remains local and offline-capable.
- A backend is introduced only when licensing, collaboration, asset delivery, AI routing, or another validated need requires it.
- Commercial systems follow demonstrated product value and production UAT.
- Every milestone has automated, manual, performance, safety, and evidence gates appropriate to its risk.
- A milestone is not complete because code exists; validation and accepted evidence are required.
- Heuristic results remain labeled, bounded, and reviewable, and no stage promises printability.

## Current Baseline

### Sprint 0 — Foundation

**Status:** Complete, merged to `main`, and tagged `v0.1.0-alpha.1`.

Sprint 0 established the Windows-first modern Blender extension, registration lifecycle, Chroma3D sidebar, session-only state, read-only mesh analysis, JSON export, deterministic packaging, Blender discovery, test runner, and acceptance tooling. Blender 4.4.3 validation passed nine acceptance gates, including a 146,968-vertex procedural statue-like fixture, geometry immutability, registration, package validation, and Blender stability.

### Sprint 1 — Production Diagnostics

**Status:** Implemented, independently validated, accepted, merged to `main`, and tagged `v0.2.0-alpha.1`.

Sprint 1 added Standard and Deep profiles; explicit evaluation states; exact edge incidence and vertex face-fan diagnostics; topological watertightness; stable shell decomposition; main, tiny-candidate, disconnected-external, and possibly-internal classifications; world-space dimensions, area, reliable volume, and orientation; bounded self-intersection candidates and containment heuristics; current-orientation build-volume checks; bounded issue evidence; stale-analysis protection; issue selection; timings; and JSON schema 2.0.

Repository evidence records 48 passing Blender background tests, 12 Sprint 1 acceptance gates, preserved Sprint 0 regression, package/security validation, and independent final validation on Blender 4.4.3/Windows. Across those Windows and Blender 4.4.3 runs, Standard analysis of the current approximately 147,000-vertex synthetic fixture has ranged from about 12 to 29 seconds against the repository's 20-second performance warning threshold. Dense-mesh performance remains active technical debt. The synthetic range is not a hard guarantee for real production models, and benchmarking on real Chroma3D statues is still required.

Interactive installed-panel and permissioned real Chroma3D statue analysis remain useful deferred evidence; Sprint 1 merge and tag checkpoints are complete.

## Sprint 2 — Safe Mesh Repair

**Status:** Implemented and accepted by automated Blender 4.4.3 gates on `feature/sprint-2-safe-mesh-repair` as `0.3.0-alpha.1`. Installed-panel smoke testing, Blender 4.5 LTS compatibility, and real-statue repair UAT remain deferred. Sprint 3 has not started.

**Objective:** Introduce controlled, reversible mesh-repair operations without weakening the read-only diagnostic path or original-asset safety.

### Scope

- Protect the original and create a traceable repair workspace copy.
- Build a versioned repair-plan model from current, non-stale diagnostic evidence.
- Preview parameters, affected-element counts, preconditions, warnings, and expected result for each operation.
- Provide tolerance-bounded merge-by-distance.
- Remove approved loose geometry, zero-length edges, and degenerate faces.
- Repair normals when topology and orientation preconditions permit.
- Fill only policy-approved tiny holes within explicit topology and size limits.
- Review and remove tiny-shell candidates individually or through an explicitly approved batch.
- Re-run analysis and compare issues, physical metrics, topology signatures, and new warnings before acceptance.
- Export a repair audit report linking source analysis, plan, approvals, operation results, and before/after analyses.
- Support Blender undo, safe-boundary cancellation, and recovery from interruption.

### Explicit exclusions

- Aggressive remeshing or topology-wide reconstruction.
- Automatic reconstruction of large or ambiguous holes.
- AI-generated repair decisions.
- Unreviewed destructive operations or automatic deletion based only on heuristic classification.
- Modifier-output repair, arbitrary Python execution, printability claims, or support generation.

### Implemented technical foundation

- Sprint 1 results remain independently usable and analysis schema 2.0 is unchanged.
- Protected source and independent workspace identities, full source signatures, live-session checkpoints, and rollback are implemented.
- Typed repair-plan, candidate, operation, checkpoint, comparison, session, and repair-audit models serialize without Blender objects; repair audit schema is 1.0.
- Repair operators, coordinator, geometry services, diagnostics, UI, and serialization remain separate.
- Centralized millimetre tolerances, deterministic safe ordering, bounded evidence, explicit selection, and failure restoration are implemented.
- Blender progress reporting is synchronous. Safe-boundary undo/restore is implemented; mid-operation cancellation remains deferred.
- Focused fixtures cover safe boundaries, stale state, idempotency, undo, restore, failed-operation rollback, finalization, audit, and stress. Restart persistence and real-model UAT remain deferred.

### Acceptance gates

1. The original object's geometry, transforms, materials, name, modifiers, and source file remain unchanged in all default paths.
2. Source and repair-workspace identities remain distinct for the live session and cannot be confused; unfinished sessions are explicitly not restart-persistent.
3. Each repair operation passes focused boundary fixtures, mixed-defect fixtures, and no-op cases.
4. Stale evidence, invalid context, unsupported topology, and out-of-policy parameters fail without partial hidden edits.
5. Before/after analysis exposes resolved, unchanged, and newly introduced findings.
6. Checkpoint undo, restore, failed-operation rollback, and cleanup pass automated checks; mid-operation cancellation and installed-panel manual checks remain deferred.
7. Repair plans and audit reports validate against explicit schemas and contain no Blender object references or sensitive data.
8. Sprint 0/1 regression, background tests, package validators, Blender-native validation, security audit, and `git diff --check` pass.
9. At least one sanitized real statue is repaired under operator review with retained evidence and no unapproved detail loss. **Deferred and not counted as passed for the current internal alpha.**
10. Known limitations and excluded operations are reflected consistently in UI, reports, README, and release notes.

### Likely risks

- Blender undo/context behavior may not align cleanly with multi-step plans.
- Merge and cleanup tolerances can remove intentional close detail.
- Normal repair on open or inconsistent shells can produce misleading results.
- Hole boundaries may be mathematically small but artistically significant.
- Dense-mesh copies, comparisons, and retained evidence can increase memory use.
- Operator cancellation can leave an ambiguous partial state unless operations are carefully bounded.

## Sprint 3 — Printability Engine

**Objective:** Add process-aware risk analysis and controlled preparation after safe repair is proven.

### Scope

- Wall-thickness analysis with threshold evidence and bounded samples.
- Overhang analysis relative to current or proposed orientation.
- Build-plate contact and stability indicators.
- Floating-part and disconnected-feature review.
- Previewed, reversible scale tools.
- Versioned printer profiles with explicit FDM/resin distinctions.
- Evidence-scored orientation recommendations and user-approved application.
- Export validation that preserves passes, warnings, skips, failures, and overrides.
- Continued current-orientation build-volume evaluation without claiming manufacturing success.

### Dependencies

Sprint 2's protected workspace, operation preview, approval, undo, audit, and comparison foundations; unit-correct Sprint 1 metrics; approved FDM/resin policy vocabulary; representative printer and geometry fixtures.

### Acceptance gates

- Thickness and overhang results match calibrated fixtures within documented tolerance.
- Contact and floating-feature policies pass positive, negative, boundary, and ambiguous cases.
- Printer-profile versions, upgrades, and FDM/resin distinctions are explicit.
- Scale/orientation application preserves the original and passes undo/comparison evidence.
- Export refuses missing required evaluations unless the user makes an auditable override.
- Real FDM and resin cases compare analysis with slicer review and physical outcomes where practical.
- Performance, memory, cancellation, security, package, regression, and manual UI gates pass.
- All product language continues to state that risk analysis is not a printability guarantee.

## Sprint 4 — Controlled Optimization

**Objective:** Reduce or restructure mesh complexity while measuring and limiting visible and engineering impact.

### Scope

- Previewed decimation with explicit polygon targets.
- Detail and feature-preservation controls for faces, hands, jewelry, inscriptions, and thin forms.
- Detail-preserving reduction with visual/geometric deviation metrics.
- Approved hidden-region simplification.
- Bounded remeshing with feature controls.
- Before/after topology, dimensions, area, volume reliability, issue, and deviation comparison.
- Acceptance, rejection, undo, and rollback of every optimization result.

### Dependencies

Stable Sprint 2 repair workspace and audit model; Sprint 3 printability rechecks; approved deviation metrics; reference renders and feature-region fixtures; performance/memory instrumentation.

### Acceptance gates

- Requested polygon targets and protected-region policies are respected within documented tolerances.
- Deviation evidence is stable, bounded, and correlated with manual visual review.
- Optimization introduces no hidden non-manifold, orientation, scale, or print-prep regression.
- Remeshing and decimation never alter the protected original.
- Representative dense models demonstrate a measurable workflow or performance benefit without unacceptable approved-detail loss.
- Undo, recovery, comparison, package, security, regression, and manual viewport checks pass.

## Sprint 5 — Chroma3D Production UAT

**Objective:** Establish product value and engineering baselines on real, permissioned production models before expanding into platform or AI work.

### Workstreams

- Create a representative, permissioned corpus and a documented sanitization/provenance process.
- Cover model categories such as full statues, busts, faces/hands, dense jewelry, crowns, garlands, thin weapons, halos, pedestals, hollow forms, and multi-shell assemblies.
- Define complexity bands using geometry, shell count, feature density, memory, and observed operation cost—not vertex count alone.
- Maintain a failure taxonomy spanning source defects, diagnostic uncertainty, repair policy, print-prep risk, optimization loss, Blender context, performance, and operator error.
- Record Standard, Deep, repair, printability, optimization, memory, cancellation, and end-to-end performance baselines.
- Collect structured operator feedback on clarity, confidence, false positives, false negatives, time, and recovery.
- Compare diagnosis and repair time with the existing production workflow.
- Where authorized and practical, connect model evidence to slicer review and physical print results.
- Promote only sanitized, rights-cleared cases into durable regression fixtures.

### Exit criteria

- The corpus covers approved categories and complexity bands with provenance and access rules.
- Critical workflows complete on representative models without original corruption or unrecoverable state.
- Baseline manual time and Chroma3D-assisted time are measured using a consistent task definition.
- High-impact false positives, false negatives, and heuristic failures have mitigations or explicit release limitations.
- Performance and memory budgets are approved from evidence; progress and cancellation are usable.
- At least one FDM and one resin-oriented preparation path has documented analysis-to-result evidence where available.
- Operator feedback supports an external-alpha scope, and accepted cases are promoted to regression fixtures.
- Product, engineering, privacy/rights, and domain reviewers approve the UAT report.

## Sprint 6 — Workflow and Asset Foundation

**Objective:** Convert repeated Chroma3D creation work into reusable, governed Blender-native workflows.

### Scope

- Project-aware reference manager and reusable presets.
- Versioned statue asset libraries for crowns, ornaments, lotus forms, halos, garlands, necklaces, weapons, and bases/pedestals.
- Geometry Nodes helpers with explicit parameters and artist-editable outputs.
- Asset metadata for scale, category, attachment, version, provenance, compatibility, author, and license.
- Asset upgrade and legacy-scene policy.
- Packaging and licensing readiness for optional asset packs.

### Gates

Assets pass visual/domain review, metadata and rights validation, Blender compatibility, save/reload and upgrade tests, scale/attachment checks, package validation, and representative workflow UAT. No asset or rule pack is presented as universally correct across cultural or artistic contexts.

## Sprint 7 — AI Recommendation Foundation

**Objective:** Evaluate bounded AI-assisted recommendations without allowing a model to control Blender or define geometry correctness.

### Scope

- A backend decision gate based on privacy, cost, latency, licensing, update, and support requirements.
- Model-provider abstraction and failure/fallback policy.
- Versioned prompt-to-JSON recommendation schema.
- Minimal, bounded, consented scene and diagnostic context extraction.
- Operation allow-list and parameter validators mapped to existing deterministic operators.
- Recommendation reason, assumptions, confidence, unmet prerequisites, and evidence links.
- Preview, explicit confirmation, rejection, cancellation, and audit trail.
- Security tests proving there is no arbitrary Python execution or model-authored system command.
- Evaluation of bring-your-own credentials and a hosted option, without committing before cost/security evidence.

### Gates

The threat model, privacy model, provider contract, structured-output evaluation set, deny-by-default operation tests, prompt-injection tests, consent UI, offline fallback, usage/cost model, and human-review rubric must pass. This sprint does not promise direct high-quality sculpt generation.

## Sprint 8 — Reference-Guided Assistance

**Objective:** Help artists compare references with the current work and receive reviewable suggestions.

### Scope

- Permissioned reference-image management and provenance.
- Optional vision analysis through the approved local/service boundary.
- User-selected regions and scoped scene context.
- Style, face, ornament, and proportion suggestions expressed as evidence-linked recommendations.
- Human approval before any deterministic operation or parameter change.
- Evaluation datasets covering accepted, rejected, ambiguous, and culturally sensitive cases.

### Gates

Reference rights/consent, region isolation, suggestion accuracy rubric, cultural/domain review, privacy/redaction, bias/failure analysis, provider fallback, and artist-override UAT must pass. Suggestions remain advisory and cannot establish artistic or iconographic correctness.

## Sprint 9 — Procedural and Text-Guided Creation

**Objective:** Translate governed intent into editable procedural assets and parameters rather than unconstrained generated geometry.

### Scope

- Parameterized ornament and statue-component generators.
- Text-to-validated-parameter mapping.
- Template assembly from approved, licensed assets.
- Versioned domain rule packs with provenance and scope.
- Artist override, conversion to editable geometry, comparison, and rollback.
- Cultural review and challenge process for iconographic rule packs.

### Gates

Parameter bounds, deterministic generator outputs, asset/version compatibility, licensing/provenance, cultural review, artist override, adversarial text inputs, quality evaluation, performance, recovery, and release security must pass.

## Sprint 10 — Commercialization

**Objective:** Package validated product value into a supportable professional release. Advanced AI is optional and must not block the non-AI MVP.

### Scope

- Polished Windows installer, uninstall, upgrade, and rollback.
- Licensing with recoverable activation and an approved offline grace policy.
- Signed, channel-aware auto-update with user control.
- Crash-reporting policy and implementation only if transparent and opt-in.
- Task-based documentation, onboarding, sample projects, limitations, and troubleshooting.
- External beta program, consent, feedback intake, and issue triage.
- Support workflow, diagnostic bundles, severity targets, and escalation ownership.
- Subscription/perpetual pricing experiments and edition packaging.
- Internal, alpha, beta, release-candidate, and stable release channels.
- Marketplace groundwork limited to governance, rights, quality, compatibility, and pilot design.

### Gates

Clean-machine install/upgrade/uninstall, license offline/recovery cases, signed update/rollback, privacy and security review, release-candidate regression, real-model UAT, documentation usability, support rehearsal, artifact checksums, release notes, approved tag, and rollback runbook must pass before commercial v1.

## Post-v1 Product Lines

Future editions remain conditional on validated demand and operational capacity:

- **Sculpt:** diagnostics, safe repair, and controlled optimization for statue meshes.
- **Print Prep:** FDM/resin risk analysis, profiles, orientation, and export governance.
- **Asset Studio:** procedural and reusable statue assets, presets, and authoring tools.
- **AI Assist:** bounded recommendations and text/reference-guided parameter workflows.
- **Enterprise:** managed deployment, libraries, policies, audit, integrations, and analytics.

The default architecture should not force these into separate products. Edition boundaries must be reevaluated using adoption, workflow, support, security, and pricing evidence.

## Milestone Dependency Map

```text
Sprint 0 Foundation
  → Sprint 1 Production Diagnostics
    → Sprint 1 integration gate (UI smoke + real statue + merge + tag)
      → Sprint 2 Safe Repair
        → Sprint 3 Printability
          → Sprint 4 Optimization
            → Sprint 5 Production UAT
              ├─→ Sprint 6 Workflow/Assets ───────────────┐
              ├─→ Sprint 7 AI Foundation → Sprint 8/9 ───┤
              └─→ Commercial readiness work ──────────────┤
                                                          ↓
                                             Sprint 10 Commercialization
```

Sprints 6 and 7 can begin as separate workstreams after Sprint 5 evidence. Sprint 8 depends on the AI safety boundary and reference governance; Sprint 9 depends on both governed assets and structured-command safety. Non-AI commercialization can proceed in parallel after Sprint 5 and does not depend on Sprints 7–9, but the final commercialization milestone incorporates only features that have passed their own gates.

## Release Stage Definitions

| Stage | Intended users | Stability expectation | Required evidence | Support expectation | Commercial status |
|---|---|---|---|---|---|
| Internal Alpha | Chroma3D operators and engineering | Incomplete but recoverable, with explicit limitations | Automated gates, named real-model smoke runs, safety audit, and internal UAT | Direct engineering support | Not sold |
| External Alpha | Invited technical sculptors/studios | Core journey usable; schema and UX may change with notice | Installer/upgrade, security, manual UI, external task completion, and known-limitations review | Time-bounded pilot support | Free/private evaluation or limited pilot |
| Beta | Broader approved testers | Feature-complete MVP candidate; no known critical data-loss defect | Representative corpus, performance/memory, FDM/resin cases, docs, recovery, regression, and release rehearsal | Documented intake and triage | Pre-release; pricing may be tested transparently |
| Release Candidate | Final commercial-v1 candidate | Frozen scope and compatibility; only release-blocking fixes | Complete release gates, signed artifacts, upgrade/rollback, clean-install, support rehearsal, and approval | Commercial support process ready | Not final sale until approved |
| Commercial v1 | Paying professional users | Supported declared workflows and compatibility matrix | Accepted RC, tag, checksums, release notes, runbooks, licensing, and monitoring/privacy policy | Published support scope and escalation path | Sellable non-AI MVP |
| AI-assisted edition | Approved users with explicit AI consent | Local core remains available; AI failures degrade safely | AI threat/privacy models, evaluation datasets, provider/cost controls, allow-list, audit, and human-approval UAT | AI-specific provider, usage, privacy, and incident support | Conditional add-on or edition after evidence |

## Technical Debt Register

| Debt | Impact | Priority | Proposed milestone |
|---|---|---|---|
| High-density analysis performance | Routine work can take tens of seconds and scale unpredictably by topology | High | Profile in Sprints 2–5; approve budgets in Sprint 5 |
| Blender 4.5 LTS and broader version testing | Commercial support matrix is unproven | High | Begin Sprint 2 compatibility run; finalize before external alpha |
| Modifier-output analysis | Results may differ from visible evaluated geometry | Medium | Product/architecture decision in Sprint 3; implement only with explicit identity/evidence semantics |
| UI scalability for many findings/shells/plans | Dense cases can become hard to review | High | Sprints 2–3 UI architecture and manual UAT |
| Long-running progress reporting | Users may interpret a synchronous operation as frozen | High | Sprint 2 foundation, extended through Sprint 4 |
| Cancellation boundaries | Unsafe interruption can leave ambiguous state | High | Sprint 2 operation contract |
| Memory instrumentation | Current evidence proves completion, not peak memory | High | Sprint 2 tooling; baselines in Sprint 5 |
| Real statue fixture coverage | Procedural fixtures may miss production failure modes | High | Immediate prerequisite and Sprint 5 corpus |
| JSON compatibility policy | Future reports/repairs/assets could break consumers | High | Define in Sprint 2 before repair schema |
| Test and acceptance runtime | Broader gates may slow iteration and discourage full runs | Medium | Tier suites in Sprints 2–5 without weakening release gates |
| Service modularity under repair/print/optimization growth | Coordinator or models could become tightly coupled | Medium | Enforce boundaries each sprint; architecture review in Sprint 4 |
| Cross-platform testing | macOS/Linux behavior is unknown | Low for Windows MVP; Medium post-v1 | Demand review in Sprint 5; pilot before any support claim |

## Architecture Evolution

### Current

A single local Blender extension with a synchronous dependency flow from UI to operators to coordinator to focused analysis services and typed immutable models. Runtime uses Blender APIs and Python's standard library, performs no network activity, and analyzes the original mesh datablock without modifiers.

### Near-term

A modular deterministic geometry engine inside the extension, with distinct diagnostic, repair, printability, optimization, comparison, audit, UI, and tooling boundaries. Long-running work gains progress, cancellation, recovery, and performance/memory evidence without weakening Blender undo or the local/offline model.

### Mid-term

The local extension remains authoritative for scene inspection and deterministic operations. An optional service boundary may handle justified AI inference, licensing, asset delivery, or collaboration. It receives minimal consented data through versioned contracts and fails without blocking local workflows.

### Long-term

A hybrid ecosystem may add governed asset delivery, account/licensing services, AI routing, marketplace operations, team policy, and production analytics. Services must remain separable, least-privileged, observable, and replaceable. A backend should not be introduced merely to anticipate scale.

## Build-versus-Buy Decisions

### Build and own

- Statue-domain workflows, policies, and Blender UX.
- Diagnostic, repair, printability, comparison, and evidence orchestration.
- Deterministic operation allow-list and safety boundaries.
- Chroma3D asset libraries, metadata, rule packs, and validation.
- Printer-aware preparation logic and production fixtures.

### Integrate behind replaceable boundaries

- LLM and vision model APIs after provider/security evaluation.
- Image-to-3D systems as optional source tools, never as correctness authorities.
- Payment, tax, and subscription infrastructure.
- Cloud object storage and delivery services.
- Crash analytics only under an approved opt-in privacy policy.

Each decision must be reevaluated against differentiation, total cost, privacy, availability, lock-in, maintenance, licensing, and support capacity. Integrations must not erode the local deterministic core.

## Roadmap Risks

| Risk | Roadmap response |
|---|---|
| Scope explosion | Enforce sprint exclusions, acceptance gates, and a complete bounded journey before adjacent features. |
| Premature AI | Require Sprint 5 evidence, Sprint 7 decision gates, structured commands, and deterministic execution. |
| Dense-mesh performance | Instrument time/memory, use centralized limits, design progress/cancel, and baseline real complexity bands. |
| Geometry correctness | Protect originals, use focused deterministic operations, compare before/after, and retain audit evidence. |
| Blender support matrix | Declare tested versions, run compatibility gates, and avoid unsupported claims. |
| Cloud and provider cost | Keep AI optional, model usage, enforce limits, and retain provider abstraction/offline fallback. |
| Dataset and customer rights | Require consent, provenance, sanitization, access controls, and deletion/retention policy. |
| Asset IP and cultural accuracy | Govern authorship, licensing, review, versioning, takedown, and artist override. |
| User trust | Make uncertainty, skips, failures, data movement, changes, recovery, and limits visible. |
| Commercial support capacity | Stage external access, measure support load, document workflows, and narrow the first supported scope. |

## Immediate Next Milestone

Sprint 2 implementation is complete. Before committing or beginning Sprint 3:

- Review the Sprint 2 machine and Markdown evidence.
- Perform an installed-package interactive Blender panel smoke test.
- Repair at least one permissioned real Chroma3D statue under operator review and retain evidence.
- Validate Blender 4.5 LTS when that runtime is available.
- Decide whether mid-operation cancellation or restart-persistent sessions are required before external alpha.

Sprint 3 remains unstarted until the Sprint 2 review checkpoint is approved.
