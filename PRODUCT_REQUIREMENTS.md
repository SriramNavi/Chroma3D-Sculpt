# Chroma3D Sculpt — Product Requirements

| Metadata | Value |
|---|---|
| Document status | Living product specification; planning baseline for review |
| Current product version | `0.3.0-alpha.1` |
| Current completed sprint | Sprint 2 — Safe Mesh Repair; automated acceptance complete |
| Next planned sprint | Sprint 3 — Printability Engine; not started |
| Primary platform | Windows 11, local Blender extension |
| Primary validated Blender version | Blender 4.4.3; minimum supported version 4.4.0 |
| Owner | Chroma3D Product and Engineering |
| Last updated | 2026-07-18 |
| Document purpose | Define product behavior, value, evidence, safety, and release expectations without implementing future sprints |

## Product Summary

Chroma3D Sculpt is a Blender-native engineering and creation workflow for high-detail statue meshes. The current internal alpha provides local read-only diagnostics plus controlled repair on an independent workspace copy. Standard and Deep profiles report topology, shells, world-space physical metrics, orientation, bounded issue evidence, build-volume fit, and candidate-based spatial findings. Sprint 2 can apply explicitly selected bounded repairs without replacing the source; it does not guarantee printability.

Sprint 0 and Sprint 1 are accepted and tagged. Sprint 2 automated background, regression, stress, package, and security evidence is implemented on `feature/sprint-2-safe-mesh-repair`; interactive installed-panel and real Chroma3D statue repair UAT remain deferred. Sprint 3 has not started.

## User Personas

### 1. Chroma3D internal operator

- **Goals:** prepare statue meshes consistently, catch failures early, preserve source quality, and reduce repeated cleanup time.
- **Current workflow:** import or receive a model, inspect it manually in Blender and other tools, make judgment-based corrections, slice, and test print.
- **Pain points:** disconnected checks, ambiguous shell intent, late failures, destructive edits, and process knowledge that is difficult to transfer.
- **Technical skill level:** intermediate Blender operator with production-specific knowledge.
- **Success criteria:** completes a repeatable diagnose-to-export workflow with evidence, recovery, and less manual effort than the baseline process.

### 2. Professional digital sculptor

- **Goals:** retain artistic detail while delivering a technically usable mesh.
- **Current workflow:** sculpt and inspect visually, apply manual cleanup, and rely on a printer specialist or trial prints for manufacturing feedback.
- **Pain points:** fingers, faces, jewelry, crowns, thin details, normals, scale, and remeshing can fail or lose detail.
- **Technical skill level:** advanced artistic skill; variable topology and print-engineering skill.
- **Success criteria:** understands actionable defects, approves only necessary repairs, and compares quality before accepting changes.

### 3. 3D-printing studio owner

- **Goals:** turn varied customer files into reliable FDM or resin jobs with predictable labor and fewer reprints.
- **Current workflow:** triage files, move among repair and slicing tools, estimate risk, communicate issues, and manually document decisions.
- **Pain points:** unknown source quality, printer/profile differences, thin or floating features, schedule pressure, and costly failed prints.
- **Technical skill level:** intermediate to advanced manufacturing knowledge; may delegate Blender work.
- **Success criteria:** staff can follow governed preparation gates, produce reports, and reduce preventable failures without overpromising results.

### 4. Technical mesh-preparation specialist

- **Goals:** diagnose dense organic meshes accurately and apply controlled corrections at scale.
- **Current workflow:** use Blender inspection tools, scripts, slicer checks, and manual before/after review.
- **Pain points:** high-density performance, heuristic false positives, evidence overload, stale selections, and difficult rollback.
- **Technical skill level:** advanced Blender, topology, and scripting knowledge.
- **Success criteria:** obtains bounded reproducible evidence, sees explicit skipped/failed states, and can audit each approved operation.

### 5. Future asset creator or marketplace seller

- **Goals:** create reusable statue assets or procedural presets and distribute them with clear compatibility and rights.
- **Current workflow:** build assets ad hoc, package files manually, and support buyers without shared metadata or validation.
- **Pain points:** inconsistent scale and attachment conventions, unclear licensing, weak provenance, and variable quality.
- **Technical skill level:** intermediate to advanced Blender and asset-authoring skill.
- **Success criteria:** publishes versioned, validated, licensed assets that integrate predictably and remain artist-editable.

## Core User Journeys

### Journey A — Diagnose an imported statue (implemented)

Import or select mesh → choose Standard or Deep profile → optionally choose a build-volume profile → analyze → review explicit check states and bounded evidence → select an issue for inspection → export the versioned JSON report.

The analysis reads the original mesh datablock. Issue selection may change mode and selection only after topology-signature validation; it does not modify geometry.

### Journey B — Safely repair a model (internal alpha)

