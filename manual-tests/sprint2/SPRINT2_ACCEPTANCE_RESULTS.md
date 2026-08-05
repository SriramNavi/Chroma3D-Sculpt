# Chroma3D Sculpt Sprint 2 Acceptance Results

## 1. Overall Result

**PASS**

## 2. Sprint Decision

**SPRINT 2 ACCEPTED**

## 3. Environment

- Repository: `E:\VPRS\Sriram\Projects\Chroma3D Sculpt`
- Branch: `feature/sprint-3-printability-engine`
- Blender: `4.4.3` at `D:\Softwares\Design\Blender\blender.exe`
- Extension: `0.4.0-alpha.1`; analysis schema `2.0`; repair audit schema `1.0`.

## 4. Baseline

- Accepted baseline tag: `v0.2.0-alpha.1` at `7a932b2449632b8c134ee064da32cb59b08c9330`.

## 5. Gate Summary

| Gate | Result | Duration |
|---|---|---:|
| S2-01 - Baseline regression | PASS | 464.271s |
| S2-02 - Source protection | PASS | 0.010s |
| S2-03 - Plan and stale protection | PASS | 0.010s |
| S2-04 - Duplicate repair | PASS | 0.026s |
| S2-05 - Degenerate and loose cleanup | PASS | 0.022s |
| S2-06 - Normal repair | PASS | 0.003s |
| S2-07 - Tiny-shell removal | PASS | 0.034s |
| S2-08 - Small-hole filling | PASS | 0.025s |
| S2-09 - Checkpoints and recovery | PASS | 0.023s |
| S2-10 - Before/after diagnostics | PASS | 0.017s |
| S2-11 - Accept and rollback | PASS | 0.022s |
| S2-12 - Repair audit | PASS | 0.021s |
| S2-13 - Repair stress test | PASS | 6.698s |
| S2-14 - Package and security | PASS | 1.817s |

## 6. Source-Protection Evidence

- Source signature before/after: `b321cb7ef8861ad2b771a525378180c1c1a3eba7876b507f9fcdd2103703a576` / `b321cb7ef8861ad2b771a525378180c1c1a3eba7876b507f9fcdd2103703a576`.
- Independent object and mesh identities: `2749292134664` / `2749265667080` and `2749292136456` / `2749265659912`.

## 7. Repair-Plan Evidence

- Plan `86b083ad-17fc-4c32-a5e4-547a71a52aa4` used analysis `9b96df13-5bf3-45f2-b476-3226fe37075b`; generation was read-only and external workspace mutation was rejected: `True`.

## 8. Operation Results

- `{"S2-04": {"first": {"original_vertex_count": 11, "candidate_duplicate_count": 2, "cluster_count": 2, "vertices_merged": 2, "final_vertex_count": 9, "resulting_counts": {"vertices": 9, "edges": 12, "faces": 6}, "duration_ms": 0.5157999985385686, "tolerance_mm": 0.001}, "second_status": "NO_CHANGE", "source_unchanged": true}, "S2-05": {"operations": [{"type": "REMOVE_DEGENERATE_FACES", "status": "APPLIED", "metrics": {"faces_evaluated": 7, "degenerate_faces_found": 1, "faces_removed": 1, "threshold_mm2": 1e-08, "duration_ms": 0.2927999958046712, "resulting_counts": {"vertices": 14, "edges": 16, "faces": 6}}}, {"type": "REMOVE_LOOSE_GEOMETRY", "status": "APPLIED", "metrics": {"loose_edges_found": 4, "loose_edges_removed": 4, "loose_vertices_found": 1, "loose_vertices_removed": 1, "resulting_counts": {"vertices": 8, "edges": 12, "faces": 6}, "duration_ms": 0.37939999310765415}}], "final_topology": {"non_manifold_edges": 0, "boundary_edges": 0, "manifold_edges": 12, "high_incidence_non_manifold_edges": 0, "loose_vertices": 0, "loose_edges": 0, "zero_length_edges": 0, "degenerate_faces": 0, "connected_components": 1, "disconnected_shells": 0, "face_shell_count": 1, "potential_duplicate_vertices": 0, "duplicate_evaluation_status": "COMPLETED", "edge_manifold_state": "MANIFOLD", "vertex_manifold_state": "MANIFOLD", "vertex_manifold_anomalies": 0, "watertight_state": "TOPOLOGICALLY_WATERTIGHT", "watertight_detail": "Topologically watertight. This is not a printability guarantee.", "normal_consistency": "CONSISTENT", "normal_consistency_detail": "All evaluated two-face adjacencies use opposite shared-edge winding."}, "source_unchanged": true}, "S2-06": {"outward_status": "NO_CHANGE", "inward": {"shells_evaluated": 1, "shells_reoriented": 1, "shells_skipped": 0, "skip_details": [], "vertex_coordinates_unchanged": true, "resulting_counts": {"vertices": 8, "edges": 12, "faces": 6}, "duration_ms": 0.3391999998711981}, "open": {"shells_evaluated": 0, "shells_reoriented": 0, "shells_skipped": 1, "skip_details": [{"shell_id": 0, "reason": "Shell is open or non-manifold."}], "vertex_coordinates_unchanged": true, "resulting_counts": {"vertices": 8, "edges": 12, "faces": 5}, "duration_ms": 0.22159999934956431}, "coordinates_unchanged": true}}`

