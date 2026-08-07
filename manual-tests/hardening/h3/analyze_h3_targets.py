"""Build the bounded H3 architecture-risk ledger from frozen H2 targets."""

from __future__ import annotations

import argparse
import ast
from collections import Counter, deque
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "hardening" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import analyze_complexity  # noqa: E402
import analyze_dependencies  # noqa: E402
import _common  # noqa: E402


OUTPUT = ROOT / "hardening" / "h3" / "H3_COMPLEXITY_LEDGER.json"
AFTER_OUTPUT = ROOT / "hardening" / "h3" / "H3_COMPLEXITY_AFTER.json"
SUMMARY = ROOT / "hardening" / "h3" / "H3_COMPLEXITY_LEDGER.md"
REVIEW_CLASSES = {"CRITICAL_REVIEW_PRIORITY", "HIGH_REVIEW_PRIORITY"}
ALLOWED_DISPOSITIONS = {
    "REFACTOR_CANDIDATE",
    "KEEP_AS_IS",
    "SPLIT_FUNCTION",
    "EXTRACT_PURE_HELPER",
    "EXTRACT_INTERNAL_SERVICE",
    "SIMPLIFY_CONTROL_FLOW",
    "CONSOLIDATE_DUPLICATE_FLOW",
    "TEST_FIRST",
    "PUBLIC_CONTRACT_LOCKED",
    "DYNAMIC_OR_HIGH_RISK",
    "INSUFFICIENT_EVIDENCE",
}
SELECTIONS = {
    "blender_addon/chroma3d_sculpt/services/repair_operations.py": (
        "repair_normal_consistency",
        "EXTRACT_PURE_HELPER",
        "Separate deterministic component-winding planning from the owned-copy mutation loop.",
    ),
    "blender_addon/chroma3d_sculpt/services/ai_assistance_coordinator.py": (
        "request_recommendations",
        "SPLIT_FUNCTION",
        "Separate fail-closed dispatch validation, validated-response binding, and failure finalization.",
    ),
    "blender_addon/chroma3d_sculpt/services/mesh_analyzer.py": (
        "_analyze",
        "SPLIT_FUNCTION",
        "Extract deterministic warning/result assembly from Blender-bound read-only orchestration.",
    ),
}
PUBLIC_BOUNDARIES = {
    "blender_addon/chroma3d_sculpt/models/ai_assistance_models.py",
    "blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py",
    "blender_addon/chroma3d_sculpt/models/optimization_models.py",
    "blender_addon/chroma3d_sculpt/models/printability_models.py",
    "blender_addon/chroma3d_sculpt/ui/panels.py",
}
STATEFUL_PATHS = {
    "blender_addon/chroma3d_sculpt/services/ai_assistance_coordinator.py",
    "blender_addon/chroma3d_sculpt/services/intelligent_optimization_coordinator.py",
    "blender_addon/chroma3d_sculpt/services/repair_operations.py",
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value.rstrip() + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def _current_python_paths() -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or "git ls-files failed")
    return [
        ROOT / path
        for path in sorted(completed.stdout.splitlines())
        if path.endswith(".py") and not path.startswith(_common.HARDENING_EXCLUSIONS)
    ]


def _has_import(tree: ast.AST, roots: set[str]) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".", 1)[0] in roots for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".", 1)[0] in roots:
                return True
    return False


def _sprint(path: str) -> str:
    lowered = path.lower()
    for number in range(8):
        if f"sprint{number}" in lowered or f"sprint-{number}" in lowered:
            return f"Sprint {number}"
    if any(value in lowered for value in ("mesh_analyzer", "topology_analyzer", "shell_analyzer")):
        return "Sprint 1"
    if "repair" in lowered or "boundary_loops" in lowered:
        return "Sprint 2"
    if "printability" in lowered:
        return "Sprint 3"
    if "advanced_preparation" in lowered:
        return "Sprint 4"
    if "optimization_models" in lowered:
        return "Sprint 5"
    if "intelligent_optimization" in lowered:
        return "Sprint 6"
    if "ai_assistance" in lowered:
        return "Sprint 7"
    return "Cross-sprint validation"


