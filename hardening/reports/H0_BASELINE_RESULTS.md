# H0 Baseline Results

Decision: **H0 BASELINE COMPLETE WITH FINDINGS**

Checkpoint: `v0.8.0-pre-hardening-backup` / `d06e1a05890fe23e77e66f95fc40e0200638a765`. Product: `0.8.0-alpha.1`.

| Gate | Status | Detail |
| --- | --- | --- |
| H0-01 | REUSED_VALIDATED | Continuation preflight passed; H0-only scope revalidated. branch=feature/v1.0-release-hardening checkpoint=d06e1a05890fe23e77e66f95fc40e0200638a765 annotated backup local/remote |
| H0-02 | REUSED_VALIDATED | Hardening compile evidence reused; final H0 compileall is rerun by the safety audit. |
| H0-03 | REUSED_VALIDATED | 516 checkpoint files; 22 Python files over 500 LOC (review signal only). |
| H0-04 | REUSED_VALIDATED | 221 modules; 855 internal edges; 82 review findings. |
| H0-05 | REUSED_VALIDATED | 5452 symbols; 627 static candidates; none classified DEAD. |
| H0-06 | REUSED_VALIDATED | 82 duplication candidates; 37 high/critical review targets; no refactor performed. |
| H0-07 | REUSED_VALIDATED | chroma3d_sculpt-0.8.0-alpha.1.zip; 178 files; 350155 bytes; SHA-256 d33abab09c3f516405791c7ccd0f1f0d8a87be416245eeb3cd2d57ce0947d3c6; repository/native validation PASS; retained release ZIP byte match=False. |
| H0-08 | REUSED_VALIDATED | 82 classes; register median 0.0043386s; unregister median 0.000409s. |
| H0-09 | REUSED_VALIDATED | 813 tests passed on Blender 4.4.3 in 6.567003s. |
| H0-10 | REUSED_VALIDATED | Dataset 27 and benchmark 27 identities verified; evidence=FRESH_H0_VALIDATION; fresh 10/10 and 27/27 PASS; frozen Sprint 7 evidence unchanged. |
| H0-11 | REUSED_VALIDATED | 15 bounded operation records; protected source unchanged; no optimization. |
| H0-12 | PASS_WITH_FINDINGS | 10 lifecycle scenarios; protected source unchanged; confirmed leaks=0; review findings=1. |
| H0-13 | PASS_WITH_FINDINGS | 178 write call sites; 19 runtime surfaces recorded without behavior change. |
| H0-14 | PASS_WITH_FINDINGS | 128 runtime files; zero prohibited findings; explicit provider boundary retained; Sprint 7 scanner passed. |
| H0-15 | PASS | 70 operators, 7 panels, 38 schemas; contract SHA-256 b5fe2b8b164ff36c07f0900bb0f2ae91c74cbb3c5bc1255b56e59fa2f7db18ac. |
| H0-16 | PASS_WITH_FINDINGS | 2 documentation drift findings queued for H7; no existing docs rewritten. |
| H0-17 | PASS | 48 H0-only changed paths; refs unchanged; whitespace clean |

## Finding counts

| Finding | Count |
| --- | --- |
| confirmed_defects | 0 |
| static_symbol_candidates | 627 |
| duplication_candidates | 82 |
| complexity_hotspots | 37 |
| performance_review_targets | 10 |
| resource_risks | 1 |
| package_review_targets | 2 |
| ui_consistency | 0 |
| documentation_drift | 2 |

## Evidence boundaries

The combined Blender suite and H0-01 through H0-09 evidence are reused validated evidence. Fresh H0 10/10 and 27/27 dataset validation, bounded performance/lifecycle fixtures, asset integrity, static security, and contract snapshots are current evidence. Live provider, Blender 4.5 LTS, slicer/material calibration, manual installed-panel UAT, printer commands, and physical printing are `NOT_RUN`.

## Safety

H0 deleted no runtime code, refactored no runtime code, performed no runtime optimization, weakened no threshold, falsified no historical evidence, did not rewrite the old fingerprint to look current, changed no package/version, and started no H1 work. No commit, push, PR, merge, or tag was performed.
