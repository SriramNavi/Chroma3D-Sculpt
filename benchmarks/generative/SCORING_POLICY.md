# CGB 0.1 Scoring Policy

Primary truth is the raw scorecard:

`SHAPE_FIDELITY`, `GEOMETRY_HEALTH`, `DETAIL`, `TOPOLOGY`, `PRINTABILITY`, `TEXTURE_PBR`, `LATENCY`, `COST`, and `RELIABILITY`.

No universal scalar score is primary. Pareto dominance uses higher-is-better for all quality/reliability dimensions and lower-is-better for latency/cost. Missing, unsupported, skipped, indeterminate, or failed dimensions never become zero-quality observations.

Transparent v0.1 helpers:

- normalized Chamfer = mean of generated-to-ground-truth and ground-truth-to-generated nearest surface-sample distances, divided by ground-truth bounding diagonal;
- F-score thresholds = 1%, 2%, and 5% of that diagonal;
- geometry health = `100 - min(100, 0.02*boundary_edges + 2*high_incidence_edges + 0.5*degenerate_faces + 3*(components-1))`;
- silhouette = binary triangle-mask IoU for each canonical view, plus mean and worst view;
- detail = experimental triangle-density and worst-silhouette proxy, excluded from primary ranking;
- texture/PBR for GT27 = capability-only, because the ground truth has no texture labels.

## PROJECT_DEFAULT

| Dimension | Weight |
|---|---:|
| Shape/reference fidelity | 30 |
| Geometry health | 25 |
| Fine detail | 15 |
| Topology/editability | 10 |
| Printability | 10 |
| Reliability | 5 |
| Latency | 2.5 |
| Cost | 2.5 |

Total: 100. This profile is provisional and **not scientifically validated**. PBR remains separate for untextured GT27.
