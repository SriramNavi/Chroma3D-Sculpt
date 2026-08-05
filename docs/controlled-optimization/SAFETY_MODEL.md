# Safety Model

The source object and mesh datablock are protected by a full source snapshot. The session copies both into a uniquely named, session-owned collection and records ownership metadata. All transformations and geometry changes target that workspace only.

Source identity and signature are checked before session creation, candidate generation, plan execution, undo, restore, accept, discard, and export. A mismatch creates a stale event and fails closed; the source is never auto-repaired or auto-restored.

Every mutating operation has a valid mesh/transform checkpoint. A failure restores the last valid checkpoint. Checkpoint history is bounded, and no-change operations do not evict usable undo history. Accept creates a separate object. Discard deletes only session-owned resources.
