"""Install and smoke the exact Sprint 7 ZIP in a removable Blender profile."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "dist" / "chroma3d_sculpt-0.8.0-alpha.1.zip"
REPORTS = ROOT / "manual-tests" / "sprint7-final" / "reports"
ARTIFACTS = ROOT / "manual-tests" / "sprint7-final" / "artifacts"
SMOKE = Path(__file__).with_name("installed_extension_smoke.py")


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--blender", type=Path, required=True); args = parser.parse_args()
    if not PACKAGE.is_file() or not args.blender.is_file():
        raise SystemExit("Exact package or Blender executable is unavailable.")
    package_sha256_before = hashlib.sha256(PACKAGE.read_bytes()).hexdigest()
    REPORTS.mkdir(parents=True, exist_ok=True); ARTIFACTS.mkdir(parents=True, exist_ok=True)
    smoke_output = REPORTS / "installed_smoke_payload.json"
    environment = os.environ.copy(); environment.pop("OPENAI_API_KEY", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    install = smoke = None; profile_path = ""; installed_inventory_matches = False; installed_root = None
    installed_extra_files: list[str] = []
    installed_missing_files: list[str] = []
    runtime_generated_files: list[str] = []
    unexpected_installed_files: list[str] = []
    with tempfile.TemporaryDirectory(prefix="isolated-profile-", dir=ARTIFACTS) as temporary:
        profile = Path(temporary); profile_path = str(profile)
        environment.update({
            "BLENDER_USER_CONFIG": str(profile / "config"), "BLENDER_USER_SCRIPTS": str(profile / "scripts"),
            "BLENDER_USER_DATAFILES": str(profile / "datafiles"),
            "BLENDER_USER_EXTENSIONS": str(profile / "extensions"),
        })
        install = subprocess.run(
            [str(args.blender), "--background", "--factory-startup", "--command", "extension", "install-file", "-r", "user_default", "-e", str(PACKAGE)],
            cwd=ROOT, env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, check=False,
        )
        manifests = tuple(profile.rglob("blender_manifest.toml"))
        installed_root = next((path.parent for path in manifests if path.parent.name == "chroma3d_sculpt"), None)
        if installed_root is not None:
            with zipfile.ZipFile(PACKAGE) as archive:
                archive_files = {info.filename for info in archive.infolist() if not info.is_dir()}
                installed_files = {path.relative_to(installed_root).as_posix() for path in installed_root.rglob("*") if path.is_file()}
                installed_extra_files = sorted(installed_files - archive_files)
                installed_missing_files = sorted(archive_files - installed_files)
                runtime_generated_files = sorted(name for name in installed_extra_files if "/__pycache__/" in f"/{name}" and name.endswith(".pyc"))
                unexpected_installed_files = sorted(set(installed_extra_files) - set(runtime_generated_files))
                installed_inventory_matches = not installed_missing_files and not unexpected_installed_files and all(
                    (installed_root / info.filename).is_file()
                    and hashlib.sha256((installed_root / info.filename).read_bytes()).digest() == hashlib.sha256(archive.read(info.filename)).digest()
                    for info in archive.infolist() if not info.is_dir()
                )
        smoke = subprocess.run(
            [str(args.blender), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(SMOKE), "--", "--root", str(installed_root.parent if installed_root else profile), "--output", str(smoke_output)],
            cwd=ROOT, env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, check=False,
        )
        try:
            smoke_payload = json.loads(smoke_output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            smoke_payload = {"status": "FAIL", "reason": "Smoke payload missing or invalid."}
    profile_removed = not Path(profile_path).exists()
    with zipfile.ZipFile(PACKAGE) as archive:
        file_count = len(archive.infolist()); manifest = archive.read("blender_manifest.toml").decode("utf-8")
    package_sha256_after = hashlib.sha256(PACKAGE.read_bytes()).hexdigest()
    payload = {
        "schema_version": "1.0.0",
        "status": "PASS" if install.returncode == 0 and installed_inventory_matches and smoke.returncode == 0 and smoke_payload.get("status") == "PASS" and profile_removed and package_sha256_before == package_sha256_after else "FAIL",
        "package": str(PACKAGE.relative_to(ROOT)), "package_file_count": file_count, "package_size_bytes": PACKAGE.stat().st_size,
        "package_sha256": package_sha256_after, "package_sha256_before_smoke": package_sha256_before,
        "package_unchanged_during_smoke": package_sha256_before == package_sha256_after,
        "manifest_version_present": 'version = "0.8.0"' in manifest,
        "install_exit_code": install.returncode, "installed_inventory_matches_zip": installed_inventory_matches, "smoke_exit_code": smoke.returncode, "smoke": smoke_payload,
        "installed_extra_files": installed_extra_files, "installed_missing_files": installed_missing_files,
        "runtime_generated_files": runtime_generated_files, "unexpected_installed_files": unexpected_installed_files,
        "temporary_profile_removed": profile_removed, "live_provider_calls": 0,
        "install_output_tail": (install.stdout + install.stderr).splitlines()[-20:],
        "smoke_output_tail": (smoke.stdout + smoke.stderr).splitlines()[-30:] if smoke.returncode else [],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "limitations": ["Automated headless installed-package smoke; manual panel visual UAT remains NOT RUN."],
    }
    target = REPORTS / "installed_package_smoke.json"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": payload["status"], "install_exit_code": install.returncode, "smoke_exit_code": smoke.returncode, "temporary_profile_removed": profile_removed}))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
