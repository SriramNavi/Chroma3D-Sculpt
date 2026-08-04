# Golden Benchmark Baseline Summary

## Outcome

- Benchmark version: `1.0.0`
- Dataset version: `1.0.0`
- Chroma3D version: `0.3.0-alpha.1`
- Meshes benchmarked: 27
- Failed meshes: 0
- Stored warnings: 89
- Total wall time: 7432.224 seconds
- Total Blender CPU time: 7208.328 seconds
- Peak observed process working set: 3.509 GiB

The stored warnings are production diagnostic evidence. They are not benchmark
execution failures.

## Per-mesh Results

| Mesh | Triangles | Timing class | Mesh classification | Before severity | Selected operations | Analysis s | Repair s | Warnings |
| --- | ---: | --- | --- | --- | ---: | ---: | ---: | ---: |
| `statue-asad-al-lat` | 29,402 | Small | Architectural carving, Animal | WARNING | 0 | 1.987 | 0.000 | 5 |
| `statue-bastet` | 16,520 | Tiny | Printable STL, Animal | WARNING | 0 | 1.086 | 0.000 | 5 |
| `statue-bato-kannon-shirane` | 995,673 | Huge | Photogrammetry, High-detail sculpture, Architectural carving | WARNING | 0 | 65.932 | 0.000 | 7 |
| `statue-belvedere-torso` | 97,796 | Small | Museum Scan, Human | PASS | 0 | 5.709 | 0.000 | 0 |
| `statue-caracalla-bust` | 181,169 | Medium | Bust, Human | WARNING | 1 | 10.521 | 23.312 | 7 |
| `statue-castlestrange-stone` | 67,652 | Small | Architectural carving | WARNING | 0 | 4.022 | 0.000 | 5 |
| `statue-cosmic-buddha-smithsonian-150k` | 150,000 | Medium | Museum Scan, Photogrammetry, Full statue, Human | PASS | 0 | 8.840 | 0.000 | 0 |
| `statue-dainichi-nyorai-tower` | 1,249,711 | Extreme | Photogrammetry, High-detail sculpture, Architectural carving, Animal | WARNING | 0 | 65.283 | 0.000 | 6 |
| `statue-danaid-rodin` | 110,538 | Medium | Museum Scan, Full statue, Human | PASS | 0 | 6.725 | 0.000 | 0 |
| `statue-david-michelangelo` | 1,199,948 | Extreme | Museum Scan, Photogrammetry, High-detail sculpture, Full statue, Human | WARNING | 0 | 67.877 | 0.000 | 3 |
| `statue-ganesha-java-10c` | 63,950 | Small | Museum Scan, Full statue, Human | PASS | 0 | 3.739 | 0.000 | 0 |
| `statue-greek-slave-smithsonian-150k` | 149,965 | Medium | Museum Scan, Full statue, Human | WARNING | 0 | 8.639 | 0.000 | 6 |
| `statue-hercules-archer-mia` | 99,983 | Small | Museum Scan, Full statue, Human | WARNING | 0 | 5.775 | 0.000 | 5 |
| `statue-heroic-head-pierre-de-wissant` | 623,366 | Huge | High-detail sculpture, Bust, Human | WARNING | 0 | 38.117 | 0.000 | 2 |
| `statue-hizen-komainu` | 1,998,496 | Extreme | Photogrammetry, High-detail sculpture, Guardian, Animal | WARNING | 1 | 101.966 | 244.505 | 8 |
| `statue-hotei-water-basin` | 280,209 | Large | Architectural carving | WARNING | 0 | 16.088 | 0.000 | 4 |
| `statue-icarus-ioannidou` | 146,505 | Medium | Photogrammetry, Full statue, Human | WARNING | 0 | 8.975 | 0.000 | 4 |
| `statue-juno-ludovisi` | 642,984 | Huge | Museum Scan, High-detail sculpture, Bust, Human | PASS | 0 | 41.301 | 0.000 | 0 |
| `statue-laocoon-group` | 600,000 | Huge | Museum Scan, High-detail sculpture, Full statue, Human | PASS | 0 | 38.406 | 0.000 | 0 |
| `statue-laurana-woman-bust` | 99,868 | Small | Museum Scan, Photogrammetry, Bust, Human | WARNING | 0 | 5.716 | 0.000 | 2 |
| `statue-mick-odwyer` | 400,000 | Large | Full statue, Human | WARNING | 0 | 23.779 | 0.000 | 6 |
| `statue-pieta-michelangelo` | 815,738 | Huge | Museum Scan, High-detail sculpture, Full statue, Human | WARNING | 0 | 51.937 | 0.000 | 3 |
| `statue-thinker-rodin` | 837,482 | Huge | Museum Scan, High-detail sculpture, Full statue, Human | WARNING | 0 | 53.328 | 0.000 | 2 |
| `statue-uma-maheshvara-java-10c` | 99,994 | Small | Museum Scan, Full statue, Human | WARNING | 0 | 5.784 | 0.000 | 5 |
| `statue-venus-de-milo` | 607,274 | Huge | Museum Scan, High-detail sculpture, Full statue, Human | WARNING | 0 | 38.740 | 0.000 | 2 |
| `statue-venus-willendorf` | 699,996 | Huge | Museum Scan, High-detail sculpture, Human | PASS | 0 | 44.797 | 0.000 | 0 |
| `statue-water-buffalo-boy` | 661,492 | Huge | Photogrammetry, High-detail sculpture, Full statue, Animal, Human | WARNING | 0 | 39.746 | 0.000 | 2 |

## Timing Distribution

| Class | Meshes |
| --- | ---: |
| Tiny | 1 |
| Small | 7 |
| Medium | 5 |
| Large | 2 |
| Huge | 9 |
| Extreme | 3 |

Triangle thresholds are Tiny `<25k`, Small `<100k`, Medium `<250k`, Large
`<500k`, Huge `<1m`, and Extreme `>=1m`.

## Repair Statistics

| Operation outcome | Records |
| --- | ---: |
| APPLIED | 2 |
| UNDONE | 2 |

The canonical plan uses production defaults. Candidate-based destructive
operations and orientation changes remain unselected unless the production
plan selects them through its normal UI state.

## Known Limitations

- Timings are authoritative only as a reference for this recorded machine,
  Blender version, power state, and one-fresh-process-per-mesh execution model.
- Peak memory is the Windows process high-water mark, sampled at phase
  boundaries; it is not a line-by-line allocator trace.
- Standard diagnostics are benchmarked. Deep self-intersection heuristics are
  outside Sprint 2.6.
- A production repair plan can legitimately select no operation. Such a mesh
  records an honest not-applicable comparison rather than a fabricated repair.
- Geometry still requires human review; the baseline is regression evidence,
  not a printability guarantee.
