# Calibration and Threshold Governance

Physical evidence informs proposals; it never edits production profiles or
thresholds automatically.

## Evidence separation

Group observations by printer, nozzle, material, layer height, support policy,
profile version, slicer/version, and relevant plate preparation. Do not combine
wall, thin-feature, overhang, contact/stability, and floating-component metrics
into a single confusion matrix.

Preserve raw job cards, engine evidence, slicer evidence, observation JSON,
photo manifests/hashes, measurement records, and invalid experiments. A later
summary must remain reproducible from these records.

## Change rule

No packaged threshold change is permitted until at least three controlled,
comparable observations support the same change, unless an independently
reproduced mathematical or software defect explains the result. A single print
may open an investigation but cannot change a profile.

Every proposal must:

1. identify whether the cause is engine logic, profile calibration, slicer,
   material, printer setup, operator error, or invalid experiment;
2. preserve the prior profile, threshold, rationale, and source classification;
3. state sample count, false positives/negatives, precision/recall, confidence,
   sensitivity, affected hardware/process stratum, and counter-evidence;
4. receive explicit review/approval before any packaged profile change; and
5. add focused synthetic and physical-regression coverage when implemented.

Version proposals independently (for example `proposal-001`); do not declare
Printability Baseline `1.0.0` final until software validation passes and the
physical status is recorded truthfully.
