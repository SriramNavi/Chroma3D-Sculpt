# Chroma3D Sculpt Architecture

Chroma3D Sculpt 0.8.0-alpha.1 is a synchronous, local-first Blender extension with independent diagnostic, controlled-repair, advisory-printability, advanced-preparation, controlled-optimization, intelligent-optimization, and optional AI-recommendation paths. Dependency direction is `UI -> operators -> coordinator -> focused services -> typed models/utilities`. Sprint 7 uses `UI -> assistance operators -> assistance coordinator -> pure context/validation/provider interfaces -> existing Sprint 5/6 coordinators`; provider adapters are Blender-reference-free.

## Sprint 7 specification architecture

The implemented [Sprint 7 Engineering Specification](SPRINT7_SPECIFICATION.md) adds an optional OpenAI-first provider-neutral layer. Provider adapters cannot import Blender or call operators/coordinators. Context contains only bounded consented JSON-safe summaries/evidence identities, never raw geometry, paths, assets, or credentials. Provider output is untrusted data and becomes previewable only after strict decoding, semantic/evidence validation, and exact resolution to a current existing candidate, plan, or strategy. The AI layer owns no mutation implementation; fresh approval delegates only to the established Sprint 5/6 safety boundary.

Recommendation and preview remain read-only. A fresh explicit approval may delegate an already validated plan to Sprint 5/6's isolated workspace, checkpoint, comparison, restore, accept-copy and discard interfaces. Sprint 7 must not duplicate geometry mutation, weaken source signatures or stale checks, add hidden network activity, or block the deterministic local product when assistance is disabled/unavailable. Live provider/backend/BYOK/hosted deployment remains a decision gate; draft schemas under `schemas/sprint7-draft/` are specification artifacts and are not packaged.

## Intelligent Optimization architecture

Sprint 6 is a pure deterministic search layer above Sprint 5. `intelligent_optimization_models.py` serializes only bounded identities, hashes, objective scalars, evidence states, constraints, rankings, and audit data. `search_policy.py`, `constraint_engine.py`, `strategy_generator.py`, `strategy_evaluator.py`, `pareto_frontier.py`, `strategy_ranker.py`, `strategy_explainer.py`, and `strategy_history.py` are Blender-reference-free. `intelligent_optimization_coordinator.py` owns lifecycle and stale-state checks; it delegates every geometry mutation to Sprint 5's workspace, checkpoint, comparison, accept-copy, and discard interfaces. Search and recommendation never mutate the protected source and never auto-execute.

## Controlled Optimization architecture

Sprint 5 is a bounded, reversible layer above the Sprint 2-4 services. `optimization_session.py` captures a protected source snapshot and owns an independent object, mesh datablock, collection, and checkpoint store. `optimization_candidates.py` and `optimization_plan.py` are read-only and bind evidence to process, feature, policy, objective, and implementation hashes. `optimization_operations.py` mutates only the owned workspace and restores the last valid checkpoint on failure. `optimization_comparison.py` retains missing/indeterminate evidence and conservative fidelity proxies; `optimization_audit.py` serializes JSON-safe identity, history, stale events, and outcomes. The panel exposes explicit session, plan, apply, undo, restore, accept-copy, discard, and export actions. No source replacement, automatic optimization, support generation, slicing, G-code, or printer command exists.

## Advanced preparation architecture

Sprint 4 composes immutable hardware facts, a schema-validated generic material profile, nozzle, layer height, build plate, support policy, and user overrides into a deterministic process context. The context retains per-threshold provenance and feeds the unchanged Sprint 3 engine through a transient compatibility adapter; reports retain the original hardware and material snapshots separately.

`advanced_preparation_coordinator.py` is the read-only orchestration boundary. It invokes bounded bridge, support, resin, scale, and orientation services; masks explicitly disabled checks as `NOT_EVALUATED`; verifies source/file-state immutability; and stores only JSON-safe evidence. `performance_registry.py` is the only Sprint 4 algorithm-limit registry. `feature_flags.py`, process hashes, build direction, source identity, settings, and registry version participate in stale-state rejection.

Batch analysis is sequential and isolated per object, preserves partial failures, supports resume/cancellation between objects, and never shares geometry state. Baseline services bind 27 per-model records to source/process/flag/implementation hashes. The comparator preserves classification, score, timing, ranking, failure, and skip-state changes; the dashboard is static local HTML with embedded CSS/JavaScript and escaped user content.

## Printability architecture

Sprint 3 implements a separate advisory path: immutable source/profile/settings
snapshots -> world-space geometry facts -> focused checks -> risk items ->
score/status/confidence -> bounded report evidence. `printability_coordinator.py`
orchestrates the path; focused services own wall thickness, thin features,
overhangs, floating components, plate contact, build-volume/scale evaluation,
orientation candidates, scoring, session state, and report generation.

