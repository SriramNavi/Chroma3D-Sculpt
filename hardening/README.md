# Version 1.0 Hardening Harness

H0 measures the immutable `v0.8.0-pre-hardening-backup` checkpoint before any cleanup or behavioral change. It adds analysis tools, policies, compact tracked summaries, and ignored machine evidence. It does not authorize deletion, refactoring, optimization, threshold changes, or H1 work.

## Evidence layout

- `baseline/`: tracked comparison anchors and compact summaries.
- `policies/`: invariants and review rules for H1-H9.
- `reports/`: tracked H0 gate summary.
- `tools/`: deterministic static/package analyzers.
- `../manual-tests/hardening/`: Blender instrumentation and the gate runner.
- `../manual-tests/hardening/reports/`: ignored machine evidence and logs.

Run the bounded baseline from the repository root:

```powershell
py manual-tests\hardening\run_hardening_baseline.py --blender "D:\Softwares\Design\Blender\blender.exe"
```

The runner does not execute the full 27-model corpus, live providers, Blender 4.5, slicers, printer commands, or physical printing. A failed recovery, source-scope, functional, security, or compatibility gate blocks H0. Technical-debt findings may produce `PASS_WITH_FINDINGS`.

Generated JSON is intentionally ignored. Tracked summaries must retain `SKIPPED`, `UNKNOWN`, `INDETERMINATE`, and `NOT_RUN` states without converting them to pass.
