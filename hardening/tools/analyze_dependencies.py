"""Analyze the checkpoint Python import graph without importing product code."""

from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
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


def _resolve_relative(current: str, node: ast.ImportFrom, *, package_module: bool) -> str:
    parts = current.split(".")
    if node.level:
        levels_to_drop = node.level - 1 if package_module else node.level
        parts = parts[: max(0, len(parts) - levels_to_drop)]
    if node.module:
        parts.extend(node.module.split("."))
    return ".".join(parts)


def _known_module(imported: str, known: set[str], aliases: dict[str, str]) -> str | None:
    if imported in aliases:
        return aliases[imported]
    candidates = [name for name in known if imported == name or imported.startswith(name + ".")]
    return max(candidates, key=len) if candidates else None


def _strong_components(graph: dict[str, set[str]]) -> list[list[str]]:
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    result: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = low[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for target in graph.get(node, set()):
            if target not in indices:
                visit(target)
                low[node] = min(low[node], low[target])
            elif target in on_stack:
                low[node] = min(low[node], indices[target])
        if low[node] == indices[node]:
            component: list[str] = []
            while True:
                item = stack.pop()
                on_stack.remove(item)
                component.append(item)
                if item == node:
                    break
            if len(component) > 1 or node in graph.get(node, set()):
                result.append(sorted(component))

    for node in sorted(graph):
        if node not in indices:
            visit(node)
    return sorted(result)


def _subsystem(module: str) -> str:
    checks = (
        ("ai_", "ai_recommendation"), ("provider", "ai_recommendation"), ("recommendation", "ai_recommendation"),
        ("intelligent", "intelligent_optimization"), ("strategy", "intelligent_optimization"), ("pareto", "intelligent_optimization"),
        ("optimization", "controlled_optimization"), ("advanced", "advanced_preparation"), ("batch_preparation", "advanced_preparation"),
        ("printability", "printability"), ("repair", "repair"),
    )
    lowered = module.lower()
    return next((value for token, value in checks if token in lowered), "shared_or_diagnostics")


def analyze() -> dict[str, object]:
    paths = checkpoint_python_paths()
    module_to_path = {module_name(path): relative(path) for path in paths}
    known = set(module_to_path)
    alias_candidates: dict[str, list[str]] = defaultdict(list)
    for module, path in module_to_path.items():
        if path.startswith(("scripts/", "tests/", "manual-tests/")):
            alias_candidates[Path(path).stem].append(module)
    aliases = {name: values[0] for name, values in alias_candidates.items() if len(values) == 1}
    graph: dict[str, set[str]] = {name: set() for name in known}
    external: dict[str, set[str]] = defaultdict(set)
    parse_errors: list[dict[str, str]] = []
    registration_modules: set[str] = set()
    bl_id_modules: set[str] = set()

    for path in paths:
        current = module_name(path)
        try:
            tree = parse_python(path)
        except SyntaxError as exc:
            parse_errors.append({"path": relative(path), "error": str(exc)})
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "register_class" in text or "_CLASSES" in text or current.endswith(".__init__"):
            registration_modules.add(current)
        if "bl_idname" in text:
            bl_id_modules.add(current)
        for node in ast.walk(tree):
            imported_values: list[str] = []
            if isinstance(node, ast.Import):
                imported_values.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = _resolve_relative(current, node, package_module=path.name == "__init__.py") if node.level else (node.module or "")
                imported_values.append(base)
                imported_values.extend(f"{base}.{alias.name}" for alias in node.names if base)
            for imported in imported_values:
                target = _known_module(imported, known, aliases)
                if target and target != current:
                    graph[current].add(target)
                elif imported:
                    external[current].add(imported.split(".")[0])

    fan_in: Counter[str] = Counter()
    for targets in graph.values():
        fan_in.update(targets)
    edges = [
        {"source": source, "target": target}
        for source in sorted(graph)
        for target in sorted(graph[source])
    ]
    candidates = []
    for module in sorted(known):
        if fan_in[module] or module.endswith(".__main__"):
            continue
        path = module_to_path[module]
        evidence = {
            "registration": module in registration_modules,
            "bl_idname": module in bl_id_modules,
            "package_inclusion": path.startswith("blender_addon/chroma3d_sculpt/"),
            "cli_or_test_entrypoint": path.startswith(("scripts/", "tests/", "manual-tests/")),
            "init_module": path.endswith("/__init__.py"),
        }
        candidates.append({
            "module": module,
            "path": path,
            "classification": "STATICALLY_UNREFERENCED_CANDIDATE",
            "evidence": evidence,
            "note": "Zero static imports is not dead-code proof; dynamic, registration, CLI, test, package, schema, and documentation references require review.",
        })

    service_to_ui = [item for item in edges if ".services." in item["source"] and any(token in item["target"] for token in (".ui.", ".operators."))]
    ui_to_service = [item for item in edges if any(token in item["source"] for token in (".ui.", ".operators.")) and ".services." in item["target"]]
    cross = [
        {**item, "source_subsystem": _subsystem(item["source"]), "target_subsystem": _subsystem(item["target"])}
        for item in edges
        if _subsystem(item["source"]) != _subsystem(item["target"])
        and _subsystem(item["source"]) != "shared_or_diagnostics"
        and _subsystem(item["target"]) != "shared_or_diagnostics"
    ]
    external_roots = sorted({value for values in external.values() for value in values if value != "__future__"})
    return {
        "schema_version": "1.0.0",
        "generated_at": utc_now(),
        "checkpoint_tag": CHECKPOINT_TAG,
        "checkpoint_commit": CHECKPOINT_COMMIT,
        "module_count": len(known),
        "internal_dependency_count": len(edges),
        "external_dependency_count": len(external_roots),
        "external_import_edge_count": sum(len(values - {"__future__"}) for values in external.values()),
        "external_roots": external_roots,
        "module_imports": {name: sorted(values) for name, values in sorted(graph.items())},
        "external_imports": {name: sorted(values) for name, values in sorted(external.items()) if values},
        "potential_circular_imports": _strong_components(graph),
        "statically_unreferenced_candidates": candidates,
        "high_fan_in": [
            {"module": name, "dependents": count, "path": module_to_path[name]}
            for name, count in sorted(fan_in.items(), key=lambda item: (-item[1], item[0]))[:20]
        ],
        "high_fan_out": [
            {"module": name, "dependencies": len(values), "path": module_to_path[name]}
            for name, values in sorted(graph.items(), key=lambda item: (-len(item[1]), item[0]))[:20]
        ],
        "service_imports_ui_or_operators": service_to_ui,
        "ui_or_operators_import_services": ui_to_service,
        "cross_subsystem_coupling": cross,
        "registration_only_candidates": sorted((registration_modules | bl_id_modules) & {item["module"] for item in candidates}),
        "parse_errors": parse_errors,
    }


def render(report: dict[str, object]) -> str:
    circular = report["potential_circular_imports"]
    candidates = report["statically_unreferenced_candidates"]
    assert isinstance(circular, list) and isinstance(candidates, list)
    return "\n".join((
        "# Dependency Baseline",
        "",
        f"Checkpoint: `{report['checkpoint_tag']}` / `{report['checkpoint_commit']}`.",
        "",
        markdown_table(("Metric", "Value"), (
            ("Modules", report["module_count"]),
            ("Internal dependency edges", report["internal_dependency_count"]),
            ("External dependency roots", report["external_dependency_count"]),
            ("External import edges", report["external_import_edge_count"]),
            ("Potential circular components", len(circular)),
            ("Statically unreferenced candidates", len(candidates)),
            ("Service to UI/operator edges", len(report["service_imports_ui_or_operators"])),
            ("UI/operator to service edges", len(report["ui_or_operators_import_services"])),
            ("Cross-subsystem edges", len(report["cross_subsystem_coupling"])),
        )),
        "",
        "## Highest fan-in",
        "",
        markdown_table(("Module", "Dependents"), ((item["module"], item["dependents"]) for item in report["high_fan_in"][:12])),
        "",
        "## Highest fan-out",
        "",
        markdown_table(("Module", "Dependencies"), ((item["module"], item["dependencies"]) for item in report["high_fan_out"][:12])),
        "",
        "## Interpretation",
        "",
        "Every zero-static-import item remains `STATICALLY_UNREFERENCED_CANDIDATE`. Registration, reflection, operator IDs, CLI entrypoints, test discovery, package inclusion, schema paths, and documentation contracts must be checked before H1 action.",
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPORT_ROOT / "dependency_graph.json")
    parser.add_argument("--markdown", type=Path, default=BASELINE_ROOT / "DEPENDENCY_BASELINE.md")
    args = parser.parse_args()
    report = analyze()
    write_json(args.output, report)
    write_text(args.markdown, render(report))
    print(f"dependency graph: {report['module_count']} modules, {report['internal_dependency_count']} internal edges")
    return 1 if report["parse_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
