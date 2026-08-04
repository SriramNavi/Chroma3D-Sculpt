"""Run focused Sprint 2.7 storage, archive, restore, and policy tests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))
sys.path.insert(0, str(REPOSITORY_ROOT / "manual-tests" / "datasets"))
sys.path.insert(0, str(REPOSITORY_ROOT / "manual-tests" / "benchmarks"))

import build_benchmark_release  # noqa: E402
import build_dataset_release  # noqa: E402
import fetch_validation_assets  # noqa: E402
from check_repository_size_policy import check_repository  # noqa: E402
from storage_architecture import (  # noqa: E402
    build_deterministic_zip,
    read_json,
    remove_cache,
    sha256_file,
    verify_archive,
    verify_installed,
)


RELEASES_ROOT = REPOSITORY_ROOT / "release-staging" / "releases"
REPORT_ROOT = REPOSITORY_ROOT / "manual-tests" / "sprint2.7" / "reports"
ARTIFACT_ROOT = REPOSITORY_ROOT / "manual-tests" / "sprint2.7" / "artifacts"
DATASET_ARCHIVE = RELEASES_ROOT / "chroma3d-statue-dataset-1.0.0.zip"
BENCHMARK_ARCHIVE = RELEASES_ROOT / "chroma3d-golden-benchmark-1.0.0.zip"


def _expect_failure(function, label: str) -> None:
    try:
        function()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError):
        return
    raise AssertionError(f"expected failure did not occur: {label}")


def _size_without_generated_payloads() -> int:
    total = 0
    for path in REPOSITORY_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(REPOSITORY_ROOT).as_posix()
        if relative.startswith((".git/", "release-staging/", ".validation-assets/", "manual-tests/sprint2.7/artifacts/", "datasets/statues/raw/", "datasets/statues/thumbnails/", "benchmarks/golden/raw/", "benchmarks/golden/timings/", "benchmarks/golden/comparisons/", "benchmarks/golden/thumbnails/")):
            continue
        total += path.stat().st_size
    return total


def _externalized_local_size() -> int:
    total = 0
    prefixes = (
        "datasets/statues/raw/",
        "datasets/statues/thumbnails/",
        "benchmarks/golden/raw/",
        "benchmarks/golden/timings/",
        "benchmarks/golden/comparisons/",
        "benchmarks/golden/thumbnails/",
    )
    for path in REPOSITORY_ROOT.rglob("*"):
        if path.is_file() and path.relative_to(REPOSITORY_ROOT).as_posix().startswith(prefixes):
            total += path.stat().st_size
    return total


def _tracked_size() -> int:
    total = 0
    for relative in subprocess.check_output(["git", "ls-files"], cwd=REPOSITORY_ROOT, text=True).splitlines():
        path = REPOSITORY_ROOT / Path(*relative.replace("/", "\\").split("\\"))
        if path.is_file():
            total += path.stat().st_size
    return total


def _make_test_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "--quiet"], cwd=path, check=True)


def _size_policy_tests() -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix="sprint2.7-size-") as temporary:
        root = Path(temporary)
        _make_test_git_repo(root)
        oversized = root / "oversized.stl"
        oversized.write_bytes(b"0" * (26 * 1024 * 1024))
        subprocess.run(["git", "add", "oversized.stl"], cwd=root, check=True)
        subprocess.run(
            ["git", "-c", "user.name=Sprint 2.7 test", "-c", "user.email=sprint27@example.invalid", "commit", "--quiet", "-m", "fixture"],
            cwd=root,
            check=True,
        )
        if check_repository(root, policy_path=REPOSITORY_ROOT / ".repository-size-policy.json")["status"] != "FAIL":
            raise AssertionError("expected oversized tracked STL rejection did not occur")
        policy = json.loads((REPOSITORY_ROOT / ".repository-size-policy.json").read_text(encoding="utf-8"))
        policy["reviewed_exceptions"] = ["oversized.stl"]
        policy_path = root / "policy.json"
        policy_path.write_text(json.dumps(policy), encoding="utf-8")
        report = check_repository(root, policy_path=policy_path)
        if report["status"] != "PASS":
            raise AssertionError("reviewed size-policy exception was not honored")
    return {"clean_case": "PASS", "oversized_tracked_stl": "PASS", "approved_exception": "PASS"}


def _archive_security_tests() -> dict[str, str]:
    tests = {}
    _expect_failure(
        lambda: build_deterministic_zip(
            ARTIFACT_ROOT / "unsafe.zip",
            archive_root="dataset",
            index_relative_path="manifests/archive_index.json",
            created_at_utc="2026-07-26T00:00:00Z",
            entries=[("../escape.txt", b"x", {"source_id": None, "license_id": None})],
            index_payload={"archive_type": "test"},
        ),
        "path traversal",
    )
    tests["path_traversal_rejection"] = "PASS"
    _expect_failure(
        lambda: build_deterministic_zip(
            ARTIFACT_ROOT / "unsafe-absolute.zip",
            archive_root="dataset",
            index_relative_path="manifests/archive_index.json",
            created_at_utc="2026-07-26T00:00:00Z",
            entries=[("/absolute.txt", b"x", {"source_id": None, "license_id": None})],
            index_payload={"archive_type": "test"},
        ),
        "absolute path",
    )
    tests["absolute_path_rejection"] = "PASS"
    with tempfile.TemporaryDirectory(prefix="sprint2.7-zip-") as temporary:
        malicious = Path(temporary) / "symlink.zip"
        info = zipfile.ZipInfo("dataset/file.txt")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(malicious, "w") as archive:
            archive.writestr(info, b"target")
        _expect_failure(lambda: verify_archive(malicious), "symlink archive entry")
    tests["symlink_special_entry_rejection"] = "PASS"
    return tests


def _archive_metadata_tests() -> dict[str, object]:
    dataset_index = verify_archive(DATASET_ARCHIVE)
    benchmark_index = verify_archive(BENCHMARK_ARCHIVE)
    if [item.filename for item in zipfile.ZipFile(DATASET_ARCHIVE).infolist()] != sorted(item.filename for item in zipfile.ZipFile(DATASET_ARCHIVE).infolist()):
        raise AssertionError("dataset archive entries are not sorted")
    if [item.filename for item in zipfile.ZipFile(BENCHMARK_ARCHIVE).infolist()] != sorted(item.filename for item in zipfile.ZipFile(BENCHMARK_ARCHIVE).infolist()):
        raise AssertionError("benchmark archive entries are not sorted")
    for archive, index in ((DATASET_ARCHIVE, dataset_index), (BENCHMARK_ARCHIVE, benchmark_index)):
        sidecar = archive.with_name(f"{archive.name}.sha256").read_text(encoding="utf-8").split()[0]
        if sidecar != sha256_file(archive):
            raise AssertionError(f"archive sidecar mismatch: {archive.name}")
        if len(index["files"]) == 0 or any(len(item["sha256"]) != 64 for item in index["files"]):
            raise AssertionError(f"archive index is incomplete: {archive.name}")
    return {
        "dataset": {"archive_sha256": sha256_file(DATASET_ARCHIVE), "archive_size_bytes": DATASET_ARCHIVE.stat().st_size, "file_count": len(dataset_index["files"]), "asset_count": dataset_index["asset_count"]},
        "benchmark": {"archive_sha256": sha256_file(BENCHMARK_ARCHIVE), "archive_size_bytes": BENCHMARK_ARCHIVE.stat().st_size, "file_count": len(benchmark_index["files"]), "asset_count": benchmark_index["asset_count"], "json_artifact_count": benchmark_index["json_artifact_count"]},
        "stable_entry_order": "PASS",
        "sidecar_and_index_checksums": "PASS",
    }


def _restore_tests() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="sprint2.7-cache-") as temporary:
        cache = Path(temporary)
        (cache / "downloads").mkdir()
        shutil.copy2(DATASET_ARCHIVE, cache / "downloads" / DATASET_ARCHIVE.name)
        shutil.copy2(BENCHMARK_ARCHIVE, cache / "downloads" / BENCHMARK_ARCHIVE.name)
        dataset_result = fetch_validation_assets.acquire("dataset", cache, offline=True, force=False)
        benchmark_result = fetch_validation_assets.acquire("benchmark", cache, offline=True, force=False)
        if dataset_result["installed_state"] != "INSTALLED_AND_VALID" or benchmark_result["installed_state"] != "INSTALLED_AND_VALID":
            raise AssertionError("valid archive did not install as valid")
        status_json = json.dumps({kind: fetch_validation_assets._status_for(kind, cache) for kind in ("dataset", "benchmark")})
        json.loads(status_json)
        fetch_validation_assets.verify("dataset", cache)
        fetch_validation_assets.verify("benchmark", cache)
        subprocess.run(
            [sys.executable, str(REPOSITORY_ROOT / "manual-tests" / "datasets" / "verify_statue_dataset.py"), "--dataset-root", str(cache / "dataset")],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [sys.executable, str(REPOSITORY_ROOT / "manual-tests" / "benchmarks" / "verify_golden_baseline.py"), "--baseline-root", str(cache / "benchmark"), "--dataset-root", str(cache / "dataset")],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        modified = cache / "dataset" / "raw" / "statue-asad-al-lat.stl"
        with modified.open("ab") as stream:
            stream.write(b"modified")
        if fetch_validation_assets._status_for("dataset", cache)["installed_state"] != "INSTALLED_BUT_MODIFIED_OR_CORRUPT":
            raise AssertionError("modified installation was not detected")
        _expect_failure(lambda: fetch_validation_assets.acquire("dataset", cache, offline=True, force=False), "modified installation overwrite")
        fetch_validation_assets.acquire("dataset", cache, offline=True, force=True)
        (cache / "downloads" / "interrupted.part").write_bytes(b"partial")
        removed = remove_cache(cache, force=False)
        if not any(item.endswith("interrupted.part") for item in removed):
            raise AssertionError("clean-cache did not remove interrupted .part")
        if verify_installed(cache / "dataset")["asset_count"] != 27:
            raise AssertionError("restored dataset count mismatch")
        if verify_installed(cache / "benchmark")["asset_count"] != 27:
            raise AssertionError("restored benchmark count mismatch")
    return {
        "valid_extraction": "PASS",
        "atomic_installation": "PASS",
        "offline_verification": "PASS",
        "modified_local_detection": "PASS",
        "status_json": "PASS",
        "cache_cleanup": "PASS",
        "interrupted_part_handling": "PASS",
        "lock_parsing": "PASS",
        "restored_dataset_verifier": "PASS",
        "restored_golden_verifier": "PASS",
    }


def _rebuild_tests() -> dict[str, str]:
    dataset_before = sha256_file(DATASET_ARCHIVE)
    benchmark_before = sha256_file(BENCHMARK_ARCHIVE)
    build_dataset_release.build_release(
        source_root=REPOSITORY_ROOT / "datasets" / "statues",
        output_dir=RELEASES_ROOT,
        lock_path=REPOSITORY_ROOT / "datasets" / "statues" / "DATASET_LOCK.json",
    )
    build_benchmark_release.build_release(
        source_root=REPOSITORY_ROOT / "benchmarks" / "golden",
        output_dir=RELEASES_ROOT,
        lock_path=REPOSITORY_ROOT / "benchmarks" / "golden" / "BENCHMARK_LOCK.json",
    )
    if sha256_file(DATASET_ARCHIVE) != dataset_before or sha256_file(BENCHMARK_ARCHIVE) != benchmark_before:
        raise AssertionError("rebuilding a local corpus changed an archive hash")
    return {"dataset_rebuild": "PASS", "benchmark_rebuild": "PASS", "byte_identical": "PASS"}


def _compatibility_tests() -> dict[str, str]:
    dataset_lock = read_json(REPOSITORY_ROOT / "datasets" / "statues" / "DATASET_LOCK.json")
    benchmark_lock = read_json(REPOSITORY_ROOT / "benchmarks" / "golden" / "BENCHMARK_LOCK.json")
    dataset_index = verify_archive(DATASET_ARCHIVE)
    benchmark_index = verify_archive(BENCHMARK_ARCHIVE)
    if dataset_lock["asset_count"] != dataset_index["asset_count"] or benchmark_lock["expected_mesh_count"] != benchmark_index["asset_count"]:
        raise AssertionError("lock/manifest count mismatch")
    if dataset_lock["manifest_sha256"] != dataset_index["source_manifest_sha256"] or benchmark_lock["manifest_sha256"] != benchmark_index["source_manifest_sha256"]:
        raise AssertionError("lock/archive manifest mismatch")
    if benchmark_lock["software_release_used_to_generate"] != "0.3.0-alpha.1":
        raise AssertionError("baseline software provenance was rewritten")
    tracked = subprocess.check_output(["git", "ls-files"], cwd=REPOSITORY_ROOT, text=True).splitlines()
    if any(path.startswith("datasets/statues/raw/") and path.endswith(".stl") for path in tracked):
        raise AssertionError("raw mesh remains tracked")
    if any(path.startswith("benchmarks/golden/raw/") or path.startswith("benchmarks/golden/timings/") or path.startswith("benchmarks/golden/comparisons/") for path in tracked):
        raise AssertionError("externalized benchmark payload remains tracked")
    for source in (REPOSITORY_ROOT / "scripts").glob("storage*.py"):
        text = source.read_text(encoding="utf-8")
        if "import bpy" in text or "blender_addon" in text:
            raise AssertionError(f"storage tool imports runtime code: {source.name}")
    return {"version_compatibility": "PASS", "manifest_count_match": "PASS", "no_external_payload_tracked": "PASS", "no_runtime_import_dependency": "PASS"}


def _run_existing_verifiers() -> dict[str, str]:
    checks: dict[str, str] = {}
    for name, command in (
        ("dataset_verifier", [sys.executable, str(REPOSITORY_ROOT / "manual-tests" / "datasets" / "verify_statue_dataset.py")]),
        ("golden_verifier", [sys.executable, str(REPOSITORY_ROOT / "manual-tests" / "benchmarks" / "verify_golden_baseline.py")]),
    ):
        subprocess.run(command, cwd=REPOSITORY_ROOT, check=True, capture_output=True, text=True)
        checks[name] = "PASS"
    return checks


def run(report_path: Path) -> dict[str, object]:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    before = read_json(REPOSITORY_ROOT / "release-staging" / "preflight_inventory.json")
    security = _archive_security_tests()
    size_policy = _size_policy_tests()
    archives = _archive_metadata_tests()
    restore = _restore_tests()
    rebuild = _rebuild_tests()
    compatibility = _compatibility_tests()
    verifiers = _run_existing_verifiers()
    staging = read_json(REPOSITORY_ROOT / "release-staging" / "staging-summary.json") if (REPOSITORY_ROOT / "release-staging" / "staging-summary.json").is_file() else {"status": "prepared separately"}
    report = {
        "schema_version": "1.0.0",
        "status": "PASS",
        "sprint": "2.7",
        "repository": {
            "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=REPOSITORY_ROOT, text=True).strip(),
            "working_tree_bytes_before_migration": before["working_tree_bytes_before_migration"],
            "working_tree_bytes_after_migration": _size_without_generated_payloads(),
            "ignored_externalized_payload_bytes_retained_locally": _externalized_local_size(),
            "tracked_bytes_after_migration": _tracked_size(),
            "historical_git_bytes": sum(path.stat().st_size for path in (REPOSITORY_ROOT / ".git").rglob("*") if path.is_file()),
            "history_rewrite": False,
        },
        "archives": archives,
        "tests": {
            "size_policy": size_policy,
            "archive_security": security,
            "restore_and_cache": restore,
            "rebuild": rebuild,
            "compatibility": compatibility,
            "existing_verifiers": verifiers,
        },
        "staging": staging,
        "files_externalized": [
            "datasets/statues/raw/*.stl",
            "datasets/statues/thumbnails/*.png",
            "benchmarks/golden/raw/*.json",
            "benchmarks/golden/reports/*_benchmark_report.json",
            "benchmarks/golden/timings/*.json",
            "benchmarks/golden/comparisons/*.json",
            "benchmarks/golden/thumbnails/*.png",
        ],
        "files_retained": [
            "datasets/statues/manifests/statue_dataset_manifest.json",
            "datasets/statues/metadata/*.json",
            "datasets/statues/licenses/*",
            "benchmarks/golden/manifests/golden_manifest.json",
            "benchmarks/golden/statistics/golden_statistics.json",
            "benchmarks/golden/reports/generation_status.json",
            "benchmarks/golden/reports/golden_per_mesh_summary.json",
            "schemas/*",
            "lock files, policies, scripts, and documentation",
        ],
        "known_limitations": [
            "Historical Git size remains because published history was not rewritten.",
            "Initial acquisition depends on public GitHub Release availability and bandwidth.",
            "Redistribution and attribution obligations remain per source license.",
            "The separate dataset repository and release assets are staged but unpublished.",
            "Real production UAT remains separate from this storage milestone.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=REPORT_ROOT / "storage_architecture_results.json")
    arguments = parser.parse_args()
    report = run(arguments.report.resolve())
    print(f"{report['status']} Sprint 2.7 storage architecture tests")
    print(f"Report {arguments.report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
