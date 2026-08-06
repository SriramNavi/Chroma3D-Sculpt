# Changelog

## 0.7.0-alpha.1 - 2026-08-06 (Sprint 6)

### Added

- Deterministic FAST/STANDARD/DEEP/CUSTOM intelligent search policies with centralized budgets, explicit constraint sets, strategy-family generation, pruning records, objective vectors, Pareto-front construction, explainable ranking, recommendation overrides, local history, and complete JSON/Markdown audit export.
- Native Intelligent Optimization panel and explicit start, generate, evaluate, Pareto, rank, review, preview, execute, cancel, accept-copy, discard, and export actions.
- Sprint 6 focused Blender tests, resumable dataset identity tooling, acceptance wrapper, and independent final-validation wrapper.

### Safety

- Search, ranking, and recommendations are read-only. Workspace execution delegates to Sprint 5's protected isolated workspace and checkpoint model; the protected source is never replaced or automatically accepted.
- No AI/LLM, cloud service, telemetry, automatic execution, supports, slicer, G-code, printer command, physical validation, or global-optimum claim exists.

### Evidence boundary

- Estimated, measured, skipped, indeterminate, infeasible, dominated, and budget-limited states remain explicit. Physical printing, slicer comparison, material calibration, Blender 4.5 LTS, and manual installed-panel UAT remain separate evidence tasks.

## 0.5.0-alpha.1 - 2026-08-05 (feature branch)

### Added

- Separate hardware and generic material profiles with schema 1.0 validation, provenance, compatibility checks, deterministic composition, and stale-result hashes.
- Explicit feature flags and a central FAST/STANDARD/DEEP performance registry by mesh-size class and check type.
- Advisory bridge-risk, support-risk, bounded resin geometry checks, material-aware scale intervals, improved orientation comparison with non-dominated candidates, and safe selected-object batch analysis.
- Advanced Preparation JSON/Markdown reports, Printability Baseline 1.0.0, regression comparator modes, and a dependency-free offline HTML dashboard.
- A 132-case Sprint 4 Blender matrix, resumable 27-model workers, acceptance tooling, package integration, and Advanced Preparation panel.

### Safety

- No Sprint 4 operation changes geometry, transforms, modifiers, materials, collections, visibility, properties, or file save state.
- No support generation, slicing, G-code, network runtime, upload, automatic orientation/scale, or printer command exists.
- Material, bridge, support, resin, scale, and orientation output remains advisory and is not physically calibrated.

### Validation

- Passed 363/363 combined Blender tests, including the 132-case Sprint 4 matrix.
- Passed all 16 Sprint 4 acceptance gates and the fingerprint-bound Dataset 1.0.0 run for 27/27 immutable models.
- Generated and self-compared 27 Printability Baseline 1.0.0 records plus the self-contained offline dashboard.
- Passed package, repository, Blender-native, registration, security, and whitespace gates.
- Sprint 0, Sprint 1, Sprint 1-final, Sprint 2, Sprint 3, and Sprint 3-final runners passed. Sprint 2-final retained one environment-sensitive performance warning: its realistic repair batch took 115.83s, and an isolated recheck took 106.69s, above the unchanged 60s gate; all other Sprint 2-final gates passed.

### Known limitations

- Generic material profiles are uncalibrated project defaults; bridge/support/resin output is bounded advisory evidence.
- The dense Hizen Komainu Sprint 4 worker required 659.3s, so the resumable per-mesh evidence envelope is 900s and remains active performance debt.
- Installed Advanced Preparation panel UAT, Blender 4.5 LTS, slicer comparison, material calibration, and physical printing remain deferred.

## 0.4.0-alpha.1 - 2026-08-04

### Added

- Added the profile-driven Printability Engine with schema-validated Generic FDM, Generic Resin, Bambu Lab X1 Carbon, Bambu Lab P1S, Prusa MK4, and validated Custom printer/process profiles.
- Added immutable world-space geometry facts, bounded sampled wall-thickness estimates, a conservative thin-feature risk proxy, overhang analysis, floating-component analysis, build-plate contact classification, and build-volume/scale evaluation.
- Added deterministic virtual orientation recommendations and conservative weighted risk scoring with critical caps and explicit confidence/evidence states.
- Added stale-result protection, bounded evidence selection, UTF-8 schema 1.0.0 JSON/Markdown reports, and the native Blender Printability panel.
- Added the Sprint 3.5 physical validation framework with print job cards, calibration coupons, observation schemas, calibration comparison tooling, and a governed printability baseline policy.

