# Scale and Build-Volume Contract

## Reuse and separation

Sprint 3 should reuse the existing current-orientation rectangular fit concept:
world-space dimensions are compared axis by axis with profile build volume.
The existing Sprint 1 analyzer remains unchanged in Sprint 2.8. The future
printability result adds profile safety margins and scaling consequences without
changing current diagnostic semantics.

## Fit rules

- Record profile dimensions as `x`, `y`, and `z` in `mm` and their source.
- Subtract a non-negative dimensional safety margin from each usable axis.
- Compare each dimension with a declared exact-boundary tolerance.
- Return axis fit, excess per axis, overall fit, and current-orientation-only
  status. Exact-boundary behavior is deterministic and visible.
- A missing or invalid profile is `NOT_APPLICABLE` or `FAILED`, not a fit.

The advertised build volume and a slicer/plate usable envelope may differ. The
profile must say which one it represents and cite the source. For example, the
Bambu profile records the manufacturer-stated 256 x 256 x 256 `mm` volume but
does not infer a larger usable region.

## Uniform scale preview

The advisory calculation may report the largest uniform scale that fits the
usable volume. It must not apply that scale. Before a user approves any future
transform, preview the consequences for:

- minimum wall thickness;
- minimum feature diameter;
- contact tolerance and contact area;
- build-plane offset;
- profile threshold crossings; and
- orientation and all stale signatures.

If fitting requires a scale that moves any measured wall or feature below a
profile warning/critical threshold, emit a risk item explaining the trade-off.
Do not silently scale to fit, and do not report fit as evidence that thin
features remain viable.
