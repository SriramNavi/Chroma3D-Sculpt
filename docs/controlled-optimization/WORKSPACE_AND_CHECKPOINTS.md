# Workspace and Checkpoints

The workspace duplicates the source object and mesh datablock and is linked only to a session-owned collection. It is transient and is not automatically saved. Source selection/active-object state is restored after workspace creation.

The initial checkpoint is created immediately. Each mutating operation creates another checkpoint containing mesh state, transform, operation index, candidate identity, source signature, process hash, and policy hash. Undo restores the prior valid checkpoint; Restore Session Start restores the initial checkpoint. Failed operations roll back automatically. Cleanup removes only session-owned resources.
