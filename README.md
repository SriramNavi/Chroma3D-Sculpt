# Chroma3D Sculpt

Chroma3D Sculpt is a local Blender extension for read-only diagnostics of complex printable statue meshes. Sprint 1 adds production-grade topology, shell, physical-metric, spatial, build-volume, issue-evidence, and timing reports without repairing or modifying geometry.

**Current status:** Sprint 1 accepted

**Version:** 0.2.0-alpha.1

**JSON schema:** 2.0

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

## Blender panel

Open **3D Viewport > Sidebar > Chroma3D > Chroma3D Sculpt**.

1. Select Standard or Deep.
2. Optionally select **Bambu Lab X1 Carbon** (256 × 256 × 256 mm) or enter a Custom build volume.
3. Select an active mesh in Object Mode and choose **Analyze Mesh**.
4. Review topology, physical metrics, shells, Deep states, build-volume fit, issue counts, and timings.
5. Use an issue-selection button to inspect stored vertex, edge, or face evidence in Edit Mode.
6. Choose **Export JSON Report** for a UTF-8 schema 2.0 report.

Issue selection is the only intentional state-changing Sprint 1 action. It changes selection/mode for inspection but never changes geometry. If topology changed after analysis it refuses with `Analysis is stale. Run Analyze Mesh again.`

## Build, test, and acceptance

From the repository root:

```powershell
Set-Location "E:\VPRS\Sriram\Projects\Chroma3D Sculpt"
py -m compileall -q blender_addon scripts tests manual-tests
py scripts\run_blender_tests.py --blender "D:\Softwares\Design\Blender\blender.exe"
py manual-tests\run_acceptance_gates.py --blender "D:\Softwares\Design\Blender\blender.exe"
py manual-tests\sprint1\run_sprint1_acceptance.py --blender "D:\Softwares\Design\Blender\blender.exe"
py scripts\package_extension.py
py scripts\validate_package.py
& "D:\Softwares\Design\Blender\blender.exe" --background --command extension validate "E:\VPRS\Sriram\Projects\Chroma3D Sculpt\dist\chroma3d_sculpt-0.2.0-alpha.1.zip"
```

The installable archive is `dist\chroma3d_sculpt-0.2.0-alpha.1.zip`. Install it through Blender's **Edit > Preferences > Extensions > Install from Disk**, then enable the extension if prompted.

The background suite contains the preserved 12 Sprint 0 tests plus 36 Sprint 1 tests. Sprint 1 evidence is generated under `manual-tests\sprint1`; generated JSON/log folders and ZIP files remain ignored.

## Known limitations and safety

- Modifier output, wall thickness, support clearances, purge zones, and optimal print orientation are not evaluated.
- Self-intersection results are candidates; containment is a bounded heuristic with confidence evidence.
- Build-volume evaluation is rectangular, current-orientation only, and performs no rotation or scaling.
- There is no repair, hole filling, normal recalculation, Boolean operation, remeshing, decimation, deletion, joining, separation, transform application, or print support generation.
- Printability and manufacturing success are not guaranteed.
- Runtime code is offline and uses only Blender APIs plus Python's standard library. It contains no AI API, telemetry, credentials, server, downloaded code, arbitrary `eval`/`exec`, or external package.

Runtime paths are derived from Blender APIs and package-relative files. Windows paths containing spaces are supported.
