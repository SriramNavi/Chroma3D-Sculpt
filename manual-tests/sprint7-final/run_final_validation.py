"""Aggregate exact S7F-A through S7F-R evidence without live calls."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "manual-tests" / "sprint7-final" / "reports"
NORMAL_REPORTS = ROOT / "manual-tests" / "sprint7" / "reports"
OUTPUT = REPORTS / "sprint7_final_validation.json"


def read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> int:
    independent = read(REPORTS / "final_validation_results.json")
    installed = read(REPORTS / "installed_package_smoke.json")
    security = read(REPORTS / "security_scan.json")
    representative = read(NORMAL_REPORTS / "dataset" / "representative_summary.json")
    full = read(NORMAL_REPORTS / "dataset" / "full_summary.json")
    historical = read(NORMAL_REPORTS / "historical_layers.json")
    synthetic = read(NORMAL_REPORTS / "synthetic_acceptance.json")
    focused = read(NORMAL_REPORTS / "sprint7_test_depth.json")
    acceptance = read(NORMAL_REPORTS / "sprint7_acceptance.json")
    release_identity = read(NORMAL_REPORTS / "release_input_fingerprint.json")

    by_id = {item.get("id"): dict(item) for item in independent.get("gates", []) if isinstance(item, dict)}
    gate_a = by_id.get("S7F-A", {"id": "S7F-A", "title": "Static safety and package scope", "status": "FAIL", "detail": {}})
    gate_a["status"] = "PASS" if gate_a.get("status") == "PASS" and security.get("status") == "PASS" else "FAIL"
    gate_a["detail"] = {
        **dict(gate_a.get("detail", {})),
        "security_scan": security.get("status", "NOT_RUN"),
        "runtime_violations": len(security.get("violations", ())),
        "package_violations": len(security.get("package_violations", ())),
    }
    by_id["S7F-A"] = gate_a

    package_pass = all((
        installed.get("status") == "PASS",
        installed.get("installed_inventory_matches_zip") is True,
        installed.get("temporary_profile_removed") is True,
        installed.get("smoke", {}).get("registered_panel") is True,
        installed.get("package_unchanged_during_smoke") is True,
    ))
    by_id["S7F-P"] = {
        "id": "S7F-P", "title": "Package and installed behavior",
        "status": "PASS" if package_pass else "FAIL",
        "detail": {
            "installed_smoke": installed.get("status", "NOT_RUN"),
            "inventory_matches": installed.get("installed_inventory_matches_zip"),
            "panel_registered": installed.get("smoke", {}).get("registered_panel"),
            "temporary_profile_removed": installed.get("temporary_profile_removed"),
            "package_sha256": installed.get("package_sha256"),
            "package_unchanged_during_smoke": installed.get("package_unchanged_during_smoke"),
        },
    }
    by_id["S7F-R"] = {
        "id": "S7F-R", "title": "Manual and live disposition", "status": "PASS_WITH_LIMITATIONS",
        "detail": {
            "manual_installed_panel_uat": "NOT_RUN", "live_openai_call": "NOT_RUN",
            "blender_4_5_lts": "NOT_RUN", "slicer_material_physical": "NOT_RUN",
            "live_provider_calls": 0,
        },
    }

    expected_executable = tuple(f"S7F-{letter}" for letter in "ABCDEFGHIJKLMNOPQ")
    gates = [by_id.get(gate_id, {"id": gate_id, "title": "Missing required gate", "status": "FAIL", "detail": {}}) for gate_id in expected_executable]
    gates.append(by_id["S7F-R"])

    supporting = {
        "focused": focused.get("status", "NOT_RUN"),
        "synthetic": synthetic.get("status", "NOT_RUN"),
        "representative_dataset": representative.get("status", "NOT_RUN"),
        "full_dataset": full.get("status", "NOT_RUN"),
        "historical": historical.get("status", "NOT_RUN"),
        "normal_acceptance": acceptance.get("status", "NOT_RUN"),
        "security": security.get("status", "NOT_RUN"),
        "installed_package": installed.get("status", "NOT_RUN"),
        "release_input_fingerprint": release_identity.get("aggregate_sha256", "MISSING"),
    }
    supporting_failures = {
        key: status for key, status in supporting.items()
        if key != "release_input_fingerprint" and status not in {"PASS", "PASS_WITH_LIMITATIONS"}
    }
    if supporting["release_input_fingerprint"] == "MISSING":
        supporting_failures["release_input_fingerprint"] = "MISSING"

    failures = [item for item in gates if item.get("status") in {"FAIL", "NOT_RUN", "BLOCKED"}]
    limited = [item for item in gates if item.get("status") == "PASS_WITH_LIMITATIONS"]
    status = "FAIL" if failures or supporting_failures else ("PASS_WITH_LIMITATIONS" if limited else "PASS")
    failure_files = sorted(path.name for path in (ROOT / "manual-tests" / "sprint7").glob("*FIRST_FAILURE.md")) + sorted(path.name for path in (ROOT / "manual-tests" / "sprint7-final").glob("*FIRST_FAILURE.md"))
    payload = {
        "schema_version": "1.1.0", "milestone": "Sprint 7 AI Recommendation Foundation",
        "status": status, "gates": gates,
        "passed_gate_count": sum(item.get("status") == "PASS" for item in gates),
        "limited_gate_count": len(limited), "failed_gate_count": len(failures),
        "supporting_release_gates": supporting, "supporting_failures": supporting_failures,
        "first_failure_files": failure_files, "live_provider_calls": 0,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "limitations": ["Manual installed-panel UAT, Blender 4.5 LTS, live-provider qualification, slicer/material/physical validation are NOT_RUN."],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": status, "pass": payload["passed_gate_count"], "limited": len(limited), "fail": len(failures), "supporting_failures": supporting_failures}, sort_keys=True))
    return 0 if status != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
