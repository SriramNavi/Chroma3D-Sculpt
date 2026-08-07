# Refactor Safety Policy

Refactors must start from an H1 queue item and state the preserved contract. Before editing, record the backup-tag diff, affected invariants, schemas, IDs, thresholds, ownership rules, and targeted tests. After editing, compare public contracts, package members, test topology, source signatures, resource lifecycle, and relevant performance fixtures.

Do not combine behavior changes with consolidation. Preserve first failure evidence. A failed safety or compatibility gate stops the phase; skipped or indeterminate evidence is not pass evidence.
