# Real Statue Dataset Summary

## Outcome

- Downloaded: 27 meshes
- Validated and accepted: 27 meshes
- Acquisition failures: 0
- Validation failures: 0
- Policy or curation rejections: 6
- Raw mesh size: 630.09 MiB
- SHA-256 status: generated and rechecked for every accepted mesh
- Blender readability status: every accepted mesh imported successfully in Blender 4.4.3

## Licenses

| License | Accepted assets |
| --- | --- |
| CC-BY-4.0 | 4 |
| CC-BY-SA-4.0 | 11 |
| CC0-1.0 | 12 |

Official license texts are retained under `datasets/statues/licenses/`. Per-asset
attribution and immutable source-revision links are in `ATTRIBUTIONS.md` and the
individual metadata JSON files.

## Categories

| Category | Assets |
| --- | --- |
| bust | 2 |
| deity_group | 1 |
| figure_group | 3 |
| figurine | 2 |
| fragment | 1 |
| full_statue | 10 |
| functional_sculpture | 1 |
| head | 2 |
| monument_reconstruction | 1 |
| ornamental_stone | 1 |
| temple_guardian | 1 |
| temple_monument | 2 |

## Formats

| Format | Assets |
| --- | --- |
| STL | 27 |

All accepted assets are STL files. The single-format baseline is deliberate: it
keeps Sprint 2.5 import comparisons controlled. OBJ, PLY, FBX, GLB, and GLTF
coverage remains a future dataset expansion, not a validation claim.

## Size Distribution

| Raw file band | Assets |
| --- | --- |
| large_50_mib_or_more | 3 |
| medium_10_to_50_mib | 12 |
| small_under_10_mib | 12 |

- Minimum: 0.79 MiB
- Median: 18.97 MiB
- Maximum: 95.30 MiB

## Triangle Distribution

| Triangle band | Assets |
| --- | --- |
| large_1m_or_more | 3 |
| medium_100k_to_1m | 16 |
| small_under_100k | 8 |

- Minimum: 16,520
- Median: 280,209
- Maximum: 1,998,496
- Total: 12,925,711

Counts are produced by Blender's native STL importer. STL triangle soups can
import with merged vertices, so vertex counts are Blender-import counts rather
than counts claimed by source websites.

## Rejected Candidates

| Candidate | License | Reason |
| --- | --- | --- |
| Cosmic Buddha full-resolution no-texture | CC0-1.0 | Rejected before download: 2.88 GiB and roughly 62 million faces exceed this baseline corpus budget; the Smithsonian 150k derivative is retained. |
| Gisant test | CC-BY-SA-4.0 | Rejected before download: source labels the asset only as a test and does not provide sufficient object provenance for the curated corpus. |
| Generic Moai rendering | CC-BY-4.0 | Rejected before download: generic rendering rather than a documented scan or identified heritage object. |
| Open Heritage 3D general project downloads | Varies by project | Rejected as an acquisition route for this sprint: downloads require user identity fields and many projects prohibit commercial use. |
| Sketchfab models without anonymous downloads | Varies by model | Rejected as an acquisition route unless mirrored by a public repository with model-level license evidence; direct downloads can require login. |
| Paid marketplace statue meshes | Paid or unclear redistribution terms | Rejected by policy: paid, private, or redistribution-restricted assets are outside this dataset. |

## Known Issues and Limits

- Source units are not reliably declared by STL; bounding boxes are recorded in
  Blender world coordinates after default import with units marked unspecified.
- Blender may omit duplicate or degenerate STL facets during import. Per-asset
  binary-header/import triangle deltas are retained as warnings rather than
  misreported as corruption when the remaining mesh is finite and reasonable.
- The corpus contains culturally and religiously significant subjects. Use
  respectful labels, retain provenance, and do not infer theological meaning
  from geometry alone.
- CC BY and CC BY-SA items require attribution; adapted CC BY-SA distributions
  also require the applicable share-alike terms.
- Source thumbnails are provenance previews from Wikimedia Commons, not
  regression renders and not evidence of mesh validity.
- No Chroma3D production diagnostics or repair operations were executed while
  constructing this dataset. Inclusion is not a printability or repair-success
  claim.
- `processed/` intentionally contains no derived geometry. Raw source meshes are
  preserved byte-for-byte under their recorded SHA-256 values.
- The 2.88 GiB full-resolution Cosmic Buddha was excluded in favor of the
  Smithsonian 150k derivative to keep the baseline dataset practical.
