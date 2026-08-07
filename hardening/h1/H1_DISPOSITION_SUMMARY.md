# H1 disposition summary

H0 identity: `v0.8.0-h0-hardening-baseline` / `6f20b8c3007658a78eb89e2d2937924175384feb`.
H0 manifest: `c24d4215064d46affc46d5aff834355d682ce025bcdd3029dd772e1de4ca4fec`; status `H0_BASELINE_COMPLETE_WITH_FINDINGS`.

Candidates inspected: **912**. Symbols removed: **16**. Files/modules removed: **0**.

| Classification | Count |
| --- | ---: |
| KEEP | 20 |
| REGISTERED_RUNTIME | 251 |
| DYNAMIC_REFERENCE | 8 |
| PUBLIC_CONTRACT | 136 |
| TEST_ONLY | 247 |
| DEV_TOOL_ONLY | 102 |
| COMPATIBILITY | 0 |
| GENERATED_REFERENCE | 0 |
| DUPLICATE_BUT_KEEP | 82 |
| SUSPICIOUS | 50 |
| UNRESOLVED | 0 |
| SAFE_TO_REMOVE | 16 |

## Proven removals

| Candidate | Path | Group |
| --- | --- | --- |
| `_ALL` | `blender_addon/chroma3d_sculpt/optimization_settings.py` | `H1-R3` |
| `compare_results` | `blender_addon/chroma3d_sculpt/services/repair_coordinator.py` | `H1-R1` |
| `has_result` | `blender_addon/chroma3d_sculpt/session.py` | `H1-R1` |
| `reset_session_state` | `blender_addon/chroma3d_sculpt/ui/properties.py` | `H1-R2` |
| `object_dimensions_mm` | `blender_addon/chroma3d_sculpt/utilities/units.py` | `H1-R1` |
| `_metric_summary` | `blender_addon/chroma3d_sculpt/services/repair_coordinator.py` | `H1-R1` |
| `Any` | `blender_addon/chroma3d_sculpt/services/pareto_frontier.py` | `H1-R4` |
| `Iterable` | `blender_addon/chroma3d_sculpt/services/pareto_frontier.py` | `H1-R4` |
| `Mapping` | `blender_addon/chroma3d_sculpt/services/pareto_frontier.py` | `H1-R4` |
| `stable_hash` | `blender_addon/chroma3d_sculpt/services/pareto_frontier.py` | `H1-R4` |
| `Any` | `blender_addon/chroma3d_sculpt/services/strategy_explainer.py` | `H1-R4` |
| `EvidenceState` | `blender_addon/chroma3d_sculpt/services/strategy_explainer.py` | `H1-R4` |
| `Mapping` | `blender_addon/chroma3d_sculpt/services/strategy_explainer.py` | `H1-R4` |
| `asdict` | `blender_addon/chroma3d_sculpt/services/strategy_generator.py` | `H1-R4` |
| `is_dataclass` | `blender_addon/chroma3d_sculpt/services/strategy_generator.py` | `H1-R4` |
| `math` | `blender_addon/chroma3d_sculpt/services/strategy_generator.py` | `H1-R4` |

## Dispositions

- Lifecycle: `CONFIRMED_BOUNDED_DEFECT_FIXED`; zero suspicious retention after recheck.
- Documentation: 2 proven drifts corrected; runtime contracts were not redefined.
- Modules: no module removed; CLI/test/package-boundary candidates were retained.
- Duplicates: retained as `DUPLICATE_BUT_KEEP`; consolidation is H2+.
- Hotspots: no complexity refactor; only separately proven dead pieces were removed.

## H2 candidate queue

Prioritize the 7 critical and 29 high complexity targets, then the 82 duplicate candidates and remaining unresolved/suspicious dependency surfaces. Revalidate objectives and public contracts before any H2 change.
