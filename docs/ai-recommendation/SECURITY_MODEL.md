# Security Model

Trust boundaries are deny-by-default: user/object/evidence text is untrusted data; provider output is untrusted data; local schemas, policy, evidence and target registries are authoritative. The adapter cannot import Blender and receives IDs/summaries rather than callables.

The transport permits HTTPS POST only to `api.openai.com`, with bounded body/response/time, JSON content type, no redirects, cookies, sessions, automatic retries, proxy credential logging, or model-authored host/path. The response cannot contain Python, shell commands, Blender operator names, paths, URLs, arbitrary parameters, unknown operations, remesh, policy-bypass instructions, or unsupported guarantees.

No `eval`, `exec`, pickle, dynamic/generated code, downloaded binaries, telemetry, slicing, G-code, printer commands, automatic execution/acceptance, source replacement, or hidden network path exists. Cancellation is monotonic; a late response is quarantined and cannot become actionable.
