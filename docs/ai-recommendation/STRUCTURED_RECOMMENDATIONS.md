# Structured Recommendations

The provider must return exactly one strict JSON object. Supported classes are `SELECT_EXISTING_STRATEGY`, `SELECT_EXISTING_CANDIDATE`, `SELECT_EXISTING_PLAN`, `CONSIDER_ALTERNATIVE`, `REQUEST_MORE_EVIDENCE`, `NO_ACTION_RECOMMENDED`, and `CANNOT_RECOMMEND`.

Local validation checks byte size, strict UTF-8, JSON-only content, duplicate/non-finite/depth/node limits, exact fields and enums, bounded text/arrays, prohibited code/shell/path/URL/policy-bypass/guarantee content, exact evidence IDs, exact disclosed target ID/fingerprint, source/current-state truth, local feasibility, operation policy, and exact operation/candidate/canonical parameter hashes. Values are never repaired or clamped.

Provider confidence is only a hint. Product confidence is derived locally from current evidence completeness, hard failures/unknowns, target resolution, prerequisites and limitations. Provider prose cannot establish geometry, cultural/iconographic, printability, manufacturing, or physical correctness.