Diagnose → duplicate and protect the original → create a repair workspace → preview a controlled repair plan → approve selected operations → execute deterministic operators → compare before/after analysis and signatures → undo, reject, or accept → export a repair audit record.

### Journey C — Prepare for printing (partially implemented, future completion)

Validate scene scale → choose an FDM or resin printer profile → check world-space dimensions and build-volume fit → analyze wall thickness, overhangs, contact, and floating features → preview orientation or scale recommendations → approve changes → pass an export gate with limitations recorded.

Current support is limited to dimensions and current-orientation rectangular build-volume checks for Bambu Lab X1 Carbon or a custom volume.

### Journey D — Receive an AI-assisted recommendation (future)

Analyze → extract bounded scene context → request a structured recommendation → validate it against a schema and operation allow-list → show the proposed deterministic command and expected impact → obtain user approval → execute the existing deterministic operator → record the result.

AI output never executes arbitrary Python and never bypasses preview, validation, or confirmation.

## Functional Requirements

Status values are **Implemented**, **Partial**, **Planned**, and **Deferred**. Future acceptance evidence describes the evidence required before the status can change.

### Diagnostics

| ID | Requirement | User value | Status | Target milestone | Acceptance evidence |
|---|---|---|---|---|---|
| FR-DIAG-001 | Install and register as a modern Blender extension on the declared platform and minimum Blender version. | Predictable local setup and lifecycle. | Implemented | Sprint 0 | [Sprint 0 acceptance](manual-tests/ACCEPTANCE_RESULTS.md) and package validation |
| FR-DIAG-002 | Provide Standard and Deep profiles with immutable settings snapshots, centralized limits, timings, and explicit `COMPLETED`, `SKIPPED`, `FAILED`, or `NOT_APPLICABLE` states. | Honest, repeatable evaluations. | Implemented | Sprint 1 | [Sprint 1 acceptance](manual-tests/sprint1/SPRINT1_ACCEPTANCE_RESULTS.md), gates S1-01 and S1-11 |
| FR-DIAG-003 | Classify loose, boundary, two-face manifold, and high-incidence edges, plus zero-length edges and degenerate faces. | Finds foundational topology defects. | Implemented | Sprints 0–1 | Sprint 0 gates and Sprint 1 topology matrix |
| FR-DIAG-004 | Detect vertex face-fan manifold anomalies without relying on edge counts alone. | Finds bow-tie and related vertex defects. | Implemented | Sprint 1 | Sprint 1 background tests and final topology matrix |
| FR-DIAG-005 | Report object and per-shell topological watertightness using explicit, non-manufacturing wording. | Prevents “closed-looking” meshes from being mistaken for proven printable assets. | Implemented | Sprint 1 | Sprint 1 gate S1-02 and final validation |
| FR-DIAG-006 | Decompose face-connected shells with stable identifiers. | Makes disconnected structures reviewable. | Implemented | Sprint 1 | Sprint 1 gates S1-02 and S1-05 |
| FR-DIAG-007 | Report world-space dimensions and surface area, and volume only when closed and orientation-consistent. | Provides unit-correct production measurements without false volume results. | Implemented | Sprint 1 | Sprint 1 gates S1-03 and S1-04; numerical final validation |
| FR-DIAG-008 | Report shared-edge orientation consistency and closed-shell outward, inward, open, or indeterminate states. | Exposes winding problems before later operations. | Implemented | Sprint 1 | Sprint 1 gate S1-04 |
| FR-DIAG-009 | Classify a deterministic main shell, combined-criteria tiny-shell candidates, and neutral disconnected external shells. | Prioritizes review without declaring uncertain geometry defective. | Implemented | Sprint 1 | Sprint 1 gate S1-05 |
| FR-DIAG-010 | In Deep profile, report possibly internal shells using bounded containment heuristics and confidence evidence. | Surfaces likely hidden structures while preserving uncertainty. | Implemented | Sprint 1 | Sprint 1 gates S1-06 and S1-11 |
| FR-DIAG-011 | In Deep profile, report bounded self-intersection candidate face pairs after shared-topology filtering. | Directs inspection without claiming exact intersection proof. | Implemented | Sprint 1 | Sprint 1 gates S1-07 and S1-11 |
| FR-DIAG-012 | Evaluate current-orientation rectangular fit for Bambu Lab X1 Carbon and user-defined build volumes. | Catches obvious size mismatch early. | Implemented | Sprint 1 | Sprint 1 gate S1-08 |
| FR-DIAG-013 | Store bounded issue counts and samples with total, cap, and truncation information. | Keeps dense reports usable without hiding total scope. | Implemented | Sprint 1 | Sprint 1 gates S1-09 and S1-12 |
| FR-DIAG-014 | Reject issue selection when the topology signature no longer matches; valid selection may change only mode and selection. | Prevents stale evidence from targeting the wrong elements. | Implemented | Sprint 1 | Sprint 1 gate S1-09 and final issue-selection evidence |
| FR-DIAG-015 | Export deterministic UTF-8 JSON with analysis ID, schema version, settings, checks, evidence, timings, warnings, and limitations. | Enables audit, comparison, and downstream tooling. | Implemented | Sprints 0–1 | Sprint 1 gate S1-12 and schema 2.0 audit |
| FR-DIAG-016 | Analyze the original mesh datablock without evaluating modifiers or changing geometry, transforms, names, materials, or files. | Preserves source assets and makes scope explicit. | Implemented | Sprints 0–1 | Immutability evidence in all acceptance reports |

