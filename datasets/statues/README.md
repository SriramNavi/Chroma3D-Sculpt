# Chroma3D Real Statue Validation Dataset

## Purpose

This versioned corpus contains 27 rights-cleared, real or
documented heritage statue meshes for regression testing, repair validation,
diagnostic evaluation, performance benchmarking, and future governed research.
It is test data only and is not loaded by the Chroma3D production extension.

Dataset version: `1.0.0`

## Directory Structure

```text
datasets/statues/
├── raw/          Original downloaded meshes; never modify in place
├── processed/    Reserved for documented derived meshes
├── metadata/     One JSON record per accepted asset plus rejected candidates
├── thumbnails/   Source-provided preview images for human identification
├── manifests/    Dataset manifest and acquisition report
└── licenses/     Official license texts, index, and attribution table
```

## License and Provenance Policy

Every accepted model must be publicly downloadable without bypassing access
controls and must have explicit CC0, CC BY, CC BY-SA, public-domain, MIT,
Apache, or equivalent commercial-use-compatible terms. Unknown, noncommercial,
no-redistribution, paid, private, login-only, and ambiguous assets are rejected.

Each metadata record preserves the source page, exact source-page revision,
download URL, acquisition time, author/credit, canonical license URL, original
and stored filenames, file size, Wikimedia SHA-1 where supplied, local SHA-256,
and validation evidence. Raw meshes are immutable source evidence.

## Adding an Asset

1. Review the model-level license and redistribution terms, not only the host's
   general policy or a search-result label.
2. Add one bounded `CuratedAsset` entry to
   `manual-tests/datasets/acquire_statue_dataset.py`.
3. Run the acquisition script from the repository root.
4. Run the Blender validation command below.
5. Review the per-asset metadata, source revision, attribution entry, manifest
   summaries, and any rejected-asset evidence.
6. Never overwrite an existing raw asset under the same ID if its SHA-256 has
   changed; assign a new dataset version and document the change.

## Validation

Acquisition:

```powershell
py manual-tests\datasets\acquire_statue_dataset.py
```

Structural validation with the repository's Blender installation:

```powershell
& "D:\Softwares\Design\Blender\blender.exe" `
  --background `
  --factory-startup `
  --python-exit-code 1 `
  --python "manual-tests\datasets\validate_statue_dataset.py"
```

The validator rechecks SHA-256, recognizes STL container structure, imports each
file in an isolated factory-startup Blender process, confirms finite/non-empty
mesh data, compares binary-header/imported triangle counts, records Blender
vertex/triangle counts and world-space bounds, and rebuilds the manifest and
documentation. It does not call Chroma3D diagnostics or repairs.

## Citation

For an individual mesh, cite its title, credited author or institution, original
repository, license, and recorded source-revision URL from the asset metadata.
For the corpus, cite:

> Chroma3D Sculpt Real Statue Validation Dataset, version
> 1.0.0, created 2026-07-26, with
> per-asset provenance in `datasets/statues/metadata/`.

Keep `licenses/ATTRIBUTIONS.md` with any redistributed subset and comply with
the applicable attribution/share-alike obligations.

## Safety and Interpretation

Dataset acceptance means the file is rights-cleared for the stated terms,
byte-verified, readable, non-empty, finite, and structurally reasonable. It does
not mean watertight, printable, diagnostically clean, culturally neutral, or
safe for automatic repair. Always use an independent repair workspace and
retain the protected raw source.
