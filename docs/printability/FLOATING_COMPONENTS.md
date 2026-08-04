# Floating-Component Method Contract

## Definitions

- A **connected shell** is a face-connected component under the mesh's shared
  edge connectivity.
- A **build-plane-connected shell** has at least one valid face, edge, or vertex
  within the profile contact tolerance of the selected build plane.
- A **suspended disconnected shell** is a connected shell that does not contact
  the selected plane and is not connected indirectly to a contacting shell.
- A shell connected to a contacting shell through geometry is one component for
  this check even if a narrow bridge or ornament is fragile.

## Evaluation

Use world-space coordinates and the profile build direction. For each shell,
measure minimum signed build-plane offset, contact primitive counts, reliable
volume availability, and connectivity to other shells. The main shell is not
special-cased as safe; tiny external shells are retained as review evidence.

Open shells can still have a geometric contact point, but confidence is reduced
and a reliable volume/center-of-mass conclusion is unavailable. A shell that is
not contacting the plane receives the neutral wording:

> Disconnected component not contacting the selected build plane; support or
> orientation review required.

This is not a declaration that the component is impossible to print. A slicer
may connect it with supports or a user may choose another orientation.

## Results

`PASS` means every evaluated shell is connected to the build plane under the
selected tolerance. `WARNING` means one or more disconnected shells are
present but the check is complete. `CRITICAL` is reserved for a profile policy
that treats suspended components as high risk; the profile and reason must be
visible. `INDETERMINATE` covers missing direction, ambiguous tolerance, or
invalid shell connectivity. Limits produce `SKIPPED_LIMIT`.

Evidence includes shell IDs, face counts, minimum offsets, contact classes,
connected-parent IDs where present, confidence, and bounded representative
faces/vertices. No shell is automatically removed or merged.
