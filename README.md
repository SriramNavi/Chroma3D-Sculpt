# Chroma3D Sculpt

Chroma3D Sculpt is a local Blender extension for production mesh diagnostics, controlled reversible repair, and advisory printability risk analysis of complex statue meshes. Repair preserves the original source; Printability never changes geometry, transforms, orientation, or scale.

**Current published release:** `v0.8.0-alpha.1`. Version 1.0 hardening proceeds from that published Sprint 7 release without changing the package version. Physical validation remains separate; no printability or print-success guarantee is provided.

Sprint 2.7 added the dataset storage architecture: Dataset `1.0.0` and Golden Benchmark `1.0.0` are packaged as verified release assets, while manifests, provenance, licenses, schemas, locks, and tooling remain in this product repository. The existing `v0.3.1-alpha.1` history is immutable; Sprint 3 advances the extension separately to `0.4.0-alpha.1`.

Sprint 3 implements the approved [Printability Engineering Specification](PRINTABILITY_SPECIFICATION.md) as a separate advisory path. It adds local versioned printer profiles, geometry facts, wall/feature/overhang/floating/contact/scale checks, bounded virtual orientation candidates, conservative scoring, stale-state protection, issue selection, and JSON/Markdown reports. It does not slice, generate supports, rotate, scale, or guarantee manufacturing success.

Sprint 4 adds a software-only layer above Sprint 3: separate hardware and generic material profiles, deterministic process composition, explicit feature flags, centralized limits, bridge/support/resin advisories, scale intervals, improved orientation comparison, bounded batch analysis, Printability Baseline `1.0.0`, regression comparison, and an offline HTML dashboard. See the [Advanced Preparation guide](docs/advanced-preparation/README.md).

Sprint 5 adds a workspace-only Controlled Optimization workflow. It generates deterministic candidates and plans, applies only explicit bounded steps to an independently owned copy, checkpoints every mutation, compares before/after evidence, supports undo/restore, accepts a separate optimized copy, discards session-owned resources, and exports an audit. Experimental decimation/remesh remain opt-in and advisory; automatic supports, slicing, G-code, printer control, and source replacement do not exist. See the [Controlled Optimization guide](docs/controlled-optimization/README.md).

Sprint 6 adds an Intelligent Optimization workflow. It generates named strategy families from Sprint 5 candidates, evaluates visible objective vectors, applies hard/soft constraints, constructs a bounded Pareto frontier, ranks with explicit tie-breaks, explains estimated versus measured evidence, retains local history, and recommends without auto-executing. Strategy execution still delegates to Sprint 5's isolated workspace/checkpoints and requires explicit selection. See the [Intelligent Optimization guide](docs/intelligent-optimization/README.md).

Sprint 7 implements the optional [AI Recommendation Foundation](docs/ai-recommendation/README.md). An OpenAI-first adapter sits behind a provider-neutral interface and uses one explicit user-initiated HTTPS request with BYOK from `OPENAI_API_KEY` or process-memory session entry. Context is consented, bounded, redacted, summary-only, and contains zero geometry. Provider output is untrusted strict JSON; local validation permits only exact current Sprint 5/6 IDs, fingerprints, evidence links, operation names, and parameter hashes. Preview, fresh approval, delegated checkpointed execution, accept-copy/discard, audit, and offline Sprint 6 fallback remain separate actions. No API key or network is required for installation or any Sprint 0–6 workflow.

**Current extension version:** 0.8.0-alpha.1

**JSON schema:** 2.0

**Repair audit schema:** 1.0

**Printability report / profile / settings schemas:** 1.0.0

**Advanced preparation / material / process / batch / dashboard schemas:** 1.0

**Controlled Optimization schemas:** 1.0

**Intelligent Optimization schemas:** 1.0 (strategy, policy, constraints, Pareto, ranking, explanation, history, audit)

**AI Recommendation schemas:** 1.0.0 (policy, context, exchange, recommendation, session, report, audit)

**Minimum Blender:** 4.4.0