### Safe Repair

| ID | Requirement | User value | Status | Target milestone | Acceptance evidence |
|---|---|---|---|---|---|
| FR-REPAIR-001 | Create a protected backup and separate repair workspace copy before any geometry-changing action. | Preserves the original and provides recovery. | Implemented | Sprint 2 | S2-02/S2-09; live session is not restart-persistent |
| FR-REPAIR-002 | Generate a controlled repair plan from completed diagnostic evidence and record unavailable prerequisites. | Shows scope and risk before action. | Implemented | Sprint 2 | S2-03 and plan serialization tests |
| FR-REPAIR-003 | Offer tolerance-bounded merge-by-distance with previewed counts and explicit approval. | Removes intended duplicates without silent over-merging. | Implemented | Sprint 2 | S2-04 and spatial-cell/non-uniform-scale tests |
| FR-REPAIR-004 | Remove approved loose vertices, edges, and geometry without affecting unrelated shells. | Clears non-contributing elements safely. | Implemented | Sprint 2 | S2-05 mixed fixtures |
| FR-REPAIR-005 | Detect and remove zero-length edges and degenerate faces through deterministic operations. | Resolves common invalid geometry. | Implemented | Sprint 2 | Focused Blender fixtures and S2-05 |
| FR-REPAIR-006 | Repair normals only when preconditions are met and expose the intended orientation result. | Corrects winding without hidden global changes. | Implemented | Sprint 2 | S2-06 open/closed/inward fixtures |
| FR-REPAIR-007 | Fill only policy-approved small holes within explicit size and topology limits. | Addresses routine gaps while avoiding invented large surfaces. | Implemented | Sprint 2 | S2-08 bounded/rejected/undo fixtures |
| FR-REPAIR-008 | Present tiny-shell candidates for individual review and removal; never auto-delete solely from a heuristic label. | Removes debris while protecting intentional ornamentation. | Implemented | Sprint 2 | S2-07 candidate/main-shell/undo fixtures |
| FR-REPAIR-009 | Re-run diagnostics and show before/after metrics, issue deltas, signatures, and new warnings. | Makes repair quality measurable. | Implemented | Sprint 2 | S2-10 comparison evidence |
| FR-REPAIR-010 | Support Blender undo plus explicit cancellation between safe operation boundaries. | Gives the operator a practical escape path. | Partial | Sprint 2 | Extension checkpoints, undo-last, restore, and failure rollback implemented; mid-operation cancellation and installed UI test deferred |
| FR-REPAIR-011 | Export a repair audit log containing plan, approvals, parameters, operations, outcomes, and analysis references. | Enables traceability and support. | Implemented | Sprint 2 | S2-12 repair audit schema 1.0 |

### Printability

| ID | Requirement | User value | Status | Target milestone | Acceptance evidence |
|---|---|---|---|---|---|
| FR-PRINT-001 | Report world-space scale and dimensions with explicit scene-unit context. | Establishes manufacturing size. | Implemented | Sprint 1 | Sprint 1 physical-metric evidence |
| FR-PRINT-002 | Maintain a versioned printer profile system that distinguishes FDM and resin constraints. | Makes checks relevant to the selected process. | Partial | Sprint 3 | Current X1 Carbon/custom build volumes; profile-schema and printer-fixture tests required |
| FR-PRINT-003 | Analyze wall thickness with threshold evidence and bounded samples. | Finds fragile or unmanufacturable regions earlier. | Planned | Sprint 3 | Calibrated thickness fixtures and slicer/measurement comparisons |
| FR-PRINT-004 | Analyze overhangs relative to approved orientation and process settings. | Identifies support-sensitive regions. | Planned | Sprint 3 | Known-angle fixtures and FDM/resin policy tests |
| FR-PRINT-005 | Evaluate build-plate contact and stability indicators. | Reduces poorly grounded exports. | Planned | Sprint 3 | Contact fixtures and operator-reviewed cases |
| FR-PRINT-006 | Detect disconnected floating parts or features relevant to manufacture. | Prevents unnoticed unprintable components. | Planned | Sprint 3 | Multi-component fixtures and real-model review |
| FR-PRINT-007 | Provide controlled scale tools with preview and original protection. | Fits target output without hidden transform changes. | Planned | Sprint 3 | Transform, unit, undo, and before/after tests |
| FR-PRINT-008 | Produce orientation recommendations with scored evidence; apply only after user approval. | Improves preparation while preserving artist control. | Planned | Sprint 3 | Reference fixtures, printer-specific review, and rollback tests |
| FR-PRINT-009 | Gate export on required completed checks and preserve warnings, skips, failures, and overrides in evidence. | Prevents silent omission of risk. | Planned | Sprint 3 | Export-state matrix and override audit tests |
| FR-PRINT-010 | State that analysis reduces risk but does not guarantee printability or manufacturing success. | Maintains user trust and accurate expectations. | Implemented | All milestones | README and report wording; release-content review |

