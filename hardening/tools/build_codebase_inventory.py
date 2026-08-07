"""Build a deterministic inventory of the pre-hardening checkpoint."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    BASELINE_ROOT,
    CHECKPOINT_COMMIT,
    CHECKPOINT_TAG,
    HARDENING_EXCLUSIONS,
    REPOSITORY_ROOT,
    REPORT_ROOT,
    checkpoint_paths,
    line_count,
    markdown_table,
    parse_python,
    relative,
    utc_now,
    write_json,
    write_text,
)


def _is_dataclass(node: ast.ClassDef) -> bool:
    return any(
        (isinstance(item, ast.Name) and item.id == "dataclass")
        or (isinstance(item, ast.Call) and isinstance(item.func, ast.Name) and item.func.id == "dataclass")
        for item in node.decorator_list
    )


def _base_names(node: ast.ClassDef) -> set[str]:
    return {
        base.id if isinstance(base, ast.Name) else base.attr
        for base in node.bases
        if isinstance(base, (ast.Name, ast.Attribute))
    }


def build_inventory() -> dict[str, object]:
    scripts_path = str(REPOSITORY_ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    from _project import PACKAGE_ASSET_FILES  # noqa: PLC0415

    paths = checkpoint_paths()
    records: list[dict[str, object]] = []
    class_counts = {"operators": 0, "panels": 0, "models_or_dataclasses": 0}
    for name in paths:
        path = REPOSITORY_ROOT / name
        if not path.is_file():
            continue
        size = path.stat().st_size
        lines = 0
        if path.suffix.lower() in {".py", ".md", ".json", ".toml", ".ps1"}:
            lines = line_count(path.read_text(encoding="utf-8", errors="replace"))
        records.append({"path": name, "bytes": size, "lines": lines, "suffix": path.suffix.lower()})
        if path.suffix.lower() == ".py":
            try:
                tree = parse_python(path)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                bases = _base_names(node)
                if "Operator" in bases:
                    class_counts["operators"] += 1
                if "Panel" in bases:
                    class_counts["panels"] += 1
                if _is_dataclass(node) or bases.intersection({"Enum", "str", "IntEnum"}) or "/models/" in name:
                    class_counts["models_or_dataclasses"] += 1

    python = [item for item in records if item["suffix"] == ".py"]
    source_python = [item for item in python if str(item["path"]).startswith("blender_addon/chroma3d_sculpt/")]
    package_sources = [item for item in records if str(item["path"]).startswith("blender_addon/chroma3d_sculpt/")]
    packaged_asset_paths = set(PACKAGE_ASSET_FILES)
    package_assets = [item for item in records if str(item["path"]) in packaged_asset_paths]
    largest_sources = sorted(python, key=lambda item: (-int(item["lines"]), str(item["path"])))[:20]
    large_tracked = sorted(
        (item for item in records if int(item["bytes"]) >= 1024 * 1024),
        key=lambda item: (-int(item["bytes"]), str(item["path"])),
    )
    counts = {
        "tracked_files": len(records),
        "python_source_files": len(python),
        "python_physical_loc": sum(int(item["lines"]) for item in python),
        "markdown_files": sum(str(item["path"]).endswith(".md") for item in records),
        "json_schema_files": sum(str(item["path"]).endswith(".schema.json") for item in records),
        "powershell_files": sum(str(item["path"]).endswith(".ps1") for item in records),
        "package_source_files": len(package_sources),
        "package_python_modules": len(source_python),
        "test_source_files": sum(str(item["path"]).startswith("tests/") and str(item["path"]).endswith(".py") for item in records),
        "manual_test_files": sum(str(item["path"]).startswith("manual-tests/") for item in records),
        "service_modules": sum(str(item["path"]).startswith("blender_addon/chroma3d_sculpt/services/") and str(item["path"]).endswith(".py") for item in records),
        "operator_classes": class_counts["operators"],
        "panel_classes": class_counts["panels"],
        "models_or_dataclasses": class_counts["models_or_dataclasses"],
        "utility_modules": sum(str(item["path"]).startswith("blender_addon/chroma3d_sculpt/utilities/") and str(item["path"]).endswith(".py") for item in records),
        "schema_files": sum(str(item["path"]).startswith("schemas/") and str(item["path"]).endswith(".json") for item in records),
        "printer_profiles": sum(str(item["path"]).startswith("profiles/printability/") and str(item["path"]).endswith(".json") for item in records),
        "material_profiles": sum(str(item["path"]).startswith("profiles/materials/") and str(item["path"]).endswith(".json") for item in records),
        "package_file_count_expected": len(package_sources) + len(package_assets) + 1,
        "large_tracked_files_1mib": len(large_tracked),
        "python_files_over_500_loc": sum(int(item["lines"]) > 500 for item in python),
        "python_files_over_1000_loc": sum(int(item["lines"]) > 1000 for item in python),
    }
    return {
        "schema_version": "1.0.0",
        "generated_at": utc_now(),
        "checkpoint_tag": CHECKPOINT_TAG,
        "checkpoint_commit": CHECKPOINT_COMMIT,
        "loc_definition": "physical lines from UTF-8-decoded tracked Python files",
        "hardening_exclusions": list(HARDENING_EXCLUSIONS),
        "counts": counts,
        "largest_python_sources": largest_sources,
        "large_tracked_files": large_tracked,
        "files_over_500_loc": [item for item in largest_sources if int(item["lines"]) > 500],
        "files_over_1000_loc": [item for item in largest_sources if int(item["lines"]) > 1000],
        "classification_note": "File size is a review signal only and is not classified as a defect.",
    }


def render_markdown(report: dict[str, object]) -> str:
    counts = report["counts"]
    assert isinstance(counts, dict)
    rows = [(key.replace("_", " ").title(), value) for key, value in counts.items()]
    largest = report["largest_python_sources"]
    assert isinstance(largest, list)
    return "\n".join((
        "# Codebase Inventory",
        "",
        f"Checkpoint: `{report['checkpoint_tag']}` / `{report['checkpoint_commit']}`.",
        "",
        "Counts describe the immutable pre-hardening checkpoint. H0 files and generated evidence are excluded.",
        "",
        markdown_table(("Metric", "Value"), rows),
        "",
        "## Largest Python review targets",
        "",
        markdown_table(("Path", "LOC", "Bytes"), ((item["path"], item["lines"], item["bytes"]) for item in largest)),
        "",
        "Size alone is not a defect. These files are review targets for later phases only.",
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPORT_ROOT / "codebase_inventory.json")
    parser.add_argument("--markdown", type=Path, default=BASELINE_ROOT / "CODEBASE_INVENTORY.md")
    args = parser.parse_args()
    report = build_inventory()
    write_json(args.output, report)
    write_text(args.markdown, render_markdown(report))
    print(f"codebase inventory: {report['counts']['tracked_files']} tracked files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
