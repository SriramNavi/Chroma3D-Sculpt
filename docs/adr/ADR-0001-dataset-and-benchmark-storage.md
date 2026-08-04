# ADR-0001: Dataset and Benchmark Storage

## Context

The 27-mesh Dataset `1.0.0` is approximately 630 MiB and the Sprint 2.6 golden baseline contains regenerable artifact payloads. Several STL files exceeded GitHub's recommended file size while the already-published product history must remain immutable.

## Problem

Future clones must stay lightweight without losing provenance, licensing, checksums, reproducibility, or the ability to run verified dataset and benchmark workflows offline.

## Options considered

- Ordinary Git: simple, but repeats the current clone-size problem.
- Git LFS: technically viable, but introduces quota, bandwidth, and service coupling.
- Separate Git repository: useful for lightweight policy/manifests, but not for large ordinary history.
- GitHub Release assets: versioned, checksumable, downloadable, and separate from product history.
- External object storage: flexible, but adds credentials, cost, retention, and operational ownership.
- Re-download only from upstream: fragile because source revisions and redistribution obligations can change.

## Decision

Use a separate lightweight dataset repository, `SriramNavi/Chroma3D-Benchmark-Dataset`, with large payloads attached to GitHub Releases. Keep canonical metadata, licenses, source URLs, manifests, schemas, locks, summaries, and acquisition/verification tooling in Chroma3D Sculpt. Use deterministic ZIP archives, SHA-256 sidecars, internal archive indexes, and atomic standard-library fetch tooling.

## Consequences and trade-offs

Product clones become lightweight at current HEAD and CI can fetch only what it needs. Initial acquisition depends on public GitHub availability and the corpus remains subject to license/attribution obligations. Release assets need retention and availability monitoring. Existing historical Git size is unchanged because history rewriting is prohibited. Git LFS remains a future option only if measured release-asset limits block this corpus.

## Migration and rollback

Build and verify release archives from the existing local corpus, write locks, retain lightweight canonical files, and remove only externalized payloads from the feature-branch index while leaving local ignored copies available. Rollback is a branch-level review decision: restore the tracked paths from the parent commit if the storage change is rejected; do not move tags or rewrite history. External publication is a later owner-authorized action.

## Future review triggers

Review this decision if release-asset availability or bandwidth is insufficient, the corpus exceeds practical release limits, access controls become necessary, legal takedown/retention requirements change, or CI measurements show that a different storage backend materially improves reliability without weakening verification.
