"""Capture deterministic lightweight architecture and complexity review signals."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    BASELINE_ROOT,
    CHECKPOINT_COMMIT,
    CHECKPOINT_TAG,
    REPORT_ROOT,
    checkpoint_python_paths,
    markdown_table,
    module_name,
    parse_python,
    relative,
    utc_now,
    write_json,
    write_text,
)
from analyze_dependencies import analyze as analyze_dependencies  # noqa: E402


BRANCH_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.IfExp, ast.Match, ast.comprehension)
NESTING_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith, ast.Match)


def _nesting_depth(node: ast.AST, depth: int = 0) -> int:
    current = depth + 1 if isinstance(node, NESTING_NODES) else depth
    return max([current, *(_nesting_depth(child, current) for child in ast.iter_child_nodes(node))])


def _function_record(node: ast.FunctionDef | ast.AsyncFunctionDef, owner: str = "") -> dict[str, object]:
    loc = int(getattr(node, "end_lineno", node.lineno)) - node.lineno + 1
    branches = sum(isinstance(item, BRANCH_NODES) for item in ast.walk(node))
    return {
        "symbol": f"{owner}.{node.name}" if owner else node.name,
        "line": node.lineno,
        "loc": loc,
        "branch_count_estimate": branches,
        "nesting_depth": _nesting_depth(node),
    }


def _classification(loc: int, branches: int, nesting: int, max_function_loc: int, fan_out: int) -> str:
    if loc >= 1000 or max_function_loc >= 300 or branches >= 120 or nesting >= 9:
        return "CRITICAL_REVIEW_PRIORITY"
    if loc >= 500 or max_function_loc >= 150 or branches >= 60 or nesting >= 7 or fan_out >= 20:
        return "HIGH_REVIEW_PRIORITY"
    if loc >= 250 or max_function_loc >= 80 or branches >= 30 or nesting >= 5 or fan_out >= 12:
        return "MODERATE"
    return "LOW"


def analyze() -> dict[str, object]:
    dependency = analyze_dependencies()
    imports = dependency["module_imports"]
    assert isinstance(imports, dict)
    fan_in: Counter[str] = Counter()
    for targets in imports.values():
        fan_in.update(targets)
    modules = []
    parse_errors: list[dict[str, str]] = []
    for path in checkpoint_python_paths():
        rel = relative(path)
        module = module_name(path)
        try:
            tree = parse_python(path)
        except SyntaxError as exc:
            parse_errors.append({"path": rel, "error": str(exc)})
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        functions = []
        class_count = 0
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(_function_record(node))
            elif isinstance(node, ast.ClassDef):
                class_count += 1
                functions.extend(_function_record(item, node.name) for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)))
        branch_count = sum(isinstance(item, BRANCH_NODES) for item in ast.walk(tree))
        nesting = _nesting_depth(tree)
        maximum_function = max((int(item["loc"]) for item in functions), default=0)
        fan_out = len(imports.get(module, []))
        record = {
            "module": module,
            "path": rel,
            "loc": len(lines),
            "branch_count_estimate": branch_count,
            "nesting_depth": nesting,
            "function_count": len(functions),
            "class_count": class_count,
            "import_fan_in": fan_in[module],
            "import_fan_out": fan_out,
            "maximum_function_loc": maximum_function,
            "functions": sorted(functions, key=lambda item: (-int(item["loc"]), str(item["symbol"])))[:20],
        }
        record["classification"] = _classification(len(lines), branch_count, nesting, maximum_function, fan_out)
        modules.append(record)
    order = {"CRITICAL_REVIEW_PRIORITY": 0, "HIGH_REVIEW_PRIORITY": 1, "MODERATE": 2, "LOW": 3}
    modules.sort(key=lambda item: (order[str(item["classification"])], -int(item["loc"]), str(item["path"])))
    counts = Counter(str(item["classification"]) for item in modules)
    return {
        "schema_version": "1.0.0",
        "generated_at": utc_now(),
        "checkpoint_tag": CHECKPOINT_TAG,
        "checkpoint_commit": CHECKPOINT_COMMIT,
        "classification_counts": dict(sorted(counts.items())),
        "modules": modules,
        "top_review_targets": modules[:40],
        "parse_errors": parse_errors,
        "metric_definition": {
            "loc": "physical lines",
            "branch_count_estimate": "AST control-flow and comprehension node count",
            "nesting_depth": "maximum nested control-flow depth",
            "classification": "transparent review prioritization only; never a defect verdict or refactor requirement",
        },
    }


def render(report: dict[str, object]) -> str:
    targets = report["top_review_targets"]
    assert isinstance(targets, list)
    return "\n".join((
        "# Architecture Hotspots",
        "",
        f"Checkpoint: `{report['checkpoint_tag']}` / `{report['checkpoint_commit']}`.",
        "",
        markdown_table(("Classification", "Count"), report["classification_counts"].items()),
        "",
        "## Top review targets",
        "",
        markdown_table(
            ("Path", "Class", "LOC", "Branches", "Depth", "Functions", "Classes", "Fan-in", "Fan-out", "Max function"),
            ((item["path"], item["classification"], item["loc"], item["branch_count_estimate"], item["nesting_depth"], item["function_count"], item["class_count"], item["import_fan_in"], item["import_fan_out"], item["maximum_function_loc"]) for item in targets),
        ),
        "",
        "These deterministic bands prioritize review only. High metrics are not defects and do not require refactoring without behavioral evidence.",
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPORT_ROOT / "complexity_baseline.json")
    parser.add_argument("--markdown", type=Path, default=BASELINE_ROOT / "ARCHITECTURE_HOTSPOTS.md")
    args = parser.parse_args()
    report = analyze()
    write_json(args.output, report)
    write_text(args.markdown, render(report))
    print(f"complexity analysis: {len(report['modules'])} modules")
    return 1 if report["parse_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
