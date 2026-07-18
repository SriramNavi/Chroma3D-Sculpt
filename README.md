# Chroma3D Sculpt

Chroma3D Sculpt is a local Blender extension for production mesh diagnostics and controlled, reversible repair of complex statue meshes. Sprint 2 preserves the original source and performs every approved geometry change on an independent repair workspace copy.

**Current status:** Sprint 2 accepted by automated Blender gates; installed-panel and real-statue UAT remain deferred

**Version:** 0.3.0-alpha.1

**JSON schema:** 2.0

**Repair audit schema:** 1.0

**Minimum Blender:** 4.4.0

**Validated runtime:** Blender 4.4.3 on Windows 11

**Future target:** Blender 4.5 LTS and newer

## Diagnostics

Standard profile runs the practical deterministic checks used for routine review:

- Exact loose, boundary, two-face manifold, and high-incidence edge classification.
- Vertex face-fan manifold anomalies, face-connected shells, and object/per-shell topological watertightness.
- World-space dimensions, surface area, and reliable closed-shell volume in millimetres.
- Shared-edge orientation consistency and closed-shell outward/inward state.
- Deterministic main shell, combined-criteria tiny-shell candidates, and neutral disconnected external-shell classification.
- Optional Bambu Lab X1 Carbon or custom rectangular build-volume evaluation in the current orientation.
- Bounded issue evidence, per-check status, timing, settings snapshot, analysis ID, and topology signature.

Deep profile includes Standard plus bounded BVH self-intersection candidates and closed-shell containment heuristics. Deep checks report `COMPLETED`, `SKIPPED`, `FAILED`, or `NOT_APPLICABLE`; a skipped check never appears as a successful zero-result check.

`Topologically watertight` means the required topology checks completed and the analyzed original mesh has closed face shells with no boundary, loose, high-incidence, or detected vertex-manifold anomaly. It is not a printability, wall-thickness, leak-proofing, or manufacturing guarantee.

Volume is reported as reliable only for closed, orientation-consistent shells. Surface area is world-space triangle area. Object transforms and scene scale are respected without applying transforms. Modifier output is not analyzed.

Shell classifications are `MAIN_SHELL`, `DISCONNECTED_EXTERNAL`, and Deep-only `POSSIBLY_INTERNAL`. Tiny shells and possible internal shells are review candidates, not guaranteed defects. Self-intersection findings are candidate face pairs produced by Blender's BVH overlap API after shared-topology filtering.

## Safe Repair

Safe Repair is an explicit, synchronous workflow:

1. Start a repair session from a valid mesh. Chroma3D copies the object and mesh datablock, preserves transforms, materials, modifiers, and visibility, and leaves the original visible and unchanged.
2. Generate a read-only repair plan tied to the current source signature, workspace signature, analysis ID, and immutable settings snapshot.
3. Review and explicitly apply supported operations: nearby duplicate merge, zero-length edge collapse, degenerate-face removal, loose-geometry removal, face-normal consistency, outward orientation of valid closed shells, selected tiny-shell removal, and selected bounded small-hole filling.
4. A separate mesh checkpoint is created before every operation. Use **Undo Last Repair** or **Restore Workspace to Start** when needed.
5. Review the post-repair diagnostics and before/after issue deltas.
6. Accept the repaired copy without replacing the source, or roll back and discard only the workspace. Export the schema 1.0 repair audit at any point.

Tiny-shell deletion and hole filling are never preselected. Normal changes require explicit selection. Stale plans, changed sources, changed workspaces, invalid candidate mappings, main-shell deletion, and oversized or unsafe holes are rejected.

## Repair Safety

All geometry-changing behavior is governed by the authoritative [Repair Safety Contract](REPAIR_SAFETY.md).

## Blender panel

Open **3D Viewport > Sidebar > Chroma3D > Chroma3D Sculpt**.

1. Select Standard or Deep.
2. Optionally select **Bambu Lab X1 Carbon** (256 × 256 × 256 mm) or enter a Custom build volume.
3. Select an active mesh in Object Mode and choose **Analyze Mesh**.
4. Review topology, physical metrics, shells, Deep states, build-volume fit, issue counts, and timings.
5. Use an issue-selection button to inspect stored vertex, edge, or face evidence in Edit Mode.
6. Choose **Export JSON Report** for a UTF-8 schema 2.0 report.
7. Expand **Safe Repair** to create, plan, apply, recover, compare, finalize, and export a repair audit.

Issue selection is the only intentional state-changing Sprint 1 action. It changes selection/mode for inspection but never changes geometry. If topology changed after analysis it refuses with `Analysis is stale. Run Analyze Mesh again.`

## Build, test, and acceptance

From the repository root:

```powershell
Set-Location "E:\VPRS\Sriram\Projects\Chroma3D Sculpt"
py -m compileall -q blender_addon scripts tests manual-tests
py scripts\run_blender_tests.py --blender "D:\Softwares\Design\Blender\blender.exe"
py manual-tests\run_acceptance_gates.py --blender "D:\Softwares\Design\Blender\blender.exe"
py manual-tests\sprint1\run_sprint1_acceptance.py --blender "D:\Softwares\Design\Blender\blender.exe"
py manual-tests\sprint1-final\run_final_validation.py --blender "D:\Softwares\Design\Blender\blender.exe"
py manual-tests\sprint2\run_sprint2_acceptance.py --blender "D:\Softwares\Design\Blender\blender.exe"
py scripts\package_extension.py
py scripts\validate_package.py
& "D:\Softwares\Design\Blender\blender.exe" --background --command extension validate "E:\VPRS\Sriram\Projects\Chroma3D Sculpt\dist\chroma3d_sculpt-0.3.0-alpha.1.zip"
```

The installable archive is `dist\chroma3d_sculpt-0.3.0-alpha.1.zip`. Install it through Blender's **Edit > Preferences > Extensions > Install from Disk**, then enable the extension if prompted.

The background suite preserves all Sprint 0 and Sprint 1 tests and adds 56 focused Sprint 2 tests. Sprint 2 evidence is generated under `manual-tests\sprint2`; generated JSON/log folders and ZIP files remain ignored.

## Known limitations and safety

- Modifier output, wall thickness, support clearances, purge zones, and optimal print orientation are not evaluated.
- Self-intersection results are candidates; containment is a bounded heuristic with confidence evidence.
- Build-volume evaluation is rectangular, current-orientation only, and performs no rotation or scaling.
- The original source is preserved, but repaired workspace copies still require human review.
- An unfinished repair session is session-only and is not guaranteed to survive Blender restart or extension reload.
- There is no remeshing, large-hole reconstruction, Boolean repair, wall-thickness repair, decimation, object joining, modifier application, automatic scaling, or print support generation.
- Printability and manufacturing success are not guaranteed.
- Manual interactive installed-panel testing, Blender 4.5 LTS validation, and real Chroma3D statue repair UAT remain deferred.
- Runtime code is offline and uses only Blender APIs plus Python's standard library. It contains no AI API, telemetry, credentials, server, downloaded code, arbitrary `eval`/`exec`, or external package.

Runtime paths are derived from Blender APIs and package-relative files. Windows paths containing spaces are supported.