### Optimization

| ID | Requirement | User value | Status | Target milestone | Acceptance evidence |
|---|---|---|---|---|---|
| FR-OPT-001 | Preview controlled decimation against a polygon target. | Reduces computational and file cost predictably. | Planned | Sprint 4 | Target-count fixtures and rollback tests |
| FR-OPT-002 | Preserve user-selected detail regions and critical features during reduction. | Protects faces, fingers, jewelry, inscriptions, and edges. | Planned | Sprint 4 | Region masks and feature-fixture comparisons |
| FR-OPT-003 | Support detail-preserving reduction with measurable visual or geometric deviation. | Makes quality tradeoffs inspectable. | Planned | Sprint 4 | Deviation metrics and approved reference renders |
| FR-OPT-004 | Simplify approved hidden regions separately from visible surfaces. | Saves polygons where visual risk is low. | Planned | Sprint 4 | Visibility-policy fixtures and manual review |
| FR-OPT-005 | Provide bounded remeshing with preview, feature controls, and rollback. | Resolves unsuitable topology without uncontrolled loss. | Planned | Sprint 4 | Topology/quality comparison, stress, and undo tests |
| FR-OPT-006 | Compare topology, physical metrics, issue counts, and deviation before acceptance. | Prevents optimization from becoming an unmeasured destructive step. | Planned | Sprint 4 | Versioned comparison report and regression gates |

### Asset and Creation Workflows

| ID | Requirement | User value | Status | Target milestone | Acceptance evidence |
|---|---|---|---|---|---|
| FR-ASSET-001 | Manage reference images and production presets inside a project-aware workflow. | Reduces setup repetition and context loss. | Planned | Sprint 6 | Save/reload, relink, and portability tests |
| FR-ASSET-002 | Provide reusable, editable crowns, necklaces, lotus bases, halos, garlands, ornaments, weapons, and pedestals. | Accelerates domain-specific creation without hiding authorship. | Planned | Sprint 6 | Asset checklist, quality review, metadata, and licensing evidence |
| FR-ASSET-003 | Integrate selected generators and modifiers through governed Geometry Nodes helpers. | Keeps procedural assets native and artist-editable. | Planned | Sprint 6 | Blender compatibility and parameter-boundary tests |
| FR-ASSET-004 | Store asset scale, attachment, category, version, provenance, compatibility, and license metadata. | Makes reuse and distribution reliable. | Planned | Sprint 6 | Metadata-schema validation and package audit |
| FR-ASSET-005 | Support versioned presets without silently changing existing scenes. | Protects production reproducibility. | Planned | Sprint 6 | Upgrade and legacy-scene tests |
| FR-ASSET-006 | Allow artist overrides and conversion to editable geometry through explicit actions. | Preserves creative control and long-term scene access. | Planned | Sprint 6 | Override, undo, and round-trip tests |

### AI Assistance

