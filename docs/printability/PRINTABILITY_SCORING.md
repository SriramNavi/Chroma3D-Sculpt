# Printability Scoring Contract

## Score meaning

The score is a bounded advisory index from 0 to 100 where higher means fewer
detected risks under the selected profile and completed checks. It is not a
probability, certification, or print-success prediction. A score is shown only
with overall status, confidence, primary reasons, missing checks, skipped
checks, failed checks, and profile/settings snapshots.

## Category weights

| Category | Weight |
|---|---:|
| Topology readiness | 15 |
| Wall-thickness risk | 15 |
| Thin-feature risk | 10 |
| Overhang risk | 15 |
| Floating-component risk | 15 |
| Build-contact risk | 10 |
| Build-volume fit | 10 |
| Orientation confidence | 10 |
| **Total** | **100** |

For each completed category, normalize risk to `[0, 1]` using the category's
declared aggregation method and subtract weighted risk from 100. `PASS` maps to
zero detected risk; warning and critical items map to profile-defined bounded
risk; missing/failed categories are never silently mapped to zero.

## Missing and failed checks

- `NOT_EVALUATED`, `NOT_APPLICABLE`, and `SKIPPED_LIMIT` remain visible in
  `missing_checks` or `skipped_checks` with reasons.
- A skipped required category lowers confidence. The score may be null when the
  remaining coverage is insufficient for an honest aggregate.
- A failed required category sets overall status to `FAILED` or
  `INDETERMINATE` according to report policy and contributes an explicit
  unknown/high-risk marker. It cannot improve the score.
- `NOT_APPLICABLE` contributes no category risk but is listed with process
  rationale.

## Critical caps and status precedence

Status precedence is `FAILED` -> `INDETERMINATE` -> `CRITICAL` -> `WARNING` ->
`PASS`, after `NOT_APPLICABLE`/`NOT_EVALUATED` handling. If any completed risk
item is `CRITICAL`, the numeric score is capped at `59` and overall status
remains `CRITICAL`, even if other categories are low risk. A high score must
never make a critical report appear safe.

Example:

```text
Overall score: 61/100
Overall status: CRITICAL
Confidence: MEDIUM
Primary reason: Three disconnected components do not contact the build plane.
Missing checks: Deep wall sampling (SKIPPED_LIMIT)
```

## Confidence

Start from the lowest confidence among required categories, then record
coverage, profile authority, topology validity, bounded evidence, and skipped or
failed checks. Confidence is `HIGH`, `MEDIUM`, `LOW`, or `UNKNOWN`; it is not a
success probability. Numeric score rounding is half-up to an integer and the
scoring algorithm version is required in the report.
