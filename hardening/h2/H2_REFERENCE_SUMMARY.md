# H2 suspicious-reference dispositions

Status: `PASS`

Frozen H1 candidates: `50`; resolved: `50`; removed: `43`; retained: `7`.

Classifications: `AMBIGUOUS=6`, `DYNAMIC_REFERENCE=1`, `PROVEN_UNUSED=43`.

| ID | File | Binding | Disposition | Removed | Batch |
|---|---|---|---|---:|---|
| H1-IMP-0001 | `blender_addon/chroma3d_sculpt/intelligent_optimization_settings.py` | `field` | PROVEN_UNUSED | yes | H2-R1 |
| H1-IMP-0002 | `blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py` | `datetime` | DYNAMIC_REFERENCE | no | - |
| H1-IMP-0003 | `blender_addon/chroma3d_sculpt/operators/advanced_preparation.py` | `get_batch_result` | PROVEN_UNUSED | yes | H2-R2 |
| H1-IMP-0004 | `blender_addon/chroma3d_sculpt/operators/advanced_preparation.py` | `get_preparation_result` | PROVEN_UNUSED | yes | H2-R2 |
| H1-IMP-0005 | `blender_addon/chroma3d_sculpt/operators/intelligent_optimization.py` | `BoolProperty` | PROVEN_UNUSED | yes | H2-R1 |
| H1-IMP-0006 | `blender_addon/chroma3d_sculpt/operators/intelligent_optimization.py` | `Path` | PROVEN_UNUSED | yes | H2-R1 |
| H1-IMP-0007 | `blender_addon/chroma3d_sculpt/operators/intelligent_optimization.py` | `SearchBudget` | AMBIGUOUS | no | - |
| H1-IMP-0008 | `blender_addon/chroma3d_sculpt/operators/intelligent_optimization.py` | `select_strategy` | PROVEN_UNUSED | yes | H2-R1 |
| H1-IMP-0009 | `blender_addon/chroma3d_sculpt/operators/optimization.py` | `Path` | PROVEN_UNUSED | yes | H2-R3 |
| H1-IMP-0010 | `blender_addon/chroma3d_sculpt/operators/optimization.py` | `get_workspace` | PROVEN_UNUSED | yes | H2-R3 |
| H1-IMP-0011 | `blender_addon/chroma3d_sculpt/operators/optimization.py` | `sanitize_optimization_filename` | PROVEN_UNUSED | yes | H2-R3 |
| H1-IMP-0012 | `blender_addon/chroma3d_sculpt/operators/repair.py` | `RepairSessionStatus` | PROVEN_UNUSED | yes | H2-R4 |
| H1-IMP-0013 | `blender_addon/chroma3d_sculpt/services/ai_assistance_report.py` | `Mapping` | PROVEN_UNUSED | yes | H2-R5 |
| H1-IMP-0014 | `blender_addon/chroma3d_sculpt/services/ai_assistance_report.py` | `json` | PROVEN_UNUSED | yes | H2-R5 |
| H1-IMP-0015 | `blender_addon/chroma3d_sculpt/services/ai_assistance_report.py` | `recommendation_markdown` | AMBIGUOUS | no | - |
| H1-IMP-0016 | `blender_addon/chroma3d_sculpt/services/ai_assistance_session.py` | `replace` | PROVEN_UNUSED | yes | H2-R5 |
| H1-IMP-0017 | `blender_addon/chroma3d_sculpt/services/constraint_engine.py` | `json` | PROVEN_UNUSED | yes | H2-R7 |
| H1-IMP-0018 | `blender_addon/chroma3d_sculpt/services/constraint_engine.py` | `sha256` | PROVEN_UNUSED | yes | H2-R7 |
| H1-IMP-0019 | `blender_addon/chroma3d_sculpt/services/context_budget.py` | `Mapping` | PROVEN_UNUSED | yes | H2-R6 |
| H1-IMP-0020 | `blender_addon/chroma3d_sculpt/services/fake_ai_provider.py` | `dataclass` | PROVEN_UNUSED | yes | H2-R5 |
| H1-IMP-0021 | `blender_addon/chroma3d_sculpt/services/intelligent_optimization_audit.py` | `plain_value` | PROVEN_UNUSED | yes | H2-R8 |
| H1-IMP-0022 | `blender_addon/chroma3d_sculpt/services/intelligent_optimization_coordinator.py` | `constraint_set_hash` | AMBIGUOUS | no | - |
| H1-IMP-0023 | `blender_addon/chroma3d_sculpt/services/intelligent_optimization_coordinator.py` | `frontier_is_current` | PROVEN_UNUSED | yes | H2-R8 |
| H1-IMP-0024 | `blender_addon/chroma3d_sculpt/services/intelligent_optimization_coordinator.py` | `sprint5_policy_hash` | AMBIGUOUS | no | - |
| H1-IMP-0025 | `blender_addon/chroma3d_sculpt/services/intelligent_optimization_session.py` | `DISPLAY_VERSION` | PROVEN_UNUSED | yes | H2-R8 |
| H1-IMP-0026 | `blender_addon/chroma3d_sculpt/services/intelligent_optimization_session.py` | `StrategyEvaluation` | PROVEN_UNUSED | yes | H2-R8 |
| H1-IMP-0027 | `blender_addon/chroma3d_sculpt/services/intelligent_optimization_session.py` | `get_controlled_workspace` | PROVEN_UNUSED | yes | H2-R8 |
| H1-IMP-0028 | `blender_addon/chroma3d_sculpt/services/intelligent_optimization_session.py` | `sha256` | PROVEN_UNUSED | yes | H2-R8 |
| H1-IMP-0029 | `blender_addon/chroma3d_sculpt/services/openai_provider.py` | `Mapping` | PROVEN_UNUSED | yes | H2-R6 |
| H1-IMP-0030 | `blender_addon/chroma3d_sculpt/services/optimization_comparison.py` | `uuid4` | PROVEN_UNUSED | yes | H2-R9 |
| H1-IMP-0031 | `blender_addon/chroma3d_sculpt/services/optimization_coordinator.py` | `OptimizationSettings` | AMBIGUOUS | no | - |
| H1-IMP-0032 | `blender_addon/chroma3d_sculpt/services/optimization_coordinator.py` | `compare_objects` | PROVEN_UNUSED | yes | H2-R9 |
| H1-IMP-0033 | `blender_addon/chroma3d_sculpt/services/optimization_plan.py` | `Mapping` | PROVEN_UNUSED | yes | H2-R9 |
| H1-IMP-0034 | `blender_addon/chroma3d_sculpt/services/optimization_session.py` | `build_objective_snapshot` | PROVEN_UNUSED | yes | H2-R10 |
| H1-IMP-0035 | `blender_addon/chroma3d_sculpt/services/optimization_workspace.py` | `deepcopy` | PROVEN_UNUSED | yes | H2-R10 |
| H1-IMP-0036 | `blender_addon/chroma3d_sculpt/services/provider_transport.py` | `json` | PROVEN_UNUSED | yes | H2-R6 |
| H1-IMP-0037 | `blender_addon/chroma3d_sculpt/services/repair_session.py` | `RepairDecision` | PROVEN_UNUSED | yes | H2-R4 |
| H1-IMP-0038 | `blender_addon/chroma3d_sculpt/services/search_policy.py` | `ConstraintKind` | PROVEN_UNUSED | yes | H2-R7 |
| H1-IMP-0039 | `blender_addon/chroma3d_sculpt/services/search_policy.py` | `ConstraintSet` | PROVEN_UNUSED | yes | H2-R7 |
| H1-IMP-0040 | `blender_addon/chroma3d_sculpt/services/search_policy.py` | `ConstraintSeverity` | PROVEN_UNUSED | yes | H2-R7 |
| H1-IMP-0041 | `blender_addon/chroma3d_sculpt/services/search_policy.py` | `OptimizationConstraint` | PROVEN_UNUSED | yes | H2-R7 |
| H1-IMP-0042 | `blender_addon/chroma3d_sculpt/services/search_policy.py` | `stable_hash` | PROVEN_UNUSED | yes | H2-R7 |
| H1-IMP-0043 | `blender_addon/chroma3d_sculpt/services/strategy_evaluator.py` | `Iterable` | PROVEN_UNUSED | yes | H2-R7 |
| H1-IMP-0044 | `blender_addon/chroma3d_sculpt/services/strategy_evaluator.py` | `Sequence` | PROVEN_UNUSED | yes | H2-R7 |
| H1-IMP-0045 | `blender_addon/chroma3d_sculpt/services/strategy_generator.py` | `Iterable` | PROVEN_UNUSED | yes | H2-R11 |
| H1-IMP-0046 | `blender_addon/chroma3d_sculpt/services/strategy_generator.py` | `OptimizationOperationType` | PROVEN_UNUSED | yes | H2-R11 |
| H1-IMP-0047 | `blender_addon/chroma3d_sculpt/services/strategy_generator.py` | `StrategyState` | PROVEN_UNUSED | yes | H2-R11 |
| H1-IMP-0048 | `blender_addon/chroma3d_sculpt/services/thin_features.py` | `math` | PROVEN_UNUSED | yes | H2-R12 |
| H1-IMP-0049 | `blender_addon/chroma3d_sculpt/ui/optimization_panel.py` | `OptimizationSessionState` | AMBIGUOUS | no | - |
| H1-IMP-0050 | `blender_addon/chroma3d_sculpt/ui/repair_panel.py` | `RepairSessionStatus` | PROVEN_UNUSED | yes | H2-R4 |

Only `PROVEN_UNUSED` bindings are removal-eligible. Analyzer uncertainty remains retained.