| ID | Requirement | User value | Status | Target milestone | Acceptance evidence |
|---|---|---|---|---|---|
| FR-AI-001 | Convert natural-language intent into a versioned structured-command schema, not executable code. | Makes recommendations machine-checkable. | Planned | Sprint 7 | Schema validation, malformed-output, and injection tests |
| FR-AI-002 | Extract only bounded, consented scene and diagnostic context required for a request. | Improves relevance while limiting data exposure. | Planned | Sprint 7 | Context allow-list and privacy tests |
| FR-AI-003 | Generate recommendations with reasons, assumptions, confidence, and unmet prerequisites. | Lets users judge uncertainty. | Planned | Sprint 7 | Evaluation set and human review rubric |
| FR-AI-004 | Permit only allow-listed deterministic operations with validated parameters. | Prevents uncontrolled scene or system actions. | Planned | Sprint 7 | Deny-by-default security suite |
| FR-AI-005 | Show a preview and require confirmation before execution. | Keeps the artist in control. | Planned | Sprint 7 | UI state, rejection, and cancellation tests |
| FR-AI-006 | Record prompts, structured responses, approvals, operations, and outcomes according to privacy policy. | Supports audit and troubleshooting. | Planned | Sprint 7 | Audit-schema and redaction tests |
| FR-AI-007 | Abstract model providers behind a stable internal interface. | Avoids product lock-in and keeps policy consistent. | Planned | Sprint 7 | Provider contract and failure-mode tests |
| FR-AI-008 | Evaluate bring-your-own API credentials and a hosted option without committing to either prematurely. | Supports different privacy and commercial needs. | Deferred | Sprint 7 decision gate | Security, cost, support, and consent review |
| FR-AI-009 | Account for hosted usage and enforce limits before a paid service is offered. | Controls cost and communicates consumption. | Deferred | Commercial evaluation | Usage-integrity, billing-boundary, and support tests |
| FR-AI-010 | Never execute arbitrary Python, downloaded code, or a model-authored command outside the allow-list. | Establishes the core AI security boundary. | Planned | Sprint 7 and all AI releases | Static audit, adversarial tests, and release security gate |

### Commercial Platform

| ID | Requirement | User value | Status | Target milestone | Acceptance evidence |
|---|---|---|---|---|---|
| FR-COM-001 | Provide a polished Windows installer and uninstall/upgrade path. | Reduces setup and support friction. | Planned | Sprint 10 | Clean-machine install, upgrade, rollback, and uninstall tests |
| FR-COM-002 | Implement licensing with a documented offline grace policy and recoverable activation. | Enables sales without blocking legitimate offline production unexpectedly. | Planned | Sprint 10 | Offline, clock, device, recovery, and support scenarios |
| FR-COM-003 | Support signed, channel-aware updates with explicit user control. | Delivers fixes safely. | Planned | Sprint 10 | Signature, rollback, staged-channel, and failure tests |
| FR-COM-004 | Recover safely from Blender, extension, or operation interruption. | Protects work and user trust. | Planned | Sprints 2–10 | Crash/restart fixtures and audit recovery checks |
| FR-COM-005 | Provide task-based documentation, onboarding, limitations, and troubleshooting. | Enables self-service adoption. | Planned | External alpha onward | Documentation review and first-run usability tests |
| FR-COM-006 | Keep telemetry absent by default; introduce it only as transparent opt-in collection. | Preserves privacy and offline expectations. | Planned | Sprint 10 | Consent, data inventory, disable, retention, and no-network tests |
| FR-COM-007 | Evaluate subscription and perpetual-license editions using pricing experiments and support economics. | Finds a sustainable, understandable model. | Deferred | Sprint 10 | Approved commercial decision record |
| FR-COM-008 | Package governed asset packs with provenance, compatibility, and licenses. | Creates optional domain value beyond the core extension. | Planned | Sprints 6 and 10 | Asset package validator and rights review |
| FR-COM-009 | Introduce a marketplace only after seller, quality, rights, moderation, and update policies exist. | Protects buyers, creators, and the brand. | Deferred | Post-v1 | Marketplace governance and pilot evidence |
| FR-COM-010 | Provide enterprise deployment, policy, library, and audit controls only after validated demand. | Supports teams without burdening the early product. | Deferred | Post-v1 | Design-partner requirements and security review |
| FR-COM-011 | Maintain release channels, release notes, support intake, and rollback plans. | Makes commercial operations dependable. | Planned | Sprint 10 | Release rehearsal and support runbook review |
| FR-COM-012 | Separate optional cloud services from the deterministic local core. | Keeps basic work available offline and limits service risk. | Planned | All commercial architecture | Offline acceptance and service-failure tests |

## Non-Functional Requirements

Performance expectations below are planning targets unless backed by named evidence. Mesh size alone does not predict topology cost, so Sprint 5 must establish final complexity bands from real models.