Printer profiles are local schema-validated JSON. Manufacturer facts remain
separate from project defaults, heuristics, experimental rules, and user
configuration. Results are tied to geometry, transform, profile, build direction,
settings, and Blender file state. Stale evidence cannot drive selection or export.
All candidates are virtual: the engine does not mutate geometry, apply transforms,
rotate, scale, slice, generate supports, or save files.

## Authoritative repair contract

[REPAIR_SAFETY.md](REPAIR_SAFETY.md) is the authoritative contract for every geometry-changing operation. The repair architecture and all future repair implementations must conform to it.

## Coordinator flow

`chroma3d.analyze_mesh` captures active-object and selection identity, rejects Edit Mode, snapshots immutable settings from `WindowManager`, and calls `services/mesh_analyzer.py`. The coordinator:

1. Snapshots object, mesh, mode, selection, transforms, and counts.
2. Builds an analysis ID and SHA-256 topology signature.
3. Reads the original mesh datablock and creates world-space vertices and loop triangles.
4. Runs topology, duplicate-position, shell, build-volume, and requested Deep services.
5. Collects bounded issue evidence, explicit evaluation states, and monotonic timings.
6. Verifies the read-only snapshot and returns an immutable `AnalysisResult`.

Modifiers are counted but never evaluated or applied. No service writes mesh coordinates, connectivity, winding, transforms, materials, names, scene data, or files.

## Models and settings

`models/analysis_result.py` owns enums and frozen dataclasses for severity, evaluation state, confidence, watertightness, manifold states, orientation, containment, self-intersection, build-volume fit, issue evidence, settings snapshots, shell metrics, physical metrics, Deep metrics, signatures, checks, timings, and the schema 2.0 result. Serialization walks only dataclasses, enums, tuples, lists, dictionaries, timestamps, and scalar values; Blender, BMesh, BVH, set, and object references are never serialized.

`analysis_settings.py` centralizes tolerances, evidence caps, Deep limits, and printer profiles. Standard and Deep use the same core path; Standard marks Deep checks `NOT_APPLICABLE`, while requested Deep checks can explicitly complete, skip, or fail.

## Topology and shells

`topology_analyzer.py` builds face-edge incidence in linear passes. Edge linked-face counts are classified independently as loose, boundary, manifold, or high-incidence. Vertex-manifold anomalies use an iterative local face-fan adjacency traversal. Face shells use iterative shared-edge traversal with stable IDs; no recursion or all-pairs vertex pass is used.

A shell is topologically watertight only when it has faces, has no boundary or high-incidence edge, has no detected vertex face-fan anomaly, and required checks completed. Multiple closed disconnected shells can each be watertight while still producing a review warning.

`shell_analyzer.py` maps world-space loop triangles to face shells. Surface area uses triangle cross products. Signed volume uses tetrahedra relative to each shell's bounding-box minimum for numerical stability. Positive signed volume is `OUTWARD`; negative is `INWARD`. Open, inconsistent, or indeterminate shells do not contribute a reliable volume.

Main-shell ranking is largest reliable absolute volume, then surface area, then face count, then stable shell ID. Tiny candidates require at least two enabled criteria among face count, absolute volume, relative volume, and bounding-box diagonal. Other non-main shells remain neutrally `DISCONNECTED_EXTERNAL` unless Deep containment classifies them `POSSIBLY_INTERNAL`.

## Deep spatial diagnostics

`deep_diagnostics.py` builds temporary `mathutils.bvhtree.BVHTree` instances from world-space triangles. Self-overlap pairs exclude identical triangles, same-face triangulation, duplicate order, and shared-vertex local topology. Results remain candidate pairs and are capped for storage while the total count is retained.

Containment evaluates only closed shells with reliable volume. World AABB containment is the broad phase. Candidate pairs use deterministic multi-point ray-parity voting in three non-axis directions; votes produce LOW, MEDIUM, or HIGH confidence. Shell/triangle limits produce explicit `SKIPPED` states with actual sizes and configured limits. Temporary BVHs are local and are released after analysis.

## Issue evidence and stale protection

`session.py` caches immutable results by object identity for the Blender session only, with a 32-report bound and no Blender object references. Each issue category retains total count, bounded indices or pairs, cap, domain, and truncation state.

`utilities/signatures.py` hashes object name, mesh name, counts, edge connectivity, and polygon connectivity. `chroma3d.select_diagnostic_issue` refuses mismatches, switches explicitly to the correct mesh-selection domain, selects only stored valid indices, and enters Edit Mode. It never creates, deletes, moves, rewinds, or transforms geometry.

## UI, export, and tooling

`ui/properties.py` owns settings and small UI scalars. `ui/panels.py` renders bounded summaries rather than complete issue arrays or hundreds of shell rows. `report_generator.py` writes readable deterministic UTF-8 JSON with a trailing newline and Windows-safe naming.

