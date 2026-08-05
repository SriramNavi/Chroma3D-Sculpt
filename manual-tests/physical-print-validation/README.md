# Sprint 3.5 Physical Print Validation

This directory prepares reproducible, human-observed FDM validation for the
Bambu Lab X1 Carbon Combo. It does not claim that any print was executed or
successful. Raw meshes, photographs, slicer exports, generated coupons, job
cards, and reports remain in ignored local directories.

## Workflow

1. Confirm the validation assets with `py scripts\fetch_validation_assets.py verify`.
2. Generate calibration coupons with `py manual-tests\physical-print-validation\generate_calibration_coupons.py`.
3. Generate the ten model job cards with `py manual-tests\physical-print-validation\generate_print_job_cards.py`.
4. Record material, filament batch, plate preparation, slicer/version, scale,
   orientation, supports, and estimates before printing.
5. Never send a print from these tools. Slice and print only through an
   operator-reviewed Bambu Studio, OrcaSlicer, or PrusaSlicer workflow.
6. Create an observation JSON from the template, retain photo hashes/captions,
   then run `validate_physical_validation_data.py`.
7. Run `analyze_physical_results.py`; it separates categories and never changes
   production thresholds.

The current status is maintained in [PHYSICAL_VALIDATION_STATUS.md](PHYSICAL_VALIDATION_STATUS.md).

## Storage boundary

- `runs/`: generated job JSON/Markdown and later lightweight observation JSON.
- `photos/`: ignored local photographs; Git retains only future manifests/hashes.
- `slicer-exports/`: ignored copied settings, screenshots, and previews.
- `artifacts/`: generated calibration STL files.
- `print-packs/`: generated queue and operator folders.
- `reports/`: generated validator and comparison results.

No tool modifies Dataset `1.0.0`, production extension source, printer
profiles, slicer profiles, or a printer. Resin validation is deferred until an
actual resin printer and approved profile are supplied.
