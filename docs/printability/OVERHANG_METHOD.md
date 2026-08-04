# Overhang Method Contract

## Convention

Build direction is a recorded unit vector and defaults to `+Z`. A face is a
downward face when `dot(n, b) < 0`. The overhang angle is measured from the
horizontal build plane:

`angle = degrees(acos(clamp(-dot(n, b), -1, 1)))`.

Under this convention:

| Surface | Angle | Severity |
|---|---:|---|
| Downward horizontal underside | `0 deg` | Maximum unsupported-downward severity |
| 30 degree ramp from horizontal | `30 deg` | Critical for profiles with a 30 degree critical threshold |
| 45 degree ramp from horizontal | `45 deg` | Typical FDM warning boundary in the project default |
| 60 degree ramp from horizontal | `60 deg` | Lower risk than 45 degrees |
| Vertical face | `90 deg` | Neutral for unsupported-downward evaluation |
| Upward face | Not evaluated | Not a downward overhang |

The words “45 degree overhang” are invalid without this reference convention.

## Face evaluation

For each eligible face, calculate the angle from the world-space face normal
and build direction. Compare it with profile warning and critical thresholds;
smaller downward angles are more severe. Weight area in `mm2`, retain total
downward area, warning area, critical area, and percentages of eligible surface
area. Do not use a face count alone for a dense organic mesh.

Small-face suppression is a configurable evidence/noise policy, not deletion.
The check must record suppressed count and area, and a region with enough
connected suppressed faces must be reconsidered in aggregation.

## Regions and curved surfaces

Adjacent risk faces are grouped by shared-edge connectivity and threshold band.
The report retains bounded region IDs, area, representative face, centroid,
maximum severity, and threshold band. Curved surfaces remain face-wise
piecewise estimates; sampling density and faceting limitations reduce
confidence. A smoothed normal may be displayed but must not replace the
geometric face-normal measurement without being recorded.

## Process and support policy

The profile identifies FDM, RESIN, or CUSTOM and a support assumption. The
check is a geometry risk proxy, not support generation, bridge simulation, or
slicer output. If support is assumed, the report says that the risk is support-
sensitive and that the support plan must be reviewed. It must never state that
no supports are required.

## Outputs and skip behavior

Return face count attempted/evaluated/skipped, total eligible area, warning and
critical area, connected regions, angle percentiles, build direction, bounded
face/region evidence, confidence, duration, and limitations. No build direction
or no valid normals yields `INDETERMINATE`; face/triangle limits yield
`SKIPPED_LIMIT`; a runtime error yields `FAILED`.
