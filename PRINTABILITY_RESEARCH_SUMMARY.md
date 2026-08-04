# Sprint 2.8 Printability Research Summary

## Outcome

The research supports a separation between geometric measurement and
process/profile evaluation. It does not support universal wall, feature, or
overhang thresholds across printers, materials, layer heights, nozzle sizes,
supports, post-processing, or part purpose. The profiles therefore keep
manufacturer build-volume and hardware facts separate from project defaults and
user-editable thresholds.

## Accepted evidence

| Topic | Accepted evidence | Specification use |
|---|---|---|
| AM terminology | ISO/ASTM 52900:2021 | Terminology only; no compliance claim |
| FDM hardware facts | Bambu X1 Carbon and P1S manufacturer specifications; Prusa MK4 knowledge base | Build volume and included nozzle facts in profile examples |
| FDM process guidance | PrusaSlicer guidance on layer height, extrusion width, perimeters, thin walls, and bridges | Explains why nozzle/layer/profile settings affect evaluations; not a universal threshold |
| Resin process guidance | Formlabs Form 4 and Form 3 design guidance; Formlabs support guidance on supports | Process-specific examples for thin walls, overhangs, supports, and deferred hollowing |
| Thickness methods | Rolland-Neviere, Doerr, and Alliez, *Robust diameter-based thickness estimation of 3D objects* | Research basis for SDF/diameter alternatives and defect limitations |
| Orientation methods | Das et al., *Selection of build orientation for optimal support structures and minimum part errors*; Gay et al., *Optimum Part Build Orientation...* | Supports multi-objective candidate evaluation; not a claim of global optimality |

## Research decisions

- Sprint 3 targets bounded surface sampling with opposing-surface searches as
  the first explainable method. Shape Diameter Function and signed-distance
  alternatives remain comparison methods, not silently interchangeable truth.
- A face-normal overhang convention is made explicit because manufacturer and
  slicer guidance use different angle references.
- Orientation is ranked using multiple measurable objectives. A candidate is a
  trade-off, not a proof of the best or safest build.
- Formlabs values remain manufacturer/process-specific examples and are not
  copied into generic FDM or generic resin profiles as guarantees.
- FDM thin-wall warnings should expose nozzle, layer height, perimeter and
  slicer assumptions because a wall below a single extrusion width can be
  ignored by a slicer.

## Gaps and rejected evidence

Unsourced blogs, community forums, marketing summaries without a test method,
and generic tables that omit printer/material/layer/support context were not
used to set thresholds. No accepted source establishes a universal threshold
for statue meshes, generic resin, support-free printing, dimensional margins,
or physical print success. Real failed/successful print calibration remains a
Sprint 3 and later validation need.

## Traceability

The full source ledger, URLs, access date, authority classification, supported
rules, and limitations are in [docs/printability/SOURCES.md](docs/printability/SOURCES.md).
