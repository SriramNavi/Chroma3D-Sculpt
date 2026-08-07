# H2 duplication triage

Status: `PASS`. Frozen H1 candidates: `82`; triaged: `82`.

Classifications: `EXACT_SHARED_SEMANTICS=2`, `INTENTIONAL_DOMAIN_DUPLICATION=16`, `SIMILAR_BUT_DIFFERENT=10`, `TEST_FIXTURE_DUPLICATION=42`, `TOO_RISKY=12`.

## Selected exact-semantic consolidation

- `H1-DUP-0013`: `blender_addon/chroma3d_sculpt/services/overhang_analysis.py:_percentiles | blender_addon/chroma3d_sculpt/services/thin_features.py:_percentiles`.
- Owner: `chroma3d_sculpt.services.printability_statistics.percentiles`.
- Proof: identical private input/output/error/rounding/unit/threshold/stale/mutation/public behavior.

## Deliberately retained exact-semantic candidate

- `H1-DUP-0014`: `blender_addon/chroma3d_sculpt/services/strategy_evaluator.py:cancelled | blender_addon/chroma3d_sculpt/services/strategy_generator.py:cancelled`.
- Reason: a new cross-owner cancellation utility would add dependency surface for six private lines.

All other candidates lack complete semantic equivalence or cross runtime, domain, state, schema, validation, or resource-ownership boundaries and remain local.