**Validated runtime:** Blender 4.4.3 on Windows 11

**Future target:** Blender 4.5 LTS and newer

## Diagnostics

Standard profile runs the practical deterministic checks used for routine review:

- Exact loose, boundary, two-face manifold, and high-incidence edge classification.
- Vertex face-fan manifold anomalies, face-connected shells, and object/per-shell topological watertightness.
- World-space dimensions, surface area, and reliable closed-shell volume in millimetres.
- Shared-edge orientation consistency and closed-shell outward/inward state.
- Deterministic main shell, combined-criteria tiny-shell candidates, and neutral disconnected external-shell classification.
- Optional Bambu Lab X1 Carbon or custom rectangular build-volume evaluation in the current orientation.
- Bounded issue evidence, per-check status, timing, settings snapshot, analysis ID, and topology signature.

Deep profile includes Standard plus bounded BVH self-intersection candidates and closed-shell containment heuristics. Deep checks report `COMPLETED`, `SKIPPED`, `FAILED`, or `NOT_APPLICABLE`; a skipped check never appears as a successful zero-result check.

`Topologically watertight` means the required topology checks completed and the analyzed original mesh has closed face shells with no boundary, loose, high-incidence, or detected vertex-manifold anomaly. It is not a printability, wall-thickness, leak-proofing, or manufacturing guarantee.

Volume is reported as reliable only for closed, orientation-consistent shells. Surface area is world-space triangle area. Object transforms and scene scale are respected without applying transforms. Modifier output is not analyzed.

Shell classifications are `MAIN_SHELL`, `DISCONNECTED_EXTERNAL`, and Deep-only `POSSIBLY_INTERNAL`. Tiny shells and possible internal shells are review candidates, not guaranteed defects. Self-intersection findings are candidate face pairs produced by Blender's BVH overlap API after shared-topology filtering.

## Safe Repair

Safe Repair is an explicit, synchronous workflow:

1. Start a repair session from a valid mesh. Chroma3D copies the object and mesh datablock, preserves transforms, materials, modifiers, and visibility, and leaves the original visible and unchanged.
2. Generate a read-only repair plan tied to the current source signature, workspace signature, analysis ID, and immutable settings snapshot.
3. Review and explicitly apply supported operations: nearby duplicate merge, zero-length edge collapse, degenerate-face removal, loose-geometry removal, face-normal consistency, outward orientation of valid closed shells, selected tiny-shell removal, and selected bounded small-hole filling.
4. A separate mesh checkpoint is created before every operation. Use **Undo Last Repair** or **Restore Workspace to Start** when needed.
5. Review the post-repair diagnostics and before/after issue deltas.
6. Accept the repaired copy without replacing the source, or roll back and discard only the workspace. Export the schema 1.0 repair audit at any point.

Tiny-shell deletion and hole filling are never preselected. Normal changes require explicit selection. Stale plans, changed sources, changed workspaces, invalid candidate mappings, main-shell deletion, and oversized or unsafe holes are rejected.

## Repair Safety

All geometry-changing behavior is governed by the authoritative [Repair Safety Contract](REPAIR_SAFETY.md).

## Blender panel

Open **3D Viewport > Sidebar > Chroma3D > Chroma3D Sculpt**.

