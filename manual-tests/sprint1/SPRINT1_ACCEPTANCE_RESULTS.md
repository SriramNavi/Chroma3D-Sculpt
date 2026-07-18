# Chroma3D Sculpt Sprint 1 Acceptance Results

## 1. Overall Result

**PASS**

## 2. Environment

- Repository: `E:\VPRS\Sriram\Projects\Chroma3D Sculpt`
- Branch: `feature/sprint-2-safe-mesh-repair`
- Baseline tag: `v0.1.0-alpha.1`
- Blender: `4.4.3` at `D:\Softwares\Design\Blender\blender.exe`
- Python launcher: `C:\Users\sriram\AppData\Local\Programs\Python\Python312\python.exe`
- Version: `0.3.0-alpha.1`

## 3. Git Baseline

- Main baseline: `de0e47f4d6625ccf85e5792aa2cfea16fc4517d0`
- Tag preserved: `v0.1.0-alpha.1`

## 4. Version

- Extension: `0.3.0-alpha.1`
- JSON schema: `2.0`

## 5. Gate Summary Table

| Gate | Result | Duration |
|---|---|---:|
| S1-01 - Sprint 0 regression | PASS | 0.002s |
| S1-02 - Topological watertightness | PASS | 0.011s |
| S1-03 - Physical metrics | PASS | 0.005s |
| S1-04 - Orientation | PASS | 0.010s |
| S1-05 - Shell classification | PASS | 0.007s |
| S1-06 - Internal-shell heuristic | PASS | 0.015s |
| S1-07 - Self-intersection candidates | PASS | 0.009s |
| S1-08 - Build-volume checks | PASS | 0.010s |
| S1-09 - Issue selection | PASS | 0.004s |
| S1-10 - Standard stress test | PASS | 110.053s |
| S1-11 - Deep bounded diagnostics | PASS | 0.007s |
| S1-12 - Report and package | PASS | 0.006s |

## 6. Topology Results

- Closed: `TOPOLOGICALLY_WATERTIGHT`; open: `NOT_WATERTIGHT`; high-incidence edges: `1`.

## 7. Physical Metric Evidence

- Cube area: `24000000.0` mm^2; cube volume: `7999999999.999999` mm^3.
- Non-uniform scale dimensions: `[4000.0, 6000.0, 8000.0]`; volume: `192000000000.0` mm^3.

## 8. Orientation Evidence

- `{"outward": "OUTWARD", "inward": "INWARD", "one_reversed_face": "INCONSISTENT", "geometry_unchanged": true}`

## 9. Shell-Classification Evidence

- `{"shell_count": 2, "main_shell_id": 0, "tiny_shell_ids": [1], "medium_external_ids": [1]}`

## 10. Deep Diagnostic Evidence

- Containment: `{"internal_ids": [1], "confidence": "HIGH", "votes": [3, 3], "outside_internal_ids": [], "overlap_internal_ids": [], "limit_status": "SKIPPED"}`
- Self-intersection: `{"intersecting_candidates": 4, "stored_pairs": [[0, 8]], "truncated": true, "separate_state": "NO_CANDIDATES_DETECTED", "limit_state": "SKIPPED_LIMIT"}`

## 11. Build-Volume Evidence

- Bambu pass state: `FITS`; one-axis state: `DOES_NOT_FIT`; custom state: `FITS`.

## 12. Issue-Selection Evidence

- `{"operator_result": ["FINISHED"], "selected_mode": "EDIT", "geometry_unchanged": true, "transform_unchanged": true, "stale_rejected": true}`

## 13. Stress-Test Performance

- V/E/F/T: `146968/293888/146950/293876`; shells: `15`.
- Standard duration: `12547.673500004748` ms versus Sprint 0 evidence `5377.0` ms.
- Timings: `{"object_metadata": 1012.2736999983317, "geometry_metrics": 2058.063600001333, "base_topology": 2809.625699999742, "edge_manifold_classification": 150.57629999500932, "topology_defects": 1700.1641999959247, "vertex_manifold_classification": 1790.0493999986793, "shell_decomposition": 168.9022000064142, "orientation_consistency": 150.57629999500932, "duplicate_position_detection": 2069.58719999966, "surface_area": 112.15860000083921, "volume": 216.7362000036519, "shell_metrics": 367.8654000032111, "tiny_shell_classification": 0.5098999972688034, "build_volume_evaluation": 0.031299998227041215, "self_intersection_candidate_detection": 0.0, "containment_analysis": 0.0, "total_analysis": 12547.673500004748}`

## 14. Immutability Evidence

- Stress geometry unchanged: `True`; issue selection unchanged: `True`.

## 15. Sprint 0 Regression

- Blender tests exit: `0`; Sprint 0 acceptance exit: `0`.

## 16. Package Validation

- Package: `E:\VPRS\Sriram\Projects\Chroma3D Sculpt\dist\chroma3d_sculpt-0.3.0-alpha.1.zip`
- SHA-256: `b4434241a409f4e0c7e1a2e0a1d9c82f1150cd99588f4101bdbc7b0817f4b0cb`
- Size: `78909` bytes.

## 17. Defects Found and Fixed

- Production review: per-shell watertightness initially reused capped vertex-anomaly evidence. The topology service now retains the complete anomaly set internally while serialized and selectable evidence remains bounded; the 48-test suite and all acceptance gates passed after the fix.
- Acceptance hygiene: Markdown hard-break trailing spaces caused git diff --check and the nested Sprint 0 validation gate to fail. README formatting was corrected; the focused whitespace check and complete acceptance rerun passed.

## 18. Tests Not Run

- Interactive visual smoke test of the Blender sidebar panel.
- Blender 4.5 LTS compatibility run because only Blender 4.4.3 is installed for this task.

## 19. Known Limitations

- Modifier output is not analyzed.
- Self-intersection results are candidates.
- Internal-shell classification is heuristic.
- Wall thickness and repair are not implemented.
- Printability is not guaranteed.

## 20. Safety Confirmation

- No geometry repair, network, external dependency, credential, elevation, commit, push, or Sprint 2 work was used.

## 21. Sprint 1 Gate Decision

**SPRINT 1 ACCEPTED**

## 22. One Immediate Recommended Action

Review the Sprint 1 evidence and manually smoke-test the updated Blender panel before committing.
