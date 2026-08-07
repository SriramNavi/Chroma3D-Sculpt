"""Find lightweight structural duplication candidates without asserting equivalence."""

from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from difflib import SequenceMatcher
import hashlib
from pathlib import Path
import re
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


TOPICS = {
    "hashing_or_signature": ("hash", "signature", "fingerprint", "digest"),
    "atomic_or_report_write": ("atomic", "write_json", "write_markdown", "write_report", "serialize", "export"),
    "filename_sanitization": ("sanitize", "filename", "safe_name"),
    "json_or_profile_validation": ("validate", "schema", "profile"),
    "path_validation": ("path", "extension", "allowlist", "allow_list"),
    "blender_state_cleanup": ("cleanup", "clear_runtime", "discard", "restore"),
    "registration": ("register", "unregister"),
    "timeout_or_process": ("timeout", "process", "subprocess", "worker"),
    "evidence_state": ("evidence", "status", "state", "result"),
    "package_version": ("version", "manifest", "package"),
}


def _normal_form(node: ast.AST) -> str:
    clone = ast.parse(ast.unparse(node)).body[0]
    if isinstance(clone, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        clone.name = "_"
    for item in ast.walk(clone):
        if isinstance(item, ast.Constant) and isinstance(item.value, str):
            item.value = "<str>"
    return ast.dump(clone, annotate_fields=False, include_attributes=False)


def _normalized_text(lines: list[str], node: ast.AST) -> str:
    start = max(0, int(getattr(node, "lineno", 1)) - 1)
    end = int(getattr(node, "end_lineno", start + 1))
    value = "\n".join(lines[start:end]).lower()
    value = re.sub(r"\b[a-z_][a-z0-9_]*\b", "n", value)
    value = re.sub(r"\s+", " ", value)
    return value


def _topic(name: str, source: str) -> str | None:
    haystack = f"{name.lower()} {source.lower()}"
    matches = [topic for topic, tokens in TOPICS.items() if any(token in haystack for token in tokens)]
    return matches[0] if matches else None


def _phase(topic: str) -> str:
    return {
        "registration": "H2",
        "blender_state_cleanup": "H3",
        "evidence_state": "H4",
        "timeout_or_process": "H5",
        "package_version": "H6",
    }.get(topic, "H1")


def analyze() -> dict[str, object]:
    functions: list[dict[str, object]] = []
    parse_errors: list[dict[str, str]] = []
    for path in checkpoint_python_paths():
        rel = relative(path)
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        try:
            tree = parse_python(path)
        except SyntaxError as exc:
            parse_errors.append({"path": rel, "error": str(exc)})
            continue
        parents: dict[ast.AST, str] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                if isinstance(parent, ast.ClassDef):
                    parents[child] = parent.name
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            loc = int(getattr(node, "end_lineno", node.lineno)) - node.lineno + 1
            if loc < 5:
                continue
            qualified = f"{parents[node]}.{node.name}" if node in parents else node.name
            normalized = _normal_form(node)
            source = _normalized_text(lines, node)
            functions.append({
                "file": rel,
                "symbol": qualified,
                "line": node.lineno,
                "loc": loc,
                "structural_hash": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
                "normalized_text": source,
                "topic": _topic(node.name, source),
            })

    candidates: list[dict[str, object]] = []
    exact: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in functions:
        exact[str(item["structural_hash"])].append(item)
    seen_pairs: set[tuple[str, str, str, str]] = set()
    for group in exact.values():
        files = {str(item["file"]) for item in group}
        if len(group) < 2 or len(files) < 2:
            continue
        selected = sorted(group, key=lambda item: (str(item["file"]), str(item["symbol"])))[:8]
        topic = str(next((item["topic"] for item in selected if item["topic"]), "structural_pattern"))
        candidates.append({
            "files": sorted({str(item["file"]) for item in selected}),
            "symbols": [f"{item['file']}:{item['symbol']}" for item in selected],
            "similarity_evidence": {"kind": "AST_STRUCTURAL_HASH", "score": 1.0, "hash": selected[0]["structural_hash"]},
            "semantic_differences": "String literals and definition names were normalized; preconditions, side effects, ownership, and schema meaning still require manual comparison.",
            "coupling_risk": "HIGH" if topic in {"blender_state_cleanup", "evidence_state", "registration"} else "MODERATE",
            "topic": topic,
            "recommended_phase": _phase(topic),
        })
        for left in selected:
            for right in selected:
                seen_pairs.add((str(left["file"]), str(left["symbol"]), str(right["file"]), str(right["symbol"])))

    by_topic: dict[str, list[dict[str, object]]] = defaultdict(list)
    for item in functions:
        if item["topic"]:
            by_topic[str(item["topic"])].append(item)
    for topic, group in sorted(by_topic.items()):
        limited = sorted(group, key=lambda item: (-int(item["loc"]), str(item["file"]), str(item["symbol"])))[:80]
        for index, left in enumerate(limited):
            for right in limited[index + 1:]:
                if left["file"] == right["file"]:
                    continue
                key = (str(left["file"]), str(left["symbol"]), str(right["file"]), str(right["symbol"]))
                reverse = (key[2], key[3], key[0], key[1])
                if key in seen_pairs or reverse in seen_pairs:
                    continue
                score = SequenceMatcher(None, str(left["normalized_text"]), str(right["normalized_text"]), autojunk=True).ratio()
                if score < 0.72:
                    continue
                candidates.append({
                    "files": [left["file"], right["file"]],
                    "symbols": [f"{left['file']}:{left['symbol']}", f"{right['file']}:{right['symbol']}"],
                    "similarity_evidence": {"kind": "NORMALIZED_TEXT", "score": round(score, 4)},
                    "semantic_differences": "Similar text is not semantic equivalence; compare validation rules, state ownership, failure behavior, and serialized contracts.",
                    "coupling_risk": "HIGH" if topic in {"blender_state_cleanup", "evidence_state", "registration"} else "MODERATE",
                    "topic": topic,
                    "recommended_phase": _phase(topic),
                })
                seen_pairs.add(key)
    candidates.sort(key=lambda item: (-float(item["similarity_evidence"]["score"]), str(item["topic"]), str(item["symbols"])))
    return {
        "schema_version": "1.0.0",
        "generated_at": utc_now(),
        "checkpoint_tag": CHECKPOINT_TAG,
        "checkpoint_commit": CHECKPOINT_COMMIT,
        "functions_reviewed": len(functions),
        "candidate_count": len(candidates),
        "candidates": candidates[:200],
        "parse_errors": parse_errors,
        "limitations": [
            "Similarity is candidate evidence only and never proves semantic equivalence.",
            "Generated tests and intentionally parallel schema/report adapters can create expected similarity.",
            "No refactor or consolidation is authorized by this report.",
        ],
    }


def render(report: dict[str, object]) -> str:
    candidates = report["candidates"]
    assert isinstance(candidates, list)
    return "\n".join((
        "# Duplication Baseline",
        "",
        f"Checkpoint: `{report['checkpoint_tag']}` / `{report['checkpoint_commit']}`.",
        "",
        f"Reviewed `{report['functions_reviewed']}` functions and retained `{report['candidate_count']}` bounded candidates.",
        "",
        markdown_table(
            ("Topic", "Symbols", "Evidence", "Score", "Risk", "Phase"),
            ((item["topic"], "<br>".join(item["symbols"]), item["similarity_evidence"]["kind"], item["similarity_evidence"]["score"], item["coupling_risk"], item["recommended_phase"]) for item in candidates[:60]),
        ) if candidates else "No candidates met the retained similarity bounds.",
        "",
        "Text or AST similarity is not semantic equivalence. No utility consolidation or refactor occurs in H0.",
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPORT_ROOT / "duplication_candidates.json")
    parser.add_argument("--markdown", type=Path, default=BASELINE_ROOT / "DUPLICATION_BASELINE.md")
    args = parser.parse_args()
    report = analyze()
    write_json(args.output, report)
    write_text(args.markdown, render(report))
    print(f"duplication analysis: {report['candidate_count']} candidates")
    return 1 if report["parse_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
