"""Runtime paths derived dynamically from the installed extension."""

from pathlib import Path


def extension_root() -> Path:
    return Path(__file__).resolve().parents[1]


def manifest_path() -> Path:
    return extension_root() / "blender_manifest.toml"

