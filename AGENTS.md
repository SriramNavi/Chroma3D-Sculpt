# Chroma3D Sculpt Repository Instructions

## Repository location

The repository root is `E:\VPRS\Sriram\Projects\Chroma3D Sculpt`.

- Treat this folder as the repository root; never create a nested duplicate repository.
- Do not modify files outside this folder.
- Never hard-code this path in runtime extension source. Runtime paths must come from Blender APIs, `__file__`, or `pathlib`.

## Coding rules

- Inspect relevant code before editing and preserve the documented architecture.
- Implement only the requested sprint scope; do not add speculative features.
- Add no network dependency, AI API, or external Python package without approval.
- Keep Blender operations non-destructive by default and never execute generated Python blindly.
- Treat diagnostic states honestly: skipped or failed checks must never be serialized or displayed as successful zero findings.
- Keep Standard and Deep profile limits centralized, evidence bounded, and physical metrics world-space/unit-correct.
- The explicit issue-selection operator may change selection and mode only after validating the topology signature; it must not modify geometry.
- Keep UI, operators, analysis services, typed models, and development tooling separate.
- Use typed modular Python and `pathlib`; support Windows paths containing spaces.
- Avoid hard-coded absolute paths, wildcard imports, hidden registration, and circular imports.
- Run relevant validations before completion. Report files changed, commands run, failures, and tests not run.
- Preserve Sprint 0 regressions, run Blender background tests before completion, and keep JSON schema changes explicit.
- Never commit secrets, `.env` files, generated archives, or Python bytecode.
- Never commit or push automatically.
- Never repair the protected source directly; every geometry mutation must target the independent repair workspace.
- Create a retained checkpoint before every repair operation and restore it automatically after a failure.
- Reject stale repair plans, changed source signatures, changed workspace signatures, and stale candidate mappings.
- Tiny-shell removal and hole filling require explicit candidate selection; never perform silent cleanup or auto-delete the main shell.
- Preserve safe operation ordering, bounded evidence, session cleanup, and schema 1.0 repair audit history.
- Run Sprint 0, Sprint 1, and Sprint 2 regressions before Sprint 2 completion.

## Token and context management

- Read only relevant files and do not repeatedly scan the repository.
- Use targeted filename and symbol searches, then use Git diff for review.
- Maintain a concise task ledger and work phase by phase.
- Do not repeat large requirements or dump full files in progress reports.
- Avoid duplicate documentation and speculative scope expansion.
- Keep updates concise and save coherent checkpoints before switching phases.
- Prioritize valid core functionality if an actual environmental blocker appears.
- Never sacrifice correctness merely to shorten output.
- Final reports must be concise and evidence-based.
