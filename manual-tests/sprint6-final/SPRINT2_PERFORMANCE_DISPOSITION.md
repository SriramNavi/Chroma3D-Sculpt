# Sprint 2 S2F-I Performance Disposition for Sprint 6

## Decision

**PASS** on stable AC power with the unchanged `60.0`-second repair-batch threshold.

The two isolated current-source probes and the official Sprint 2 final wrapper all passed the same retained S2F-I realistic repair fixture. Functional assertions, rollback, checkpoint behavior, and protected-source immutability also passed.

## Current environment

- Power: AC online; battery `100%` at launch.
- CPU: 13th Gen Intel(R) Core(TM) i7-13620H; 10 cores / 16 logical processors.
- Blender: `4.4.3`.
- Fixture: `76,512` vertices, `229,480` edges, `152,978` faces, `152,996` triangles.

## Current measurements

| Run | Repair batch | Full gate / process | Threshold | Source immutable | Result |
|---|---:|---:|---:|---|---|
| Isolated probe 1 | `49.060652s` | `123.102s` process | `60.0s` | yes | PASS |
| Isolated probe 2 | `48.931513s` | `122.468s` process | `60.0s` | yes | PASS |
| Official Sprint 2 final | `47.498363s` | `117.351171s` S2F-I gate | `60.0s` | yes | PASS |

The official wrapper completed `19/19` gates and reported `SPRINT 2 FINAL VALIDATION PASSED WITH LIMITATIONS`. Those limitations are deferred manual/real-model activities; the current S2F-I performance result itself is PASS.

## Preserved historical observations

- Earlier accepted AC observation: `46.126322s`.
- Earlier retained five-operation harness observation: `91.265s`; classified as historical harness evidence, not the current three-operation S2F-I threshold measurement.
- Battery/CPU-throttled investigation observations included `120.022s`, `116.480s`, and instrumented `100.438170s` failures.
- The first Sprint 6 historical chain observed `88.231s` and correctly kept S6-16 indeterminate pending stable-AC isolation.
- Later stable-AC recovery previously measured `46.857183s` isolated and `47.862992s` in the complete final chain.

No threshold was increased or weakened, and no slow observation was removed. The current evidence supports an environment-sensitive historical performance disposition rather than a product or safety defect.
