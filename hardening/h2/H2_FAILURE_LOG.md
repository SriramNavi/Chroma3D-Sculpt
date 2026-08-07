# H2 failure log

H2 preserves failures separately from eventual passing reruns.

## H2-00 preflight wrapper

- Recorded at: `2026-08-07T08:23:37.506656Z`.
- Exit code: `1`.
- Classification: `HARNESS_DEFECT`.
- Failure: the wrapper promoted the required no-upstream diagnostic to a
  terminating PowerShell error.
- Resolution: use `git for-each-ref` for an empty, non-error upstream query.
- Rerun: `PASS`.

## H2-R1 focused Blender invocation

- Gate: H2-02 removal batch `H2-R1`.
- Exit code: `2`.
- Classification: `HARNESS_DEFECT`.
- Exact failure: `blender.exe: error: unrecognized arguments: --background
  --factory-startup --python-exit-code --python ...`.
- Cause: the batch wrapper omitted Blender's trailing `--`, so the unittest
  parser received Blender's own arguments.
- Resolution: append `--` after the complete quoted `--python` path, matching
  the established hardening runner convention.
- Product source disposition: compile and analyzer tests passed; the failure
  occurred before the focused product tests executed.

The first harness correction retained the separator but still executed the
test file as `__main__`; its `unittest.main()` therefore continued to parse
Blender's complete process argument vector and returned the same exit code `2`.
This second `HARNESS_DEFECT` was corrected with a dedicated Blender-side
focused runner that imports the selected module and constructs the unittest
suite explicitly.

## H2-07 current structural scan summary

- Gate: H2-07 architecture/dependency recheck.
- Exit code: `1` after all five analyzer reports had been written.
- Classification: `HARNESS_DEFECT`.
- Exact failure: `KeyError: 'parse_errors'` while aggregating the inventory
  exit status.
- Cause: the inventory schema does not define the optional `parse_errors`
  collection used by the four AST analyzer schemas.
- Resolution: aggregate with an empty default for reports that omit the field.
- Product evidence disposition: the completed analyzer outputs were retained;
  no product source correction was required.

## H2-15 / H2-17 first final-harness pass

- Final-harness result: `15/17 PASS`; failed gates `H2-15` and `H2-17`.
- H2-15 classification: `HARNESS_DEFECT`.
- H2-15 cause: the wrapper expected `security.json` and
  `filesystem_write.json`, while the retained CLI emitted suffixed JSON names.
- H2-17 classification: `HARNESS_DEFECT` correctly detected by the scope gate.
- H2-17 cause: the retained static CLI also rewrote three frozen H0 Markdown
  baselines because their output paths were not configurable.
- Correction: call the retained scanner functions directly and write all JSON
  and Markdown only under the ignored H2 report tree.
- Historical evidence disposition: all three unintended baseline working-tree
  changes were restored byte-for-byte through targeted patches; Git reports no
  remaining baseline diff.
- Retained valid evidence: focused `763/763`, combined `814/814`, package/native/
  installed smoke PASS, representative `10/10`, full `27/27`, and retained
  Sprint 7 security zero violations. These are eligible for exact-identity
  reuse on the corrected final-harness pass.

## H2 corrected final-harness invocation

- Exit code: `1` before gate execution.
- Classification: `INVOCATION_ERROR`.
- Exact failure: `Blender not found: C:\Program Files\Blender Foundation\Blender 4.4\blender.exe`.
- Cause: the rerun command supplied a stale executable path instead of the
  repository harness's validated Blender 4.4.3 default.
- Resolution: rerun with the validated `D:\Softwares\Design\Blender\blender.exe`
  default. No product or evidence state changed in the failed invocation.

## H2 post-validation summary query

- Exit code: `1` after all independent Git checks completed successfully.
- Classification: `REPORT_QUERY_DEFECT`.
- Exact failure: `KeyError: 'status'` while compacting the structural evidence.
- Cause: the ad hoc summary expected a top-level status on the structural
  metric object; the authoritative status is carried by gate `H2-07`.
- Resolution: read gate status from the gate ledger and treat structural data
  as metrics only. The final harness and its result were unaffected.