### Safety

- Printability analysis is read-only and does not mutate geometry or transforms.
- No automatic scaling or orientation application, support generation, slicing, G-code generation, runtime network access, or print-success guarantee is provided.

### Validation

- Passed 231/231 combined Blender tests, including 121/121 focused Sprint 3 tests and the historical Sprint 0/1/2 regressions.
- Passed 15/15 Sprint 3 acceptance gates and 13/13 independent Sprint 3 final-validation gates.
- Passed Dataset 1.0.0 validation for 27/27 models while preserving source hashes, geometry signatures, and source immutability.
- Passed the isolated installed-package smoke, package validators, and package security checks.

### Known limitations

- Wall thickness is sampled and estimated; the thin-feature check is a conservative connected-shell proxy that does not recognize local merged features.
- Contact stability remains heuristic, and bounded orientation recommendations are not globally optimal.
- Physical validation and resin calibration are pending; real slicer comparison has not been run.
- Blender 4.5 LTS validation and manual installed-panel interaction remain pending.

## 0.3.0-alpha.1 - 2026-07-18

- Added protected, independent repair workspaces with full source-state signatures and source checks before and after every operation.
- Added evidence-bound repair plans, centralized millimetre settings, safe ordering, stale-plan rejection, and explicit tiny-shell/small-hole selection.
- Added controlled duplicate merge, zero-length collapse, degenerate-face removal, loose cleanup, normal consistency, outward closed-shell orientation, selected tiny-shell removal, and bounded selected-hole fill.
- Added bounded mesh checkpoints, undo-last, restore-to-start, automatic failure rollback, accepted-copy finalization, and workspace-only session rollback.
- Added before/after diagnostic comparisons and UTF-8 repair audit schema 1.0 export.
- Added Safe Repair sidebar controls, 56 focused Sprint 2 Blender tests, 14 acceptance gates, and a 50,000+ vertex repair stress fixture.
- Preserved analysis schema 2.0, the read-only analysis path, offline runtime, and all Sprint 0/Sprint 1 regressions.

## 0.2.0-alpha.1 - 2026-07-17

- Added Standard and Deep production diagnostic profiles with immutable settings snapshots and per-check timings.
- Added exact edge incidence, vertex face-fan anomaly, topological watertightness, stable shell decomposition, and bounded issue evidence.
- Added world-space shell dimensions, surface area, reliable closed-shell volume, orientation consistency, and outward/inward classification.
- Added deterministic main-shell ranking, combined-criteria tiny-shell candidates, disconnected external shells, and heuristic possible-internal shells with confidence evidence.
- Added bounded BVH self-intersection candidates with adjacency filtering, evidence caps, and explicit limit skips.
- Added Bambu Lab X1 Carbon and custom current-orientation build-volume checks.
- Added stale-analysis topology signatures and the explicit non-destructive issue-selection operator.
- Upgraded JSON reports to schema 2.0 and the extension package to 0.2.0-alpha.1.
- Added 36 Sprint 1 Blender tests, 12 acceptance gates, a 146,968-vertex Standard stress fixture, and preserved Sprint 0 regression gates.

## 0.1.0-alpha.1 - 2026-07-17

- Added the initial Windows foundation with Blender 4.4 minimum support.
- Validated the complete Sprint 0 runtime and package on Blender 4.4.3; Blender 4.5 LTS and newer remain the future compatibility target.
- Updated the development installer command for Blender 4.4's required extension repository argument.
- Added the modern extension manifest and clean registration lifecycle.
- Added the Chroma3D sidebar panel and session-only state.
- Added read-only mesh analysis and JSON report export.
- Added packaging, package validation, Windows Blender discovery, and PowerShell wrappers.
- Added procedural Blender background tests.
- Added token and context management governance.
