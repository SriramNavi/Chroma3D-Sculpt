# Intelligent Optimization

Sprint 6 is deterministic local intelligence above Sprint 5 Controlled Optimization. It generates bounded operation strategies, evaluates visible objectives, constructs a Pareto frontier, ranks feasible strategies, explains trade-offs, retains local session history, and recommends a user-selectable strategy.

Workflow: protected source → Sprint 5 candidates → strategy generation → bounded evaluation → constraints → Pareto frontier → ranking and explanation → user selection → isolated preview → explicit stepwise execution → comparison → accept separate copy or discard.

The engine does not use AI/LLM, cloud services, telemetry, automatic execution, source replacement, supports, slicing, G-code, printer commands, physical printing, or global-optimum claims.

See [Safety Model](SAFETY_MODEL.md), [Search Policy](SEARCH_POLICY.md), [Constraints](CONSTRAINTS.md), [Strategy Generation](STRATEGY_GENERATION.md), [Pareto Frontier](PARETO_FRONTIER.md), [Ranking and Explanations](RANKING_AND_EXPLANATIONS.md), [History and Overrides](HISTORY_AND_OVERRIDES.md), and [User Guide](USER_GUIDE.md).
