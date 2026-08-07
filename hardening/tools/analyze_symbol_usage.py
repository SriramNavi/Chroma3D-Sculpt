"""Inventory symbols and classify reference evidence without deleting code."""

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
    parse_python,
    relative,
    utc_now,
    write_json,
    write_text,
)


def _decorators(node: ast.AST) -> set[str]:
    values: set[str] = set()
    for item in getattr(node, "decorator_list", []):
        target = item.func if isinstance(item, ast.Call) else item
        if isinstance(target, ast.Name):
            values.add(target.id)
        elif isinstance(target, ast.Attribute):
            values.add(target.attr)
    return values


def _bases(node: ast.ClassDef) -> set[str]:
    return {
        item.id if isinstance(item, ast.Name) else item.attr
        for item in node.bases
        if isinstance(item, (ast.Name, ast.Attribute))
    }


def _definitions(path: Path, tree: ast.AST) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "registration_function" if node.name in {"register", "unregister"} else "function"
            result.append({"name": node.name, "qualified_name": node.name, "kind": kind, "line": node.lineno})
        elif isinstance(node, ast.ClassDef):
            bases = _bases(node)
            decorators = _decorators(node)
            if "Operator" in bases:
                kind = "operator"
            elif "Panel" in bases:
                kind = "panel"
            elif "PropertyGroup" in bases:
                kind = "property_group"
            elif "dataclass" in decorators:
                kind = "dataclass"
            elif bases.intersection({"Enum", "IntEnum", "StrEnum"}):
                kind = "enum"
            else:
                kind = "class"
            result.append({"name": node.name, "qualified_name": node.name, "kind": kind, "line": node.lineno})
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and not child.name.startswith("__"):
                    result.append({"name": child.name, "qualified_name": f"{node.name}.{child.name}", "kind": "method", "line": child.lineno})
                elif isinstance(child, (ast.Assign, ast.AnnAssign)):
                    targets = child.targets if isinstance(child, ast.Assign) else [child.target]
                    for target in targets:
                        if isinstance(target, ast.Name) and not target.id.startswith("_"):
                            result.append({"name": target.id, "qualified_name": f"{node.name}.{target.id}", "kind": "property_or_enum_member", "line": child.lineno})
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    result.append({"name": target.id, "qualified_name": target.id, "kind": "constant", "line": node.lineno})
    for item in result:
        item["file"] = relative(path)
    return result


