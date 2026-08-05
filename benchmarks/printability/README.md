# Printability Baseline 1.0.0

Sprint 4 implements a validated, versioned software-regression baseline. The
canonical manifest is `baseline_manifest.json`; per-model records are under
`records/`. Generated dashboard HTML, comparison output, and working baselines
remain ignored.

The baseline binds Dataset `1.0.0`, Golden Benchmark `1.0.0`, software
`0.5.0-alpha.1`, hardware/material/process context, feature flags,
implementation fingerprint, source hashes, check states, bridge/support/resin
evidence, scale interval, orientation ranking, timings, and limitations.
`SKIPPED_LIMIT`, `NOT_EVALUATED`, `INDETERMINATE`, and `FAILED` remain
first-class states.

The schema under `schemas/` references the repository schema. Large meshes,
photos, slicer exports, logs, and raw engine reports remain external artifacts
addressed by hash/path; they are not embedded in ordinary Git history.

Run the generator inside Blender, the standalone verifier with Python, and the
comparator/dashboard tools inside Blender. This baseline is not physically
calibrated; physical status remains `READY FOR PHYSICAL EXECUTION`.
