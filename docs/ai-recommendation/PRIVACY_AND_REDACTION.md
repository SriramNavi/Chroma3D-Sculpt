# Privacy and Redaction

Context uses a strict allow-list. It may contain a sanitized goal/display name, profile/settings hashes, local evidence identities/states/provenance/limitations, current candidate/plan/strategy IDs, bounded ranking summaries, and explicit unknown states.

It excludes mesh vertices/faces/bytes, `.blend` or STL contents, images, home/repository paths, usernames, credentials, unrelated scene data, arbitrary custom properties, raw logs, and source code. Geometry exported is always zero. Secrets, absolute paths, URLs and Unicode control characters in user-facing text are removed or cause a fail-closed context error. Critical failed/unknown evidence is retained before lower-priority evidence; it is never silently truncated to make a request pass.

Consent is bound to the exact context/policy/source/destination/categories/purpose disclosure. Any bound change expires derived recommendations, preview and approval. Reports retain bounded redacted projections and hashes, not raw prompts or provider bodies by default.
