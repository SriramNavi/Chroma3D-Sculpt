# Wall-Thickness Method Contract

## Meaning

Local wall thickness is an estimated distance through material between two
opposing surface locations associated with a sampled surface point. It is not
the nearest arbitrary surface distance, a guarantee of slicer extrusion, or a
structural strength measurement. The result is a geometric estimate with a
profile comparison.

For a sample point `p` with unit surface normal `n`, a valid opposing hit `q`
produces `t = length(q - p)` when the hit is within the configured search
distance and passes all filters. The method records whether the ray was cast
along `+n`, `-n`, or both because orientation and shell winding may be
uncertain.

## Preconditions and supported mesh conditions

- The primary target is a closed, consistently oriented, face-connected solid.
- Closed shells with reliable topology can receive HIGH or MEDIUM confidence
  depending on coverage and ray quality.
- Open, non-manifold, intersecting, self-overlapping, or single-surface inputs
  remain measurable only as bounded experimental samples and must downgrade
  confidence or return `INDETERMINATE`.
- A single surface without an opposing shell is not a thin solid. It must not be
  reported as zero thickness.
- Multiple shells are evaluated per shell and do not silently become one solid.

## Sampling contract

Sampling is deterministic for identical geometry, transform, profile, settings,
and seed. The first implementation should combine:

1. area-weighted face-centroid samples;
2. stratified barycentric samples on large faces;
3. a bounded subset of vertices or curvature/feature candidates; and
4. optional risk-focused samples near already detected thin-feature evidence.

The method records face ID, barycentric coordinates, world-space position,
normal, shell ID, and sample source. It does not store the raw mesh in the
report. Samples must be distributed by area rather than face count so a dense
patch of tiny triangles cannot dominate results.

## Ray and hit rules

- Offset the ray origin by `ray_origin_offset_mm` away from the source surface
  before intersection to avoid self-hits. The offset is a numeric setting, not
  a manufacturing margin.
- Reject the source face, its immediate triangulation siblings, and a bounded
  same-surface adjacency ring. The ring size is recorded.
- Prefer the first hit along each tested direction that is inside the maximum
  search distance and whose hit normal is sufficiently opposing to the sample
  normal. The opposing-normal tolerance is configurable.
- If the shell winding is trustworthy, cast toward the interior first and use
  the opposite direction only as a controlled fallback. If winding is not
  trustworthy, test both directions and downgrade confidence.
- Keep the minimum accepted opposing distance for a local conservative result;
  retain the direction and hit face that produced it.
- Do not call the first hit exact where a curved surface, acute corner,
  overlapping shell, or self-intersection makes a normal ray ambiguous.

An AABB/BVH acceleration structure is required for non-trivial meshes. It must
be built from world-space triangles and released after the check. The structure
is an implementation detail and is not serialized.

## Failure and edge behavior

| Condition | Required result |
|---|---|
| No opposing hit within max distance | Sample `skipped`; retain reason `NO_OPPOSING_HIT` |
| Boundary/open shell at sample | `INDETERMINATE` or `NOT_APPLICABLE` for the affected region |
| Self-intersection or overlapping walls | Do not select an arbitrary hit; return `INDETERMINATE` for affected samples |
| Non-manifold adjacency | Skip ambiguous samples and lower confidence |
| Curved wall | Use the normal estimate but label curvature sensitivity |
| Single surface | No thickness result; report `NOT_APPLICABLE` or `INDETERMINATE` |
| Sample/triangle limit reached | `SKIPPED_LIMIT`, with attempted/completed/remaining counts |
| Runtime exception | `FAILED`, with a safe error class and no partial success claim |

## Outputs

The check result must include:

- `samples_attempted`, `samples_completed`, `samples_skipped`;
- `minimum_sampled_thickness_mm` and percentile thicknesses (`p05`, `p25`,
  `p50`, `p75`, `p95`) when enough samples exist;
- estimated surface area below warning and critical thresholds in `mm2` and as
  a percentage of sampled/covered area;
- thin-region count, largest thin-region area, and region connectivity method;
- bounded evidence face IDs, shell IDs, sample positions, hit positions, and
  sample thicknesses;
- confidence, evidence state, duration, configured limits, and limitations.

## Threshold evaluation

Measurement and evaluation are separate. The profile supplies warning and
critical wall thresholds. A sample at or below the critical threshold produces
`CRITICAL`; a sample above critical and at or below warning produces `WARNING`.
Area ratios and region size are supporting aggregation metrics, not universal
pass/fail rules. Every threshold carries its own classification and source
reference in the profile snapshot.

## Confidence

Confidence is a bounded categorical summary derived from topology readiness,
valid sample coverage, opposing-hit rate, normal consistency, curvature and
boundary ambiguity, and whether values came from project defaults. It is not a
probability. A proposed first implementation may use an auditable weighted
coverage score internally, but it must serialize the factors and category
mapping rather than expose an unexplained number.

## Performance profiles

FAST uses sparse area samples and a strict triangle limit; STANDARD uses the
default density; DEEP increases density and retains more region evidence. Deep
wall analysis on Extreme meshes must be skipped or bounded by explicit limits,
never allowed to run without a cap. See [performance modes](PERFORMANCE_MODES.md).
