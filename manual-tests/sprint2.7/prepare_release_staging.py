"""Prepare the unpublished lightweight external dataset-repository staging tree."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

from storage_architecture import (  # noqa: E402
    build_deterministic_zip,
    read_json,
    sha256_file,
    utc_timestamp,
    write_json,
    write_sha256_sidecar,
)


def _copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def prepare(staging_root: Path, releases_root: Path) -> dict[str, Any]:
    dataset_root = REPOSITORY_ROOT / "datasets" / "statues"
    benchmark_root = REPOSITORY_ROOT / "benchmarks" / "golden"
    staging_root.mkdir(parents=True, exist_ok=True)
    release_destination = staging_root / "releases"
    release_destination.mkdir(parents=True, exist_ok=True)

    for relative in (
        "DATASET_STORAGE_POLICY.md",
        "VERSIONING_DATASETS_AND_BENCHMARKS.md",
        "docs/DATASET_CI_GUIDE.md",
        "schemas/archive_index.schema.json",
        "schemas/dataset_lock.schema.json",
        "schemas/benchmark_lock.schema.json",
        "datasets/statues/schemas/dataset_manifest.schema.json",
        "benchmarks/golden/schemas/benchmark_manifest.schema.json",
        "datasets/statues/manifests/statue_dataset_manifest.json",
        "benchmarks/golden/manifests/golden_manifest.json",
        "datasets/statues/licenses/ATTRIBUTIONS.md",
        "datasets/statues/licenses/LICENSE_INDEX.md",
        "datasets/statues/licenses/CC0-1.0.txt",
        "datasets/statues/licenses/CC-BY-4.0.txt",
        "datasets/statues/licenses/CC-BY-SA-4.0.txt",
        "datasets/statues/DATASET_LOCK.json",
        "benchmarks/golden/BENCHMARK_LOCK.json",
    ):
        source = REPOSITORY_ROOT / relative
        if source.is_file():
            target_name = Path(relative).name
            if relative.startswith("datasets/statues/manifests/"):
                destination = staging_root / "manifests" / target_name
            elif relative.startswith("benchmarks/golden/manifests/"):
                destination = staging_root / "manifests" / target_name
            elif relative.startswith("datasets/statues/licenses/"):
                destination = staging_root / target_name
            elif relative.startswith("schemas/") or "/schemas/" in relative:
                destination = staging_root / "schemas" / target_name
            elif relative.endswith("_LOCK.json"):
                destination = staging_root / "manifests" / target_name
            else:
                destination = staging_root / relative
            _copy(source, destination)

    for filename in (
        "chroma3d-statue-dataset-1.0.0.zip",
        "chroma3d-statue-dataset-1.0.0.zip.sha256",
        "chroma3d-statue-dataset-1.0.0.zip.index.json",
        "chroma3d-golden-benchmark-1.0.0.zip",
        "chroma3d-golden-benchmark-1.0.0.zip.sha256",
        "chroma3d-golden-benchmark-1.0.0.zip.index.json",
    ):
        _copy(releases_root / filename, release_destination / filename)

    dataset_manifest = dataset_root / "manifests" / "statue_dataset_manifest.json"
    benchmark_manifest = benchmark_root / "manifests" / "golden_manifest.json"
    _copy(dataset_manifest, staging_root / "manifests" / "source-manifest-1.0.0.json")
    _copy(benchmark_manifest, staging_root / "manifests" / "benchmark-manifest-1.0.0.json")
    _copy(dataset_root / "DATASET_SUMMARY.md", staging_root / "DATASET_SUMMARY.md")
    _copy(benchmark_root / "BENCHMARK_SUMMARY.md", staging_root / "BENCHMARK_SUMMARY.md")

    attribution_entries = []
    for path in sorted((dataset_root / "licenses").glob("*.txt")):
        attribution_entries.append((f"licenses/{path.name}", path.read_bytes(), {"source_id": "license-policy", "license_id": path.stem}))
    for path in sorted((dataset_root / "licenses").glob("*.md")):
        attribution_entries.append((path.name, path.read_bytes(), {"source_id": "license-policy", "license_id": None}))
    attribution_archive = release_destination / "attribution-bundle-1.0.0.zip"
    attribution_manifest = read_json(dataset_manifest)
    attribution_created = utc_timestamp(attribution_manifest["generated_at_utc"])
    build_deterministic_zip(
        attribution_archive,
        archive_root="attribution",
        index_relative_path="manifests/archive_index.json",
        created_at_utc=attribution_created,
        entries=attribution_entries,
        index_payload={
            "archive_type": "chroma3d-attribution-bundle",
            "dataset_version": "1.0.0",
            "created_at_utc": attribution_created,
            "source_manifest_sha256": sha256_file(dataset_manifest),
            "asset_count": attribution_manifest["asset_count"],
        },
    )
    attribution_sha = write_sha256_sidecar(attribution_archive, release_destination / "attribution-bundle-1.0.0.zip.sha256")

    (staging_root / "README.md").write_text(
        "# Chroma3D Benchmark Dataset release staging\n\n"
        "This is an unpublished local staging tree for Dataset 1.0.0 and Golden Benchmark 1.0.0.\n"
        "It is not a Git repository and contains no product history. Publish only after the Sprint 2.7 evidence review.\n",
        encoding="utf-8",
    )
    (staging_root / "LICENSE_POLICY.md").write_text(
        "# License Policy\n\n"
        "Redistribution must preserve the per-asset license, author/institution credit, source revision, and the attribution bundle.\n"
        "See `ATTRIBUTIONS.md` and the copied license texts. Do not imply printability, ownership, or diagnostic cleanliness.\n",
        encoding="utf-8",
    )
    (staging_root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 1.0.0\n\n- Initial 27-asset rights-cleared statue dataset.\n- Initial Golden Benchmark 1.0.0 baseline for Dataset 1.0.0.\n",
        encoding="utf-8",
    )
    (staging_root / "ATTRIBUTIONS.md").write_text(
        (dataset_root / "licenses" / "ATTRIBUTIONS.md").read_text(encoding="utf-8")
        + "\nThe full attribution bundle is `releases/attribution-bundle-1.0.0.zip`.\n",
        encoding="utf-8",
    )
    (staging_root / "release-notes").mkdir(exist_ok=True)
    (staging_root / "release-notes" / "dataset-1.0.0.md").write_text(
        "# Dataset 1.0.0\n\n27 validated, rights-cleared STL statue meshes with immutable provenance, metadata, licenses, and SHA-256 values.\n\nThe release asset is `chroma3d-statue-dataset-1.0.0.zip`.\n",
        encoding="utf-8",
    )
    (staging_root / "release-notes" / "benchmark-1.0.0.md").write_text(
        "# Golden Benchmark 1.0.0\n\n27/27 stored production-path golden records for Dataset 1.0.0. The source baseline records software `0.3.0-alpha.1`; packaging is prepared under product release `v0.3.1-alpha.1`.\n\nThe release asset is `chroma3d-golden-benchmark-1.0.0.zip`.\n",
        encoding="utf-8",
    )
    checklists = {
        "UPLOAD_CHECKLIST.md": "# Upload checklist\n\n- [ ] Review Sprint 2.7 evidence and locks.\n- [ ] Create the separate repository without a nested product checkout.\n- [ ] Upload ZIPs, sidecars, source manifest, and attribution bundle.\n- [ ] Create `dataset-v1.0.0` and `benchmark-v1.0.0` releases.\n- [ ] Do not publish until owner authorization is recorded.\n",
        "VERIFICATION_CHECKLIST.md": "# Verification checklist\n\n- [ ] Compare uploaded asset hashes with the lock files.\n- [ ] Download into a clean cache and run offline `verify`.\n- [ ] Run dataset and golden verifiers against the restored roots.\n- [ ] Confirm attribution and license files are present.\n",
        "ROLLBACK_CHECKLIST.md": "# Rollback checklist\n\n- [ ] Stop publication or mark the affected release unavailable.\n- [ ] Preserve the failing asset, hash, and evidence.\n- [ ] Do not move product tags or rewrite history.\n- [ ] Restore the prior lock/release only through reviewed branch changes.\n",
    }
    for name, content in checklists.items():
        (staging_root / name).write_text(content, encoding="utf-8")

    scripts_root = staging_root / "scripts"
    scripts_root.mkdir(exist_ok=True)
    _copy(REPOSITORY_ROOT / "scripts" / "fetch_validation_assets.py", scripts_root / "fetch_validation_assets.py")
    _copy(REPOSITORY_ROOT / "scripts" / "storage_architecture.py", scripts_root / "storage_architecture.py")
    _copy(REPOSITORY_ROOT / "manual-tests" / "datasets" / "build_dataset_release.py", scripts_root / "build_dataset_release.py")
    _copy(REPOSITORY_ROOT / "manual-tests" / "benchmarks" / "build_benchmark_release.py", scripts_root / "build_benchmark_release.py")
    return {
        "staging_root": staging_root.as_posix(),
        "release_asset_count": len(list(release_destination.iterdir())),
        "attribution_archive_sha256": attribution_sha,
        "dataset_manifest_sha256": sha256_file(dataset_manifest),
        "benchmark_manifest_sha256": sha256_file(benchmark_manifest),
        "contains_nested_git_repository": (staging_root / ".git").exists(),
    }


def main() -> int:
    result = prepare(
        REPOSITORY_ROOT / "release-staging" / "dataset-repository",
        REPOSITORY_ROOT / "release-staging" / "releases",
    )
    write_json(REPOSITORY_ROOT / "release-staging" / "staging-summary.json", {"status": "PASS", **result})
    print(f"PASS staging {result['staging_root']}")
    print(f"Release assets {result['release_asset_count']}; attribution SHA-256 {result['attribution_archive_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
