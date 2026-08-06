# Sprint 7 Independent Historical-Layer First Failure

- First status: Sprint 0-3 PASS; Sprint 4-6 FAIL.
- Classification: `HARNESS`.
- Sprint 4: direct Blender script launch did not put `tests/blender` on `sys.path`, so its Sprint 3 fixture import failed.
- Sprint 5: the module deliberately has no `unittest.main()` entry point, so direct launch executed zero tests.
- Sprint 6: its `unittest.main()` parsed Blender process arguments during direct launch.
- Fix: use a dedicated worker that adds the test directory, discovers exactly one requested module, and invokes its suite without parsing Blender arguments.
- Frozen historical evidence changed: none.
- Product thresholds or behavior changed: none.
