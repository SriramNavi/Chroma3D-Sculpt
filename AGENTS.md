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
- Keep UI, operators, analysis services, typed models, and development tooling separate.
- Use typed modular Python and `pathlib`; support Windows paths containing spaces.
- Avoid hard-coded absolute paths, wildcard imports, hidden registration, and circular imports.
- Run relevant validations before completion. Report files changed, commands run, failures, and tests not run.
- Never commit secrets, `.env` files, generated archives, or Python bytecode.

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

