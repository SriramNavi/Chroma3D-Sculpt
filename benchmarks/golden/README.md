# Chroma3D Golden Benchmark Baseline

This directory is the permanent regression reference generated from all 27
validated statue meshes in dataset `1.0.0` using Chroma3D
`0.3.0-alpha.1` production operators.

## Reproduce and compare

```powershell
py manual-tests\benchmarks\run_golden_benchmark.py --compare `
  --blender "D:\Softwares\Design\Blender\blender.exe"
```

Verify stored files and hashes without rerunning Blender:

```powershell
py manual-tests\benchmarks\verify_golden_baseline.py
```

The generator runs each mesh in a fresh Blender `--factory-startup` process and
uses only the existing production flow:

`Analysis -> Repair Plan -> Repair -> Comparison -> Accept/Audit`

Undo and restore are exercised before the canonical apply. Rollback is exercised
in a second normal production session because accept and rollback are mutually
exclusive final decisions. Raw statue files are never modified.

## Layout

- `raw/`: production analysis JSON, accepted/rollback repair audits, and one
  self-contained `*_golden.json` truth record per mesh.
- `comparisons/`: production before/after comparison plus metric deltas.
- `timings/`: wall, Blender CPU, phase, and process-memory measurements.
- `statistics/`: aggregate distributions and repair/timing statistics.
- `reports/`: concise per-mesh reports, retained Blender logs, and the summary.
- `manifests/golden_manifest.json`: authoritative corpus and artifact index.
- `thumbnails/`: byte-identical identification copies from dataset 1.0.0.

## Regression rules

### PASS

- Source, metadata, and thumbnail hashes match.
- Dataset/software/schema versions match.
- Analysis topology, shell, issue, orientation, severity, warning, and
  deterministic report values match after volatile IDs/timestamps are removed.
- Repair plan selection, operation order/outcomes/metrics, comparison, audit,
  undo/restore/accept/rollback evidence, and after-repair topology match.
- Timing remains below the warning threshold.

### WARNING

- The machine fingerprint differs, so timing evidence is not directly
  comparable.
- On the same machine, a timed phase is at least
  `1.5x` and at least
  `1.0s` slower than its golden value, while
  remaining below the fail threshold.

### FAIL

- A source, metadata, thumbnail, stored artifact, or topology hash differs.
- Shell, duplicate, boundary, non-manifold, degenerate, loose-geometry,
  connected-component, orientation, severity, warning, or other deterministic
  analysis evidence changes.
- Selected repairs, repair outcomes, operation metrics/order, comparison,
  accepted audit, rollback audit, or source-preservation evidence changes.
- A JSON schema fingerprint or declared schema/software/dataset version changes.
- On the same machine, a timed phase is at least
  `2.0x` and at least
  `5.0s` slower than its golden value.

Timing improvements do not fail. Any intentional product/schema/dataset change
requires explicit review and a new benchmark version; never silently overwrite
this baseline.

## Storage and acquisition

Golden Benchmark `1.0.0` is packaged as `chroma3d-golden-benchmark-1.0.0.zip` for the staged external dataset repository. The product repository retains the authoritative manifest, canonical statistics, lightweight summaries, schema, comparator, and runner. Raw golden truth, per-mesh reports, comparisons, timings, and generated thumbnails are ignored local payloads.

Fetch and verify with `py scripts\fetch_validation_assets.py benchmark` and `py scripts\fetch_validation_assets.py verify`. The lock file binds Dataset `1.0.0`, the source software release recorded by the baseline (`0.3.0-alpha.1` / `v0.3.0-alpha.1`), the current product packaging release (`v0.3.1-alpha.1`), archive and manifest hashes, counts, and extraction root. Sprint 2.7 does not regenerate or rewrite this baseline.
