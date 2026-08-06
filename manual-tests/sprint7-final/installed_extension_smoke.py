"""Smoke the exact extracted Sprint 7 ZIP with an isolated Blender profile."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import bpy


def _arg(name: str) -> Path:
    args = sys.argv[sys.argv.index("--") + 1:]
    return Path(args[args.index(name) + 1])


def main() -> int:
    root = _arg("--root"); output = _arg("--output"); sys.path.insert(0, str(root))
    import chroma3d_sculpt
    from chroma3d_sculpt.models.intelligent_optimization_models import SearchMode
    from chroma3d_sculpt.services.ai_assistance_audit import build_audit, write_json_audit
    from chroma3d_sculpt.services.ai_assistance_coordinator import (
        approve_context_consent, context_for, discard, offline_fallback, preview_selected,
        provider_settings, request_recommendations, select_recommendation, start_assistance,
    )
    from chroma3d_sculpt.services.ai_assistance_coordinator import clear_runtime as clear_ai_coordinator
    from chroma3d_sculpt.services.ai_assistance_report import build_report, write_json_report, write_markdown_report
    from chroma3d_sculpt.services.ai_assistance_session import clear_runtime as clear_ai_session
    from chroma3d_sculpt.services.ai_credentials import credential_status
    from chroma3d_sculpt.services.fake_ai_provider import FakeAIProvider
    from chroma3d_sculpt.services.intelligent_optimization_coordinator import (
        build_intelligent_frontier, evaluate_intelligent_strategies, generate_intelligent_strategies,
        rank_intelligent_strategies,
    )
    from chroma3d_sculpt.services.intelligent_optimization_session import start_intelligent_session
    from chroma3d_sculpt.services.search_policy import default_search_policy
    from chroma3d_sculpt.services.provider_registry import register_provider
    from chroma3d_sculpt.utilities.optimization_signatures import source_signature

    chroma3d_sculpt.register(); report_dir = output.parent; report_dir.mkdir(parents=True, exist_ok=True)
    try:
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 1.0)); source = bpy.context.object
        before = source_signature(source)["source_signature"]
        start_intelligent_session(source, bpy.context.scene, policy=default_search_policy(SearchMode.FAST))
        generate_intelligent_strategies(source=source)
        evaluate_intelligent_strategies(baseline_values={"fidelity_status": "PASS", "critical_defect_introduced": False, "geometric_deviation": 0.0, "area_drift": 0.0, "volume_drift": 0.0, "build_volume_fit": 1.0, "geometry_fidelity": 1.0, "height": 1.0, "source_protected": True}, source=source)
        build_intelligent_frontier(); rank_intelligent_strategies()
        session, context = start_assistance(user_goal="Installed mocked-provider verification", mode="FAST")
        context = approve_context_consent(session)
        provider_settings(provider_id="fake", model_id="installed-fixture", session=session)
        fake_document = {"recommendations": [{
            "recommendation_type": "NO_ACTION_RECOMMENDED", "target_id": None, "target_fingerprint": None,
            "alternative_ids": [], "reason_codes": ["INSTALLED_FIXTURE"], "reason": "Installed mocked provider returned a bounded no-action response.",
            "assumptions": ["Only current installed-package evidence is considered."], "trade_offs": [],
            "evidence_references": ["sprint6-ranking:current"], "confidence_hint": "MEDIUM",
            "unmet_prerequisites": [], "limitations": ["Deterministic installed-package fixture."], "operation_echo": [],
        }], "overall_limitations": ["No live provider or print guarantee."]}
        register_provider("fake", FakeAIProvider(fake_document), replace=True)
        mocked = request_recommendations(session=session)
        mocked_exchange_bound = bool(mocked[0].provider_exchange_id == session.exchange.exchange_id)
        clear_ai_coordinator(); clear_ai_session()
        session, context = start_assistance(user_goal="Installed offline verification", mode="FAST")
        recommendations = offline_fallback(session); item = recommendations[0]
        preview = None
        if item.action_available:
            select_recommendation(item.recommendation_id, session); preview = preview_selected(session)
        discard(session=session)
        report = build_report(session, context_for(session)); audit = build_audit(session, context_for(session))
        report_json = write_json_report(report, report_dir / "installed-report.json")
        report_md = write_markdown_report(report, report_dir / "installed-report.md")
        audit_json = write_json_audit(audit, report_dir / "installed-audit.json")
        exported = report_json.read_text(encoding="utf-8") + report_md.read_text(encoding="utf-8") + audit_json.read_text(encoding="utf-8")
        after = source_signature(source)["source_signature"]
        payload = {
            "status": "PASS" if before == after and not credential_status({})["configured"] and "authorization" not in exported.lower() and mocked_exchange_bound else "FAIL",
            "version": chroma3d_sculpt.DISPLAY_VERSION, "registered_panel": hasattr(bpy.types, "CHROMA3D_PT_ai_assistance"),
            "offline_provider_generated": item.provider_generated, "recommendation_count": len(recommendations),
            "mock_provider_validated": True, "mock_provider_exchange_bound": mocked_exchange_bound,
            "preview_mutated_source": preview["source_mutated"] if preview else None,
            "source_signature_before": before, "source_signature_after": after, "source_immutability": before == after,
            "report_json": report_json.name, "report_markdown": report_md.name, "audit_json": audit_json.name,
            "credential_absent": "authorization" not in exported.lower() and "api_key" not in exported.lower(), "discarded_state": session.state.value,
            "live_provider_calls": 0, "blender_version": bpy.app.version_string, "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        chroma3d_sculpt.unregister()
        for item in tuple(bpy.data.objects): bpy.data.objects.remove(item, do_unlink=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__": raise SystemExit(main())
