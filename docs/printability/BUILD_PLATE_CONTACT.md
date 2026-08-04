# Build-Plate Contact Method Contract

## Contact classifications

| Classification | Geometric meaning |
|---|---|
| `BROAD_CONTACT` | A substantial connected contact face/region with area above the profile evidence floor |
| `MULTI_REGION_CONTACT` | Two or more separated contact regions with meaningful area |
| `PARTIAL_FACE_CONTACT` | One or more faces intersect the tolerance band but only part of the face contacts |
| `EDGE_CONTACT` | Contact is represented by an edge or a very narrow strip |
| `POINT_CONTACT` | Contact is represented only by one or more vertices |
| `NO_CONTACT` | No valid mesh primitive is within contact tolerance |
| `INDETERMINATE` | Geometry, direction, or tolerance cannot support classification |

## Measurements

For the selected build direction and plane, return minimum signed plane offset,
contact tolerance, contact face/edge/vertex counts, contact area in `mm2`,
number of contact regions, projected footprint area and extents, contact-area
percentage, and bounded primitive IDs. If the shell is closed and reliable,
estimate the center-of-mass projection in the build plane. For open or
indeterminate-volume shells, omit the estimate and lower confidence.

## Stability heuristic

The first implementation may compare the center-of-mass projection with the
convex hull of the projected contact footprint and report a categorical
`INSIDE`, `NEAR_BOUNDARY`, `OUTSIDE`, or `UNAVAILABLE` heuristic. It must record
the margin in `mm` where defined. This is not a physical stability simulation:
friction, acceleration, adhesion, plate texture, support, resin peel forces,
and material behavior are not modeled.

Contact area and stability are separate facts. A broad but off-center contact
can still be a review risk, while several small feet can be a legitimate
multi-region contact.

## State behavior

No geometry contact is `WARNING` or `CRITICAL` according to profile policy, not
an automatic impossible-print classification. Ambiguous or limit cases are
`INDETERMINATE`/`SKIPPED_LIMIT`. Contact evidence is bounded and becomes stale
when geometry, transform, profile, build direction, or settings change.
