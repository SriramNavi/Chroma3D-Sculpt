# H1 dead-code proof and safe removal

H1 starts from published tag `v0.8.0-h0-hardening-baseline` at merge commit
`6f20b8c3007658a78eb89e2d2937924175384feb`. The H0 manifest and reports are
immutable inputs; H1 evidence is stored separately in this directory.

H1 permits only multi-source-proven dead-code removal, low-risk dependency
cleanup, the bounded diagnostic-report lifecycle correction, and two proven
documentation corrections. It does not authorize behavior redesign, public
contract removal, threshold/schema/profile/version changes, H2, Sprint 8, or
publication.

Tracked evidence:

- `H1_DISPOSITION_LEDGER.json`: one classification per inspected candidate.
- `H1_DISPOSITION_SUMMARY.md`: compact counts, removals, and deferred findings.
- `H1_FIRST_FAILURE.md`: preserved lifecycle regression before the fix.
- `H1_REMOVAL_LOG.md`: bounded deletion batches and gates.
- `H1_FINAL_RESULT.json`: final gate evidence produced by the H1 runner.

Large generated reports remain under the already ignored
`manual-tests/hardening/reports/h1/` tree.

Commands:

```powershell
py manual-tests\hardening\h1\verify_candidate_removal.py
py manual-tests\hardening\h1\run_h1_validation.py --blender "D:\Softwares\Design\Blender\blender.exe"
py manual-tests\hardening\h1\run_h1_final_validation.py --blender "D:\Softwares\Design\Blender\blender.exe"
```
