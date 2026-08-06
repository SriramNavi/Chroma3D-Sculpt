# Project Rules

## Foundation

- Repository root: `E:\VPRS\Sriram\Projects\Chroma3D Sculpt`.
- Primary platform: Windows 11 without administrator privileges.
- Minimum runtime: Blender 4.4.0 and bundled Python; current validation is Blender 4.4.3.
- Package: modern Blender Extension; manifest `0.8.0`, display `0.8.0-alpha.1`, analysis JSON schema `2.0`, repair audit schema `1.0`, printability report schema `1.0.0`, Advanced Preparation schema `1.0`, Controlled/Intelligent Optimization schemas `1.0`, and AI Assistance schemas `1.0.0`.
- Dependencies: public Blender APIs and Python standard library only.
- Runtime paths must be dynamic; repository tooling must support quoted Windows paths containing spaces.

## Sprint 1 diagnostic policy

- Analysis is read-only and operates on the original mesh datablock; modifier output is explicitly not analyzed.
- Standard runs deterministic core diagnostics. Deep adds bounded self-intersection candidates and containment heuristics.
- Every check reports `COMPLETED`, `SKIPPED`, `FAILED`, or `NOT_APPLICABLE`; a skip/failure must contain an honest reason, actual size, and applicable limit.
- Physical area, volume, containment, intersection, dimensions, and build-volume checks use world-space coordinates plus scene unit scale.
- Reliable volume requires a closed, orientation-consistent shell. Positive signed volume means outward under the tested convention.
- Topological watertightness, tiny shells, self-intersections, containment, and build-volume fit must never be worded as printability or manufacturing guarantees.
- Issue evidence is bounded and reports total count, cap, sample, and truncation. Default index and pair caps are 10,000.
- Default performance limits are 500,000 duplicate-check vertices, 50,000 self-intersection triangles, 64 containment shells, and 100,000 containment triangles.
- The user-triggered issue-selection operator may change selection and mode only. Stale topology must be rejected before selection.
- JSON schema versions are explicit. Preserve compatible Sprint 0 fields where practical and add new fields without unsafe objects.

## Sprint 2 repair policy

- [REPAIR_SAFETY.md](REPAIR_SAFETY.md) is the authoritative contract for all geometry-changing behavior.
- Geometry-changing operations run only on an independent workspace object with an independent mesh datablock; the protected source signature is verified before and after every operation.
- Every operation creates an independent checkpoint. Failures restore automatically; successful checkpoints are retained to the configured bounded depth. Undo and restore invalidate the plan and rerun diagnostics.
- Repair plans bind the session, analysis ID, source signature, workspace signature, settings, order, evidence, and candidate mappings. Stale plans never execute.
- Safe order is duplicate merge, zero-length collapse, degenerate-face removal, loose cleanup, selected tiny-shell removal, selected bounded-hole fill, normal consistency, then valid closed-shell outward orientation.
- Tiny-shell and small-hole actions require explicit candidate selection. The main shell, medium ornament, rejected boundary, unselected candidate, and unrelated face shell are protected.
- Accept keeps source and repaired copy. Rollback deletes only repair-session workspace/checkpoints. Neither path saves automatically.
- Repair audit schema 1.0 records bounded plan, settings, operation, checkpoint, undo, comparison, decision, warning, error, and limitation evidence.
- The 50,000–150,000-vertex repair batch uses 60 seconds as a warning threshold, not a production guarantee.

## Runtime safety

- No source repair, unapproved deletion, transform application, modifier evaluation, automatic file save, hidden network, telemetry, stored credentials, server, downloaded code, `eval`, or `exec`. Sprint 7 permits only an explicit consented user-initiated allow-listed provider request under the policy below.
- Catch memory and Blender-context failures and preserve `FAILED` rather than inventing zero findings.
- Avoid recursion, quadratic mesh passes, per-element logging, persistent handlers, and retained temporary BMesh/BVH data.

## Sprint 4 advanced-preparation policy

- Keep hardware facts separate from generic material/process heuristics; every effective threshold retains origin, provenance, confidence, and a deterministic context hash.
- Disabled feature flags return `NOT_EVALUATED`; experimental flags require explicit user enablement and invalidate cached evidence.
- All advanced limits come from the validated performance registry. `SKIPPED_LIMIT`, `INDETERMINATE`, and `FAILED` remain non-pass states.
- Bridge/support/resin/scale/orientation results are advisory. Never generate supports, hollowing, drain holes, slices, G-code, uploads, printer commands, or automatic transforms.
- Batch analysis is bounded, deterministic, source-isolated, resumable, and preserves partial failure evidence.
- Printability Baseline 1.0.0 binds Dataset/Golden 1.0.0 plus source, implementation, process, material, flags, settings, and schema identities; it is not physically calibrated.

