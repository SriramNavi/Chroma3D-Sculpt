# Advanced Preparation User Guide

## Analyze one object

1. Open Blender's **3D Viewport > Sidebar > Chroma3D > Advanced Preparation**.
2. Select a mesh and make it active.
3. In **Process Context**, choose a hardware profile and compatible generic
   material, then set nozzle, layer height, plate, and support-review policy.
4. Review optional overrides and feature flags. Experimental resin/material
   flags require explicit enablement.
5. Choose FAST, STANDARD, or DEEP and run **Analyze Active Object**.
6. Review status, confidence, limitations, bridge/support/resin evidence,
   feasible scale interval, and virtual orientation comparison.
7. Export JSON or Markdown only after confirming the result is current.

Changing source topology, transforms, build direction, process inputs, feature
flags, or the performance policy makes prior evidence stale. Re-analyze instead
of exporting stale results.

## Analyze a selection

Select the intended mesh objects and run **Analyze Selected Meshes**. Batch
limits are mode-dependent. Individual failures are retained without discarding
successful object evidence. Cancellation is cooperative between objects; a
compatible partial run can resume.

## Baseline tools

Baseline generation, verification, comparison, and the offline dashboard are
engineering tools for the immutable Dataset corpus. Use the repository Sprint 4
acceptance runner for canonical evidence; do not substitute working scene files
for the locked dataset when making regression claims.

## Safety and limitations

The panel never applies scale or rotation, modifies geometry, generates
supports, hollows resin, adds drain holes, slices, produces G-code, sends a
printer command, or uses a network runtime. Material values are generic and not
physically calibrated. Bridge/support/resin results are bounded advisories, not
a print-success guarantee. Installed-panel UAT, Blender 4.5 LTS, slicer
comparison, and physical validation are deferred. Sprint 5 has not started.
