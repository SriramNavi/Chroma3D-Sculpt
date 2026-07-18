# Project Rules

## Foundation

- Repository root: `E:\VPRS\Sriram\Projects\Chroma3D Sculpt`.
- Primary platform: Windows 11 without administrator privileges.
- Minimum runtime: Blender 4.4.0 and bundled Python; current validation is Blender 4.4.3.
- Package: modern Blender Extension; manifest `0.3.0`, display `0.3.0-alpha.1`, analysis JSON schema `2.0`, repair audit schema `1.0`.
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

- No source repair, unapproved deletion, transform application, modifier evaluation, automatic file save, network, telemetry, credentials, server, external service, AI API, downloaded code, `eval`, or `exec`.
- Catch memory and Blender-context failures and preserve `FAILED` rather than inventing zero findings.
- Avoid recursion, quadratic mesh passes, per-element logging, persistent handlers, and retained temporary BMesh/BVH data.

## Regression and release

- Preserve all Sprint 0 and Sprint 1 Blender tests and historical reports.
- Run compilation, all Blender tests, Sprint 0 acceptance, Sprint 1 acceptance, Sprint 1 final validation, Sprint 2 acceptance, repository package validation, Blender-native validation, security scan, `git diff --check`, and final diff review.
- Generated reports/logs/screenshots/artifacts and ZIPs stay ignored. Track acceptance runners and human Sprint result files.
- Do not commit, push, tag, publish, reset, clean, or discard local changes unless explicitly requested.

## Token and context policy

Inspect narrowly, maintain a concise phase ledger, prefer targeted symbol searches and diffs, avoid repeated file dumps, and report actual evidence plus anything not run.
