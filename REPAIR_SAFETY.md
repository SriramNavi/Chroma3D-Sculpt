# Repair Safety Contract

## Purpose

Sprint 2 introduces controlled geometry modification while guaranteeing protection of the original source object. This document defines the safety boundary for every geometry-changing operation in Chroma3D Sculpt. Every current and future repair implementation must satisfy this contract.

## Core Principles

- **Source preservation:** The original source object and its state are immutable for the lifetime of a repair session.
- **Independent repair workspace:** Every geometry mutation targets a session-owned object with an independent mesh datablock.
- **Explicit user approval:** Detection and recommendation never authorize a repair. The user must explicitly choose the operation, and candidate-based operations require explicit candidate selection.
- **Checkpoint-first architecture:** A valid checkpoint must exist before any mutation begins.
- **Honest reporting:** Results, failures, skips, undo actions, and final decisions must describe what actually happened.
- **Deterministic behavior:** The same valid input, settings, plan, and candidate selections must produce the same ordered repair behavior.
- **No hidden geometry mutation:** Analysis, plan generation, preview, comparison, and audit export are read-only. Geometry may change only through an explicit repair command.

## Source Preservation Rules

The protected source object must never be modified by a repair session. This prohibition covers:

- mesh geometry;
- topology;
- vertex coordinates;
- object transforms;
- modifiers;
- materials;
- custom properties;
- collection membership;
- visibility state; and
- object and mesh datablock identity.

At session start, Chroma3D Sculpt captures a protected signature and source snapshot. Together they bind the source object and mesh datablock identities to geometry, connectivity and winding, coordinates, transforms, modifiers, materials, custom properties, collection membership, visibility, names, and blend-file context. The source is revalidated before and after repair operations. A missing source, replaced datablock, identity mismatch, or signature mismatch blocks further repair.

## Workspace Ownership

A repair session creates a dedicated workspace object and a copied mesh datablock. The workspace object must not be the source object, and the workspace mesh must not share the source mesh datablock.

The active session owns the workspace, its temporary checkpoint meshes, its repair plan, and its audit state until the session ends. Rollback and failure cleanup may remove only resources created and owned by that session. Accept transfers the repaired workspace into ordinary scene ownership while retaining the protected source. Extension unload may release temporary checkpoints, but it must not implicitly delete an unfinished workspace.

## Repair Session Lifecycle

```text
Start Session
    ↓
Protected Signature
    ↓
Workspace Creation
    ↓
Analysis
    ↓
Repair Plan
    ↓
Checkpoint
    ↓
Repair
    ↓
Comparison
    ↓
Accept or Rollback
    ↓
Audit Export
```

Each transition must validate the active session and preserve the separation between the protected source and repair workspace. A failed transition must not be reported as successful.

## Repair Plan Contract

Generating or reviewing a repair plan must never modify geometry. A plan is an evidence-bound proposal, not permission to mutate the workspace.

A plan becomes stale and must be regenerated when any bound state changes, including:

- the session identity;
- the protected source signature or identity;
- the repair workspace signature, object, or mesh datablock;
- the current analysis identity;
- the repair settings snapshot;
- workspace geometry changed outside the session;
- an undo, restore, or successful geometry change; or
- a candidate mapping or fingerprint no longer matches the evidenced topology.

Candidate mappings must be validated against the current workspace before use. Missing, ineligible, unselected, stale, oversized, or otherwise rejected candidates must not execute. Recommendations must be derived from bounded diagnostic evidence, state their limitations, and remain subject to human review.

## Checkpoint Contract

A separate mesh checkpoint is required before every geometry mutation. If checkpoint creation fails, the operation must not begin. If an operation or its post-repair validation fails, Chroma3D Sculpt must restore the pre-operation checkpoint automatically and verify the restored workspace when possible.

**Undo Last Repair** restores the checkpoint associated with the most recent successfully applied operation, marks that operation as undone, reruns diagnostics, and invalidates the existing plan.

**Restore Workspace to Start** restores the retained initial checkpoint, marks applied operations as undone, clears later checkpoints, invalidates the plan and comparison, and reruns diagnostics.

