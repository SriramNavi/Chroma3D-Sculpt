"""Discover a local Blender executable without assuming one Windows version path."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Iterable

try:
    import winreg
except ImportError:  # pragma: no cover - non-Windows portability
    winreg = None  # type: ignore[assignment]


@dataclass(frozen=True, slots=True)
class BlenderDiscovery:
    executable: Path
    source: str
    version: str


def _valid_executable(value: str | Path | None) -> Path | None:
    if not value:
        return None
    candidate = Path(value).expanduser()
    try:
        candidate = candidate.resolve()
    except OSError:
        return None
    return candidate if candidate.is_file() and candidate.name.lower() in {"blender.exe", "blender"} else None


def _probe_version(executable: Path) -> str:
    try:
        completed = subprocess.run(
            [str(executable), "--version"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "Unknown"
    match = re.search(r"Blender\s+([0-9]+(?:\.[0-9]+){1,2})", completed.stdout + completed.stderr)
    return match.group(1) if match else "Unknown"


def _version_hint(path: Path) -> tuple[int, int, int]:
    match = re.search(r"Blender[ _-]+(\d+)\.(\d+)(?:\.(\d+))?", str(path), re.IGNORECASE)
    if not match:
        return (0, 0, 0)
    return tuple(int(value or 0) for value in match.groups())  # type: ignore[return-value]


def _preferred(candidates: Iterable[Path]) -> Path | None:
    unique = {candidate.resolve() for candidate in candidates if _valid_executable(candidate)}
    if not unique:
        return None
    return sorted(
        unique,
        key=lambda path: (
            _version_hint(path)[:2] != (4, 5),
            tuple(-value for value in _version_hint(path)),
            str(path).lower(),
        ),
    )[0]


def _standard_candidates() -> list[Path]:
    candidates: list[Path] = []
    roots = {
        Path(value) / "Blender Foundation"
        for key in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)")
        if (value := os.environ.get(key))
    }
    for root in roots:
        try:
            candidates.extend(root.glob("Blender */blender.exe"))
            candidates.append(root / "blender.exe")
        except OSError:
            continue
    return candidates


def _other_candidates() -> list[Path]:
    candidates: list[Path] = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        local = Path(local_app_data)
        candidates.extend((local / "Programs" / "Blender Foundation").glob("Blender */blender.exe"))
        candidates.append(local / "Microsoft" / "WindowsApps" / "blender.exe")
    return candidates


def _registry_candidates() -> list[Path]:
    if winreg is None:
        return []
    candidates: list[Path] = []
    locations = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    )
    for hive, location in locations:
        try:
            root = winreg.OpenKey(hive, location)
        except OSError:
            continue
        with root:
            index = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(root, index)
                except OSError:
                    break
                index += 1
                try:
                    with winreg.OpenKey(root, subkey_name) as subkey:
                        display_name = str(winreg.QueryValueEx(subkey, "DisplayName")[0])
                        if "blender" not in display_name.lower():
                            continue
                        try:
                            install_location = str(winreg.QueryValueEx(subkey, "InstallLocation")[0])
                        except OSError:
                            install_location = ""
                        try:
                            display_icon = str(winreg.QueryValueEx(subkey, "DisplayIcon")[0])
                        except OSError:
                            display_icon = ""
                except OSError:
                    continue
                if install_location:
                    candidates.append(Path(install_location) / "blender.exe")
                if display_icon:
                    candidates.append(Path(display_icon.strip().strip('"').split(",", 1)[0]))
    return candidates


def discover_blender(explicit: str | Path | None = None) -> BlenderDiscovery | None:
    tiers: list[tuple[str, list[Path]]] = []
    if explicit:
        tiers.append(("explicit --blender argument", [Path(explicit)]))
    environment_value = os.environ.get("BLENDER_EXECUTABLE")
    if environment_value:
        tiers.append(("BLENDER_EXECUTABLE environment variable", [Path(environment_value)]))
    path_value = shutil.which("blender") or shutil.which("blender.exe")
    if path_value:
        tiers.append(("PATH", [Path(path_value)]))
    tiers.append(("standard Blender Foundation installation", _standard_candidates()))
    tiers.append(("Windows installed-app registry", _registry_candidates()))
    tiers.append(("per-user or Microsoft Store alias", _other_candidates()))

    for source, candidates in tiers:
        executable = _preferred(candidates)
        if executable is not None:
            return BlenderDiscovery(executable, source, _probe_version(executable))
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, help="Explicit path to blender.exe")
    args = parser.parse_args()
    result = discover_blender(args.blender)
    if result is None:
        print("Blender executable was not found.", file=sys.stderr)
        print(r"Set BLENDER_EXECUTABLE or run: py scripts\find_blender.py --blender \"C:\path\to\blender.exe\"", file=sys.stderr)
        return 1
    print(f"Detected executable: {result.executable}")
    print(f"Detected version: {result.version}")
    print(f"Detection source: {result.source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