def _tests_for(path: str) -> list[str]:
    lowered = path.lower()
    values: list[str] = []
    mappings = (
        (("mesh_analyzer", "topology_analyzer", "shell_analyzer"), ("tests/blender/test_mesh_analysis.py", "tests/blender/test_sprint1_diagnostics.py")),
        (("repair", "boundary_loops"), ("tests/blender/test_sprint2_repair.py",)),
        (("printability",), ("tests/blender/test_sprint3_printability.py",)),
        (("advanced_preparation",), ("tests/blender/test_sprint4_advanced_preparation.py",)),
        (("optimization",), ("tests/blender/test_sprint5_optimization.py",)),
        (("intelligent_optimization", "strategy"), ("tests/blender/test_sprint6_intelligent_optimization.py",)),
        (("ai_assistance", "sprint7"), ("tests/blender/test_sprint7_ai_recommendation.py",)),
    )
    for tokens, tests in mappings:
        if any(token in lowered for token in tokens):
            values.extend(test for test in tests if (ROOT / test).is_file())
    if path.startswith("tests/"):
        values.append(path)
    if path.startswith("manual-tests/"):
        values.append(path)
    return sorted(set(values))


def _reverse_graph(imports: dict[str, list[str]]) -> dict[str, set[str]]:
    reverse = {module: set() for module in imports}
    for source, targets in imports.items():
        for target in targets:
            reverse.setdefault(target, set()).add(source)
    return reverse


def _reachable_callers(module: str, reverse: dict[str, set[str]]) -> set[str]:
    found: set[str] = set()
    pending = deque(reverse.get(module, ()))
    while pending:
        caller = pending.popleft()
        if caller in found:
            continue
        found.add(caller)
        pending.extend(reverse.get(caller, ()))
    return found


def _flags(path: str, text: str, tree: ast.AST) -> dict[str, bool]:
    lowered = text.lower()
    validation_only = path.startswith(("tests/", "manual-tests/"))
    return {
        "blender_coupled": _has_import(tree, {"bpy", "bmesh", "mathutils"}),
        "blender_registration_involvement": "bl_idname" in text or "register_class" in text or "_CLASSES" in text,
        "mutation_involvement": path.endswith("repair_operations.py") or ("bmesh.ops" in text and "to_mesh" in text),
        "filesystem_involvement": any(token in text for token in ("write_text(", "write_bytes(", "Path(", "open(", "os.replace")),
        "network_or_provider_involvement": any(token in lowered for token in ("provider", "transporterror", "urlopen", "http")),
        "lifecycle_or_state_involvement": path in STATEFUL_PATHS or any(token in lowered for token in ("transition(", "session", "cleanup", "cancel")),
        "source_protection_involvement": any(token in lowered for token in ("source_signature", "read_only_state", "repair", "workspace")),
        "checkpoint_or_rollback_involvement": any(token in lowered for token in ("checkpoint", "rollback", "restore")),
        "validation_only": validation_only,
        "public_contract_exposure": path in PUBLIC_BOUNDARIES,
    }


def _invariants(path: str, flags: dict[str, bool]) -> list[str]:
    values = ["Externally observable results and error classifications remain unchanged."]
    if flags["mutation_involvement"]:
        values.extend((
            "Only the caller-owned repair workspace may be mutated.",
            "Vertex coordinates, source identity, and non-selected geometry remain unchanged.",
        ))
    if flags["network_or_provider_involvement"]:
        values.extend((
            "Provider output remains untrusted strict structured data with local grounding.",
            "Consent, bounded attempts, cancellation quarantine, redaction, and offline fallback remain unchanged.",
        ))
    if "mesh_analyzer.py" in path:
        values.extend((
            "Analysis remains read-only and preserves object, mesh, transform, mode, and selection state.",
            "Skipped, failed, and indeterminate checks remain explicit and never become PASS.",
        ))
    if flags["public_contract_exposure"]:
        values.append("Operator, property, enum, schema, profile, and serialized identities remain frozen.")
    if flags["validation_only"]:
        values.append("Validation thresholds and first-failure behavior remain unchanged.")
    return values


