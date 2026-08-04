# Dataset and Benchmark CI Guide

The product repository intentionally does not require large validation payloads for ordinary CI. Use the standard-library fetch tool only in jobs that need the corpus.

```powershell
$env:CHROMA3D_VALIDATION_CACHE = "$env:RUNNER_TEMP\chroma3d-validation"
py scripts\fetch_validation_assets.py status --json
py scripts\fetch_validation_assets.py dataset
py scripts\fetch_validation_assets.py benchmark
py scripts\fetch_validation_assets.py verify --json
```

Use `--offline` after a successful acquisition. A public release URL is read from the tracked lock file; arbitrary URLs are not accepted. `--force` is required to replace a modified or corrupt local installation.

CI should fail fast when required assets are absent or invalid, use `status --json` for machine-readable state, and keep the cache outside the checkout. Lint, unit, package, and repository-size jobs should not invoke `dataset`, `benchmark`, or `all`. A golden benchmark job may fetch only when its job explicitly opts in.

The three states are `NOT_INSTALLED`, `INSTALLED_AND_VALID`, and `INSTALLED_BUT_MODIFIED_OR_CORRUPT`. `clean-cache` removes interrupted `.part` and staging files; `clean-cache --force` removes the full cache and must be used deliberately. No administrator permission, registry write, secret, or downloaded code is required.