## 9. Tiny-Shell Evidence

- `{"candidate_count": 2, "selected": "tiny-shell-0001-ec064d742e82", "operation": {"selected_shell_ids": [1], "removed_faces": 6, "removed_edges": 12, "removed_vertices": 8, "resulting_counts": {"vertices": 16, "edges": 24, "faces": 12}, "duration_ms": 0.5722999994759448}, "undo_restored": true, "main_shell_protected": true, "source_unchanged": true}`

## 10. Hole-Fill Evidence

- `{"candidate": "small-hole-0000-73accbe1d3e9", "operation": {"selected_candidate_ids": ["small-hole-0000-73accbe1d3e9"], "new_face_count": 1, "resulting_counts": {"vertices": 8, "edges": 12, "faces": 6}, "duration_ms": 0.43169999844394624}, "undo_restored": true, "large_hole_rejected": true, "source_unchanged": true}`

## 11. Checkpoint and Rollback Evidence

- Checkpoints: `{"checkpoint_records": 2, "restored_initial": true, "retained_meshes": 1, "source_unchanged": true}`
- Finalization: `{"accept_decision": "ACCEPTED", "accept_kept_source": true, "accept_kept_copy": true, "rollback_decision": "ROLLED_BACK", "rollback_deleted_workspace_only": true, "automatic_save": false}`

## 12. Before/After Diagnostics

- `{"improved": ["loose_vertices", "potential_duplicate_vertices"], "unchanged": ["boundary_edges", "non_manifold_edges", "vertex_manifold_anomalies", "loose_edges", "zero_length_edges", "degenerate_faces"], "regressed": [], "before_severity": "WARNING", "after_severity": "PASS", "source_signature": "5bafe31e41e7ee3165eb919fa3558798086a96a12af525bd04c681718c4464ad", "workspace_signature": "c0391dee5100353fb59e22ddbe874da36a69cf7107486336547a822c1c686031"}`

## 13. Stress Performance

- Source counts: `{'vertices': 50146, 'edges': 54, 'faces': 22}`; final workspace counts: `{'vertices': 16, 'edges': 24, 'faces': 12}`.
- Fixture generation: `0.047447`s; repair batch: `6.355316`s; final analysis: `1.8098000000463799`ms.
- 60-second warning threshold passed: `True`; source unchanged: `True`.

## 14. Audit Evidence

- `{"schema_version": "1.0", "settings_snapshot": true, "operation_records": 1, "checkpoint_records": 2, "comparison": true, "decision": "PENDING", "encoded_bytes": 31561}`

## 15. Regression Results

- `{"combined_test_count": 231, "Combined Blender tests": 0, "Sprint 0 acceptance": 0, "Sprint 1 acceptance": 0, "Sprint 1 final validation": 0, "analysis_read_only": true}`

## 16. Package Validation

- Package: `E:\VPRS\Sriram\Projects\Chroma3D Sculpt\dist\chroma3d_sculpt-0.3.0-alpha.1.zip`
- Files: `40`; size: `79072` bytes; SHA-256: `ec375cb0ce9ec659197091980fa8d641f54853a0fbb3f91b2d82131d59fb15d9`.

## 17. Defects Found and Fixed

- Tiny-shell review initially inherited a face-count plus relative-volume classification that could offer a physically medium ornament. Repair eligibility now also requires the configured physical diagonal criterion; focused regression added.
- A no-change operation could evict a prior valid undo checkpoint before its outcome was known. History eviction now occurs only after a geometry-changing operation succeeds; focused history regression added.
- The first normal-consistency implementation delegated to Blender's outward-oriented recalculation, coupling two user decisions. It now propagates deterministic adjacency winding while preserving the seed orientation; outward shell orientation remains a separate explicit operation and non-manifold skips are recorded.
- Coincident disconnected candidates could share a geometry fingerprint. Candidate IDs now include a deterministic component identity, and apply-time remapping rejects non-unique fingerprints instead of allowing one selection to affect multiple candidates.

## 18. Tests Not Run

- Manual interactive installed-panel smoke test.
- Real Chroma3D statue repair UAT (intentionally deferred).
- Blender 4.5 LTS compatibility because Blender 4.5 is not installed in this environment.

## 19. Known Limitations

- Original source is preserved, but workspace repair still requires human review.
- An unfinished session is not guaranteed to survive Blender restart.
- No remeshing, large-hole reconstruction, boolean repair, wall-thickness repair, AI, or printability guarantee.
- Real statue UAT is deferred.

## 20. Safety Confirmation

- Original source preserved; no network, external dependency, credential, administrator elevation, automatic save, commit, push, tag, merge, AI, or Sprint 3 work.

## 21. Final Decision

**SPRINT 2 ACCEPTED**

## 22. One Immediate Recommended Action

Review the Sprint 2 evidence and perform an installed-panel smoke test before committing the feature branch.
