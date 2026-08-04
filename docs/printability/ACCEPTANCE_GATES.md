# Sprint 3 Acceptance Gates

Sprint 3 cannot be accepted from documentation alone. Each gate requires
retained machine evidence, focused tests, and the applicable manual review.

## S3-01 - Architecture and regression

- Existing diagnostics and repair behavior are unchanged.
- Sprint 0, Sprint 1, and Sprint 2 regressions pass.
- Printability services remain separate from diagnostics, repair, UI, and
  report serialization boundaries.

## S3-02 - Printer profiles

- All profiles validate against the printer-profile schema.
- Published build volumes and included nozzle facts have authoritative source
  URLs and no unsupported manufacturer thresholds.
- Project defaults are labeled; custom profiles reject invalid units, ranges,
  and threshold ordering.
- Profile snapshots are immutable for a run and changes stale prior results.

## S3-03 - Wall thickness

- Known-thickness boxes and curved shells match geometric truth within declared
  fixture tolerance.
- Samples, opposing hits, skipped counts, confidence, and evidence are present.
- Open, intersecting, non-manifold, and limit cases are not reported as pass.
- FAST/STANDARD/DEEP bounds are measured and enforced.

## S3-04 - Thin features

- Known-diameter cylinders, spikes, stems, fingers, and ornaments classify at
  configured warning/critical boundaries.
- Ambiguous feature regions remain experimental/indeterminate.
- Evidence selection and caps are deterministic.

## S3-05 - Overhangs

- The 0/30/45/60/90 degree truth table passes with build direction changes.
- Downward area and connected-region aggregation are correct.
- Small-face suppression retains counts and does not hide material area.

## S3-06 - Floating components

- Contacting and suspended shells classify correctly under tolerance boundaries.
- Evidence uses neutral support/orientation review wording.
- Main shell, tiny shell, and shell-chain behavior is explicit.

## S3-07 - Build contact

- Broad, multi-region, partial-face, edge, point, none, tilted, and ambiguous
  fixtures pass.
- Contact area, footprint, center-of-mass availability, and stability limits are
  evidenced.
- Stability is labeled heuristic and does not claim physical simulation.

## S3-08 - Scale and volume

- Axis fit, margin, exact-boundary tolerance, and overflow are correct.
- Uniform scale preview is arithmetic only and does not mutate geometry.
- Scale consequences for walls and features produce explicit warnings.

## S3-09 - Orientation recommendations

- Candidate generation is bounded, deterministic, and deduplicated.
- Candidate metrics, trade-offs, confidence, and reasons are serialized.
- No automatic rotation occurs; user approval and stale protection are tested.

## S3-10 - Scoring

- Weights total 100 and score rounding/versioning are deterministic.
- Critical caps, missing-check behavior, failed-check behavior, and confidence
  downgrades pass an explicit matrix.
- A critical report cannot appear safe because of a high numeric score.

## S3-11 - Reports and stale state

- JSON schema and Markdown report validate, are UTF-8/newline-terminated, and
  contain bounded evidence only.
- Geometry, transform, profile, build-direction, and settings changes reject
  stale evidence and issue selection.

## S3-12 - Performance

- Tiny through Extreme policies enforce limits, progress, cancellation, memory,
  and state transitions.
- Deep wall/orientation work on Extreme never runs uncapped.
- Dataset regression does not change existing diagnostics or repair truth.

## S3-13 - Security and safety

- No network runtime, AI call, arbitrary code execution, geometry mutation,
  automatic transform, or cloud dependency is introduced.
- Reports contain no secrets, raw full-mesh payloads, or unsafe paths.
- Product wording does not promise print success.

## S3-14 - Package and release

- Extension package validation passes without changing the extension version.
- Documentation, schemas, profile examples, and release classification are
  complete.
- Golden Benchmark compatibility is retained or intentionally versioned.
