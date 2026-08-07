"""Build, validate, and fingerprint the current checkpoint package."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import re
import sys
import tomllib
import zipfile

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
    sha256_path,
    utc_now,
    write_json,
    write_text,
)

sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))
from _project import DISPLAY_VERSION, EXTENSION_ID, MANIFEST_VERSION, PACKAGE_PATH  # noqa: E402
from package_extension import build_package  # noqa: E402
from validate_package import validate_archive  # noqa: E402


def _external_runtime_roots() -> list[str]:
    internal = {"chroma3d_sculpt"}
    standard = set(getattr(sys, "stdlib_module_names", ()))
    roots: set[str] = set()
    for path in SOURCE_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return sorted(roots - internal - standard - {"__future__"})


def capture() -> dict[str, object]:
    package, built_count, built_size = build_package()
    errors = validate_archive(package)
    with zipfile.ZipFile(package, "r") as archive:
        names = sorted(name for name in archive.namelist() if not name.endswith("/"))
        manifest = tomllib.loads(archive.read("blender_manifest.toml").decode("utf-8"))
    forbidden = [
        name for name in names
        if "__pycache__" in name.lower().split("/")
        or name.lower().endswith((".pyc", ".pyo", ".env", ".pem", ".key", ".tmp"))
        or any(part in {"tests", "manual-tests", "scripts", ".git"} for part in name.lower().split("/"))
    ]
    checkpoint_text = (REPOSITORY_ROOT / "docs" / "releases" / "PRE_V1_HARDENING_CHECKPOINT.md").read_text(encoding="utf-8")
    retained_files = re.search(r"ZIP entries:\s*`([0-9,]+)`", checkpoint_text)
    retained_bytes = re.search(r"Size:\s*`([0-9,]+) bytes`", checkpoint_text)
    retained_sha = re.search(r"SHA-256:\s*`([a-f0-9]{64})`", checkpoint_text)
    retained = {
        "archive_file_count": int(retained_files.group(1).replace(",", "")) if retained_files else None,
        "archive_bytes": int(retained_bytes.group(1).replace(",", "")) if retained_bytes else None,
        "archive_sha256": retained_sha.group(1) if retained_sha else None,
        "evidence_source": "docs/releases/PRE_V1_HARDENING_CHECKPOINT.md",
    }
    current_sha = sha256_path(package)
    return {
        "schema_version": "1.0.0",
        "generated_at": utc_now(),
        "checkpoint_tag": CHECKPOINT_TAG,
        "checkpoint_commit": CHECKPOINT_COMMIT,
        "product_version": PRODUCT_VERSION,
        "extension_id": EXTENSION_ID,
        "extension_version": DISPLAY_VERSION,
        "manifest_version": manifest.get("version", MANIFEST_VERSION),
        "manifest_schema_version": manifest.get("schema_version"),
        "archive_filename": package.name,
        "archive_file_count": len(names),
        "archive_bytes": package.stat().st_size,
        "archive_sha256": current_sha,
        "builder_reported_file_count": built_count,
        "builder_reported_bytes": built_size,
        "source_module_count": sum(name.endswith(".py") for name in names),
        "schemas_included": [name for name in names if name.startswith("schemas/") and name.endswith(".json")],
        "profiles_included": [name for name in names if name.startswith("profiles/") and name.endswith(".json")],
        "docs_included": [name for name in names if name.lower().endswith(".md")],
        "forbidden_files": forbidden,
        "forbidden_files_absent": not forbidden,
        "repository_validator_errors": errors,
        "startup_registration_modules": [
            "chroma3d_sculpt",
            "chroma3d_sculpt.operators",
            "chroma3d_sculpt.ui",
        ],
        "external_runtime_dependencies": _external_runtime_roots(),
        "archive_members": names,
        "retained_release_identity": retained,
        "matches_retained_release_archive_bytes": retained["archive_file_count"] == len(names) and retained["archive_bytes"] == package.stat().st_size and retained["archive_sha256"] == current_sha,
        "retained_identity_note": "A stable exact member count with different ZIP bytes can reflect local ZIP metadata/compression environment; H0 records the rebuilt current-checkout archive as the future comparison anchor and does not rewrite retained release evidence.",
    }


def render(report: dict[str, object]) -> str:
    return "\n".join((
        "# Package Baseline",
        "",
        f"Checkpoint: `{report['checkpoint_tag']}` / `{report['checkpoint_commit']}`.",
        "",
        markdown_table(("Metric", "Value"), (
            ("Extension version", report["extension_version"]),
            ("Manifest version", report["manifest_version"]),
            ("Archive", report["archive_filename"]),
            ("Files", report["archive_file_count"]),
            ("Bytes", report["archive_bytes"]),
            ("SHA-256", report["archive_sha256"]),
            ("Python modules", report["source_module_count"]),
            ("Schemas", len(report["schemas_included"])),
            ("Profiles", len(report["profiles_included"])),
            ("Docs", len(report["docs_included"])),
            ("Forbidden files absent", report["forbidden_files_absent"]),
            ("Repository validator errors", len(report["repository_validator_errors"])),
            ("External runtime roots", ", ".join(report["external_runtime_dependencies"]) or "none"),
            ("Matches retained release ZIP bytes", report["matches_retained_release_archive_bytes"]),
        )),
        "",
        "This exact rebuilt archive identity is the package comparison anchor for H1-H9. Blender-native validation is recorded separately by the H0 runner. The retained pre-v1 release ZIP identity remains historical evidence and is not rewritten.",
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BASELINE_ROOT / "package_baseline.json")
    parser.add_argument("--markdown", type=Path, default=BASELINE_ROOT / "PACKAGE_BASELINE.md")
    args = parser.parse_args()
    report = capture()
    write_json(args.output, report)
    write_text(args.markdown, render(report))
    print(f"package baseline: {report['archive_file_count']} files, sha256={report['archive_sha256']}")
    return 0 if not report["repository_validator_errors"] and report["forbidden_files_absent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
