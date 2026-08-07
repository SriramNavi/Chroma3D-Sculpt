# Performance Baseline

Status: `PASS` on Blender `4.4.3`. Protected source unchanged: `True`.

| Operation | Mode | Input | Seconds | Working-set before | Working-set after | Delta |
| --- | --- | --- | --- | --- | --- | --- |
| diagnostics | STANDARD | {"size": "small", "triangles": 20} | 0.002388 | None | None | None |
| printability | FAST | {"size": "small", "triangles": 20} | 0.0054922 | None | None | None |
| printability | STANDARD | {"size": "small", "triangles": 20} | 0.0066387 | None | None | None |
| diagnostics | STANDARD | {"size": "medium", "triangles": 320} | 0.0195267 | None | None | None |
| printability | FAST | {"size": "medium", "triangles": 320} | 0.0474425 | None | None | None |
| printability | STANDARD | {"size": "medium", "triangles": 320} | 0.0511461 | None | None | None |
| diagnostics | STANDARD | {"size": "large", "triangles": 5120} | 0.2998366 | None | None | None |
| printability | FAST | {"size": "large", "triangles": 5120} | 0.72421 | None | None | None |
| repair_workspace_create_and_discard | CHECKPOINTED | {"size": "small", "triangles": 20} | 0.0098631 | None | None | None |
| advanced_preparation | FAST | {"size": "medium", "triangles": 320} | 0.1184191 | None | None | None |
| controlled_optimization_candidate_generation_comparison | STANDARD | {"candidate_input": "bounded synthetic snapshot", "triangles": null} | 0.0039039 | None | None | None |
| intelligent_optimization_strategy_generation_ranking | STANDARD | {"candidate_count": 5, "triangles": null} | 0.1022118 | None | None | None |
| ai_context_building | STANDARD | {"evidence_count": 1, "strategy_count": 23, "triangles": 0} | 0.0027504 | None | None | None |
| offline_recommendation | STANDARD | {"test_cases": 1, "triangles": 12} | 0.1970003 | None | None | None |
| report_export | JSON_AND_MARKDOWN | {"test_cases": 2, "triangles": 0} | 0.0555603 | None | None | None |

Working-set values are point observations, not continuously sampled peaks. Timings are local comparison anchors and include fixture/setup cost where stated; no optimization occurred.
