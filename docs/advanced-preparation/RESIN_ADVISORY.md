# Resin Advisory

Resin advisory checks are experimental and disabled by default. They are
available only when a resin-compatible process context is selected and the user
explicitly enables the feature flag.

The implementation reports bounded geometry indicators such as downward-facing
island candidates, broad cross-section change, enclosed-volume uncertainty,
and review states derived from available mesh evidence. Insufficient or
ambiguous evidence returns an honest `NOT_EVALUATED`, limited, or indeterminate
state.

The feature does not simulate peel force, suction, fluid flow, pressure,
exposure, drainage, or cure behavior. It does not hollow a model, create drain
holes, add supports, rotate the object, or guarantee resin printability. Resin
profiles and thresholds are generic software heuristics; slicer and physical
resin calibration remain deferred.
