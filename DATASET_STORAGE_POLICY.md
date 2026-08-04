# Dataset Storage Policy

Chroma3D keeps code, manifests, provenance, licenses, schemas, summaries, lock files, and acquisition/verification tooling in the product repository. Large raw meshes and regenerable golden payloads are distributed as versioned GitHub Release assets from `SriramNavi/Chroma3D-Benchmark-Dataset`.

## Boundaries

- No newly tracked file should exceed 25 MiB without an explicit reviewed exception.
- Raw STL/OBJ/PLY/FBX/GLB/GLTF payloads, archives, `.blend` fixtures, generated thumbnails, verbose logs, timings, comparisons, and per-mesh generated reports are release payloads, not ordinary product history.
- Lightweight manifests, metadata, attribution/license text, canonical statistics, regression rules, schemas, and lock files remain tracked.
- The current payload is Dataset `1.0.0` and Golden Benchmark `1.0.0`. Software and payload versions are independent.
- Every accepted asset requires a source identifier, immutable upstream/provenance metadata, a license identifier, and a SHA-256 value. Every release archive has a sidecar SHA-256 and an internal `archive_index.json`.

The archive format is deterministic ZIP: sorted normalized entries, fixed UTC timestamps, regular-file permissions, stable DEFLATE settings, and no hidden temporary files. Archive paths must be relative, use `/`, contain no `.` or `..` components, and contain no symlink or special-file entries. Fetch tooling verifies the archive checksum before extraction and verifies every extracted file before atomic installation.

## History and recovery

Published product history, including `v0.3.1-alpha.1`, is immutable. Removing payloads from the current feature-branch HEAD does not remove them from old commits or tags; this sprint never rewrites history. Historical Git size therefore remains a known limitation.

If a release asset is unavailable, recover from another verified copy of the same archive or from the preserved upstream source URLs after revalidating license/provenance and checksums. Do not silently substitute a new corpus under an old version. A modified local cache is reported as `INSTALLED_BUT_MODIFIED_OR_CORRUPT` and is not overwritten without `--force`.

## Release, CI, and security policy

Release assets use `chroma3d-statue-dataset-<version>.zip`, `chroma3d-golden-benchmark-<version>.zip`, matching `.sha256` sidecars, versioned `source-manifest-<version>.json`, and attribution bundles. Payload retention is indefinite while the corresponding version is supported; superseded versions remain addressable unless legal takedown, corruption, or an approved retention decision requires withdrawal. Deprecation must preserve a replacement notice and lock-file compatibility record.

CI jobs must use `CHROMA3D_VALIDATION_CACHE` or `--cache-dir`, run `status`/`verify` in JSON mode, and fetch payloads only in jobs that need them. Ordinary lint, unit, and package checks must not download the full corpus. Public release assets require no secret. Fetch is HTTPS-only, restricted to the approved GitHub Release URL recorded in the lock file, does not execute archive contents, does not write the registry or administrator locations, and rejects unsafe archive paths, special files, checksum mismatches, and interrupted `.part` files.

## Future versions

Add a new dataset version for additions, removals, source/license changes, or changed asset bytes. Add a new benchmark version for regenerated truth, comparator policy, schema, or software-baseline changes. Build and verify the archives offline from the local corpus, update the corresponding lock file, publish only after review, and keep old versions independently addressable. Git LFS was evaluated but is not the current decision: quotas, bandwidth, and clone behavior add another operational dependency for this corpus; GitHub Release assets keep the product clone lightweight and the release boundary explicit.

The complete local workflow is documented in [the CI guide](docs/DATASET_CI_GUIDE.md), [the dataset README](datasets/statues/README.md), and [the benchmark README](benchmarks/golden/README.md). Sprint 3 remains unstarted.
