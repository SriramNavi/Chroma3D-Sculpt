# H4 persistence and reload matrix

The automated save/reload run classifies all `161` WindowManager session
properties and `22` runtime-only state boundaries. The authoritative per-item
mapping is retained in the ignored `persistence.json` report; totals are:

| Classification | Items | H4 rule |
|---|---:|---|
| `PERSIST_REQUIRED` | 1 | Accepted-copy provenance may remain with the accepted copy. |
| `PERSIST_SAFE` | 117 | Bounded user configuration values are safe; the current WindowManager design still treats them as process/session scoped. |
| `RECOMPUTE_REQUIRED` | 10 | Analysis/result availability and counts must be rebuilt from current objects. |
| `TRANSIENT_MUST_CLEAR` | 41 | Runtime statuses, paths, source/workspace display names, cancellation/progress, and temporary datablock references clear on reload/unload. |
| `STALE_MUST_REJECT` | 8 | Session/workspace/candidate/strategy IDs, fingerprints, previews, approvals, and checkpoints are never accepted after reconstruction without fresh validation. |
| `DO_NOT_SERIALIZE` | 6 | API keys, credential characters, provider exchanges/raw responses, geometry arrays, and file bytes must never enter `.blend` state. |

Automated Blender 4.4.3 evidence saved a file with representative repair,
optimization, intelligent-optimization, and AI-assistance state, then opened it
in a fresh process. Transient fields returned to defaults; runtime registries and
credentials were empty; the source cube remained 8 vertices; the fake in-memory
credential bytes were absent from the `.blend` file.

This is fail-closed reconstruction, not a state-migration system. Users must
start a fresh operation after reload. Manual Blender 4.5 LTS and interactive
panel UAT remain `NOT_RUN`.
