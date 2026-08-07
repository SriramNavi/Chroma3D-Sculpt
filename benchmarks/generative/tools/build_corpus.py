"""Build strict CGB-SMOKE3/CORE10/FULL27 manifests from Dataset 1.0.0."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import CGB_VERSION, GENERATIVE_ROOT, PROJECT_ROOT, VALIDATION_ROOT, read_json, sha256_file, stable_hash, write_json


SMOKE3 = (
    "statue-asad-al-lat",
    "statue-cosmic-buddha-smithsonian-150k",
    "statue-pieta-michelangelo",
)
CORE10 = (
    "statue-asad-al-lat",
    "statue-bastet",
    "statue-cosmic-buddha-smithsonian-150k",
    "statue-hizen-komainu",
    "statue-hotei-water-basin",
    "statue-laocoon-group",
    "statue-mick-odwyer",
    "statue-pieta-michelangelo",
    "statue-thinker-rodin",
    "statue-venus-willendorf",
)


def _reference_record(case_id: str, view: str, render_index: dict[str, Any]) -> dict[str, Any]:
    expected = f".validation-assets/generative-benchmark/reference-renders/{case_id}/{view}.png"
    record = render_index.get("cases", {}).get(case_id, {}).get("views", {}).get(view, {})
    digest = record.get("sha256") if isinstance(record, dict) else None
    return {
        "view": view, "path": expected, "sha256": digest,
        "hash_basis": record.get("hash_basis") if isinstance(record, dict) else None,
        "file_sha256": record.get("file_sha256") if isinstance(record, dict) else None,
        "state": "READY" if isinstance(digest, str) and len(digest) == 64 else "NOT_RUN",
    }


def _source_path(dataset_root: Path, asset: dict[str, Any]) -> Path:
    return dataset_root / "raw" / str(asset["stored_filename"])


def _case(asset: dict[str, Any], dataset_root: Path, render_index: dict[str, Any]) -> dict[str, Any]:
    case_id = str(asset["unique_id"])
    source = _source_path(dataset_root, asset)
    references = [_reference_record(case_id, view, render_index) for view in ("front", "front_three_quarter", "side", "back")]
    case = {
        "case_id": case_id,
        "source_dataset_version": "1.0.0",
        "source_mesh_id": case_id,
        "source_sha256": str(asset["checksum_sha256"]),
        "source_storage_hint": f".validation-assets/dataset/raw/{asset['stored_filename']}",
        "rights_or_provenance": {
            "title": asset.get("title"), "author": asset.get("author"), "license": asset.get("license"),
            "license_url": asset.get("license_url"), "source_revision_url": asset.get("source_revision_url"),
            "credit": asset.get("credit"),
        },
        "category": asset.get("category"),
        "reference_render_hashes": {item["view"]: item["sha256"] for item in references if item["sha256"]},
        "single_image_reference": references[1],
        "multiview_references": references,
        "canonical_dimensions": {
            "values": asset.get("bounding_box", {}).get("dimensions"),
            "source_units": asset.get("bounding_box", {}).get("source_units", "unspecified"),
            "normalization": "evaluation_copy_only",
        },
        "ground_truth_geometry_available": True,
        "prompt_if_defined": None,
        "benchmark_tracks": ["A", "B", "D", "E", "F", "G", "H"],
        "notes": list(asset.get("notes", [])) + ["Source geometry is immutable; Track G is capability-only for this untextured ground truth."],
    }
    case["case_hash"] = stable_hash(case)
    if not source.is_file():
        raise FileNotFoundError(f"Dataset source is missing: {case_id}")
    actual = sha256_file(source)
    if actual != case["source_sha256"]:
        raise RuntimeError(f"Dataset source hash mismatch: {case_id}")
    return case


def _subset(subset_id: str, case_ids: tuple[str, ...], manifest_hash: str) -> dict[str, Any]:
    payload = {
        "cgb_version": CGB_VERSION, "subset_id": subset_id, "attempts": 1,
        "primary_result_policy": "FIRST_SHOT", "case_count": len(case_ids),
        "case_ids": list(case_ids), "corpus_manifest_hash": manifest_hash,
    }
    payload["subset_hash"] = stable_hash(payload)
    return payload


def build(dataset_root: Path, output_root: Path, render_index_path: Path) -> dict[str, Any]:
    dataset_manifest_path = dataset_root / "manifests" / "statue_dataset_manifest.json"
    dataset_manifest = read_json(dataset_manifest_path)
    if dataset_manifest.get("dataset_version") != "1.0.0" or dataset_manifest.get("asset_count") != 27:
        raise RuntimeError("CGB v0.1 requires exactly Dataset 1.0.0 with 27 assets.")
    assets = sorted(dataset_manifest["assets"], key=lambda item: item["unique_id"])
    ids = tuple(str(item["unique_id"]) for item in assets)
    if len(ids) != 27 or len(set(ids)) != 27:
        raise RuntimeError("Dataset manifest IDs are not a unique Full27 corpus.")
    for expected in CORE10 + SMOKE3:
        if expected not in ids:
            raise RuntimeError(f"Required existing representative case is missing: {expected}")
    before = {str(asset["unique_id"]): sha256_file(_source_path(dataset_root, asset)) for asset in assets}
    render_index = read_json(render_index_path) if render_index_path.is_file() else {}
    cases = [_case(asset, dataset_root, render_index) for asset in assets]
    after = {str(asset["unique_id"]): sha256_file(_source_path(dataset_root, asset)) for asset in assets}
    if before != after:
        raise RuntimeError("Source immutability failure while building CGB corpus.")
    payload = {
        "schema_version": "1.0.0", "cgb_version": CGB_VERSION,
        "corpus_id": "CGB-GT27", "source_dataset_name": dataset_manifest.get("dataset_name"),
        "source_dataset_version": "1.0.0", "source_manifest_sha256": sha256_file(dataset_manifest_path),
        "rights_cleared": True, "source_immutable": True, "source_mutation_count": 0,
        "case_count": len(cases), "render_config_hash": render_index.get("render_config_hash"),
        "rendered_case_count": sum(bool(case["reference_render_hashes"]) for case in cases),
        "cases": cases,
    }
    payload["corpus_hash"] = stable_hash(payload)
    write_json(output_root / "manifest.json", payload)
    write_json(output_root / "smoke3.json", _subset("CGB-SMOKE3", SMOKE3, payload["corpus_hash"]))
    write_json(output_root / "core10.json", _subset("CGB-CORE10", CORE10, payload["corpus_hash"]))
    write_json(output_root / "full27.json", _subset("CGB-FULL27", ids, payload["corpus_hash"]))
    text_prompts = {
        "schema_version": "1.0.0", "cgb_version": CGB_VERSION, "track": "C",
        "separate_from_ground_truth_reconstruction": True,
        "prompts": [
            {"prompt_id": "simple_object", "prompt": "A plain ceramic mug with one handle."},
            {"prompt_id": "organic_object", "prompt": "A natural branching coral specimen."},
            {"prompt_id": "hard_surface_object", "prompt": "A compact industrial gearbox housing."},
            {"prompt_id": "stylized_object", "prompt": "A stylized low-poly owl figurine."},
            {"prompt_id": "high_detail_statue", "prompt": "A high-detail stone statue of a robed scholar."},
            {"prompt_id": "character_bust", "prompt": "A heroic character bust with layered armor."},
            {"prompt_id": "thin_feature_object", "prompt": "An ornate wrought-iron lantern with thin curved bars."},
        ],
    }
    text_prompts["prompt_corpus_hash"] = stable_hash(text_prompts)
    write_json(output_root / "text_prompts.json", text_prompts)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=PROJECT_ROOT / ".validation-assets" / "dataset")
    parser.add_argument("--output-root", type=Path, default=GENERATIVE_ROOT / "corpus")
    parser.add_argument("--render-index", type=Path, default=VALIDATION_ROOT / "reference-renders" / "index.json")
    args = parser.parse_args()
    try:
        manifest = build(args.dataset_root.resolve(), args.output_root.resolve(), args.render_index.resolve())
    except Exception as exc:
        print(f"CGB corpus build failed: {type(exc).__name__}: {exc}")
        return 1
    print(json_summary(manifest))
    return 0


def json_summary(manifest: dict[str, Any]) -> str:
    return (
        f"CGB corpus PASS: cases={manifest['case_count']} rendered={manifest['rendered_case_count']} "
        f"source_mutations={manifest['source_mutation_count']} hash={manifest['corpus_hash']}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
