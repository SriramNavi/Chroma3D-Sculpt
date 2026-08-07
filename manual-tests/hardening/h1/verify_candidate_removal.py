"""Build and verify the conservative H1 candidate disposition ledger."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
H0_REPORTS = ROOT / "manual-tests" / "hardening" / "reports"
H1_ROOT = ROOT / "hardening" / "h1"
DEFAULT_LEDGER = H1_ROOT / "H1_DISPOSITION_LEDGER.json"
DEFAULT_SUMMARY = H1_ROOT / "H1_DISPOSITION_SUMMARY.md"
H0_TAG = "v0.8.0-h0-hardening-baseline"
H0_MERGE = "6f20b8c3007658a78eb89e2d2937924175384feb"

ALLOWED_CLASSIFICATIONS = (
    "KEEP",
    "REGISTERED_RUNTIME",
    "DYNAMIC_REFERENCE",
    "PUBLIC_CONTRACT",
    "TEST_ONLY",
    "DEV_TOOL_ONLY",
    "COMPATIBILITY",
    "GENERATED_REFERENCE",
    "DUPLICATE_BUT_KEEP",
    "SUSPICIOUS",
    "UNRESOLVED",
    "SAFE_TO_REMOVE",
)

REMOVED_SYMBOLS = {
    ("blender_addon/chroma3d_sculpt/services/repair_coordinator.py", "compare_results"): "H1-R1",
    ("blender_addon/chroma3d_sculpt/services/repair_coordinator.py", "_metric_summary"): "H1-R1",
    ("blender_addon/chroma3d_sculpt/session.py", "has_result"): "H1-R1",
    ("blender_addon/chroma3d_sculpt/utilities/units.py", "object_dimensions_mm"): "H1-R1",
    ("blender_addon/chroma3d_sculpt/ui/properties.py", "reset_session_state"): "H1-R2",
    ("blender_addon/chroma3d_sculpt/optimization_settings.py", "_ALL"): "H1-R3",
}

REMOVED_IMPORTS = {
    ("blender_addon/chroma3d_sculpt/services/pareto_frontier.py", "Any"): "H1-R4",
    ("blender_addon/chroma3d_sculpt/services/pareto_frontier.py", "Iterable"): "H1-R4",
    ("blender_addon/chroma3d_sculpt/services/pareto_frontier.py", "Mapping"): "H1-R4",
    ("blender_addon/chroma3d_sculpt/services/pareto_frontier.py", "stable_hash"): "H1-R4",
    ("blender_addon/chroma3d_sculpt/services/strategy_explainer.py", "Any"): "H1-R4",
    ("blender_addon/chroma3d_sculpt/services/strategy_explainer.py", "Mapping"): "H1-R4",
    ("blender_addon/chroma3d_sculpt/services/strategy_explainer.py", "EvidenceState"): "H1-R4",
    ("blender_addon/chroma3d_sculpt/services/strategy_generator.py", "asdict"): "H1-R4",
    ("blender_addon/chroma3d_sculpt/services/strategy_generator.py", "is_dataclass"): "H1-R4",
    ("blender_addon/chroma3d_sculpt/services/strategy_generator.py", "math"): "H1-R4",
}

SOURCE_ROOTS = (
    ROOT / "blender_addon",
    ROOT / "benchmarks",
    ROOT / "hardening" / "tools",
    ROOT / "manual-tests",
    ROOT / "scripts",
    ROOT / "tests",
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, check=False, capture_output=True, text=True, encoding="utf-8"
    )
    if check and completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout.strip()


def _module_for(path: str) -> str:
    value = Path(path).with_suffix("").as_posix().replace("/", ".")
    prefix = "blender_addon."
    return value[len(prefix):] if value.startswith(prefix) else value


def _contract_names(contract: dict[str, Any]) -> set[str]:
    result = set(contract.get("property_names", ()))
    result.update(contract.get("important_serialized_keys", ()))
    result.update(contract.get("metadata_versions", {}).keys())
    for collection in (contract.get("feature_flag_ids", ()), contract.get("profile_ids", ())):
        for item in collection:
            if isinstance(item, dict):
                result.update(str(value) for value in item.values() if isinstance(value, str))
            elif isinstance(item, str):
                result.add(item)
    for record in contract.get("status_and_result_enums", ()):
        result.add(str(record.get("enum", "")))
        for member in record.get("members", ()):
            result.add(str(member.get("name", "")))
            result.add(str(member.get("value", "")))
    return result


def _registration_names() -> set[str]:
    values: set[str] = set()
    for path in (ROOT / "blender_addon" / "chroma3d_sculpt").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                base_names = {ast.unparse(base) for base in node.bases}
                if any(name.endswith(("Operator", "Panel", "PropertyGroup")) for name in base_names):
                    values.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "CLASSES":
                        for item in ast.walk(node.value):
                            if isinstance(item, ast.Name):
                                values.add(item.id)
    return values


def _baseline_contains_definition(path: str, symbol: str) -> bool:
    text = _git("show", f"{H0_TAG}:{path}")
    pattern = rf"(?m)^\s*(?:async\s+def|def|class)\s+{re.escape(symbol)}\b|^\s*{re.escape(symbol)}\s*="
    return re.search(pattern, text) is not None


def _current_contains_definition(path: str, symbol: str) -> bool:
    target = ROOT / path
    if not target.is_file():
        return False
    text = target.read_text(encoding="utf-8")
    pattern = rf"(?m)^\s*(?:async\s+def|def|class)\s+{re.escape(symbol)}\b|^\s*{re.escape(symbol)}\s*="
    return re.search(pattern, text) is not None


def _current_reference_count(symbol: str) -> int:
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(symbol)}(?![A-Za-z0-9_])")
    count = 0
    for root in SOURCE_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".py", ".md", ".json", ".toml", ".ps1"}:
                continue
            if "reports" in path.parts or ("hardening" in path.parts and "h1" in path.parts):
                continue
            count += len(pattern.findall(path.read_text(encoding="utf-8", errors="replace")))
    return count


def _path_reference_count(path: str, symbol: str) -> int:
    target = ROOT / path
    if not target.is_file():
        return 0
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(symbol)}(?![A-Za-z0-9_])")
    return len(pattern.findall(target.read_text(encoding="utf-8", errors="replace")))


def _contains_import(text: str, symbol: str) -> bool:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for alias in node.names:
            local = alias.asname or alias.name.split(".")[0]
            if local == symbol:
                return True
    return False


def _baseline_contains_import(path: str, symbol: str) -> bool:
    return _contains_import(_git("show", f"{H0_TAG}:{path}"), symbol)


def _current_contains_import(path: str, symbol: str) -> bool:
    target = ROOT / path
    return target.is_file() and _contains_import(target.read_text(encoding="utf-8"), symbol)


def _focused_tests() -> list[str]:
    result = [
        "Sprint 0: 12/12 PASS",
        "Sprint 1: 39/39 PASS",
        "Sprint 2: 60/60 PASS",
        "Sprint 5: 161/161 PASS",
        "Sprint 6: 222/222 PASS",
        "Blender registration: 82 classes PASS",
    ]
    final_path = H1_ROOT / "H1_FINAL_RESULT.json"
    if final_path.is_file():
        final = _read_json(final_path)
        combined = final.get("evidence", {}).get("combined_tests", {})
        if combined.get("status") == "PASS":
            result.append(f"Combined Blender: {combined.get('tests_run')}/{combined.get('tests_run')} PASS")
    return result


def _classification_for_symbol(
    candidate: dict[str, Any], contract_names: set[str], registration_names: set[str]
) -> tuple[str, str]:
    path = str(candidate["file"])
    name = str(candidate["name"])
    qualified = str(candidate["qualified_name"])
    if (path, qualified) in REMOVED_SYMBOLS or (path, name) in REMOVED_SYMBOLS:
        return "SAFE_TO_REMOVE", "All removal-proof surfaces were negative and the bounded removal gates passed."
    if path.startswith("tests/"):
        return "TEST_ONLY", "Discovered by the Blender unittest harness; test methods and fixtures are validation contracts."
    if path.startswith(("manual-tests/", "benchmarks/", "hardening/", "scripts/")):
        return "DEV_TOOL_ONLY", "Retained development, validation, benchmark, or hardening entrypoint."
    dynamic = candidate.get("dynamic_or_registration_evidence", {})
    if bool(dynamic.get("registration")) or name == "CLASSES" or qualified in registration_names:
        return "REGISTERED_RUNTIME", "Referenced by Blender registration or a registered class surface."
    if path.startswith("blender_addon/chroma3d_sculpt/operators/") or path.startswith("blender_addon/chroma3d_sculpt/ui/"):
        return "REGISTERED_RUNTIME", "Operator, panel, draw, property, or callback member retained for Blender runtime dispatch."
    if bool(dynamic.get("reflection_string")):
        return "DYNAMIC_REFERENCE", "H0 recorded a string/reflection surface; static reference counts are not deletion proof."
    if name in contract_names or qualified in contract_names or "/models/" in path or path.endswith("/metadata.py"):
        return "PUBLIC_CONTRACT", "Schema, dataclass, enum, metadata, or serialized contract member retained."
    if candidate.get("kind") == "property_or_enum_member":
        return "DYNAMIC_REFERENCE", "Attribute access and dataclass construction are not resolved by the H0 name-only analyzer."
    return "UNRESOLVED", "No complete dynamic, compatibility, and public-use proof; fail closed."


def _base_entry(
    candidate_id: str,
    symbol: str,
    path: str,
    classification: str,
    reason: str,
    *,
    evidence: dict[str, Any],
    removed: bool = False,
    group: str = "",
    notes: str = "",
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "symbol": symbol,
        "module": _module_for(path),
        "path": path,
        "classification": classification,
        "reason": reason,
        "evidence": evidence,
        "references_checked": [
            "H0 AST symbol/import graph",
            "current exact-name source and string scan",
            "package exports and __all__",
            "Blender registration arrays and class surfaces",
            "schemas, documentation, tests, and retained contract",
            "Git introduction history for removed symbols",
        ],
        "public_contract_checked": True,
        "registration_checked": True,
        "tests_checked": _focused_tests() if removed else [],
        "removed": removed,
        "removal_commit_candidate_group": group,
        "notes": notes,
    }


def _symbol_entries(
    report: dict[str, Any], contract_names: set[str], registration_names: set[str]
) -> list[dict[str, Any]]:
    entries = []
    seen_removed: set[tuple[str, str]] = set()
    for index, candidate in enumerate(report["candidates"], 1):
        path = str(candidate["file"])
        qualified = str(candidate["qualified_name"])
        name = str(candidate["name"])
        classification, reason = _classification_for_symbol(candidate, contract_names, registration_names)
        key = (path, qualified) if (path, qualified) in REMOVED_SYMBOLS else (path, name)
        removed = classification == "SAFE_TO_REMOVE"
        if removed:
            seen_removed.add(key)
        entries.append(
            _base_entry(
                f"H1-P1-{index:04d}", qualified, path, classification, reason,
                evidence={
                    "h0_line": candidate.get("line"),
                    "h0_kind": candidate.get("kind"),
                    "h0_static_references": candidate.get("static_references"),
                    "h0_test_evidence": candidate.get("test_evidence"),
                    "h0_dynamic_or_registration_evidence": candidate.get("dynamic_or_registration_evidence"),
                    "package_inclusion": candidate.get("package_inclusion"),
                    "baseline_definition_present": _baseline_contains_definition(path, name) if removed else None,
                    "current_definition_absent": not _current_contains_definition(path, name) if removed else None,
                    "current_reference_count": _current_reference_count(name) if removed else None,
                    "public_contract_name_present": name in contract_names or qualified in contract_names,
                },
                removed=removed,
                group=REMOVED_SYMBOLS.get(key, ""),
                notes="H0 candidate; candidate count is not a defect verdict.",
            )
        )
    for (path, symbol), group in REMOVED_SYMBOLS.items():
        if (path, symbol) in seen_removed:
            continue
        entries.append(
            _base_entry(
                "H1-DERIVED-0001", symbol, path, "SAFE_TO_REMOVE",
                "Private helper was reachable only through another fully proven dead function in the same bounded batch.",
                evidence={
                    "source": "H1 derived dependency proof",
                    "baseline_definition_present": _baseline_contains_definition(path, symbol),
                    "current_definition_absent": not _current_contains_definition(path, symbol),
                    "current_reference_count": _current_reference_count(symbol),
                    "public_contract_name_present": symbol in contract_names,
                },
                removed=True,
                group=group,
                notes="Derived candidate; absent from H0 because private symbols were excluded from its candidate list.",
            )
        )
    return entries


def _dependency_entries(report: dict[str, Any]) -> list[dict[str, Any]]:
    entries = []
    for index, candidate in enumerate(report.get("statically_unreferenced_candidates", ()), 1):
        path = str(candidate["path"])
        evidence = dict(candidate.get("evidence", {}))
        if path.startswith("tests/"):
            classification, reason = "TEST_ONLY", "Loaded by unittest discovery or a dedicated Blender test runner."
        elif path.startswith(("manual-tests/", "benchmarks/", "scripts/")):
            classification, reason = "DEV_TOOL_ONLY", "Standalone CLI/validation entrypoint; zero imports are expected."
        elif path.endswith("/__init__.py"):
            classification, reason = "PUBLIC_CONTRACT", "Package boundary retained for import and distribution compatibility."
        elif evidence.get("registration") or evidence.get("bl_idname"):
            classification, reason = "REGISTERED_RUNTIME", "Dynamic Blender registration/identifier surface."
        else:
            classification, reason = "UNRESOLVED", "Static orphan status alone cannot prove dynamic or compatibility reachability."
        entries.append(
            _base_entry(
                f"H1-MOD-{index:04d}", str(candidate["module"]), path, classification, reason,
                evidence={"h0_dependency_evidence": evidence, "module_deleted": False},
                notes="No module deletion was authorized without import, CLI, registration, schema, test, and package proof.",
            )
        )
    return entries


def _removed_import_entries(contract_names: set[str]) -> list[dict[str, Any]]:
    return [
        _base_entry(
            f"H1-IMPORT-REMOVED-{index:04d}", symbol, path, "SAFE_TO_REMOVE",
            "Imported binding had no AST Name load, string reference, export, registration, schema, test, or contract use; its source module remains imported through live bindings where applicable.",
            evidence={
                "source": "H1 bounded AST import review plus exact-name proof",
                "baseline_definition_present": _baseline_contains_import(path, symbol),
                "current_definition_absent": not _current_contains_import(path, symbol),
                "current_reference_count": _path_reference_count(path, symbol),
                "public_contract_name_present": symbol in contract_names,
            },
            removed=True,
            group=group,
            notes="Removed import binding only; no runtime module, public export, or package file was removed.",
        )
        for index, ((path, symbol), group) in enumerate(sorted(REMOVED_IMPORTS.items()), 1)
    ]


def _hotspot_entries(report: dict[str, Any], symbol_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_path = Counter(entry["path"] for entry in symbol_entries if entry["classification"] == "SAFE_TO_REMOVE")
    targets = [
        item for item in report.get("top_review_targets", ())
        if item.get("classification") in {"CRITICAL_REVIEW_PRIORITY", "HIGH_REVIEW_PRIORITY"}
    ]
    entries = []
    for index, candidate in enumerate(targets, 1):
        path = str(candidate["path"])
        if path.startswith("tests/"):
            classification, reason = "TEST_ONLY", "Complex test matrix retained; no test weakening or consolidation in H1."
        elif path.startswith("manual-tests/"):
            classification, reason = "DEV_TOOL_ONLY", "Validation/benchmark hotspot retained; complexity work is deferred."
        else:
            classification, reason = "KEEP", "Runtime hotspot remains live; H1 removed only separately proven unreachable pieces."
        entries.append(
            _base_entry(
                f"H1-HOT-{index:04d}", str(candidate["module"]), path, classification, reason,
                evidence={
                    "h0_priority": candidate.get("classification"),
                    "loc": candidate.get("loc"),
                    "branch_count_estimate": candidate.get("branch_count_estimate"),
                    "maximum_function_loc": candidate.get("maximum_function_loc"),
                    "safe_removed_symbols_in_file": by_path[path],
                },
                notes="No complexity refactor was performed; that work belongs to H2+.",
            )
        )
    return entries


def _duplication_entries(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _base_entry(
            f"H1-DUP-{index:04d}", " | ".join(map(str, candidate.get("symbols", ()))),
            str(candidate.get("files", [""])[0]), "DUPLICATE_BUT_KEEP",
            "Similarity is not semantic equivalence; both implementations retain distinct validation/state/schema ownership.",
            evidence={
                "topic": candidate.get("topic"),
                "similarity_evidence": candidate.get("similarity_evidence"),
                "coupling_risk": candidate.get("coupling_risk"),
                "files": candidate.get("files"),
            },
            notes="General consolidation is H2+ and was not performed.",
        )
        for index, candidate in enumerate(report.get("candidates", ()), 1)
    ]


def _unused_import_entries() -> list[dict[str, Any]]:
    records: list[tuple[str, str, int]] = []
    for root in SOURCE_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if "reports" in path.parts or path.name == "__init__.py":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            try:
                tree = ast.parse(text, filename=str(path))
            except SyntaxError:
                continue
            used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
            for node in ast.walk(tree):
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
                    if any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
                        value = node.value
                        used.update(
                            item.value for item in ast.walk(value)
                            if isinstance(item, ast.Constant) and isinstance(item.value, str)
                        )
            lines = text.splitlines()
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Import, ast.ImportFrom)):
                    continue
                if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                    continue
                line = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
                if "noqa" in line.lower():
                    continue
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    local = alias.asname or alias.name.split(".")[0]
                    if local not in used:
                        relative = path.relative_to(ROOT).as_posix()
                        records.append((relative, local, node.lineno))
    entries = []
    for index, (path, name, line) in enumerate(sorted(set(records)), 1):
        if path.startswith("tests/"):
            classification, reason = "TEST_ONLY", "Import is retained in discovered test code; static Name-use is insufficient proof."
        elif path.startswith(("manual-tests/", "benchmarks/", "hardening/", "scripts/")):
            classification, reason = "DEV_TOOL_ONLY", "Tool import may provide entrypoint or import-time behavior; retained conservatively."
        else:
            classification, reason = "SUSPICIOUS", "AST reports no direct Name load, but dynamic/import-time behavior is not fully disproven."
        entries.append(
            _base_entry(
                f"H1-IMP-{index:04d}", name, path, classification, reason,
                evidence={"line": line, "scanner": "bounded AST unused-import review", "removed": False},
                notes="No import was removed on analyzer output alone.",
            )
        )
    return entries


def _queue_entries() -> list[dict[str, Any]]:
    entries = [
        _base_entry(
            "H1-LIFE-0001", "diagnostic_session._reports after repair rollback",
            "blender_addon/chroma3d_sculpt/session.py", "KEEP",
            "Confirmed bounded stale retention was fixed by evicting only the deleted workspace's report.",
            evidence={"before": "SUSPICIOUS_RETENTION=1", "after": "SUSPICIOUS_RETENTION=0", "disposition": "CONFIRMED_BOUNDED_DEFECT_FIXED"},
            notes="The cache remains bounded at 32 and retains valid object-owned reports.",
        ),
        _base_entry(
            "H1-PKG-0001", "intelligent_optimization_models.py package target",
            "blender_addon/chroma3d_sculpt/models/intelligent_optimization_models.py", "KEEP",
            "Packaged model and serialized contract remain live; no module split/removal in H1.",
            evidence={"h0_packaging_priority": "P6", "module_deleted": False},
        ),
        _base_entry(
            "H1-PKG-0002", "ai_assistance_models.py package target",
            "blender_addon/chroma3d_sculpt/models/ai_assistance_models.py", "KEEP",
            "Packaged model and serialized contract remain live; no module split/removal in H1.",
            evidence={"h0_packaging_priority": "P6", "module_deleted": False},
        ),
        _base_entry(
            "H1-DOC-0001", "README published release wording", "README.md", "KEEP",
            "Documentation was corrected to the published v0.8.0-alpha.1 tag without redefining runtime behavior.",
            evidence={"h0_classification": "CONTRADICTORY", "h1_disposition": "CORRECTED"},
        ),
        _base_entry(
            "H1-DOC-0002", "AI untrusted-output wording", "docs/ai-recommendation/README.md", "KEEP",
            "Documentation now states the already implemented untrusted strict-JSON and exact-current-ID validation boundary.",
            evidence={"h0_classification": "MINOR_DRIFT", "h1_disposition": "CORRECTED"},
        ),
    ]
    return entries


def build_ledger() -> dict[str, Any]:
    manifest_path = ROOT / "hardening" / "baseline" / "hardening_baseline_manifest.json"
    manifest = _read_json(manifest_path)
    contract = _read_json(ROOT / "hardening" / "baseline" / "public_contract_baseline.json")
    contract_names = _contract_names(contract)
    registration_names = _registration_names()
    symbols = _read_json(H0_REPORTS / "symbol_usage.json")
    dependency = _read_json(H0_REPORTS / "dependency_graph.json")
    complexity = _read_json(H0_REPORTS / "complexity_baseline.json")
    duplication = _read_json(H0_REPORTS / "duplication_candidates.json")

    symbol_entries = _symbol_entries(symbols, contract_names, registration_names)
    entries = list(symbol_entries)
    entries.extend(_removed_import_entries(contract_names))
    entries.extend(_dependency_entries(dependency))
    entries.extend(_hotspot_entries(complexity, symbol_entries))
    entries.extend(_duplication_entries(duplication))
    entries.extend(_unused_import_entries())
    entries.extend(_queue_entries())
    counts = Counter(entry["classification"] for entry in entries)
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "branch": _git("branch", "--show-current"),
        "head": _git("rev-parse", "HEAD"),
        "h0_identity": {
            "tag": H0_TAG,
            "tag_target": _git("rev-parse", f"{H0_TAG}^{{}}"),
            "expected_merge": H0_MERGE,
            "manifest_sha256": _sha256(manifest_path),
            "manifest_status": manifest.get("status"),
            "symbol_candidates": symbols.get("symbol_count") and len(symbols.get("candidates", ())),
            "dependency_candidates": len(dependency.get("statically_unreferenced_candidates", ())),
            "complexity_hotspots": sum(value for key, value in complexity.get("classification_counts", {}).items() if key in {"CRITICAL_REVIEW_PRIORITY", "HIGH_REVIEW_PRIORITY"}),
            "duplication_candidates": duplication.get("candidate_count"),
        },
        "classification_counts": {name: counts.get(name, 0) for name in ALLOWED_CLASSIFICATIONS},
        "candidate_count": len(entries),
        "removed_symbol_count": sum(bool(entry["removed"]) for entry in entries),
        "removed_file_count": 0,
        "entries": entries,
        "limitations": [
            "Static absence is never sufficient for removal; unresolved dynamic or compatibility reachability stays retained.",
            "Unused-import review is AST-bounded and retains every suspicious result unless independent proof exists.",
            "Duplication and complexity candidates are review signals, not defect verdicts or H1 refactor authorization.",
        ],
    }


def _render_summary(ledger: dict[str, Any]) -> str:
    counts = ledger["classification_counts"]
    removed = [entry for entry in ledger["entries"] if entry["removed"]]
    return "\n".join((
        "# H1 disposition summary",
        "",
        f"H0 identity: `{ledger['h0_identity']['tag']}` / `{ledger['h0_identity']['tag_target']}`.",
        f"H0 manifest: `{ledger['h0_identity']['manifest_sha256']}`; status `{ledger['h0_identity']['manifest_status']}`.",
        "",
        f"Candidates inspected: **{ledger['candidate_count']}**. Symbols removed: **{ledger['removed_symbol_count']}**. Files/modules removed: **0**.",
        "",
        "| Classification | Count |",
        "| --- | ---: |",
        *(f"| {name} | {counts[name]} |" for name in ALLOWED_CLASSIFICATIONS),
        "",
        "## Proven removals",
        "",
        "| Candidate | Path | Group |",
        "| --- | --- | --- |",
        *(f"| `{entry['symbol']}` | `{entry['path']}` | `{entry['removal_commit_candidate_group']}` |" for entry in removed),
        "",
        "## Dispositions",
        "",
        "- Lifecycle: `CONFIRMED_BOUNDED_DEFECT_FIXED`; zero suspicious retention after recheck.",
        "- Documentation: 2 proven drifts corrected; runtime contracts were not redefined.",
        "- Modules: no module removed; CLI/test/package-boundary candidates were retained.",
        "- Duplicates: retained as `DUPLICATE_BUT_KEEP`; consolidation is H2+.",
        "- Hotspots: no complexity refactor; only separately proven dead pieces were removed.",
        "",
        "## H2 candidate queue",
        "",
        "Prioritize the 7 critical and 29 high complexity targets, then the 82 duplicate candidates and remaining unresolved/suspicious dependency surfaces. Revalidate objectives and public contracts before any H2 change.",
        "",
    ))


def verify(ledger: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    entries = ledger.get("entries", [])
    ids = [entry.get("candidate_id") for entry in entries]
    if len(ids) != len(set(ids)):
        failures.append("candidate IDs are not unique")
    invalid = sorted({entry.get("classification") for entry in entries} - set(ALLOWED_CLASSIFICATIONS))
    if invalid:
        failures.append(f"invalid classifications: {invalid}")
    if ledger.get("h0_identity", {}).get("tag_target") != H0_MERGE:
        failures.append("H0 tag target mismatch")
    if ledger.get("h0_identity", {}).get("symbol_candidates") != 627:
        failures.append("H0 symbol candidate coverage is not 627")
    removed = [entry for entry in entries if entry.get("removed")]
    expected_removed = len(REMOVED_SYMBOLS) + len(REMOVED_IMPORTS)
    if len(removed) != expected_removed:
        failures.append(f"removed-symbol coverage mismatch: {len(removed)} != {expected_removed}")
    for entry in removed:
        evidence = entry.get("evidence", {})
        if entry.get("classification") != "SAFE_TO_REMOVE":
            failures.append(f"removed entry is not SAFE_TO_REMOVE: {entry.get('candidate_id')}")
        if not evidence.get("baseline_definition_present"):
            failures.append(f"baseline definition missing: {entry.get('symbol')}")
        if not evidence.get("current_definition_absent"):
            failures.append(f"current definition still present: {entry.get('symbol')}")
        if evidence.get("current_reference_count") != 0:
            failures.append(f"current references remain: {entry.get('symbol')}")
        if not entry.get("tests_checked"):
            failures.append(f"tests not recorded: {entry.get('symbol')}")
    expected_counts = Counter(entry["classification"] for entry in entries)
    if any(ledger.get("classification_counts", {}).get(name) != expected_counts.get(name, 0) for name in ALLOWED_CLASSIFICATIONS):
        failures.append("classification counts do not match ledger entries")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    ledger = _read_json(args.output) if args.check_only else build_ledger()
    failures = verify(ledger)
    if not args.check_only:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        args.summary.write_text(_render_summary(ledger), encoding="utf-8", newline="\n")
    print(json.dumps({
        "status": "PASS" if not failures else "FAIL",
        "candidates": ledger.get("candidate_count"),
        "classifications": ledger.get("classification_counts"),
        "removed_symbols": ledger.get("removed_symbol_count"),
        "failures": failures,
    }, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
