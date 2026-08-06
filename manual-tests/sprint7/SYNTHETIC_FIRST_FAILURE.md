# Sprint 7 Synthetic-Acceptance First Failure

- First status: `FAIL` (`9/15` gates passed).
- Classification: `HARNESS`.
- Cause 1: the runner incorrectly paired a STANDARD assistance policy with FAST limits, so context construction correctly failed closed.
- Cause 2: the runner tried to report `AssistanceLimits.mode`, a field that is intentionally not part of the limit contract.
- Fix: derive the policy with `policy_for_mode(..., "FAST")` and report the three invoked mode labels explicitly.
- Product limits changed or weakened: none.
- Live provider calls: `0`.
