# Hardening Invariants

Blocking severity is `RELEASE_BLOCKING` unless explicitly marked `PHASE_BLOCKING`; both stop the affected hardening phase.

| ID | Statement | Affected subsystem | Verification source | Blocking severity |
| --- | --- | --- | --- | --- |
| HINV-001 | Protected-source geometry cannot mutate unexpectedly. | Repair, optimization, AI delegation | Source-signature tests and lifecycle/performance reports | RELEASE_BLOCKING |
| HINV-002 | Existing source/repair safety semantics remain intact. | Repair | Sprint 2 regression and `REPAIR_SAFETY.md` | RELEASE_BLOCKING |
| HINV-003 | Diagnostics remain non-destructive. | Diagnostics | Sprint 0/1 tests and source signatures | RELEASE_BLOCKING |
| HINV-004 | Repair operations remain checkpointed and recoverable. | Repair | Sprint 2 checkpoint/failure/rollback tests | RELEASE_BLOCKING |
| HINV-005 | Printability analysis remains advisory. | Printability | Sprint 3 tests, schemas, UI wording | RELEASE_BLOCKING |
| HINV-006 | Advanced preparation does not auto-rotate, scale, support, or print. | Advanced preparation | Sprint 4 tests and prohibited-action scan | RELEASE_BLOCKING |
| HINV-007 | Controlled optimization operates on protected workspaces. | Controlled optimization | Sprint 5 source/workspace tests | RELEASE_BLOCKING |
| HINV-008 | Intelligent optimization remains bounded and deterministic. | Intelligent optimization | Sprint 6 budget/determinism tests | RELEASE_BLOCKING |
| HINV-009 | AI provider output remains untrusted. | AI recommendation | Sprint 7 decoder/validator/security tests | RELEASE_BLOCKING |
| HINV-010 | Provider output cannot mint executable parameters. | AI recommendation | Exact operation/parameter-hash grounding tests | RELEASE_BLOCKING |
| HINV-011 | Preview and fresh approval remain mandatory where specified. | Repair/optimization/AI | State-transition and approval-scope tests | RELEASE_BLOCKING |
| HINV-012 | Credentials never persist or appear in reports, logs, or UI. | AI/provider/security | Sprint 7 credential and report scans | RELEASE_BLOCKING |
| HINV-013 | AI context remains bounded and zero-geometry. | AI context | Context budget/allow-list tests | RELEASE_BLOCKING |
| HINV-014 | Offline fallback remains deterministic and network-free. | AI fallback | Sprint 6/7 offline tests | RELEASE_BLOCKING |
| HINV-015 | No printer, G-code, or slicer command exists in runtime. | Runtime boundary | Static security/prohibited-action scan | RELEASE_BLOCKING |
| HINV-016 | Historical schemas retain version meaning. | Schemas/reports | Public-contract snapshot and schema tests | RELEASE_BLOCKING |
| HINV-017 | Package registration and unregistration remain clean. | Package/startup | Factory-startup registration/lifecycle baseline | RELEASE_BLOCKING |
| HINV-018 | Existing supported Blender compatibility remains intact. | Runtime/package | Blender 4.4 regression/native validation | RELEASE_BLOCKING |
| HINV-019 | No new runtime network behavior exists beyond the explicit opt-in provider adapter. | Provider transport | Static network boundary and Sprint 7 tests | RELEASE_BLOCKING |
| HINV-020 | Public operator IDs and extension registration contracts require migration evidence before removal. | Operators/UI/package | Public-contract diff and migration record | RELEASE_BLOCKING |
| HINV-021 | No hardening phase silently changes thresholds. | Performance/safety policy | Registry/profile/schema diff | RELEASE_BLOCKING |
| HINV-022 | `SKIPPED`, `UNKNOWN`, or `INDETERMINATE` evidence never becomes `PASS`. | Evidence models/reports | Enum/serialization diff and regression tests | RELEASE_BLOCKING |
| HINV-023 | Historical evidence is not deleted merely to reduce repository size. | Validation evidence | Git path diff against backup tag | PHASE_BLOCKING |
| HINV-024 | Static unused classification alone never authorizes symbol removal. | All code | Dead-code policy and multi-source proof record | PHASE_BLOCKING |
| HINV-025 | Every H1-H9 phase remains diff-comparable against the pre-hardening backup. | Repository/release | `git diff v0.8.0-pre-hardening-backup...HEAD` | RELEASE_BLOCKING |
