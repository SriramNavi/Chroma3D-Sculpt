"""Static and artifact security audit for the Sprint 7 implementation."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "blender_addon" / "chroma3d_sculpt"
PACKAGE = ROOT / "dist" / "chroma3d_sculpt-0.8.0-alpha.1.zip"
OUTPUT = ROOT / "manual-tests" / "sprint7-final" / "reports" / "security_scan.json"
SERVICE_NAMES = (
    "ai_credentials.py", "ai_provider.py", "provider_transport.py", "openai_provider.py", "fake_ai_provider.py",
    "provider_registry.py", "context_redaction.py", "context_budget.py", "assistance_context.py",
    "recommendation_decoder.py", "recommendation_validator.py", "recommendation_grounding.py",
    "recommendation_resolver.py", "recommendation_explainer.py", "ai_recommendation.py",
    "ai_assistance_session.py", "ai_assistance_coordinator.py", "ai_assistance_report.py", "ai_assistance_audit.py",
)
FILES = (
    RUNTIME / "ai_assistance_settings.py", RUNTIME / "models" / "ai_assistance_models.py",
    RUNTIME / "operators" / "ai_assistance.py", RUNTIME / "ui" / "ai_assistance_panel.py",
    *(RUNTIME / "services" / name for name in SERVICE_NAMES),
)
SECRET_RE = re.compile(r"sk-[A-Za-z0-9_-]{12,}")


def main() -> int:
    violations = []
    network_imports = []
    for path in FILES:
        tree = ast.parse(path.read_text(encoding="utf-8")); relative = path.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec", "compile", "__import__"}:
                    violations.append(f"{relative}: prohibited call {node.func.id}")
                if isinstance(node.func, ast.Attribute) and node.func.attr in {"system", "popen", "Popen", "check_call", "check_output"}:
                    violations.append(f"{relative}: prohibited process call {node.func.attr}")
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                value = ast.unparse(node)
                if any(token in value for token in ("subprocess", "pickle", "requests", "urllib.request", "socket")):
                    violations.append(f"{relative}: prohibited import {value}")
                if "http.client" in value or "ssl" in value:
                    network_imports.append(f"{relative}:{value}")
        if SECRET_RE.search(path.read_text(encoding="utf-8")):
            violations.append(f"{relative}: secret-like literal")
    allowed_network = {
        "blender_addon/chroma3d_sculpt/services/provider_transport.py:import http.client",
        "blender_addon/chroma3d_sculpt/services/provider_transport.py:import ssl",
    }
    if set(network_imports) != allowed_network:
        violations.append(f"network import boundary mismatch: {network_imports}")
    transport = (RUNTIME / "services" / "provider_transport.py").read_text(encoding="utf-8")
    provider = (RUNTIME / "services" / "openai_provider.py").read_text(encoding="utf-8")
    if 'frozenset({"api.openai.com"})' not in transport or 'OPENAI_PATH = "/v1/responses"' not in provider:
        violations.append("OpenAI host/path allow-list mismatch")
    package_violations = []
    if not PACKAGE.is_file():
        package_violations.append("package missing")
    else:
        with zipfile.ZipFile(PACKAGE) as archive:
            for name in archive.namelist():
                lowered = name.lower(); parts = lowered.split("/")
                if any(part in {"tests", "manual-tests", "__pycache__", "sprint7-draft", "sprint7-specification"} for part in parts) or lowered.endswith((".pyc", ".pyo", ".env", ".pem", ".key")):
                    package_violations.append(name)
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False).stdout.splitlines()
    tracked_violations = [name for name in tracked if name.lower().endswith((".env", ".pem", ".p12", ".pfx", ".key", ".pyc")) or "__pycache__" in name.lower().split("/")]
    report_secret_hits = []
    for folder in (ROOT / "manual-tests" / "sprint7" / "reports", ROOT / "manual-tests" / "sprint7-final" / "reports"):
        for path in folder.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".json", ".md", ".log", ".txt"}:
                text = path.read_text(encoding="utf-8", errors="replace")
                if SECRET_RE.search(text):
                    report_secret_hits.append(path.relative_to(ROOT).as_posix())
    status = "PASS" if not violations and not package_violations and not tracked_violations and not report_secret_hits else "FAIL"
    payload = {
        "schema_version": "1.0.0", "status": status, "runtime_files_scanned": len(FILES),
        "violations": violations, "network_imports": network_imports, "package_violations": package_violations,
        "tracked_secret_or_bytecode_files": tracked_violations, "report_secret_hits": report_secret_hits,
        "live_provider_calls": 0, "recorded_at": datetime.now(timezone.utc).isoformat(),
        "limitations": ["Static and local artifact audit; no live-provider penetration test or external security certification."],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True); OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": status, "runtime_files": len(FILES), "violations": len(violations), "package_violations": len(package_violations), "report_secret_hits": len(report_secret_hits)}))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
