# H2 structural simplification report

H2 preserves runtime behavior and public contracts while reducing only
independently demonstrated maintenance risk.

## Measured structural change

| Metric | Frozen H1 | Current H2 | Meaning |
|---|---:|---:|---|
| Suspicious import/reference queue | 50 | 0 unresolved | 43 removed; 7 explicitly retained |
| Critical complexity hotspots | 7 | 7 | No critical state/geometry/test hotspot was refactored for score alone |
| High complexity hotspots | 29 | 28 | One deterministic generator moved to moderate |
| Duplication candidates | 82 | 80 | One exact two-copy implementation was consolidated |
| Python physical LOC | 48,207 | 48,181 | Net `-26`; line reduction was not a target |
| Python modules | 221 | 222 | One printability-specific shared owner added |
| Internal dependency edges | 856 | 858 | Two consumers now depend on the shared owner |
| Package dependency edges | 467 | 469 | Same two explicit package edges |
| Circular components | 0 | 0 | Required invariant preserved |

The module and edge counts increased deliberately: a single
`printability_statistics` owner replaced two byte-equivalent percentile
implementations in overhang and thin-feature analysis. No external dependency
root was added.

## Simplified

- Removed 43 bindings only after AST use, exports, registration, strings,
  tests, tooling, history, and import-side-effect evidence proved them unused.
- Split candidate identity validation and cancellation checks from
  `generate_strategies` into private helpers; ordering, hashes, budgets,
  pruning, and public aliases remain unchanged.
- Consolidated identical percentile labels, rounding, empty behavior, scalar
  units, and mutation-free semantics under a printability-specific owner.

## Deliberately retained

- Six sole internal imports remain `AMBIGUOUS` because removing them could
  change import-time behavior.
- One `datetime` binding remains `DYNAMIC_REFERENCE` because its module builds
  `__all__` from `globals()`.
- 35 critical/high complexity hotspots remain public, stateful,
  geometry-coupled, test-matrix, or deferred validation boundaries.
- One exact six-line cancellation predicate remains local because a new shared
  dependency would cost more than the duplication.
- The remaining duplication candidates retain domain, schema, threshold,
  resource, stale-state, validation, or public-visibility ownership.

No product/package version, schema version, printer/material profile,
validation threshold, operator, panel, property, enum, feature flag, or user
semantics was intentionally changed.
