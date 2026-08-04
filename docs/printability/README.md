# Printability Specification Documents

This directory is the reviewable implementation contract for Sprint 3. It is
documentation only: Sprint 2.8 does not add a runtime engine, operator, repair,
diagnostic, slicer, or package change.

## Reading order

1. [Terminology and result states](TERMINOLOGY_AND_RESULT_STATES.md)
2. [Rule classification](RULE_CLASSIFICATION.md)
3. Measurement methods: [wall thickness](WALL_THICKNESS_METHOD.md),
   [thin features](THIN_FEATURE_METHOD.md), [overhangs](OVERHANG_METHOD.md),
   [floating components](FLOATING_COMPONENTS.md), and [contact](BUILD_PLATE_CONTACT.md)
4. [Scale/build volume](SCALE_AND_BUILD_VOLUME.md) and
   [orientation](ORIENTATION_RECOMMENDATION.md)
5. [Scoring](PRINTABILITY_SCORING.md) and [performance](PERFORMANCE_MODES.md)
6. [Fixtures](VALIDATION_FIXTURES.md) and [acceptance gates](ACCEPTANCE_GATES.md)
7. [Sources](SOURCES.md) and [open questions](OPEN_QUESTIONS.md)

## Contract invariants

- Units are millimetres, square millimetres, cubic millimetres, degrees, or
  seconds unless a field says otherwise.
- Geometry facts are not profile evaluations.
- Thresholds are never presented as universal manufacturing truth.
- Skipped and failed checks are retained in reports.
- Evidence is bounded and tied to current geometry, transform, profile, build
  direction, and settings signatures.
- Orientation and scale are recommendations only; user approval is required.
- The product does not guarantee print success.
