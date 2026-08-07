"""Run the reusable focused H1 compile, ledger, registration, contract, and graph gates."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
REPORTS = ROOT / "manual-tests" / "hardening" / "reports" / "h1"
LOGS = REPORTS / "logs"
TOOLS = ROOT / "hardening" / "tools"
BLENDER_DEFAULT = Path(r"D:\Softwares\Design\Blender\blender.exe")
H0_CONTRACT = ROOT / "hardening" / "baseline" / "public_contract_baseline.json"
EXPLAINED_DEAD_SERIALIZED_KEYS = {
    "analysis_duration_ms",
    "build_volume_result",
    "degenerate_faces",
    "loose_edges",
    "loose_vertices",
    "orientation_state",
    "potential_duplicate_vertices",
    "reliable_volume_mm3",
    "surface_area_mm2",
    "tiny_shell_candidates",
    "watertightness",
    "world_space_bounding_box_mm",
    "zero_length_edges",
}


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def _run(command: list[str], name: str, timeout: int = 600) -> dict[str, Any]:
    started = time.perf_counter()
    completed = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, check=False,
    )
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / f"{name}.log").write_text(
        completed.stdout + ("\n" if completed.stdout and completed.stderr else "") + completed.stderr,
        encoding="utf-8", newline="\n",
    )
    return {
        "returncode": completed.returncode,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "stdout_tail": completed.stdout.splitlines()[-20:],
        "stderr_tail": completed.stderr.splitlines()[-20:],
    }


def _python(script: Path, name: str, *args: str, timeout: int = 600) -> dict[str, Any]:
    return _run([sys.executable, str(script), *args], name, timeout)


def _blender(blender: Path, script: Path, name: str, *args: str, timeout: int = 600) -> dict[str, Any]:
    return _run([
        str(blender), "--background", "--factory-startup", "--python-exit-code", "1",
        "--python", str(script), "--", *args,
    ], name, timeout)


def _contract_comparison(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "product_version", "operator_bl_idnames", "panel_ids", "property_names",
        "manifest", "metadata_versions", "schemas", "package_module_roots",
        "profile_ids", "feature_flag_ids", "status_and_result_enums",
        "important_serialized_keys",
    )
    changed = [field for field in fields if current.get(field) != baseline.get(field)]
    removed_serialized_keys = sorted(
        set(baseline.get("important_serialized_keys", ()))
        - set(current.get("important_serialized_keys", ()))
    )
    added_serialized_keys = sorted(
        set(current.get("important_serialized_keys", ()))
        - set(baseline.get("important_serialized_keys", ()))
    )
    explained_dead_artifact_only = (
        changed == ["important_serialized_keys"]
        and set(removed_serialized_keys) == EXPLAINED_DEAD_SERIALIZED_KEYS
        and not added_serialized_keys
    )
    return {
        "status": "PASS" if not changed or explained_dead_artifact_only else "FAIL",
        "changed_fields": changed,
        "disposition": "EXPLAINED_DEAD_PRIVATE_HELPER_KEYS" if explained_dead_artifact_only else ("IDENTICAL" if not changed else "UNEXPLAINED_CHANGE"),
        "removed_serialized_keys": removed_serialized_keys,
        "added_serialized_keys": added_serialized_keys,
        "external_contract_changed": bool(changed) and not explained_dead_artifact_only,
        "counts": {
            "operators": len(current.get("operator_bl_idnames", ())),
            "panels": len(current.get("panel_ids", ())),
            "properties": len(current.get("property_names", ())),
            "schemas": len(current.get("schemas", ())),
            "feature_flags": len(current.get("feature_flag_ids", ())),
            "enums": len(current.get("status_and_result_enums", ())),
        },
        "baseline_contract_sha256": baseline.get("contract_sha256"),
        "current_contract_sha256": current.get("contract_sha256"),
    }


def run(blender: Path) -> dict[str, Any]:
    REPORTS.mkdir(parents=True, exist_ok=True)
    gates: list[dict[str, Any]] = []

    compile_result = _run([
        sys.executable, "-m", "compileall", "-q", "blender_addon", "scripts", "tests",
        "hardening", "manual-tests",
    ], "focused_compile", 600)
    gates.append({"id": "H1-F01", "name": "compile", "status": "PASS" if not compile_result["returncode"] else "FAIL", "detail": compile_result})

    ledger_result = _python(
        ROOT / "manual-tests" / "hardening" / "h1" / "verify_candidate_removal.py",
        "focused_ledger", "--check-only",
    )
    gates.append({"id": "H1-F02", "name": "ledger", "status": "PASS" if not ledger_result["returncode"] else "FAIL", "detail": ledger_result})

    registration_path = REPORTS / "registration.json"
    registration_result = _blender(
        blender, ROOT / "manual-tests" / "hardening" / "measure_registration.py",
        "focused_registration", "--output", str(registration_path), "--iterations", "3",
    )
    registration = json.loads(registration_path.read_text(encoding="utf-8")) if registration_path.is_file() else {}
    registration_pass = not registration_result["returncode"] and registration.get("status") == "PASS" and registration.get("expected_class_count") == 82
    gates.append({"id": "H1-F03", "name": "registration", "status": "PASS" if registration_pass else "FAIL", "detail": registration})

    contract_path = REPORTS / "public_contract.json"
    contract_result = _python(
        TOOLS / "capture_public_contract.py", "focused_contract",
        "--output", str(contract_path), "--markdown", str(REPORTS / "PUBLIC_CONTRACT.md"),
    )
    current_contract = json.loads(contract_path.read_text(encoding="utf-8")) if contract_path.is_file() else {}
    baseline_contract = json.loads(H0_CONTRACT.read_text(encoding="utf-8"))
    contract_comparison = _contract_comparison(current_contract, baseline_contract)
    contract_pass = not contract_result["returncode"] and contract_comparison["status"] == "PASS"
    gates.append({"id": "H1-F04", "name": "public_contract", "status": "PASS" if contract_pass else "FAIL", "detail": contract_comparison})

    dependency_path = REPORTS / "dependency_graph.json"
    dependency_result = _python(
        TOOLS / "analyze_dependencies.py", "focused_dependencies",
        "--output", str(dependency_path), "--markdown", str(REPORTS / "DEPENDENCY_GRAPH.md"),
    )
    dependency = json.loads(dependency_path.read_text(encoding="utf-8")) if dependency_path.is_file() else {}
    dependency_pass = not dependency_result["returncode"] and not dependency.get("parse_errors") and not dependency.get("potential_circular_imports")
    gates.append({
        "id": "H1-F05", "name": "dependency_graph", "status": "PASS" if dependency_pass else "FAIL",
        "detail": {
            "module_count": dependency.get("module_count"),
            "internal_dependency_count": dependency.get("internal_dependency_count"),
            "circular_components": len(dependency.get("potential_circular_imports", ())),
            "statically_unreferenced_candidates": len(dependency.get("statically_unreferenced_candidates", ())),
        },
    })

    diff_result = _run(["git", "diff", "--check"], "focused_diff_check", 120)
    gates.append({"id": "H1-F06", "name": "diff_check", "status": "PASS" if not diff_result["returncode"] else "FAIL", "detail": diff_result})

    failures = [gate["id"] for gate in gates if gate["status"] != "PASS"]
    payload = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not failures else "FAIL",
        "gates": gates,
        "failures": failures,
        "registration": registration,
        "public_contract": contract_comparison,
        "dependency_graph": dependency,
    }
    _write_json(REPORTS / "focused_validation.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, default=BLENDER_DEFAULT)
    args = parser.parse_args()
    if not args.blender.is_file():
        print(json.dumps({"status": "FAIL", "reason": f"Blender not found: {args.blender}"}))
        return 2
    payload = run(args.blender.resolve())
    print(json.dumps({
        "status": payload["status"],
        "gates": {gate["id"]: gate["status"] for gate in payload["gates"]},
        "failures": payload["failures"],
    }, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
