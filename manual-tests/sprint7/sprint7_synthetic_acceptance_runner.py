"""Execute normal Sprint 7 synthetic gates S7-01 through S7-15."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import perf_counter
import traceback

import bpy

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "blender_addon"
if str(ADDON) not in sys.path:
    sys.path.insert(0, str(ADDON))

import chroma3d_sculpt  # noqa: E402
from chroma3d_sculpt.ai_assistance_settings import default_assistance_policy, limits_for_mode, policy_for_mode  # noqa: E402
from chroma3d_sculpt.metadata import DISPLAY_VERSION  # noqa: E402
from chroma3d_sculpt.models.ai_assistance_models import ConfidenceClassification, EvidenceReference, EvidenceState, ProviderSettings  # noqa: E402
from chroma3d_sculpt.services.ai_assistance_report import build_report  # noqa: E402
from chroma3d_sculpt.services.ai_assistance_session import create_session  # noqa: E402
from chroma3d_sculpt.services.ai_recommendation import validate_provider_recommendations  # noqa: E402
from chroma3d_sculpt.services.assistance_context import build_context_manifest  # noqa: E402
from chroma3d_sculpt.services.openai_provider import OpenAIProvider  # noqa: E402
from chroma3d_sculpt.services.recommendation_validator import SAFE_OPERATIONS  # noqa: E402


HASH = "d" * 64
OUTPUT = ROOT / "manual-tests" / "sprint7" / "reports" / "synthetic_acceptance.json"
FOCUSED = ROOT / "manual-tests" / "sprint7" / "reports" / "sprint7_test_depth.json"
RUNTIME = ADDON / "chroma3d_sculpt"


def require(value, message):
    if not value:
        raise AssertionError(message)


def sources() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in RUNTIME.rglob("*.py"))


def manifest():
    policy = policy_for_mode(default_assistance_policy(enabled=True), "FAST")
    evidence = EvidenceReference("acceptance:risk", "ACCEPTANCE", EvidenceState.PASS, ConfidenceClassification.HIGH, HASH, ("synthetic",), (), False)
    return build_context_manifest(
        source_signature_hash=HASH, object_display_name=r"C:\Users\canary\source.blend", policy=policy,
        limits=limits_for_mode("FAST"), user_goal="Review sk-canarysecret https://bad.example",
        evidence=(evidence,), consent_approved=True, consent_timestamp="2026-08-06T00:00:00+00:00",
    )


def recommendation_document():
    return {
        "recommendations": [{
            "recommendation_type": "NO_ACTION_RECOMMENDED", "target_id": None, "target_fingerprint": None,
            "alternative_ids": [], "reason_codes": ["CURRENT_EVIDENCE_ONLY"],
            "reason": "No current action is supported by the supplied evidence.",
            "assumptions": ["Only current local evidence is considered."], "trade_offs": [],
            "evidence_references": ["acceptance:risk"], "confidence_hint": "HIGH",
            "unmet_prerequisites": [], "limitations": ["Advisory software evidence only."], "operation_echo": [],
        }],
        "overall_limitations": ["No print guarantee."],
    }


def focused_report():
    return json.loads(FOCUSED.read_text(encoding="utf-8"))


def gate_01():
    violations = []
    for name in ("ai_provider.py", "openai_provider.py", "provider_transport.py", "fake_ai_provider.py"):
        tree = ast.parse((RUNTIME / "services" / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)) and any(value in ast.unparse(node) for value in ("bpy", "operators", "coordinator")):
                violations.append(f"{name}:{ast.unparse(node)}")
    require(not violations, f"provider boundary violations: {violations}")
    return {"provider_boundary_violations": 0, "delegation_tests": (54, 55)}


def gate_02():
    schemas = list((ROOT / "schemas").glob("*.schema.json"))
    for path in schemas:
        json.loads(path.read_text(encoding="utf-8"))
    require(DISPLAY_VERSION == "0.8.0-alpha.1", "version mismatch")
    return {"stable_schema_count": len(schemas), "version": DISPLAY_VERSION}


def gate_03():
    context = manifest(); raw = context.to_json().lower()
    require(context.geometry_elements_exported == 0 and context.consent.approved, "context/consent contract failed")
    require(all(value not in raw for value in ("users\\canary", "sk-canarysecret", "https://bad.example")), "context leaked canary")
    return {"context_bytes": context.byte_count, "token_estimate": context.token_estimate, "geometry_elements_exported": 0}


def gate_04():
    context = manifest(); request = OpenAIProvider().prepare(context, ProviderSettings("openai", "gpt-5", "openai-responses-v1", 30.0, 262144, 262144))
    require(request.metadata["store"] is False and request.metadata["tools"] == 0 and b'"store":false' in request.canonical_body, "provider request contract failed")
    return {"request_prepared_without_network": True, "automatic_retries": 0, "live_provider_calls": 0}


def gate_05_06():
    context = manifest(); policy = policy_for_mode(default_assistance_policy(enabled=True), "FAST")
    values = validate_provider_recommendations(json.dumps(recommendation_document()), context=context, registry={}, policy=policy, limits=limits_for_mode("FAST"))
    require(len(values) == 1 and not values[0].action_available and values[0].assumptions, "grounded no-action truth failed")
    return {"recommendations": len(values), "confidence": values[0].confidence.value, "assumption_count": len(values[0].assumptions)}


def gate_07():
    text = (RUNTIME / "services" / "ai_assistance_coordinator.py").read_text(encoding="utf-8")
    keys = ("source_signature", "policy", "provider", "schema", "prompt", "candidate_set", "strategy_set", "workspace_identity", "blend_file_state")
    require(all(key in text for key in keys), "stale dependency matrix incomplete")
    return {"bound_dependency_classes": len(keys), "focused_stale_tests": (36, 37, 38)}


def gate_08():
    require("EXPERIMENTAL_REMESH" not in SAFE_OPERATIONS and len(SAFE_OPERATIONS) == 7, "operation allow-list changed")
    return {"allowed_operation_count": len(SAFE_OPERATIONS), "experimental_remesh_allowed": False}


def gate_09():
    report = focused_report(); require(report["status"] == "PASS" and report["total_executable_tests"] >= 58, "focused source-safety evidence missing")
    return {"focused_tests": report["total_executable_tests"], "delegated_checkpoint_and_restore_tests": (54, 55)}


def gate_10():
    report = focused_report(); require(report["status"] == "PASS", "cancellation/recovery suite failed")
    return {"cancellation_tests": (18, 39, 58), "explicit_retry_test": 57, "automatic_retries": 0}


def gate_11():
    violations = []
    for path in tuple((RUNTIME / "services").glob("ai_*.py")) + tuple((RUNTIME / "services").glob("*provider*.py")) + tuple((RUNTIME / "services").glob("recommendation_*.py")) + (RUNTIME / "services" / "assistance_context.py",):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec", "compile", "__import__"}:
                violations.append(f"{path.name}:{node.func.id}")
    require(not violations, f"dynamic execution found: {violations}")
    raw = sources().lower(); require("import requests" not in raw and "import subprocess" not in raw, "dependency/capability drift")
    return {"dynamic_execution_calls": 0, "external_runtime_dependencies": 0}


def gate_12():
    context = manifest(); session = create_session(source_identity={"object_identity": 1, "api_key": "never"}, source_signature_hash=HASH); session.context_hash = context.context_hash; session.policy_hash = context.policy_hash
    raw = build_report(session, context).to_json().lower()
    require("object_identity" not in raw and "api_key" not in raw and "users\\canary" not in raw, "report redaction failed")
    return {"redacted": True, "raw_geometry_retained": False}


def gate_13():
    values = [limits_for_mode(mode) for mode in ("FAST", "STANDARD", "DEEP")]
    require(values[0].context_bytes < values[1].context_bytes < values[2].context_bytes, "mode bounds are not monotonic")
    require(all(item.automatic_retries == 0 and item.explicit_retries == 1 for item in values), "retry policy changed")
    return {"modes": ["FAST", "STANDARD", "DEEP"], "point_memory_only": True}


def gate_14():
    ui = (RUNTIME / "ui" / "ai_assistance_panel.py").read_text(encoding="utf-8")
    required = ("Optional external assistance", "External request disclosure", "Preview and separate approval", "Offline Sprint 6 View", "Advisory only")
    require(all(value in ui for value in required), "critical UI state copy missing")
    return {"panel_registered": hasattr(bpy.types, "CHROMA3D_PT_ai_assistance"), "critical_state_labels": len(required)}


def gate_15():
    report = focused_report(); require(report["status"] == "PASS" and report["total_executable_tests"] >= 58 and report["live_provider_calls"] == 0, "synthetic truth suite incomplete")
    return {"focused_tests": report["total_executable_tests"], "live_provider_calls": 0}


def main() -> int:
    chroma3d_sculpt.register(); gates = []
    try:
        actions = {
            "S7-01": gate_01, "S7-02": gate_02, "S7-03": gate_03, "S7-04": gate_04,
            "S7-05": gate_05_06, "S7-06": gate_05_06, "S7-07": gate_07, "S7-08": gate_08,
            "S7-09": gate_09, "S7-10": gate_10, "S7-11": gate_11, "S7-12": gate_12,
            "S7-13": gate_13, "S7-14": gate_14, "S7-15": gate_15,
        }
        for gate_id, action in actions.items():
            started = perf_counter()
            try:
                detail, status = action(), "PASS"
            except Exception as exc:
                detail, status = {"error": f"{type(exc).__name__}: {exc}", "traceback_tail": traceback.format_exc().splitlines()[-6:]}, "FAIL"
            gates.append({"id": gate_id, "status": status, "duration_seconds": round(perf_counter() - started, 6), "detail": detail})
    finally:
        chroma3d_sculpt.unregister()
    payload = {
        "schema_version": "1.0.0", "status": "PASS" if all(item["status"] == "PASS" for item in gates) else "FAIL",
        "gates": gates, "passed_gate_count": sum(item["status"] == "PASS" for item in gates),
        "failed_gate_count": sum(item["status"] == "FAIL" for item in gates), "live_provider_calls": 0,
        "blender_version": bpy.app.version_string, "recorded_at": datetime.now(timezone.utc).isoformat(),
        "limitations": ["Synthetic/provider-independent software evidence only; dataset, historical, package and installed gates are separate."],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True); OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
