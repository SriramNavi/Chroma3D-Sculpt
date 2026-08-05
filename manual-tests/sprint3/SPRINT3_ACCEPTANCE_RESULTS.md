# Sprint 3 Acceptance Results

## 1. Overall result

**SPRINT 3 ACCEPTED**

## 2. Environment and baseline

- Repository: `E:\VPRS\Sriram\Projects\Chroma3D Sculpt`
- Branch: `feature/sprint-4-advanced-print-preparation`
- Baseline: `c4bccfe4970f08171c7cb767d70c30c524600adf`
- Blender path: `D:\Softwares\Design\Blender\blender.exe`
- Blender: 4.4.3
- Python: 3.11.11
- Extension: 0.5.0-alpha.1
- Analysis / repair / printability schemas: 2.0 / 1.0 / 1.0.0
- Dataset / Golden Benchmark: 1.0.0 / 1.0.0

## 3. Feature summary

Profile-driven geometry facts, bounded wall/feature/overhang/floating/contact/scale checks, virtual orientations, conservative scoring, stale-safe evidence, and JSON/Markdown reports are implemented without geometry or transform mutation.

## 4. Acceptance gates

| Gate | Result | Evidence |
|---|---|---|
| S3-01 | PASS | Combined Sprint 0/1/2/3 suite passed 368 tests; analysis remains read-only. |
| S3-02 | PASS | 5 packaged profiles and custom validation passed. |
| S3-03 | PASS | Known wall thickness, open-surface honesty, bounds, and immutability passed. |
| S3-04 | PASS | Experimental connected-shell feature proxy boundaries and evidence caps passed. |
| S3-05 | PASS | 0/30/45/60/90 convention, area, regions, and build-direction behavior passed. |
| S3-06 | PASS | Contacting and suspended shells plus neutral wording passed. |
| S3-07 | PASS | Broad, multi-region, edge/partial, point, and no-contact states passed. |
| S3-08 | PASS | Axis fit, margin, uniform scale, consequence warnings, and no transform passed. |
| S3-09 | PASS | Bounded deterministic virtual candidates and no automatic rotation passed. |
| S3-10 | PASS | Weights, critical cap, missing/skipped/failed behavior, confidence, and determinism passed. |
| S3-11 | PASS | JSON/Markdown, bounded evidence, safe names, and stale rejection passed. |
| S3-12 | PASS | Mode limits, explicit skip behavior, isolated per-mesh runtime bounds, progress, and source immutability passed; peak working set was not sampled. |
| S3-13 | PASS | Dataset regression status: PASS (27/27). |
| S3-14 | PASS | Security/safety scan: PASS. |
| S3-15 | PASS | Package validation: PASS. |

## 5. Regression and fixture evidence

- Combined Sprint 0/1/2/3 tests: 368 run; 0 failures; 0 errors; per-file counts `{'test_mesh_analysis.py': 12, 'test_sprint1_diagnostics.py': 39, 'test_sprint2_repair.py': 59, 'test_sprint3_printability.py': 121, 'test_sprint4_advanced_preparation.py': 137}`.
- Known 2.0 mm hollow-wall, 0.4 mm thin-wall/stem, open-surface, exact overhang-angle, suspended-shell, broad/multi/edge/point/no-contact, overflow/scale, deterministic orientation, scoring, stale-state, and report fixtures are covered by the production-path Blender suite.
- Existing analysis schema 2.0 and repair audit schema 1.0 remain unchanged.

## 6. Wall-thickness evidence

- 2.0 mm hollow / 0.4 mm thin minimums: `1.999999238014221` / `0.39999998903274536` mm; open surface: `INDETERMINATE`.

## 7. Thin-feature evidence

- Thin stem state / minimum diameter proxy: `CRITICAL` / `0.3999999761581421` mm.
- EXPERIMENTAL: local diameter is approximated by the minimum bounding dimension of rod-like elongated connected shells.

## 8. Overhang evidence

- Upward is `None` (not evaluated), vertical is `None` (neutral/not downward), and downward horizontal is `0.0` degrees.
- 30 / 45 / 60 degree ramp truth: `30.000001781168113` / `45.00000098057549` / `60.00000000000001`; regions, areas, and build direction passed.

