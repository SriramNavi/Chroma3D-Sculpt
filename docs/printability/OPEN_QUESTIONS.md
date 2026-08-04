# Open Questions Before Sprint 3 Runtime Work

These questions are intentionally unresolved. They must not be silently turned
into universal thresholds or product promises.

1. What wall-thickness sampling density and ray offset remain stable across the
   Tiny through Extreme benchmark classes?
2. Should local feature radius ship in the first Sprint 3 implementation, or
   should only a conservative diameter proxy be exposed initially?
3. How should generic resin thresholds be calibrated across printer, resin,
   layer height, orientation, wash, and cure settings?
4. How should the support assumption be represented when a user intends to use
   supports but has not supplied slicer settings?
5. How many orientation candidates provide useful coverage without making Deep
   analysis impractical on Huge and Extreme meshes?
6. Is center-of-mass estimation sufficiently reliable for open shells or only
   for reliable closed solids?
7. Should the numeric score be shown during alpha, or should status and evidence
   be the primary UI until print-outcome calibration exists?
8. How will analysis be compared with real failed and successful FDM and resin
   prints under retained process metadata?
9. Which Chroma3D printers, materials, nozzles, layer heights, and support
   presets should become first-party profiles?
10. How should profile overrides be persisted, versioned, reviewed, and migrated?
11. Should a future profile distinguish plate usable area from advertised build
   volume, and how should that source be cited?
12. What operator workflow is appropriate for a risk item whose evidence is
   bounded or whose result is INDETERMINATE?
