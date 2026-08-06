"""Complete JSON/Markdown evidence export for Sprint 6."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Mapping

from ..metadata import DISPLAY_VERSION
from ..models.intelligent_optimization_models import (
    IntelligentOptimizationAudit,
    IntelligentOptimizationSession,
    STRATEGY_SET_SCHEMA_VERSION,
    plain_value,
)


_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_intelligent_optimization_filename(name: str) -> str:
    value = re.sub(r"[:/\\]+", "_", str(name))
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip(" ._") or "chroma3d_intelligent_optimization"
    if value.split(".", 1)[0].upper() in _RESERVED:
        value = f"_{value}"
    return value


def _mapping(value: Any) -> Mapping[str, Any]:
    if value is None:
        return {}
    return value.to_dict() if hasattr(value, "to_dict") else dict(value)


def build_audit(
    session: IntelligentOptimizationSession,
    *,
    blender_version: str = "",
    sprint5_audit: Mapping[str, Any] | None = None,
    sprint5_policy: Mapping[str, Any] | None = None,
    sprint5_objectives: Mapping[str, Any] | None = None,
    sprint5_candidates: Mapping[str, Any] | None = None,
    search_policy: Mapping[str, Any] | None = None,
    constraints: Mapping[str, Any] | None = None,
) -> IntelligentOptimizationAudit:
    strategy_set = _mapping(session.strategy_set)
    frontier = _mapping(session.frontier)
    return IntelligentOptimizationAudit(
        schema_version="1.0",
        extension_version=DISPLAY_VERSION,
        blender_version=blender_version,
        exported_at=_now(),
        source_identity=session.source_identity,
        source_signature=session.source_signature,
        hardware_profile_hash=session.hardware_profile_hash,
        material_profile_hash=session.material_profile_hash,
        process_context_hash=session.process_context_hash,
        feature_flag_hash=session.feature_flag_hash,
        performance_registry_version=session.performance_registry_version,
        sprint5_policy=dict(sprint5_policy or {}),
        sprint5_objectives=dict(sprint5_objectives or {}),
        sprint5_candidates=dict(sprint5_candidates or {}),
        search_policy=dict(search_policy or {}),
        constraints=dict(constraints or {}),
        budget=session.budget_usage.to_dict(),
        strategy_set=strategy_set,
        evaluations=tuple(item.to_dict() for item in session.evaluations),
        pareto_frontier=frontier,
        rankings=tuple(item.to_dict() for item in session.rankings),
        recommendation=session.recommendation.to_dict() if session.recommendation else None,
        explanations=tuple(item.to_dict() for item in session.explanations),
        selected_strategy_id=session.selected_strategy_id,
        preview_execution_audit=tuple(dict(item) for item in session.preview_audit + session.execution_audit),
        sprint5_audit=dict(sprint5_audit or {}),
        history=session.history.to_dict(),
        stale_events=tuple(dict(item) for item in session.stale_events),
        cancellation_events=tuple(dict(item) for item in session.cancellation_events),
        warnings=tuple(session.warnings),
        failures=tuple(session.failures),
        skipped_evidence=tuple(sorted({item for evaluation in session.evaluations for item in evaluation.skipped_evidence + evaluation.indeterminate_evidence})),
    )


def write_json_audit(audit: IntelligentOptimizationAudit, path: str | Path) -> Path:
    target = Path(path)
    if ".." in str(path).replace("\\", "/").split("/"):
        raise ValueError("Path traversal is not allowed in audit exports.")
    safe_name = sanitize_intelligent_optimization_filename(target.name)
    if safe_name != target.name:
        target = target.with_name(safe_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(audit.to_json().encode("utf-8"))
    return target


def audit_markdown(audit: IntelligentOptimizationAudit) -> str:
    lines = [
        "# Chroma3D Sculpt Intelligent Optimization Audit", "",
        f"- Extension: `{audit.extension_version}`", f"- Blender: `{audit.blender_version or 'not recorded'}`",
        f"- Audit schema: `{audit.schema_version}`", f"- Strategy schema: `{STRATEGY_SET_SCHEMA_VERSION}`",
        f"- Source signature: `{audit.source_signature}`", "", "## Safety", "",
        audit.advisory_disclaimer, "", "- Protected source is never mutated by search, ranking, or recommendation.",
        "- Preview and execution require explicit user selection inside the Sprint 5 isolated workspace.",
        "- No automatic execution, source replacement, slicer, G-code, printer command, or physical validation.", "",
        "## Search evidence", "", f"- Strategies: `{len(audit.strategy_set.get('strategies', []))}`",
        f"- Evaluations: `{len(audit.evaluations)}`", f"- Pareto points: `{len(audit.pareto_frontier.get('points', []))}`",
        f"- Rankings: `{len(audit.rankings)}`", f"- Selected strategy: `{audit.selected_strategy_id or 'none'}`", "",
        "## Limitations", "", "- Unknown, skipped, and estimated evidence remains visible and is not promoted to PASS.",
        "- Ranking is a recommendation within the evaluated bounded search, not a global optimum.", "",
        "## Deterministic payload", "", "```json", audit.to_json().rstrip("\n"), "```", "",
    ]
    return "\n".join(lines)


def write_markdown_audit(audit: IntelligentOptimizationAudit, path: str | Path) -> Path:
    target = Path(path)
    if ".." in str(path).replace("\\", "/").split("/"):
        raise ValueError("Path traversal is not allowed in audit exports.")
    safe_name = sanitize_intelligent_optimization_filename(target.name)
    if safe_name != target.name:
        target = target.with_name(safe_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(audit_markdown(audit), encoding="utf-8", newline="\n")
    return target


__all__ = ("audit_markdown", "build_audit", "sanitize_intelligent_optimization_filename", "write_json_audit", "write_markdown_audit")
