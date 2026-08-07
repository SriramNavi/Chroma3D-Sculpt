"""Run H0 analyzers against the complete current H2 product path set."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "hardening" / "tools"
REPORTS = ROOT / "manual-tests" / "hardening" / "reports" / "h2"
sys.path.insert(0, str(TOOLS))

import _common  # noqa: E402
import analyze_complexity  # noqa: E402
import analyze_dependencies  # noqa: E402
import analyze_duplication  # noqa: E402
import analyze_symbol_usage  # noqa: E402
import build_codebase_inventory  # noqa: E402


def _current_product_paths() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or "git ls-files failed")
    return sorted(
        path for path in completed.stdout.splitlines()
        if path and not path.startswith(_common.HARDENING_EXCLUSIONS)
    )


def _write(name: str, report: dict[str, Any], markdown: str) -> None:
    report["measurement_scope"] = "H2_CURRENT_PRODUCT_PATHS"
    report["current_product_path_count"] = len(_current_product_paths())
    _common.write_json(REPORTS / f"{name}.json", report)
    _common.write_text(REPORTS / f"{name.upper()}.md", markdown)


def main() -> int:
    paths = _current_product_paths()
    python_paths = [ROOT / path for path in paths if path.endswith(".py")]
    build_codebase_inventory.checkpoint_paths = lambda: paths
    for module in (analyze_dependencies, analyze_complexity, analyze_duplication, analyze_symbol_usage):
        module.checkpoint_python_paths = lambda: python_paths

    inventory = build_codebase_inventory.build_inventory()
    dependencies = analyze_dependencies.analyze()
    complexity = analyze_complexity.analyze()
    duplication = analyze_duplication.analyze()
    symbols = analyze_symbol_usage.analyze()
    _write("codebase_inventory", inventory, build_codebase_inventory.render_markdown(inventory))
    _write("dependency_graph", dependencies, analyze_dependencies.render(dependencies))
    _write("complexity", complexity, analyze_complexity.render(complexity))
    _write("duplication", duplication, analyze_duplication.render(duplication))
    _write("symbol_usage", symbols, analyze_symbol_usage.render(symbols))
    summary = {
        "inventory_python_files": inventory["counts"]["python_source_files"],
        "inventory_python_physical_loc": inventory["counts"]["python_physical_loc"],
        "dependency_modules": dependencies["module_count"],
        "dependency_edges": dependencies["internal_dependency_count"],
        "circular_components": len(dependencies["potential_circular_imports"]),
        "critical_complexity": complexity["classification_counts"].get("CRITICAL_REVIEW_PRIORITY", 0),
        "high_complexity": complexity["classification_counts"].get("HIGH_REVIEW_PRIORITY", 0),
        "duplication_candidates": duplication["candidate_count"],
        "static_symbol_candidates": len(symbols["candidates"]),
        "measurement_scope": "H2_CURRENT_PRODUCT_PATHS",
    }
    print(json.dumps(summary, sort_keys=True))
    reports = (inventory, dependencies, complexity, duplication, symbols)
    return 1 if any(report.get("parse_errors", ()) for report in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
