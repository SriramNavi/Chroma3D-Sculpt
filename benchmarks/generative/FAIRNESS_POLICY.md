# CGB 0.1 Fairness Policy

1. Comparable backends receive the same input references and benchmark track.
2. Exact model versions, adapter versions, parameters, seed support, and quality modes are recorded.
3. Raw provider output is captured before Chroma3D conditioning.
4. Primary evidence is first-shot; no cherry-picking or invisible success-only reruns.
5. `BEST-OF-N` and finalist variance runs are secondary and separately labeled.
6. Smoke3 and Core10 use one attempt by default. Finalist variance may use three only when budget permits.
7. Seeds are recorded where officially supported; cross-family seeds are not treated as equivalent.
8. Provider defaults, custom quality modes, and provider-side post-processing are disclosed separately.
9. Raw and conditioned scorecards remain visible side by side.
10. Failures, timeouts, invalid artifacts, imports, and analyses remain in reliability evidence.
11. Unsupported tracks are `NOT_APPLICABLE`, never numeric zero.
12. Stage order is Smoke3, Core10, finalists, then Full27. Before any live stage, jobs, credits, estimated USD cost, and configured budget are shown.
13. Unknown USD cost stops execution unless an owner explicitly authorizes that unknown-cost stage in addition to all live/spend gates.
