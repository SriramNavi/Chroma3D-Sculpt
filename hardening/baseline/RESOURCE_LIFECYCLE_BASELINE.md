# Resource Lifecycle Baseline

Status: `PASS` on Blender `4.4.3`. Protected source unchanged: `True`.

| Classification | Count |
| --- | --- |
| CONFIRMED_LEAK | 0 |
| EXPECTED_RETENTION | 9 |
| INCONCLUSIVE | 0 |
| LIKELY_LEAK | 0 |
| SUSPICIOUS_RETENTION | 1 |

| Scenario | Restored | Classification |
| --- | --- | --- |
| register_unregister_1 | True | EXPECTED_RETENTION |
| register_unregister_2 | True | EXPECTED_RETENTION |
| register_unregister_3 | True | EXPECTED_RETENTION |
| diagnostic_session | True | EXPECTED_RETENTION |
| repair_workspace_create_discard | False | SUSPICIOUS_RETENTION |
| printability_session | True | EXPECTED_RETENTION |
| optimization_workspace_create_discard | True | EXPECTED_RETENTION |
| intelligent_optimization_session | True | EXPECTED_RETENTION |
| ai_assistance_session_cancel_discard | True | EXPECTED_RETENTION |
| temporary_file_create_cleanup | True | EXPECTED_RETENTION |

Observed resources include meshes, objects, collections, handlers, registered classes, session registries, provider registries, caches, and temporary files. No lifecycle finding is remediated in H0.
