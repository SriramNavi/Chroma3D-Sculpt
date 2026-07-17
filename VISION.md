# Chroma3D Sculpt — Product Vision

## Executive Vision

Chroma3D Sculpt is intended to become a professional Blender-based engineering and creation workflow for turning complex statue meshes into reliable, high-detail, print-ready assets. It begins with trustworthy diagnostics and evidence, expands through safe preparation and controlled repair, and later adds optimization, domain-specific procedural assets, and carefully bounded AI-assisted recommendations. The product should remain useful as a local Blender extension while gaining modular commercial surfaces only when real production needs justify them.

The current foundation is `0.2.0-alpha.1`: Sprint 1 diagnostics are accepted on the feature branch, and Sprint 2 safe mesh repair has not started. Current capabilities are diagnostic only and provide no printability guarantee.

Across Windows and Blender 4.4.3 validation runs, Standard analysis of the current approximately 147,000-vertex synthetic fixture has ranged from about 12 to 29 seconds against the repository's 20-second performance warning threshold. Dense-mesh performance remains active technical debt; these synthetic results are not a hard guarantee for production assets, and real Chroma3D statue benchmarking is still required.

The long-term opportunity is not a generic mesh utility or text-to-3D wrapper. It is an ecosystem that joins sculptural craft, mesh engineering, 3D-print preparation, reusable statue workflows, and professional release discipline without hiding uncertainty or taking control away from the artist.

## Problem Statement

High-detail statue production sits between artistic sculpting and manufacturing engineering. AI-generated and imported meshes frequently need cleanup, while faces, fingers, jewelry, crowns, ornaments, weapons, and thin forms are common failure points. Source files may arrive with unknown scale, unclear orientation, disconnected shells, internal structures, or topology that looks closed but is not topologically watertight.

Finding and correcting these problems is slow. Blender provides powerful general-purpose tools, but operators must combine them across fragmented workflows and understand subtle topology and print constraints. Manual repair can be destructive, and manufacturing failures may appear only after slicing or printing. Generic AI systems do not understand Chroma3D's statue domain, cannot establish geometry correctness, and often lack safe review and rollback boundaries.

Chroma3D Sculpt should move defect discovery earlier, explain what was evaluated, preserve the original asset, and make preparation work repeatable. It must distinguish evidence from inference: self-intersection candidates are not exact intersections, a possibly internal shell is a heuristic classification, and no analysis is a printability guarantee.

## Target Users

| Group | Their job | Their pain | Value provided |
|---|---|---|---|
| Primary — Chroma3D internal production operators | Prepare high-detail statues for reliable manufacturing | Repeated manual checks, inconsistent cleanup, late print failures, and knowledge concentrated in a few people | A repeatable, evidence-producing Blender workflow validated on real Chroma3D models |
| Primary — independent 3D-printing studios and small decorative-manufacturing teams | Convert customer or generated meshes into printable jobs | Uncertain source quality, expensive reprints, printer constraints, and limited specialist time | Faster triage, controlled preparation, printer-aware checks, and auditable decisions |
| Primary — statue, figurine, and digital-sculpt creators | Preserve artistic detail while delivering printable models | Fragile features, disconnected ornamentation, destructive cleanup, and tool fragmentation | Statue-aware diagnostics, reversible repair, and detail-preserving optimization inside Blender |
| Secondary — technical mesh-preparation specialists and FDM/resin professionals | Diagnose and correct difficult organic assets | Large meshes, ambiguous shell intent, and repetitive validation across tools | Bounded evidence, explicit states, repair planning, and comparable before/after results |
| Future — miniature, jewelry, ornamental, cultural, devotional, collectible, and educational creators | Build specialized printable assets with domain constraints | General tools lack reusable domain assets and reviewed rule sets | Procedural libraries, governed rule packs, reference workflows, and artist-controlled assistance |
| Future — enterprise 3D-production teams | Standardize preparation across people and projects | Version drift, inconsistent evidence, asset governance, and deployment/support needs | Managed libraries, team workflows, production analytics, controlled deployment, and service integrations where justified |

## Long-Term Product Identity

Chroma3D Sculpt is the potential foundation of a modular ecosystem. The following names describe future product directions, not products available today:

- **Chroma3D Sculpt:** Blender-native statue mesh diagnostics, preparation, safe repair, and optimization.
- **Chroma3D Print Prep:** printer-aware validation, orientation, export gates, and FDM/resin workflows.
- **Chroma3D Asset Studio:** governed procedural and reusable statue components, presets, and Geometry Nodes workflows.
- **Chroma3D AI Assist:** constrained recommendations translated into reviewable, allow-listed deterministic operations.
- **Chroma3D Marketplace:** curated asset packs and domain rule packs with provenance, licensing, and quality controls.
- **Chroma3D Enterprise:** team deployment, managed libraries, policy controls, integrations, and production analytics.

These surfaces should share an evidence model and deterministic local core. Packaging them as separate editions should remain a commercial decision based on validated demand, not an early architecture constraint.

## Strategic Differentiators

