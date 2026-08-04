# Chroma3D Sculpt - Sprint 2.8 Printability Engineering Specification

**Status:** Sprint 2.8 specification milestone complete for review; Sprint 3 remains unstarted.

| Contract item | Value |
|---|---|
| Repository release at this milestone | `v0.3.1-alpha.1` |
| Blender extension version | `0.3.0-alpha.1` (unchanged) |
| Dataset dependency | Dataset `1.0.0` (unchanged) |
| Golden Benchmark dependency | Golden Benchmark `1.0.0` (unchanged) |
| Proposed printability benchmark | Printability Benchmark `1.0.0` (not generated in Sprint 2.8) |
| Runtime implementation | None; Sprint 3 implementation is not authorized by this document |

## Purpose

This document is the implementation contract for a future advisory Printability
Engine. It defines measurements, profile-dependent evaluations, risk states,
evidence, scoring, reports, performance limits, fixtures, and acceptance gates.
It does not add runtime functionality, Blender operators, geometry mutation,
automatic transforms, slicing, support generation, or a manufacturing claim.

The product question is:

> What geometric and profile-dependent risks were detected for this model, and
> what actions should the user review before printing?

The product must not answer that the model is guaranteed printable, will print successfully, or that any orientation is perfect. A report is advisory evidence for
operator and slicer review; it is not a printability guarantee.

## Design principles

1. Measure geometry facts before applying printer/process policy.
2. Keep every threshold classified as authoritative, standards-based,
   manufacturer-specific, project default, heuristic, user-configurable,
   experimental, or not yet defined.
3. Preserve uncertainty. `NOT_EVALUATED`, `SKIPPED_LIMIT`, `INDETERMINATE`, and
   `FAILED` are meaningful outcomes, never successful zero-risk substitutes.
4. Bound samples, evidence, candidate counts, memory, and expensive work.
5. Bind results to geometry, transform, profile, build direction, and settings
   signatures. Stale printability evidence cannot drive issue selection.
6. Recommend review actions without changing the mesh, orientation, scale, or
   scene automatically.
7. Keep FDM and resin policy separate. Resin hollowing, drain holes, suction,
   and support generation are deferred.
8. Expose a score only with status, confidence, primary reasons, skipped checks,
   and failed checks.

## Evaluation pipeline

```text
Geometry facts
    -> profile evaluation
    -> check result and risk items
    -> score aggregation with critical caps
    -> bounded evidence and user review actions
```

Geometry facts include world-space dimensions, shell topology, connected
components, reliable volume where valid, local thickness samples, downward
surface area, build-plane contact, floating shell IDs, and transform/signature
data. Profile evaluation adds thresholds, process assumptions, build-volume
limits, margins, and orientation weights. The two layers must remain separately
serializable.

## Sprint 3 advisory scope

The future runtime may implement:

- wall-thickness risk analysis;
- thin-feature risk analysis;
- overhang risk analysis;
- floating-component detection;
- build-plate contact analysis;
- build-volume and scale evaluation without applying scale;
- bounded orientation candidate evaluation;
- versioned FDM, resin, and custom profiles;
- risk aggregation and a score with critical caps;
- bounded evidence selection;
- JSON and Markdown reports.

The following are explicitly deferred: support generation, G-code, slicing,
automatic geometry repair, automatic rotation or scaling, remeshing, Boolean
repair, exact print-time prediction, thermal or warping simulation, resin
hollowing, drain-hole generation, suction-cup simulation, material simulation,
full bridge simulation, AI recommendations, cloud services, and any claim that
printing will succeed.

## Required contract documents

The detailed contracts are maintained under [`docs/printability/`](docs/printability/README.md):

- [Terminology and result states](docs/printability/TERMINOLOGY_AND_RESULT_STATES.md)
- [Rule classification registry](docs/printability/RULE_CLASSIFICATION.md)
- [Wall-thickness method](docs/printability/WALL_THICKNESS_METHOD.md)
- [Thin-feature method](docs/printability/THIN_FEATURE_METHOD.md)
- [Overhang method](docs/printability/OVERHANG_METHOD.md)
- [Floating components](docs/printability/FLOATING_COMPONENTS.md)
- [Build-plate contact](docs/printability/BUILD_PLATE_CONTACT.md)
- [Scale and build volume](docs/printability/SCALE_AND_BUILD_VOLUME.md)
- [Orientation recommendation](docs/printability/ORIENTATION_RECOMMENDATION.md)
- [Scoring](docs/printability/PRINTABILITY_SCORING.md)
- [Performance modes](docs/printability/PERFORMANCE_MODES.md)
- [Validation fixtures](docs/printability/VALIDATION_FIXTURES.md)
- [Sprint 3 acceptance gates](docs/printability/ACCEPTANCE_GATES.md)
- [Sources](docs/printability/SOURCES.md)
- [Open questions](docs/printability/OPEN_QUESTIONS.md)

Machine-readable contracts are under [`schemas/`](schemas/printer_profile.schema.json)
and profile examples under [`profiles/printability/`](profiles/printability/README.md).

## Report contract

The report must carry the report schema version, extension and Blender versions,
analysis and run identifiers, object metadata, geometry and transform
signatures, a printer-profile snapshot, settings, build direction, geometry
facts, each check result, risk items, score/status/confidence, orientation
candidates, bounded evidence, skipped and failed checks, timings, warnings,
limitations, and stale-state data. JSON is UTF-8, deterministic where practical,
newline-terminated, and Windows-safe. Raw mesh payloads are forbidden.

## Review boundary

Sprint 2.8 is accepted only when the specification validator passes, all profile
examples validate, schemas parse, sources and classifications are traceable,
and the project remains unchanged at runtime. Sprint 0, Sprint 1, Sprint 2,
Dataset `1.0.0`, and Golden Benchmark `1.0.0` are regression inputs, not altered
by this milestone. Review and approval of this contract is required before any
Sprint 3 runtime implementation begins.
