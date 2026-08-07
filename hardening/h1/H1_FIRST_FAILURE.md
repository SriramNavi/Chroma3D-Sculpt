# H1 first failure

Status: `RESOLVED_BY_MINIMAL_FIX`

The first H1 runtime change was preceded by a failing regression against the
unchanged H0 runtime.

- Scope: Sprint 2 repair rollback diagnostic-report ownership.
- Command: Blender 4.4.3 factory startup running `tests/blender/test_sprint2_repair.py`.
- Result before fix: `60` tests run, `1` failure.
- Failing test: `test_48b_rollback_discards_workspace_diagnostic_report`.
- Failure: `diagnostic_session.get_result()` returned the deleted repair
  workspace's `AnalysisResult` after rollback instead of `None`.
- Source state: the protected source was unchanged; no runtime fix had yet been
  applied.

After the minimal object-owned cache eviction was added, the same file passed
`60/60` and the lifecycle measurement changed from one
`SUSPICIOUS_RETENTION` record to zero.
