# Sprint 7 Dataset and Fixture Plan

## Purpose

Validate context minimization, structured recommendation truth, deny-by-default resolution, source immutability, provider failure handling, and delegated workspace safety without using customer assets as training data or transmitting geometry.

## Fixture layers

### Synthetic truth fixtures

| Fixture family | Truth controlled |
|---|---|
| Context manifests | Exact allowed/forbidden fields, counts, truncation, hashes, consent and stale dependencies |
| Recommendation JSON | Valid no-action/current-candidate/current-strategy responses and every malformed/over-limit variant |
| Evidence graph | Known PASS/WARNING/FAIL/unknown/stale links, missing IDs, conflicting provenance and confidence overclaims |
| Provider adapters | Success, delay, timeout, cancellation acknowledgement, late response, malformed bytes, oversized output, usage/cost missing/invalid |
| Prompt-injection corpus | Direct and indirect instructions in intent, object names, evidence text, provider output, filenames and error strings |
| Existing-operation references | All allow-list tiers, exact/mismatched parameter hashes, prohibited remesh, hard-infeasible strategy |
| State/recovery | Every legal/illegal transition, stale revocation, checkpoint failure, operation failure, comparison/report/cleanup failure |

Synthetic geometry uses existing procedural Sprint 0–6 fixtures. Sprint 7 adds no geometry arrays to expected provider context.

## Representative real models

Use the established permissioned representative 10-model subset. The future representative run has two separated paths:

1. **Nondestructive recommendation path (10/10):** load model in isolated worker; generate or load current local Sprint 1–6 evidence; build context; invoke only the deterministic fake/recorded adapter; validate recommendations; verify source file hash and complete source snapshot unchanged; export bounded audit.
2. **Delegated mutation path (minimum one model per operation tier, target 10/10 when release scope enables execution):** resolve an existing candidate/strategy; preview; explicitly test approve/reject/cancel; run only in Sprint 5 workspace; compare; restore/discard or accept separate copy; verify source unchanged.

No real model is sent to a live provider. If a future approved live evaluation needs model-derived context, it requires a separate consent/provenance review and must use the exact bounded manifest defined here.

## Full 27-model use

The 27-model workflow is nondestructive by default. Each per-model worker validates current evidence identities, builds context under FAST/STANDARD/DEEP as selected, applies fake-provider truth cases, verifies no geometry payload, source hash/signature immutability, bounded audit size, and deterministic context hash. It does not run Blender mutation, live provider calls, slicing, or physical work unless a later gate explicitly authorizes a separate representative mutation subset.

Full-corpus reruns are required only when a relevant fingerprint changes. A provider/model version change alone reruns provider/evaluation fixtures and stored context manifests; it does not force geometry analysis when source/evidence fingerprints remain current.

## Fingerprint contract

Per-model record identity includes:

- dataset/manifest/license/provenance record version and source SHA-256;
- Blender/version/platform and source object/mesh/topology/transform/blend-file signatures;
- diagnostic, printability, process, feature, profile, performance-registry, Sprint 5 policy/objective/candidate, Sprint 6 search/constraint/strategy/frontier/ranking, and implementation fingerprints;
- assistance policy, mode, context allow-list/redaction, prompt template, draft/runtime schema, provider contract/adapter, fake evaluation case, and implementation fingerprints;
- consent scope and data-category manifest hash (never credential value).

Changing any consumed input invalidates the derived context/recommendation record. Presentation-only Markdown changes do not invalidate machine evidence.

## Worker isolation, limits, and resumability

- One Blender process per model, factory startup, explicit input/output paths that support spaces.
- Parent owns timeout and termination classification; worker writes a temporary record then atomically promotes only a complete valid record.
- Initial per-model limits are measurement envelopes, not release PASS claims: 180 seconds nondestructive fake-provider FAST/STANDARD, 600 seconds DEEP, and 1,200 seconds only for separately approved representative workspace execution. Calibrate from retained first-run evidence without weakening after failures.
- Resume key is the complete fingerprint; partial, invalid, stale, timed-out, or mismatched records rerun.
- Parent records exit code, timeout owner, stdout/stderr paths, elapsed time, point memory observations where available, source before/after hashes, and classification.
- No worker shares Blender objects, provider session state, credentials, or mutable caches.

## Failure classifications

`PASS`, `PRODUCT_DEFECT`, `FIXTURE_DEFECT`, `SOURCE_MISMATCH`, `STALE_INPUT`, `PROVIDER_CONTRACT_FAILURE`, `PROVIDER_UNAVAILABLE`, `SECURITY_REJECTION`, `TIMEOUT`, `CANCELLED`, `BUDGET_EXHAUSTED`, `INDETERMINATE`, and `ENVIRONMENT_FAILURE` are distinct. Only `PASS` satisfies a required dataset gate. Expected adversarial rejection is PASS only when the specific test expected denial and proves no side effect.

## Mutation and source immutability evidence

Record source object/mesh identities, geometry/topology/transform/state signatures, collection/visibility/material/modifier/custom-property snapshots, file hash where applicable, owned workspace/checkpoint IDs, and before/after checks. Nondestructive workers require byte/signature equality. Mutation workers permit changes only to session-owned workspaces and accepted copies; the source remains identical.

## Performance evidence

Retain context extraction/canonicalization, request construction, fake-provider, decode/schema, grounding/resolution, preview/delegated execution, comparison, export and total monotonic timings; input/output/evidence/recommendation/report sizes; timeout owner; and point memory observations with sampling labels. Do not call point observations peak memory.

## Dataset execution status

Sprint 7 adds `manual-tests/sprint7/run_dataset_validation.py` and an isolated Blender worker. The worker imports one permissioned model, captures its source signature, creates bounded current Sprint 5 candidates/Sprint 6 strategies, builds the consented zero-geometry FAST context, validates an exact fake-provider strategy response, repeats the context hash, proves source immutability, and records elapsed time plus a labeled point working-set observation. Representative 10/10 and full 27/27 results pass under the current validation fingerprint with zero live-provider calls, geometry payloads, source mutations, or timeouts. Frozen Sprint 0–6 evidence was verified unchanged.
