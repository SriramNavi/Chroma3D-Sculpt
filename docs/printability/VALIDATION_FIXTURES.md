# Sprint 3 Validation Fixtures

Synthetic fixtures are mathematical truth fixtures for geometry and state
behavior. They do not prove real-world printing. Every fixture record must
declare geometry, expected measurement, tolerance, expected classification,
expected confidence, expected bounded evidence, and checks not applicable.

## Wall thickness

| Fixture | Expected truth |
|---|---|
| Closed box with known 2.0 mm wall | Samples cluster around 2.0 mm within declared geometric tolerance |
| Closed box with one 0.4 mm wall | Thin region identified and classified against profile thresholds |
| Hollow sphere with known thickness | Curved samples remain bounded; curvature limitation retained |
| Open single surface | No zero thickness; `NOT_APPLICABLE`/`INDETERMINATE` with low confidence |
| Intersecting walls | Ambiguous samples rejected or indeterminate |
| Curved thin shell | Opposing hits and curvature limitation are evidenced |
| Non-manifold thin region | Affected samples skipped/indeterminate; confidence reduced |

## Thin features

Use known-diameter cylinders, cone/spike series, thin rectangular stems,
finger-like protrusions, and ornament chains. Expected outcomes must cover
warning, critical, pass, ambiguous branch, and evidence cap cases.

## Overhangs

Use a horizontal underside, 30/45/60 degree ramps, a vertical wall, a curved
dome, an unsupported ledge, and small noisy faces. The truth table must verify
the documented angle convention, including 0 degree maximum severity and 90
degree neutral vertical behavior.

## Contact and floating components

Use a flat broad base, four feet, edge contact, point contact, elevated object,
two separate contact regions, a tilted base, a plate-connected shell, a
suspended cube, multiple suspended shells, an ornament connected to the main
shell, a shell chain, and a tiny external shell.

## Orientation

Use stable flat-bottom, tall narrow, L-shaped, sphere-like, multi-shell
statue-like, and build-volume-overflow fixtures. Verify bounded candidates,
deterministic ranking, trade-offs, stale rejection, and no automatic rotation.

## Real-world regression policy

Dataset `1.0.0` and Golden Benchmark `1.0.0` are regression inputs that expose
real mesh edge cases. They are not numerical truth and their existing
diagnostic/repair truth must remain unchanged. Proposed Printability Benchmark
`1.0.0` is independent and is not generated in Sprint 2.8.