def _disposition(path: str, flags: dict[str, bool]) -> tuple[str, str, str]:
    if path in SELECTIONS:
        symbol, disposition, strategy = SELECTIONS[path]
        return disposition, strategy, symbol
    if flags["public_contract_exposure"]:
        return "PUBLIC_CONTRACT_LOCKED", "Retain the frozen serialized or registered boundary.", ""
    if flags["validation_only"]:
        return "KEEP_AS_IS", "Retain explicit validation matrices and runners outside the bounded runtime slice.", ""
    if flags["blender_registration_involvement"]:
        return "DYNAMIC_OR_HIGH_RISK", "Retain dynamic registration code without stronger behavior locks.", ""
    if flags["lifecycle_or_state_involvement"]:
        return "TEST_FIRST", "Add narrower lifecycle characterization before any later structural change.", ""
    return "KEEP_AS_IS", "Retain for H3; complexity alone does not justify expanding the bounded implementation set.", ""


def _risk_score(metrics: dict[str, Any], flags: dict[str, bool]) -> float:
    score = (
        float(metrics["branch_count_estimate"])
        + float(metrics["loc"]) / 20.0
        + float(metrics["maximum_function_loc"]) / 3.0
        + float(metrics["nesting_depth"]) * 4.0
        + float(metrics["import_fan_in"])
        + float(metrics["import_fan_out"])
    )
    score += 90.0 if flags["mutation_involvement"] else 0.0
    score += 70.0 if flags["network_or_provider_involvement"] else 0.0
    score += 45.0 if flags["lifecycle_or_state_involvement"] else 0.0
    score += 35.0 if flags["source_protection_involvement"] else 0.0
    score += 25.0 if flags["checkpoint_or_rollback_involvement"] else 0.0
    score += 20.0 if flags["public_contract_exposure"] else 0.0
    if flags["validation_only"]:
        score *= 0.25
    return round(score, 3)


def _target_paths(complexity: dict[str, Any], phase: str) -> list[str]:
    if phase == "before":
        return sorted(item["path"] for item in complexity["modules"] if item["classification"] in REVIEW_CLASSES)
    baseline = _read_json(OUTPUT)
    return sorted(item["file"] for item in baseline["entries"])