## 9. Floating-component evidence

- Suspended fixture state / shell evidence: `WARNING` / `[1]`.

## 10. Contact evidence

- Broad / multi / partial / edge / point / none: `BROAD_CONTACT` / `MULTI_REGION_CONTACT` / `PARTIAL_FACE_CONTACT` / `EDGE_CONTACT` / `POINT_CONTACT` / `NO_CONTACT`.

## 11. Scale and build-volume evidence

- Oversize fit / advisory uniform fit: `False` / `66.0` percent; consequences `['Scaling down to fit may move sampled wall thickness below the configured warning threshold.']`.

## 12. Orientation evidence

- Candidate count / sources / scores: `4` / `['PRINCIPAL_AXIS', 'CURRENT', 'BOUNDING_BOX_AXIS', 'PRINCIPAL_AXIS']` / `[93.99, 93.99, 93.99, 93.99]`.

## 13. Scoring evidence

- Synthetic cube: `{"category_scores": {"build_plate_contact": 10.0, "build_volume": 10.0, "floating_components": 15.0, "orientation": 10.0, "overhangs": 15.0, "topology_readiness": 15.0, "wall_thickness": 15.0}, "confidence": "UNKNOWN", "coverage_percent": 90.0, "critical_reasons": [], "failed_checks": [], "missing_checks": [{"check": "thin_features", "reason": "The Sprint 3 conservative proxy evaluates rod-like elongated connected shells only; flat plates, walls, and local features merged into a larger shell remain unsupported.; Medial-axis, semantic feature recognition, strength, material, support, and slicer toolpaths are not evaluated.", "state": "NOT_EVALUATED"}], "score": 95, "scoring_policy_version": "1.0.0", "skipped_checks": [], "status": "INDETERMINATE"}`

## 14. Report and stale-state evidence

- Geometry/transform/profile/settings stale rejection and JSON/Markdown UTF-8 round-trip passed in the combined suite.
- Synthetic source immutability: `True`.

## 15. Profiles

- Validated: generic_fdm, generic_resin, bambu_x1_carbon, bambu_p1s, prusa_mk4 plus Custom profile validation.
- Manufacturer build-volume facts remain source-classified; wall, feature, and overhang values remain labeled project defaults, heuristics, or user-configurable values.
- Profile evidence: `[{'profile_id': 'generic_fdm', 'process_type': 'FDM', 'source_classification': 'PROJECT_DEFAULT', 'build_volume_source_references': [], 'profile_hash': '71c71d7f39e49fa66ef1d2dd4c164a73040f0c6ed57ee33fc2b17b91db725065'}, {'profile_id': 'generic_resin', 'process_type': 'RESIN', 'source_classification': 'PROJECT_DEFAULT', 'build_volume_source_references': [], 'profile_hash': '3923ced424335f5321d745a90ca36b74d1e97f3dcfb27fa4a6cd911bda6e931a'}, {'profile_id': 'bambu_x1_carbon', 'process_type': 'FDM', 'source_classification': 'MANUFACTURER_SPECIFIC', 'build_volume_source_references': ['SRC-003'], 'profile_hash': 'acef11685d1140b3115c6ae9be081d3aa17f7e4ad5b320b43ccb6bae8383635e'}, {'profile_id': 'bambu_p1s', 'process_type': 'FDM', 'source_classification': 'MANUFACTURER_SPECIFIC', 'build_volume_source_references': ['SRC-004', 'SRC-005'], 'profile_hash': '5473f58fbf9f3ba1bbbef374d3b606edf43e679c4efc3bffa5179f310c6daed0'}, {'profile_id': 'prusa_mk4', 'process_type': 'FDM', 'source_classification': 'MANUFACTURER_SPECIFIC', 'build_volume_source_references': ['SRC-008'], 'profile_hash': 'faf4aaa5fd999b0261117cd0ac4da7d2c10e7147e7b3e909c21981aee4c993e5'}]`

## 16. Dataset regression

- Status: PASS
- Available/completed meshes: 27 / 27
- Failures: 0
- Skipped/indeterminate checks: 88
- Check-state / score-status counts: `{'dataset_mode': 'FAST', 'check_state_counts': {'CRITICAL': 9, 'INDETERMINATE': 7, 'NOT_EVALUATED': 5, 'PASS': 31, 'SKIPPED_LIMIT': 76, 'WARNING': 88}, 'score_status_counts': {'CRITICAL': 2, 'INDETERMINATE': 7, 'WARNING': 18}}`
- Source immutability: True

