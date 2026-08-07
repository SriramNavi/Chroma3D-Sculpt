"""Capture the immutable H3 starting identity for H4 qualification."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "hardening" / "h4" / "H4_BASELINE_IDENTITY.json"
EXPECTED_BRANCH = "feature/v1.0-release-hardening"
EXPECTED_HEAD = "ba77d12e3a7e768fdc05d542c6ea12e1a3515a0b"
EXPECTED_TAG = "v0.8.0-h3-hardening-checkpoint"
EXPECTED_TAG_OBJECT = "e481d6530a8b502630d02f14b5f66a108815b33a"


def _git(*args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if check and completed.returncode:
        raise RuntimeError(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return completed.stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_status() -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or "git status failed")
    return completed.stdout.splitlines()


def _aggregate(entries: Iterable[tuple[str, str]]) -> str:
    digest = hashlib.sha256()
    for relative, file_hash in entries:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _tracked_entries(*pathspecs: str) -> list[dict[str, str]]:
    paths = sorted(filter(None, _git("ls-files", "--", *pathspecs).splitlines()))
    return [{"path": value, "sha256": _sha256(ROOT / value)} for value in paths]


def _entry_summary(entries: list[dict[str, str]]) -> dict[str, Any]:
    pairs = [(item["path"], item["sha256"]) for item in entries]
    return {"file_count": len(entries), "aggregate_sha256": _aggregate(pairs), "files": entries}


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def capture() -> dict[str, Any]:
    head = _git("rev-parse", "HEAD")
    main = _git("rev-parse", "main")
    origin_main = _git("rev-parse", "origin/main")
    branch = _git("branch", "--show-current")
    tag_object = _git("rev-parse", f"refs/tags/{EXPECTED_TAG}")
    tag_peeled = _git("rev-parse", f"refs/tags/{EXPECTED_TAG}^{{}}")
    dirty = _git_status()
    allowed_dirty = {
        ".gitignore",
        "hardening/h4/H4_FAILURE_LOG.md",
        "hardening/h4/H4_FIRST_FAILURE.md",
        "manual-tests/hardening/h4/capture_h4_baseline.py",
    }
    dirty_paths = {line[3:].replace("\\", "/") for line in dirty}
    upstream = _git("for-each-ref", "--format=%(upstream:short)", f"refs/heads/{branch}")
    remote_feature = _git("for-each-ref", "--format=%(refname)", f"refs/remotes/origin/{EXPECTED_BRANCH}")

    if not all((
        branch == EXPECTED_BRANCH,
        head == main == origin_main == EXPECTED_HEAD,
        tag_object == EXPECTED_TAG_OBJECT,
        tag_peeled == EXPECTED_HEAD,
        not (dirty_paths - allowed_dirty),
        not _git("diff", "--cached", "--name-only"),
        not upstream,
        not remote_feature,
        int(_git("rev-list", "--count", "main..HEAD")) == 0,
    )):
        raise RuntimeError("H4 baseline capture preflight failed closed")

    fingerprint_module = _load(
        "h4_release_input",
        ROOT / "manual-tests" / "sprint7" / "release_input_fingerprint.py",
    )
    contract_module = _load(
        "h4_public_contract",
        ROOT / "hardening" / "tools" / "capture_public_contract.py",
    )
    release_input = fingerprint_module.build_release_input_identity()
    public_contract = contract_module.capture()
    combined_entries = _tracked_entries("tests/blender", "scripts/run_blender_tests.py")
    frozen_entries = _tracked_entries(
        "hardening/baseline",
        "hardening/h1",
        "hardening/h2",
        "hardening/h3",
        "manual-tests/hardening/h1",
        "manual-tests/hardening/h2",
        "manual-tests/hardening/h3",
    )
    h3_entries = _tracked_entries("hardening/h3", "manual-tests/hardening/h3")
    h3_final = json.loads((ROOT / "hardening" / "h3" / "H3_FINAL_RESULT.json").read_text(encoding="utf-8"))
    metadata = _load("h4_metadata", ROOT / "blender_addon" / "chroma3d_sculpt" / "metadata.py")

    release_files = [
        {"path": str(item["path"]), "sha256": str(item["sha256"])}
        for item in release_input["files"]
    ]
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "preflight": {
            "phase": "H4-00",
            "status": "PASS",
            "branch": branch,
            "head": head,
            "main": main,
            "origin_main": origin_main,
            "worktree_scope_at_capture": sorted(dirty_paths),
            "nothing_staged": True,
            "unique_commits_beyond_main": 0,
            "upstream_configured": False,
            "remote_rolling_branch_present": False,
        },
        "frozen_h3": {
            "tag": EXPECTED_TAG,
            "tag_type": _git("cat-file", "-t", f"refs/tags/{EXPECTED_TAG}"),
            "tag_object": tag_object,
            "tag_peeled_target": tag_peeled,
            "decision": h3_final.get("decision"),
            "gate_count": len(h3_final.get("gates", ())),
            "passed_gate_count": sum(gate.get("status") == "PASS" for gate in h3_final.get("gates", ())),
        },
        "h3_artifacts": _entry_summary(h3_entries),
        "frozen_h0_h3_evidence": _entry_summary(frozen_entries),
        "release_input": {
            "file_count": int(release_input["file_count"]),
            "aggregate_sha256": str(release_input["aggregate_sha256"]),
            "files": release_files,
        },
        "public_contract": {
            "sha256": public_contract["contract_sha256"],
            "operators": len(public_contract["operator_bl_idnames"]),
            "panels": len(public_contract["panel_ids"]),
            "properties": len(public_contract["property_names"]),
            "schemas": len(public_contract["schemas"]),
            "feature_flags": len(public_contract["feature_flag_ids"]),
            "enums": len(public_contract["status_and_result_enums"]),
        },
        "package_identity": {
            key: h3_final["evidence"]["package"].get(key)
            for key in ("status", "archive_filename", "archive_file_count", "archive_bytes", "archive_sha256")
        },
        "combined_test_identity": {
            **_entry_summary(combined_entries),
            "retained_h3_tests_run": h3_final["evidence"]["combined"].get("tests_run"),
            "retained_h3_status": h3_final["evidence"]["combined"].get("status"),
        },
        "dataset_identity": {
            "dataset_manifest_sha256": release_input["dataset_manifest_sha256"],
            "benchmark_manifest_sha256": release_input["golden_manifest_sha256"],
            "profile_context_sha256": release_input["profile_context_sha256"],
            "retained_h3_release_input_sha256": h3_final["evidence"]["dataset"].get("current_release_input_sha256"),
            "retained_representative": h3_final["evidence"]["dataset"].get("representative"),
            "retained_full": h3_final["evidence"]["dataset"].get("full"),
        },
        "version": {
            "extension_version": metadata.EXTENSION_VERSION,
            "display_version": metadata.DISPLAY_VERSION,
        },
        "safety": {
            "h3_artifacts_modified": False,
            "product_or_package_version_changed": False,
            "source_geometry_mutated": False,
            "sprint8_started": False,
        },
    }


def main() -> int:
    value = capture()
    _write_json(OUTPUT, value)
    print(json.dumps({
        "status": "PASS",
        "release_input_sha256": value["release_input"]["aggregate_sha256"],
        "public_contract_sha256": value["public_contract"]["sha256"],
        "h3_artifact_count": value["h3_artifacts"]["file_count"],
        "frozen_evidence_count": value["frozen_h0_h3_evidence"]["file_count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
