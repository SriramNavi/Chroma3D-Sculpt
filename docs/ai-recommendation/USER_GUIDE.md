# User Guide

1. Finish the local Intelligent Optimization generate/evaluate/Pareto/rank workflow for a protected source.
2. Expand **AI Recommendation (Optional)** and enable it. Choose FAST, STANDARD, or DEEP; enter a short goal; set the explicit OpenAI model ID.
3. Choose **Prepare Bounded Context**. This is local and makes no network request.
4. Review destination, purpose, included and omitted categories, retention/cost wording, byte count, and credential state.
5. For OpenAI, configure `OPENAI_API_KEY` before Blender starts or use **Set Session Key**. Tick consent and bind it to the displayed context. **Validate Configuration Locally** never calls the provider.
6. Choose **Request Recommendations** for one external request, or **Offline Sprint 6 View** for no external request.
7. Review confidence, reason, target, evidence status, trade-offs and limitations. Select an actionable current item.
8. Preview it. Preview is not approval. Approve the exact displayed plan as a separate action, then execute only if intended.
9. Review comparison. Accepting keeps a separate copy and the source; discard removes only the session-owned workspace.
10. Export a redacted report or audit. If stale, failed or cancelled, start again from fresh local evidence.
