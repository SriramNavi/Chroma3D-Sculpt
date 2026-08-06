# Sprint 7 Post-Merge Validator First Failure

**Classification:** validator/harness defect; no product runtime defect

## Execution context

- Pre-merge context: `feature/sprint-7-specification` passed before publication.
- Post-merge branch: `main`
- Post-merge commit: `544c4dce5c5dff42c57ccd7dd4ee8ffe54292f8e`
- Command: `py manual-tests\sprint7-specification\validate_sprint7_specification.py`
- Exit code: `1`
- Evidence file write time (UTC): `2026-08-06T17:41:00.0852722Z`
- Failure: `AssertionError: Unexpected current branch`

## Established specification counts

- Requirements: `32`
- Draft schemas: `7`
- Acceptance gates: `38` total (`20` normal and `18` independent-final)

The specification contents had already merged successfully through PR #10. The failure occurred before content counts were recomputed because the validator required the pre-merge feature branch. No Sprint 7 runtime defect was involved, and no Blender, package, dataset, historical, slicer, or physical test was implicated. This artifact preserves the first failed post-merge validation without claiming that it passed.

## Exact changed-line transcript from the dirty diff

Unchanged framing lines are omitted. Every removed and added line below is reproduced exactly from the captured dirty diff.

```text
REMOVED | **Status:** `PASS`
REMOVED | **Decision:** `SPRINT 7 SPECIFICATION ACCEPTED WITH OPEN QUESTIONS`
ADDED   | **Status:** `FAIL`
ADDED   | **Decision:** `SPRINT 7 SPECIFICATION FAILED`
REMOVED | - Requirements validated: `32`
REMOVED | - Acceptance gates validated: `38`
REMOVED | - Draft schemas parsed and audited: `7`
REMOVED | - Internal Markdown paths checked: `7`
REMOVED | - Changed paths scope-checked: `24`
ADDED   | - Requirements validated: `0`
ADDED   | - Acceptance gates validated: `0`
ADDED   | - Draft schemas parsed and audited: `0`
ADDED   | - Internal Markdown paths checked: `0`
ADDED   | - Changed paths scope-checked: `0`
REMOVED | - Extension version: `0.7.0-alpha.1`
REMOVED | - Release commit: `63f98b8cef68dc977f6bd8c17972303fa7e3d05e`
ADDED   | - Extension version: `not established`
ADDED   | - Release commit: `not established`
REMOVED | - PASS: `required_files_and_headings`
REMOVED | - PASS: `scope_non_goals_and_safety`
REMOVED | - PASS: `evidence_semantics`
REMOVED | - PASS: `state_machine`
REMOVED | - PASS: `requirements_traceability_and_gates`
REMOVED | - PASS: `draft_schemas`
REMOVED | - PASS: `markdown_paths`
REMOVED | - PASS: `git_scope_release_and_ignore`
REMOVED | - PASS: `unsupported_claims`
REMOVED | - Provider, model, backend/direct/local, BYOK/hosted, retention, cost/quota and initial execution scope remain owner decisions.
REMOVED | - No live provider, Blender runtime, dataset, package, physical print, slicer or material calibration was run for this specification milestone.
REMOVED | - Draft schemas are specification artifacts and are intentionally excluded from the extension package.
ADDED   | - AssertionError: Unexpected current branch
```