## Sprint 5 controlled-optimization policy

- Optimization never mutates the protected source. Every workspace has an independent object, mesh datablock, session-owned collection, ownership metadata, and retained initial checkpoint.
- Candidate and plan generation are read-only, deterministic, bounded, and stale when source, workspace, process, material, feature, performance, policy, objective, or implementation identity changes.
- Every geometry-affecting workspace operation requires a valid checkpoint; failures restore automatically. Ordinary plan selection is explicit user approval; base stabilization, decimation, and remesh require the additional explicit approval flag.
- Accept retains the source and a separate optimized object. Discard removes only session-owned workspace/checkpoints. Neither path saves automatically.
- Comparison must preserve critical regressions, missing evidence, `INDETERMINATE`, and `SKIPPED_LIMIT`; heuristic objective scores never claim global optimality or print success.
- Experimental remesh is deferred in the safe runtime. No automatic supports, hollowing, drain holes, slicing, G-code, printer control, network runtime, or source replacement exists.

## Sprint 6 intelligent-optimization policy

- Intelligent Optimization is deterministic local rule-based search, not generative AI. Search policies are mode-specific, bounded, hashable, and reject booleans-as-numbers, NaN, infinity, negative/unsafe budgets, unknown operations, duplicate IDs, conflicting constraints, and hidden experimental enablement.
- Strategy generation, virtual evaluation, Pareto construction, ranking, explanations, recommendations, history reuse, and exports are read-only. Unknown or skipped evidence never satisfies a hard constraint or dominates known valid evidence; no global optimum or print-success claim is permitted.
- Workspace preview/execution must delegate to Sprint 5's isolated workspace and checkpoint services. Every selected mutation remains explicit, rollback-safe, source-preserving, and followed by comparison. Accept creates a separate optimized copy; discard/cancel remove only owned resources.
- Sprint 6 schemas are all version `1.0`: intelligent strategy, strategy set, search policy, constraint set, Pareto frontier, ranking, explanation, optimization history, and intelligent audit.

## Sprint 7 AI-recommendation policy

- Assistance is optional and disabled by default. Installation, registration, startup, panel drawing, analysis, repair, preparation, optimization, packaging, and automated tests perform no live provider request and require no API key.
- Direct OpenAI BYOK uses `OPENAI_API_KEY` or session-only process memory. Keys never enter Blender data, preferences, reports, audits, logs, fixtures, source, or package assets.
- Context is explicit, consented, allow-listed, bounded, redacted, and summary-only with zero geometry. Destination, purpose, categories, retention, and cost/usage limitations are visible before request.
- Provider JSON is untrusted. Duplicate keys, non-finite values, unknown fields/IDs/evidence/operations, arbitrary parameters, code/shell/path/URL content, policy bypass, guarantees, and stale or hard-infeasible evidence fail closed.
- Actionable output resolves an exact current Sprint 5 candidate/plan or Sprint 6 strategy plus fingerprint, operation, candidate, and canonical parameter hash. Safe-default operations are scale, orientation, and build-plate translation; gated operations remain disabled unless an explicit local policy enables them; remesh is prohibited.
- Recommendation, selection, preview, approval, delegated execution, comparison, accept-copy/discard, export, cancellation, and offline fallback are distinct states. Any bound change revokes preview/approval. No automatic retry, provider switch, execution, acceptance, source replacement, learning, or policy mutation exists.

## Regression and release

- Preserve all Sprint 0 and Sprint 1 Blender tests and historical reports.
- Run compilation, all Blender tests, Sprint 0 acceptance, Sprint 1 acceptance, Sprint 1 final validation, Sprint 2 acceptance, repository package validation, Blender-native validation, security scan, `git diff --check`, and final diff review.
- Generated reports/logs/screenshots/artifacts and ZIPs stay ignored. Track acceptance runners and human Sprint result files.
- Do not commit, push, tag, publish, reset, clean, or discard local changes unless explicitly requested.

## Token and context policy

Inspect narrowly, maintain a concise phase ledger, prefer targeted symbol searches and diffs, avoid repeated file dumps, and report actual evidence plus anything not run.
