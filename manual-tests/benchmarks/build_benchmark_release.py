"""Build and verify the reproducible Golden Benchmark 1.0.0 archive."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

from storage_architecture import (  # noqa: E402
    build_deterministic_zip,
    read_json,
    sha256_file,
    utc_timestamp,
    verify_archive,
    write_json,
    write_sha256_sidecar,
)


BENCHMARK_VERSION = "1.0.0"
DATASET_VERSION = "1.0.0"
PRODUCT_RELEASE = "v0.3.1-alpha.1"
ARCHIVE_FILENAME = f"chroma3d-golden-benchmark-{BENCHMARK_VERSION}.zip"
RELEASE_URL = (
    "https://github.com/SriramNavi/Chroma3D-Benchmark-Dataset/releases/"
    f"download/benchmark-v{BENCHMARK_VERSION}/{ARCHIVE_FILENAME}"
)
INCLUDED_DIRECTORIES = {"raw", "reports", "timings", "statistics", "comparisons", "manifests", "thumbnails", "schemas"}


def _is_excluded(path: Path, relative: str) -> bool:
    if path.name.startswith(".") or path.name.endswith((".part", ".blend1")) or path.name.endswith("_LOCK.json"):
        return True
    if path.suffix.lower() in {".pyc", ".pyo", ".blend", ".log"}:
        return True
    top = Path(relative).parts[0] if Path(relative).parts else ""
    if top not in INCLUDED_DIRECTORIES and relative not in {"README.md", "BENCHMARK_SUMMARY.md"}:
        return True
    return False


def _source_id(relative: str, benchmark_manifest: dict[str, Any]) -> str | None:
    for entry in benchmark_manifest.get("benchmark_entries", []):
        mesh_id = entry.get("mesh_id")
        if mesh_id and mesh_id in Path(relative).name:
            return mesh_id
    return None


def build_release(
    *,
    source_root: Path,
    output_dir: Path,
    lock_path: Path,
) -> dict[str, Any]:
    manifest_path = source_root / "manifests" / "golden_manifest.json"
    manifest = read_json(manifest_path)
    if manifest.get("benchmark_version") != BENCHMARK_VERSION:
        raise ValueError("golden manifest is not Benchmark 1.0.0")
    if manifest.get("dataset_version") != DATASET_VERSION:
        raise ValueError("golden manifest does not target Dataset 1.0.0")
    entries: list[tuple[str, bytes, dict[str, Any]]] = []
    for path in sorted(source_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source_root).as_posix()
        if relative == "manifests/archive_index.json" or _is_excluded(path, relative):
            continue
        entries.append(
            (
                relative,
                path.read_bytes(),
                {"source_id": _source_id(relative, manifest), "license_id": None},
            )
        )

    created_at = utc_timestamp(manifest.get("benchmark_date_utc"))
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / ARCHIVE_FILENAME
    index = build_deterministic_zip(
        archive_path,
        archive_root="benchmark",
        index_relative_path="manifests/archive_index.json",
        created_at_utc=created_at,
        entries=entries,
        index_payload={
            "archive_type": "chroma3d-golden-benchmark",
            "benchmark_version": BENCHMARK_VERSION,
            "dataset_version": DATASET_VERSION,
            "created_at_utc": created_at,
            "source_manifest_path": "manifests/golden_manifest.json",
            "source_manifest_sha256": sha256_file(manifest_path),
            "asset_count": manifest["mesh_count"],
            "json_artifact_count": 193,
            "source_software_release": manifest["software_version"],
            "source_git_tag": manifest["source_git_tag"],
            "packaged_for_product_release": PRODUCT_RELEASE,
        },
    )
    archive_sha256 = write_sha256_sidecar(archive_path, output_dir / f"{ARCHIVE_FILENAME}.sha256")
    index["archive_sha256"] = archive_sha256
    index_path = output_dir / f"{ARCHIVE_FILENAME}.index.json"
    write_json(index_path, index)

    lock = {
        "schema_version": "1.0.0",
        "benchmark_lock_schema_version": "1.0.0",
        "benchmark_name": "Chroma3D Golden Benchmark Baseline",
        "benchmark_version": BENCHMARK_VERSION,
        "dataset_version_dependency": DATASET_VERSION,
        "software_release_used_to_generate": manifest["software_version"],
        "source_git_tag": manifest["source_git_tag"],
        "dataset_repository": "SriramNavi/Chroma3D-Benchmark-Dataset",
        "release_tag": f"benchmark-v{BENCHMARK_VERSION}",
        "release_url": RELEASE_URL,
        "release_identifier": f"benchmark-v{BENCHMARK_VERSION}",
        "asset_filename": ARCHIVE_FILENAME,
        "asset_size_bytes": archive_path.stat().st_size,
        "asset_sha256": archive_sha256,
        "manifest_sha256": sha256_file(manifest_path),
        "expected_mesh_count": manifest["mesh_count"],
        "expected_json_artifact_count": 193,
        "extraction_directory": "benchmark",
        "comparator_compatibility_notes": (
            "Use the stored benchmark comparator and the exact Dataset 1.0.0 manifest. "
            "The baseline was generated with the product runtime recorded in the golden manifest."
        ),
        "packaged_for_product_release": PRODUCT_RELEASE,
        "created_at_utc": created_at,
    }
    write_json(lock_path, lock)
    verify_archive(archive_path)
    return {
        "archive_path": archive_path.as_posix(),
        "archive_filename": ARCHIVE_FILENAME,
        "archive_size_bytes": archive_path.stat().st_size,
        "archive_sha256": archive_sha256,
        "index_path": index_path.as_posix(),
        "index_file_count": len(index["files"]),
        "json_artifact_count": 193,
        "mesh_count": manifest["mesh_count"],
        "manifest_sha256": sha256_file(manifest_path),
        "source_software_release": manifest["software_version"],
        "packaged_for_product_release": PRODUCT_RELEASE,
        "reproducibility_timestamp": created_at,
        "lock_path": lock_path.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=REPOSITORY_ROOT / "benchmarks" / "golden")
    parser.add_argument("--output-dir", type=Path, default=REPOSITORY_ROOT / "release-staging" / "releases")
    parser.add_argument("--lock-path", type=Path, default=REPOSITORY_ROOT / "benchmarks" / "golden" / "BENCHMARK_LOCK.json")
    arguments = parser.parse_args()
    result = build_release(
        source_root=arguments.source_root.resolve(),
        output_dir=arguments.output_dir.resolve(),
        lock_path=arguments.lock_path.resolve(),
    )
    print(f"PASS benchmark archive {result['archive_filename']}")
    print(f"SHA-256 {result['archive_sha256']}")
    print(f"Files {result['index_file_count']}; meshes {result['mesh_count']}; JSON artifacts {result['json_artifact_count']}")
    print(f"Source software {result['source_software_release']}; packaged for {result['packaged_for_product_release']}")
    print(f"Reproducibility timestamp {result['reproducibility_timestamp']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
