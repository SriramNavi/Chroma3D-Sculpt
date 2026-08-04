# Orientation Recommendation Contract

## Boundary

Sprint 3 recommends orientations; it does not rotate the model automatically.
Every candidate is a bounded what-if evaluation relative to the current object
transform. User approval is mandatory before any future transform workflow.
No candidate is guaranteed optimal, and no candidate proves that the model will
print successfully.

## Candidate generation

Generate a deterministic bounded set from:

1. current orientation;
2. principal-axis and bounding-box-axis alignments;
3. major planar-face normals and their opposite directions;
4. stable-contact candidates from contact-region normals; and
5. optional deterministic sampled orientations within a profile limit.

Deduplicate rotations by a declared angular tolerance and preserve the source
of each candidate. Do not generate an unbounded search or optimize geometry.

## Candidate metrics

Each candidate may evaluate fit and scale requirement, object height, contact
classification/area/regions, downward warning and critical area, floating-shell
count, thin-feature exposure, center-of-mass projection where valid, a
support-exposure proxy, and stability heuristic. Any missing metric is a
missing check with a state, not zero risk.

## Output

Return candidate ID, rotation relative to current orientation, score, overall
risk, advantages, trade-offs, confidence, measurement summary, and a concise
reason. Include profile/settings/build-direction snapshots and candidate
limits. Rank deterministically for equal inputs, but retain ties and explain
the weighted trade-off.

## Multi-objective policy

The ranking balances fit, contact, overhang, floating components, thin-feature
exposure, height, and stability. A candidate with lower support exposure may
have worse visible-surface orientation or contact; the report must show both.
Weights are profile/settings data, not hard-coded manufacturing truth.