1. Select Standard or Deep.
2. Optionally select **Bambu Lab X1 Carbon** (256 × 256 × 256 mm) or enter a Custom build volume.
3. Select an active mesh in Object Mode and choose **Analyze Mesh**.
4. Review topology, physical metrics, shells, Deep states, build-volume fit, issue counts, and timings.
5. Use an issue-selection button to inspect stored vertex, edge, or face evidence in Edit Mode.
6. Choose **Export JSON Report** for a UTF-8 schema 2.0 report.
7. Expand **Safe Repair** to create, plan, apply, recover, compare, finalize, and export a repair audit.
8. Expand **Printability**, select a packaged or Custom profile and performance mode, then choose **Analyze Printability**.
9. Expand **Advanced Preparation**, compose Hardware + Material + nozzle/layer/plate/support policy, review feature flags, then analyze the active object or selected mesh batch.
10. Review status, confidence, score reasons, skipped/failed checks, risk evidence, and virtual orientation candidates; use explicit issue-selection controls where evidence exists.
11. Open **Controlled Optimization**, create a session, generate candidates and a plan, apply only selected workspace steps, review comparisons, then accept a separate copy or discard the workspace.
12. Optionally expand **AI Recommendation**, prepare and review the exact context disclosure, consent, use OpenAI BYOK or the deterministic offline Sprint 6 view, then review before preview and separately approve any delegated action.
13. Export the current non-stale result as schema 1.0.0 JSON or a human-readable Markdown report.

Issue selection is the only intentional state-changing Sprint 1 action. It changes selection/mode for inspection but never changes geometry. If topology changed after analysis it refuses with `Analysis is stale. Run Analyze Mesh again.`

## Build, test, and acceptance

From the repository root:

```powershell
Set-Location "E:\VPRS\Sriram\Projects\Chroma3D Sculpt"
py -m compileall -q blender_addon scripts tests manual-tests
py scripts\run_blender_tests.py --blender "D:\Softwares\Design\Blender\blender.exe"
py manual-tests\run_acceptance_gates.py --blender "D:\Softwares\Design\Blender\blender.exe"
py manual-tests\sprint1\run_sprint1_acceptance.py --blender "D:\Softwares\Design\Blender\blender.exe"
py manual-tests\sprint1-final\run_final_validation.py --blender "D:\Softwares\Design\Blender\blender.exe"
py manual-tests\sprint2\run_sprint2_acceptance.py --blender "D:\Softwares\Design\Blender\blender.exe"
py manual-tests\sprint2-final\run_final_validation.py --blender "D:\Softwares\Design\Blender\blender.exe"
py manual-tests\sprint3\run_sprint3_acceptance.py --blender "D:\Softwares\Design\Blender\blender.exe"
py manual-tests\sprint5\run_sprint5_acceptance.py --blender "D:\Softwares\Design\Blender\blender.exe"
& "D:\Softwares\Design\Blender\blender.exe" --background --factory-startup --python tests\blender\run_sprint7_tests.py
py manual-tests\sprint7\run_dataset_validation.py --source-directory ".validation-assets\dataset\raw" --blender "D:\Softwares\Design\Blender\blender.exe" --scope representative
py manual-tests\sprint7\run_dataset_validation.py --source-directory ".validation-assets\dataset\raw" --blender "D:\Softwares\Design\Blender\blender.exe" --scope full
py manual-tests\benchmarks\verify_golden_baseline.py
py manual-tests\benchmarks\run_golden_benchmark.py --self-check
py scripts\package_extension.py
py scripts\validate_package.py
& "D:\Softwares\Design\Blender\blender.exe" --background --command extension validate "E:\VPRS\Sriram\Projects\Chroma3D Sculpt\dist\chroma3d_sculpt-0.8.0-alpha.1.zip"
```

The locally built Sprint 7 candidate archive is `dist\chroma3d_sculpt-0.8.0-alpha.1.zip`. It is not a published release. Install it through Blender's **Edit > Preferences > Extensions > Install from Disk**, then enable the extension if prompted.

The background suite preserves the prior sprint regressions and adds 161 focused Sprint 5 tests. Sprint 5 evidence is generated under `manual-tests\sprint5`; generated JSON/log/dashboard folders and ZIP files remain ignored. See the [Printability user guide](docs/printability/USER_GUIDE.md), [Advanced Preparation user guide](docs/advanced-preparation/USER_GUIDE.md), and [Controlled Optimization user guide](docs/controlled-optimization/USER_GUIDE.md).

## Golden Benchmark Baseline

Sprint 2.6 establishes `benchmarks\golden` as the permanent regression
reference for dataset `1.0.0` and Chroma3D `0.3.0-alpha.1`. Every one of the 27
validated statues was processed in a fresh Blender 4.4.3 factory-startup
process through the existing production operators:

