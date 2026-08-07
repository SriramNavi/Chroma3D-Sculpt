# H4 failure log

| ID | Phase | Classification | Status | Observation | Resolution |
|---|---|---|---|---|---|
| H4-R1 | H4-01 | HARNESS_DEFECT | RESOLVED | Baseline scope check collapsed an untracked directory and rejected its own allowed script. | Use exact porcelain paths with `--untracked-files=all`. |
| H4-R2 | H4-01 | HARNESS_DEFECT | RESOLVED | The generic Git helper stripped the leading porcelain status column and turned `.gitignore` into `gitignore`. | Capture porcelain stdout without trimming before slicing status columns. |
| H4-F001 | H4-02 | HIGH | FIXED | A second `register()` raised `ValueError: register_class(...): already registered as a subclass`; normal cycles still passed. Evidence: `manual-tests/hardening/h4/reports/registration_before.json`. | Registration is idempotent; the identical after-test passes 5/5 cycles. |
| H4-F002 | H4-02 | HIGH | FIXED | An injected fifth class-registration failure retained one class and the WindowManager property until explicit cleanup. Evidence: `manual-tests/hardening/h4/reports/registration_before.json`. | Registration tracks completed classes and rolls back property/classes/runtime state before re-raising. |
| H4-R3 | H4-03 | HARNESS_DEFECT | RESOLVED | The dual host/Blender persistence runner ignored ordinary Python CLI arguments when no Blender `--` separator was present. | Parse `sys.argv[1:]` in host mode and Blender-tail arguments in worker mode. |
| H4-R4 | H4-06 | HARNESS_DEFECT | RESOLVED | The UI audit called `poll` on Python classes lacking an explicit method and treated Blender's bounded `CANCELLED` error promotion as a crash. | Query registered `bpy.ops.*.poll()` and recognize only the exact bounded prerequisite cancellation. |
| H4-D001 | H4-19 | DOCUMENTATION_DRIFT | FIXED | README contradicted the shipped optional provider adapter and the roadmap still called the published Sprint 7 state uncommitted. | Clarify offline core/explicit provider boundary, save/reload clearing, and published `v0.8.0-alpha.1` state. |
