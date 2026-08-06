"""Smoke the extracted installable extension in an isolated Blender profile."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import bpy


def _arg(name: str) -> Path:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return Path(args[args.index(name) + 1])


def main() -> int:
    root = _arg("--root")
    output = _arg("--output")
    sys.path.insert(0, str(root))
    import chroma3d_sculpt
    from chroma3d_sculpt.models.intelligent_optimization_models import SearchMode
    from chroma3d_sculpt.services.intelligent_optimization_coordinator import (
        build_intelligent_frontier, cancel_intelligent_search, evaluate_intelligent_strategies,
        generate_intelligent_strategies, preview_selected_strategy, rank_intelligent_strategies,
        record_strategy_history,
    )
    from chroma3d_sculpt.services.intelligent_optimization_audit import write_json_audit, write_markdown_audit, build_audit
    from chroma3d_sculpt.services.intelligent_optimization_session import get_active_session, get_archived_session, clear_runtime, start_intelligent_session
    from chroma3d_sculpt.services.search_policy import default_search_policy
    from chroma3d_sculpt.services.strategy_history import write_history_json

    chroma3d_sculpt.register()
    try:
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 1.0))
        source = bpy.context.object
        start_intelligent_session(source, bpy.context.scene, policy=default_search_policy(SearchMode.FAST))
        generated = generate_intelligent_strategies(source=source)
        values = {"fidelity_status": "PASS", "critical_defect_introduced": False, "geometric_deviation": 0.0, "area_drift": 0.0, "volume_drift": 0.0, "build_volume_fit": 1.0, "geometry_fidelity": 1.0, "height": 1.0}
        evaluated = evaluate_intelligent_strategies(baseline_values=values, source=source)
        frontier = build_intelligent_frontier()
        rankings = rank_intelligent_strategies()
        record_strategy_history()
        preview = preview_selected_strategy(strategy_id=rankings[0].strategy_id)
        report_dir = output.parent
        report_dir.mkdir(parents=True, exist_ok=True)
        write_json_audit(build_audit(get_active_session(), blender_version=bpy.app.version_string), report_dir / "installed-audit.json")
        write_markdown_audit(build_audit(get_active_session(), blender_version=bpy.app.version_string), report_dir / "installed-audit.md")
        cancel_intelligent_search()
        write_history_json(get_archived_session().history, report_dir / "installed-history.json")
        payload = {"status": "PASS", "generated": len(generated.strategies), "evaluated": len(evaluated), "frontier": len(frontier.points), "ranked": len(rankings), "preview_mutated_source": preview["mutated_source"], "cancelled_state": get_archived_session().state.value, "blender_version": bpy.app.version_string, "recorded_at": datetime.now(timezone.utc).isoformat()}
    finally:
        clear_runtime()
        for obj in tuple(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        chroma3d_sculpt.unregister()
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
