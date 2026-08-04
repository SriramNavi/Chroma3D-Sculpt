from __future__ import annotations

import hashlib
import json
import math
import statistics
import struct
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATASET_ROOT = REPOSITORY_ROOT / "datasets" / "statues"
RAW_ROOT = DATASET_ROOT / "raw"
PROCESSED_ROOT = DATASET_ROOT / "processed"
METADATA_ROOT = DATASET_ROOT / "metadata"
MANIFEST_ROOT = DATASET_ROOT / "manifests"
LICENSE_ROOT = DATASET_ROOT / "licenses"
REGRESSION_DOC = REPOSITORY_ROOT / "manual-tests" / "datasets" / "REAL_STATUE_DATASET.md"

DATASET_VERSION = "1.0.0"
MINIMUM_REASONABLE_VERTICES = 100
MINIMUM_REASONABLE_TRIANGLES = 100
MEBIBYTE = 1024 * 1024


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * MEBIBYTE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stl_structure(path: Path) -> dict[str, Any]:
    file_size = path.stat().st_size
    if file_size < 84:
        return {
            "encoding": "invalid",
            "declared_triangle_count": None,
            "binary_size_consistent": False,
        }

    with path.open("rb") as stream:
        header = stream.read(84)
    declared_triangles = struct.unpack("<I", header[80:84])[0]
    expected_binary_size = 84 + declared_triangles * 50
    if expected_binary_size == file_size:
        return {
            "encoding": "binary",
            "declared_triangle_count": declared_triangles,
            "binary_size_consistent": True,
        }

    with path.open("rb") as stream:
        start = stream.read(512).lstrip().lower()
        stream.seek(max(0, file_size - 512))
        end = stream.read(512).rstrip().lower()
    is_ascii = start.startswith(b"solid") and b"endsolid" in end
    return {
        "encoding": "ascii" if is_ascii else "unknown",
        "declared_triangle_count": None,
        "binary_size_consistent": None,
    }


def _clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def _import_stl(path: Path) -> tuple[list[bpy.types.Object], float]:
    before_ids = {id(item) for item in bpy.data.objects}
    started = time.perf_counter()
    result = bpy.ops.wm.stl_import(filepath=str(path))
    elapsed = time.perf_counter() - started
    if "FINISHED" not in result:
        raise RuntimeError(f"Blender STL importer returned {sorted(result)}")

    imported = [
        item
        for item in bpy.data.objects
        if id(item) not in before_ids and item.type == "MESH"
    ]
    if not imported:
        imported = [item for item in bpy.context.selected_objects if item.type == "MESH"]
    if not imported:
        raise RuntimeError("Blender importer produced no mesh objects")
    return imported, elapsed


def _mesh_statistics(objects: list[bpy.types.Object]) -> dict[str, Any]:
    vertex_count = 0
    edge_count = 0
    polygon_count = 0
    triangle_count = 0
    non_finite_vertex_count = 0
    bounds_min = Vector((math.inf, math.inf, math.inf))
    bounds_max = Vector((-math.inf, -math.inf, -math.inf))

    for obj in objects:
        mesh = obj.data
        mesh.calc_loop_triangles()
        vertex_count += len(mesh.vertices)
        edge_count += len(mesh.edges)
        polygon_count += len(mesh.polygons)
        triangle_count += len(mesh.loop_triangles)
        non_finite_vertex_count += sum(
            1
            for vertex in mesh.vertices
            if not all(math.isfinite(component) for component in vertex.co)
        )
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ Vector(corner)
            for axis in range(3):
                bounds_min[axis] = min(bounds_min[axis], world_corner[axis])
                bounds_max[axis] = max(bounds_max[axis], world_corner[axis])

    dimensions = bounds_max - bounds_min
    diagonal = dimensions.length
    finite_bounds = all(
        math.isfinite(component)
        for component in (*bounds_min, *bounds_max, *dimensions, diagonal)
    )
    return {
        "object_count": len(objects),
        "vertex_count": vertex_count,
        "edge_count": edge_count,
        "polygon_count": polygon_count,
        "triangle_count": triangle_count,
        "non_finite_vertex_count": non_finite_vertex_count,
        "bounding_box": {
            "coordinate_space": "Blender world space after default STL import",
            "source_units": "unspecified",
            "minimum": [round(float(value), 9) for value in bounds_min],
            "maximum": [round(float(value), 9) for value in bounds_max],
            "dimensions": [round(float(value), 9) for value in dimensions],
            "diagonal": round(float(diagonal), 9),
        },
        "finite_bounds": finite_bounds,
    }


