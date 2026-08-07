# Dead-Code Candidate Baseline

Checkpoint: `v0.8.0-pre-hardening-backup` / `d06e1a05890fe23e77e66f95fc40e0200638a765`.

| Classification | Count |
| --- | --- |
| CONFIRMED_REFERENCED | 886 |
| DEV_TOOL_ONLY | 2 |
| LEGACY_COMPATIBILITY | 2 |
| REFLECTION_REFERENCED | 1574 |
| REGISTRATION_REFERENCED | 1396 |
| STATICALLY_UNREFERENCED_CANDIDATE | 627 |
| TEST_ONLY | 965 |

## Static candidates

| Symbol | File | Static refs | Test refs | Package | Confidence | H1 action |
| --- | --- | --- | --- | --- | --- | --- |
| PERFORMANCE_REGISTRY_SCHEMA_VERSION | blender_addon/chroma3d_sculpt/metadata.py | 0 | 0 | True | LOW | INVESTIGATE |
| OPTIMIZATION_SESSION_SCHEMA_VERSION | blender_addon/chroma3d_sculpt/metadata.py | 0 | 0 | True | LOW | INVESTIGATE |
| OPTIMIZATION_AUDIT_SCHEMA_VERSION | blender_addon/chroma3d_sculpt/metadata.py | 0 | 0 | True | LOW | INVESTIGATE |
| OPTIMIZATION_COMPARISON_SCHEMA_VERSION | blender_addon/chroma3d_sculpt/metadata.py | 0 | 0 | True | LOW | INVESTIGATE |
| OPTIMIZATION_CANDIDATE_SCHEMA_VERSION | blender_addon/chroma3d_sculpt/metadata.py | 0 | 0 | True | LOW | INVESTIGATE |
| STRATEGY_RANKING_SCHEMA_VERSION | blender_addon/chroma3d_sculpt/metadata.py | 0 | 0 | True | LOW | INVESTIGATE |
| STRATEGY_EXPLANATION_SCHEMA_VERSION | blender_addon/chroma3d_sculpt/metadata.py | 0 | 0 | True | LOW | INVESTIGATE |
| INTELLIGENT_OPTIMIZATION_AUDIT_SCHEMA_VERSION | blender_addon/chroma3d_sculpt/metadata.py | 0 | 0 | True | LOW | INVESTIGATE |
| MAINTAINER | blender_addon/chroma3d_sculpt/metadata.py | 0 | 0 | True | LOW | INVESTIGATE |
| TAGLINE | blender_addon/chroma3d_sculpt/metadata.py | 0 | 0 | True | LOW | INVESTIGATE |
| LICENSE_ID | blender_addon/chroma3d_sculpt/metadata.py | 0 | 0 | True | LOW | INVESTIGATE |
| PerformanceLimit.expected_memory_class | blender_addon/chroma3d_sculpt/models/advanced_preparation_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| BridgeRiskRegion.profile_material_modifier | blender_addon/chroma3d_sculpt/models/advanced_preparation_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| SupportRiskRegion.total_area_percent | blender_addon/chroma3d_sculpt/models/advanced_preparation_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| AdvancedScaleRecommendation.sampled_scale_scores | blender_addon/chroma3d_sculpt/models/advanced_preparation_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| AdvancedPreparationResult.preparation_run_id | blender_addon/chroma3d_sculpt/models/advanced_preparation_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| BatchPreparationResult.batch_id | blender_addon/chroma3d_sculpt/models/advanced_preparation_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| PrintabilityBaselineRecord.resin_advisory_states | blender_addon/chroma3d_sculpt/models/advanced_preparation_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| ProviderSettings.consent_state | blender_addon/chroma3d_sculpt/models/ai_assistance_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| ProviderExchange.redaction_summary | blender_addon/chroma3d_sculpt/models/ai_assistance_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| AssistanceSession.delegated_session_id | blender_addon/chroma3d_sculpt/models/ai_assistance_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| AssistanceReport.report_id | blender_addon/chroma3d_sculpt/models/ai_assistance_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| AssistanceReport.provider_exchange | blender_addon/chroma3d_sculpt/models/ai_assistance_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| AssistanceAudit.audit_id | blender_addon/chroma3d_sculpt/models/ai_assistance_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| AssistanceAudit.provider_exchange | blender_addon/chroma3d_sculpt/models/ai_assistance_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| ObjectMetadata.object_type | blender_addon/chroma3d_sculpt/models/analysis_result.py | 0 | 0 | True | LOW | INVESTIGATE |
| ObjectMetadata.collection_names | blender_addon/chroma3d_sculpt/models/analysis_result.py | 0 | 0 | True | LOW | INVESTIGATE |
| ObjectMetadata.blend_file_unsaved | blender_addon/chroma3d_sculpt/models/analysis_result.py | 0 | 0 | True | LOW | INVESTIGATE |
| ObjectMetadata.analysis_source | blender_addon/chroma3d_sculpt/models/analysis_result.py | 0 | 0 | True | LOW | INVESTIGATE |
| ObjectMetadata.modifiers_evaluated | blender_addon/chroma3d_sculpt/models/analysis_result.py | 0 | 0 | True | LOW | INVESTIGATE |
| GeometryMetrics.loop_count | blender_addon/chroma3d_sculpt/models/analysis_result.py | 0 | 0 | True | LOW | INVESTIGATE |
| GeometryMetrics.metric_source | blender_addon/chroma3d_sculpt/models/analysis_result.py | 0 | 0 | True | LOW | INVESTIGATE |
| GeometryMetrics.triangle_source | blender_addon/chroma3d_sculpt/models/analysis_result.py | 0 | 0 | True | LOW | INVESTIGATE |
| TopologyMetrics.disconnected_shells | blender_addon/chroma3d_sculpt/models/analysis_result.py | 0 | 0 | True | LOW | INVESTIGATE |
| ShellMetrics.boundary_edge_count | blender_addon/chroma3d_sculpt/models/analysis_result.py | 0 | 0 | True | LOW | INVESTIGATE |
| ShellMetrics.non_manifold_edge_count | blender_addon/chroma3d_sculpt/models/analysis_result.py | 0 | 0 | True | LOW | INVESTIGATE |
| ShellMetrics.centroid_mm | blender_addon/chroma3d_sculpt/models/analysis_result.py | 0 | 0 | True | LOW | INVESTIGATE |
| ShellMetrics.diagnostic_notes | blender_addon/chroma3d_sculpt/models/analysis_result.py | 0 | 0 | True | LOW | INVESTIGATE |
| SurfaceVolumeMetrics.surface_area_status | blender_addon/chroma3d_sculpt/models/analysis_result.py | 0 | 0 | True | LOW | INVESTIGATE |
| SurfaceVolumeMetrics.reliable_volume_shell_count | blender_addon/chroma3d_sculpt/models/analysis_result.py | 0 | 0 | True | LOW | INVESTIGATE |
| SurfaceVolumeMetrics.unavailable_volume_shell_count | blender_addon/chroma3d_sculpt/models/analysis_result.py | 0 | 0 | True | LOW | INVESTIGATE |
| ContainmentEvidence.broad_phase_bbox_contained | blender_addon/chroma3d_sculpt/models/analysis_result.py | 0 | 0 | True | LOW | INVESTIGATE |
| STRATEGY_RANKING_SCHEMA_VERSION | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| STRATEGY_EXPLANATION_SCHEMA_VERSION | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| INTELLIGENT_OPTIMIZATION_AUDIT_SCHEMA_VERSION | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| ObjectiveMetric.PRINTABILITY_SCORE | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| ObjectiveMetric.ADVANCED_PREPARATION_SCORE | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| ObjectiveMetric.CONTROLLED_OPTIMIZATION_SCORE | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| ConstraintEvaluation.required_bound | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| ConstraintEvaluation.evidence_source | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| StrategyEvaluation.operation_audit | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| DominanceRecord.left_strategy_id | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| DominanceRecord.right_strategy_id | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| DominanceRecord.better_objectives | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| DominanceRecord.worse_objectives | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| DominanceRecord.equal_objectives | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| ParetoPoint.dominance_reason | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| ParetoPoint.frontier_index | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| ParetoFrontier.dominance_records | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| RankingRecord.tie_break_trace | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| StrategyExplanation.hard_constraints_passed | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| StrategyExplanation.soft_constraints_violated | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| StrategyHistory.history_id | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| IntelligentOptimizationSession.sprint5_objective_hash | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| IntelligentOptimizationSession.ranking_method_hash | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| IntelligentOptimizationAudit.preview_execution_audit | blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| OPTIMIZATION_SESSION_SCHEMA_VERSION | blender_addon/chroma3d_sculpt/models/optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| OPTIMIZATION_AUDIT_SCHEMA_VERSION | blender_addon/chroma3d_sculpt/models/optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| OPTIMIZATION_COMPARISON_SCHEMA_VERSION | blender_addon/chroma3d_sculpt/models/optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| OPTIMIZATION_CANDIDATE_SCHEMA_VERSION | blender_addon/chroma3d_sculpt/models/optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| OptimizationPolicy.objective_weights | blender_addon/chroma3d_sculpt/models/optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| OptimizationPolicy.approval_requirements | blender_addon/chroma3d_sculpt/models/optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| OptimizationPlanStep.expected_objective_deltas | blender_addon/chroma3d_sculpt/models/optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| OptimizationPlanStep.prerequisite_states | blender_addon/chroma3d_sculpt/models/optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| OptimizationComparison.objective_score_before | blender_addon/chroma3d_sculpt/models/optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| OptimizationComparison.objective_score_after | blender_addon/chroma3d_sculpt/models/optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| AcceptanceRecord.optimized_object_name | blender_addon/chroma3d_sculpt/models/optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| AcceptanceRecord.explicit_user_action | blender_addon/chroma3d_sculpt/models/optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| DiscardRecord.explicit_user_action | blender_addon/chroma3d_sculpt/models/optimization_models.py | 0 | 0 | True | LOW | INVESTIGATE |
| GeometryFacts.lowest_build_plane_offset_mm | blender_addon/chroma3d_sculpt/models/printability_models.py | 0 | 0 | True | LOW | INVESTIGATE |

`STATICALLY_UNREFERENCED_CANDIDATE` is not a dead-code verdict. H1 must add runtime/reference proof before removal. This baseline never emits `DEAD`.
