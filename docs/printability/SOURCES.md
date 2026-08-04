# Printability Research Sources

Access date for this Sprint 2.8 ledger: `2026-08-04`.

| Source ID | Organization/author | Title | URL | Access date | Source type | Topics/rules supported | Authority classification | Limitations |
|---|---|---|---|---|---|---|---|---|
| SRC-001 | ISO/ASTM | ISO/ASTM 52900:2021 - Additive manufacturing - General principles - Fundamentals and vocabulary | https://www.iso.org/standard/74514.html?browse=tc | 2026-08-04 | International standard | AM terminology and process vocabulary | STANDARDS_BASED | Terminology only; this specification does not claim conformity |
| SRC-002 | ASTM International | Additive Manufacturing Standards overview | https://store.astm.org/products-services/standards-and-publications/standards/additive-manufacturing-standards.html | 2026-08-04 | Standards organization guidance | Standards landscape and terminology context | AUTHORITATIVE_SOURCE | Overview, not a process threshold |
| SRC-003 | Bambu Lab | X1 Carbon technical specifications | https://us.store.bambulab.com/products/x1-carbon?variant=42698346037384 | 2026-08-04 | Manufacturer specification | X1 Carbon 256 x 256 x 256 mm build volume and included 0.4 mm nozzle | MANUFACTURER_SPECIFIC | Advertised volume; usable envelope and process settings can differ |
| SRC-004 | Bambu Lab | Bambu Lab printer comparison - P1S | https://bambulab.com/en-us/compare?type=p1 | 2026-08-04 | Manufacturer specification | P1S 256 x 256 x 256 mm build volume | MANUFACTURER_SPECIFIC | Comparison page does not establish wall or overhang guarantees |
| SRC-005 | Bambu Lab | P1S Quick Start Guide | https://cdn1.bambulab.com/documentation/quick-start-59b0cefdc0fc4/P1S/English%20version-Quick%20Start%20Guide%20for%20P1S.pdf | 2026-08-04 | Manufacturer technical guide | P1S process type, build volume, nozzle options | MANUFACTURER_SPECIFIC | Hardware facts do not define generic statue thresholds |
| SRC-006 | Prusa Research | Modeling with 3D printing in mind | https://help.prusa3d.com/article/modeling-with-3d-printing-in-mind_164135?product=core-one | 2026-08-04 | Slicer/manufacturer guidance | Layered deposition, nozzle/extrusion width, overhang/support review | SLICER_GUIDANCE | Guidance depends on printer, material, and settings |
| SRC-007 | Prusa Research | Layers and perimeters | https://help.prusa3d.com/article/layers-and-perimeters_1748 | 2026-08-04 | Slicer documentation | Layer-height/nozzle relationship, perimeter width, thin walls, bridges | SLICER_GUIDANCE | PrusaSlicer behavior is not every slicer's behavior |
| SRC-008 | Prusa Research | FAQ - MK4/S build volume | https://help.prusa3d.com/article/faq-frequently-asked-questions_1932?product=xl | 2026-08-04 | Manufacturer support documentation | MK4 250 x 210 x 220 mm build volume | MANUFACTURER_SPECIFIC | Page includes product variants; profile records selected model |
| SRC-009 | Formlabs | Form 4 Design Guide | https://formlabs.com/white-papers/form-4-design-guide/ | 2026-08-04 | Manufacturer process guide | Resin thin walls, unsupported angles, spans, wires, drain-hole deferral | MANUFACTURER_SPECIFIC | Grey Resin, Form 4, stated layer/post-process conditions |
| SRC-010 | Formlabs | Design specifications for 3D models - Form 3/Form 3B | https://formlabs.com/support/Design-specifications-for-3D-models-form-3/ | 2026-08-04 | Manufacturer process guide | Resin supported/unsupported walls and support-sensitive features | MANUFACTURER_SPECIFIC | Form 3 and Clear Resin at stated layer conditions |
| SRC-011 | Formlabs | How supports work in SLA printing | https://formlabs.com/global/support/How-supports-work-in-SLA-printing/ | 2026-08-04 | Manufacturer process guidance | Support dependence, orientation, unsupported islands, resin process context | MANUFACTURER_SPECIFIC | Does not specify generic resin thresholds |
| SRC-012 | Rolland-Neviere, Doerr, Alliez | Robust diameter-based thickness estimation of 3D objects | https://doi.org/10.1016/j.gmod.2013.06.001 | 2026-08-04 | Peer-reviewed paper | Shape Diameter Function, robust thickness, AABB/ray and defect limitations | PEER_REVIEWED_METHOD | General geometry method; not a Chroma3D printability validation |
| SRC-013 | Das, Mhapsekar, Chowdhury, Samant, Anand | Selection of build orientation for optimal support structures and minimum part errors | https://doi.org/10.1080/16864360.2017.1308074 | 2026-08-04 | Peer-reviewed paper | Multi-objective orientation, support/contact/error trade-offs | PEER_REVIEWED_METHOD | Method/process-specific; no global optimum for Chroma3D |
| SRC-014 | Gay et al. | Optimum Part Build Orientation in Additive Manufacturing for Minimizing Part Errors and Support Structures | https://doi.org/10.1016/j.promfg.2015.09.041 | 2026-08-04 | Peer-reviewed paper | Orientation as a multi-objective manufacturing decision | PEER_REVIEWED_METHOD | DMLS study; evidence informs method shape only |

## Classification and use ledger

- SRC-001 and SRC-002 define vocabulary and standards context. Chroma3D does
  not claim standards compliance from using their terminology.
- SRC-003, SRC-004, and SRC-005 support only the listed Bambu hardware facts.
- SRC-008 supports the selected Prusa MK4 build-volume fact. No wall or
  overhang value is inferred from a product's build volume.
- SRC-006 and SRC-007 explain FDM process dependencies and slicer behavior.
  Their values are not copied as universal manufacturing limits.
- SRC-009, SRC-010, and SRC-011 are resin/manufacturer examples. They are not
  used to make a generic resin profile authoritative.
- SRC-012 supports research alternatives for thickness estimation; SRC-013 and
  SRC-014 support the multi-objective orientation framing.

## Rejected weak evidence

Community forums, unsourced threshold tables, marketing summaries without a
test setup, and generic “works every time” claims were rejected for setting
rules. They may be useful operator anecdotes later only if printer, material,
layer, orientation, support, and outcome metadata are retained.
