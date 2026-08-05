# Sprint 4 Baseline Compatibility Disposition

- Decision: **EXPECTED IDENTITY MISMATCH; NO BEHAVIORAL REGRESSION OBSERVED**
- Frozen records preserved without edits:
  - `manual-tests/sprint4-final/FINAL_VALIDATION_RESULTS.md`
  - `manual-tests/sprint4/SPRINT4_ACCEPTANCE_RESULTS.md`
- Historical independent Blender gates: `15/16 PASS`
- Combined Blender regression suite: `529/529 PASS`
- Blender: `4.4.3`
- Current extension: `0.6.0-alpha.1`

## Disposition

The one historical independent failure was `S4F-J - Baseline integrity`, which reported `Canonical implementation fingerprint is stale.` This is an expected identity mismatch: Sprint 5 changes the implementation fingerprint, runtime version, optimization schemas, and package contents. It is not evidence that the frozen Sprint 4 baseline records are equivalent to the Sprint 5 implementation, and those records were not rewritten.

The remaining historical independent gates passed, and the full combined Blender suite passed 529/529. No actual Sprint 4 behavioral regression was reproduced in the executable regression suite.

The first historical launch attempt also exposed a Windows path-quoting defect in the temporary audit launcher. It was corrected and rerun; this was a validation-launcher defect, not a product or frozen-baseline defect.

## Evidence

- Direct historical independent-run evidence: `manual-tests/sprint4-final/reports/blender_gate_results.json`
- Historical run log: `manual-tests/sprint5-final/logs/historical_sprint4_independent.log`
- Combined suite result: `scripts/run_blender_tests.py --blender D:\Softwares\Design\Blender\blender.exe` -> `529 tests`, `OK`

## Compatibility boundary

Frozen Sprint 4 identity equivalence remains **NOT CLAIMED** under the changed implementation fingerprint. Physical printing, real slicer comparison, material calibration, Blender 4.5 LTS, and manual installed-panel UAT remain outside this software-only disposition.