def _validate_metadata(path: Path) -> tuple[dict[str, Any], str | None]:
    metadata = _read_json(path)
    raw_path = REPOSITORY_ROOT / metadata["stored_path"]
    failure = None
    started = time.perf_counter()
    structure = _stl_structure(raw_path)

    try:
        if not raw_path.is_file() or raw_path.stat().st_size == 0:
            raise RuntimeError("raw mesh is missing or empty")
        checksum = _hash_file(raw_path)
        if checksum != metadata["checksum_sha256"]:
            raise RuntimeError("SHA-256 differs from acquisition metadata")
        if structure["encoding"] not in {"binary", "ascii"}:
            raise RuntimeError("STL encoding is not recognized")

        objects, import_seconds = _import_stl(raw_path)
        mesh_stats = _mesh_statistics(objects)
        declared_triangles = structure["declared_triangle_count"]
        triangle_count_matches_header = (
            declared_triangles is None
            or declared_triangles == mesh_stats["triangle_count"]
        )
        triangle_count_delta_from_header = (
            None
            if declared_triangles is None
            else declared_triangles - mesh_stats["triangle_count"]
        )
        reasonable = (
            mesh_stats["vertex_count"] >= MINIMUM_REASONABLE_VERTICES
            and mesh_stats["triangle_count"] >= MINIMUM_REASONABLE_TRIANGLES
            and mesh_stats["finite_bounds"]
            and mesh_stats["bounding_box"]["diagonal"] > 0.0
            and mesh_stats["non_finite_vertex_count"] == 0
        )
        if not reasonable:
            raise RuntimeError("mesh failed the bounded reasonableness checks")

        metadata["vertex_count"] = mesh_stats["vertex_count"]
        metadata["triangle_count"] = mesh_stats["triangle_count"]
        metadata["bounding_box"] = mesh_stats["bounding_box"]
        metadata["validation"] = {
            "status": "validated",
            "validated_at_utc": datetime.now(timezone.utc).isoformat(),
            "validator": f"Blender {bpy.app.version_string} native STL importer",
            "readable": True,
            "non_empty": True,
            "reasonable_mesh": True,
            "obvious_corruption": False,
            "stl_encoding": structure["encoding"],
            "binary_size_consistent": structure["binary_size_consistent"],
            "declared_triangle_count": declared_triangles,
            "triangle_count_matches_header": triangle_count_matches_header,
            "triangle_count_delta_from_header": triangle_count_delta_from_header,
            "imported_object_count": mesh_stats["object_count"],
            "edge_count": mesh_stats["edge_count"],
            "polygon_count": mesh_stats["polygon_count"],
            "non_finite_vertex_count": mesh_stats["non_finite_vertex_count"],
            "import_seconds": round(import_seconds, 6),
            "validation_seconds": round(time.perf_counter() - started, 6),
            "checks": [
                "File exists and is non-empty.",
                "Current SHA-256 matches acquisition metadata.",
                "STL container structure is recognized.",
                "Blender native importer completed and produced mesh data.",
                "Vertex and triangle counts exceed bounded minimums.",
                "All imported vertex coordinates and bounds are finite.",
                "Bounding-box diagonal is non-zero.",
                (
                    "Binary STL header/import triangle delta is recorded; Blender "
                    "may omit duplicate or degenerate facets during import."
                ),
            ],
            "warnings": (
                []
                if triangle_count_matches_header
                else [
                    (
                        "Blender imported "
                        f"{triangle_count_delta_from_header} fewer triangles than "
                        "the binary STL header declared, consistent with importer "
                        "cleanup of duplicate or degenerate facets."
                    )
                ]
            ),
        }
    except Exception as exc:
        failure = str(exc)
        metadata["validation"] = {
            "status": "rejected",
            "validated_at_utc": datetime.now(timezone.utc).isoformat(),
            "validator": f"Blender {bpy.app.version_string} native STL importer",
            "readable": False,
            "non_empty": raw_path.is_file() and raw_path.stat().st_size > 0,
            "reasonable_mesh": False,
            "obvious_corruption": True,
            "stl_encoding": structure["encoding"],
            "failure": failure,
            "validation_seconds": round(time.perf_counter() - started, 6),
        }
    finally:
        _clear_scene()

    _write_json(path, metadata)
    return metadata, failure


