# Real Statue Dataset Regression Guide

## Scope

This guide orders the dataset for manual and future automated regression work.
Sprint 2.5 validates the corpus itself; it does not claim that Chroma3D
diagnostics or repairs have passed on these meshes.

## Recommended Regression Order

1. Confirm the raw file SHA-256 against its metadata.
2. Import a small case and complete read-only analysis under operator review.
3. Progress through medium and large cases while recording wall time, CPU state,
   memory, analysis profile, warnings, and failures.
4. Start repair sessions only on independent workspace copies.
5. Exercise one approved operation at a time before mixed-operation sequences.
6. Retain before/after reports, source/workspace signatures, checkpoints, and
   operator decisions. Never promote a skipped or failed check as a pass.

## Small Meshes

- `statue-bastet` — Bastet (16,520 triangles, 0.79 MiB)
- `statue-asad-al-lat` — Asad Al-Lat (29,402 triangles, 1.40 MiB)
- `statue-ganesha-java-10c` — Ganesha, 10th–11th century CE (63,950 triangles, 3.05 MiB)
- `statue-castlestrange-stone` — Castlestrange Stone (67,652 triangles, 3.23 MiB)
- `statue-belvedere-torso` — Belvedere Torso (97,796 triangles, 4.66 MiB)
- `statue-laurana-woman-bust` — Woman by Francesco Laurana (99,868 triangles, 4.76 MiB)

Use these first for importer, registration, report-schema, selection, session,
failure-recovery, and quick operator-flow checks.

## Medium Meshes

- `statue-greek-slave-smithsonian-150k` — The Greek Slave, 150k plaster cast (149,965 triangles, 7.15 MiB)
- `statue-cosmic-buddha-smithsonian-150k` — Cosmic Buddha, 150k laser scan (150,000 triangles, 7.15 MiB)
- `statue-caracalla-bust` — Bust of Emperor Caracalla (181,169 triangles, 8.64 MiB)
- `statue-hotei-water-basin` — Ana-Hachimangu Hotei water basin (280,209 triangles, 13.36 MiB)
- `statue-mick-odwyer` — Mick O'Dwyer (400,000 triangles, 19.07 MiB)
- `statue-laocoon-group` — Laocoön Group (600,000 triangles, 28.61 MiB)

Use these for routine Standard/Deep timing, evidence bounds, undo/restore, and
before/after comparison with representative organic detail.

## Large Meshes

- `statue-hizen-komainu` — Hizen Komainu at Hachiryū Shrine (1,998,496 triangles, 95.30 MiB)
- `statue-dainichi-nyorai-tower` — Dainichi Nyorai Tower at Jūni Shrine (1,249,711 triangles, 59.59 MiB)
- `statue-david-michelangelo` — David (1,199,948 triangles, 57.22 MiB)
- `statue-bato-kannon-shirane` — Batō Kannon at Shirane (995,673 triangles, 47.48 MiB)
- `statue-thinker-rodin` — The Thinker (837,482 triangles, 39.93 MiB)
- `statue-pieta-michelangelo` — Pietà (815,738 triangles, 38.90 MiB)

Use these only after the small/medium sequence passes. Record AC status, CPU
frequency/performance, RAM, paging, process count, and CPU-versus-wall time.

## Repair Stress Models

- `statue-laocoon-group` — Laocoön Group (600,000 triangles, 28.61 MiB)
- `statue-pieta-michelangelo` — Pietà (815,738 triangles, 38.90 MiB)
- `statue-hizen-komainu` — Hizen Komainu at Hachiryū Shrine (1,998,496 triangles, 95.30 MiB)
- `statue-thinker-rodin` — The Thinker (837,482 triangles, 39.93 MiB)
- `statue-uma-maheshvara-java-10c` — Uma-Maheshvara, 10th–11th century CE (99,994 triangles, 4.77 MiB)
- `statue-water-buffalo-boy` — Water Buffalo and Boy (661,492 triangles, 31.54 MiB)

These models have group compositions, drapery, weathering, extended forms, or
high density that may expose workspace-copy, checkpoint, mapping, and
detail-preservation risks. Candidate presence is not guaranteed; never force an
operation when the plan is empty, stale, ambiguous, or ineligible.

## Diagnostic Stress Models

- `statue-hizen-komainu` — Hizen Komainu at Hachiryū Shrine (1,998,496 triangles, 95.30 MiB)
- `statue-dainichi-nyorai-tower` — Dainichi Nyorai Tower at Jūni Shrine (1,249,711 triangles, 59.59 MiB)
- `statue-bato-kannon-shirane` — Batō Kannon at Shirane (995,673 triangles, 47.48 MiB)
- `statue-belvedere-torso` — Belvedere Torso (97,796 triangles, 4.66 MiB)
- `statue-asad-al-lat` — Asad Al-Lat (29,402 triangles, 1.40 MiB)
- `statue-venus-de-milo` — Venus de Milo (607,274 triangles, 28.96 MiB)

These include weathered photogrammetry, fragments, monuments, reconstructed
heritage, and high-density surfaces. Treat Deep output as bounded heuristic
evidence, not printability, wall-thickness, or repair proof.

## Future Benchmark Models

- `statue-bastet` — Bastet (16,520 triangles, 0.79 MiB)
- `statue-castlestrange-stone` — Castlestrange Stone (67,652 triangles, 3.23 MiB)
- `statue-greek-slave-smithsonian-150k` — The Greek Slave, 150k plaster cast (149,965 triangles, 7.15 MiB)
- `statue-laocoon-group` — Laocoön Group (600,000 triangles, 28.61 MiB)
- `statue-pieta-michelangelo` — Pietà (815,738 triangles, 38.90 MiB)
- `statue-hizen-komainu` — Hizen Komainu at Hachiryū Shrine (1,998,496 triangles, 95.30 MiB)

This six-case ladder spans the observed corpus. A future benchmark record should
include asset SHA-256, Blender and Chroma3D versions, machine/power state,
profile/settings, import time, analysis time, repair time by operation, peak
memory when available, outcome, warnings, and retained report paths.

## Manual Evidence Checklist

- Work from `datasets/statues/raw/` as immutable source evidence.
- Verify source and workspace signatures before every geometry mutation.
- Confirm the source remains byte/geometry unchanged after every operation.
- Capture actual diagnostics; do not infer expected defects from file size.
- Review faces, fingers, jewelry, inscriptions, drapery, thin forms, and
  culturally significant attributes for visible loss.
- Record accepted, rejected, ambiguous, no-op, skipped, and failed outcomes
  separately.
- Use the model's metadata title and classification respectfully in reports.
