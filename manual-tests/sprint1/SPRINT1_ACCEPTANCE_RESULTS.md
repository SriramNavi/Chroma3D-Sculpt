# Chroma3D Sculpt Sprint 1 Acceptance Results

## 1. Overall Result

**PASS**

## 2. Environment

- Repository: `E:\VPRS\Sriram\Projects\Chroma3D Sculpt`
- Branch: `feature/sprint-4-advanced-print-preparation`
- Baseline tag: `v0.1.0-alpha.1`
- Blender: `4.4.3` at `D:\Softwares\Design\Blender\blender.exe`
- Python launcher: `C:\Users\sriram\AppData\Local\Programs\Python\Python312\python.exe`
- Version: `0.5.0-alpha.1`

## 3. Git Baseline

- Main baseline: `de0e47f4d6625ccf85e5792aa2cfea16fc4517d0`
- Tag preserved: `v0.1.0-alpha.1`

## 4. Version

- Extension: `0.5.0-alpha.1`
- JSON schema: `2.0`

## 5. Gate Summary Table

| Gate | Result | Duration |
|---|---|---:|
| S1-01 - Sprint 0 regression | PASS | 0.002s |
| S1-02 - Topological watertightness | PASS | 0.012s |
| S1-03 - Physical metrics | PASS | 0.004s |
| S1-04 - Orientation | PASS | 0.008s |
| S1-05 - Shell classification | PASS | 0.006s |
| S1-06 - Internal-shell heuristic | PASS | 0.012s |
| S1-07 - Self-intersection candidates | PASS | 0.008s |
| S1-08 - Build-volume checks | PASS | 0.009s |
| S1-09 - Issue selection | PASS | 0.005s |
| S1-10 - Standard stress test | PASS | 110.499s |
| S1-11 - Deep bounded diagnostics | PASS | 0.009s |
| S1-12 - Report and package | PASS | 0.007s |

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
- Standard duration: `13420.552200012025` ms versus Sprint 0 evidence `5377.0` ms.
- Timings: `{"object_metadata": 1042.4339000019245, "geometry_metrics": 2120.5782999895746, "base_topology": 3198.78360000439, "edge_manifold_classification": 161.37849999358878, "topology_defects": 1750.924899999518, "vertex_manifold_classification": 1848.0009999912, "shell_decomposition": 200.10239999101032, "orientation_consistency": 161.37849999358878, "duplicate_position_detection": 2157.264800000121, "surface_area": 126.61540000408422, "volume": 255.87620001169853, "shell_metrics": 446.62240000616293, "tiny_shell_classification": 0.97490000189282, "build_volume_evaluation": 0.039699996705166996, "self_intersection_candidate_detection": 0.0, "containment_analysis": 0.0, "total_analysis": 13420.552200012025}`

## 14. Immutability Evidence

- Stress geometry unchanged: `True`; issue selection unchanged: `True`.

## 15. Sprint 0 Regression

- Blender tests exit: `0`; Sprint 0 acceptance exit: `0`.

## 16. Package Validation

- Package: `E:\VPRS\Sriram\Projects\Chroma3D Sculpt\dist\chroma3d_sculpt-0.3.0-alpha.1.zip`
- SHA-256: `ec375cb0ce9ec659197091980fa8d641f54853a0fbb3f91b2d82131d59fb15d9`
- Size: `79072` bytes.

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
