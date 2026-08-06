# Safety Model

- Search, constraint evaluation, Pareto construction, ranking, explanation, recommendation, and export are read-only.
- The protected source is bound by object, mesh, geometry, transform, process, feature, policy, objective, strategy, frontier, ranking, and implementation identities.
- Any workspace mutation is delegated to Sprint 5's independent workspace, checkpoint, comparison, undo/restore, accept-copy, and discard services.
- Each selected step is explicit. A recommendation never executes and accept never replaces the source.
- Unknown, skipped, indeterminate, failed, and budget-exhausted evidence cannot silently become PASS.
- Experimental operations require an explicit policy toggle and approval. They are disabled by default.

This remains advisory software evidence. It does not establish physical strength, adhesion, surface quality, support behavior, slicer correctness, or print success.
