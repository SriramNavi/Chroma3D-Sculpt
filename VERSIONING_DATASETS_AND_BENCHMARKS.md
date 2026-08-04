# Dataset and Benchmark Versioning

## Software versions

The product repository release under this milestone is `v0.3.1-alpha.1`. The Blender extension manifest and the authoritative Sprint 2.6 golden records remain `0.3.0-alpha.1`; Sprint 2.7 does not change runtime versioning or benchmark truth.

## Independent payload versions

- Dataset: `1.0.0`, addressed as `dataset-v1.0.0`.
- Golden Benchmark: `1.0.0`, addressed as `benchmark-v1.0.0`.
- Dataset manifest schema: `1.0.0`.
- Benchmark manifest schema: `1.0.0`.
- Dataset lock schema: `1.0.0`.
- Benchmark lock schema: `1.0.0`.
- Archive index schema: `1.0.0`.

Dataset changes do not automatically bump software. Benchmark regeneration may bump the benchmark without changing the dataset. A runtime or Blender-facing change may require a new benchmark baseline. Dataset additions or source/license/checksum changes require a new dataset version. Schema changes increment the relevant schema version and require a compatibility review.

Lock files bind exact release tags, archive names, checksums, manifest hashes, counts, extraction roots, and compatibility notes. Old datasets and benchmarks remain independently addressable.

| Software | Dataset | Benchmark | Meaning |
| --- | --- | --- | --- |
| `v0.3.1-alpha.1` | `1.0.0` | `1.0.0` | Current storage architecture package; baseline content records `0.3.0-alpha.1` |
| `v0.4.0-alpha.1` | `1.0.0` | `2.0.0` | Runtime change requires a new benchmark baseline |
| `v0.4.0-alpha.1` | `1.1.0` | `2.1.0` | Dataset and dependent benchmark both change |

Compatibility is exact for lock-file acquisition and manifest/checksum validation. Benchmark comparison additionally requires the comparator-compatible software, dataset manifest hash, schema fingerprints, and documented execution model. A clean product clone can run lightweight tests without payloads; dataset validation and golden comparison require an installed verified cache.

Published product history and tags, including `v0.3.1-alpha.1`, are immutable. This sprint does not publish the separate repository or release assets.