## 17. Performance

- Dataset timings retained: 27
- Dataset FAST minimum / median / p95 / maximum seconds: `1.482427100003406` / `42.820314399999916` / `244.0866862000039` / `359.93002340000385`.
- Synthetic fixture timings: `{'cube': 0.002736399997957051, 'hollow_2mm': 0.003570200002286583, 'thin_0_4mm': 0.0022861999896122143, 'floating': 0.0036306999973021448, 'oversize': 0.00239280000096187}`.
- FAST/STANDARD/DEEP sample, triangle, candidate, and evidence caps are enforced; skipped limits remain explicit.
- Memory: Maximum external Get-Process checkpoint observed during the first isolated Dataset 1.0.0 FAST pass. This is a point observation, not a continuously sampled peak.

## 18. Package and security

- Package: PASS — `E:\VPRS\Sriram\Projects\Chroma3D Sculpt\dist\chroma3d_sculpt-0.5.0-alpha.1.zip`
- Files / size / SHA-256: 104 / 197280 / `7b43fb2fdb5c4a0adf565ecfc40911e816dcc43e2feafd02de8e3cbe91f11cae`
- Compile / whitespace / Blender-native validator: `True` / `0` / `0`.
- Security: PASS

## 19. Defects found and fixed

- Product defect: build-plate contact faces were initially counted as unsupported downward overhang; the overhang and virtual-orientation evaluators now exclude coplanar plate-contact faces, with fixture coverage.
- Harness defect: Blender float32 normals exceeded an overly strict micro-degree assertion; truth-angle tests now use the repository's established physical float tolerance.
- Harness defect: a monolithic 27-mesh Blender process could time out without flushing evidence; isolated bounded workers now retain atomic resumable results per source and implementation hash.
- Harness compatibility defect: Sprint 1-final pinned exactly two diagnostic mode transitions and version 0.3.0; it now permits only the two diagnostic plus two Printability selector transitions and verifies manifest/imported version consistency.
- Harness compatibility defect: Sprint 2-final pinned the 0.3.0 package/report version; it now discovers the current package version while keeping analysis schema 2.0 and repair audit schema 1.0 frozen.
- Harness defect: rotated-solid contact fixtures allowed partial-face classifications for intended edge/point cases; exact loose-edge and loose-vertex fixtures now prove EDGE_CONTACT and POINT_CONTACT.

## 20. Evidence paths

- Machine JSON: `manual-tests\sprint3\reports\sprint3_acceptance_results.json`
- Markdown: `manual-tests\sprint3\SPRINT3_ACCEPTANCE_RESULTS.md`
- Blender log: `manual-tests/sprint3/logs/blender_sprint3_acceptance.log`
- Preserved failure log: `manual-tests/sprint3/logs/sprint3_initial_failures.log`

## 21. Tests not run

- Installed-package interactive panel smoke, Blender 4.5 LTS, slicer comparisons, retained physical FDM/resin calibration, and peak working-set sampling were not run.

## 22. Known limitations

- Advisory only; no printability guarantee, support generation, slicing, G-code, automatic rotation, or automatic scaling.
- Wall thickness is sampled/estimated; thin-feature detection is a conservative experimental connected-shell proxy.
- Stability is heuristic; orientation candidates are bounded and not guaranteed optimal; real-print calibration remains pending.
- Blender 4.5 LTS compatibility and native installed-panel manual smoke testing were not available in this automated Blender 4.4.3 run.

## 23. Safety confirmation

No geometry or transform mutation, runtime network, external dependency, credential, administrator requirement, automatic save, commit, push, merge, tag, or Sprint 4 work was introduced.

## 24. Final decision and Git state

**SPRINT 3 ACCEPTED** on branch `feature/sprint-4-advanced-print-preparation`; implementation changes remain intentionally uncommitted for review.

## Immediate next action

Review the Sprint 3 evidence and manually smoke-test the installed 0.4.0-alpha.1 Printability panel before committing the feature branch.
