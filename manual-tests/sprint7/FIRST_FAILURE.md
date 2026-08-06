# Sprint 7 First-Failure Evidence

- First focused run status: `FAIL` (`47/52` passed).
- First reproduced product defect: the consented context bounded `ranking_information` but serialized the full Sprint 6 `strategy_ids` collection.
- Safety consequence: the request could disclose more existing target identities than the selected `maximum_strategies` policy allowed.
- Root cause: `ai_assistance_coordinator._build_context()` passed the full strategy set independently of the bounded ranking slice.
- Fix: derive both `ranking_information` and `strategy_ids` from the same bounded ranked slice before context hashing and consent.
- Thresholds weakened: none.
- Live provider calls: `0`.
- Current verification: the focused provider-independent Blender suite passes `62/62` after the fix and subsequent audit coverage additions.

This record preserves the first product failure; transient test-harness fixture corrections are not reclassified as product defects.
