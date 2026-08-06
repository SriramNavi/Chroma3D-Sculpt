"""Shared repository metadata for development scripts."""

from __future__ import annotations

from pathlib import Path
import runpy
import tomllib
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "blender_addon" / "chroma3d_sculpt"
DIST_DIRECTORY = REPOSITORY_ROOT / "dist"
MANIFEST_PATH = SOURCE_ROOT / "blender_manifest.toml"
LICENSE_PATH = REPOSITORY_ROOT / "LICENSE"

_metadata: dict[str, Any] = runpy.run_path(str(SOURCE_ROOT / "metadata.py"))
EXTENSION_ID = str(_metadata["EXTENSION_ID"])
MANIFEST_VERSION = str(_metadata["EXTENSION_VERSION"])
DISPLAY_VERSION = str(_metadata["DISPLAY_VERSION"])
PACKAGE_FILENAME = f"{EXTENSION_ID}-{DISPLAY_VERSION}.zip"
PACKAGE_PATH = DIST_DIRECTORY / PACKAGE_FILENAME

REQUIRED_SOURCE_FILES = (
    "__init__.py",
    "analysis_settings.py",
    "printability_settings.py",
    "feature_flags.py",
    "performance_registry.py",
    "optimization_settings.py",
    "intelligent_optimization_settings.py",
    "ai_assistance_settings.py",
    "repair_settings.py",
    "blender_manifest.toml",
    "metadata.py",
    "session.py",
    "models/__init__.py",
    "models/analysis_result.py",
    "models/repair_models.py",
    "models/printability_models.py",
    "models/advanced_preparation_models.py",
    "models/optimization_models.py",
    "models/intelligent_optimization_models.py",
    "models/ai_assistance_models.py",
    "operators/__init__.py",
    "operators/analyze_mesh.py",
    "operators/export_report.py",
    "operators/select_issue.py",
    "operators/repair.py",
    "operators/printability.py",
    "operators/advanced_preparation.py",
    "operators/optimization.py",
    "operators/intelligent_optimization.py",
    "operators/ai_assistance.py",
    "services/__init__.py",
    "services/mesh_analyzer.py",
    "services/topology_analyzer.py",
    "services/shell_analyzer.py",
    "services/deep_diagnostics.py",
    "services/build_volume_analyzer.py",
    "services/report_generator.py",
    "services/repair_audit.py",
    "services/repair_coordinator.py",
    "services/repair_operations.py",
    "services/repair_plan.py",
    "services/repair_session.py",
    "services/printer_profile_loader.py",
    "services/geometry_facts.py",
    "services/wall_thickness.py",
    "services/thin_features.py",
    "services/overhang_analysis.py",
    "services/floating_components.py",
    "services/build_plate_contact.py",
    "services/scale_evaluation.py",
    "services/orientation_analysis.py",
    "services/printability_scoring.py",
    "services/printability_session.py",
    "services/printability_report.py",
    "services/printability_coordinator.py",
    "services/hardware_profile_loader.py",
    "services/material_profile_loader.py",
    "services/process_context.py",
    "services/bridge_risk.py",
    "services/support_risk.py",
    "services/resin_advisory.py",
    "services/advanced_scale.py",
    "services/advanced_orientation.py",
    "services/advanced_preparation_coordinator.py",
    "services/advanced_preparation_session.py",
    "services/advanced_preparation_report.py",
    "services/batch_preparation.py",
    "services/batch_preparation_session.py",
    "services/printability_baseline.py",
    "services/regression_dashboard.py",
    "services/optimization_policy.py",
    "services/optimization_workspace.py",
    "services/optimization_candidates.py",
    "services/optimization_plan.py",
    "services/optimization_operations.py",
    "services/optimization_comparison.py",
    "services/optimization_audit.py",
    "services/optimization_session.py",
    "services/optimization_coordinator.py",
    "services/search_policy.py",
    "services/constraint_engine.py",
    "services/strategy_generator.py",
    "services/strategy_evaluator.py",
    "services/pareto_frontier.py",
    "services/strategy_ranker.py",
    "services/strategy_explainer.py",
    "services/strategy_history.py",
    "services/intelligent_optimization_audit.py",
    "services/intelligent_optimization_session.py",
    "services/intelligent_optimization_coordinator.py",
    "services/ai_credentials.py",
    "services/ai_provider.py",
    "services/provider_transport.py",
    "services/openai_provider.py",
    "services/fake_ai_provider.py",
    "services/provider_registry.py",
    "services/context_redaction.py",
    "services/context_budget.py",
    "services/assistance_context.py",
    "services/recommendation_decoder.py",
    "services/recommendation_validator.py",
    "services/recommendation_grounding.py",
    "services/recommendation_resolver.py",
    "services/recommendation_explainer.py",
    "services/ai_recommendation.py",
    "services/ai_assistance_session.py",
    "services/ai_assistance_coordinator.py",
    "services/ai_assistance_report.py",
    "services/ai_assistance_audit.py",
    "ui/__init__.py",
    "ui/panels.py",
    "ui/properties.py",
    "ui/repair_panel.py",
    "ui/printability_panel.py",
    "ui/advanced_preparation_panel.py",
    "ui/optimization_panel.py",
    "ui/intelligent_optimization_panel.py",
    "ui/ai_assistance_panel.py",
    "utilities/__init__.py",
    "utilities/blender_paths.py",
    "utilities/context.py",
    "utilities/geometry.py",
    "utilities/logging.py",
    "utilities/units.py",
    "utilities/signatures.py",
    "utilities/boundary_loops.py",
    "utilities/repair_signatures.py",
    "utilities/printability_signatures.py",
    "utilities/optimization_signatures.py",
)

