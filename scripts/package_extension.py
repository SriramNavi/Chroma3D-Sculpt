"""Build the installable modern Blender Extension ZIP."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
import sys
import zipfile

from _project import DIST_DIRECTORY, LICENSE_PATH, PACKAGE_PATH, SOURCE_ROOT, validate_source_layout

_EXCLUDED_PARTS = {"__pycache__", ".git", "tests", "dist", ".vscode", ".idea"}
_EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".tmp", ".blend1", ".blend2", ".blend@"}


def _include(path: Path) -> bool:
    relative = path.relative_to(SOURCE_ROOT)
    if any(part in _EXCLUDED_PARTS for part in relative.parts):
        return False
    if any(part == ".env" or part.startswith(".env.") for part in relative.parts):
        return False
    if path.suffix.lower() in _EXCLUDED_SUFFIXES:
        return False
    return path.is_file()


def build_package() -> tuple[Path, int, int]:
    validate_source_layout()
    DIST_DIRECTORY.mkdir(parents=True, exist_ok=True)
    temporary = PACKAGE_PATH.with_suffix(".zip.tmp")
    if temporary.exists():
        temporary.unlink()

    included = 0
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for source in sorted(SOURCE_ROOT.rglob("*"), key=lambda item: item.as_posix().lower()):
                if not _include(source):
                    continue
                relative = source.relative_to(SOURCE_ROOT)
                archive_name = PurePosixPath(*relative.parts).as_posix()
                archive.write(source, archive_name)
                included += 1
            archive.write(LICENSE_PATH, "LICENSE")
            included += 1
        temporary.replace(PACKAGE_PATH)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise
    return PACKAGE_PATH, included, PACKAGE_PATH.stat().st_size


def main() -> int:
    try:
        output, file_count, size = build_package()
    except Exception as exc:
        print(f"Package build failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"Output path: {output}")
    print(f"Included files: {file_count}")
    print(f"Archive size: {size} bytes")
    print("Package root: archive root (blender_manifest.toml)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

