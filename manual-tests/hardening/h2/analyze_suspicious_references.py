"""Resolve the 50 frozen H1 suspicious import bindings conservatively for H2."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[3]
H1_TAG = "v0.8.0-h1-hardening-checkpoint"
H1_LEDGER = ROOT / "hardening" / "h1" / "H1_DISPOSITION_LEDGER.json"
H2_ROOT = ROOT / "hardening" / "h2"
DEFAULT_LEDGER = H2_ROOT / "H2_REFERENCE_DISPOSITIONS.json"
DEFAULT_SUMMARY = H2_ROOT / "H2_REFERENCE_SUMMARY.md"
SOURCE_ROOTS = (
    ROOT / "blender_addon",
    ROOT / "benchmarks",
    ROOT / "hardening" / "tools",
    ROOT / "manual-tests",
    ROOT / "scripts",
    ROOT / "tests",
)
ALLOWED_CLASSIFICATIONS = {
    "PROVEN_UNUSED",
    "RUNTIME_USED",
    "REGISTERED_RUNTIME",
    "PUBLIC_CONTRACT",
    "DYNAMIC_REFERENCE",
    "TEST_ONLY",
    "DEV_TOOL_ONLY",
    "COMPATIBILITY",
    "AMBIGUOUS",
    "KEEP",
}
SIDE_EFFECT_SAFE_ROOTS = {
    "collections",
    "copy",
    "dataclasses",
    "datetime",
    "enum",
    "functools",
    "hashlib",
    "json",
    "math",
    "pathlib",
    "re",
    "typing",
    "uuid",
    "bpy",
}

# Added only after each removal batch passed its declared focused validation.
REMOVAL_BATCH_BY_PATH: dict[str, str] = {
    "blender_addon/chroma3d_sculpt/intelligent_optimization_settings.py": "H2-R1",
    "blender_addon/chroma3d_sculpt/operators/intelligent_optimization.py": "H2-R1",
    "blender_addon/chroma3d_sculpt/operators/advanced_preparation.py": "H2-R2",
    "blender_addon/chroma3d_sculpt/operators/optimization.py": "H2-R3",
    "blender_addon/chroma3d_sculpt/operators/repair.py": "H2-R4",
    "blender_addon/chroma3d_sculpt/services/repair_session.py": "H2-R4",
    "blender_addon/chroma3d_sculpt/ui/repair_panel.py": "H2-R4",
    "blender_addon/chroma3d_sculpt/services/ai_assistance_report.py": "H2-R5",
    "blender_addon/chroma3d_sculpt/services/ai_assistance_session.py": "H2-R5",
    "blender_addon/chroma3d_sculpt/services/fake_ai_provider.py": "H2-R5",
    "blender_addon/chroma3d_sculpt/services/openai_provider.py": "H2-R6",
    "blender_addon/chroma3d_sculpt/services/provider_transport.py": "H2-R6",
    "blender_addon/chroma3d_sculpt/services/context_budget.py": "H2-R6",
    "blender_addon/chroma3d_sculpt/services/constraint_engine.py": "H2-R7",
    "blender_addon/chroma3d_sculpt/services/search_policy.py": "H2-R7",
    "blender_addon/chroma3d_sculpt/services/strategy_evaluator.py": "H2-R7",
    "blender_addon/chroma3d_sculpt/services/intelligent_optimization_audit.py": "H2-R8",
    "blender_addon/chroma3d_sculpt/services/intelligent_optimization_coordinator.py": "H2-R8",
    "blender_addon/chroma3d_sculpt/services/intelligent_optimization_session.py": "H2-R8",
    "blender_addon/chroma3d_sculpt/services/optimization_comparison.py": "H2-R9",
    "blender_addon/chroma3d_sculpt/services/optimization_coordinator.py": "H2-R9",
    "blender_addon/chroma3d_sculpt/services/optimization_plan.py": "H2-R9",
    "blender_addon/chroma3d_sculpt/services/optimization_session.py": "H2-R10",
    "blender_addon/chroma3d_sculpt/services/optimization_workspace.py": "H2-R10",
    "blender_addon/chroma3d_sculpt/services/strategy_generator.py": "H2-R11",
    "blender_addon/chroma3d_sculpt/services/thin_features.py": "H2-R12",
}


@dataclass(frozen=True)
class SourceUnit:
    path: Path
    relative: str
    module: str
    text: str
    tree: ast.Module


@dataclass(frozen=True)
class ImportBinding:
    source_module: str
    imported_name: str
    local_name: str
    line: int
    alias_count: int
    statement: str


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8", newline="\n")
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _git(*args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, check=False,
        text=True, encoding="utf-8", errors="replace",
    )
    if check and completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout


def _tag_text(path: str) -> str:
    return _git("show", f"{H1_TAG}:{path}")


def _module_for(path: str) -> str:
    value = Path(path).with_suffix("").as_posix().replace("/", ".")
    prefix = "blender_addon."
    return value[len(prefix):] if value.startswith(prefix) else value


def _resolve_from(current: str, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""
    parts = current.split(".")
    base = parts[:-node.level]
    if node.module:
        base.extend(node.module.split("."))
    return ".".join(base)


def _python_units() -> list[SourceUnit]:
    units: list[SourceUnit] = []
    seen: set[Path] = set()
    for source_root in SOURCE_ROOTS:
        if not source_root.exists():
            continue
        for path in sorted(source_root.rglob("*.py")):
            if path in seen or "reports" in path.parts or "__pycache__" in path.parts:
                continue
            seen.add(path)
            text = path.read_text(encoding="utf-8", errors="replace")
            try:
                tree = ast.parse(text, filename=str(path))
            except SyntaxError:
                continue
            relative = path.relative_to(ROOT).as_posix()
            units.append(SourceUnit(path, relative, _module_for(relative), text, tree))
    return units


def _find_bindings(text: str, module: str, symbol: str) -> list[ImportBinding]:
    tree = ast.parse(text)
    lines = text.splitlines()
    bindings: list[ImportBinding] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        source = _resolve_from(module, node) if isinstance(node, ast.ImportFrom) else ""
        for alias in node.names:
            local = alias.asname or alias.name.split(".")[0]
            if local != symbol:
                continue
            bindings.append(
                ImportBinding(
                    source_module=source or alias.name,
                    imported_name=alias.name,
                    local_name=local,
                    line=node.lineno,
                    alias_count=len(node.names),
                    statement=lines[node.lineno - 1].strip(),
                )
            )
    return bindings


def _name_load_count(text: str, symbol: str) -> int:
    tree = ast.parse(text)
    return sum(
        1 for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id == symbol
    )


def _all_exports(tree: ast.Module) -> set[str]:
    exports: set[str] = set()
    for node in tree.body:
        value: ast.AST | None = None
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
        ):
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "__all__":
            value = node.value
        if value is not None:
            exports.update(
                item.value for item in ast.walk(value)
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            )
    return exports


def _annotation_strings(tree: ast.Module, symbol: str) -> list[int]:
    lines: set[int] = set()

    def inspect(annotation: ast.AST | None) -> None:
        if annotation is None:
            return
        for item in ast.walk(annotation):
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                if symbol in item.value.replace("[", " ").replace("]", " ").replace(",", " ").split():
                    lines.add(item.lineno)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            inspect(node.returns)
            for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
                inspect(argument.annotation)
            if node.args.vararg:
                inspect(node.args.vararg.annotation)
            if node.args.kwarg:
                inspect(node.args.kwarg.annotation)
        elif isinstance(node, ast.AnnAssign):
            inspect(node.annotation)
    return sorted(lines)


def _dynamic_module_risks(tree: ast.Module, symbol: str) -> list[str]:
    risks: set[str] = set()
    if any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "__getattr__" for node in tree.body):
        risks.add("module___getattr__")
    module_scope_calls: set[ast.Call] = set()
    for statement in tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        module_scope_calls.update(node for node in ast.walk(statement) if isinstance(node, ast.Call))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if (
            node in module_scope_calls and isinstance(node.func, ast.Name)
            and node.func.id in {"globals", "locals"} and not node.args
        ):
            risks.add(f"{node.func.id}_namespace_access")
        if (
            isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant) and node.args[1].value == symbol
        ):
            risks.add("getattr_exact_symbol")
    annotation_lines = _annotation_strings(tree, symbol)
    if annotation_lines:
        risks.add("string_annotation:" + ",".join(str(line) for line in annotation_lines))
    return sorted(risks)


def _path_kind(relative: str) -> str:
    if relative.startswith("blender_addon/chroma3d_sculpt/"):
        return "runtime"
    if relative.startswith("tests/"):
        return "test"
    return "dev"


def _external_references(
    units: Iterable[SourceUnit], candidate_path: str, candidate_module: str, symbol: str,
) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    parent, _, leaf = candidate_module.rpartition(".")
    qualified = f"{candidate_module}.{symbol}"
    for unit in units:
        if unit.relative == candidate_path:
            continue
        alias_names: set[str] = set()
        for node in ast.walk(unit.tree):
            if isinstance(node, ast.ImportFrom):
                source = _resolve_from(unit.module, node)
                for alias in node.names:
                    if source == candidate_module and alias.name == symbol:
                        references.append({
                            "kind": _path_kind(unit.relative),
                            "mechanism": "from_import",
                            "path": unit.relative,
                            "line": node.lineno,
                        })
                    if source == parent and alias.name == leaf:
                        alias_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == candidate_module:
                        alias_names.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and qualified in node.value:
                references.append({
                    "kind": _path_kind(unit.relative),
                    "mechanism": "qualified_string",
                    "path": unit.relative,
                    "line": node.lineno,
                })
        for node in ast.walk(unit.tree):
            if (
                isinstance(node, ast.Attribute) and node.attr == symbol
                and isinstance(node.value, ast.Name) and node.value.id in alias_names
            ):
                references.append({
                    "kind": _path_kind(unit.relative),
                    "mechanism": "qualified_attribute",
                    "path": unit.relative,
                    "line": node.lineno,
                })
    return sorted(references, key=lambda item: (item["path"], item["line"], item["mechanism"]))


def _side_effect_disposition(text: str, module: str, binding: ImportBinding) -> str:
    tree = ast.parse(text)
    same_source_other_names = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and _resolve_from(module, node) == binding.source_module:
            same_source_other_names += sum(
                1 for alias in node.names
                if (alias.asname or alias.name.split(".")[0]) != binding.local_name
            )
        elif isinstance(node, ast.Import):
            same_source_other_names += sum(
                1 for alias in node.names
                if alias.name == binding.source_module
                and (alias.asname or alias.name.split(".")[0]) != binding.local_name
            )
    if binding.alias_count > 1 or same_source_other_names:
        return "PRESERVED_BY_REMAINING_IMPORT"
    root = binding.source_module.split(".", 1)[0]
    if root in SIDE_EFFECT_SAFE_ROOTS:
        return "SAFE_PLATFORM_OR_STDLIB_IMPORT"
    return "IMPORT_SIDE_EFFECT_NOT_DISPROVEN"


def _recursive_strings(value: Any) -> set[str]:
    strings: set[str] = set()
    if isinstance(value, str):
        strings.add(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            strings.update(_recursive_strings(key))
            strings.update(_recursive_strings(item))
    elif isinstance(value, list):
        for item in value:
            strings.update(_recursive_strings(item))
    return strings


def _history(path: str, symbol: str) -> dict[str, str]:
    output = _git("log", "--reverse", "--format=%H%x09%s", "-S", symbol, "--", path, check=False)
    first = output.splitlines()[0] if output.splitlines() else ""
    commit, _, subject = first.partition("\t")
    return {"introduction_commit": commit, "introduction_subject": subject}


def _classify(evidence: dict[str, Any]) -> tuple[str, str]:
    if evidence["h1_name_loads"] or evidence["current_name_loads"]:
        return "RUNTIME_USED", "The binding has a direct AST Name load and must remain."
    if evidence["exported_by___all__"]:
        return "PUBLIC_CONTRACT", "The binding is explicitly exported by the candidate module."
    references = evidence["external_references"]
    if any(item["mechanism"] == "qualified_string" for item in references):
        return "DYNAMIC_REFERENCE", "A fully qualified string reference retains the binding conservatively."
    if evidence["dynamic_module_risks"]:
        return "DYNAMIC_REFERENCE", "Dynamic module or annotation behavior prevents static removal proof."
    runtime = [item for item in references if item["kind"] == "runtime"]
    if runtime:
        if any(Path(item["path"]).name == "__init__.py" for item in runtime):
            return "REGISTERED_RUNTIME", "A package initialization or registration surface imports the binding."
        return "RUNTIME_USED", "Another runtime module references the imported binding."
    if any(item["kind"] == "test" for item in references):
        return "TEST_ONLY", "Test code references the candidate module's imported binding."
    if any(item["kind"] == "dev" for item in references):
        return "DEV_TOOL_ONLY", "Development tooling references the candidate module's imported binding."
    if evidence["side_effect_disposition"] in {
        "PRESERVED_BY_REMAINING_IMPORT", "SAFE_PLATFORM_OR_STDLIB_IMPORT",
    }:
        return "PROVEN_UNUSED", (
            "No direct, exported, dynamic, runtime, test, or development reference exists; "
            "import-time behavior is preserved or belongs to a safe platform/stdlib module."
        )
    return "AMBIGUOUS", "The binding is unused, but removing its sole internal import could change import-time behavior."


def analyze() -> tuple[dict[str, Any], list[str]]:
    h1 = _read_json(H1_LEDGER)
    candidates = [entry for entry in h1["entries"] if entry.get("classification") == "SUSPICIOUS"]
    units = _python_units()
    unit_by_path = {unit.relative: unit for unit in units}
    contract_path = ROOT / "manual-tests" / "hardening" / "reports" / "h1" / "public_contract.json"
    contract_strings = _recursive_strings(_read_json(contract_path)) if contract_path.exists() else set()
    entries: list[dict[str, Any]] = []
    errors: list[str] = []
    for candidate in candidates:
        path = candidate["path"]
        symbol = candidate["symbol"]
        module = candidate["module"]
        baseline_text = _tag_text(path)
        baseline_tree = ast.parse(baseline_text)
        bindings = _find_bindings(baseline_text, module, symbol)
        if len(bindings) != 1:
            errors.append(f"{candidate['candidate_id']}: expected one H1 import binding, found {len(bindings)}")
            continue
        binding = bindings[0]
        current_unit = unit_by_path.get(path)
        if current_unit is None:
            errors.append(f"{candidate['candidate_id']}: current source path is missing")
            continue
        current_bindings = _find_bindings(current_unit.text, module, symbol)
        evidence = {
            "h1_import_line": binding.line,
            "h1_import_statement": binding.statement,
            "source_module": binding.source_module,
            "imported_name": binding.imported_name,
            "h1_name_loads": _name_load_count(baseline_text, symbol),
            "current_name_loads": _name_load_count(current_unit.text, symbol),
            "exported_by___all__": symbol in _all_exports(baseline_tree),
            "dynamic_module_risks": sorted(set(
                _dynamic_module_risks(baseline_tree, symbol)
                + _dynamic_module_risks(current_unit.tree, symbol)
            )),
            "external_references": _external_references(units, path, module, symbol),
            "side_effect_disposition": _side_effect_disposition(baseline_text, module, binding),
            "symbol_present_in_frozen_contract": symbol in contract_strings,
            **_history(path, symbol),
        }
        classification, reason = _classify(evidence)
        removed = not current_bindings
        batch = REMOVAL_BATCH_BY_PATH.get(path, "") if removed else ""
        if removed and classification != "PROVEN_UNUSED":
            errors.append(f"{candidate['candidate_id']}: removed binding classified {classification}")
        if removed and not batch:
            errors.append(f"{candidate['candidate_id']}: removed binding has no validated H2 batch")
        entries.append({
            "candidate_id": candidate["candidate_id"],
            "path": path,
            "module": module,
            "binding": symbol,
            "classification": classification,
            "reason": reason,
            "removed": removed,
            "removal_batch": batch,
            "proof": evidence,
        })
    counts = Counter(entry["classification"] for entry in entries)
    report = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "frozen_h1_tag": H1_TAG,
        "frozen_h1_target": _git("rev-parse", f"{H1_TAG}^{{}}").strip(),
        "h1_candidate_count": len(candidates),
        "resolved_candidate_count": len(entries),
        "classification_counts": dict(sorted(counts.items())),
        "removed_count": sum(1 for entry in entries if entry["removed"]),
        "retained_count": sum(1 for entry in entries if not entry["removed"]),
        "entries": entries,
        "errors": errors,
        "status": "PASS" if not errors and len(entries) == 50 else "FAIL",
    }
    if len(candidates) != 50:
        errors.append(f"Frozen H1 suspicious candidate count is {len(candidates)}, expected 50")
    if len(entries) != 50:
        errors.append(f"Resolved candidate count is {len(entries)}, expected 50")
    invalid = sorted(set(counts) - ALLOWED_CLASSIFICATIONS)
    if invalid:
        errors.append("Invalid classifications: " + ", ".join(invalid))
    report["errors"] = errors
    report["status"] = "PASS" if not errors else "FAIL"
    return report, errors


def render_summary(report: dict[str, Any]) -> str:
    lines = [
        "# H2 suspicious-reference dispositions",
        "",
        f"Status: `{report['status']}`",
        "",
        f"Frozen H1 candidates: `{report['h1_candidate_count']}`; resolved: "
        f"`{report['resolved_candidate_count']}`; removed: `{report['removed_count']}`; "
        f"retained: `{report['retained_count']}`.",
        "",
        "Classifications: " + ", ".join(
            f"`{name}={count}`" for name, count in report["classification_counts"].items()
        ) + ".",
        "",
        "| ID | File | Binding | Disposition | Removed | Batch |",
        "|---|---|---|---|---:|---|",
    ]
    for entry in report["entries"]:
        lines.append(
            f"| {entry['candidate_id']} | `{entry['path']}` | `{entry['binding']}` | "
            f"{entry['classification']} | {'yes' if entry['removed'] else 'no'} | "
            f"{entry['removal_batch'] or '-'} |"
        )
    if report["errors"]:
        lines.extend(("", "Errors:", ""))
        lines.extend(f"- {error}" for error in report["errors"])
    lines.extend(("", "Only `PROVEN_UNUSED` bindings are removal-eligible. Analyzer uncertainty remains retained.", ""))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()
    report, errors = analyze()
    _write_json(args.ledger, report)
    _write_text(args.summary, render_summary(report))
    print(json.dumps({
        "status": report["status"],
        "resolved": report["resolved_candidate_count"],
        "removed": report["removed_count"],
        "counts": report["classification_counts"],
        "errors": errors,
        "ledger_sha256": hashlib.sha256(args.ledger.read_bytes()).hexdigest(),
    }, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
