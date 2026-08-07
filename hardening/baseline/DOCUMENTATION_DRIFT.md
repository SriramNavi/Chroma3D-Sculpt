# Documentation Drift

Checkpoint: `v0.8.0-pre-hardening-backup` / `d06e1a05890fe23e77e66f95fc40e0200638a765`.

| Classification | Count |
| --- | --- |
| CONTRADICTORY | 1 |
| CURRENT | 12 |
| MINOR_DRIFT | 1 |

| Path | Classification | Evidence | Recommended H7 action |
| --- | --- | --- | --- |
| README.md | CONTRADICTORY | README identifies v0.7.0-alpha.1 as current published release while v0.8.0-alpha.1 is tagged and the pre-v1 checkpoint identifies it as current. | Align release-status wording with the published tag and checkpoint evidence. |
| ARCHITECTURE.md | CURRENT | Required current-scope terms are present. | KEEP |
| ROADMAP.md | CURRENT | Required current-scope terms are present. | KEEP |
| TECHNICAL_ROADMAP.md | CURRENT | Required current-scope terms are present. | KEEP |
| PRODUCT_REQUIREMENTS.md | CURRENT | Required current-scope terms are present. | KEEP |
| REPAIR_SAFETY.md | CURRENT | Required current-scope terms are present. | KEEP |
| PROJECT_RULES.md | CURRENT | Required current-scope terms are present. | KEEP |
| AGENTS.md | CURRENT | Required current-scope terms are present. | KEEP |
| docs/printability/README.md | CURRENT | Required current-scope terms are present. | KEEP |
| docs/advanced-preparation/README.md | CURRENT | Required current-scope terms are present. | KEEP |
| docs/controlled-optimization/README.md | CURRENT | Required current-scope terms are present. | KEEP |
| docs/intelligent-optimization/README.md | CURRENT | Required current-scope terms are present. | KEEP |
| docs/ai-recommendation/README.md | MINOR_DRIFT | Expected current contract terms not found: untrusted | Review against current Sprint 7 implementation and update in H7 only. |
| docs/sprint7 | CURRENT | Required current-scope terms are present. | KEEP |

No documentation was rewritten in H0; changes are queued for H7 review only.