def _counter(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(item[field]) for item in items).items()))


def _size_band(size_bytes: int) -> str:
    if size_bytes < 10 * MEBIBYTE:
        return "small_under_10_mib"
    if size_bytes < 50 * MEBIBYTE:
        return "medium_10_to_50_mib"
    return "large_50_mib_or_more"


def _triangle_band(triangle_count: int) -> str:
    if triangle_count < 100_000:
        return "small_under_100k"
    if triangle_count < 1_000_000:
        return "medium_100k_to_1m"
    return "large_1m_or_more"


def _distribution(
    assets: list[dict[str, Any]],
    value_field: str,
    band_function: Any,
) -> dict[str, int]:
    return dict(
        sorted(Counter(band_function(int(item[value_field])) for item in assets).items())
    )


def _summary_statistics(assets: list[dict[str, Any]]) -> dict[str, Any]:
    sizes = [int(item["file_size_bytes"]) for item in assets]
    triangles = [int(item["triangle_count"]) for item in assets]
    vertices = [int(item["vertex_count"]) for item in assets]
    return {
        "total_size_bytes": sum(sizes),
        "minimum_size_bytes": min(sizes),
        "median_size_bytes": int(statistics.median(sizes)),
        "maximum_size_bytes": max(sizes),
        "total_vertices": sum(vertices),
        "minimum_vertices": min(vertices),
        "median_vertices": int(statistics.median(vertices)),
        "maximum_vertices": max(vertices),
        "total_triangles": sum(triangles),
        "minimum_triangles": min(triangles),
        "median_triangles": int(statistics.median(triangles)),
        "maximum_triangles": max(triangles),
    }