| ID | Area | Requirement | Status or evidence |
|---|---|---|---|
| NFR-PERF-001 | Performance | Centralize caps and record per-check and total monotonic timings; skips must state actual size and configured limit. | Implemented in Sprint 1 |
| NFR-PERF-002 | Small meshes | Standard analysis should feel interactive; target budgets will be set from representative fixtures. Deep should complete only when within declared spatial limits. | Baseline required in Sprint 5; no current guarantee |
| NFR-PERF-003 | Medium meshes | Standard analysis may take several seconds and must not hide a long-running state. Deep can be materially slower and may skip bounded checks honestly. | Progress/cancellation required by Sprints 2–3 |
| NFR-PERF-004 | High-density statue meshes | Plan for tens-of-seconds work, bounded memory, progress, and cancellation. Across Windows and Blender 4.4.3 validation runs, Standard analysis of the current approximately 147,000-vertex synthetic fixture has ranged from about 12 to 29 seconds against the repository's 20-second performance warning threshold. Performance remains active technical debt; this synthetic range is not a hard guarantee for production models, and real Chroma3D statue benchmarking is still required. | Sprint 1 acceptance and final-validation evidence; real-model baseline required in Sprint 5 |
| NFR-PERF-005 | Standard versus Deep | Standard remains the routine deterministic path. Deep adds BVH and containment work and may return explicit limit skips; it must never silently downgrade or serialize a skip as zero findings. | Implemented policy; broaden evidence in Sprint 5 |
| NFR-REL-001 | Reliability | A failed or skipped check must remain distinct from a successful zero finding in UI, reports, comparisons, and gates. | Implemented for diagnostics; required everywhere |
| NFR-REL-002 | Reliability | Geometry-changing workflows must be transactional at safe boundaries, preserve the original, and provide recovery evidence. | Implemented and validated in Sprint 2 |
| NFR-SEC-001 | Security | Use Blender APIs and the Python standard library for the local core; prohibit hidden network activity, downloaded code, `eval`, `exec`, and generated-code execution. | Current static audit passed; permanent gate |
| NFR-PRIV-001 | Privacy | Keep local assets local by default. Any upload requires purpose-specific consent, a clear data inventory, retention policy, and redaction controls. | Required before any service integration |
| NFR-COMP-001 | Compatibility | Support Blender 4.4.0 minimum; validate against Blender 4.4.3 on Windows today and establish a commercial Blender LTS/version policy before external beta. | 4.4.3 validated; 4.5 LTS not yet tested |
| NFR-TEST-001 | Testability | Provide procedural fixtures, deterministic expected results, preserved Sprint 0 regressions, real-model tests, and separable service tests. | 48 background tests plus acceptance runners exist |
| NFR-MAINT-001 | Maintainability | Preserve dependency direction from UI to operators to coordinator to focused services and typed models; avoid circular imports and hidden registration. | Current architecture documented and validated |
| NFR-ACC-001 | Accessibility | UI controls must have descriptive labels, logical grouping, keyboard reachability where Blender supports it, readable states, and no color-only meaning. | Manual UI gate required for each external release |
| NFR-I18N-001 | Internationalization | Keep user-facing text separable from logic, use UTF-8, avoid text embedded in evidence keys, and design layouts for longer translations. | Readiness required by beta; localization deferred |
| NFR-OFF-001 | Offline operation | Diagnostics, safe repair, print-prep core, optimization, and local assets must work without network access. | Diagnostics and Sprint 2 repair validated offline |
| NFR-DET-001 | Determinism | Given the same supported Blender version, mesh, transforms, settings, and operation version, diagnostic and deterministic-operation outputs must be stable within documented numeric tolerances. | Diagnostics and repair fixtures validated |
| NFR-LOG-001 | Logging | Store bounded operational evidence with IDs and actionable failures; avoid per-element logs and sensitive content. | Analysis reports and repair audit schema 1.0 implemented |
| NFR-REC-001 | Recovery | Preserve originals, support undo/cancel, persist recoverable plans where appropriate, and explain partial completion after interruption. | Checkpoint undo/restore/failure rollback implemented; restart persistence deferred |
| NFR-PKG-001 | Packaging | Reject nested roots, tests, secrets, bytecode, traversal paths, generated evidence, and undeclared dependencies from release packages. | Sprint 0/1 package validators passed |
| NFR-UPG-001 | Upgrade safety | Version schemas, assets, settings, and repair policies; preserve old scenes or provide explicit migration and rollback. | Policy required before external alpha |

## Data and Evidence Requirements

| ID | Requirement |
|---|---|
| DER-001 | Every analysis has a unique analysis ID, timestamp, product/schema version, Blender/platform context, object identity, and topology signature. |
| DER-002 | Every result stores an immutable settings snapshot including profile, tolerances, evidence caps, printer selection, and bounded-check limits. |
| DER-003 | Geometry-changing work records original, workspace, pre-operation, and post-operation signatures plus an explicit relationship between them. |
| DER-004 | JSON analysis and repair schemas use explicit semantic compatibility rules, deterministic serialization, UTF-8, and versioned upgrade tests. |
| DER-005 | Issue evidence stores total count, domain, cap, bounded sample, and truncation; complete internal sets may be used only where required for correctness and within limits. |
| DER-006 | Repair audit records reference source analyses, plans, user approvals, operation versions, parameters, outcomes, cancellations, warnings, and before/after analyses. |
| DER-007 | Test evidence distinguishes procedural fixtures, sanitized real models, manual UI evidence, performance runs, and physical print results. |
| DER-008 | Real-model fixtures require owner permission, anonymization or sanitization where needed, documented provenance, and access controls. |
| DER-009 | No sensitive customer asset, image, prompt, report, or scene data is uploaded without explicit purpose-specific consent. |
| DER-010 | Evidence retention, deletion, export, and redaction rules must be defined before cloud, telemetry, marketplace, or enterprise services launch. |

