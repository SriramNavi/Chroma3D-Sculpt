"""Build and verify the reproducible Dataset 1.0.0 release archive."""

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


DATASET_VERSION = "1.0.0"
ARCHIVE_FILENAME = f"chroma3d-statue-dataset-{DATASET_VERSION}.zip"
RELEASE_URL = (
    "https://github.com/SriramNavi/Chroma3D-Benchmark-Dataset/releases/"
    f"download/dataset-v{DATASET_VERSION}/{ARCHIVE_FILENAME}"
)


def _is_excluded(path: Path) -> bool:
    return (
        path.name.startswith(".")
        or path.name.endswith((".part", ".blend1"))
        or path.name.endswith("_LOCK.json")
        or path.suffix.lower() in {".pyc", ".pyo", ".blend"}
    )


def _asset_context(relative: str, assets: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    filename = Path(relative).name
    for asset in assets:
        if filename in {asset.get("stored_filename"), asset.get("original_filename")}:
            return asset["unique_id"], asset.get("license")
        if filename == f"{asset['unique_id']}.json" or filename == f"{asset['unique_id']}.png":
            return asset["unique_id"], asset.get("license")
    if relative.startswith("licenses/"):
        return "license-policy", Path(relative).stem
    return None, None


def build_release(
    *,
    source_root: Path,
    output_dir: Path,
    lock_path: Path,
) -> dict[str, Any]:
    manifest_path = source_root / "manifests" / "statue_dataset_manifest.json"
    manifest = read_json(manifest_path)
    if manifest.get("dataset_version") != DATASET_VERSION:
        raise ValueError("dataset manifest is not Dataset 1.0.0")
    assets = list(manifest["assets"])
    entries: list[tuple[str, bytes, dict[str, Any]]] = []
    for path in sorted(source_root.rglob("*")):
        if not path.is_file() or _is_excluded(path):
            continue
        relative = path.relative_to(source_root).as_posix()
        if relative == "manifests/archive_index.json":
            continue
        source_id, license_id = _asset_context(relative, assets)
        entries.append(
            (
                relative,
                path.read_bytes(),
                {"source_id": source_id, "license_id": license_id},
            )
        )

    created_at = utc_timestamp(manifest.get("generated_at_utc") or manifest.get("creation_date"))
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / ARCHIVE_FILENAME
    index = build_deterministic_zip(
        archive_path,
        archive_root="dataset",
        index_relative_path="manifests/archive_index.json",
        created_at_utc=created_at,
        entries=entries,
        index_payload={
            "archive_type": "chroma3d-dataset",
            "dataset_version": DATASET_VERSION,
            "created_at_utc": created_at,
            "source_manifest_path": "manifests/statue_dataset_manifest.json",
            "source_manifest_sha256": sha256_file(manifest_path),
            "asset_count": manifest["asset_count"],
            "license_summary": manifest["license_summary"],
        },
    )
    archive_sha256 = write_sha256_sidecar(archive_path, output_dir / f"{ARCHIVE_FILENAME}.sha256")
    index["archive_sha256"] = archive_sha256
    index_path = output_dir / f"{ARCHIVE_FILENAME}.index.json"
    write_json(index_path, index)

    lock = {
        "schema_version": "1.0.0",
        "dataset_lock_schema_version": "1.0.0",
        "dataset_name": "Chroma3D Statue Dataset",
        "dataset_version": DATASET_VERSION,
        "dataset_repository": "SriramNavi/Chroma3D-Benchmark-Dataset",
        "release_tag": f"dataset-v{DATASET_VERSION}",
        "release_url": RELEASE_URL,
        "release_identifier": f"dataset-v{DATASET_VERSION}",
        "asset_filename": ARCHIVE_FILENAME,
        "asset_size_bytes": archive_path.stat().st_size,
        "asset_sha256": archive_sha256,
        "manifest_sha256": sha256_file(manifest_path),
        "asset_count": manifest["asset_count"],
        "license_summary": manifest["license_summary"],
        "required_extracted_directory": "dataset",
        "minimum_acquisition_tool_version": "1.0.0",
        "created_at_utc": created_at,
        "source_software_compatibility_notes": (
            "Dataset 1.0.0 is the rights-cleared STL corpus validated by Blender 4.4.3; "
            "it makes no claim of watertightness, printability, diagnostic cleanliness, or repair success."
        ),
        "packaged_for_product_release": "v0.3.1-alpha.1",
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
        "asset_count": manifest["asset_count"],
        "manifest_sha256": sha256_file(manifest_path),
        "reproducibility_timestamp": created_at,
        "lock_path": lock_path.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=REPOSITORY_ROOT / "datasets" / "statues")
    parser.add_argument("--output-dir", type=Path, default=REPOSITORY_ROOT / "release-staging" / "releases")
    parser.add_argument("--lock-path", type=Path, default=REPOSITORY_ROOT / "datasets" / "statues" / "DATASET_LOCK.json")
    arguments = parser.parse_args()
    result = build_release(
        source_root=arguments.source_root.resolve(),
        output_dir=arguments.output_dir.resolve(),
        lock_path=arguments.lock_path.resolve(),
    )
    print(f"PASS dataset archive {result['archive_filename']}")
    print(f"SHA-256 {result['archive_sha256']}")
    print(f"Files {result['index_file_count']}; assets {result['asset_count']}")
    print(f"Reproducibility timestamp {result['reproducibility_timestamp']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
