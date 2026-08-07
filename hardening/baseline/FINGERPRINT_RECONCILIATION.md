# Fingerprint Reconciliation

Status: `PASS`. Retained raw fingerprint: `4101fea6263011e3b3157466dc3ae7fe09df2415a3f167e59c35befa90e89baa`. Current raw fingerprint: `3c91d5a44ae8f7a35f2e1a28aa935ae35d9d8fef7326a420b32c59e851e71759`.

| Measure | Count |
| --- | --- |
| Canonical release inputs | 206 |
| Raw mismatches | 54 |
| LF-normalized equivalents | 45 |
| Content-different | 9 |
| Binary-different | 0 |
| Unreadable | 0 |

All 45 reported newline-only paths match their frozen Sprint 7 SHA-256 after deterministic CRLF/CR-to-LF normalization. Source files were not rewritten.

## Substantive paths

| Path | Classification | ZIP | Imported | Worker | Result | Relevant change |
| --- | --- | --- | --- | --- | --- | --- |
| blender_addon/chroma3d_sculpt/__init__.py | REGISTRATION_SURFACE_CHANGE | yes | yes | yes | no | Integrated Sprint 7 operator/panel registration and AI session, credential, and provider cleanup. |
| blender_addon/chroma3d_sculpt/blender_manifest.toml | VERSION_OR_RELEASE_METADATA_ONLY | yes | no | no | no | Extension manifest version advanced from 0.7.0 to 0.8.0. |
| blender_addon/chroma3d_sculpt/metadata.py | VERSION_OR_RELEASE_METADATA_ONLY | yes | yes | yes | no | Advanced product version to 0.8.0 and declared the Sprint 7 schema version. |
| blender_addon/chroma3d_sculpt/operators/__init__.py | REGISTRATION_SURFACE_CHANGE | yes | yes | yes | no | Added the Sprint 7 AI assistance operator class surface. |
| blender_addon/chroma3d_sculpt/performance_registry.py | RUNTIME_BEHAVIOR_CHANGE | yes | yes | yes | yes | Added bounded FAST/STANDARD/DEEP AI assistance limits consumed by limits_for_mode. |
| blender_addon/chroma3d_sculpt/ui/__init__.py | REGISTRATION_SURFACE_CHANGE | yes | yes | yes | no | Added the Sprint 7 AI assistance panel registration surface. |
| blender_addon/chroma3d_sculpt/ui/properties.py | REGISTRATION_SURFACE_CHANGE | yes | yes | yes | no | Added AI assistance properties and the stale-session invalidation callback. |
| scripts/_project.py | PACKAGE_INVENTORY_ONLY | no | no | no | no | Added Sprint 7 runtime modules, panel, and schemas to the required package inventory. |
| scripts/validate_package.py | VALIDATION_OR_HARNESS_ONLY | no | no | no | no | Added rejection of Sprint 7 draft/specification development content in packages. |

All nine paths trace to `b21911eecf543cafa32c7dafd0e5e926c33a5f28` (`feat: implement Sprint 7 AI recommendation foundation`) before the recovery checkpoint merge. The frozen report preserved hashes but not the exact intermediate bytes; no matching blob exists in the current Git object database. Current-versus-pre-publication word diffs identify the symbols above, but exact retained-to-current textual ranges are not reconstructable.

## Dataset evidence decision

`FRESH_DATASET_VALIDATION_REQUIRED`

performance_registry.py is a content-different runtime input directly consumed by the Sprint 7 dataset worker through limits_for_mode; the exact retained bytes are not recoverable from Git, so semantic equivalence cannot be proven fail-closed.

The historical Sprint 7 fingerprint and dataset reports remain unchanged. H0 records the current raw and semantic identities separately.
