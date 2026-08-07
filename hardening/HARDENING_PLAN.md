# Version 1.0 Hardening Plan

## H0 baseline boundary

H0 records the product, package, tests, retained datasets, performance signals, resource lifecycle, filesystem writes, security boundaries, documentation drift, and public contracts at `v0.8.0-pre-hardening-backup`. Runtime files, existing tests, schemas, profiles, thresholds, versions, and historical evidence are immutable during H0.

## Later phase sequence

| Phase | Candidate scope | Required comparison before acceptance |
| --- | --- | --- |
| H1 | Proven dead or obsolete code | Symbol evidence, public contract, combined regression, package inventory |
| H2 | Dependency and registration consolidation | Dependency graph, registration lifecycle, public IDs |
| H3 | Blender ownership and cleanup | Protected-source signature, checkpoints, lifecycle counts |
| H4 | Evidence and serialization consistency | Schema versions, status enums, retained historical evidence |
| H5 | Measured performance work | Same fixture/mode/input, median runs, correctness gates |
| H6 | Package footprint | Exact member diff, native validation, installed smoke |
| H7 | Documentation and UI consistency | Runtime truth, operator/property IDs, accessibility/manual review |
| H8 | Compatibility hardening | Supported Blender matrix and migration evidence |
| H9 | Version 1.0 qualification | All H0 invariants, full release gates, manual/provider/physical boundaries |

Each later phase starts from a reviewed queue item, uses a narrow diff against the backup tag, preserves first-failure evidence, and stops when an invariant fails. H1 is not started by H0.
