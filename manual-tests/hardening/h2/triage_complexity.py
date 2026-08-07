"""Rank and disposition the frozen 7 critical and 29 high H1 complexity hotspots."""

from __future__ import annotations

import ast
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
H1_COMPLEXITY = ROOT / "manual-tests" / "hardening" / "reports" / "h1" / "complexity.json"
H1_LEDGER = ROOT / "hardening" / "h1" / "H1_DISPOSITION_LEDGER.json"
OUTPUT = ROOT / "hardening" / "h2" / "H2_COMPLEXITY_TRIAGE.json"
SUMMARY = ROOT / "hardening" / "h2" / "H2_COMPLEXITY_TRIAGE.md"
REVIEW_CLASSES = {"CRITICAL_REVIEW_PRIORITY", "HIGH_REVIEW_PRIORITY"}
ALLOWED_DISPOSITIONS = {
    "REFACTOR_NOW", "KEEP_COMPLEX", "DEFER", "NEEDS_MORE_TESTS",
    "PUBLIC_BOUNDARY", "STATEFUL_RISK",
}
REFACTOR_NOW = {"blender_addon/chroma3d_sculpt/services/strategy_generator.py"}
PUBLIC_BOUNDARIES = {
    "blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py",
    "blender_addon/chroma3d_sculpt/models/ai_assistance_models.py",
    "blender_addon/chroma3d_sculpt/models/printability_models.py",
    "blender_addon/chroma3d_sculpt/models/optimization_models.py",
    "blender_addon/chroma3d_sculpt/ui/panels.py",
}
STATEFUL_RISKS = {
    "blender_addon/chroma3d_sculpt/services/repair_operations.py",
    "blender_addon/chroma3d_sculpt/services/ai_assistance_coordinator.py",
    "blender_addon/chroma3d_sculpt/services/intelligent_optimization_coordinator.py",
}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8", newline="\n")
    temporary.replace(path)


def _imports_blender(path: str) -> bool:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(alias.name.split(".", 1)[0] in {"bpy", "bmesh", "mathutils"} for alias in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".", 1)[0] in {"bpy", "bmesh", "mathutils"}:
            return True
    return False


def _ownership(path: str) -> str:
    if path == "blender_addon/chroma3d_sculpt/services/repair_operations.py":
        return "GEOMETRY_MUTATION"
    if "coordinator.py" in path:
        return "SESSION_OR_WORKSPACE_STATE"
    if "/models/" in path:
        return "SERIALIZED_CONTRACT"
    if path.startswith("tests/") or path.startswith("manual-tests/"):
        return "VALIDATION_ONLY"
    if path.endswith("strategy_generator.py"):
        return "PURE_DETERMINISTIC_GENERATION"
    if any(name in path for name in ("mesh_analyzer.py", "topology_analyzer.py", "shell_analyzer.py", "printability_coordinator.py", "boundary_loops.py")):
        return "READ_ONLY_GEOMETRY_EVIDENCE"
    if "/ui/" in path:
        return "UI_RENDERING"
    return "RUNTIME_LOGIC"


def _coverage(path: str) -> dict[str, Any]:
    if "strategy_generator.py" in path or "intelligent_optimization" in path:
        return {"status": "STRONG", "evidence": "Sprint 6 focused 222/222 and H1 combined regression"}
    if "ai_assistance" in path or "sprint7" in path:
        return {"status": "STRONG", "evidence": "Sprint 7 focused 62/62 and H1 combined regression"}
    if "repair" in path or "sprint2" in path:
        return {"status": "STRONG", "evidence": "Sprint 2 focused 60/60 and H1 combined regression"}
    if any(value in path for value in ("printability", "topology", "shell_analyzer", "boundary_loops", "sprint3")):
        return {"status": "BROAD", "evidence": "Sprint 3 focused 121/121 and H1 combined regression"}
    if "sprint4" in path:
        return {"status": "BROAD", "evidence": "Sprint 4 focused 137/137 and H1 combined regression"}
    if "optimization" in path or "sprint5" in path:
        return {"status": "STRONG", "evidence": "Sprint 5 focused 161/161 and H1 combined regression"}
    return {"status": "HARNESS", "evidence": "Validation/benchmark code is exercised by its owning gate, not runtime product tests"}


def _disposition(path: str) -> tuple[str, str]:
    if path in REFACTOR_NOW:
        return (
            "REFACTOR_NOW",
            "Deterministic private generation logic has strong regression coverage and can separate candidate validation from bounded execution without changing state ownership or public APIs.",
        )
    if path in PUBLIC_BOUNDARIES:
        return "PUBLIC_BOUNDARY", "Typed models or registered UI expose public/serialized behavior; metric-only restructuring is not justified."
    if path in STATEFUL_RISKS:
        return "STATEFUL_RISK", "Geometry mutation, provider workflow, or session state transitions make structural movement higher risk than the measured complexity."
    if path.startswith("manual-tests/"):
        return "DEFER", "Development validation orchestration is outside the runtime-risk reduction slice selected for H2."
    return "KEEP_COMPLEX", "The complexity represents explicit test matrices or distinct read-only geometry/evidence semantics; extraction has no independently proven maintenance benefit."


