# Pareto Frontier

The frontier compares objective vectors using an explicit minimize/maximize direction per metric and a configured tolerance. A strategy dominates another only when it is no worse on every known comparable objective and better on at least one, after hard-constraint feasibility is considered.

Equal vectors are handled deterministically. Unknown or skipped evidence cannot dominate known valid evidence. New critical defects prevent a strategy from dominating a safe strategy. The frontier is bounded and records dominated IDs, pairwise reasons, stable ordering, and limitations; it does not claim a global optimum.
