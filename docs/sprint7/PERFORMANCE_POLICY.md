# Sprint 7 Performance Policy

FAST/STANDARD/DEEP limits are now centralized in `performance_registry.py`. Current local results are observations under these unchanged provisional bounds; live-provider latency and cost remain `NOT RUN`.

## Status and provenance

The assistance limits below are implemented centralized project bounds and were exercised with local fake-provider/factory-Blender evidence. They remain safety maxima/warning envelopes, not provider latency guarantees. Dataset workers retain per-model elapsed time and a labeled point working-set observation; no peak-memory claim is made. Live-provider performance remains `NOT RUN`.

## Measured phases

1. source/evidence revalidation;
2. context allow-list extraction;
3. redaction and canonicalization;
4. request construction;
5. provider queue/connect/response, reported separately where observable;
6. strict decode and structural schema validation;
7. semantic/evidence grounding and local confidence;
8. exact candidate/strategy resolution;
9. existing preview;
10. delegated execution/checkpoints/comparison when explicitly approved;
11. report projection and local write;
12. total user-visible elapsed time.

Every local phase and total uses a monotonic clock. Provider-reported timing is labeled provider-reported and does not replace client-observed time.

## Mode envelopes

| Limit | FAST | STANDARD | DEEP | CUSTOM validated range | Provenance |
|---|---:|---:|---:|---:|---|
| Exported geometry elements | 0 | 0 | 0 | exactly 0 | Product safety invariant |
| Context JSON bytes | 32 KiB | 128 KiB | 512 KiB | 4–1,024 KiB | Provisional bounded default |
| User-intent UTF-8 bytes | 2 KiB | 4 KiB | 8 KiB | 1–16 KiB | Provisional bounded default |
| Recommendation candidates | 4 | 8 | 16 | 1–32 | At or below Sprint 6 frontier bounds |
| Evidence links | 64 | 256 | 1,024 | 1–2,048 | Provisional bounded default |
| Response bytes | 64 KiB | 256 KiB | 512 KiB | 4–1,024 KiB | Provisional security bound |
| JSON nesting depth | 16 | 20 | 24 | 4–32 | Provisional parser bound |
| Local wall-time warning | 5 s | 15 s | 45 s | 1–60 s | Provisional; excludes provider and delegated geometry work |
| Provider worker timeout | 15 s | 45 s | 120 s | 1–180 s | Provisional; provider decision gate required |
| Automatic retries | 0 | 0 | 0 | exactly 0 | Consent/cost/determinism safety invariant |
| Report bytes | 512 KiB | 1 MiB | 2 MiB | 64 KiB–4 MiB | Provisional bounded default |

### Triangle, sample, and candidate policy

Sprint 7 exports zero triangles and performs no mesh traversal. It consumes current Sprint 1–6 summaries. If fresh evidence is needed, the existing coordinator and `performance_registry.py` own triangle/sample/candidate limits; Sprint 7 cannot raise or override them. Sprint 7 recommendation limits apply after the Sprint 6 bounded strategy/frontier output and therefore never authorize more strategy candidates than Sprint 6 produced.

## Fixture sizes

- Tiny synthetic manifest: 1 source, 4 evidence links, 1 candidate.
- Boundary manifest per mode: exact context/evidence/recommendation/output byte and count limit.
- Over-limit manifest: one byte/item/depth beyond each limit, expected fail/skip with no provider/execution side effect.
- Representative 10-model and full 27-model manifests: real current summary density, no geometry payload.
- Adversarial output: maximum legal strings plus nested/duplicate/non-finite/unknown-field payloads.

## Timeout ownership and classification

The caller owns total request budget; the adapter owns transport cancellation and reports whether it acknowledged cancellation. The per-model parent owns dataset worker timeout. Existing Sprint 5/6 coordinators own geometry-operation boundaries. `TIMEOUT`, `BUDGET_EXHAUSTED`, `CANCELLED`, provider unavailability, and environment failure remain distinct. A timed-out/late/partial response is never parsed into an actionable recommendation.

## Cancellation behavior

Check cancellation before context work, before dispatch, after response receipt, between validation phases, before preview, before approval consumption, and at every existing safe execution boundary. The UI must update within the next local phase boundary. Provider transport may not be immediately interruptible; this limitation and late-response disposal are recorded.

## Memory observation terminology

Use **point memory observation** when RSS/private-working-set is sampled at phase boundaries. Record timestamp, tool/API, process scope, and units. Do not call this peak memory. Exact peak claims require continuous sampling with a documented interval and sampler overhead; absent that evidence, report only maximum observed sample.

## Environment record

Release performance evidence records CPU, logical cores, RAM, OS/build, Blender/Python/extension versions, provider adapter/model/deployment/region where applicable, network connection class where consented, power source, thermal/power mode, fixture fingerprint, background-load note, and clock source. Secrets, account identifiers, IP addresses, and customer paths are excluded.

## AC-power release condition

Local release performance gates run on AC power with stable performance mode and no known update/build workload. Live-provider latency is reported separately and cannot be a universal hard guarantee. Battery/power-throttled or provider-incident runs are retained as environment-sensitive evidence and do not erase local pass/fail results.

## Threshold approval and no weakening

1. Run retained baseline fixtures with first-failure evidence.
2. Separate deterministic local time from provider/network time.
3. Choose release warning/block thresholds from observed distributions and user workflow needs.
4. Record approver, rationale, hardware/provider scope and date in the versioned policy.
5. Never raise a threshold, reduce a fixture, remove a state, or reclassify a failure merely to obtain PASS. A legitimate policy change requires new evidence, version/hash change, rationale, and full affected rerun.

## Current execution status

Local compilation, focused/combined Blender suites, 10/27-model workers, bounded fake-provider gates, package/native/install smoke and independent final gates run without a live provider. AC/power-plan evidence and point-memory observations are retained separately. Live-provider latency/cost, Blender 4.5 LTS, slicer, material calibration and physical printing remain `NOT RUN`.
