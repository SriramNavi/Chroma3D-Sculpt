# H3 complexity and architecture-risk ledger

Status: `PASS`. Targets: `35`.

The bounded implementation set excludes validation-only and public-contract-locked entries even when their raw complexity score is higher.

| Order | File | Symbol | Disposition | Risk rank |
|---:|---|---|---|---:|
| 1 | `blender_addon/chroma3d_sculpt/services/repair_operations.py` | `repair_normal_consistency` | EXTRACT_PURE_HELPER | 1 |
| 2 | `blender_addon/chroma3d_sculpt/services/ai_assistance_coordinator.py` | `request_recommendations` | SPLIT_FUNCTION | 3 |
| 3 | `blender_addon/chroma3d_sculpt/services/mesh_analyzer.py` | `_analyze` | SPLIT_FUNCTION | 8 |

All 35 entries and their callers, dependencies, invariants, coverage, risk evidence, and dispositions are retained in `H3_COMPLEXITY_LEDGER.json`.
