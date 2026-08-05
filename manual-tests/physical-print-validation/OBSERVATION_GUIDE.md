# Human Observation Guide

Complete observations only after an operator has inspected the physical print.
Use `NOT_RUN` before printing and `INVALID_EXPERIMENT` when the setup cannot
support a comparison (wrong scale/material/profile, corrupted file, printer
fault unrelated to the model, or missing evidence).

## Required setup record

Record printer, nozzle, material, filament batch where available, layer height,
scale, orientation, supports/settings summary, plate, preparation, slicer and
version, estimated duration/material, start/end time, and operator identifier.

## Observable taxonomy

- Wall/feature: `PRINTED_INTACT`, `FLEXIBLE_BUT_INTACT`, `WARPED`,
  `PARTIALLY_MISSING`, `FULLY_MISSING`, `BROKEN_DURING_SUPPORT_REMOVAL`,
  `BROKEN_DURING_HANDLING`, `DIMENSION_OUTSIDE_TOLERANCE`, `NOT_MEASURABLE`.
- Overhang: `CLEAN`, `MINOR_SURFACE_DEGRADATION`, `SEVERE_DROOP`,
  `SUPPORT_REQUIRED`, `SUPPORT_FAILED`, `PRINT_DETACHED`, `INCONCLUSIVE`.
- Contact/stability: `STABLE_ADHESION`, `PARTIAL_LIFT`, `WARPING`, `DETACHED`,
  `TIPPED`, `SUPPORT_RAFT_DOMINATED`, `INCONCLUSIVE`.
- Floating component: `SUPPORTED_SUCCESSFULLY`, `UNSUPPORTED_AND_FAILED`,
  `DETACHED`, `MISSING`, `SLICER_REMOVED`, `NOT_PRINTED`, `INCONCLUSIVE`.
- Overall: `SUCCESS`, `SUCCESS_WITH_MINOR_DEFECTS`, `PARTIAL_FAILURE`,
  `FAILURE`, `INVALID_EXPERIMENT`, `NOT_RUN`.

Do not translate surface quality into a universal printability conclusion.
Distinguish engine defect, profile calibration, slicer behavior, material,
printer setup, operator error, and invalid experiment in notes.

## Photo and measurement evidence

Every completed run requires photo-manifest entries for `FRONT`, `REAR`,
`SIDE`, `PREDICTED_RISK_CLOSEUP`, and `BUILD_PLATE_BASE`. Store image binaries
under ignored `photos/<run-id>/`; record relative path, SHA-256, caption, and
capture time in observation JSON. Add caliper measurements for applicable
walls/features with nominal, observed, tolerance, and unit. Record support
removal damage separately from as-printed failure.
