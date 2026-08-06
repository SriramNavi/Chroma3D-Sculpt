# Search Policy

FAST, STANDARD, DEEP, and CUSTOM modes select explicit limits for generated strategies, evaluations, workspace previews, depth, branch factor, permutations, frontier size, wall time, per-strategy time, memory observations, history, and export size. CUSTOM values are still checked against repository safety maxima.

Policies include enabled strategy families, allowed Sprint 5 operations, objective profile, hard/soft constraints, tie-breaking, pruning rules, duplicate/dominance tolerances, deterministic seed, provenance, and a deterministic hash. Boolean-as-number, NaN, infinity, negative, zero-required, unknown-operation, duplicate-ID, conflicting, and hidden experimental values are rejected.

When a budget ends, completed evidence is retained, the session is marked budget-limited, and unevaluated strategies are not failures.
