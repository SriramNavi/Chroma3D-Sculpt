# Sprint 6 Historical Regression Evidence

- Status: **PASS_WITH_LIMITATIONS**
- Release-input SHA-256: `3ce3cd1d8eb74fc7b3f57e446227fcf54ddb38052aca4ca983e5542c99f5cdbb`
- Blender: `4.4.3`
- Sprint 6 implementation fingerprint: `sprint6-intelligent-optimization-1.2-verification`

| Layer | Result | Duration | Release safety |
|---|---|---:|---|
| H1 Sprint 0 acceptance | PASS | 121.065s | cleared |
| H2 Sprint 1 acceptance | PASS | 236.976s | cleared |
| H3 Sprint 1 independent final | PASS | 111.246s | cleared |
| H4 Sprint 2 acceptance | PASS | 481.735s | cleared |
| H5 Sprint 2 independent final | PASS_WITH_LIMITATIONS | 1078.261s | cleared |
| H6 Sprint 3 acceptance | PASS | 6.588s | cleared |
| H7 Sprint 3 independent final | PASS_WITH_LIMITATIONS | 72.062s | cleared |
| H8 Sprint 4 acceptance | PASS | 7.096s | cleared |
| H9 Sprint 4 independent final | PASS_WITH_LIMITATIONS | 106.016s | cleared |
| H10 Sprint 5 acceptance | PASS_WITH_LIMITATIONS | 3.012s | cleared |
| H11 Sprint 5 independent final | PASS_WITH_LIMITATIONS | 33.860s | cleared |

Frozen Sprint 1-5 result documents and Sprint 4 canonical baselines are restored to `origin/main` after each layer. Detailed command logs remain ignored.

H9 retains the underlying `15/16` frozen Sprint 4 wrapper result: only `S4F-J` failed because the current implementation identity differs from the historical Sprint 4 fingerprint. The other functional, safety, package, and installation gates passed, and the frozen baseline was not changed.

## Decisive metrics

- `H1`: `{"failed_gate_count": 0, "gate_count": 9}`
- `H2`: `{"failed_gate_count": 0, "gate_count": 12}`
- `H3`: `{"failed_gate_count": 0, "gate_count": 11, "package_status": "PENDING_EXTERNAL"}`
- `H4`: `{"failed_gate_count": 0, "gate_count": 14}`
- `H5`: `{"face_count": 152978, "failed_gate_count": 0, "gate_count": 19, "installed_package_smoke": "PASS", "repair_batch_seconds": 47.498363, "source_unchanged": true, "triangle_count": 152996, "vertex_count": 76512, "warning_threshold_passed": true, "warning_threshold_seconds": 60.0}`
- `H6`: `{"errors": 0, "failed_gate_count": 0, "failures": 0, "gate_count": 15, "package_status": "PASS", "skipped": 0, "tests_run": 751}`
- `H7`: `{"failed_gate_count": 0, "gate_count": 13, "installed_package_smoke": "PASS", "package_status": "PASS", "passed_gates": 13, "total_gates": 13}`
- `H8`: `{"errors": 0, "failed_gate_count": 0, "failures": 0, "gate_count": 16, "package_status": "PASS", "passed_gates": 16, "skipped": 0, "tests_run": 751, "total_gates": 16}`
- `H9`: `{"failed_gate_count": 1, "gate_count": 16, "installed_package_smoke": "PASS", "package_status": "PASS", "passed_gates": 15, "total_gates": 16}`
- `H10`: `{"errors": 0, "failed_gate_count": 0, "failures": 0, "gate_count": 16, "package_status": "PASS", "skipped": 0, "tests_run": 161}`
- `H11`: `{"failed": 0, "failed_gate_count": 0, "gate_count": 17, "passed": 17, "source_immutability": true}`

Manual installed-panel UAT, Blender 4.5 LTS, slicer comparison, material calibration, and physical printing remain deferred.