## Safety Requirements

| ID | Requirement |
|---|---|
| SR-001 | Never modify the original asset by default; create a named, traceable repair workspace. |
| SR-002 | Create and verify an automatic backup before the first destructive action in a plan. |
| SR-003 | Require confirmation for every operation or explicitly approved batch whose geometry impact has been previewed. |
| SR-004 | Revalidate topology and relevant state before selection, repair, comparison, or command execution. |
| SR-005 | Deny operations and parameters not present in a versioned allow-list. |
| SR-006 | Do not execute arbitrary Python, generated code, shell commands, or downloaded binaries. |
| SR-007 | Perform no hidden network activity; disclose destination, data, purpose, cost, and retention before an optional service call. |
| SR-008 | Label candidates, heuristics, confidence, limits, skips, failures, and indeterminate outcomes clearly. |
| SR-009 | Never present diagnostics, repair, or export gates as a printability or manufacturing guarantee. |
| SR-010 | Provide a tested recovery path through original preservation, backup, undo, audit evidence, and restart handling. |
| SR-011 | Support cancellation at safe boundaries where practical and describe when an operation cannot be interrupted safely. |
| SR-012 | Never auto-remove a shell, fill a large hole, remesh, or apply an AI recommendation without review and approval. |

## Current Product Status Matrix

| Capability | Status | Version | Validation | Known limitation |
|---|---|---|---|---|
| Modern extension registration, panel, session state, and JSON export | Implemented | 0.1.0–0.3.0-alpha.1 | Sprint 0–2 acceptance | Windows/Blender 4.4.3 is the primary validated runtime |
| Read-only original-mesh analysis | Implemented | 0.1.0-alpha.1 | Immutability and stability gates | Modifier output is not analyzed |
| Standard/Deep profiles and explicit evaluation states | Implemented | 0.2.0-alpha.1 | Sprint 1 S1-01/S1-11 | Deep checks are bounded and may skip |
| Edge and vertex manifold diagnostics | Implemented | 0.2.0-alpha.1 | 48-test suite and topology matrices | Evidence samples are capped by design |
| Topologically watertight state and shell decomposition | Implemented | 0.2.0-alpha.1 | S1-02 and final validation | Not a printability result |
| Main, tiny-candidate, disconnected-external, and possibly-internal shell classifications | Implemented | 0.2.0-alpha.1 | S1-05/S1-06 | Tiny/internal results require review; internal is heuristic |
| World-space dimensions, area, reliable volume, and orientation | Implemented | 0.2.0-alpha.1 | S1-03/S1-04 and numerical validation | Volume is unavailable when reliability preconditions fail |
| Self-intersection candidates | Implemented | 0.2.0-alpha.1 | S1-07/S1-11 | Candidate-based, bounded, not exact proof |
| Bambu X1 Carbon/custom rectangular build-volume fit | Implemented | 0.2.0-alpha.1 | S1-08 | Current orientation only; no support/purge clearance |
| Bounded evidence, stale protection, and issue selection | Implemented | 0.2.0-alpha.1 | S1-09 and final validation | Selection changes mode/selection but not geometry |
| Schema 2.0 reports and performance timings | Implemented | 0.2.0-alpha.1 | S1-10/S1-12 | Current schema compatibility policy needs formalization |
| Safe mesh repair | Implemented | 0.3.0-alpha.1 | 56 focused tests and S2-02 through S2-14 | Workspace copies require human review; session restart persistence and real-statue UAT deferred |
| Printability engine | Planned | Sprint 3 target | No implementation evidence | No thickness, overhang, contact, support, or orientation analysis |
| Controlled optimization | Planned | Sprint 4 target | No implementation evidence | No decimation or remeshing |
| Asset workflows, AI assistance, and commercial platform | Planned/Deferred | Sprints 6–10/post-v1 | No implementation evidence | No asset library, AI, cloud, licensing, billing, or marketplace |

## MVP Definition

The first sellable MVP is a professional Windows Blender product for a bounded statue-preparation journey. It should include validated diagnostics, protected safe repair, scale and build-volume tools, basic wall-thickness/overhang/contact checks, controlled export with evidence, polished installation and documentation, real-model UAT, recovery, and basic licensing. Advanced AI, a marketplace, cloud collaboration, and autonomous sculpt generation are not MVP requirements.

