# Sprint 2 S2F-I Performance Breakdown

## Result

- Root cause: environment (`K`), specifically battery-power CPU throttling.
- Instrumented repair batch: `100.438170` seconds; threshold: `60.0` seconds; result: **FAIL**.
- Threshold and assertion are unchanged.
- Product regression: **not found**. Harness regression: **not found**.

## Causal Evidence

The accepted report was written at `2026-07-19T00:30:05+05:30` after a `1876.019617`-second wrapper run, placing its first independent Blender validation at approximately `23:58:48.980` through `00:00:55.063`. Windows Kernel-Power event `105` records AC online during that interval and AC disconnect at `00:01:15.410`, `20.347` seconds after the accepted inner validation ended.

All later failures ran after that AC disconnect. The instrumented reproduction ended on battery at `9%`, AC offline and discharging. Across 123 samples the CPU stayed at exactly `1506 MHz`, with Windows processor performance held to `57.17–57.76%`.

| Measurement | Accepted | Battery instrumentation | Ratio |
|---|---:|---:|---:|
| Fixture generation | 8.352067s | 16.457845s | 1.971x |
| Session creation | 11.250121s | 25.090423s | 2.230x |
| Plan generation | 5.954872s | 13.594082s | 2.283x |
| Checkpoint probe | 0.932842s | 2.244273s | 2.406x |
| Repair batch | 46.126322s | 100.438170s | 2.177x |
| Before analysis | 8.315699s | 18.255378s | 2.195x |
| After analysis | 8.691142s | 17.696015s average | 2.036x |

The uniform slowdown across fixture creation, analysis, planning, checkpoints, and the repair batch is inconsistent with a localized repair-algorithm or stopwatch regression and matches the measured system-wide CPU limit.

## Run History

| Run | Repair batch | Power evidence |
|---|---:|---|
| Earlier accepted | 46.126322s | AC online during inferred S2F-I interval |
| Independent failure 1 | 120.022s | After recorded AC disconnect |
| Independent failure 2 | 116.480s | After recorded AC disconnect |
| Unmodified investigation reproduction | 105.026s | Battery, AC offline |
| Instrumented reproduction | 100.438170s | Battery 9%, AC offline, CPU fixed at 1506 MHz |

## Fixture and Operation Equivalence

- Vertices: `76,512`
- Edges: `229,480`
- Faces: `152,978`
- Triangles: `152,996`
- Selected operations in both accepted and failing runs: duplicate merge, degenerate cleanup, loose cleanup.
- Candidate-sensitive tiny-shell and hole-fill operations remained unselected, as required by the retained S2F-I definition.

## Threshold-Batch Breakdown

| Component | Wall seconds | CPU seconds | Notes |
|---|---:|---:|---|
| Analysis, three post-operation calls | 53.088046 | 49.718750 | 17.307–18.387s each |
| Checkpoint creation, three calls | 6.392482 | 6.015625 | 2.087–2.176s each |
| Repair algorithm dispatch | 3.925183 | 3.921875 | Three selected algorithms |
| Validation, signatures, orchestration | 37.032459 | derived within batch | Source/workspace safety checks and record handling |
| **Repair batch** | **100.438170** | **93.468750** | Original threshold stopwatch |

The batch was CPU-bound: `93.469` CPU-seconds during `100.438` wall-seconds. The outer monitor measured Blender at `92.67%` average of one logical core and `181.24%` sampled peak.

## Full Phase Timing

| Phase | Status | Wall seconds | CPU seconds |
|---|---|---:|---:|
| Fixture generation | Measured | 16.457845 | 16.046875 |
| Harness preparation | Measured | 2.162064 | 2.000000 |
| Session creation | Measured | 25.090423 | 22.750000 |
| Initial analysis within session | Measured | 18.255378 | 16.421875 |
| Repair plan | Measured | 13.594082 | 12.343750 |
| Standalone checkpoint probe | Measured | 2.244273 | 2.078125 |
| Repair batch | Measured | 100.438170 | 93.468750 |
| Undo | Measured | 26.568660 | 25.015625 |
| Undo re-plan | Measured | 13.144869 | 11.984375 |
| Reapply | Measured | 39.868837 | 36.750000 |
| Rollback | Measured | 2.320729 | 2.078125 |
| S2F-I cleanup | Measured | 0.002993 | 0.015625 |
| Harness main | Measured | 256.049225 | not aggregated |
| Non-gate harness overhead | Measured | 0.034353 | not aggregated |
| External launch to harness import | Measured | 3.473221 | not aggregated |

Supporting small-fixture gate measurements: undo `0.011749s`, restore `0.004279s`, accept `0.013274s`, rollback `0.000684s`, audit generation/export `0.018813s`, registration gate `0.010849s`.

