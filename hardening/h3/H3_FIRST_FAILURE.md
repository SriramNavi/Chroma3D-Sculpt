# H3 first failure

- Phase: `H3-00`
- Gate: consolidated fail-closed preflight harness
- First observed evidence: the read-only preflight command stopped before producing a gate verdict because its helper treated PowerShell's pipeline `LASTEXITCODE=-1` as a Git failure and returned an empty Git directory.
- Affected target: H3 validation harness only
- Source identity: `208016e87dbebe0580d9fa63cd1392e398fc3bf2`
- Classification: `HARNESS_DEFECT`
- Correction: removed the unreliable pipeline exit-code branch and retained the command's explicit invariant comparisons.
- Rerun result: `PASS`, 18/18 preflight invariants.

No product, test threshold, historical artifact, or repository state was changed by the failed invocation.
