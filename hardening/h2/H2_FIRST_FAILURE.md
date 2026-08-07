# H2 first failure

Status: `RESOLVED_HARNESS_DEFECT`

The first H2-00 consolidated preflight attempt stopped before editing because
the PowerShell wrapper promoted an expected Git diagnostic to a terminating
native-command error.

- Recorded at: `2026-08-07T08:23:37.506656Z`.
- Gate: `H2-00` preflight.
- Command: consolidated read-only H2 preflight including
  `git rev-parse --abbrev-ref --symbolic-full-name "@{u}"`.
- Exit code: `1`.
- Exact Git failure: `fatal: no upstream configured for branch
  'feature/v1.0-release-hardening'`.
- Classification: `HARNESS_DEFECT`.
- Repository disposition: the absence of an upstream was the required H2
  invariant, not a repository defect.
- Correction: query `%(upstream:short)` with `git for-each-ref`, which returns
  an empty value without converting the expected state into an error.

The corrected consolidated preflight passed. No file had been edited when the
first attempt stopped.
