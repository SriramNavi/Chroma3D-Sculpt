# Golden Benchmark Runner

This runner executes the validated statue corpus through the existing Chroma3D
production operators. It does not contain alternate diagnostic or repair
implementations.

## Verify the stored baseline

```powershell
py manual-tests\benchmarks\verify_golden_baseline.py
py manual-tests\benchmarks\run_golden_benchmark.py --self-check
```

## Run a future regression

```powershell
py manual-tests\benchmarks\run_golden_benchmark.py --compare `
  --blender "D:\Softwares\Design\Blender\blender.exe"
```

The default comparison runs all 27 meshes, writes only the concise
`manual-tests/benchmarks/latest_regression_report.json`, and treats the stored
baseline as immutable.

For a bounded diagnostic rerun:

```powershell
py manual-tests\benchmarks\run_golden_benchmark.py --compare `
  --mesh-id statue-bastet `
  --blender "D:\Softwares\Design\Blender\blender.exe"
```

## Baseline generation

Baseline generation is intentionally guarded against overwriting an existing
`golden_manifest.json`.

```powershell
py manual-tests\benchmarks\run_golden_benchmark.py --generate `
  --blender "D:\Softwares\Design\Blender\blender.exe"
```

If a first generation is interrupted, rerun the same command with `--resume`.
The runner reuses only mesh records that already have a PASS validation and a
matching immutable source hash.

Each mesh runs in a fresh Blender factory-startup process and follows:

1. Native STL import.
2. `chroma3d.analyze_mesh`.
3. Production analysis export.
4. `chroma3d.start_repair_session`.
5. `chroma3d.generate_repair_plan`.
6. Default selected production repairs.
7. Undo and restore lifecycle checks.
8. Canonical plan/apply, comparison, and accept.
9. Production repair-audit export.
10. A separate production plan/rollback/audit session.

No repair parameter is changed. Candidate-based destructive operations and
orientation operations remain unselected unless production defaults select
them.
