# Terminology and Result States

## Units and coordinate convention

World-space geometry uses millimetres (`mm`), area uses `mm2`, volume uses
`mm3`, angles use degrees, and durations use seconds. The build direction is a
unit vector; Sprint 3 defaults to `+Z = (0, 0, 1)` and records any custom
direction in the report.

The overhang angle is measured from the horizontal build plane for downward
faces. For a unit face normal `n` and build direction `b`, a downward face has
`dot(n, b) < 0` and:

`overhang_angle_deg = degrees(acos(clamp(-dot(n, b), -1, 1)))`.

Thus a downward horizontal face is `0 deg` and has maximum unsupported-downward
severity; a vertical face is `90 deg` and is neutral for this check; an upward
face is not an unsupported-downward face. A profile threshold is crossed when a
downward face angle is at or below that threshold.

## Result states

| State | Meaning | User-facing interpretation |
|---|---|---|
| `PASS` | Required inputs and method completed; no configured risk crossed | No risk detected by this check under this profile |
| `WARNING` | Method completed and a review-level risk crossed | Review the evidence and process assumptions |
| `CRITICAL` | Method completed and a high-severity risk crossed | Resolve or explicitly accept the risk before slicing |
| `NOT_EVALUATED` | Check was not requested or required prerequisites were absent | No conclusion was made |
| `NOT_APPLICABLE` | Check does not apply to the selected process/geometry | Not a failure and not evidence of safety |
| `SKIPPED_LIMIT` | A declared performance/evidence limit prevented completion | Re-run in a deeper profile or inspect externally |
| `INDETERMINATE` | Inputs or geometry do not support a defensible result | Manual inspection or better geometry evidence is required |
| `FAILED` | The check attempted but encountered an implementation/runtime error | Treat the check as missing; retain the error safely |

## Confidence states

`HIGH`, `MEDIUM`, `LOW`, and `UNKNOWN` describe confidence in the measurement
and classification, not probability of printing. Confidence is reduced for
open/non-manifold geometry, low sample coverage, heuristic-only measurements,
profile defaults, stale or partial evidence, and skipped checks.

## Evidence states

`COMPLETE` means all evidence allowed by the method was retained. `BOUNDED`
means the method completed but storage was intentionally capped.
`TRUNCATED` means the cap removed items from the retained set while a total
count remains. `UNAVAILABLE` means no valid evidence could be retained.

## Stale states

`CURRENT` binds the result to all recorded signatures. `STALE_GEOMETRY`,
`STALE_TRANSFORM`, `STALE_PROFILE`, and `STALE_SETTINGS` identify which input
changed. A changed build direction is recorded as a settings/profile change and
must invalidate orientation and overhang evidence. Stale evidence cannot be
selected in the Blender viewport.

## Facts, evaluations, and risk items

Facts are measurements such as dimensions, shell IDs, triangle areas, sampled
thickness, contact offsets, and component connectivity. Evaluations compare
facts with a profile and settings. A risk item contains a stable rule key,
severity, message, affected evidence references, confidence, source
classification, and limitation. A risk message must say what was detected and
what the user should review; it must not promise that a part will print
successfully or that no supports are required.
