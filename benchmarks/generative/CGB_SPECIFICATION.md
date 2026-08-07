# Chroma3D Generative Benchmark 0.1.0

Name: **Chroma3D Generative Benchmark**<br>
Short name: **CGB**<br>
Version: **0.1.0**

Every attempt records `cgb_version`; evidence from incompatible versions is never silently compared.

## Tracks

| Track | Scope | Unsupported state |
|---|---|---|
| A | Single image to ground-truth reconstruction | `NOT_APPLICABLE` |
| B | Multi-view to ground-truth reconstruction | `NOT_APPLICABLE` |
| C | Text to 3D, separate prompt corpus | `NOT_APPLICABLE` |
| D | Raw geometry health | `NOT_APPLICABLE` |
| E | Chroma3D conditioning uplift | `NOT_APPLICABLE` |
| F | Performance, reliability, and cost | `NOT_APPLICABLE` |
| G | Texture/PBR capability | `CAPABILITY_ONLY` for untextured GT27 |
| H | Blind human preference | `NOT_RUN` until an owner scores it |

## Corpus

Dataset 1.0.0 supplies 27 rights-cleared, source-immutable ground-truth STLs. `CGB-SMOKE3` contains 3 cases, `CGB-CORE10` reuses the exact Sprint 7 representative set, and `CGB-FULL27` contains all 27. Source SHA-256 is checked before and after corpus, render, conditioning, and run stages.

## Canonical references

The Blender background renderer uses an isolated imported source plus independent render copy. Only the copy is centered and uniformly scaled. Four fixed views are rendered: front, front three-quarter, side, and back. Resolution, camera, lights, clay material, background, engine, color management, and transparency are pinned in `render_config.json`; its canonical JSON SHA-256 is the render-config identity.

## Artifact/evaluation flow

```text
provider artifact -> preserve and hash raw bytes -> import/validate -> RAW METRICS
                  -> evaluation copy -> center/uniform scale/24 bounded orientations
                  -> FIDELITY + SILHOUETTE METRICS
                  -> isolated Chroma3D repair workspace -> CONDITIONED METRICS
```

Raw artifacts are never overwritten. The alignment transform is retained. Zero diagonal or otherwise unreliable alignment produces `ALIGNMENT_INDETERMINATE`, not invented metrics.

Minimum fidelity evidence is normalized symmetric sampled-surface Chamfer distance, F-score at 1/2/5% of ground-truth diagonal, absolute normal consistency, bounding-box proportion error, canonical silhouette IoU, surface-area ratio, reliable-solid volume ratio, and component-count difference. Detail evidence in v0.1 is explicitly `EXPERIMENTAL` and excluded from primary ranking.

## Run identity and failures

Reusable generation identity requires exact CGB version, case hash, backend ID, model version, request-parameter hash, adapter version, attempt, seed semantics, and quality mode. Artifact SHA-256 must still match. Failed attempts remain evidence and are never reused as success.

Statuses are `PASS`, `GENERATION_FAILED`, `PROVIDER_ERROR`, `TIMEOUT`, `INVALID_ARTIFACT`, `IMPORT_FAILED`, `ANALYSIS_FAILED`, `ALIGNMENT_INDETERMINATE`, `UNSUPPORTED_TRACK`, `MISSING_CREDENTIAL`, `SPEND_NOT_AUTHORIZED`, `MODEL_NOT_INSTALLED`, `INSUFFICIENT_HARDWARE`, `VERSION_UNVERIFIED`, and `NOT_RUN`.

## Decision boundary

Offline framework/fake evidence yields `G0_FRAMEWORK_COMPLETE_READY_FOR_BACKEND_EXECUTION` and the exact statement **NO MODEL WINNER HAS BEEN DECLARED.** Actual winners require genuine Smoke3 plus Core10 evidence for finalists.