| Stage | Definition | Minimum evidence |
|---|---|---|
| Internal Alpha | Current diagnostics plus progressively approved internal repair/print-prep slices used by Chroma3D operators. | Automated regression, real-model smoke evidence, explicit limitations, and recoverability |
| External Alpha | Installer-supported build for invited technical users with bounded diagnostics, repair, and print-prep journeys. | Clean install/upgrade, manual UI, security, support intake, and consented external task evidence |
| Beta | Feature-complete MVP candidate with stable schemas/workflows and representative FDM/resin testing. | Real-model corpus, performance baselines, documentation, low unresolved critical-defect count, and release rehearsal |
| MVP | Sellable, supported Windows release providing the complete bounded preparation workflow and basic licensing without advanced AI. | All release gates, licensing/recovery tests, rollback plan, real-statue UAT, and approved limitations |
| Commercial v1 | MVP hardened through beta evidence, support readiness, upgrade policy, release channels, and sustainable packaging/pricing. | Release-candidate pass, signed artifacts, operational runbooks, and commercial approval |

## Acceptance and Release Gates

Every release stage must scale the depth of these gates to its risk; none may be marked complete because code exists.

1. Python/static validation and targeted service tests.
2. Complete Blender background suite, including preserved regressions.
3. Sprint/milestone acceptance runner with deterministic fixtures and edge cases.
4. At least one representative, permissioned real-statue smoke test; broader corpus coverage for beta and later.
5. Performance and memory evidence for affected complexity bands, including Standard/Deep or operation-specific limits.
6. Repository package validation and Blender-native extension validation.
7. Security scan for prohibited network, dynamic execution, secrets, traversal, unsafe command paths, and dependency drift.
8. Manual installed-build UI check covering happy path, error/skip states, stale data, cancellation, undo, and recovery where applicable.
9. Documentation and known-limitations review against actual behavior.
10. Upgrade and rollback plan, with rehearsal for external releases.
11. Clean version metadata, release notes, approved Git tag, artifact checksums, and traceable source commit.
12. Explicit product, engineering, and—where relevant—cultural/domain review sign-off.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Geometry corruption | Loss of valuable source work and trust | Protected original, verified backup, preview, small deterministic operations, undo, signatures, and audit logs |
| Dense-mesh performance or memory pressure | Blocked UI, crashes, impractical workflows | Centralized limits, staged work, progress/cancel, fixtures by complexity, memory instrumentation, and skip states |
| False positives or negatives | Wasted repair or missed defects | Calibrated fixtures, confidence labels, bounded evidence, human review, and comparison with independent tools/prints |
| Heuristic shell misclassification | Intentional ornament removed or hidden structure missed | Neutral labels, no automatic deletion, explainable evidence, and domain-reviewed policies |
| Blender API changes and version fragmentation | Broken installs or inconsistent results | Declared support matrix, compatibility CI/manual runs, stable adapters, and release-channel testing |
| Support burden | Commercial cost exceeds product value | Bounded MVP, strong evidence exports, documentation, diagnostic tooling, and staged beta |
| AI API cost or outage | Unpredictable margins and unavailable features | AI remains optional, provider abstraction, quotas, usage accounting, BYO/hosted evaluation, and local deterministic fallback |
| Loss of user trust | Adoption failure | Accurate wording, no hidden network, reversible actions, visible uncertainty, and incident/rollback process |
| Licensing friction | Paid users blocked during production | Simple policy, offline grace, recoverable activation, transparent errors, and support override process |
| Cultural or iconographic inaccuracy | Harmful or inappropriate assets/recommendations | Reviewed rule packs, provenance, scoped claims, expert/community review, and artist override |
| Dataset or customer-asset rights | Legal/privacy exposure | Explicit consent, provenance, sanitization, access control, retention/deletion policy, and no default uploads |
| Marketplace quality or IP failures | Buyer harm and brand damage | Delay launch until seller verification, rights checks, moderation, compatibility validation, and takedown/update processes exist |

## Open Product Questions

- Which Blender LTS and feature releases should commercial editions support, and for how long?
- Should licensing be subscription, perpetual with paid upgrades, or a hybrid by edition?
- Which workflows must remain entirely local, and which AI or collaboration cases justify a hosted boundary?
- Which FDM and resin printer profiles should follow the Bambu Lab X1 Carbon profile?
- Which repair operations and parameter ranges are safe enough for an approved batch, and which always require individual review?
- How should repair policies vary by face, hand, jewelry, ornament, pedestal, hollow shell, and printer process?
- How will cultural and iconographic rule packs be authored, reviewed, versioned, and challenged?
- What evidence threshold justifies a separate backend rather than local files and Blender APIs?
- Which real Chroma3D files can become sanitized regression fixtures, and what permission/provenance record is required?
- Which geometric-deviation metrics correlate with acceptable visible detail on real statues?
- What telemetry, if any, offers enough support value to justify explicit opt-in collection?
- Which capabilities belong in one product versus conditional Sculpt, Print Prep, Asset Studio, AI Assist, and Enterprise editions?
