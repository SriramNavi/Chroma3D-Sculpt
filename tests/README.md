# Blender Background Tests

The procedural `unittest` suite creates temporary in-memory meshes under Blender `--factory-startup`, analyzes them, and removes every created object and datablock. It does not open or save user `.blend` files.

From the repository root:

```powershell
.\scripts\run_blender_tests.ps1
```

The current runtime validation environment is Blender 4.4.3. Blender 4.4 is the minimum supported version; Blender 4.5 LTS and newer remain the future compatibility target.

Override discovery when needed:

```powershell
py scripts\run_blender_tests.py --blender "D:\Softwares\Design\Blender\blender.exe"
```

Direct Blender invocation:

```powershell
& "D:\Softwares\Design\Blender\blender.exe" `
  --background `
  --factory-startup `
  --python-exit-code 1 `
  --python "E:\VPRS\Sriram\Projects\Chroma3D Sculpt\tests\blender\test_mesh_analysis.py"
```
