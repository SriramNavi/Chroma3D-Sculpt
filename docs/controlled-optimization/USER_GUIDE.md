# User Guide

Open `3D Viewport > Sidebar > Chroma3D > Controlled Optimization`.

- Select a mesh in Object Mode and click **Start Optimization Session**.
- Choose an objective preset and safe policy limits.
- Click **Generate Candidates**, then **Generate Plan**.
- Review candidate IDs and apply one selected step at a time. Experimental/base operations require explicit approval through the operation action.
- Review objective, risk, critical-regression, skipped/indeterminate, and fidelity results.
- Use **Undo Last** or **Restore Start** before further planning.
- Choose **Accept Optimized Copy** to retain a separate object, or **Discard Workspace** to remove only the session workspace.
- Export JSON and Markdown audits for review.

The panel is advisory and software-only. Manually test the installed extension before committing or releasing the feature branch.