Repository tooling discovers Blender safely, runs all background `unittest` files with factory startup, preserves historical Sprint 0 evidence, executes Sprint 1 acceptance, builds the modern extension ZIP at archive root, and rejects tests, evidence, logs, secrets, bytecode, traversal, and nested roots.

## Performance boundaries

Core passes are linear in vertices, edges, face loops, or triangles. Duplicate detection uses fixed-neighbour spatial hashing and skips above 500,000 vertices by default. Self-intersection defaults to 50,000 triangles; containment defaults to 64 shells and 100,000 triangles. Issue indices and candidate pairs default to 10,000 stored items per configured cap. Every major check and total analysis use `perf_counter` timing.

## Repair lifecycle

`services/repair_session.py` captures a protected source snapshot containing object/mesh identity, names, geometry hash, connectivity and winding, transforms, modifiers, materials, collection membership, custom properties, and visibility. It copies both the object and mesh datablock, links the copy beside the source, verifies the datablocks are independent, creates the initial checkpoint, runs complete diagnostics on the workspace, and activates only the workspace for repair. The live session stores identities and JSON-safe evidence, not serializable Blender objects.

An unfinished session is intentionally session-only. Extension unload releases zero-user checkpoint meshes but leaves the workspace as ordinary user-visible scene data; it never attempts an unsafe implicit resume or deletes the workspace.

## Plan and stale protection

`services/repair_plan.py` previews targeted evidence without mutation and binds the plan ID to the session, analysis ID, source signature, workspace signature, analysis profile, immutable repair settings, operation order, recommendations, bounded candidate mappings, warnings, and limitations. Repair commands reject a missing/deleted source or workspace, changed source state, replaced workspace datablock, external workspace geometry change, settings mismatch, analysis mismatch, stale plan, unrelated active object, or stale candidate fingerprint.

Tiny-shell mappings derive from stable world-space coordinate fingerprints and Sprint 1 shell classifications, with an additional physical diagonal criterion for deletion eligibility. Small-hole mappings derive from simple closed boundary components. Neither candidate type is preselected.

## Controlled operations

`services/repair_operations.py` owns focused workspace-only BMesh mutations. Duplicate detection uses neighboring world-space millimetre cells and deterministic lowest-index representatives. Zero-length edges use deterministic connected endpoint groups. Degenerate faces use world-space area and `FACES_ONLY` deletion. Loose cleanup deletes zero-face edges and then isolated vertices while preserving disconnected face shells. Normal consistency and valid closed-shell outward orientation do not change coordinates. Tiny-shell removal deletes only selected disconnected shell vertices. Hole fill passes only selected eligible boundary edges to Blender's supported BMesh hole-fill operation.

`services/repair_coordinator.py` is the only normal orchestration entry. It validates the protected source, creates a checkpoint, dispatches one operation, revalidates the source, reruns diagnostics, records the outcome, and either retains a bounded undo checkpoint or discards a no-change checkpoint. Exceptions restore the checkpoint before the failure is surfaced. Batch execution follows the documented safe order and uses Blender progress reporting.

## Checkpoints, undo, and memory

The initial and per-operation checkpoints are independent zero-user mesh copies held only by the session service. The initial snapshot is retained for restore-to-start. Applied-operation history is bounded by the centralized depth; eviction occurs only after a geometry-changing operation succeeds, so a failed or no-change attempt cannot remove an earlier undo point. Undo replaces the workspace mesh from the immediate checkpoint, marks the operation `UNDONE`, reruns diagnostics, and stales the plan. Restore-to-start replaces from the initial snapshot, clears retained operation checkpoints, marks applied history undone, clears plan/comparison state, and reruns diagnostics. Accepted and rolled-back sessions clear all checkpoint datablocks.

The default checkpoint depth is three. Candidate evidence defaults to 10,000 indices. Repair code avoids per-element logs and O(n²) all-mesh comparisons. The Sprint 2 stress gate records fixture construction separately from repair duration and treats 60 seconds as a warning threshold.

## Comparison, audit, and finalization

After repair, the coordinator compares geometry counts and diagnostic issue metrics, preserving improved, unchanged, regressed, skipped, and failed states rather than treating lower geometry counts as success. Accept reruns diagnostics, renames the workspace to a collision-safe repaired-copy name, keeps both objects, clears checkpoints, and never saves. Rollback removes only the workspace and unused workspace mesh, clears checkpoints, restores captured selection where practical, and preserves an exportable archived audit summary.

`services/repair_audit.py` exports repair audit schema 1.0 with extension/analysis versions, environment, session and plan IDs, protected and workspace signatures, immutable settings, bounded candidates, operation/checkpoint/undo/failure records, comparison, decision, timing, warnings, errors, and limitations. JSON is UTF-8, readable, newline-terminated, and Windows-safe; raw mesh data and Blender objects are excluded.