PACKAGE_ASSET_FILES = tuple(
    [f"profiles/printability/{name}" for name in (
        "generic_fdm.json", "generic_resin.json", "bambu_x1_carbon.json", "bambu_p1s.json", "prusa_mk4.json", "custom_profile.template.json",
    )]
    + [f"schemas/{name}" for name in (
        "printer_profile.schema.json", "printability_settings.schema.json", "printability_report.schema.json", "printability_risk_item.schema.json", "orientation_candidate.schema.json",
        "material_profile.schema.json", "feature_flags.schema.json", "performance_registry.schema.json", "composed_process_context.schema.json",
        "advanced_preparation_report.schema.json", "batch_preparation.schema.json", "printability_baseline.schema.json", "regression_dashboard.schema.json",
        "optimization_plan.schema.json", "optimization_session.schema.json", "optimization_audit.schema.json", "optimization_comparison.schema.json", "optimization_candidate.schema.json", "optimization_policy.schema.json",
        "intelligent_strategy.schema.json", "strategy_set.schema.json", "intelligent_search_policy.schema.json", "constraint_set.schema.json", "pareto_frontier.schema.json", "strategy_ranking.schema.json", "strategy_explanation.schema.json", "optimization_history.schema.json", "intelligent_optimization_audit.schema.json",
        "assistance_policy.schema.json", "context_manifest.schema.json", "provider_exchange.schema.json", "ai_recommendation.schema.json", "assistance_session.schema.json", "assistance_report.schema.json", "assistance_audit.schema.json",
    )]
    + [f"profiles/materials/{name}" for name in (
        "generic_pla.json", "generic_petg.json", "generic_abs.json", "generic_asa.json", "generic_tpu.json", "generic_resin.json", "custom_material.template.json",
    )]
)


def read_manifest_bytes(data: bytes) -> dict[str, Any]:
    return tomllib.loads(data.decode("utf-8"))


def read_source_manifest() -> dict[str, Any]:
    return read_manifest_bytes(MANIFEST_PATH.read_bytes())


def validate_source_layout() -> None:
    if REPOSITORY_ROOT.name != "Chroma3D Sculpt":
        raise RuntimeError(f"Unexpected repository root: {REPOSITORY_ROOT}")
    if not SOURCE_ROOT.is_dir():
        raise FileNotFoundError(f"Extension source is missing: {SOURCE_ROOT}")
    missing = [relative for relative in REQUIRED_SOURCE_FILES if not (SOURCE_ROOT / relative).is_file()]
    if not LICENSE_PATH.is_file():
        missing.append("LICENSE")
    if missing:
        raise FileNotFoundError("Required file(s) missing: " + ", ".join(missing))
    missing_assets = [relative for relative in PACKAGE_ASSET_FILES if not (REPOSITORY_ROOT / relative).is_file()]
    if missing_assets:
        raise FileNotFoundError("Required package asset(s) missing: " + ", ".join(missing_assets))
    manifest = read_source_manifest()
    expected = {
        "schema_version": "1.0.0",
        "id": EXTENSION_ID,
        "version": MANIFEST_VERSION,
        "type": "add-on",
    }
    mismatches = [f"{key}={manifest.get(key)!r} (expected {value!r})" for key, value in expected.items() if manifest.get(key) != value]
    if mismatches:
        raise ValueError("Invalid manifest metadata: " + "; ".join(mismatches))
