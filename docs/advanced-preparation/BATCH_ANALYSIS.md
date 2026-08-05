# Batch Analysis

Batch analysis applies one composed process context and one feature-flag set to
the selected mesh objects. Inputs are deterministically ordered, capped by the
central performance registry, and recorded with source signatures and the
process/feature hashes.

Each object is isolated: a failure is retained for that object while remaining
eligible objects continue. The aggregate state distinguishes completed,
completed-with-warnings, partial, cancelled, and failed runs. Progress is
reported between objects, cancellation is cooperative between objects, and an
interrupted run can resume only when the bound inputs and hashes still match.

The JSON/Markdown aggregate retains counts, per-object outcomes, critical risks,
timing, limitations, and identity evidence. Batch execution does not mutate
geometry or transforms and does not hide per-object skipped or failed checks.
FAST, STANDARD, and DEEP batch-size caps are defined only in
`performance_registry.py`.