def build(phase: str = "before") -> tuple[dict[str, Any], list[str]]:
    current_paths = _current_python_paths()
    analyze_dependencies.checkpoint_python_paths = lambda: current_paths
    analyze_complexity.checkpoint_python_paths = lambda: current_paths
    complexity = analyze_complexity.analyze()
    dependency = analyze_dependencies.analyze()
    modules = {item["path"]: item for item in complexity["modules"]}
    imports = dependency["module_imports"]
    reverse = _reverse_graph(imports)
    target_paths = _target_paths(complexity, phase)
    rows: list[dict[str, Any]] = []
    for path in target_paths:
        metrics = modules[path]
        text = _source(path)
        tree = ast.parse(text, filename=path)
        flags = _flags(path, text, tree)
        disposition, strategy, selected_symbol = _disposition(path, flags)
        callers = sorted(reverse.get(metrics["module"], ()))
        reachable = _reachable_callers(metrics["module"], reverse)
        largest = (metrics.get("functions") or [{}])[0]
        selected_metrics = next(
            (item for item in metrics.get("functions", ()) if item.get("symbol", "").split(".")[-1] == selected_symbol),
            None,
        )
        rows.append({
            "file": path,
            "symbol": metrics["module"],
            "symbol_type": "MODULE",
            "priority_band": metrics["classification"],
            "physical_loc": metrics["loc"],
            "logical_complexity": int(metrics["branch_count_estimate"]) + 1,
            "branch_count": metrics["branch_count_estimate"],
            "nesting_depth": metrics["nesting_depth"],
            "dependency_count": metrics["import_fan_out"],
            "dependency_fan_in": metrics["import_fan_in"],
            "direct_dependencies": imports.get(metrics["module"], []),
            "direct_callers": callers,
            "indirect_public_reachability": {
                "reachable_caller_count": len(reachable),
                "registration_or_ui_reachable": any(".ui." in item or ".operators." in item for item in reachable),
                "test_or_runner_reachable": any(item.startswith(("tests.", "manual-tests.")) for item in reachable),
            },
            **flags,
            "tests_exercising": _tests_for(path),
            "relevant_sprint": _sprint(path),
            "relevant_invariants": _invariants(path, flags),
            "largest_function": largest,
            "selected_symbol": selected_symbol,
            "selected_symbol_metrics": selected_metrics,
            "likely_refactor_strategy": strategy,
            "refactor_risk": "HIGH" if any(flags[key] for key in ("mutation_involvement", "network_or_provider_involvement", "public_contract_exposure")) else "MODERATE",
            "risk_score": _risk_score(metrics, flags),
            "disposition": disposition,
        })
    rows.sort(key=lambda item: (-float(item["risk_score"]), str(item["file"])))
    for rank, row in enumerate(rows, 1):
        row["risk_rank"] = rank
    selected = [row for row in rows if row["selected_symbol"]]
    selected.sort(key=lambda item: list(SELECTIONS).index(item["file"]))
    errors: list[str] = []
    counts = Counter(item["disposition"] for item in rows)
    if phase == "before":
        critical = sum(item["priority_band"] == "CRITICAL_REVIEW_PRIORITY" for item in rows)
        high = sum(item["priority_band"] == "HIGH_REVIEW_PRIORITY" for item in rows)
        if (critical, high, len(rows)) != (7, 28, 35):
            errors.append(f"Expected 7 critical + 28 high = 35, got {critical} + {high} = {len(rows)}")
    if len(selected) != 3:
        errors.append(f"Expected exactly 3 selected targets, got {len(selected)}")
    invalid = sorted(set(counts) - ALLOWED_DISPOSITIONS)
    if invalid:
        errors.append("Invalid dispositions: " + ", ".join(invalid))
    report = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "source_checkpoint": "v0.8.0-h2-hardening-checkpoint",
        "source_sha": "208016e87dbebe0580d9fa63cd1392e398fc3bf2",
        "metric_definition": {
            "physical_loc": "Module physical lines from the frozen hardening analyzer.",
            "logical_complexity": "One plus the module AST branch-node count; review signal only.",
            "branch_count": "AST control-flow and comprehension node count.",
            "dependency_count": "Direct internal import fan-out.",
        },
        "target_count": len(rows),
        "priority_counts": dict(sorted(Counter(item["priority_band"] for item in rows).items())),
        "disposition_counts": dict(sorted(counts.items())),
        "selected_targets": [
            {
                "order": index,
                "file": item["file"],
                "symbol": item["selected_symbol"],
                "disposition": item["disposition"],
                "reason": item["likely_refactor_strategy"],
                "risk_rank": item["risk_rank"],
            }
            for index, item in enumerate(selected, 1)
        ],
        "selection_policy": "Highest-value eligible runtime targets after excluding validation-only and public-contract-locked entries; one mutation path, one provider/state path, and one read-only analysis coordinator.",
        "entries": rows,
        "dependency_summary": {
            "module_count": dependency["module_count"],
            "internal_edges": dependency["internal_dependency_count"],
            "circular_components": len(dependency["potential_circular_imports"]),
            "service_to_ui_or_operator_edges": len(dependency["service_imports_ui_or_operators"]),
        },
        "errors": errors,
        "status": "PASS" if not errors else "FAIL",
    }
    return report, errors


def render(report: dict[str, Any]) -> str:
    lines = [
        "# H3 complexity and architecture-risk ledger",
        "",
        f"Status: `{report['status']}`. Targets: `{report['target_count']}`.",
        "",
        "The bounded implementation set excludes validation-only and public-contract-locked entries even when their raw complexity score is higher.",
        "",
        "| Order | File | Symbol | Disposition | Risk rank |",
        "|---:|---|---|---|---:|",
    ]
    for item in report["selected_targets"]:
        lines.append(f"| {item['order']} | `{item['file']}` | `{item['symbol']}` | {item['disposition']} | {item['risk_rank']} |")
    lines.extend(("", "All 35 entries and their callers, dependencies, invariants, coverage, risk evidence, and dispositions are retained in `H3_COMPLEXITY_LEDGER.json`."))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("before", "after"), default="before")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report, errors = build(args.phase)
    output = args.output or (OUTPUT if args.phase == "before" else AFTER_OUTPUT)
    _write_json(output, report)
    if args.phase == "before":
        _write_text(SUMMARY, render(report))
    print(json.dumps({
        "status": report["status"],
        "targets": report["target_count"],
        "selected": [item["symbol"] for item in report["selected_targets"]],
        "circular_components": report["dependency_summary"]["circular_components"],
        "errors": errors,
    }, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
