from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATASET_ROOT = REPOSITORY_ROOT / "datasets" / "statues"
RAW_ROOT = DATASET_ROOT / "raw"
METADATA_ROOT = DATASET_ROOT / "metadata"
THUMBNAIL_ROOT = DATASET_ROOT / "thumbnails"
MANIFEST_PATH = DATASET_ROOT / "manifests" / "statue_dataset_manifest.json"

REQUIRED_METADATA_FIELDS = {
    "unique_id",
    "title",
    "subject",
    "category",
    "religious_cultural_classification",
    "source_url",
    "download_date",
    "author",
    "license",
    "license_url",
    "file_format",
    "vertex_count",
    "triangle_count",
    "bounding_box",
    "checksum_sha256",
    "original_filename",
    "stored_filename",
    "notes",
}
ACCEPTED_FORMATS = {"OBJ", "PLY", "STL", "FBX", "GLB", "GLTF"}
REQUIRED_DOCUMENTS = (
    DATASET_ROOT / "README.md",
    DATASET_ROOT / "DATASET_SUMMARY.md",
    DATASET_ROOT / "processed" / "README.md",
    DATASET_ROOT / "licenses" / "ATTRIBUTIONS.md",
    DATASET_ROOT / "licenses" / "LICENSE_INDEX.md",
    REPOSITORY_ROOT / "manual-tests" / "datasets" / "REAL_STATUE_DATASET.md",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    manifest = _read_json(MANIFEST_PATH)
    assets = manifest["assets"]
    _check(manifest["dataset_version"] == "1.0.0", "unexpected dataset version")
    _check(20 <= manifest["asset_count"] <= 50, "asset count is outside 20–50")
    _check(manifest["asset_count"] == len(assets), "manifest asset count mismatch")
    _check(
        manifest["validated_asset_count"] == len(assets),
        "validated asset count mismatch",
    )
    print("PASS manifest shape and target asset count")

    identifiers = [item["unique_id"] for item in assets]
    _check(len(identifiers) == len(set(identifiers)), "duplicate unique IDs")
    _check(
        all(REQUIRED_METADATA_FIELDS <= set(item) for item in assets),
        "required metadata field is missing",
    )
    _check(
        all(str(item["author"]).strip() for item in assets),
        "author/credit field is empty",
    )
    print("PASS unique IDs and required metadata fields")

    metadata_files = sorted(METADATA_ROOT.glob("statue-*.json"))
    _check(len(metadata_files) == len(assets), "per-asset metadata count mismatch")
    metadata_by_id = {
        item["unique_id"]: item for item in map(_read_json, metadata_files)
    }
    for asset in assets:
        _check(
            metadata_by_id.get(asset["unique_id"]) == asset,
            f"manifest/per-asset metadata mismatch: {asset['unique_id']}",
        )
    print("PASS manifest and per-asset metadata equality")

    manifest_raw_names = set()
    for asset in assets:
        _check(asset["file_format"] in ACCEPTED_FORMATS, "unaccepted mesh format")
        raw_path = REPOSITORY_ROOT / asset["stored_path"]
        manifest_raw_names.add(raw_path.name)
        _check(raw_path.is_file(), f"missing raw mesh: {asset['unique_id']}")
        _check(raw_path.stat().st_size > 0, f"empty raw mesh: {asset['unique_id']}")
        _check(
            raw_path.stat().st_size == asset["file_size_bytes"],
            f"raw size mismatch: {asset['unique_id']}",
        )
        _check(
            _sha256(raw_path) == asset["checksum_sha256"],
            f"SHA-256 mismatch: {asset['unique_id']}",
        )
    raw_names = {path.name for path in RAW_ROOT.glob("*") if path.is_file()}
    _check(raw_names == manifest_raw_names, "raw directory/manifest mismatch")
    print("PASS 27 raw mesh sizes and SHA-256 checksums")

    for asset in assets:
        validation = asset["validation"]
        _check(
            validation["status"] == "validated",
            f"asset not validated: {asset['unique_id']}",
        )
        _check(validation["readable"], f"asset not readable: {asset['unique_id']}")
        _check(
            validation["reasonable_mesh"],
            f"asset not reasonable: {asset['unique_id']}",
        )
        _check(
            not validation["obvious_corruption"],
            f"asset marked corrupt: {asset['unique_id']}",
        )
        _check(asset["vertex_count"] > 0, "non-positive vertex count")
        _check(asset["triangle_count"] > 0, "non-positive triangle count")
        _check(asset["bounding_box"]["diagonal"] > 0, "zero bounding box")
    print("PASS Blender readability and bounded geometry validation")

    for asset in assets:
        thumbnail_path = REPOSITORY_ROOT / asset["thumbnail_path"]
        _check(
            thumbnail_path.is_file() and thumbnail_path.stat().st_size > 0,
            f"missing thumbnail: {asset['unique_id']}",
        )
        _check(
            _sha256(thumbnail_path) == asset["thumbnail_checksum_sha256"],
            f"thumbnail SHA-256 mismatch: {asset['unique_id']}",
        )
    thumbnail_names = {path.name for path in THUMBNAIL_ROOT.glob("*.png")}
    _check(len(thumbnail_names) == len(assets), "thumbnail count mismatch")
    print("PASS thumbnail presence and SHA-256 checksums")

    actual_license_summary = dict(
        sorted(Counter(item["license"] for item in assets).items())
    )
    actual_category_summary = dict(
        sorted(Counter(item["category"] for item in assets).items())
    )
    actual_format_summary = dict(
        sorted(Counter(item["file_format"] for item in assets).items())
    )
    _check(
        actual_license_summary == manifest["license_summary"],
        "license summary mismatch",
    )
    _check(
        actual_category_summary == manifest["category_summary"],
        "category summary mismatch",
    )
    _check(
        actual_format_summary == manifest["format_summary"],
        "format summary mismatch",
    )
    for asset in assets:
        license_path = REPOSITORY_ROOT / asset["license_document"]
        _check(
            license_path.is_file() and license_path.stat().st_size > 0,
            f"missing license document: {asset['license']}",
        )
    print("PASS license, category, and format summaries")

    rejected = _read_json(METADATA_ROOT / "rejected_assets.json")
    _check(
        len(rejected["policy_rejections"])
        == manifest["policy_rejected_candidate_count"],
        "policy rejection count mismatch",
    )
    _check(not rejected["acquisition_failures"], "acquisition failures recorded")
    _check(
        not manifest["validation"]["failures"],
        "validation failures recorded",
    )
    print("PASS rejection and zero-failure accounting")

    for document in REQUIRED_DOCUMENTS:
        _check(
            document.is_file() and document.stat().st_size > 0,
            f"missing required documentation: {document}",
        )
    _check(
        not list(DATASET_ROOT.rglob("*.part")),
        "partial download artifacts remain",
    )
    print("PASS required documentation and no partial artifacts")

    _check(
        not manifest["validation"]["production_diagnostics_executed"],
        "manifest incorrectly claims production diagnostics",
    )
    _check(
        not manifest["validation"]["repair_operations_executed"],
        "manifest incorrectly claims repair execution",
    )
    print("PASS dataset-only scope claims")
    print(f"Verified {len(assets)} accepted assets with no integrity failures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
