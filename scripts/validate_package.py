"""Validate the generated Blender Extension archive and its safety boundaries."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import sys
import zipfile

from _project import (
    DISPLAY_VERSION,
    EXTENSION_ID,
    MANIFEST_VERSION,
    PACKAGE_PATH,
    REQUIRED_SOURCE_FILES,
    read_manifest_bytes,
)

_SECRET_NAMES = {"id_rsa", "id_ed25519", "credentials", "secrets", "api_key", "private_key"}
_SECRET_SUFFIXES = {".pem", ".p12", ".pfx", ".key"}


def validate_archive(package: Path) -> list[str]:
    errors: list[str] = []
    expected_filename = f"{EXTENSION_ID}-{DISPLAY_VERSION}.zip"
    if package.name != expected_filename:
        errors.append(f"Filename must be {expected_filename!r}.")
    if not package.is_file():
        return errors + [f"Package does not exist: {package}"]

    try:
        with zipfile.ZipFile(package, "r") as archive:
            bad_member = archive.testzip()
            if bad_member:
                errors.append(f"ZIP CRC failure: {bad_member}")
            names = archive.namelist()
            if not names:
                errors.append("Archive is empty.")

            files = {name for name in names if not name.endswith("/")}
            required = set(REQUIRED_SOURCE_FILES) | {"LICENSE"}
            errors.extend(f"Missing required archive entry: {item}" for item in sorted(required - files))

            for name in names:
                if "\\" in name:
                    errors.append(f"Unsafe ZIP separator: {name}")
                    continue
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts or (path.parts and ":" in path.parts[0]):
                    errors.append(f"Unsafe ZIP path: {name}")
                lowered_parts = tuple(part.lower() for part in path.parts)
                lowered_name = path.name.lower()
                if "__pycache__" in lowered_parts or lowered_name.endswith((".pyc", ".pyo")):
                    errors.append(f"Bytecode is not allowed: {name}")
                if any(part == ".env" or part.startswith(".env.") for part in lowered_parts):
                    errors.append(f"Environment file is not allowed: {name}")
                if "tests" in lowered_parts or "scripts" in lowered_parts:
                    errors.append(f"Development content is not allowed: {name}")
                stem = Path(lowered_name).stem
                if stem in _SECRET_NAMES or Path(lowered_name).suffix in _SECRET_SUFFIXES:
                    errors.append(f"Secret-like file is not allowed: {name}")
                if lowered_parts and lowered_parts[0] in {"chroma3d sculpt", "chroma3d-sculpt", EXTENSION_ID}:
                    errors.append(f"Unexpected nested package/repository root: {name}")

            if "blender_manifest.toml" in files:
                try:
                    manifest = read_manifest_bytes(archive.read("blender_manifest.toml"))
                except Exception as exc:
                    errors.append(f"Manifest is unreadable: {exc}")
                else:
                    if manifest.get("version") != MANIFEST_VERSION:
                        errors.append(
                            f"Manifest version {manifest.get('version')!r} does not match {MANIFEST_VERSION!r}."
                        )
                    if manifest.get("id") != EXTENSION_ID:
                        errors.append(f"Manifest id {manifest.get('id')!r} does not match {EXTENSION_ID!r}.")
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"ZIP is unreadable: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", nargs="?", type=Path, default=PACKAGE_PATH, help="ZIP package to validate")
    args = parser.parse_args()
    errors = validate_archive(args.package.resolve())
    if errors:
        print("Package validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"Package validation passed: {args.package.resolve()}")
    print("Package root: archive root (modern Blender Extension layout)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