- **Statue and ornament specialization:** workflows designed around faces, hands, jewelry, crowns, halos, garlands, pedestals, and other high-detail organic or decorative forms.
- **Printability-focused engineering:** topology, dimensions, scale, shell intent, thickness, overhang, contact, orientation, and export checks organized around manufacturing preparation.
- **Evidence-driven diagnostics:** bounded issue samples, analysis identifiers, settings snapshots, explicit check states, and versioned reports.
- **Safe, reversible repair:** protected originals, previewed repair plans, user-approved operations, before/after comparison, undo, and audit records.
- **Domain-aware asset libraries:** reusable procedural components and presets shaped by real statue production rather than generic asset catalogs.
- **Blender-native workflow:** analysis and preparation remain close to the artist's existing scene, tools, and review process.
- **Pragmatic hybrid architecture:** local and offline capability for core work, with cloud services added only for capabilities that need them.
- **Production feedback:** real Chroma3D models and print outcomes drive priorities, fixtures, performance baselines, and quality gates.
- **Explicit limits and confidence states:** heuristics, skipped checks, failed checks, and bounded analyses remain visible instead of being converted into false certainty.
- **Commercial modularity:** a deterministic core can support professional editions, asset packs, optional services, and enterprise controls without premature cloud complexity.

## Product Principles

1. Make non-destructive behavior the default.
2. Preserve the original asset and keep recovery paths explicit.
3. Prefer deterministic operations before AI assistance.
4. Complete diagnostics before proposing repair.
5. Require user review before destructive action.
6. Represent completed, skipped, failed, and not-applicable evaluations explicitly.
7. Label heuristics, candidates, and confidence honestly.
8. Never imply a printability or manufacturing guarantee.
9. Produce evidence that operators can inspect, export, compare, and audit.
10. Make geometry-changing operations reversible and recovery-oriented.
11. Define measurable acceptance, regression, performance, security, and release gates.
12. Keep core workflows local and offline wherever practical.
13. Add commercial architecture without premature cloud complexity.
14. Treat statue-domain specialization as the product's advantage.
15. Use real, permissioned Chroma3D production models as the primary validation source.
16. Design for high-density meshes with bounded work, progress, cancellation, and honest limits.
17. Maintain modular boundaries suitable for future editions and optional services.
18. Constrain AI output to structured recommendations and allow-listed operations.
19. Never execute arbitrary generated Python, hidden downloaded code, or unvalidated commands.
20. Maintain professional security, privacy, compatibility, test, package, and release discipline.

## Three-to-Five-Year Horizon

These horizons are capability stages, not calendar commitments.

### Horizon 1 — Internal Production Tool

Deliver trusted diagnostics, safe mesh repair, foundational print preparation, and repeatable internal Chroma3D adoption. Validate behavior and performance on sanitized real statue models, and measure time saved and defects caught before expanding scope.

### Horizon 2 — Professional Blender Product

Turn validated internal workflows into a polished professional product with reliable optimization, accessible UX, representative model coverage, documentation, installation, updates, licensing, recovery, and an external beta. Commercial readiness depends on evidence from real production tasks, not feature count.

### Horizon 3 — Domain-Specific Creation Platform

Add procedural statue assets, reference-guided workflows, governed domain rule packs, and AI-assisted recommendations that remain reviewable and execute through deterministic operators. Evaluate a curated marketplace and specialized editions only after asset provenance, quality, and support processes exist.

### Horizon 4 — Ecosystem and Enterprise

Support team workflows, managed asset libraries, production analytics, controlled enterprise deployment, and API or backend services where scale, licensing, collaboration, asset delivery, or AI routing demonstrably requires them.

## Success Definition

Success will be evaluated through measurable production outcomes rather than unverified market claims:

- Median operator time spent diagnosing and cleaning a representative model decreases.
- More actionable defects are found before slicing and fewer prints fail for preventable mesh-preparation reasons.
- Operators rely on fewer disconnected tools and manual checklists for a standard preparation job.
- Before/after evidence shows repairs preserve approved detail and do not introduce regressions.
- Different artists produce more consistent results using the same policies and model categories.
- Internal workflows are repeatable, recoverable, and supported by versioned reports and fixtures.
- External alpha and beta users complete defined production journeys without expert intervention.
- Performance remains acceptable across declared complexity bands, with honest progress and cancellation behavior.
- Professional editions, asset packs, or optional services generate sustainable revenue without weakening local core workflows.

Targets for these measures should be set only after baseline data is collected during Chroma3D production UAT.

## What the Product Will Not Become

Chroma3D Sculpt will not promise unbounded one-click autonomous sculpting or museum-quality output. It will not modify geometry blindly, execute arbitrary Python, disguise heuristic classifications as facts, or claim that analysis proves manufacturing success. It will not present Chroma3D-specific rules as universal cultural or manufacturing truth. It will not become a generic AI wrapper, a cloud-dependent gate for basic local work, or a replacement for artist judgment and printer-specific validation.

## Closing Vision Statement

Chroma3D Sculpt will make high-detail statue production more reliable by combining Blender-native craft with evidence-driven mesh engineering, reversible preparation, domain-specific creation tools, and carefully governed assistance—giving artists and production teams greater control from imported mesh to print-ready asset.
