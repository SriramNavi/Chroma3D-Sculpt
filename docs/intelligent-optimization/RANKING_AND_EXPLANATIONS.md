# Ranking and Explanations

Supported methods include weighted sum, weighted Tchebycheff, lexicographic, constraint-first, balanced distance-to-ideal, user priority, fidelity-first, minimum supports, fit-to-printer, stable base, and lightweight. Hard-constraint filtering precedes ranking.

Tie-breaking is explicit: fewer hard warnings, fewer critical regressions, higher confidence, higher fidelity, fewer operations, lower runtime estimate, then stable fingerprint/ID. Each explanation states why a strategy was generated and feasible, improvements, regressions, passed hard constraints, soft warnings, ranking reasons, alternatives, measured/estimated/skipped evidence, approvals, confidence, runtime estimate, and limitations.

Recommendation wording is limited to “recommended under current objectives” or “top-ranked within evaluated bounded search.” It never says globally optimal or print-ready.
