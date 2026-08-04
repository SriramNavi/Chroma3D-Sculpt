# Thin-Feature Method Contract

## Why this is separate

Wall thickness describes material between opposing surfaces. A finger, crown
spike, hair strand, ornament stem, weapon edge, or jewelry link may be a solid
protrusion whose failure risk is dominated by local diameter, length, exposure,
orientation, and support rather than two broad parallel walls. Sprint 3 must
not report a wall sample as proof that a thin protrusion is safe.

## Sprint 3 target

The first implementation targets an explainable geometric proxy:

- identify candidate feature regions from connected surface neighborhoods,
  local cross-sections, high-curvature/branch-like transitions, and bounded
  user-selected evidence;
- estimate a local minimum diameter or radius in a plane approximately normal
  to the feature direction;
- record feature length, local diameter/radius, direction, shell ID, exposed
  surface area, and distance to the nearest connected support mass;
- evaluate the estimate against profile warning and critical minimum-feature
  thresholds; and
- label the result `EXPERIMENTAL` until calibrated against known fixtures and
  real prints.

This is a proxy, not semantic recognition. It must not claim to know that a
region is a finger, hair strand, or weapon without user metadata.

## Deferred alternatives

Medial-axis extraction, robust shape-diameter fields, full cross-section sweep,
feature recognition, slicer toolpath inspection, support generation, and
material-strength modeling remain alternatives or future work. The research
method in SRC-011 is useful background but does not make a particular proxy
exact for Chroma3D statue meshes.

## Classification

- Below the profile critical diameter: `CRITICAL` risk item.
- At or below the warning diameter and above critical: `WARNING` risk item.
- No valid cross-section, ambiguous branch, open region, or limit: `INDETERMINATE`
  or `SKIPPED_LIMIT`, never `PASS` with zero risk.
- Adequate geometry above thresholds: `PASS` for this proxy only.

Thresholds are measured in `mm`, are profile-dependent, and remain
user-editable. Height-to-diameter ratio, unsupported orientation, material,
layer height, post-processing, and support assumptions must appear in the
limitations when not modeled.

## Evidence and outputs

Return attempted/completed/skipped candidate counts, minimum and percentile
diameters, warning/critical feature counts, largest affected region, bounded
feature IDs, center/axis endpoints, confidence, evidence state, duration,
limits, and limitations. Evidence is selectable only while all current
signatures match.
