# Printability Baseline Design

The proposed Printability Baseline version is `1.0.0`. It is a design only and
is **not frozen or published**. Freezing requires the independent Sprint 3
software validation to pass and the physical calibration status to be recorded
without implying that pending prints succeeded.

A future baseline binds Dataset `1.0.0` source hashes to extension/profile/
settings versions, geometry and transform signatures, per-check states,
bounded evidence summaries, score/status/confidence, timings, limitations, and
optional validated physical-run links. `SKIPPED_LIMIT`, `NOT_EVALUATED`,
`INDETERMINATE`, and `FAILED` remain first-class states.

The schema under `schemas/` describes one baseline manifest. Large meshes,
photos, slicer exports, logs, and raw engine reports remain external artifacts
addressed by hash/path; they are not embedded in ordinary Git history.
