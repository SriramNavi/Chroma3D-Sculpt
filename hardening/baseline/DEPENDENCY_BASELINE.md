# Dependency Baseline

Checkpoint: `v0.8.0-pre-hardening-backup` / `d06e1a05890fe23e77e66f95fc40e0200638a765`.

| Metric | Value |
| --- | --- |
| Modules | 221 |
| Internal dependency edges | 855 |
| External dependency roots | 61 |
| External import edges | 1138 |
| Potential circular components | 0 |
| Statically unreferenced candidates | 82 |
| Service to UI/operator edges | 0 |
| UI/operator to service edges | 45 |
| Cross-subsystem edges | 46 |

## Highest fan-in

| Module | Dependents |
| --- | --- |
| chroma3d_sculpt.metadata | 45 |
| chroma3d_sculpt.models.printability_models | 37 |
| chroma3d_sculpt.models.ai_assistance_models | 24 |
| chroma3d_sculpt.printability_settings | 24 |
| chroma3d_sculpt | 23 |
| chroma3d_sculpt.models.analysis_result | 23 |
| chroma3d_sculpt.models.advanced_preparation_models | 22 |
| chroma3d_sculpt.models.intelligent_optimization_models | 21 |
| chroma3d_sculpt.utilities.context | 19 |
| chroma3d_sculpt.utilities.optimization_signatures | 18 |
| chroma3d_sculpt.models.optimization_models | 17 |
| chroma3d_sculpt.analysis_settings | 16 |

## Highest fan-out

| Module | Dependencies |
| --- | --- |
| tests.blender.test_sprint7_ai_recommendation | 27 |
| manual-tests.sprint7-final.final_validation_runner | 25 |
| tests.blender.test_sprint4_advanced_preparation | 22 |
| manual-tests.sprint4-final.final_validation_runner | 21 |
| tests.blender.test_sprint6_intelligent_optimization | 18 |
| manual-tests.sprint6-final.final_validation_runner | 17 |
| chroma3d_sculpt | 16 |
| chroma3d_sculpt.services.intelligent_optimization_coordinator | 15 |
| manual-tests.sprint3-final.final_validation_runner | 15 |
| chroma3d_sculpt.operators.advanced_preparation | 14 |
| chroma3d_sculpt.services.advanced_preparation_coordinator | 14 |
| chroma3d_sculpt.services.ai_assistance_coordinator | 14 |

## Interpretation

Every zero-static-import item remains `STATICALLY_UNREFERENCED_CANDIDATE`. Registration, reflection, operator IDs, CLI entrypoints, test discovery, package inclusion, schema paths, and documentation contracts must be checked before H1 action.
