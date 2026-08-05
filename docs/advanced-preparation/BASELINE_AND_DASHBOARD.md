# Printability Baseline and Dashboard

Printability Baseline `1.0.0` stores one record per immutable Dataset `1.0.0`
model. Records bind the source SHA-256, process-context hash, feature flags,
software fingerprint, score/status/confidence, per-check states, bridge and
support summaries, resin states, scale interval, orientation candidates,
timings, and limitations. The manifest and records are schema validated and
verified before comparison.

The comparator supports exact, policy-aware, and informational fields. It
reports additions, removals, changed hashes, regressions, improvements,
warnings, and review-required differences without normalizing away diagnostic
states. A skip, failure, limit, or indeterminate result cannot be treated as a
successful zero finding.

The dashboard generator writes a single escaped, self-contained HTML file. It
uses no CDN, telemetry, remote font, script, or runtime network request. It
summarizes model outcomes and comparisons but remains engineering regression
evidence—not physical validation. Canonical generated evidence is produced by
the Sprint 4 acceptance runner under `benchmarks/printability` and
`manual-tests/sprint4`.
