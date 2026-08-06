# Sprint 7 Static Architecture and Provider Contract Audit

Audit date: **2026-08-07**
Disposition: **PASS after reproduced hardening**
Live provider calls: **0**

## Architecture and safety

1. Provider-neutral protocol boundary: PASS (`AIProvider`, prepared request, invocation result and capability models are vendor-neutral).
2. OpenAI isolation: PASS (endpoint, headers, request/response envelope logic and HTTPS transport are isolated from the coordinator).
3. Runtime dependency boundary: PASS (standard library plus Blender runtime only; no added external package).
4. Deterministic fake/offline paths: PASS.
5. Automated live-provider prohibition: PASS (all automated gates use fake/offline or transport stubs).
6. Provider-to-Blender operator access: PASS (provider modules import neither `bpy` nor operator/coordinator modules).
7. Provider geometry mutation access: PASS.
8. Context/transport separation: PASS.
9. Pre-transport redaction: PASS (strict allow-list manifest is constructed and checked before adapter preparation).
10. Central mode limits: PASS (`performance_registry.py` and `ai_assistance_settings.py`).
11. Untrusted provider output: PASS.
12. Strict decoding: PASS (duplicate keys, non-finite values, extra/trailing data, depth/node/string/byte limits, markup, executable text, paths and URLs fail closed).
13. Recommendation validation: PASS, fail closed.
14. Exact disclosed-ID/hash grounding: PASS.
15. Approval binding: PASS (session, source, context, policy/settings, exchange-derived recommendation, selected target, operations/parameter hashes and exact preview are bound through deterministic identities and the approval scope hash).
16. Stale approval invalidation: PASS.
17. Sprint 5/6 execution delegation: PASS (provider output cannot call mutation; approved targets resolve to existing protected-workspace operations).
18. Bounded local redacted reports/audits: PASS after atomic-write and UNC-path hardening.
19. Credential lifetime/serialization: PASS after removing the rendered credential suffix; status now exposes presence/source only and the transient operator input is `SKIP_SAVE`.
20. Retry behavior: PASS (zero automatic retries; one explicit user retry at most).
21. Cancellation: PASS, fail closed at phase boundaries; delegated cancellation exercises restore behavior.
22. Offline fallback: PASS and explicitly non-provider-generated.
23. Generic provider models: PASS (no OpenAI-specific field leaks into the provider protocol/session coordinator).
24. Provider truth claims: PASS (confidence is derived locally and limitations remain explicit).

## Reproduced findings and corrections

- SECURITY: the credential status exposed the final four characters in the Blender panel/configuration message. Corrected to expose zero credential characters; regression coverage scans the full sentinel and suffix.
- INTEGRATION: the raw REST adapter accepted the SDK-only top-level `output_text` convenience field. Corrected to accept only canonical `output` message content from the raw Responses envelope.
- INTEGRATION: report/audit writers wrote final destinations directly and did not explicitly reject UNC paths. Corrected with bounded same-directory temporary writes plus atomic replacement and explicit network-path rejection.
- HARNESS: the retained final evidence used a hard-coded dataset label and did not map the required S7F groups exactly. Corrected with a deterministic per-file release-input fingerprint and exact S7F-A through S7F-R aggregation.

First-failure evidence is retained in `AUDIT_FIRST_FAILURE.md`. No assertion, threshold, schema or safety rule was weakened.

## Official OpenAI Responses adapter contract

Official contract checked on **2026-08-07** against:

- https://developers.openai.com/api/docs/guides/text
- https://developers.openai.com/api/docs/guides/structured-outputs
- https://platform.openai.com/docs/api-reference/responses

Verified assumptions:

- `POST https://api.openai.com/v1/responses` with bearer authorization and JSON content.
- Request supplies `model`, `instructions`, `input`, `text.format` JSON Schema with `strict: true`, and `store: false`.
- Raw REST response extraction scans `output` message content for exactly one `output_text` item and treats `refusal` as non-recommendation output.
- Non-completed responses, non-2xx status, redirects, non-JSON content, invalid/oversized bodies, timeout and transport errors fail closed with bounded safe messages.
- Credential values are supplied only at the explicit invocation boundary and are not persisted, reported or audited.
- No automatic live retry, provider switch, tool call or live request exists in automated validation.

The adapter contract is source-verified but **live provider qualification remains NOT_RUN**. Model availability, provider retention, billing, account policy and production response behavior are intentionally unqualified for this alpha.
