# Dataset 1.0.0 Physical Model Selection

All ten sources are validation-cache references. Their raw SHA-256 values and
licenses come from the validated Dataset `1.0.0` manifest. Source STL units are
unspecified; target height is a planning goal and scale must be confirmed
manually in the slicer.

| Priority | Dataset ID | Title | License | Triangles / class | Target height | Print difficulty | Why selected / predicted risks | Expected evidence |
|---:|---|---|---|---|---:|---|---|---|
| 1 | `statue-bastet` | Bastet | CC-BY-4.0 | 16,520 / Tiny | 80 mm | Low | Low-complexity baseline; broad-base/contact and ordinary overhang control. | Baseline agreement for contact, overhang, overall status, and confidence. |
| 2 | `statue-asad-al-lat` | Asad Al-Lat | CC0-1.0 | 29,402 / Small | 90 mm | Low | Monument reconstruction; compact topology, base contact, surface overhangs. | Contact-region and surface-overhang observations with base photos. |
| 3 | `statue-ganesha-java-10c` | Ganesha | CC0-1.0 | 63,950 / Small | 90 mm | Medium | Hindu museum scan; multiple attributes, thin ornaments, compact seated base. | Ornament survival, wall/feature measurements, and contact evidence. |
| 4 | `statue-hercules-archer-mia` | Hercules as Archer | CC0-1.0 | 99,983 / Small | 110 mm | High | Extended limbs/weapon details; thin features, overhangs, support-removal risk. | Thin-feature survival, overhang quality, and support-removal damage evidence. |
| 5 | `statue-uma-maheshvara-java-10c` | Uma-Maheshvara | CC0-1.0 | 99,994 / Small | 100 mm | Medium | Hindu multi-figure relief; crowded detail, cavities, contact and overhang regions. | Cavity/overhang observations and evidence for detached or floating regions. |
| 6 | `statue-cosmic-buddha-smithsonian-150k` | Cosmic Buddha | CC0-1.0 | 150,000 / Medium | 100 mm | Medium | High-detail laser scan; robe overhangs and broad-base comparison. | Robe-overhang close-ups, broad-base adhesion, score/confidence agreement. |
| 7 | `statue-greek-slave-smithsonian-150k` | The Greek Slave | CC0-1.0 | 149,965 / Medium | 120 mm | High | Slender classical figure; narrow contact, limbs, orientation/stability trade-off. | Narrow-contact stability, limb survival, and controlled orientation evidence. |
| 8 | `statue-laocoon-group` | Laocoon Group | CC-BY-SA-4.0 | 600,000 / Huge | 110 mm | High | Complex multi-figure composition; disconnected/floating risk and severe overhang exposure. | Floating-component disposition, supported overhang quality, and slicer removals. |
| 9 | `statue-bato-kannon-shirane` | Bato Kannon at Shirane | CC-BY-4.0 | 995,673 / Huge | 90 mm | High | Weathered photogrammetry monument; noisy surface and high-detail robustness. | Skip-state truth, surface-quality observations, and base/contact evidence. |
| 10 | `statue-hizen-komainu` | Hizen Komainu | CC-BY-SA-4.0 | 1,998,496 / Extreme | 100 mm | High | Prior timeout stress model; noisy scan, complex base/contact, high computational risk. | Bounded-analysis/skip evidence plus physical base, surface, and stability observations. |

## Integrity records

| Dataset ID | Raw SHA-256 | Source |
|---|---|---|
| `statue-bastet` | `5fe8b7d22c7831f9e53dbd2ab70691945583be5fb3bcd681df16df7d5d683d22` | Wikimedia Commons `Thingiverse_-_Bastet.stl` |
| `statue-asad-al-lat` | `5748e4d150a370f34328ea768ced85ccafcaae6dd3c3891f2c0e80fb0a7a4ac8` | Wikimedia Commons `Asad_Al-Lat.stl` |
| `statue-ganesha-java-10c` | `5758dab5acda32bd928b0920c4fdb79ffc6c2211a141760a7ea6f15c261412b4` | Wikimedia Commons Ganesha 3D model |
| `statue-hercules-archer-mia` | `30d178b8e2e8c769883409a1c85e28a429ce022385fa0a918e16eda41b223017` | Wikimedia Commons Hercules as Archer 3D model |
| `statue-uma-maheshvara-java-10c` | `db055654560c508fd97249b0c88c33663aceebd9d293091136e99fd259b86702` | Wikimedia Commons Uma-Maheshvara 3D model |
| `statue-cosmic-buddha-smithsonian-150k` | `de75f3aa58ed3da3e27884cd96671ef172c98ce26f1b78510c4f3dda88e91e72` | Wikimedia Commons Smithsonian scan |
| `statue-greek-slave-smithsonian-150k` | `6057e7ac013894f5cff80f6faf4290c8356e6de0b1d6f227f0c38f3e74989f90` | Wikimedia Commons Smithsonian scan |
| `statue-laocoon-group` | `8f962593056edf56ce0272b7c2c0c4d4fef0324a2fe90130ed6fc80fcb936700` | Wikimedia Commons Scan the World |
| `statue-bato-kannon-shirane` | `e3695cb8fee26543780b9ab135a933d881c598a6247fde6fb2e265a73d4d5659` | Wikimedia Commons photogrammetry |
| `statue-hizen-komainu` | `127e2da11069dbdc17166588cffae0e4f8eaca3128fbe6c8d78c8eb4808bcec8` | Wikimedia Commons photogrammetry |

Difficulty and priority are experiment-planning judgments, not physical
outcomes. Expected evidence is engine-vs-observation agreement for wall,
feature, overhang, contact/stability, floating-component, score, confidence,
and any skipped/indeterminate check.
