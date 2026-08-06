# Sprint 7 Security-Scan First Failure

- First status: `FAIL` with 16 findings.
- Classification: `HARNESS`.
- All 16 findings were safe regular-expression constructors (`re.compile`) incorrectly matched as Python's executable built-in `compile`.
- Package violations: `0`.
- Retained report secret hits: `0`.
- Fix: distinguish `ast.Name` built-ins from `ast.Attribute` calls and reserve process checks for actual shell/process attribute names.
- Security policy weakened: no; executable `eval`, `exec`, built-in `compile`, dynamic `__import__`, shell and process calls remain prohibited.
