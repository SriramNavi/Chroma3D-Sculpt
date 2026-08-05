# Sprint 2 Historical Performance Disposition

## Decision

`S2-PERF-PASS`

The Sprint 2 S2F-I warning gate remains separate from the Sprint 4 release-readiness decision. The warning threshold was not changed or bypassed: the retained threshold is strictly less than 60 seconds for the three-operation realistic repair batch.

## Current isolated confirmation

| Run | Repair batch | Threshold | Result |
|---|---:|---:|---|
| 1 | 47.357981 s | < 60 s | PASS |
| 2 | 47.651000 s | < 60 s | PASS |
| Authoritative Sprint 2 final wrapper | 46.933559 s | < 60 s | PASS |

All three results used Blender 4.4.3 with `--background --factory-startup` and the unchanged S2F-I fixture and assertions. The two isolated confirmation runs used AC power, the Turbo power scheme, no pre-existing Blender or Python worker, and normal process priority. Processor-performance samples were approximately 86.83-92.39% around and during those runs. Point working-set collection was unavailable, so no exact or peak-memory claim is made.

## Retained earlier evidence

The earlier full historical wrapper observation of 115.830 seconds is retained as a failed environment-dependent observation. It is not relabelled or deleted. The two controlled confirmations and the current authoritative Sprint 2 final wrapper demonstrate that the same release candidate meets the unchanged warning threshold under the current isolated conditions.

## Scope boundary

This disposition does not change Sprint 2 repair logic, the S2F-I fixture, or the 60-second warning threshold. It does not convert skipped, indeterminate, or failed correctness evidence into a pass. It only records the independently repeated current performance result.
