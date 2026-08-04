# Chroma3D Sculpt v0.3.1-alpha.1

## Golden Benchmark Baseline

Sprint 2.6 establishes the permanent Golden Benchmark Baseline for the validated real-statue corpus.

- 27/27 meshes processed successfully with zero worker failures.
- One golden truth record per mesh, with production analysis, repair/audit lifecycle evidence, comparisons, timings, hashes, schema fingerprints, statistics, reports, and thumbnails.
- Authoritative manifest: `benchmarks/golden/manifests/golden_manifest.json`.
- Total wall time: 7,432.224 seconds.
- Total Blender CPU time: 7,208.328 seconds.
- Peak observed process working set: 3.509 GiB.
- Timing distribution: 1 Tiny, 7 Small, 5 Medium, 2 Large, 9 Huge, and 3 Extreme meshes.
- Stored production diagnostic warnings: 89.

## Regression Runner

- Golden verifier: 27/27 meshes, 193 JSON artifacts, zero integrity failures.
- Comparator self-check: 27/27 PASS.
- Stored live `statue-bastet` regression: PASS.
- Combined Blender validation evidence: 110/110 tests passed.
- Sprint 0, Sprint 1, and Sprint 2 acceptance evidence: PASS.

## Golden Truth and Dataset

- Dataset version `1.0.0` contains 27 accepted, hash-validated statue meshes.
- Source, metadata, thumbnails, generated artifacts, schema fingerprints, and deterministic production evidence are integrity-checked.
- Future comparisons must preserve deterministic topology, diagnostics, repair/audit outcomes, schemas, versions, and hashes unless a reviewed versioned baseline change is approved.

## Scope and Safety

- No production runtime modifications.
- No repair modifications.
- No algorithm changes or optimizations.
- Sprint 3 remains unstarted.
- The protected source and repair-safety contract remain unchanged.

## Known Limitations

- Timings are reference evidence for the recorded Windows/Blender version, power state, and one-fresh-process-per-mesh execution model; they are not universal performance guarantees.
- Peak memory is a Windows process high-water mark sampled at phase boundaries, not an allocator trace.
- The baseline uses Standard diagnostics; Deep self-intersection heuristics are outside Sprint 2.6.
- Automated real-statue execution does not replace operator-reviewed visual UAT or guarantee printability.
- Stored diagnostic warnings are evidence and are not benchmark execution failures.
