"""Shared repository metadata for development scripts."""

from __future__ import annotations

from pathlib import Path
import runpy
import tomllib
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "blender_addon" / "chroma3d_sculpt"
DIST_DIRECTORY = REPOSITORY_ROOT / "dist"
MANIFEST_PATH = SOURCE_ROOT / "blender_manifest.toml"
LICENSE_PATH = REPOSITORY_ROOT / "LICENSE"

_metadata: dict[str, Any] = runpy.run_path(str(SOURCE_ROOT / "metadata.py"))
EXTENSION_ID = str(_metadata["EXTENSION_ID"])
MANIFEST_VERSION = str(_metadata["EXTENSION_VERSION"])
DISPLAY_VERSION = str(_metadata["DISPLAY_VERSION"])
PACKAGE_FILENAME = f"{EXTENSION_ID}-{DISPLAY_VERSION}.zip"
PACKAGE_PATH = DIST_DIRECTORY / PACKAGE_FILENAME

REQUIRED_SOURCE_FILES = (
    "__init__.py",
    "analysis_settings.py",
    "repair_settings.py",
    "blender_manifest.toml",
    "metadata.py",
    "session.py",
    "models/__init__.py",
    "models/analysis_result.py",
    "models/repair_models.py",
    "operators/__init__.py",
    "operators/analyze_mesh.py",
    "operators/export_report.py",
    "operators/select_issue.py",
    "operators/repair.py",
    "services/__init__.py",
    "services/mesh_analyzer.py",
    "services/topology_analyzer.py",
    "services/shell_analyzer.py",
    "services/deep_diagnostics.py",
    "services/build_volume_analyzer.py",
    "services/report_generator.py",
    "services/repair_audit.py",
    "services/repair_coordinator.py",
    "services/repair_operations.py",
    "services/repair_plan.py",
    "services/repair_session.py",
    "ui/__init__.py",
    "ui/panels.py",
    "ui/properties.py",
    "ui/repair_panel.py",
    "utilities/__init__.py",
    "utilities/blender_paths.py",
    "utilities/context.py",
    "utilities/geometry.py",
    "utilities/logging.py",
    "utilities/units.py",
    "utilities/signatures.py",
    "utilities/boundary_loops.py",
    "utilities/repair_signatures.py",
)


def read_manifest_bytes(data: bytes) -> dict[str, Any]:
    return tomllib.loads(data.decode("utf-8"))


def read_source_manifest() -> dict[str, Any]:
    return read_manifest_bytes(MANIFEST_PATH.read_bytes())


def validate_source_layout() -> None:
    if REPOSITORY_ROOT.name != "Chroma3D Sculpt":
        raise RuntimeError(f"Unexpected repository root: {REPOSITORY_ROOT}")
    if not SOURCE_ROOT.is_dir():
        raise FileNotFoundError(f"Extension source is missing: {SOURCE_ROOT}")
    missing = [relative for relative in REQUIRED_SOURCE_FILES if not (SOURCE_ROOT / relative).is_file()]
    if not LICENSE_PATH.is_file():
        missing.append("LICENSE")
    if missing:
        raise FileNotFoundError("Required file(s) missing: " + ", ".join(missing))
    manifest = read_source_manifest()
    expected = {
        "schema_version": "1.0.0",
        "id": EXTENSION_ID,
        "version": MANIFEST_VERSION,
        "type": "add-on",
    }
    mismatches = [f"{key}={manifest.get(key)!r} (expected {value!r})" for key, value in expected.items() if manifest.get(key) != value]
    if mismatches:
        raise ValueError("Invalid manifest metadata: " + "; ".join(mismatches))
