"""Capture filesystem-write, security, and documentation-truth baselines."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import re
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    BASELINE_ROOT,
    CHECKPOINT_COMMIT,
    CHECKPOINT_TAG,
    REPOSITORY_ROOT,
    REPORT_ROOT,
    SOURCE_ROOT,
    checkpoint_python_paths,
    markdown_table,
    relative,
    utc_now,
    write_json,
    write_text,
)


WRITE_CALLS = {"write_text", "write_bytes", "write", "writelines", "dump", "open", "replace", "rename", "save_as_mainfile"}
DESTRUCTIVE_CALLS = {"unlink", "remove", "rmdir", "rmtree"}


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ast.unparse(node.func)


def _call_qualified_name(node: ast.Call) -> str:
    return ast.unparse(node.func)


def _is_filesystem_write(node: ast.Call) -> bool:
    call = _call_name(node)
    if call not in WRITE_CALLS:
        return False
    if call == "open":
        mode = None
        if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
            mode = node.args[1].value
        for keyword in node.keywords:
            if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
                mode = keyword.value.value
        return isinstance(mode, str) and any(flag in mode for flag in "wax+")
    if call == "replace":
        if not isinstance(node.func, ast.Attribute):
            return False
        receiver = ast.unparse(node.func.value).lower()
        return receiver in {"os", "pathlib"} or any(token in receiver for token in ("temporary", "temp_path", "tmp_path"))
    return True


def _artifact_kind(path: str, function: str, context: str) -> str:
    value = f"{path} {function} {context}".lower()
    if "audit" in value:
        return "AUDIT"
    if "markdown" in value or ".md" in value:
        return "MARKDOWN"
    if "json" in value:
        return "JSON"
    if "report" in value:
        return "REPORT"
    if "temporary" in value or "tempfile" in value or ".tmp" in value:
        return "TEMPORARY"
    if "cache" in value or "history" in value:
        return "CACHE_OR_HISTORY"
    if "export" in value:
        return "EXPORTED_EVIDENCE"
    return "OTHER"


def _enclosing_functions(tree: ast.AST) -> dict[ast.AST, ast.FunctionDef | ast.AsyncFunctionDef | None]:
    result: dict[ast.AST, ast.FunctionDef | ast.AsyncFunctionDef | None] = {}

    def visit(node: ast.AST, current: ast.FunctionDef | ast.AsyncFunctionDef | None = None) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            current = node
        result[node] = current
        for child in ast.iter_child_nodes(node):
            visit(child, current)

    visit(tree)
    return result


def filesystem_baseline() -> dict[str, object]:
    surfaces = []
    parse_errors = []
    for path in checkpoint_python_paths():
        rel = relative(path)
        source = path.read_text(encoding="utf-8", errors="replace")
        lines = source.splitlines()
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError as exc:
            parse_errors.append({"path": rel, "error": str(exc)})
            continue
        parents = _enclosing_functions(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call = _call_name(node)
            if not _is_filesystem_write(node):
                continue
            function = parents[node]
            start = max(0, (function.lineno if function else node.lineno) - 1)
            end = int(getattr(function, "end_lineno", node.lineno)) if function else node.lineno
            context = "\n".join(lines[start:end]).lower()
            function_name = function.name if function else "<module>"
            surfaces.append({
                "path": rel,
                "line": node.lineno,
                "function": function_name,
                "call": call,
                "artifact_kind": _artifact_kind(rel, function_name, context),
                "scope": "RUNTIME" if rel.startswith("blender_addon/chroma3d_sculpt/") else "DEVELOPMENT_OR_TEST",
                "path_validation": any(token in context for token in ("resolve(", "is_relative_to", "relative_to(", "validate_path", "safe_path")),
                "atomic_write_support": "replace(" in context and (".tmp" in context or "temporary" in context),
                "extension_allowlist": any(token in context for token in ("allowed_extension", "allowlist", "allow_list", "suffix not in", "suffix in")),
                "filename_sanitization": "sanitize" in context or "safe_name" in context,
                "overwrite_behavior": "ATOMIC_REPLACE" if "replace(" in context else "DIRECT_OR_LIBRARY_DEFINED",
                "cleanup_behavior": "EXPLICIT" if any(token + "(" in context for token in DESTRUCTIVE_CALLS) or "temporarydirectory" in context else "NOT_EVIDENT_LOCALLY",
            })
    runtime_surfaces = [item for item in surfaces if item["scope"] == "RUNTIME"]
    safeguards = {
        "path_validation_evident": sum(bool(item["path_validation"]) for item in runtime_surfaces),
        "atomic_write_evident": sum(bool(item["atomic_write_support"]) for item in runtime_surfaces),
        "extension_allowlist_evident": sum(bool(item["extension_allowlist"]) for item in runtime_surfaces),
        "filename_sanitization_evident": sum(bool(item["filename_sanitization"]) for item in runtime_surfaces),
        "explicit_cleanup_evident": sum(item["cleanup_behavior"] == "EXPLICIT" for item in runtime_surfaces),
    }
    return {
        "schema_version": "1.0.0",
        "generated_at": utc_now(),
        "checkpoint_tag": CHECKPOINT_TAG,
        "checkpoint_commit": CHECKPOINT_COMMIT,
        "write_surface_count": len(surfaces),
        "status": "PASS_WITH_FINDINGS" if runtime_surfaces else "PASS",
        "runtime_write_surface_count": len(runtime_surfaces),
        "runtime_artifact_kind_counts": dict(sorted(Counter(item["artifact_kind"] for item in runtime_surfaces).items())),
        "runtime_safeguard_counts": safeguards,
        "surfaces": sorted(surfaces, key=lambda item: (str(item["path"]), int(item["line"]))),
        "parse_errors": parse_errors,
        "limitations": ["Static call-site evidence does not prove all runtime destinations or overwrite outcomes."],
    }


def security_baseline(filesystem: dict[str, object]) -> dict[str, object]:
    hits = []
    prohibited = []
    absolute_path = re.compile(r"(?:^|\s)([A-Za-z]:[\\/][A-Za-z0-9])")
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        rel = relative(path)
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call = _call_name(node)
                qualified_call = _call_qualified_name(node)
                if call in {"eval", "exec", "__import__"} or (call == "compile" and isinstance(node.func, ast.Name)):
                    item = {"path": rel, "line": node.lineno, "category": "dynamic_execution", "evidence": call, "classification": "PROHIBITED_RUNTIME"}
                    hits.append(item); prohibited.append(item)
                if qualified_call in {"os.system", "os.popen", "subprocess.Popen", "subprocess.run", "subprocess.call", "subprocess.check_call", "subprocess.check_output"}:
                    item = {"path": rel, "line": node.lineno, "category": "process_or_shell", "evidence": qualified_call, "classification": "PROHIBITED_RUNTIME"}
                    hits.append(item); prohibited.append(item)
                for keyword in node.keywords:
                    if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                        item = {"path": rel, "line": node.lineno, "category": "shell_true", "evidence": "shell=True", "classification": "PROHIBITED_RUNTIME"}
                        hits.append(item); prohibited.append(item)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                imported = ast.unparse(node)
                if any(token in imported for token in ("pickle", "yaml", "subprocess", "urllib.request", "requests", "socket")):
                    item = {"path": rel, "line": node.lineno, "category": "sensitive_import", "evidence": imported, "classification": "PROHIBITED_RUNTIME"}
                    hits.append(item); prohibited.append(item)
                elif "http.client" in imported or imported == "import ssl":
                    classification = "EXPECTED_RESTRICTED_PROVIDER_PATH" if rel.endswith("services/provider_transport.py") else "REVIEW_CANDIDATE"
                    item = {"path": rel, "line": node.lineno, "category": "network_boundary", "evidence": imported, "classification": classification}
                    hits.append(item)
                    if classification == "REVIEW_CANDIDATE":
                        prohibited.append(item)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and absolute_path.search(node.value):
                item = {"path": rel, "line": node.lineno, "category": "developer_absolute_path", "evidence": node.value[:160], "classification": "PROHIBITED_RUNTIME"}
                hits.append(item); prohibited.append(item)
        for line_number, line in enumerate(source.splitlines(), 1):
            if re.search(r"(authorization|api[_-]?key|credential).*(logger\.|print\()", line, re.IGNORECASE):
                item = {"path": rel, "line": line_number, "category": "credential_logging_candidate", "evidence": line.strip()[:160], "classification": "REVIEW_CANDIDATE"}
                hits.append(item)

    transport = (SOURCE_ROOT / "services" / "provider_transport.py").read_text(encoding="utf-8")
    provider = (SOURCE_ROOT / "services" / "openai_provider.py").read_text(encoding="utf-8")
    provider_boundary = {
        "host_allowlist_present": 'frozenset({"api.openai.com"})' in transport,
        "fixed_openai_path_present": 'OPENAI_PATH = "/v1/responses"' in provider,
        "runtime_network_modules": sorted({item["path"] for item in hits if item["category"] == "network_boundary"}),
    }
    secret_like_tracked = [
        name for name in __import__("subprocess").run(
            ["git", "ls-files"], cwd=REPOSITORY_ROOT, capture_output=True, text=True, encoding="utf-8", check=False
        ).stdout.splitlines()
        if name.lower().endswith((".env", ".pem", ".p12", ".pfx", ".key", ".pyc")) or "__pycache__" in name.lower().split("/")
    ]
    if not provider_boundary["host_allowlist_present"] or not provider_boundary["fixed_openai_path_present"]:
        prohibited.append({"category": "provider_boundary", "classification": "PROHIBITED_RUNTIME"})
    return {
        "schema_version": "1.0.0",
        "generated_at": utc_now(),
        "checkpoint_tag": CHECKPOINT_TAG,
        "checkpoint_commit": CHECKPOINT_COMMIT,
        "runtime_files_scanned": len(list(SOURCE_ROOT.rglob("*.py"))),
        "hits": hits,
        "classification_counts": dict(sorted(Counter(item["classification"] for item in hits).items())),
        "prohibited_runtime_findings": prohibited,
        "provider_boundary": provider_boundary,
        "tracked_secret_or_bytecode_files": secret_like_tracked,
        "runtime_write_surfaces_for_review": [item for item in filesystem["surfaces"] if item["scope"] == "RUNTIME"],
        "credential_persistence_evidence": "No credential file or serialized credential field established by this static scan.",
        "temporary_profile_leakage": "INCONCLUSIVE_STATIC",
        "status": "PASS" if not prohibited and not secret_like_tracked else "FAIL",
        "limitations": ["Local static baseline only; no live-provider penetration test or external certification."],
    }


def documentation_baseline() -> dict[str, object]:
    requirements = {
        "README.md": ("0.8.0-alpha.1", "AI Recommendation Foundation"),
        "ARCHITECTURE.md": ("AI", "provider"),
        "ROADMAP.md": ("Sprint 7", "AI"),
        "TECHNICAL_ROADMAP.md": ("Sprint 7", "AI"),
        "PRODUCT_REQUIREMENTS.md": ("AI",),
        "REPAIR_SAFETY.md": ("checkpoint", "protected"),
        "PROJECT_RULES.md": ("Sprint 7",),
        "AGENTS.md": ("Sprint 7",),
        "docs/printability/README.md": ("advisory",),
        "docs/advanced-preparation/README.md": ("advisory",),
        "docs/controlled-optimization/README.md": ("workspace",),
        "docs/intelligent-optimization/README.md": ("deterministic",),
        "docs/ai-recommendation/README.md": ("untrusted",),
        "docs/sprint7": ("",),
    }
    records = []
    for name, tokens in requirements.items():
        path = REPOSITORY_ROOT / name
        if not path.exists():
            records.append({"path": name, "classification": "MISSING", "evidence": "Required path is absent.", "recommended_h7_action": "Create or restore the missing contract documentation."})
            continue
        if path.is_dir():
            text = "\n".join(item.read_text(encoding="utf-8", errors="replace") for item in path.rglob("*.md"))
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
        lowered = text.lower()
        if name == "README.md" and "current published release:** `v0.7.0-alpha.1`" in lowered:
            classification = "CONTRADICTORY"
            evidence = "README identifies v0.7.0-alpha.1 as current published release while v0.8.0-alpha.1 is tagged and the pre-v1 checkpoint identifies it as current."
            action = "Align release-status wording with the published tag and checkpoint evidence."
        else:
            missing = [token for token in tokens if token and token.lower() not in lowered]
            if missing:
                classification = "MINOR_DRIFT" if len(missing) == 1 else "STALE"
                evidence = "Expected current contract terms not found: " + ", ".join(missing)
                action = "Review against current Sprint 7 implementation and update in H7 only."
            else:
                classification = "CURRENT"
                evidence = "Required current-scope terms are present."
                action = "KEEP"
        records.append({"path": name, "classification": classification, "evidence": evidence, "recommended_h7_action": action})
    counts = Counter(item["classification"] for item in records)
    return {
        "schema_version": "1.0.0",
        "generated_at": utc_now(),
        "checkpoint_tag": CHECKPOINT_TAG,
        "checkpoint_commit": CHECKPOINT_COMMIT,
        "classification_counts": dict(sorted(counts.items())),
        "documents": records,
        "limitations": ["Keyword-backed truth checks identify review targets; semantic document review remains an H7 task."],
    }


def render_filesystem(report: dict[str, object]) -> str:
    return "\n".join((
        "# Filesystem Write Baseline", "",
        f"Checkpoint: `{report['checkpoint_tag']}` / `{report['checkpoint_commit']}`.", "",
        markdown_table(("Metric", "Value"), (("Write call sites", report["write_surface_count"]), ("Runtime write call sites", report["runtime_write_surface_count"]))), "",
        markdown_table(("Artifact kind", "Count"), report["runtime_artifact_kind_counts"].items()), "",
        markdown_table(("Safeguard", "Call sites with local evidence"), report["runtime_safeguard_counts"].items()), "",
        markdown_table(("Path", "Line", "Function", "Call", "Kind", "Validation", "Atomic", "Extension", "Sanitize", "Cleanup"), ((item["path"], item["line"], item["function"], item["call"], item["artifact_kind"], item["path_validation"], item["atomic_write_support"], item["extension_allowlist"], item["filename_sanitization"], item["cleanup_behavior"]) for item in report["surfaces"] if item["scope"] == "RUNTIME")), "",
        "This is static call-site evidence only; H1-H9 must preserve path, extension, overwrite, atomicity, and cleanup contracts when changing a write surface.",
    ))


def render_security(report: dict[str, object]) -> str:
    return "\n".join((
        "# Security Baseline", "",
        f"Status: `{report['status']}` at checkpoint `{report['checkpoint_tag']}`.", "",
        markdown_table(("Classification", "Count"), report["classification_counts"].items()), "",
        markdown_table(("Path", "Line", "Category", "Classification", "Evidence"), ((item.get("path", ""), item.get("line", ""), item["category"], item["classification"], item.get("evidence", "")) for item in report["hits"])), "",
        "The explicit provider adapter is classified separately from unbounded network behavior. This is a local static baseline, not live-provider security qualification.",
    ))


def render_docs(report: dict[str, object]) -> str:
    return "\n".join((
        "# Documentation Drift", "",
        f"Checkpoint: `{report['checkpoint_tag']}` / `{report['checkpoint_commit']}`.", "",
        markdown_table(("Classification", "Count"), report["classification_counts"].items()), "",
        markdown_table(("Path", "Classification", "Evidence", "Recommended H7 action"), ((item["path"], item["classification"], item["evidence"], item["recommended_h7_action"]) for item in report["documents"])), "",
        "No documentation was rewritten in H0; changes are queued for H7 review only.",
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, default=REPORT_ROOT)
    args = parser.parse_args()
    filesystem = filesystem_baseline()
    security = security_baseline(filesystem)
    docs = documentation_baseline()
    write_json(args.report_dir / "filesystem_write_baseline.json", filesystem)
    write_json(args.report_dir / "security_baseline.json", security)
    write_json(args.report_dir / "documentation_drift.json", docs)
    write_text(BASELINE_ROOT / "FILESYSTEM_WRITE_BASELINE.md", render_filesystem(filesystem))
    write_text(BASELINE_ROOT / "SECURITY_BASELINE.md", render_security(security))
    write_text(BASELINE_ROOT / "DOCUMENTATION_DRIFT.md", render_docs(docs))
    print(json.dumps({"filesystem_writes": filesystem["write_surface_count"], "security": security["status"], "documentation": docs["classification_counts"]}, sort_keys=True))
    return 0 if security["status"] == "PASS" and not filesystem["parse_errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