def analyze() -> dict[str, object]:
    paths = checkpoint_python_paths()
    definitions: list[dict[str, object]] = []
    production_loads: Counter[str] = Counter()
    test_loads: Counter[str] = Counter()
    string_references: Counter[str] = Counter()
    registration_loads: Counter[str] = Counter()
    parse_errors: list[dict[str, str]] = []
    path_text: dict[str, str] = {}

    for path in paths:
        rel = relative(path)
        try:
            tree = parse_python(path)
        except SyntaxError as exc:
            parse_errors.append({"path": rel, "error": str(exc)})
            continue
        path_text[rel] = path.read_text(encoding="utf-8", errors="replace")
        definitions.extend(_definitions(path, tree))
        target = test_loads if rel.startswith(("tests/", "manual-tests/")) else production_loads
        registration_context = rel.endswith("/__init__.py") or "register_class" in path_text[rel] or "_CLASSES" in path_text[rel]
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                target[node.id] += 1
                if registration_context:
                    registration_loads[node.id] += 1
            elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                target[node.attr] += 1
                if registration_context:
                    registration_loads[node.attr] += 1
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) <= 160:
                string_references[node.value] += 1

    records = []
    classifications: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    for item in definitions:
        name = str(item["name"])
        path = str(item["file"])
        production = production_loads[name]
        tests = test_loads[name]
        registration = registration_loads[name] > 0 or item["kind"] in {"operator", "panel", "property_group", "registration_function"}
        reflection = string_references[name] > 0
        package = path.startswith("blender_addon/chroma3d_sculpt/")
        dev_tool = path.startswith(("scripts/", "manual-tests/"))
        legacy = "legacy" in name.lower() or "compat" in name.lower()
        if registration:
            classification = "REGISTRATION_REFERENCED"
        elif reflection:
            classification = "REFLECTION_REFERENCED"
        elif production:
            classification = "CONFIRMED_REFERENCED"
        elif tests:
            classification = "TEST_ONLY"
        elif legacy:
            classification = "LEGACY_COMPATIBILITY"
        elif dev_tool:
            classification = "DEV_TOOL_ONLY"
        else:
            classification = "STATICALLY_UNREFERENCED_CANDIDATE"
        action = "KEEP" if classification in {"CONFIRMED_REFERENCED", "REFLECTION_REFERENCED", "REGISTRATION_REFERENCED", "LEGACY_COMPATIBILITY"} else "INVESTIGATE"
        confidence = "HIGH" if classification in {"CONFIRMED_REFERENCED", "REGISTRATION_REFERENCED"} else "MEDIUM" if classification != "STATICALLY_UNREFERENCED_CANDIDATE" else "LOW"
        record = {
            **item,
            "classification": classification,
            "static_references": production,
            "dynamic_or_registration_evidence": {"registration": registration, "reflection_string": reflection},
            "test_evidence": tests,
            "package_inclusion": package,
            "confidence": confidence,
            "recommended_h1_action": action,
        }
        records.append(record)
        classifications[classification] += 1
        kinds[str(item["kind"])] += 1

    candidates = [item for item in records if item["classification"] == "STATICALLY_UNREFERENCED_CANDIDATE"]
    candidates.sort(key=lambda item: (str(item["file"]), int(item["line"]), str(item["qualified_name"])))
    return {
        "schema_version": "1.0.0",
        "generated_at": utc_now(),
        "checkpoint_tag": CHECKPOINT_TAG,
        "checkpoint_commit": CHECKPOINT_COMMIT,
        "symbol_count": len(records),
        "kind_counts": dict(sorted(kinds.items())),
        "classification_counts": dict(sorted(classifications.items())),
        "symbols": records,
        "candidates": candidates,
        "parse_errors": parse_errors,
        "limitations": [
            "Name-based AST references can be ambiguous across modules.",
            "Static analysis cannot prove Blender registration, reflection, schema, CLI, package, or documentation reachability is absent.",
            "No symbol is classified DEAD and no removal is authorized by this report.",
        ],
    }


def render(report: dict[str, object]) -> str:
    candidates = report["candidates"]
    assert isinstance(candidates, list)
    counts = report["classification_counts"]
    assert isinstance(counts, dict)
    return "\n".join((
        "# Dead-Code Candidate Baseline",
        "",
        f"Checkpoint: `{report['checkpoint_tag']}` / `{report['checkpoint_commit']}`.",
        "",
        markdown_table(("Classification", "Count"), counts.items()),
        "",
        "## Static candidates",
        "",
        markdown_table(
            ("Symbol", "File", "Static refs", "Test refs", "Package", "Confidence", "H1 action"),
            ((item["qualified_name"], item["file"], item["static_references"], item["test_evidence"], item["package_inclusion"], item["confidence"], item["recommended_h1_action"]) for item in candidates[:80]),
        ) if candidates else "No statically unreferenced candidates were emitted.",
        "",
        "`STATICALLY_UNREFERENCED_CANDIDATE` is not a dead-code verdict. H1 must add runtime/reference proof before removal. This baseline never emits `DEAD`.",
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPORT_ROOT / "symbol_usage.json")
    parser.add_argument("--markdown", type=Path, default=BASELINE_ROOT / "DEAD_CODE_CANDIDATES.md")
    args = parser.parse_args()
    report = analyze()
    write_json(args.output, report)
    write_text(args.markdown, render(report))
    print(f"symbol usage: {report['symbol_count']} symbols, {len(report['candidates'])} static candidates")
    return 1 if report["parse_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
