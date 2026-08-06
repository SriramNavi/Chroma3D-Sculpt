# Provider and BYOK

The shipped adapter uses OpenAI's Responses API through a vendor-neutral interface and Python's standard-library HTTPS client. The model ID is user-configurable; the extension does not silently select or switch models/providers.

Credentials may come from `OPENAI_API_KEY` or session-only entry. Session entry stays in process memory and is cleared on unload; the environment remains owned by the launching process. Keys never enter `.blend` data, properties, preferences, prompts, reports, audits, logs, fixtures, source files, ZIP assets, or exceptions. The UI shows only source and an optional masked suffix.

Each run is stateless: one explicit request, zero automatic retries, at most one separate user-requested retry, no conversation history, cookies, persistent HTTP session, redirects, tools, or provider-authored destination. Provider-reported token usage is recorded when available; guaranteed currency cost is not calculated. Live provider calls are not used in automated validation.
