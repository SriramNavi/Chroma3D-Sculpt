"""Run H4 filesystem, credential, privacy, and provider-boundary checks."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import importlib.util
from io import StringIO
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "blender_addon" / "chroma3d_sculpt"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def _tracked_runtime_files() -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "blender_addon/chroma3d_sculpt"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return [ROOT / value for value in completed.stdout.splitlines() if value.endswith(".py")]


def _credential_surface() -> dict[str, Any]:
    files = _tracked_runtime_files()
    violations = []
    api_key_property_fields = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT).as_posix()
        if re.search(r"(?i)(api[_-]?key|credential).{0,80}(StringProperty|bpy\.props)", text):
            api_key_property_fields.append(relative)
        for line_number, line in enumerate(text.splitlines(), start=1):
            if re.search(r"(?i)(print|logger\.(debug|info|warning|error|exception))\([^\n]*(api[_-]?key|credential|_session_key)", line):
                violations.append({"path": relative, "line": line_number, "kind": "CREDENTIAL_LOG_SURFACE"})
    operator_text = (RUNTIME / "operators" / "ai_assistance.py").read_text(encoding="utf-8")
    password_skip_save = bool(re.search(
        r"key_value\s*:\s*StringProperty\([^\n]*subtype=\"PASSWORD\"[^\n]*options=\{\"SKIP_SAVE\"\}",
        operator_text,
    ))
    properties_text = (RUNTIME / "ui" / "properties.py").read_text(encoding="utf-8")
    forbidden_persistent_fields = sorted(set(re.findall(
        r"(?im)^\s*(\w*(?:api_?key|credential|secret|token)\w*)\s*:\s*",
        properties_text,
    )))
    return {
        "status": "PASS" if not violations and not forbidden_persistent_fields and password_skip_save else "FAIL",
        "runtime_python_files": len(files),
        "credential_log_violations": violations,
        "persistent_credential_fields": forbidden_persistent_fields,
        "password_operator_skip_save": password_skip_save,
        "credential_related_property_surfaces": api_key_property_fields,
    }


def main() -> int:
    args = _arguments()
    reports = args.output.parent
    scanner = _load("h4_static", ROOT / "hardening" / "tools" / "scan_static_baselines.py")
    filesystem = scanner.filesystem_baseline()
    security = scanner.security_baseline(filesystem)
    retained_module = _load("h4_retained_security", ROOT / "manual-tests" / "sprint7-final" / "run_security_scan.py")
    retained_output = reports / "retained_security.json"
    retained_module.OUTPUT = retained_output
    capture = StringIO()
    with redirect_stdout(capture):
        retained_code = int(retained_module.main())
    retained = json.loads(retained_output.read_text(encoding="utf-8")) if retained_output.is_file() else {}
    credential = _credential_surface()
    persistence_path = reports / "persistence.json"
    persistence = json.loads(persistence_path.read_text(encoding="utf-8")) if persistence_path.is_file() else {}
    passed = all((
        filesystem.get("status") in {"PASS", "PASS_WITH_FINDINGS"},
        filesystem.get("runtime_write_surface_count") == 19,
        not filesystem.get("parse_errors"),
        security.get("status") == "PASS",
        not security.get("prohibited_runtime_findings"),
        not security.get("tracked_secret_or_bytecode_files"),
        retained_code == 0,
        retained.get("status") == "PASS",
        not retained.get("violations"),
        not retained.get("package_violations"),
        not retained.get("report_secret_hits"),
        retained.get("live_provider_calls") == 0,
        credential["status"] == "PASS",
        persistence.get("create", {}).get("credential_absent_from_blend") is True,
        persistence.get("reload", {}).get("credential_configured") is False,
    ))
    payload = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if passed else "FAIL",
        "filesystem": {
            "status": filesystem.get("status"),
            "write_surface_count": filesystem.get("write_surface_count"),
            "runtime_write_surface_count": filesystem.get("runtime_write_surface_count"),
            "runtime_artifact_kind_counts": filesystem.get("runtime_artifact_kind_counts"),
            "runtime_safeguard_counts": filesystem.get("runtime_safeguard_counts"),
            "parse_errors": filesystem.get("parse_errors"),
        },
        "security": {
            "status": security.get("status"),
            "runtime_files_scanned": security.get("runtime_files_scanned"),
            "classification_counts": security.get("classification_counts"),
            "prohibited_runtime_findings": security.get("prohibited_runtime_findings"),
            "tracked_secret_or_bytecode_files": security.get("tracked_secret_or_bytecode_files"),
        },
        "retained_security": {
            key: retained.get(key)
            for key in ("status", "violations", "tracked_secret_or_bytecode_files", "package_violations", "report_secret_hits", "live_provider_calls")
        },
        "credential_boundary": credential,
        "persistence_boundary": {
            "credential_absent_from_blend": persistence.get("create", {}).get("credential_absent_from_blend"),
            "credential_configured_after_reload": persistence.get("reload", {}).get("credential_configured"),
        },
        "live_provider_calls": 0,
        "limitations": ["Static inventory plus mock/fake provider tests; no live provider request was authorized or performed."],
    }
    _write_json(args.output, payload)
    print(json.dumps({
        "status": payload["status"],
        "runtime_write_surfaces": payload["filesystem"]["runtime_write_surface_count"],
        "live_provider_calls": 0,
        "credential_violations": len(credential["credential_log_violations"]),
    }, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