## Repair Operations

| Operation | S2F-I status | Dispatch wall seconds |
|---|---|---:|
| Duplicate merge | Measured, selected | 2.241053 |
| Zero-length collapse | Not selected by retained S2F-I | — |
| Degenerate cleanup | Measured, selected | 1.447811 |
| Loose cleanup | Measured, selected | 0.236319 |
| Normal consistency | Not selected by retained S2F-I | — |
| Orientation | Not selected by retained S2F-I | — |
| Tiny shell | Explicit candidate selection absent; not run | — |
| Hole filling | Explicit candidate selection absent; not run | — |

All eight dedicated operation gates passed in the same instrumented Blender launch; their full small-fixture gate durations ranged from `0.045252` to `0.076664` seconds. Non-executed realistic-fixture operations are not serialized as zero-duration successes.

## Environment

| Item | Evidence |
|---|---|
| CPU | 13th Gen Intel Core i7-13620H, 10 cores / 16 logical processors |
| RAM | 31.631 GB total |
| Blender / embedded Python | 4.4.3 / 3.11.11 |
| Validation wrapper Python | 3.12.0, same as accepted report |
| Power plan | Windows `Performance` |
| Power source | Battery, AC offline, discharging |
| CPU frequency | 1506 MHz min / average / max across 123 samples |
| Processor performance | 57.17% min, 57.58% average, 57.76% max |
| Process priority | Normal |
| Peak Blender working set | 0.522 GB |
| Peak Blender private memory | 0.533 GB |
| Minimum available RAM | 15.517 GB |
| Maximum paging-file usage | 0.410% |
| System CPU | 23.39% average, 46.05% peak |
| Background Blender before run | 0 |
| Blender launches | 1 |
| Outer validation wrappers | 0 |
| Instrumented log volume | 12,142 bytes stderr; 1,081 bytes stdout |

The earlier accepted report did not record CPU frequency, available RAM, process priority, or peak utilization. Those fields remain `NOT RECORDED`; only its AC-online state is recoverable from the Windows event timeline.

## Cause Matrix

| Suspect | Finding |
|---|---|
| A Fixture generation | Same fixture; globally slowed 1.971x |
| B Analysis | Largest timed component; globally slowed 2.0–2.2x |
| C Repair algorithms | Only 3.925s of the 100.438s batch |
| D Checkpoints | Same implementation; globally slowed 2.406x |
| E Validation wrapper | Eliminated; direct one-process reproduction failed |
| F Legacy acceptance wrappers | Eliminated; they execute after the independent gate |
| G Package validation | Eliminated; not launched in direct reproduction |
| H Blender startup | 3.473s to import, outside batch stopwatch |
| I Python startup | Included in startup above, outside batch stopwatch |
| J Logging | 12 stress log lines; no evidence of material contribution |
| K Environment | **Confirmed root cause: AC-to-battery CPU throttling** |
| L Garbage collection | Active, but CPU-bound and no code/fixture change evidence |
| M Memory pressure | Eliminated: 0.522 GB peak, 15.517 GB minimum available |
| N Repeated registration | Eliminated: one registration before S2F-I; lifecycle gate after it |
| O Repeated loading | Eliminated: one Blender launch and one fixture creation |
| P Repeated analysis | Expected initial plus one post-analysis per operation; no duplicate call |
| Q Timing bug | Eliminated: wall and process CPU agree; independent monitor agrees |
| R Threshold bug | Eliminated: 60.0s unchanged and scoped only to repair batch |
| S Different fixture | Eliminated: all topology counts and selected operations match |

## AC-Powered Recovery

- Pre-run environment: AC online, charging, `86%` battery, `2400 MHz`, and `92–95%` Windows processor performance.
- Focused unchanged S2F-I repair batch: `46.857183` seconds; result: **PASS**.
- Authoritative full final-validation S2F-I repair batch: `47.862992` seconds; result: **PASS** (`19/19` Sprint 2 final gates).
- Post-run environment: AC online, charging, `99%` battery, `2400 MHz`, and `96–97%` Windows processor performance.
- Fixture topology remained `76,512` vertices, `152,978` faces, and `152,996` triangles. Selected operations remained merge duplicate vertices, remove degenerate faces, and remove loose geometry.
- The threshold remained exactly `60.0` seconds. Source immutability passed.
- No product or permanent harness change was made to recover the gate. The historical battery failures and generated JSON evidence remain preserved.

## Decision

The unchanged S2F-I gate recovered on stable AC power and passed again in the complete final-validation chain. The prior failures were environmental battery CPU throttling, not a product or permanent harness regression. No production or harness fix is justified, and the `60.0`-second threshold remains unchanged.
