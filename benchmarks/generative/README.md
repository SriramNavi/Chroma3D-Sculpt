# Chroma3D Generative Benchmark

`CGB 0.1.0` is offline-first research and evaluation infrastructure for choosing Chroma3D's open research foundation and immediate commercial MVP backend. It does not add generation to the shipping Blender extension.

Default execution is fail-closed:

```text
G0_MAX_SPEND_USD=0
G0_MAX_LIVE_JOBS=0
G0_ALLOW_MODEL_DOWNLOADS=0
G0_ALLOW_CLOUD_GPU=0
G0_ALLOW_LIVE_PROVIDER_CALLS=0
```

Credentials never imply permission. Unknown cost is not zero. Generated renders, meshes, provider payloads, logs, caches, and run matrices stay under `.validation-assets/generative-benchmark/` and out of Git.

Core commands from the repository root:

```powershell
python benchmarks/generative/tools/build_corpus.py
python benchmarks/generative/tools/run_benchmark.py --backend fake_generator --subset smoke3 --blender "D:\Softwares\Design\Blender\blender.exe"
& "D:\Softwares\Design\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python benchmarks/generative/tools/render_ground_truth.py -- --subset smoke3 --determinism-check
python manual-tests/g0/run_g0_acceptance.py --blender "D:\Softwares\Design\Blender\blender.exe"
```

The primary report is a dimension/status matrix plus Pareto evidence. `PROJECT_DEFAULT` is a provisional secondary profile, not scientific truth. Fake-generator evidence is excluded from backend rankings.

No model winner may be declared without genuine Smoke3 and Core10 finalist evidence.
