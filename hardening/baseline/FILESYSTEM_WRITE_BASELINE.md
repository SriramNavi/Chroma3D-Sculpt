# Filesystem Write Baseline

Checkpoint: `v0.8.0-pre-hardening-backup` / `d06e1a05890fe23e77e66f95fc40e0200638a765`.

| Metric | Value |
| --- | --- |
| Write call sites | 178 |
| Runtime write call sites | 19 |

| Artifact kind | Count |
| --- | --- |
| AUDIT | 5 |
| JSON | 7 |
| MARKDOWN | 4 |
| OTHER | 1 |
| REPORT | 2 |

| Safeguard | Call sites with local evidence |
| --- | --- |
| path_validation_evident | 10 |
| atomic_write_evident | 4 |
| extension_allowlist_evident | 0 |
| filename_sanitization_evident | 4 |
| explicit_cleanup_evident | 2 |

| Path | Line | Function | Call | Kind | Validation | Atomic | Extension | Sanitize | Cleanup |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| blender_addon/chroma3d_sculpt/services/advanced_preparation_report.py | 131 | write_preparation_json | write_text | JSON | True | False | False | False | NOT_EVIDENT_LOCALLY |
| blender_addon/chroma3d_sculpt/services/advanced_preparation_report.py | 138 | write_preparation_markdown | write_text | MARKDOWN | True | False | False | False | NOT_EVIDENT_LOCALLY |
| blender_addon/chroma3d_sculpt/services/advanced_preparation_report.py | 145 | write_batch_json | write_text | JSON | True | False | False | False | NOT_EVIDENT_LOCALLY |
| blender_addon/chroma3d_sculpt/services/advanced_preparation_report.py | 152 | write_batch_markdown | write_text | MARKDOWN | True | False | False | False | NOT_EVIDENT_LOCALLY |
| blender_addon/chroma3d_sculpt/services/ai_assistance_report.py | 96 | _atomic_write | write_bytes | REPORT | False | True | False | False | EXPLICIT |
| blender_addon/chroma3d_sculpt/services/ai_assistance_report.py | 97 | _atomic_write | replace | REPORT | False | True | False | False | EXPLICIT |
| blender_addon/chroma3d_sculpt/services/intelligent_optimization_audit.py | 97 | write_json_audit | write_bytes | AUDIT | False | False | False | True | NOT_EVIDENT_LOCALLY |
| blender_addon/chroma3d_sculpt/services/intelligent_optimization_audit.py | 128 | write_markdown_audit | write_text | AUDIT | False | False | False | True | NOT_EVIDENT_LOCALLY |
| blender_addon/chroma3d_sculpt/services/optimization_audit.py | 61 | write_json_audit | write_text | AUDIT | False | False | False | False | NOT_EVIDENT_LOCALLY |
| blender_addon/chroma3d_sculpt/services/optimization_audit.py | 76 | write_markdown_audit | write_text | AUDIT | False | False | False | False | NOT_EVIDENT_LOCALLY |
| blender_addon/chroma3d_sculpt/services/printability_baseline.py | 159 | write_baseline_manifest | write_text | JSON | True | True | False | False | NOT_EVIDENT_LOCALLY |
| blender_addon/chroma3d_sculpt/services/printability_baseline.py | 160 | write_baseline_manifest | replace | JSON | True | True | False | False | NOT_EVIDENT_LOCALLY |
| blender_addon/chroma3d_sculpt/services/printability_report.py | 29 | write_printability_json | write_text | JSON | True | False | False | False | NOT_EVIDENT_LOCALLY |
| blender_addon/chroma3d_sculpt/services/printability_report.py | 107 | write_printability_markdown | write_text | MARKDOWN | True | False | False | False | NOT_EVIDENT_LOCALLY |
| blender_addon/chroma3d_sculpt/services/regression_dashboard.py | 105 | write_dashboard | write_text | OTHER | True | False | False | False | NOT_EVIDENT_LOCALLY |
| blender_addon/chroma3d_sculpt/services/repair_audit.py | 61 | write_repair_audit | write_text | AUDIT | True | False | False | False | NOT_EVIDENT_LOCALLY |
| blender_addon/chroma3d_sculpt/services/report_generator.py | 40 | write_json_report | write_text | JSON | False | False | False | False | NOT_EVIDENT_LOCALLY |
| blender_addon/chroma3d_sculpt/services/strategy_history.py | 117 | write_history_json | write_bytes | JSON | False | False | False | True | NOT_EVIDENT_LOCALLY |
| blender_addon/chroma3d_sculpt/services/strategy_history.py | 136 | write_history_markdown | write_text | MARKDOWN | False | False | False | True | NOT_EVIDENT_LOCALLY |

This is static call-site evidence only; H1-H9 must preserve path, extension, overwrite, atomicity, and cleanup contracts when changing a write surface.
