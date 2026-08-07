# H2 complexity hotspot triage

Status: `PASS`. Frozen H1 queue: `7 critical + 29 high = 36`; triaged: `36`.

Dispositions: `DEFER=17`, `KEEP_COMPLEX=10`, `PUBLIC_BOUNDARY=5`, `REFACTOR_NOW=1`, `STATEFUL_RISK=3`.

Only `strategy_generator.generate_strategies` is selected. The bounded transformation extracts private candidate validation and cancellation logic; public identity, ordering, budgets, pruning, hashes, and state ownership remain unchanged.

| Rank | H1 priority | Path | Disposition | Score | Ownership |
|---:|---|---|---|---:|---|
| 1 | CRITICAL_REVIEW_PRIORITY | `tests/blender/test_sprint4_advanced_preparation.py` | KEEP_COMPLEX | 505.7 | VALIDATION_ONLY |
| 2 | CRITICAL_REVIEW_PRIORITY | `tests/blender/test_sprint3_printability.py` | KEEP_COMPLEX | 460.1 | VALIDATION_ONLY |
| 3 | CRITICAL_REVIEW_PRIORITY | `manual-tests/benchmarks/run_golden_benchmark.py` | DEFER | 379.6 | VALIDATION_ONLY |
| 4 | CRITICAL_REVIEW_PRIORITY | `tests/blender/test_sprint6_intelligent_optimization.py` | KEEP_COMPLEX | 248.85 | VALIDATION_ONLY |
| 5 | CRITICAL_REVIEW_PRIORITY | `blender_addon/chroma3d_sculpt/services/repair_operations.py` | STATEFUL_RISK | 225.9 | GEOMETRY_MUTATION |
| 6 | CRITICAL_REVIEW_PRIORITY | `manual-tests/sprint5-final/final_validation_runner.py` | DEFER | 210.05 | VALIDATION_ONLY |
| 7 | CRITICAL_REVIEW_PRIORITY | `manual-tests/sprint2-final/final_validation_runner.py` | DEFER | 199.6 | VALIDATION_ONLY |
| 8 | HIGH_REVIEW_PRIORITY | `blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py` | PUBLIC_BOUNDARY | 185.2 | SERIALIZED_CONTRACT |
| 9 | HIGH_REVIEW_PRIORITY | `blender_addon/chroma3d_sculpt/services/ai_assistance_coordinator.py` | STATEFUL_RISK | 180.6 | SESSION_OR_WORKSPACE_STATE |
| 10 | HIGH_REVIEW_PRIORITY | `manual-tests/sprint4-final/final_validation_runner.py` | DEFER | 177.3 | VALIDATION_ONLY |
| 11 | HIGH_REVIEW_PRIORITY | `manual-tests/sprint3-final/final_validation_runner.py` | DEFER | 175.35 | VALIDATION_ONLY |
| 12 | HIGH_REVIEW_PRIORITY | `blender_addon/chroma3d_sculpt/models/ai_assistance_models.py` | PUBLIC_BOUNDARY | 171.2 | SERIALIZED_CONTRACT |
| 13 | HIGH_REVIEW_PRIORITY | `manual-tests/sprint1-final/final_validation_runner.py` | DEFER | 161.85 | VALIDATION_ONLY |
| 14 | HIGH_REVIEW_PRIORITY | `manual-tests/sprint6/run_historical_regression.py` | DEFER | 151.55 | VALIDATION_ONLY |
| 15 | HIGH_REVIEW_PRIORITY | `manual-tests/run_acceptance_gates.py` | DEFER | 145.0 | VALIDATION_ONLY |
| 16 | HIGH_REVIEW_PRIORITY | `blender_addon/chroma3d_sculpt/services/intelligent_optimization_coordinator.py` | STATEFUL_RISK | 144.4 | SESSION_OR_WORKSPACE_STATE |
| 17 | HIGH_REVIEW_PRIORITY | `blender_addon/chroma3d_sculpt/services/topology_analyzer.py` | KEEP_COMPLEX | 135.3 | READ_ONLY_GEOMETRY_EVIDENCE |
| 18 | HIGH_REVIEW_PRIORITY | `manual-tests/datasets/validate_statue_dataset.py` | DEFER | 134.55 | VALIDATION_ONLY |
| 19 | HIGH_REVIEW_PRIORITY | `blender_addon/chroma3d_sculpt/services/shell_analyzer.py` | KEEP_COMPLEX | 128.35 | READ_ONLY_GEOMETRY_EVIDENCE |
| 20 | HIGH_REVIEW_PRIORITY | `manual-tests/acceptance_gate_runner.py` | DEFER | 125.95 | VALIDATION_ONLY |
| 21 | HIGH_REVIEW_PRIORITY | `blender_addon/chroma3d_sculpt/models/optimization_models.py` | PUBLIC_BOUNDARY | 121.05 | SERIALIZED_CONTRACT |
| 22 | HIGH_REVIEW_PRIORITY | `manual-tests/sprint3/sprint3_acceptance_runner.py` | DEFER | 118.85 | VALIDATION_ONLY |
| 23 | HIGH_REVIEW_PRIORITY | `blender_addon/chroma3d_sculpt/services/printability_coordinator.py` | KEEP_COMPLEX | 117.15 | SESSION_OR_WORKSPACE_STATE |
| 24 | HIGH_REVIEW_PRIORITY | `blender_addon/chroma3d_sculpt/services/strategy_generator.py` | REFACTOR_NOW | 117.15 | PURE_DETERMINISTIC_GENERATION |
| 25 | HIGH_REVIEW_PRIORITY | `blender_addon/chroma3d_sculpt/services/mesh_analyzer.py` | KEEP_COMPLEX | 116.85 | READ_ONLY_GEOMETRY_EVIDENCE |
| 26 | HIGH_REVIEW_PRIORITY | `manual-tests/datasets/acquire_statue_dataset.py` | DEFER | 113.5 | VALIDATION_ONLY |
| 27 | HIGH_REVIEW_PRIORITY | `blender_addon/chroma3d_sculpt/models/printability_models.py` | PUBLIC_BOUNDARY | 112.65 | SERIALIZED_CONTRACT |
| 28 | HIGH_REVIEW_PRIORITY | `manual-tests/sprint7-final/final_validation_runner.py` | DEFER | 105.5 | VALIDATION_ONLY |
| 29 | HIGH_REVIEW_PRIORITY | `manual-tests/sprint7-specification/validate_sprint7_specification.py` | DEFER | 101.5 | VALIDATION_ONLY |
| 30 | HIGH_REVIEW_PRIORITY | `manual-tests/benchmarks/verify_golden_baseline.py` | DEFER | 99.2 | VALIDATION_ONLY |
| 31 | HIGH_REVIEW_PRIORITY | `blender_addon/chroma3d_sculpt/ui/panels.py` | PUBLIC_BOUNDARY | 85.05 | UI_RENDERING |
| 32 | HIGH_REVIEW_PRIORITY | `blender_addon/chroma3d_sculpt/utilities/boundary_loops.py` | KEEP_COMPLEX | 82.15 | READ_ONLY_GEOMETRY_EVIDENCE |
| 33 | HIGH_REVIEW_PRIORITY | `tests/blender/test_sprint2_repair.py` | KEEP_COMPLEX | 81.65 | VALIDATION_ONLY |
| 34 | HIGH_REVIEW_PRIORITY | `tests/blender/test_sprint7_ai_recommendation.py` | KEEP_COMPLEX | 77.35 | VALIDATION_ONLY |
| 35 | HIGH_REVIEW_PRIORITY | `manual-tests/datasets/verify_statue_dataset.py` | DEFER | 67.7 | VALIDATION_ONLY |
| 36 | HIGH_REVIEW_PRIORITY | `manual-tests/sprint2.7/prepare_release_staging.py` | DEFER | 63.1 | VALIDATION_ONLY |
