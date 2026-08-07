# Historical Evidence Policy

Frozen validation documents, schemas, locks, manifests, thresholds, failure records, and release artifacts retain their original meaning. Later tooling may read and compare them but must not rewrite a historical failure, timeout, `SKIPPED`, `UNKNOWN`, `INDETERMINATE`, `NOT_RUN`, software-only limitation, or physical/manual limitation into pass evidence.

Expensive dataset evidence may be reused only when dataset, benchmark, runtime/profile, and release-input fingerprints remain compatible. A mismatch requires a clear rerun decision; it must not trigger an automatic full-corpus run.
