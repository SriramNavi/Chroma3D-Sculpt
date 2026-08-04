# Performance Modes and Mesh-Class Policy

## Modes

| Mode | Intended use | Wall samples | Expensive triangle limit | Orientation candidates | Memory/evidence | Skip behavior |
|---|---|---:|---:|---:|---|---|
| `FAST` | Interactive first look | 256 | 100,000 | 4 | Small BVH; evidence cap 256 | Skip wall/orientation detail at limits |
| `STANDARD` | Default review | 2,048 | 500,000 | 8 | Bounded BVH; evidence cap 2,048 | Return `SKIPPED_LIMIT` with counts |
| `DEEP` | Deliberate investigation | 16,384 | 1,000,000 | 12 | Higher bounded memory; evidence cap 10,000 | Never run uncapped on Extreme |

These are project defaults and user-configurable limits. They are not timing
guarantees. Every expensive check reports duration, attempted work, completed
work, limits, and cancellation state.

Geometry quantities retain `mm`, `mm2`, and `mm3` units; angles are degrees;
durations are seconds; triangle and sample limits are integer counts. Memory
behavior is bounded by the declared evidence and spatial-index limits.

## Benchmark classes

The existing benchmark classification remains:

| Class | Sprint 3 policy |
|---|---|
| Tiny | All modes; synthetic and smoke coverage |
| Small | All modes; full fixture coverage |
| Medium | All modes; bounded evidence |
| Large | FAST/STANDARD default; DEEP explicit |
| Huge | FAST/STANDARD default; Deep requires reviewable limits |
| Extreme | No uncapped Deep wall-thickness or orientation search; skip or sampled mode only |

Triangle count is not the only complexity signal. Shell count, spatial index
memory, face size distribution, sample count, and evidence size must be
recorded. The Dataset `1.0.0` and Golden Benchmark `1.0.0` classes are regression
inputs, not mathematical truth fixtures.

## Progress, cancellation, and states

Long checks expose monotonic progress with phase, completed/total work, and a
cancellation point between bounded batches. Cancellation produces an explicit
`INDETERMINATE` or `SKIPPED_LIMIT` result with retained partial counts; it does
not serialize a successful zero result. A caught implementation error is
`FAILED`. A valid completed check is `PASS`, `WARNING`, or `CRITICAL`.
