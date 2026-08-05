# Sprint 3 Printability User Guide

Printability is an advisory, local analysis workflow for the active mesh. It
reports profile-dependent geometric risks and review actions; it does not prove
that a model will print successfully.

## Analyze a mesh

1. Open **3D Viewport > Sidebar > Chroma3D > Chroma3D Sculpt > Printability**.
2. Select one mesh in Object Mode.
3. Choose Generic FDM, Generic Resin, Bambu Lab X1 Carbon, Bambu Lab P1S,
   Prusa MK4, or Custom. Packaged manufacturer profiles use cited build-volume
   facts; process thresholds remain visibly classified project defaults,
   heuristics, experimental rules, or user configuration.
4. For Custom, enter the build volume and threshold values shown in the panel.
5. Choose FAST, STANDARD, or DEEP. Higher modes increase bounded samples,
   triangle limits, candidate limits, and evidence caps; they do not remove
   those limits.
6. Confirm the build direction and candidate-source toggles, then choose
   **Analyze Printability**.

## Interpret the result

- Read status, score, confidence, primary reasons, skipped checks, and failed
  checks together. A high score is not a manufacturing guarantee.
- Review geometry facts separately from profile-dependent findings.
- Wall thickness is a bounded ray-sampled estimate. Open or ambiguous surfaces
  may be indeterminate.
- Thin-feature detection is an experimental conservative connected-shell
  diameter proxy and may return `NOT_EVALUATED` where the method is unsupported.
- Overhang angles follow the specification's build-direction convention.
- Floating components identify disconnected shells above the build plane; they
  do not predict slicer supports.
- Build-plate contact and stability are heuristics. Center-of-mass evidence is
  used only where volume is reliable.
- Scale advice and orientation candidates are virtual. No button applies a
  scale or rotation, and the best bounded candidate is not guaranteed optimal.

`NOT_EVALUATED`, `SKIPPED_LIMIT`, `INDETERMINATE`, and `FAILED` mean evidence is
missing or uncertain. They are never equivalent to a safe zero-finding result.

## Evidence and reports

Issue-selection controls operate only on bounded evidence from the current
source signature. They may change selection and Edit/Object mode after a stale
check, but never change geometry. Re-run Printability after any geometry,
transform, profile, build-direction, settings, or relevant file-state change.

Use **Export Printability JSON** for the schema 1.0.0 machine report or **Export
Printability Markdown** for a reviewable summary. Both preserve check states,
confidence, risk reasons, thresholds, candidates, timing, warnings, errors, and
limitations. Export rejects stale session evidence and writes UTF-8 files with
Windows-safe names.

## Current limitations

Sprint 4 adds a separate **Advanced Preparation** panel above this workflow. It
composes hardware and material profiles, compares bridge/support/resin/scale/
orientation evidence, supports bounded selected-object batches, and produces a
versioned software regression baseline/dashboard. See
[Advanced Preparation User Guide](../advanced-preparation/USER_GUIDE.md).

The Sprint 3 Printability report schema remains `1.0.0`; Sprint 4 does not
rewrite it or change the read-only Printability workflow.

- No slicing, G-code, support generation, resin hollowing/drain/suction checks,
  print-time estimate, automatic rotation, automatic scaling, or mesh repair.
- Modifier output is not evaluated.
- Printer/material/nozzle/layer/support interactions require slicer and operator
  review; retained real-print calibration is pending.
- Automated evidence targets Blender 4.4.3 on Windows 11. Blender 4.5 LTS and
  installed-panel manual interaction remain separate validation gates.
