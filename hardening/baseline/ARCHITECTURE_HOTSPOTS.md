# Architecture Hotspots

Checkpoint: `v0.8.0-pre-hardening-backup` / `d06e1a05890fe23e77e66f95fc40e0200638a765`.

| Classification | Count |
| --- | --- |
| CRITICAL_REVIEW_PRIORITY | 7 |
| HIGH_REVIEW_PRIORITY | 30 |
| LOW | 116 |
| MODERATE | 68 |

## Top review targets

| Path | Class | LOC | Branches | Depth | Functions | Classes | Fan-in | Fan-out | Max function |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| manual-tests/benchmarks/run_golden_benchmark.py | CRITICAL_REVIEW_PRIORITY | 2040 | 176 | 5 | 40 | 0 | 0 | 5 | 433 |
| manual-tests/sprint2-final/final_validation_runner.py | CRITICAL_REVIEW_PRIORITY | 1088 | 112 | 3 | 44 | 0 | 0 | 11 | 81 |
| tests/blender/test_sprint6_intelligent_optimization.py | CRITICAL_REVIEW_PRIORITY | 849 | 60 | 7 | 22 | 1 | 1 | 18 | 567 |
| manual-tests/sprint5-final/final_validation_runner.py | CRITICAL_REVIEW_PRIORITY | 725 | 134 | 4 | 36 | 0 | 0 | 13 | 94 |
| blender_addon/chroma3d_sculpt/services/repair_operations.py | CRITICAL_REVIEW_PRIORITY | 510 | 141 | 6 | 21 | 1 | 6 | 4 | 62 |
| tests/blender/test_sprint3_printability.py | CRITICAL_REVIEW_PRIORITY | 486 | 153 | 110 | 14 | 1 | 2 | 14 | 234 |
| tests/blender/test_sprint4_advanced_preparation.py | CRITICAL_REVIEW_PRIORITY | 470 | 160 | 120 | 10 | 1 | 1 | 22 | 296 |
| manual-tests/sprint4-final/final_validation_runner.py | HIGH_REVIEW_PRIORITY | 942 | 86 | 4 | 32 | 0 | 0 | 21 | 76 |
| blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | HIGH_REVIEW_PRIORITY | 856 | 83 | 3 | 24 | 36 | 21 | 0 | 37 |
| manual-tests/sprint1-final/final_validation_runner.py | HIGH_REVIEW_PRIORITY | 849 | 90 | 3 | 34 | 0 | 0 | 7 | 82 |
| manual-tests/sprint3-final/final_validation_runner.py | HIGH_REVIEW_PRIORITY | 847 | 95 | 4 | 26 | 0 | 0 | 15 | 75 |
| manual-tests/datasets/validate_statue_dataset.py | HIGH_REVIEW_PRIORITY | 835 | 64 | 3 | 24 | 0 | 0 | 0 | 114 |
| manual-tests/acceptance_gate_runner.py | HIGH_REVIEW_PRIORITY | 823 | 54 | 3 | 31 | 0 | 0 | 8 | 84 |
| manual-tests/datasets/acquire_statue_dataset.py | HIGH_REVIEW_PRIORITY | 766 | 40 | 6 | 12 | 1 | 0 | 0 | 116 |
| blender_addon/chroma3d_sculpt/models/ai_assistance_models.py | HIGH_REVIEW_PRIORITY | 664 | 77 | 3 | 24 | 22 | 24 | 0 | 30 |
| tests/blender/test_sprint2_repair.py | HIGH_REVIEW_PRIORITY | 655 | 29 | 2 | 72 | 1 | 0 | 10 | 22 |
| blender_addon/chroma3d_sculpt/models/printability_models.py | HIGH_REVIEW_PRIORITY | 609 | 11 | 1 | 21 | 33 | 37 | 0 | 36 |
| manual-tests/run_acceptance_gates.py | HIGH_REVIEW_PRIORITY | 600 | 72 | 3 | 14 | 0 | 0 | 1 | 180 |
| manual-tests/sprint7-specification/validate_sprint7_specification.py | HIGH_REVIEW_PRIORITY | 530 | 57 | 4 | 21 | 0 | 0 | 0 | 50 |
| blender_addon/chroma3d_sculpt/models/optimization_models.py | HIGH_REVIEW_PRIORITY | 525 | 40 | 2 | 16 | 27 | 17 | 0 | 44 |
| tests/blender/test_sprint7_ai_recommendation.py | HIGH_REVIEW_PRIORITY | 523 | 17 | 2 | 73 | 1 | 0 | 27 | 16 |
| blender_addon/chroma3d_sculpt/services/repair_coordinator.py | HIGH_REVIEW_PRIORITY | 521 | 59 | 3 | 17 | 0 | 5 | 10 | 82 |
| manual-tests/sprint7-final/final_validation_runner.py | HIGH_REVIEW_PRIORITY | 506 | 38 | 4 | 26 | 0 | 0 | 25 | 46 |
| manual-tests/sprint3/sprint3_acceptance_runner.py | HIGH_REVIEW_PRIORITY | 501 | 47 | 5 | 11 | 0 | 0 | 6 | 154 |
| blender_addon/chroma3d_sculpt/services/ai_assistance_coordinator.py | HIGH_REVIEW_PRIORITY | 488 | 93 | 3 | 20 | 0 | 6 | 14 | 61 |
| manual-tests/sprint6/run_historical_regression.py | HIGH_REVIEW_PRIORITY | 483 | 95 | 5 | 14 | 1 | 0 | 0 | 112 |
| manual-tests/benchmarks/verify_golden_baseline.py | HIGH_REVIEW_PRIORITY | 476 | 29 | 5 | 10 | 0 | 0 | 0 | 182 |
| blender_addon/chroma3d_sculpt/services/mesh_analyzer.py | HIGH_REVIEW_PRIORITY | 469 | 24 | 1 | 10 | 1 | 10 | 12 | 227 |
| blender_addon/chroma3d_sculpt/services/topology_analyzer.py | HIGH_REVIEW_PRIORITY | 342 | 71 | 6 | 6 | 1 | 3 | 2 | 151 |
| blender_addon/chroma3d_sculpt/services/strategy_generator.py | HIGH_REVIEW_PRIORITY | 341 | 53 | 5 | 17 | 0 | 4 | 3 | 151 |
| blender_addon/chroma3d_sculpt/services/intelligent_optimization_coordinator.py | HIGH_REVIEW_PRIORITY | 336 | 65 | 3 | 19 | 0 | 10 | 15 | 33 |
| blender_addon/chroma3d_sculpt/services/shell_analyzer.py | HIGH_REVIEW_PRIORITY | 315 | 55 | 4 | 4 | 2 | 3 | 4 | 213 |
| blender_addon/chroma3d_sculpt/services/printability_coordinator.py | HIGH_REVIEW_PRIORITY | 263 | 20 | 1 | 2 | 0 | 7 | 14 | 180 |
| manual-tests/datasets/verify_statue_dataset.py | HIGH_REVIEW_PRIORITY | 230 | 19 | 2 | 5 | 0 | 0 | 0 | 166 |
| blender_addon/chroma3d_sculpt/ui/panels.py | HIGH_REVIEW_PRIORITY | 197 | 33 | 3 | 3 | 1 | 2 | 4 | 151 |
| manual-tests/sprint2.7/prepare_release_staging.py | HIGH_REVIEW_PRIORITY | 178 | 12 | 7 | 3 | 0 | 0 | 1 | 136 |
| blender_addon/chroma3d_sculpt/utilities/boundary_loops.py | HIGH_REVIEW_PRIORITY | 123 | 37 | 7 | 3 | 0 | 4 | 2 | 95 |
| manual-tests/sprint2/sprint2_acceptance_runner.py | MODERATE | 461 | 36 | 2 | 24 | 0 | 0 | 10 | 42 |
| manual-tests/sprint1/sprint1_acceptance_runner.py | MODERATE | 433 | 34 | 2 | 24 | 0 | 0 | 6 | 51 |
| manual-tests/sprint3-final/run_final_validation.py | MODERATE | 429 | 34 | 4 | 7 | 0 | 0 | 0 | 99 |

These deterministic bands prioritize review only. High metrics are not defects and do not require refactoring without behavioral evidence.
