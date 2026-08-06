# User Guide

1. Select a mesh and start **Intelligent Optimization**. The source is protected and an isolated Sprint 5 workspace is owned by the session.
2. Choose FAST, STANDARD, DEEP, or a validated custom mode, an objective preset, and a ranking method.
3. Generate strategies, evaluate them, build the Pareto frontier, rank, and review the recommendation.
4. Inspect objective trade-offs and estimated/measured/skipped evidence. Select the recommendation or another valid strategy. A dominated strategy requires an explicit warning override.
5. Preview the selected strategy. Execution is a separate explicit action and applies steps through Sprint 5 checkpoints.
6. Review comparison and fidelity evidence. Accept creates a separate optimized copy; discard removes only the owned workspace.
7. Export JSON, Markdown, or local strategy history.

The panel does not slice, generate supports or G-code, communicate with a printer, or guarantee physical or print success. Run manual installed-panel smoke testing separately before committing the feature branch.