`Analysis -> Repair Plan -> Repair -> Comparison -> Accept/Audit`

Undo and restore were exercised before the canonical apply where applicable.
Accept and rollback were captured as separate normal production decisions.
The run completed 27/27 meshes with no worker or integrity failures, covered
12,925,711 triangles, recorded 7,432.224 seconds of wall time and 7,208.328
seconds of Blender CPU time, and observed a 3.509 GiB maximum process working
set. Stored production diagnostic warnings remain golden evidence, not
benchmark execution failures.

The authoritative index is
`benchmarks\golden\manifests\golden_manifest.json`. It links one self-contained
golden truth record per mesh to the production analysis reports, accepted and
rollback repair audits, comparisons, timings, statistics, thumbnails, source
hashes, artifact hashes, schema fingerprints, software versions, and machine
information.

Future releases rerun and compare without overwriting the baseline:

```powershell
py manual-tests\benchmarks\run_golden_benchmark.py --compare `
  --blender "D:\Softwares\Design\Blender\blender.exe"
```

The regression rules in `benchmarks\golden\README.md` fail deterministic
topology, diagnostic, repair, audit, schema, version, and hash changes; classify
bounded same-machine timing degradation as WARNING or FAIL; and warn when a
machine mismatch makes timing non-comparable. An intentional product, schema,
dataset, or benchmark-policy change requires explicit review and a new
versioned baseline.

## External validation assets

Large local payloads are acquired into an ignored cache and are not required for ordinary lint or unit-test jobs:

```powershell
py scripts\fetch_validation_assets.py status --json
py scripts\fetch_validation_assets.py dataset
py scripts\fetch_validation_assets.py benchmark
py scripts\fetch_validation_assets.py verify --json
```

Use `--offline` after acquisition. See [DATASET_STORAGE_POLICY.md](DATASET_STORAGE_POLICY.md), [VERSIONING_DATASETS_AND_BENCHMARKS.md](VERSIONING_DATASETS_AND_BENCHMARKS.md), and [docs/DATASET_CI_GUIDE.md](docs/DATASET_CI_GUIDE.md). Sprint 3's resumable dataset runner uses one bounded factory-startup Blender process per STL and retains explicit failures or timeouts.

## Known limitations and safety

- Modifier output, slicer support clearances, purge zones, resin hollowing/drain/suction behavior, and optimal print orientation are not evaluated.
- Wall thickness is sampled and estimated; connected thin-feature detection is an experimental conservative diameter proxy.
- Contact/stability and orientation ranking are heuristics. Candidates are virtual, bounded, and not guaranteed optimal.
- Self-intersection results are candidates; containment is a bounded heuristic with confidence evidence.
- Build-volume and scale evaluation is rectangular and advisory; it performs no rotation or scaling.
- The original source is preserved, but repaired workspace copies still require human review.
- Unfinished diagnostic, repair, optimization, and AI-assistance sessions are session-only. Save/reload and extension reload clear their transient IDs, previews, approvals, cancellation state, and runtime object references; start a fresh session after reload.
- There is no remeshing, large-hole reconstruction, Boolean repair, wall-thickness repair, decimation, object joining, modifier application, automatic scaling, or print support generation.
- Printability and manufacturing success are not guaranteed.
- Manual interactive installed-panel testing, Blender 4.5 LTS validation, and real Chroma3D statue repair UAT remain deferred.
- Core runtime workflows are offline and use only Blender APIs plus Python's standard library. The optional Sprint 7 provider adapter can make one explicit consented BYOK HTTPS request; keys remain process-memory/environment only. There is no telemetry, bundled credential, server component, downloaded code, arbitrary `eval`/`exec`, or external Python package. Intelligent Optimization itself is rule-based local intelligence, not generative AI.

Runtime paths are derived from Blender APIs and package-relative files. Windows paths containing spaces are supported.