Checkpoint history is bounded by the centralized repair setting. Sprint 2 retains a default maximum of three operation checkpoints in addition to the initial checkpoint. History eviction occurs only after a geometry-changing operation succeeds; a failed or no-change operation must not evict an earlier undo point.

## Operation Ordering

Sprint 2 uses this safe order:

1. Merge duplicate vertices.
2. Collapse zero-length edges.
3. Remove degenerate faces.
4. Remove loose geometry.
5. Remove explicitly selected tiny shells.
6. Fill explicitly selected bounded small holes.
7. Repair face-normal consistency.
8. Orient valid closed shells outward.

This order resolves deterministic local topology defects before cleanup, performs destructive candidate operations only after their mappings are validated, fills approved boundaries before final normal processing, and applies outward orientation only after the surviving closed shells and their face consistency are established. Implementations must not silently reorder selected operations.

## Candidate Selection Rules

Tiny-shell deletion requires explicit selection of an eligible, evidenced tiny-shell candidate. Hole filling requires explicit selection of an eligible, bounded small-hole candidate. Candidates are never preselected merely because they were detected or recommended.

There is no automatic destructive cleanup. The main shell must never be treated as a tiny-shell deletion candidate, and unselected, rejected, stale, oversized, or unrelated geometry must remain untouched.

## Accept vs Rollback

**Accept** revalidates the protected source, reruns diagnostics on the workspace, records the final state, gives the repaired object and mesh collision-safe repaired-copy names, clears session checkpoints, and retains both the protected source and the repaired copy. Accept never replaces, relinks, or deletes the source object and never saves the blend file automatically.

**Rollback** removes only the session-owned repair workspace and its unused workspace mesh, clears session checkpoints, restores the captured selection where practical, records the rollback decision, and retains an exportable archived audit summary. Rollback never deletes or rewrites the protected source or unrelated scene resources.

## Failure Behaviour

- **Source modification detection:** Abort the command when the source is missing, replaced, or no longer matches its protected snapshot. Do not attempt to repair the source.
- **Workspace invalidation:** Abort when the workspace is missing, shares source geometry, has a replaced mesh datablock, or changed outside the active session.
- **Stale plans:** Mark or treat the plan as stale, perform no mutation, and require fresh analysis and plan generation.
- **Memory failures:** If checkpoint allocation fails, do not dispatch the mutation. If a later memory failure occurs, restore the checkpoint and record the failure.
- **Checkpoint failures:** Do not mutate without a checkpoint. If restoration or restoration verification fails, record that failure, mark the session failed, and block further repair until the state is safely resolved.
- **Safe abort:** Preserve the source, avoid touching unrelated scene data, retain honest failure evidence, and never serialize a failed or skipped check as a successful zero-finding result.

## Audit Contract

The Repair Audit JSON is the machine-readable record of the session. Schema 1.0 records the environment, versions, session and plan identities, protected and workspace signatures, settings, bounded candidates, operation order and outcomes, checkpoints, undo and restore actions, failures, comparisons, decision, timings, warnings, errors, and limitations.

An audit must represent exactly what happened. It must not fabricate operations, omit known failures, turn skipped work into success, claim a mutation that did not occur, or include raw mesh data or live Blender objects. Export must remain deterministic, JSON-safe, UTF-8, readable, and newline-terminated.

## Explicit Non-Goals

The Sprint 2 repair framework does not provide:

- remeshing;
- AI-driven repair;
- Boolean repair;
- wall-thickness repair;
- large-hole reconstruction; or
- an automatic printability guarantee.

These capabilities must not be implied by diagnostics, repair results, comparisons, audits, or user-interface wording.

## Engineering Rules

Future contributors must:

- never mutate the protected source;
- never bypass checkpoints;
- never weaken signature, stale-plan, workspace, or candidate validation;
- never perform a silent repair;
- never hide, downgrade, or fabricate failures;
- always add regression tests for new or changed repair behavior; and
- always update this contract and its references when safety behavior changes.

Any proposed implementation that cannot satisfy these rules must not be merged as a repair feature.

## Known Limitations

- Every repaired workspace requires human review before downstream use.
- Validation on representative real statue meshes is still pending.
- An unfinished repair session is not guaranteed to persist across a Blender restart.
