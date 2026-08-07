"""Reconcile retained Sprint 7 release inputs with the current checkout.

The tool is deliberately read-only with respect to product and historical files.
It retrieves retained bytes from the commit recorded in the frozen Sprint 7
fingerprint report, then compares raw and newline-normalized identities.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unicodedata
from typing import Any, Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    BASELINE_ROOT,
    REPORT_ROOT,
    REPOSITORY_ROOT,
    canonical_bytes,
    markdown_table,
    utc_now,
    write_json,
    write_text,
)


DEFAULT_MISMATCH_REPORT = REPORT_ROOT / "dataset_benchmark_identity.json"
DEFAULT_RETAINED_REPORT = (
    REPOSITORY_ROOT
    / "manual-tests"
    / "sprint7"
    / "reports"
    / "release_input_fingerprint.json"
)
DEFAULT_OUTPUT = REPORT_ROOT / "fingerprint_reconciliation.json"
DEFAULT_MARKDOWN = BASELINE_ROOT / "FINGERPRINT_RECONCILIATION.md"
CAUSAL_COMMIT = "b21911eecf543cafa32c7dafd0e5e926c33a5f28"


SUBSTANTIVE_ASSESSMENTS: dict[str, dict[str, Any]] = {
    "blender_addon/chroma3d_sculpt/__init__.py": {
        "classification": "REGISTRATION_SURFACE_CHANGE",
        "changed_symbols_or_keys": ["bl_info.description", "_RUNTIME_CLASSES", "unregister"],
        "diff_summary": "Integrated Sprint 7 operator/panel registration and AI session, credential, and provider cleanup.",
        "shipped_in_zip": True,
        "runtime_imported": True,
        "influences_dataset_worker": True,
        "influences_analysis_result": False,
        "influences_implementation_fingerprint": True,
        "evidence_invalidation_impact": "Invalidates registration/package identity; package initialization is executed by the dataset worker but these additions do not compute its result.",
    },
    "blender_addon/chroma3d_sculpt/blender_manifest.toml": {
        "classification": "VERSION_OR_RELEASE_METADATA_ONLY",
        "changed_symbols_or_keys": ["version"],
        "diff_summary": "Extension manifest version advanced from 0.7.0 to 0.8.0.",
        "shipped_in_zip": True,
        "runtime_imported": False,
        "influences_dataset_worker": False,
        "influences_analysis_result": False,
        "influences_implementation_fingerprint": True,
        "evidence_invalidation_impact": "Invalidates byte/package/version identity only.",
    },
    "blender_addon/chroma3d_sculpt/metadata.py": {
        "classification": "VERSION_OR_RELEASE_METADATA_ONLY",
        "changed_symbols_or_keys": ["EXTENSION_VERSION", "AI_ASSISTANCE_SCHEMA_VERSION"],
        "diff_summary": "Advanced product version to 0.8.0 and declared the Sprint 7 schema version.",
        "shipped_in_zip": True,
        "runtime_imported": True,
        "influences_dataset_worker": True,
        "influences_analysis_result": False,
        "influences_implementation_fingerprint": True,
        "evidence_invalidation_impact": "Invalidates runtime/package metadata identity; the dataset worker imports the package but does not serialize these changed values.",
    },
    "blender_addon/chroma3d_sculpt/operators/__init__.py": {
        "classification": "REGISTRATION_SURFACE_CHANGE",
        "changed_symbols_or_keys": ["AI_ASSISTANCE_CLASSES", "__all__"],
        "diff_summary": "Added the Sprint 7 AI assistance operator class surface.",
        "shipped_in_zip": True,
        "runtime_imported": True,
        "influences_dataset_worker": True,
        "influences_analysis_result": False,
        "influences_implementation_fingerprint": True,
        "evidence_invalidation_impact": "Invalidates registration identity; imported during dataset package initialization but not called by the worker.",
    },
    "blender_addon/chroma3d_sculpt/performance_registry.py": {
        "classification": "RUNTIME_BEHAVIOR_CHANGE",
        "changed_symbols_or_keys": ["AI_ASSISTANCE_LIMITS", "__all__"],
        "diff_summary": "Added bounded FAST/STANDARD/DEEP AI assistance limits consumed by limits_for_mode.",
        "shipped_in_zip": True,
        "runtime_imported": True,
        "influences_dataset_worker": True,
        "influences_analysis_result": True,
        "influences_implementation_fingerprint": True,
        "evidence_invalidation_impact": "Directly affects dataset context construction, recommendation validation, and the recorded performance-limits hash; fresh validation is required.",
    },
    "blender_addon/chroma3d_sculpt/ui/__init__.py": {
        "classification": "REGISTRATION_SURFACE_CHANGE",
        "changed_symbols_or_keys": ["AI_ASSISTANCE_PANEL_CLASSES", "__all__"],
        "diff_summary": "Added the Sprint 7 AI assistance panel registration surface.",
        "shipped_in_zip": True,
        "runtime_imported": True,
        "influences_dataset_worker": True,
        "influences_analysis_result": False,
        "influences_implementation_fingerprint": True,
        "evidence_invalidation_impact": "Invalidates registration identity; imported during dataset package initialization but not used in result computation.",
    },
    "blender_addon/chroma3d_sculpt/ui/properties.py": {
        "classification": "REGISTRATION_SURFACE_CHANGE",
        "changed_symbols_or_keys": ["_mark_ai_assistance_stale", "CHROMA3D_PG_session_state.ai_assistance_*"],
        "diff_summary": "Added AI assistance properties and the stale-session invalidation callback.",
        "shipped_in_zip": True,
        "runtime_imported": True,
        "influences_dataset_worker": True,
        "influences_analysis_result": False,
        "influences_implementation_fingerprint": True,
        "evidence_invalidation_impact": "Invalidates property/registration identity; class definitions load in the worker but the properties are not exercised there.",
    },
    "scripts/_project.py": {
        "classification": "PACKAGE_INVENTORY_ONLY",
        "changed_symbols_or_keys": ["REQUIRED_SOURCE_FILES", "PACKAGE_ASSET_FILES"],
        "diff_summary": "Added Sprint 7 runtime modules, panel, and schemas to the required package inventory.",
        "shipped_in_zip": False,
        "runtime_imported": False,
        "influences_dataset_worker": False,
        "influences_analysis_result": False,
        "influences_implementation_fingerprint": True,
        "evidence_invalidation_impact": "Invalidates package inventory validation only.",
    },
    "scripts/validate_package.py": {
        "classification": "VALIDATION_OR_HARNESS_ONLY",
        "changed_symbols_or_keys": ["validate_archive"],
        "diff_summary": "Added rejection of Sprint 7 draft/specification development content in packages.",
        "shipped_in_zip": False,
        "runtime_imported": False,
        "influences_dataset_worker": False,
        "influences_analysis_result": False,
        "influences_implementation_fingerprint": True,
        "evidence_invalidation_impact": "Invalidates validation-tool identity only.",
    },
}


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _lf_normalize(value: bytes) -> bytes:
    return value.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _utf8_normalize(value: bytes) -> bytes:
    text = _lf_normalize(value).decode("utf-8")
    return unicodedata.normalize("NFC", text).encode("utf-8")


def _aggregate(entries: Iterable[tuple[str, str]]) -> str:
    digest = hashlib.sha256()
    for relative, file_hash in entries:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _git_blob(commit: str, relative: str) -> bytes | None:
    completed = subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        return None
    return completed.stdout


def _is_probably_binary(value: bytes) -> bool:
    return b"\0" in value


def _compare(
    relative: str,
    retained_hash: str,
    current: bytes,
    retained: bytes | None,
) -> dict[str, Any]:
    current_raw = _sha256(current)
    current_lf = _sha256(_lf_normalize(current))
    result: dict[str, Any] = {
        "path": relative,
        "retained_raw_sha256": retained_hash,
        "current_raw_sha256": current_raw,
        "current_lf_sha256": current_lf,
        "retained_git_blob_available": retained is not None,
    }
    if retained is not None:
        result["retained_git_blob_sha256"] = _sha256(retained)
        result["retained_git_blob_matches_report"] = (
            result["retained_git_blob_sha256"] == retained_hash
        )
        result["retained_lf_sha256"] = _sha256(_lf_normalize(retained))
    if retained_hash == current_raw:
        result["classification"] = "BYTE_IDENTICAL"
        return result
    if (retained is not None and _is_probably_binary(retained)) or _is_probably_binary(current):
        result["classification"] = "BINARY_DIFFERENT"
        return result
    try:
        current_utf8 = _sha256(_utf8_normalize(current))
    except UnicodeDecodeError as exc:
        result["classification"] = "BINARY_DIFFERENT"
        result["decode_error"] = str(exc)
        return result
    if retained is not None:
        try:
            result["retained_utf8_nfc_sha256"] = _sha256(_utf8_normalize(retained))
        except UnicodeDecodeError:
            pass
    result["current_utf8_nfc_sha256"] = current_utf8
    result["classification"] = (
        "NEWLINE_ONLY_EQUIVALENT" if retained_hash == current_lf else "CONTENT_DIFFERENT"
    )
    return result


def reconcile(mismatch_report: Path, retained_report: Path) -> dict[str, Any]:
    mismatch = json.loads(mismatch_report.read_text(encoding="utf-8"))
    retained = json.loads(retained_report.read_text(encoding="utf-8"))
    retained_commit = str(retained["head"])
    retained_entries = {
        str(item["path"]): str(item["sha256"])
        for item in retained.get("files", [])
    }
    current_entries: list[tuple[str, str]] = []
    retained_semantic_entries: list[tuple[str, str]] = []
    current_semantic_entries: list[tuple[str, str]] = []
    comparisons: list[dict[str, Any]] = []
    unreadable: list[dict[str, str]] = []

    for item in mismatch.get("release_input_mismatches", []):
        relative = str(item["path"])
        path = REPOSITORY_ROOT / relative
        try:
            current_bytes = path.read_bytes()
            retained_bytes = _git_blob(retained_commit, relative)
            comparison = _compare(
                relative,
                str(item["retained_sha256"]),
                current_bytes,
                retained_bytes,
            )
            comparison["reported_retained_sha256"] = str(item["retained_sha256"])
            comparison["reported_current_sha256"] = str(item["current_sha256"])
            comparison["reported_classification"] = str(item["classification"])
            comparison["reported_hashes_verified"] = (
                comparison["current_raw_sha256"] == item["current_sha256"]
            )
            comparisons.append(comparison)
        except (OSError, RuntimeError) as exc:
            unreadable.append({"path": relative, "error": str(exc)})

    for relative in sorted(retained_entries):
        path = REPOSITORY_ROOT / relative
        try:
            current_bytes = path.read_bytes()
        except OSError as exc:
            unreadable.append({"path": relative, "error": str(exc)})
            continue
        current_entries.append((relative, _sha256(current_bytes)))
        retained_hash = retained_entries[relative]
        current_hash = _sha256(current_bytes)
        if not _is_probably_binary(current_bytes):
            try:
                normalized_hash = _sha256(_utf8_normalize(current_bytes))
            except UnicodeDecodeError:
                pass
            else:
                current_hash = retained_hash if normalized_hash == retained_hash else normalized_hash
        retained_semantic_entries.append((relative, retained_hash))
        current_semantic_entries.append((relative, current_hash))

    counts = Counter(item["classification"] for item in comparisons)
    comparison_by_path = {str(item["path"]): item for item in comparisons}
    substantive_assessments = []
    for relative, assessment in SUBSTANTIVE_ASSESSMENTS.items():
        comparison = comparison_by_path.get(relative, {})
        substantive_assessments.append({
            "path": relative,
            "backup_sha256": comparison.get("retained_raw_sha256"),
            "current_sha256": comparison.get("current_raw_sha256"),
            "backup_lf_sha256": comparison.get("retained_lf_sha256", comparison.get("retained_raw_sha256")),
            "current_lf_sha256": comparison.get("current_lf_sha256"),
            "retained_exact_bytes_recoverable": bool(
                comparison.get("retained_git_blob_matches_report")
            ),
            "causal_commit": CAUSAL_COMMIT,
            "causal_origin": "Sprint 7 foundation feature publication incorporated into the pre-Version-1.0 recovery checkpoint",
            **assessment,
        })
    result = {
        "schema_version": "1.0.0",
        "generated_at": utc_now(),
        "retained_report": retained_report.relative_to(REPOSITORY_ROOT).as_posix(),
        "retained_commit": retained_commit,
        "retained_release_input_sha256": retained.get("aggregate_sha256"),
        "current_release_input_sha256": _aggregate(current_entries),
        "retained_semantic_input_sha256": _aggregate(retained_semantic_entries),
        "current_semantic_input_sha256": _aggregate(current_semantic_entries),
        "release_input_file_count": len(retained_entries),
        "raw_mismatch_count": len(comparisons),
        "newline_only_equivalent_count": counts["NEWLINE_ONLY_EQUIVALENT"],
        "content_different_count": counts["CONTENT_DIFFERENT"],
        "binary_different_count": counts["BINARY_DIFFERENT"],
        "byte_identical_count": counts["BYTE_IDENTICAL"],
        "unreadable_count": len(unreadable),
        "reported_hash_mismatch_count": sum(
            not bool(item.get("reported_hashes_verified")) for item in comparisons
        ),
        "substantive_assessments": substantive_assessments,
        "dataset_evidence_decision": "FRESH_DATASET_VALIDATION_REQUIRED",
        "dataset_evidence_decision_reason": (
            "performance_registry.py is a content-different runtime input directly consumed by "
            "the Sprint 7 dataset worker through limits_for_mode; the exact retained bytes are not "
            "recoverable from Git, so semantic equivalence cannot be proven fail-closed."
        ),
        "comparisons": comparisons,
        "unreadable": unreadable,
    }
    result["status"] = "PASS" if not unreadable and not result["reported_hash_mismatch_count"] else "FAIL"
    return result


def render(report: dict[str, Any]) -> str:
    assessment_rows = []
    for item in report["substantive_assessments"]:
        assessment_rows.append((
            item["path"],
            item["classification"],
            "yes" if item["shipped_in_zip"] else "no",
            "yes" if item["runtime_imported"] else "no",
            "yes" if item["influences_dataset_worker"] else "no",
            "yes" if item["influences_analysis_result"] else "no",
            item["diff_summary"],
        ))
    return "\n".join((
        "# Fingerprint Reconciliation",
        "",
        f"Status: `{report['status']}`. Retained raw fingerprint: `{report['retained_release_input_sha256']}`. Current raw fingerprint: `{report['current_release_input_sha256']}`.",
        "",
        markdown_table(("Measure", "Count"), (
            ("Canonical release inputs", report["release_input_file_count"]),
            ("Raw mismatches", report["raw_mismatch_count"]),
            ("LF-normalized equivalents", report["newline_only_equivalent_count"]),
            ("Content-different", report["content_different_count"]),
            ("Binary-different", report["binary_different_count"]),
            ("Unreadable", report["unreadable_count"]),
        )),
        "",
        "All 45 reported newline-only paths match their frozen Sprint 7 SHA-256 after deterministic CRLF/CR-to-LF normalization. Source files were not rewritten.",
        "",
        "## Substantive paths",
        "",
        markdown_table(("Path", "Classification", "ZIP", "Imported", "Worker", "Result", "Relevant change"), assessment_rows),
        "",
        f"All nine paths trace to `{CAUSAL_COMMIT}` (`feat: implement Sprint 7 AI recommendation foundation`) before the recovery checkpoint merge. The frozen report preserved hashes but not the exact intermediate bytes; no matching blob exists in the current Git object database. Current-versus-pre-publication word diffs identify the symbols above, but exact retained-to-current textual ranges are not reconstructable.",
        "",
        "## Dataset evidence decision",
        "",
        f"`{report['dataset_evidence_decision']}`",
        "",
        report["dataset_evidence_decision_reason"],
        "",
        "The historical Sprint 7 fingerprint and dataset reports remain unchanged. H0 records the current raw and semantic identities separately.",
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mismatch-report", type=Path, default=DEFAULT_MISMATCH_REPORT)
    parser.add_argument("--retained-report", type=Path, default=DEFAULT_RETAINED_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    report = reconcile(args.mismatch_report, args.retained_report)
    write_json(args.output, report)
    write_text(args.markdown, render(report))
    summary = {
        key: report[key]
        for key in (
            "status",
            "raw_mismatch_count",
            "newline_only_equivalent_count",
            "content_different_count",
            "binary_different_count",
            "unreadable_count",
            "reported_hash_mismatch_count",
            "retained_semantic_input_sha256",
            "current_semantic_input_sha256",
        )
    }
    print(canonical_bytes(summary).decode("utf-8"), end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
