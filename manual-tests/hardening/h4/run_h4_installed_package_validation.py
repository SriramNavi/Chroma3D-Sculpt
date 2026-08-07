"""Install, enable, disable, re-enable, smoke, remove, and clean H4 package."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any
import zipfile


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BLENDER = Path(r"D:\Softwares\Design\Blender\blender.exe")
DEFAULT_PACKAGE = ROOT / "dist" / "chroma3d_sculpt-0.8.0-alpha.1.zip"
MODULE_ID = "bl_ext.user_default.chroma3d_sculpt"


def _arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, default=DEFAULT_BLENDER)
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", choices=("cycle", "cleanup"))
    parser.add_argument("--installed-root", type=Path)
    parser.add_argument("--worker-output", type=Path)
    return parser.parse_args(values)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def _worker(args: argparse.Namespace) -> int:
    import bpy

    if args.installed_root is None or args.worker_output is None:
        raise ValueError("worker paths are required")
    if args.worker == "cleanup":
        enabled = MODULE_ID in bpy.context.preferences.addons
        remaining_manifests = [
            path.as_posix() for path in args.installed_root.parent.rglob("blender_manifest.toml")
            if path.parent.name == "chroma3d_sculpt"
        ] if args.installed_root.parent.exists() else []
        payload = {
            "status": "PASS" if not enabled and not args.installed_root.exists() and not remaining_manifests else "FAIL",
            "enabled_after_remove": enabled,
            "installed_root_exists": args.installed_root.exists(),
            "remaining_manifests": remaining_manifests,
        }
        _write_json(args.worker_output, payload)
        return 0 if payload["status"] == "PASS" else 1

    initially_enabled = MODULE_ID in bpy.context.preferences.addons
    if not initially_enabled:
        enable_result = set(bpy.ops.preferences.addon_enable(module=MODULE_ID))
    else:
        enable_result = {"FINISHED"}
    module = importlib.import_module(MODULE_ID)
    installed_path = Path(module.__file__).resolve()
    imported_from_installed_root = args.installed_root.resolve() in installed_path.parents
    first_registered = hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state")
    module.register()
    duplicate_register_safe = hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state")
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    source = bpy.context.object
    source_vertices_before = len(source.data.vertices)
    first_analyze = set(bpy.ops.chroma3d.analyze_mesh())
    source_vertices_after_first = len(source.data.vertices)
    first_disable = set(bpy.ops.preferences.addon_disable(module=MODULE_ID))
    disabled_clean = (
        MODULE_ID not in bpy.context.preferences.addons
        and not hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state")
        and not any(getattr(item, "is_registered", False) for item in (*module.PROPERTY_CLASSES, *module._RUNTIME_CLASSES))
    )
    second_enable = set(bpy.ops.preferences.addon_enable(module=MODULE_ID))
    module = importlib.import_module(MODULE_ID)
    second_registered = MODULE_ID in bpy.context.preferences.addons and hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state")
    second_analyze = set(bpy.ops.chroma3d.analyze_mesh())
    source_vertices_after_second = len(source.data.vertices)
    final_disable = set(bpy.ops.preferences.addon_disable(module=MODULE_ID))
    final_disabled_clean = MODULE_ID not in bpy.context.preferences.addons and not hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state")
    for item in tuple(bpy.data.objects):
        bpy.data.objects.remove(item, do_unlink=True)
    passed = all((
        enable_result == {"FINISHED"},
        imported_from_installed_root,
        first_registered,
        duplicate_register_safe,
        first_analyze == {"FINISHED"},
        first_disable == {"FINISHED"},
        disabled_clean,
        second_enable == {"FINISHED"},
        second_registered,
        second_analyze == {"FINISHED"},
        final_disable == {"FINISHED"},
        final_disabled_clean,
        source_vertices_before == source_vertices_after_first == source_vertices_after_second == 8,
    ))
    payload = {
        "status": "PASS" if passed else "FAIL",
        "module_id": MODULE_ID,
        "module_file_relative": installed_path.relative_to(args.installed_root.parent).as_posix() if imported_from_installed_root else installed_path.name,
        "imported_from_installed_root": imported_from_installed_root,
        "initially_enabled": initially_enabled,
        "first_registered": first_registered,
        "duplicate_register_safe": duplicate_register_safe,
        "first_analysis": sorted(first_analyze),
        "disabled_clean": disabled_clean,
        "second_registered": second_registered,
        "second_analysis": sorted(second_analyze),
        "final_disabled_clean": final_disabled_clean,
        "source_vertices": [source_vertices_before, source_vertices_after_first, source_vertices_after_second],
        "source_mutation_count": 0 if source_vertices_before == source_vertices_after_first == source_vertices_after_second else 1,
        "live_provider_calls": 0,
        "blender_version": bpy.app.version_string,
    }
    _write_json(args.worker_output, payload)
    return 0 if passed else 1


def _run(command: list[str], environment: dict[str, str], log: Path, timeout: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        timed_out = True
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(stdout + "\n--- STDERR ---\n" + stderr, encoding="utf-8", newline="\n")
    return {
        "returncode": returncode,
        "timed_out": timed_out,
        "log": log.relative_to(ROOT).as_posix(),
        "stdout_tail": stdout.splitlines()[-12:],
        "stderr_tail": stderr.splitlines()[-12:],
    }


def _host(args: argparse.Namespace) -> int:
    if not args.blender.is_file() or not args.package.is_file():
        raise FileNotFoundError("Exact package or Blender executable is unavailable")
    reports = args.output.parent
    artifacts = reports / "installed_artifacts"
    logs = ROOT / "manual-tests" / "hardening" / "h4" / "logs"
    artifacts.mkdir(parents=True, exist_ok=True)
    package_before = hashlib.sha256(args.package.read_bytes()).hexdigest()
    profile_path = ""
    install = cycle = remove = cleanup = {"returncode": None}
    cycle_payload: dict[str, Any] = {}
    cleanup_payload: dict[str, Any] = {}
    installed_inventory_matches = False
    installed_extra_files: list[str] = []
    installed_missing_files: list[str] = []
    runtime_generated_files: list[str] = []
    unexpected_installed_files: list[str] = []
    installed_root: Path | None = None
    isolation_paths: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="isolated-h4-", dir=artifacts) as temporary:
        profile = Path(temporary).resolve()
        profile_path = str(profile)
        environment = os.environ.copy()
        environment.pop("OPENAI_API_KEY", None)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        isolation_paths = {
            "BLENDER_USER_CONFIG": str(profile / "config"),
            "BLENDER_USER_SCRIPTS": str(profile / "scripts"),
            "BLENDER_USER_DATAFILES": str(profile / "datafiles"),
            "BLENDER_USER_EXTENSIONS": str(profile / "extensions"),
        }
        environment.update(isolation_paths)
        install = _run([
            str(args.blender), "--background", "--factory-startup", "--command", "extension",
            "install-file", "-r", "user_default", "-e", str(args.package.resolve()),
        ], environment, logs / "installed_install.log", 180)
        manifests = tuple(profile.rglob("blender_manifest.toml"))
        installed_root = next((path.parent for path in manifests if path.parent.name == "chroma3d_sculpt"), None)
        if installed_root is not None:
            with zipfile.ZipFile(args.package) as archive:
                archive_files = {info.filename for info in archive.infolist() if not info.is_dir()}
                installed_files = {path.relative_to(installed_root).as_posix() for path in installed_root.rglob("*") if path.is_file()}
                installed_extra_files = sorted(installed_files - archive_files)
                installed_missing_files = sorted(archive_files - installed_files)
                runtime_generated_files = sorted(name for name in installed_extra_files if "/__pycache__/" in f"/{name}" and name.endswith(".pyc"))
                unexpected_installed_files = sorted(set(installed_extra_files) - set(runtime_generated_files))
                installed_inventory_matches = not installed_missing_files and not unexpected_installed_files and all(
                    hashlib.sha256((installed_root / info.filename).read_bytes()).digest() == hashlib.sha256(archive.read(info.filename)).digest()
                    for info in archive.infolist() if not info.is_dir()
                )
            cycle_output = reports / "installed_cycle_payload.json"
            cycle = _run([
                str(args.blender), "--background", "--python-exit-code", "1", "--python", str(Path(__file__).resolve()), "--",
                "--worker", "cycle", "--installed-root", str(installed_root), "--worker-output", str(cycle_output),
                "--output", str(args.output),
            ], environment, logs / "installed_cycle.log", 300)
            cycle_payload = json.loads(cycle_output.read_text(encoding="utf-8")) if cycle_output.is_file() else {}
            remove = _run([
                str(args.blender), "--background", "--command", "extension", "remove", "chroma3d_sculpt",
            ], environment, logs / "installed_remove.log", 180)
            cleanup_output = reports / "installed_cleanup_payload.json"
            cleanup = _run([
                str(args.blender), "--background", "--python-exit-code", "1", "--python", str(Path(__file__).resolve()), "--",
                "--worker", "cleanup", "--installed-root", str(installed_root), "--worker-output", str(cleanup_output),
                "--output", str(args.output),
            ], environment, logs / "installed_cleanup.log", 180)
            cleanup_payload = json.loads(cleanup_output.read_text(encoding="utf-8")) if cleanup_output.is_file() else {}
    profile_removed = not Path(profile_path).exists()
    package_after = hashlib.sha256(args.package.read_bytes()).hexdigest()
    isolation_complete = all(Path(value).is_relative_to(Path(profile_path)) for value in isolation_paths.values())
    passed = all((
        install.get("returncode") == 0,
        installed_root is not None,
        installed_inventory_matches,
        cycle.get("returncode") == 0,
        cycle_payload.get("status") == "PASS",
        remove.get("returncode") == 0,
        cleanup.get("returncode") == 0,
        cleanup_payload.get("status") == "PASS",
        profile_removed,
        isolation_complete,
        package_before == package_after,
    ))
    with zipfile.ZipFile(args.package) as archive:
        package_file_count = len([info for info in archive.infolist() if not info.is_dir()])
    payload = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if passed else "FAIL",
        "package": args.package.relative_to(ROOT).as_posix(),
        "package_file_count": package_file_count,
        "package_bytes": args.package.stat().st_size,
        "package_sha256": package_after,
        "package_unchanged_during_qualification": package_before == package_after,
        "profile_isolation": {"status": "PASS" if isolation_complete else "FAIL", "all_paths_under_temporary_profile": isolation_complete},
        "install": install,
        "installed_inventory_matches_zip": installed_inventory_matches,
        "installed_extra_files": installed_extra_files,
        "installed_missing_files": installed_missing_files,
        "runtime_generated_files": runtime_generated_files,
        "unexpected_installed_files": unexpected_installed_files,
        "enable_disable_reenable": cycle_payload,
        "remove": remove,
        "cleanup": cleanup_payload,
        "temporary_profile_removed": profile_removed,
        "live_provider_calls": 0,
        "limitations": ["Automated headless installed-package qualification; manual installed-panel visual UAT remains NOT_RUN."],
    }
    _write_json(args.output, payload)
    print(json.dumps({
        "status": payload["status"], "install": install.get("returncode"),
        "cycle": cycle.get("returncode"), "remove": remove.get("returncode"),
        "cleanup": cleanup.get("returncode"), "profile_removed": profile_removed,
    }, sort_keys=True))
    return 0 if passed else 1


def main() -> int:
    args = _arguments()
    return _worker(args) if args.worker else _host(args)


if __name__ == "__main__":
    raise SystemExit(main())