def _score(item: dict[str, Any], ownership: str) -> float:
    score = (
        float(item["branch_count_estimate"])
        + float(item["loc"]) / 20.0
        + float(item["maximum_function_loc"]) / 5.0
        + float(item["import_fan_in"])
        + float(item["import_fan_out"])
        + float(item["nesting_depth"]) * 2.0
    )
    if ownership in {"GEOMETRY_MUTATION", "SESSION_OR_WORKSPACE_STATE", "SERIALIZED_CONTRACT"}:
        score += 25.0
    return round(score, 3)


def build() -> tuple[dict[str, Any], list[str]]:
    complexity = _read(H1_COMPLEXITY)
    h1_ledger = _read(H1_LEDGER)
    candidates = [item for item in complexity["modules"] if item["classification"] in REVIEW_CLASSES]
    duplicate_paths = Counter()
    for entry in h1_ledger["entries"]:
        if not str(entry.get("candidate_id", "")).startswith("H1-DUP-"):
            continue
        for path in entry.get("evidence", {}).get("files", ()):
            duplicate_paths[path] += 1
    rows: list[dict[str, Any]] = []
    for item in candidates:
        path = item["path"]
        ownership = _ownership(path)
        disposition, reason = _disposition(path)
        coverage = _coverage(path)
        rows.append({
            "path": path,
            "module": item["module"],
            "h1_priority": item["classification"],
            "disposition": disposition,
            "reason": reason,
            "rank_score": _score(item, ownership),
            "metrics": {
                "physical_loc": item["loc"],
                "branch_count_estimate": item["branch_count_estimate"],
                "maximum_function_loc": item["maximum_function_loc"],
                "nesting_depth": item["nesting_depth"],
                "import_fan_in": item["import_fan_in"],
                "import_fan_out": item["import_fan_out"],
                "function_count": item["function_count"],
                "class_count": item["class_count"],
                "h1_duplication_candidate_overlap": duplicate_paths[path],
            },
            "risk": {
                "mutation_ownership": ownership,
                "blender_coupled": _imports_blender(path),
                "public_contract_exposure": path in PUBLIC_BOUNDARIES,
                "state_machine_involvement": path in STATEFUL_RISKS,
                "failure_blast_radius": "HIGH" if item["classification"] == "CRITICAL_REVIEW_PRIORITY" else "MODERATE",
            },
            "test_coverage": coverage,
            "selected_symbol": "generate_strategies" if path in REFACTOR_NOW else "",
            "selected_transformation": "extract private candidate validation and cancellation predicate" if path in REFACTOR_NOW else "",
        })
    rows.sort(key=lambda row: (-row["rank_score"], row["path"]))
    for index, row in enumerate(rows, 1):
        row["rank"] = index
    counts = Counter(row["disposition"] for row in rows)
    errors: list[str] = []
    expected = complexity.get("classification_counts", {})
    if expected.get("CRITICAL_REVIEW_PRIORITY") != 7 or expected.get("HIGH_REVIEW_PRIORITY") != 29:
        errors.append("Frozen H1 complexity counts are not 7 critical and 29 high")
    if len(rows) != 36:
        errors.append(f"Complexity triage has {len(rows)} rows, expected 36")
    invalid = sorted(set(counts) - ALLOWED_DISPOSITIONS)
    if invalid:
        errors.append("Invalid dispositions: " + ", ".join(invalid))
    if counts.get("REFACTOR_NOW", 0) != 1:
        errors.append("Exactly one bounded REFACTOR_NOW candidate was expected")
    report = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "h1_counts": {"critical": 7, "high": 29, "total": 36},
        "triaged_count": len(rows),
        "disposition_counts": dict(sorted(counts.items())),
        "entries": rows,
        "errors": errors,
        "status": "PASS" if not errors else "FAIL",
    }
    return report, errors


def render(report: dict[str, Any]) -> str:
    lines = [
        "# H2 complexity hotspot triage",
        "",
        f"Status: `{report['status']}`. Frozen H1 queue: `7 critical + 29 high = 36`; triaged: `{report['triaged_count']}`.",
        "",
        "Dispositions: " + ", ".join(f"`{key}={value}`" for key, value in report["disposition_counts"].items()) + ".",
        "",
        "Only `strategy_generator.generate_strategies` is selected. The bounded transformation extracts private candidate validation and cancellation logic; public identity, ordering, budgets, pruning, hashes, and state ownership remain unchanged.",
        "",
        "| Rank | H1 priority | Path | Disposition | Score | Ownership |",
        "|---:|---|---|---|---:|---|",
    ]
    for entry in report["entries"]:
        lines.append(
            f"| {entry['rank']} | {entry['h1_priority']} | `{entry['path']}` | {entry['disposition']} | "
            f"{entry['rank_score']} | {entry['risk']['mutation_ownership']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    report, errors = build()
    _write(OUTPUT, json.dumps(report, indent=2, sort_keys=True) + "\n")
    _write(SUMMARY, render(report))
    print(json.dumps({
        "status": report["status"],
        "triaged": report["triaged_count"],
        "dispositions": report["disposition_counts"],
        "errors": errors,
    }, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
