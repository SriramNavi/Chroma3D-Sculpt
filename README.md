# Chroma3D Sculpt

Chroma3D Sculpt is a local Blender extension foundation for inspecting detailed meshes before later 3D-print preparation workflows. Sprint 0 is deterministic and read-only: it reports basic geometry, transforms, dimensions, topology signals, and a portable JSON record without changing the mesh or scene.

**Current status:** Sprint 0 — Windows foundation and read-only mesh analysis  
**Version:** 0.1.0-alpha.1  
**Minimum supported Blender version:** 4.4  
**Current runtime validation:** Blender 4.4.3 on Windows  
**Future compatibility target:** Blender 4.5 LTS and newer

## Sprint 0 features

- Modern `blender_manifest.toml` extension package.
- 3D Viewport > Sidebar > Chroma3D > Chroma3D Sculpt panel.
- Original-datablock geometry and triangulation estimates.
- Millimetre dimensions respecting scene scale and object scale.
- Read-only transform, boundary, non-manifold, loose, zero-length, degenerate, component, duplicate-position, and face-winding diagnostics.
- Session-only latest report per analyzed object.
- Blender file-browser JSON export.
- Windows Blender discovery, packaging, validation, installation helper, PowerShell wrappers, and background tests.

No external Python package, administrator privilege, VS Code, WSL, Node.js, or network access is required.

## Repository setup

The development repository root is:

```text
E:\VPRS\Sriram\Projects\Chroma3D Sculpt
```

Use PowerShell and quote every path that contains spaces:

```powershell
Set-Location "E:\VPRS\Sriram\Projects\Chroma3D Sculpt"
py scripts\find_blender.py
```

Set `BLENDER_EXECUTABLE` or pass `--blender` when Blender is installed in a custom location:

```powershell
$env:BLENDER_EXECUTABLE = "D:\Applications\Blender\blender.exe"
py scripts\run_blender_tests.py
```

## Build and validate

Preferred PowerShell commands:

```powershell
.\scripts\package_extension.ps1
.\scripts\validate_package.ps1
.\scripts\run_blender_tests.ps1
```

Equivalent Python commands:

```powershell
py scripts\package_extension.py
py scripts\validate_package.py
py scripts\run_blender_tests.py
```

The package is written to `dist\chroma3d_sculpt-0.1.0-alpha.1.zip`. The archive contains only runtime extension files and its license; the manifest is at the archive root for modern Blender installation. If script execution is locally restricted, run the Python commands directly or use a one-process execution-policy bypass—do not change machine policy permanently.

## Install in Blender

1. Build the ZIP, then open Blender 4.4 or newer.
2. Open **Edit > Preferences > Extensions** (the exact label can vary slightly by Blender point release).
3. Open the Extensions menu and choose **Install from Disk**.
4. Select `E:\VPRS\Sriram\Projects\Chroma3D Sculpt\dist\chroma3d_sculpt-0.1.0-alpha.1.zip`.
5. Enable the extension if Blender requests it.
6. In the 3D Viewport press `N`, open **Chroma3D**, then **Chroma3D Sculpt**.

`py scripts\install_dev_extension.py` builds and validates without modifying external files. Add `--install` to request Blender's extension command, or provide an existing `--user-extension-dir`; the helper refuses to overwrite an existing extension folder.

## Analyze and export

Select a mesh object in Object Mode and choose **Analyze Mesh**. Results update immediately in the panel and remain in memory for the current Blender session. Edit Mode is never changed automatically; exit it before analysis.

Choose **Export JSON Report**, confirm the suggested Windows-safe filename, and use Blender's standard overwrite confirmation. JSON contains the `.blend` file path when the file has been saved; this is documented metadata and is not displayed in the panel.

For runtime logs on Windows, open **Window > Toggle System Console**.

## Troubleshooting

- **Analyze is disabled:** make a mesh object active. Cameras, lights, curves, and missing datablocks are not valid inputs.
- **Edit Mode message:** return to Object Mode; the extension deliberately does not change modes.
- **Blender not found:** run `py scripts\find_blender.py --blender "C:\path\to\blender.exe"` or set `BLENDER_EXECUTABLE`.
- **Python launcher not found:** try `python` instead of `py`, or invoke the scripts with Blender's bundled Python.
- **Export fails:** choose an existing writable folder and a valid filename.
- **Large mesh warning:** the conservative duplicate-position check is skipped above 500,000 vertices; the report records `SKIPPED` rather than silently omitting it.

## Known limitations and safety

Sprint 0 does not repair meshes, guarantee watertightness, validate wall thickness, guarantee printability, use AI, or connect to the internet. Normal consistency is a shared-edge winding signal and is explicitly not evaluated when topology makes the result unreliable. Dimensions are object local-axis dimensions with scale; `NONE` unit scenes use the documented convention 1 Blender unit = 1 metre.

The extension makes no network request, stores no credential, loads no external dependency, applies no modifier or transform, calls no destructive Blender operator, saves no `.blend` file, requires no administrator rights, and derives runtime paths dynamically.
