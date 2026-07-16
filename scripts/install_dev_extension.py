"""Build and optionally install Chroma3D Sculpt into a Blender development setup."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import zipfile

from _project import EXTENSION_ID, PACKAGE_PATH, REPOSITORY_ROOT
from find_blender import discover_blender
from package_extension import build_package
from validate_package import validate_archive


def _install_to_directory(package: Path, extension_directory: Path) -> Path:
    root = extension_directory.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"User extension directory does not exist: {root}")
    target = root / EXTENSION_ID
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite existing extension directory: {target}")
    target.mkdir()
    try:
        with zipfile.ZipFile(package, "r") as archive:
            for info in archive.infolist():
                destination = target.joinpath(*Path(info.filename).parts)
                if info.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(archive.read(info))
    except Exception:
        print(f"Partial files may remain in the newly created directory: {target}", file=sys.stderr)
        raise
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, help="Explicit blender.exe path")
    parser.add_argument("--user-extension-dir", type=Path, help="Existing user extension repository directory")
    parser.add_argument("--install", action="store_true", help="Install through Blender's extension command")
    args = parser.parse_args()

    try:
        package, _, _ = build_package()
        errors = validate_archive(package)
        if errors:
            raise ValueError("; ".join(errors))
        if args.user_extension_dir:
            output = _install_to_directory(package, args.user_extension_dir)
            print(f"Development extension installed without overwrite: {output}")
            return 0
        if args.install:
            discovery = discover_blender(args.blender)
            if discovery is None:
                raise FileNotFoundError("Blender was not found; pass --blender or set BLENDER_EXECUTABLE.")
            command = [
                str(discovery.executable),
                "--background",
                "--command",
                "extension",
                "install-file",
                "--repo",
                "user_default",
                "--enable",
                str(package),
            ]
            completed = subprocess.run(command, cwd=REPOSITORY_ROOT, check=False)
            if completed.returncode:
                raise RuntimeError(f"Blender installation command failed with exit code {completed.returncode}.")
            print(f"Blender installed the package: {package}")
            return 0
    except Exception as exc:
        print(f"Development installation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        print(f"Manual fallback: Blender > Edit > Preferences > Extensions > Install from Disk > {PACKAGE_PATH}", file=sys.stderr)
        return 1

    print(f"Package is ready: {package}")
    print("No external files were changed. Re-run with --install or --user-extension-dir, or install from disk in Blender.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
