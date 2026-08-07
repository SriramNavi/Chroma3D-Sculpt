"""Capture public operator, schema, profile, enum, and serialization contracts."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import sys
import tomllib

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    BASELINE_ROOT,
    CHECKPOINT_COMMIT,
    CHECKPOINT_TAG,
    PRODUCT_VERSION,
    REPOSITORY_ROOT,
    SOURCE_ROOT,
    markdown_table,
    relative,
    sha256_json,
    utc_now,
    write_json,
    write_text,
)


def _bases(node: ast.ClassDef) -> set[str]:
    return {
        item.id if isinstance(item, ast.Name) else item.attr
        for item in node.bases
        if isinstance(item, (ast.Name, ast.Attribute))
    }


def _literal_string(node: ast.AST | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _class_assignment(node: ast.ClassDef, name: str) -> str | None:
    for item in node.body:
        if isinstance(item, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name for target in item.targets):
            return _literal_string(item.value)
    return None


def capture() -> dict[str, object]:
    operators: list[dict[str, str]] = []
    panels: list[dict[str, str]] = []
    properties: set[str] = set()
    enums: list[dict[str, object]] = []
    serialized: set[str] = set()
    metadata_versions: dict[str, str] = {}
    feature_flags: set[str] = set()

    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        rel = relative(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                bases = _bases(node)
                bl_idname = _class_assignment(node, "bl_idname")
                if "Operator" in bases and bl_idname:
                    operators.append({"class": node.name, "bl_idname": bl_idname, "file": rel})
                if "Panel" in bases and bl_idname:
                    panels.append({"class": node.name, "panel_id": bl_idname, "file": rel})
                if "PropertyGroup" in bases:
                    for item in node.body:
                        target = item.target if isinstance(item, ast.AnnAssign) else None
                        if isinstance(target, ast.Name):
                            properties.add(target.id)
                if bases.intersection({"Enum", "IntEnum", "StrEnum"}):
                    members = []
                    for item in node.body:
                        if isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name):
                            value = ast.literal_eval(item.value) if isinstance(item.value, ast.Constant) else ast.unparse(item.value)
                            members.append({"name": item.targets[0].id, "value": value})
                    enums.append({"enum": node.name, "file": rel, "members": members})
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                value = node.value
                for target in targets:
                    if isinstance(target, ast.Name) and target.id.endswith(("SCHEMA_VERSION", "VERSION")):
                        literal = _literal_string(value)
                        if literal is not None:
                            metadata_versions[target.id] = literal
                    if isinstance(target, ast.Name) and ("FEATURE" in target.id or target.id.endswith(("FLAG_NAMES", "FLAGS"))):
                        try:
                            literal_value = ast.literal_eval(value)
                        except (ValueError, TypeError):
                            literal_value = None
                        if isinstance(literal_value, dict):
                            feature_flags.update(str(key) for key in literal_value)
                        elif isinstance(literal_value, (tuple, list, set)):
                            feature_flags.update(str(value) for value in literal_value)
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key in node.keys:
                    value = _literal_string(key)
                    if value and len(value) <= 80 and not value.startswith(("http://", "https://")):
                        serialized.add(value)

    schemas = []
    for path in sorted((REPOSITORY_ROOT / "schemas").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        top_properties = sorted((data.get("properties") or {}).keys()) if isinstance(data, dict) else []
        serialized.update(top_properties)
        schemas.append({
            "path": relative(path),
            "id": data.get("$id") if isinstance(data, dict) else None,
            "title": data.get("title") if isinstance(data, dict) else None,
            "schema_version": data.get("schema_version") if isinstance(data, dict) else None,
            "top_level_properties": top_properties,
        })

    profiles = []
    for folder in (REPOSITORY_ROOT / "profiles" / "printability", REPOSITORY_ROOT / "profiles" / "materials"):
        for path in sorted(folder.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            identifier = next((data.get(key) for key in ("profile_id", "id", "material_id") if isinstance(data, dict) and data.get(key)), None)
            profiles.append({"path": relative(path), "id": identifier})

    manifest = tomllib.loads((SOURCE_ROOT / "blender_manifest.toml").read_text(encoding="utf-8"))
    contract = {
        "product_version": PRODUCT_VERSION,
        "operator_bl_idnames": sorted(operators, key=lambda item: item["bl_idname"]),
        "panel_ids": sorted(panels, key=lambda item: item["panel_id"]),
        "property_names": sorted(properties),
        "manifest": {
            "id": manifest.get("id"),
            "schema_version": manifest.get("schema_version"),
            "version": manifest.get("version"),
            "type": manifest.get("type"),
            "blender_version_min": manifest.get("blender_version_min"),
        },
        "metadata_versions": dict(sorted(metadata_versions.items())),
        "schemas": schemas,
        "package_module_roots": ["chroma3d_sculpt", "profiles", "schemas"],
        "profile_ids": profiles,
        "feature_flag_ids": sorted(feature_flags),
        "status_and_result_enums": sorted(enums, key=lambda item: (str(item["file"]), str(item["enum"]))),
        "important_serialized_keys": sorted(serialized),
    }
    return {
        "schema_version": "1.0.0",
        "generated_at": utc_now(),
        "checkpoint_tag": CHECKPOINT_TAG,
        "checkpoint_commit": CHECKPOINT_COMMIT,
        "contract_sha256": sha256_json(contract),
        **contract,
    }


def render(report: dict[str, object]) -> str:
    return "\n".join((
        "# Public Contract Baseline",
        "",
        f"Checkpoint: `{report['checkpoint_tag']}` / `{report['checkpoint_commit']}`.",
        "",
        f"Canonical contract SHA-256: `{report['contract_sha256']}`.",
        "",
        markdown_table(("Contract", "Count"), (
            ("Operator bl_idnames", len(report["operator_bl_idnames"])),
            ("Panel IDs", len(report["panel_ids"])),
            ("Property names", len(report["property_names"])),
            ("Metadata version constants", len(report["metadata_versions"])),
            ("Schema files", len(report["schemas"])),
            ("Profile IDs", len(report["profile_ids"])),
            ("Feature flag IDs", len(report["feature_flag_ids"])),
            ("Status/result enums", len(report["status_and_result_enums"])),
            ("Serialized keys", len(report["important_serialized_keys"])),
        )),
        "",
        "H1-H9 must compare this snapshot before removing or renaming a public operator, panel, property, schema, profile, flag, enum, or serialized key.",
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BASELINE_ROOT / "public_contract_baseline.json")
    parser.add_argument("--markdown", type=Path, default=BASELINE_ROOT / "PUBLIC_CONTRACT_BASELINE.md")
    args = parser.parse_args()
    report = capture()
    write_json(args.output, report)
    write_text(args.markdown, render(report))
    print(f"public contract: {len(report['operator_bl_idnames'])} operators, sha256={report['contract_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
