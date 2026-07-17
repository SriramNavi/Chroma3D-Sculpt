# Project Rules

## Foundation

- Repository root: `E:\VPRS\Sriram\Projects\Chroma3D Sculpt`.
- Primary platform: Windows 11 without administrator privileges.
- Minimum runtime: Blender 4.4.0 and bundled Python; current validation is Blender 4.4.3.
- Package: modern Blender Extension; manifest `0.2.0`, display `0.2.0-alpha.1`, JSON schema `2.0`.
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

## Runtime safety

- No repair, deletion, winding change, transform application, modifier evaluation, file save, network, telemetry, credentials, server, external service, AI API, downloaded code, `eval`, or `exec`.
- Catch memory and Blender-context failures and preserve `FAILED` rather than inventing zero findings.
- Avoid recursion, quadratic mesh passes, per-element logging, persistent handlers, and retained temporary BMesh/BVH data.

## Regression and release

- Preserve all 12 Sprint 0 Blender tests and the historical Sprint 0 report.
- Run compilation, all Blender tests, Sprint 0 regression acceptance, Sprint 1 acceptance, repository package validation, Blender-native validation, security scan, `git diff --check`, and final diff review.
- Generated reports/logs/screenshots/artifacts and ZIPs stay ignored. Track acceptance runners and the human Sprint 1 result.
- Do not commit, push, tag, publish, reset, clean, or discard local changes unless explicitly requested.

## Token and context policy

Inspect narrowly, maintain a concise phase ledger, prefer targeted symbol searches and diffs, avoid repeated file dumps, and report actual evidence plus anything not run.
