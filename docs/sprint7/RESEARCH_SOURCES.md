# Sprint 7 Research Sources

Access date for all sources: **2026-08-06**. Repository requirements remain authoritative; external sources support only the stated claims.

| ID | Title | Owner | URL | Scope used | Supported claim |
|---|---|---|---|---|---|
| S7-SRC-001 | JSON Schema Draft 2020-12 | JSON Schema project | https://json-schema.org/draft/2020-12 | Core and validation dialect | Draft contracts can strictly constrain structure, types, enums, required fields, arrays, and unknown properties. Application semantic checks remain necessary. |
| S7-SRC-002 | LLM01:2025 Prompt Injection | OWASP GenAI Security Project | https://genai.owasp.org/llmrisk/llm01-prompt-injection/ | Direct/indirect prompt injection risk | User/context/provider text must remain untrusted and cannot change policy, destinations, allow-lists, or execution controls. |
| S7-SRC-003 | OWASP Top 10 for LLM Applications v2.0 | OWASP GenAI Security Project | https://genai.owasp.org/download/43299/?tmstv=1731900559 | Prompt injection, improper output handling, excessive agency, sensitive disclosure and unbounded consumption | Strict output validation, least agency, data minimization and bounded consumption are required defense layers; model instructions alone are insufficient. |
| S7-SRC-004 | Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile (NIST AI 600-1) | U.S. National Institute of Standards and Technology | https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf | Risk identification, measurement, governance and transparency for generative AI | Provider/model evaluation, documented limitations, human review, incident evidence, and risk-based release gates are appropriate for this optional assistance layer. |
| S7-SRC-005 | NIST Privacy Framework | U.S. National Institute of Standards and Technology | https://www.nist.gov/privacy-framework | Privacy-risk identification and data-processing governance | Context inventory, purpose-specific consent, minimization, retention/deletion decisions and owner accountability must precede service use. |

## Rejected or insufficient evidence

- Provider marketing pages do not establish reliability, privacy, latency, cost, retention, or structured-output guarantees for this product.
- Model self-reported confidence does not establish product confidence or geometry correctness.
- Generic prompt examples do not prove prompt-injection resistance.
- Frozen Sprint 0–6 software evidence does not establish live-provider, physical-print, slicer, material, cultural, or iconographic correctness.
