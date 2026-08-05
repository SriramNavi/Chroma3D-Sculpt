# Sprint 3.5 Physical Validation Plan

## Objective and hardware

Compare Chroma3D's advisory predictions with controlled physical observations
on the available **Bambu Lab X1 Carbon Combo**, using a recorded 0.4 mm nozzle.
Material is deliberately unset until the operator records PLA, PETG, or another
specific material. Resin is out of scope.

## Stage 1 - calibration coupons

Generate four lightweight local STL packs with `generate_calibration_coupons.py`:

- walls at 0.4, 0.6, 0.8, 1.2, and 2.0 mm;
- vertical rods at 0.4, 0.6, 0.8, 1.2, and 2.0 mm diameter;
- downward ramps at 20, 30, 45, and 60 degrees under the documented convention;
- broad, edge, and point-contact solids on separate labeled bases.

Print coupons before statues. Record dimensional measurements, wall/feature
outcomes, overhang surface quality, adhesion, supports, and invalid experiments.
Bridges may be noted but are not a calibrated Sprint 3 engine category.

## Stage 2 - representative statues

The ten selected Dataset `1.0.0` models cover Tiny through Extreme complexity,
permissive redistribution licenses, broad and narrow bases, thin ornaments,
large overhangs, complex groups, museum scans, and noisy photogrammetry. Raw STL
units are unspecified, so every job remains blocked on manual unit confirmation
and explicit target scale before slicing.

Default planning values:

- printer: Bambu Lab X1 Carbon;
- nozzle: 0.4 mm;
- layer height: to be recorded (0.20 mm is a planning option, not an outcome);
- material: to be recorded;
- plate and preparation: to be recorded;
- supports: decided and recorded in the slicer for each run;
- target height: 70-120 mm by model, subject to unit and feature review.

## Stage 3 - controlled orientation comparison

Use current orientation, the top Chroma3D candidate, and the operator/slicer
choice only for high-value cases where the predicted trade-off differs. Initial
priority cases are Hercules as Archer, Laocoon Group, and Hizen Komainu. Do not
triple-print all models. Keep printer, nozzle, material, layer height, support
policy, and scale fixed inside each comparison set.

## Evidence sequence

1. Capture the current engine JSON and Markdown report.
2. Record the exact source SHA-256 and implementation signature.
3. Capture slicer settings/export or a manual screenshot summary.
4. Complete the setup checklist; no script sends printer commands.
5. After the print, complete the observation taxonomy and measurements.
6. Photograph front, rear, relevant side, predicted-risk close-up, and base.
7. Hash photos and reference them in observation JSON; do not commit binaries.
8. Validate the run, then generate comparison statistics.

## Slicer boundary

No supported slicer executable was detected in standard install locations on
2026-08-05. Slicer automation is therefore `NOT_RUN`. The operator must record
the actual Bambu Studio, OrcaSlicer, or PrusaSlicer version and capture settings
manually. These tools never install a slicer, alter user profiles, connect to a
printer, generate G-code, or send a print.

Slicer evidence is complementary evidence, not universal ground truth.