def _build_manifest(
    assets: list[dict[str, Any]],
    validation_failures: list[dict[str, str]],
    generated_at: str,
) -> dict[str, Any]:
    rejected = _read_json(METADATA_ROOT / "rejected_assets.json")
    statistics_payload = _summary_statistics(assets)
    return {
        "dataset_version": DATASET_VERSION,
        "creation_date": generated_at[:10],
        "generated_at_utc": generated_at,
        "dataset_purpose": (
            "Rights-cleared real statue meshes for Chroma3D regression, repair "
            "validation, diagnostics, benchmarking, and future governed research."
        ),
        "asset_count": len(assets),
        "validated_asset_count": len(assets),
        "validation_rejected_asset_count": len(validation_failures),
        "policy_rejected_candidate_count": len(rejected["policy_rejections"]),
        "license_summary": _counter(assets, "license"),
        "category_summary": _counter(assets, "category"),
        "format_summary": _counter(assets, "file_format"),
        "size_distribution": _distribution(
            assets, "file_size_bytes", _size_band
        ),
        "triangle_distribution": _distribution(
            assets, "triangle_count", _triangle_band
        ),
        "statistics": statistics_payload,
        "validation": {
            "blender_version": bpy.app.version_string,
            "method": (
                "SHA-256 recheck, STL container inspection, and isolated native "
                "Blender import with finite geometry and count checks."
            ),
            "production_diagnostics_executed": False,
            "repair_operations_executed": False,
            "failures": validation_failures,
        },
        "assets": assets,
    }


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        cells = [str(value).replace("|", "\\|").replace("\n", " ") for value in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _format_mib(size_bytes: int) -> str:
    return f"{size_bytes / MEBIBYTE:,.2f} MiB"


def _write_dataset_summary(
    manifest: dict[str, Any],
    acquisition_report: dict[str, Any],
) -> None:
    stats = manifest["statistics"]
    rejected = _read_json(METADATA_ROOT / "rejected_assets.json")
    license_rows = [
        [license_name, count]
        for license_name, count in manifest["license_summary"].items()
    ]
    category_rows = [
        [category, count]
        for category, count in manifest["category_summary"].items()
    ]
    size_rows = [
        [band, count] for band, count in manifest["size_distribution"].items()
    ]
    triangle_rows = [
        [band, count] for band, count in manifest["triangle_distribution"].items()
    ]
    rejection_rows = [
        [item["title"], item["license"], item["reason"]]
        for item in rejected["policy_rejections"]
    ] + [
        [item["unique_id"], "N/A", item["reason"]]
        for item in rejected["acquisition_failures"]
    ] + [
        [item["unique_id"], "N/A", item["reason"]]
        for item in manifest["validation"]["failures"]
    ]

    content = f"""# Real Statue Dataset Summary

## Outcome

- Downloaded: {acquisition_report["downloaded_asset_count"]} meshes
- Validated and accepted: {manifest["asset_count"]} meshes
- Acquisition failures: {acquisition_report["acquisition_failure_count"]}
- Validation failures: {manifest["validation_rejected_asset_count"]}
- Policy or curation rejections: {manifest["policy_rejected_candidate_count"]}
- Raw mesh size: {_format_mib(stats["total_size_bytes"])}
- SHA-256 status: generated and rechecked for every accepted mesh
- Blender readability status: every accepted mesh imported successfully in Blender {manifest["validation"]["blender_version"]}

## Licenses

{_markdown_table(["License", "Accepted assets"], license_rows)}

Official license texts are retained under `datasets/statues/licenses/`. Per-asset
attribution and immutable source-revision links are in `ATTRIBUTIONS.md` and the
individual metadata JSON files.

## Categories

{_markdown_table(["Category", "Assets"], category_rows)}

## Formats

{_markdown_table(["Format", "Assets"], [[key, value] for key, value in manifest["format_summary"].items()])}

All accepted assets are STL files. The single-format baseline is deliberate: it
keeps Sprint 2.5 import comparisons controlled. OBJ, PLY, FBX, GLB, and GLTF
coverage remains a future dataset expansion, not a validation claim.

## Size Distribution

{_markdown_table(["Raw file band", "Assets"], size_rows)}

- Minimum: {_format_mib(stats["minimum_size_bytes"])}
- Median: {_format_mib(stats["median_size_bytes"])}
- Maximum: {_format_mib(stats["maximum_size_bytes"])}

## Triangle Distribution

{_markdown_table(["Triangle band", "Assets"], triangle_rows)}

- Minimum: {stats["minimum_triangles"]:,}
- Median: {stats["median_triangles"]:,}
- Maximum: {stats["maximum_triangles"]:,}
- Total: {stats["total_triangles"]:,}

Counts are produced by Blender's native STL importer. STL triangle soups can
import with merged vertices, so vertex counts are Blender-import counts rather
than counts claimed by source websites.

## Rejected Candidates

{_markdown_table(["Candidate", "License", "Reason"], rejection_rows)}

## Known Issues and Limits

- Source units are not reliably declared by STL; bounding boxes are recorded in
  Blender world coordinates after default import with units marked unspecified.
- Blender may omit duplicate or degenerate STL facets during import. Per-asset
  binary-header/import triangle deltas are retained as warnings rather than
  misreported as corruption when the remaining mesh is finite and reasonable.
- The corpus contains culturally and religiously significant subjects. Use
  respectful labels, retain provenance, and do not infer theological meaning
  from geometry alone.
- CC BY and CC BY-SA items require attribution; adapted CC BY-SA distributions
  also require the applicable share-alike terms.
- Source thumbnails are provenance previews from Wikimedia Commons, not
  regression renders and not evidence of mesh validity.
- No Chroma3D production diagnostics or repair operations were executed while
  constructing this dataset. Inclusion is not a printability or repair-success
  claim.
- `processed/` intentionally contains no derived geometry. Raw source meshes are
  preserved byte-for-byte under their recorded SHA-256 values.
- The 2.88 GiB full-resolution Cosmic Buddha was excluded in favor of the
  Smithsonian 150k derivative to keep the baseline dataset practical.
"""
    (DATASET_ROOT / "DATASET_SUMMARY.md").write_text(content, encoding="utf-8")


def _write_attributions(assets: list[dict[str, Any]], generated_at: str) -> None:
    rows = []
    for item in sorted(assets, key=lambda asset: asset["title"].casefold()):
        author = item["author"] or "Not stated on source page"
        rows.append(
            [
                item["title"],
                author,
                item["license"],
                f"[source revision]({item['source_revision_url']})",
                item["unique_id"],
            ]
        )
    content = f"""# Statue Dataset Attributions

Generated from model-level Wikimedia Commons metadata on {generated_at[:10]}.
The source-revision links preserve the license and attribution evidence used at
acquisition time. This file is a convenience index; the per-asset metadata JSON
is authoritative for local provenance.

{_markdown_table(["Title", "Author / credited creator", "License", "Source", "Dataset ID"], rows)}
"""
    (LICENSE_ROOT / "ATTRIBUTIONS.md").write_text(content, encoding="utf-8")


def _write_license_index(assets: list[dict[str, Any]]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in assets:
        grouped.setdefault(item["license"], []).append(item)
    rows = []
    for identifier, items in sorted(grouped.items()):
        first = items[0]
        local_name = Path(first["license_document"]).name
        rows.append(
            [
                identifier,
                len(items),
                f"[official terms]({first['license_url']})",
                f"`{local_name}`",
            ]
        )
    content = f"""# License Index

Only model files with explicit commercial-use-compatible terms were admitted.
Wikimedia Commons category membership alone was not treated as license proof;
each file's model-level metadata and source-page revision were recorded.

{_markdown_table(["License", "Assets", "Canonical URL", "Local legal text"], rows)}

## Redistribution

- Preserve `ATTRIBUTIONS.md` and all per-asset metadata when redistributing this
  corpus or a subset.
- Follow attribution requirements for CC BY 4.0.
- Follow attribution and share-alike requirements for CC BY-SA 4.0 adaptations.
- CC0 assets do not require attribution, but provenance should still be retained
  for scientific reproducibility.
- Recheck the recorded source revision and consult qualified legal advice for
  high-risk commercial or culturally sensitive uses.
"""
    (LICENSE_ROOT / "LICENSE_INDEX.md").write_text(content, encoding="utf-8")


def _write_dataset_readme(manifest: dict[str, Any]) -> None:
    content = f"""# Chroma3D Real Statue Validation Dataset

## Purpose

This versioned corpus contains {manifest["asset_count"]} rights-cleared, real or
documented heritage statue meshes for regression testing, repair validation,
diagnostic evaluation, performance benchmarking, and future governed research.
It is test data only and is not loaded by the Chroma3D production extension.

Dataset version: `{manifest["dataset_version"]}`

## Directory Structure

```text
datasets/statues/
├── raw/          Original downloaded meshes; never modify in place
├── processed/    Reserved for documented derived meshes
├── metadata/     One JSON record per accepted asset plus rejected candidates
├── thumbnails/   Source-provided preview images for human identification
├── manifests/    Dataset manifest and acquisition report
└── licenses/     Official license texts, index, and attribution table
```

## License and Provenance Policy

Every accepted model must be publicly downloadable without bypassing access
controls and must have explicit CC0, CC BY, CC BY-SA, public-domain, MIT,
Apache, or equivalent commercial-use-compatible terms. Unknown, noncommercial,
no-redistribution, paid, private, login-only, and ambiguous assets are rejected.

Each metadata record preserves the source page, exact source-page revision,
download URL, acquisition time, author/credit, canonical license URL, original
and stored filenames, file size, Wikimedia SHA-1 where supplied, local SHA-256,
and validation evidence. Raw meshes are immutable source evidence.

## Adding an Asset

1. Review the model-level license and redistribution terms, not only the host's
   general policy or a search-result label.
2. Add one bounded `CuratedAsset` entry to
   `manual-tests/datasets/acquire_statue_dataset.py`.
3. Run the acquisition script from the repository root.
4. Run the Blender validation command below.
5. Review the per-asset metadata, source revision, attribution entry, manifest
   summaries, and any rejected-asset evidence.
6. Never overwrite an existing raw asset under the same ID if its SHA-256 has
   changed; assign a new dataset version and document the change.

## Validation

Acquisition:

```powershell
py manual-tests\\datasets\\acquire_statue_dataset.py
```

Structural validation with the repository's Blender installation:

```powershell
& "D:\\Softwares\\Design\\Blender\\blender.exe" `
  --background `
  --factory-startup `
  --python-exit-code 1 `
  --python "manual-tests\\datasets\\validate_statue_dataset.py"
```

The validator rechecks SHA-256, recognizes STL container structure, imports each
file in an isolated factory-startup Blender process, confirms finite/non-empty
mesh data, compares binary-header/imported triangle counts, records Blender
vertex/triangle counts and world-space bounds, and rebuilds the manifest and
documentation. It does not call Chroma3D diagnostics or repairs.

## Citation

For an individual mesh, cite its title, credited author or institution, original
repository, license, and recorded source-revision URL from the asset metadata.
For the corpus, cite:

> Chroma3D Sculpt Real Statue Validation Dataset, version
> {manifest["dataset_version"]}, created {manifest["creation_date"]}, with
> per-asset provenance in `datasets/statues/metadata/`.

Keep `licenses/ATTRIBUTIONS.md` with any redistributed subset and comply with
the applicable attribution/share-alike obligations.

## Safety and Interpretation

Dataset acceptance means the file is rights-cleared for the stated terms,
byte-verified, readable, non-empty, finite, and structurally reasonable. It does
not mean watertight, printable, diagnostically clean, culturally neutral, or
safe for automatic repair. Always use an independent repair workspace and
retain the protected raw source.
"""
    (DATASET_ROOT / "README.md").write_text(content, encoding="utf-8")


def _asset_line(item: dict[str, Any]) -> str:
    return (
        f"- `{item['unique_id']}` — {item['title']} "
        f"({item['triangle_count']:,} triangles, "
        f"{_format_mib(item['file_size_bytes'])})"
    )


def _write_regression_doc(assets: list[dict[str, Any]]) -> None:
    by_triangles = sorted(assets, key=lambda item: item["triangle_count"])
    small = by_triangles[:6]
    medium_start = max(0, len(by_triangles) // 2 - 3)
    medium = by_triangles[medium_start : medium_start + 6]
    large = list(reversed(by_triangles[-6:]))
    by_id = {item["unique_id"]: item for item in assets}

    def selected(*identifiers: str) -> list[dict[str, Any]]:
        return [by_id[item_id] for item_id in identifiers if item_id in by_id]

    repair_stress = selected(
        "statue-laocoon-group",
        "statue-pieta-michelangelo",
        "statue-hizen-komainu",
        "statue-thinker-rodin",
        "statue-uma-maheshvara-java-10c",
        "statue-water-buffalo-boy",
    )
    diagnostic_stress = selected(
        "statue-hizen-komainu",
        "statue-dainichi-nyorai-tower",
        "statue-bato-kannon-shirane",
        "statue-belvedere-torso",
        "statue-asad-al-lat",
        "statue-venus-de-milo",
    )
    benchmark = [
        small[0],
        small[len(small) // 2],
        medium[0],
        medium[-1],
        large[-1],
        large[0],
    ]
    content = f"""# Real Statue Dataset Regression Guide

## Scope

This guide orders the dataset for manual and future automated regression work.
Sprint 2.5 validates the corpus itself; it does not claim that Chroma3D
diagnostics or repairs have passed on these meshes.

## Recommended Regression Order

1. Confirm the raw file SHA-256 against its metadata.
2. Import a small case and complete read-only analysis under operator review.
3. Progress through medium and large cases while recording wall time, CPU state,
   memory, analysis profile, warnings, and failures.
4. Start repair sessions only on independent workspace copies.
5. Exercise one approved operation at a time before mixed-operation sequences.
6. Retain before/after reports, source/workspace signatures, checkpoints, and
   operator decisions. Never promote a skipped or failed check as a pass.

## Small Meshes

{chr(10).join(_asset_line(item) for item in small)}

Use these first for importer, registration, report-schema, selection, session,
failure-recovery, and quick operator-flow checks.

## Medium Meshes

{chr(10).join(_asset_line(item) for item in medium)}

Use these for routine Standard/Deep timing, evidence bounds, undo/restore, and
before/after comparison with representative organic detail.

## Large Meshes

{chr(10).join(_asset_line(item) for item in large)}

Use these only after the small/medium sequence passes. Record AC status, CPU
frequency/performance, RAM, paging, process count, and CPU-versus-wall time.

## Repair Stress Models

{chr(10).join(_asset_line(item) for item in repair_stress)}

These models have group compositions, drapery, weathering, extended forms, or
high density that may expose workspace-copy, checkpoint, mapping, and
detail-preservation risks. Candidate presence is not guaranteed; never force an
operation when the plan is empty, stale, ambiguous, or ineligible.

## Diagnostic Stress Models

{chr(10).join(_asset_line(item) for item in diagnostic_stress)}

These include weathered photogrammetry, fragments, monuments, reconstructed
heritage, and high-density surfaces. Treat Deep output as bounded heuristic
evidence, not printability, wall-thickness, or repair proof.

## Future Benchmark Models

{chr(10).join(_asset_line(item) for item in benchmark)}

This six-case ladder spans the observed corpus. A future benchmark record should
include asset SHA-256, Blender and Chroma3D versions, machine/power state,
profile/settings, import time, analysis time, repair time by operation, peak
memory when available, outcome, warnings, and retained report paths.

## Manual Evidence Checklist

- Work from `datasets/statues/raw/` as immutable source evidence.
- Verify source and workspace signatures before every geometry mutation.
- Confirm the source remains byte/geometry unchanged after every operation.
- Capture actual diagnostics; do not infer expected defects from file size.
- Review faces, fingers, jewelry, inscriptions, drapery, thin forms, and
  culturally significant attributes for visible loss.
- Record accepted, rejected, ambiguous, no-op, skipped, and failed outcomes
  separately.
- Use the model's metadata title and classification respectfully in reports.
"""
    REGRESSION_DOC.write_text(content, encoding="utf-8")


def _write_processed_readme() -> None:
    content = """# Processed Statue Meshes

This directory is intentionally empty of derived geometry in dataset version
1.0.0. Sprint 2.5 preserves downloaded files byte-for-byte under `../raw/`.

Future processed assets must use a new filename and metadata record that links
to the protected raw source, records every transformation/tool/version, carries
forward the applicable license and attribution, and includes new checksums and
validation evidence. Never overwrite a raw asset.
"""
    (PROCESSED_ROOT / "README.md").write_text(content, encoding="utf-8")


def main() -> int:
    _clear_scene()
    metadata_paths = sorted(
        path
        for path in METADATA_ROOT.glob("statue-*.json")
        if path.name != "rejected_assets.json"
    )
    validated = []
    validation_failures = []
    for path in metadata_paths:
        metadata, failure = _validate_metadata(path)
        if failure is None:
            validated.append(metadata)
            print(
                f"VALIDATED {metadata['unique_id']} "
                f"{metadata['vertex_count']}v/{metadata['triangle_count']}t"
            )
        else:
            validation_failures.append(
                {"unique_id": metadata["unique_id"], "reason": failure}
            )
            print(f"REJECTED {metadata['unique_id']}: {failure}")

    generated_at = datetime.now(timezone.utc).isoformat()
    manifest = _build_manifest(validated, validation_failures, generated_at)
    manifest_path = MANIFEST_ROOT / "statue_dataset_manifest.json"
    _write_json(manifest_path, manifest)

    acquisition_report = _read_json(MANIFEST_ROOT / "acquisition_report.json")
    _write_dataset_summary(manifest, acquisition_report)
    _write_attributions(validated, generated_at)
    _write_license_index(validated)
    _write_dataset_readme(manifest)
    _write_regression_doc(validated)
    _write_processed_readme()

    print(
        f"Validated {len(validated)}/{len(metadata_paths)} assets; "
        f"{len(validation_failures)} rejected."
    )
    return 0 if not validation_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
