"""Aggregate retained Sprint 7 evidence into normal gates S7-01 through S7-20."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "manual-tests" / "sprint7" / "reports"
FINAL_REPORTS = ROOT / "manual-tests" / "sprint7-final" / "reports"
PACKAGE = ROOT / "dist" / "chroma3d_sculpt-0.8.0-alpha.1.zip"
OUTPUT = REPORTS / "sprint7_acceptance.json"


def read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def git(*args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if completed.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed")
    return completed.stdout.strip()


def main() -> int:
    synthetic = read(REPORTS / "synthetic_acceptance.json")
    representative = read(REPORTS / "dataset" / "representative_summary.json")
    full = read(REPORTS / "dataset" / "full_summary.json")
    historical = read(REPORTS / "historical_layers.json")
    installed = read(FINAL_REPORTS / "installed_package_smoke.json")
    performance = read(REPORTS / "performance_environment.json")
    synthetic_by_id = {item.get("id"): item for item in synthetic.get("gates", [])}
    gates = []
    for index in range(1, 16):
        gate_id = f"S7-{index:02d}"; source = synthetic_by_id.get(gate_id, {})
        status = source.get("status", "NOT_RUN")
        detail = {"synthetic_evidence": source.get("detail", {})}
        if gate_id == "S7-14" and status == "PASS":
            status = "PASS_WITH_LIMITATIONS"
            detail["manual_installed_panel_uat"] = "NOT_RUN"
        if gate_id == "S7-13":
            if performance.get("status") != "PASS":
                status = "FAIL"
            detail["performance_environment"] = {key: performance.get(key) for key in ("status", "power_online_observation", "power_interpretation", "point_memory_observation")}
        gates.append({"id": gate_id, "status": status, "detail": detail})
    gates.extend((
        {"id": "S7-16", "status": representative.get("status", "NOT_RUN"), "detail": {key: representative.get(key) for key in ("expected_count", "passed_count", "source_mutation_count", "geometry_payload_count", "timeout_count", "live_provider_calls")}},
        {"id": "S7-17", "status": full.get("status", "NOT_RUN"), "detail": {key: full.get(key) for key in ("expected_count", "passed_count", "source_mutation_count", "geometry_payload_count", "timeout_count", "live_provider_calls")}},
        {"id": "S7-18", "status": historical.get("status", "NOT_RUN"), "detail": {key: historical.get(key) for key in ("total_tests", "frozen_evidence_file_count", "frozen_evidence_changes", "live_provider_calls")}},
    ))
    package_detail = {}
    if PACKAGE.is_file():
        with zipfile.ZipFile(PACKAGE) as archive:
            package_detail = {"file_count": len(archive.infolist()), "size_bytes": PACKAGE.stat().st_size, "sha256": hashlib.sha256(PACKAGE.read_bytes()).hexdigest()}
    package_pass = installed.get("status") == "PASS" and installed.get("installed_inventory_matches_zip") is True and installed.get("temporary_profile_removed") is True
    gates.append({"id": "S7-19", "status": "PASS" if package_pass else "FAIL", "detail": {**package_detail, "installed_smoke": installed.get("status"), "temporary_profile_removed": installed.get("temporary_profile_removed")}})
    branch = git("branch", "--show-current"); head = git("rev-parse", "HEAD"); main = git("rev-parse", "main"); origin_main = git("rev-parse", "origin/main")
    staged = git("diff", "--cached", "--name-only").splitlines(); tracked_package = git("ls-files", "--", "dist").splitlines()
    names = git("status", "--short").splitlines()
    hygiene = branch == "feature/sprint-7-ai-recommendation-foundation" and head == main == origin_main and not staged and not tracked_package and not any("sprint8" in item.lower() or "sprint-8" in item.lower() for item in names)
    gates.append({"id": "S7-20", "status": "PASS_WITH_LIMITATIONS" if hygiene else "FAIL", "detail": {"branch": branch, "head_unchanged_from_base": head == main == origin_main, "staged_files": len(staged), "tracked_zip_count": len(tracked_package), "publication_actions": "NOT_AUTHORIZED", "manual_panel_uat": "NOT_RUN"}})
    failures = [item for item in gates if item["status"] in {"FAIL", "NOT_RUN", "BLOCKED"}]
    limitations = [item for item in gates if item["status"] == "PASS_WITH_LIMITATIONS"]
    payload = {
        "schema_version": "1.0.0", "milestone": "Sprint 7 AI Recommendation Foundation",
        "status": "FAIL" if failures else ("PASS_WITH_LIMITATIONS" if limitations else "PASS"),
        "implementation_status": "PASS" if not failures else "FAIL",
        "release_status": "READY_FOR_MANUAL_PANEL_UAT" if not failures else "BLOCKED",
        "gates": gates, "passed_gate_count": sum(item["status"] == "PASS" for item in gates),
        "limited_gate_count": len(limitations), "failed_gate_count": len(failures), "live_provider_calls": 0,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "limitations": ["Manual installed-panel UAT, Blender 4.5 LTS, live-provider qualification, slicer comparison, material calibration and physical printing are NOT RUN.", "No commit, push, tag, PR, release or Sprint 8 work is authorized."],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True); OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": payload["status"], "pass": payload["passed_gate_count"], "limited": payload["limited_gate_count"], "fail": payload["failed_gate_count"]}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
