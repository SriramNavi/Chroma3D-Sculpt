# Project Rules

## Foundation

- Repository root: `E:\VPRS\Sriram\Projects\Chroma3D Sculpt`
- Primary platform: Windows 11 without administrator privileges.
- Minimum supported runtime: Blender 4.4 and its bundled Python.
- Current runtime validation: Blender 4.4.3 on Windows.
- Future compatibility target: Blender 4.5 LTS and newer.
- Packaging: modern Blender Extension format with `blender_manifest.toml`.
- Version: manifest `0.1.0`; product display `0.1.0-alpha.1`.
- Dependencies: Blender APIs plus the Python standard library only.
- Paths: use `pathlib`, quote subprocess arguments, and support spaces.

## Runtime rules

- Mesh work is non-destructive and read-only unless a later sprint explicitly authorizes otherwise.
- Runtime code must remain offline: no network, telemetry, credentials, dynamic code execution, servers, or external services.
- Log lifecycle, analyses, exports, and exceptions to the Blender console without duplicate handlers.
- Surface understandable errors; never suppress failures silently.
- Avoid quadratic mesh algorithms, per-element logs, persistent handlers, and unnecessary mesh copies.

## Quality and release

- Keep UI, operators, services, models, and utilities modular and dependency-directed.
- Use background Blender `unittest` fixtures for supported mesh cases.
- Validate syntax, package layout, manifest metadata, security exclusions, paths, and Git status.
- Generated ZIP files remain ignored under `dist/` and must not be committed.
- Do not commit or push unless explicitly requested.

## Token and context policy

Inspect narrowly, maintain a concise ledger, execute in phases, review with targeted diffs, and avoid repeated source or documentation dumps. Release reports must cite actual checks and disclose skipped tests.

## Release checklist

1. Verify the repository root and absence of a nested project.
2. Compile all Python sources.
3. Run Blender background tests on the supported Blender 4.4 runtime; the current validated build is Blender 4.4.3.
4. Revalidate against Blender 4.5 LTS and newer when those runtimes are available.
5. Build and validate the installable archive.
6. Scan for secrets, external networking, destructive mesh calls, and runtime absolute paths.
7. Review Git status and diff; do not stage automatically.
