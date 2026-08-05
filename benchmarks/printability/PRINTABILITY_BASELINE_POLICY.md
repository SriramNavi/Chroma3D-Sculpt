# Printability Baseline Policy

## Version and immutability

The first eligible version is `1.0.0`. Once approved, a baseline manifest is
immutable. Algorithm, profile threshold, settings schema, result schema, or
dataset changes require a new baseline version or an explicitly compatible
comparison rule. Never rewrite a historical state to conceal a skip or failure.

## Required identity

Each record includes extension version, report/profile/settings/scoring policy
versions, implementation fingerprint, Dataset `1.0.0` model ID and SHA-256,
profile/settings snapshots and hashes, geometry/transform signatures, Blender
version, and generation time.

## Truth and comparison

- Compare states and numeric metrics only when source, implementation, profile,
  settings, and schema identities are compatible.
- Normalize only declared volatile IDs/timestamps; retain algorithm outputs,
  warnings, limitations, signatures, timings, and skip/failure truth.
- Report regressions per category; never convert missing evidence to zero risk.
- Physical linkage is optional and must reference a validated run/observation
  pair. Pending physical work remains `NOT_RUN`.

## Approval gate

Baseline publication requires independent software validation, package and
installed-extension evidence, dataset compatibility, a truthful Sprint 3.5
status, schema validation, and explicit owner approval. Physical validation may
remain pending, but the baseline must say so and cannot be described as
physically calibrated.
