# Sprint 1 Architecture

Chroma3D Sculpt 0.2.0-alpha.1 is a synchronous, local, diagnostic-only Blender extension. Dependency direction is `UI -> operators -> coordinator -> focused services -> typed models/utilities`. Diagnostic services do not import UI modules.

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
