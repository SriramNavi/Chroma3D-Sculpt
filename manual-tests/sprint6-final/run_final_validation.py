"""Run independent Sprint 6 validation, package proof, and install smoke."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "manual-tests" / "sprint6-final" / "reports"
LOGS = ROOT / "manual-tests" / "sprint6-final" / "logs"
FINAL_REPORT = REPORTS / "final_validation_results.json"
PACKAGE = ROOT / "dist" / "chroma3d_sculpt-0.7.0-alpha.1.zip"


def _run(command: list[str], *, timeout: int) -> dict[str, object]:
    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
        return {"command": subprocess.list2cmdline(command), "exit_code": completed.returncode, "stdout_tail": completed.stdout[-4000:], "stderr_tail": completed.stderr[-4000:]}
    except subprocess.TimeoutExpired as exc:
        return {"command": subprocess.list2cmdline(command), "exit_code": 124, "stdout_tail": str(exc.stdout or "")[-4000:], "stderr_tail": f"Timed out after {timeout} seconds."}


def _package_scope() -> dict[str, object]:
    build = _run([sys.executable, "scripts/package_extension.py"], timeout=300)
    validate = _run([sys.executable, "scripts/validate_package.py", str(PACKAGE)], timeout=120)
    if build["exit_code"] or validate["exit_code"] or not PACKAGE.is_file():
        return {"status": "FAIL", "build": build, "validate": validate}
    with zipfile.ZipFile(PACKAGE) as archive:
        names = archive.namelist()
        lowered = [name.lower() for name in names]
        forbidden = [name for name in lowered if any(part in name.split("/") for part in ("tests", "manual-tests", "datasets", "logs", "screenshots", "__pycache__")) or name.endswith((".pyc", ".blend", ".env"))]
        absolute = [name for name in names if name.startswith(("/", "\\")) or ":" in name.split("/")[0] or ".." in name.split("/")]
    return {"status": "PASS" if not forbidden and not absolute else "FAIL", "build": build, "validate": validate, "file_count": len(names), "size_bytes": PACKAGE.stat().st_size, "sha256": hashlib.sha256(PACKAGE.read_bytes()).hexdigest(), "forbidden_entries": forbidden, "absolute_entries": absolute}


def _installed_smoke(blender: Path) -> dict[str, object]:
    if not PACKAGE.is_file():
        return {"status": "NOT_EVALUATED", "reason": "Package was not built."}
    smoke_script = ROOT / "manual-tests" / "sprint6-final" / "installed_extension_smoke.py"
    with tempfile.TemporaryDirectory(prefix="chroma3d-s6-installed-") as temporary:
        temp_root = Path(temporary)
        extracted = temp_root / "extension"
        package_root = extracted / "chroma3d_sculpt"
        package_root.mkdir(parents=True)
        with zipfile.ZipFile(PACKAGE) as archive:
            archive.extractall(package_root)
        profile = temp_root / "blender-profile"
        output = temp_root / "installed-smoke.json"
        command = [str(blender), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(smoke_script), "--", "--root", str(extracted), "--output", str(output)]
        environment = {**dict(), "BLENDER_USER_CONFIG": str(profile / "config"), "BLENDER_USER_SCRIPTS": str(profile / "scripts")}
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, check=False, env={**__import__("os").environ, **environment})
        payload = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}
        return {"status": "PASS" if completed.returncode == 0 and payload.get("status") == "PASS" else "FAIL", "exit_code": completed.returncode, "payload": payload, "stdout_tail": completed.stdout[-4000:], "stderr_tail": completed.stderr[-4000:], "profile_removed": not profile.exists()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender", type=Path, required=True)
    args = parser.parse_args()
    REPORTS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    blender_runner = ROOT / "manual-tests" / "sprint6-final" / "final_validation_runner.py"
    command = [str(args.blender), "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(blender_runner), "--", "--output", str(FINAL_REPORT)]
    result = _run(command, timeout=600)
    (LOGS / "final_validation.log").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    try:
        independent = json.loads(FINAL_REPORT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        independent = {"status": "FAIL", "gates": [], "failed_gate_count": 1, "error": "Independent runner did not produce valid JSON."}
    package = _package_scope()
    installed = _installed_smoke(args.blender)
    independent.setdefault("gates", []).append({"id": "S6F-Q-PACKAGE", "title": "Package archive scope", "status": package["status"], "detail": package})
    independent.setdefault("gates", []).append({"id": "S6F-Q-INSTALLED", "title": "Isolated installed-extension smoke", "status": installed["status"], "detail": installed})
    failed = [gate for gate in independent["gates"] if gate.get("status") == "FAIL"]
    independent["status"] = "FAIL" if failed else "PASS_WITH_LIMITATIONS"
    independent["failed_gate_count"] = len(failed)
    independent["passed_gate_count"] = sum(gate.get("status") == "PASS" for gate in independent["gates"])
    independent["package"] = package
    independent["installed_package"] = installed
    independent["recorded_at"] = datetime.now(timezone.utc).isoformat()
    FINAL_REPORT.write_text(json.dumps(independent, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    markdown = ["# Sprint 6 Independent Final Validation", "", f"- Status: **{independent['status']}**", f"- Blender: `{independent.get('blender_version', 'not recorded')}`", f"- Gates: `{independent.get('passed_gate_count', 0)}` PASS / `{independent.get('failed_gate_count', 0)}` FAIL", "", "## Gate summary", ""]
    markdown.extend(f"- `{gate.get('id')}` {gate.get('title')}: **{gate.get('status')}**" for gate in independent["gates"])
    markdown.extend(["", "## Limitations", "", "Physical printing, real slicer comparison, material calibration, Blender 4.5 LTS, and manual installed-panel UAT were not run. Bounded search, estimated virtual evidence, and synthetic performance fixtures remain explicitly limited.", ""])
    (ROOT / "manual-tests" / "sprint6-final" / "FINAL_VALIDATION_RESULTS.md").write_text("\n".join(markdown), encoding="utf-8", newline="\n")
    return 0 if not failed and result["exit_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
