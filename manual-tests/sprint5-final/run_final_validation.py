"""Launch the independent Sprint 5 validation in factory Blender."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = REPOSITORY_ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))
from find_blender import discover_blender  # noqa: E402


FINAL_ROOT = Path(__file__).resolve().parent
RUNNER = FINAL_ROOT / "final_validation_runner.py"
INSTALLED_SMOKE = FINAL_ROOT / "installed_package_smoke.py"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path)
    parser.add_argument("--phase", choices=("initial", "final"), default="final")
    parser.add_argument("--skip-performance", action="store_true")
    args = parser.parse_args()
    discovery = discover_blender(args.blender)
    if discovery is None:
        print("Blender was not found.", file=sys.stderr)
        return 2

    if args.phase == "final":
        package = subprocess.run([sys.executable, str(SCRIPT_ROOT / "package_extension.py")], cwd=REPOSITORY_ROOT, check=False)
        if package.returncode:
            return package.returncode
        package_path = REPOSITORY_ROOT / "dist" / "chroma3d_sculpt-0.6.0-alpha.1.zip"
        package_check = subprocess.run([sys.executable, str(SCRIPT_ROOT / "validate_package.py"), str(package_path)], cwd=REPOSITORY_ROOT, check=False)
        if package_check.returncode:
            return package_check.returncode

    log_root = FINAL_ROOT / "logs"
    log_root.mkdir(parents=True, exist_ok=True)
    log_path = log_root / f"final_validation_{args.phase}.log"
    command = [str(discovery.executable), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(RUNNER), "--", "--phase", args.phase]
    if args.skip_performance:
        command.append("--skip-performance")
    completed = subprocess.run(command, cwd=REPOSITORY_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    log_path.write_text(completed.stdout, encoding="utf-8", newline="\n")
    print(completed.stdout)
    print(f"Blender validation log: {log_path}")
    if completed.returncode:
        return completed.returncode

    if args.phase == "final":
        package_path = REPOSITORY_ROOT / "dist" / "chroma3d_sculpt-0.6.0-alpha.1.zip"
        extension_check = subprocess.run([str(discovery.executable), "--background", "--command", "extension", "validate", str(package_path)], cwd=REPOSITORY_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        (log_root / "package_extension_validate.log").write_text(extension_check.stdout, encoding="utf-8", newline="\n")
        print(extension_check.stdout)
        profile = FINAL_ROOT / "artifacts" / "isolated-blender-profile"
        if profile.exists():
            shutil.rmtree(profile)
        profile.mkdir(parents=True, exist_ok=True)
        environment = dict(os.environ)
        environment.update({
            "BLENDER_USER_CONFIG": str(profile / "config"),
            "BLENDER_USER_SCRIPTS": str(profile / "scripts"),
            "BLENDER_USER_DATAFILES": str(profile / "datafiles"),
        })
        install = subprocess.run([str(discovery.executable), "--background", "--factory-startup", "--command", "extension", "install-file", "-r", "user_default", "-e", str(package_path)], cwd=REPOSITORY_ROOT, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        (log_root / "package_extension_install.log").write_text(install.stdout, encoding="utf-8", newline="\n")
        smoke = subprocess.run([str(discovery.executable), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(INSTALLED_SMOKE)], cwd=REPOSITORY_ROOT, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        (log_root / "installed_package_smoke.log").write_text(smoke.stdout, encoding="utf-8", newline="\n")
        smoke_evidence = FINAL_ROOT / "artifacts" / "installed_package_smoke.json"
        smoke_payload = json.loads(smoke_evidence.read_text(encoding="utf-8")) if smoke_evidence.is_file() else {"status": "NOT_RUN"}
        (FINAL_ROOT / "reports" / "installed_package_smoke.json").write_text(json.dumps({"install_exit_code": install.returncode, "smoke_exit_code": smoke.returncode, **smoke_payload}, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        shutil.rmtree(profile)
        print(json.dumps({"installed_package_install": install.returncode, "installed_package_smoke": smoke_payload.get("status"), "profile_removed": not profile.exists()}))
        return 0 if extension_check.returncode == 0 and install.returncode == 0 and smoke.returncode == 0 and smoke_payload.get("status") == "PASS" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
