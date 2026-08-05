"""Complete JSON/Markdown audit generation for controlled optimization."""

from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Any, Iterable

from ..metadata import DISPLAY_VERSION
from ..models.optimization_models import OptimizationAudit, OptimizationSession


_WINDOWS_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{index}" for index in range(1, 10)), *(f"LPT{index}" for index in range(1, 10))}


def sanitize_optimization_filename(name: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", str(name)).strip("._") or "optimization"
    stem = stem[:120]
    if stem.upper().split(".", 1)[0] in _WINDOWS_RESERVED_NAMES:
        stem = f"{stem}_file"
    return stem


def build_audit(session: OptimizationSession, *, blender_version: str = "", candidates: Iterable[Any] | None = None) -> OptimizationAudit:
    selected_candidates = tuple(candidates if candidates is not None else session.candidates)
    return OptimizationAudit(
        schema_version="1.0", extension_version=DISPLAY_VERSION, blender_version=blender_version,
        exported_at=session.acceptance.accepted_at if session.acceptance else session.discard.discarded_at if session.discard else session.started_at,
        source_identity={
            "object_name": session.source_object_name, "object_identity": session.source_object_identity,
            "mesh_name": session.source_mesh_name, "mesh_identity": session.source_mesh_identity,
        },
        source_signature=session.source_signature,
        workspace_identity={
            "object_name": session.workspace_object_name, "object_identity": session.workspace_object_identity,
            "mesh_name": session.workspace_mesh_name, "mesh_identity": session.workspace_mesh_identity,
            "initial_signature": session.initial_workspace_signature, "current_signature": session.current_workspace_signature,
        },
        process_context_hash=session.process_context_hash, feature_flag_hash=session.feature_flag_hash,
        performance_registry_version=session.performance_registry_version,
        optimization_policy=session.policy_snapshot.to_dict() if session.policy_snapshot else {},
        objectives=session.objective_snapshot.to_dict() if session.objective_snapshot else {},
        generated_candidates=tuple(item.to_dict() for item in selected_candidates),
        selected_plan=session.plan.to_dict() if session.plan else {},
        operation_history=tuple(item.to_dict() for item in session.operation_records),
        checkpoints=tuple(item.to_dict() for item in (session.checkpoint_history or session.checkpoints)),
        comparisons=tuple(item.to_dict() for item in session.comparisons),
        fidelity_evidence=tuple(item.fidelity for item in session.operation_records if item.fidelity),
        warnings=tuple(session.warnings), failures=tuple(item.error for item in session.operation_records if item.error),
        skipped_checks=tuple(item for comparison in session.comparisons for item in comparison.skipped_checks),
        stale_events=tuple(session.stale_events),
        acceptance_outcome=session.acceptance.to_dict() if session.acceptance else None,
        discard_outcome=session.discard.to_dict() if session.discard else None,
    )


def write_json_audit(audit: OptimizationAudit, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(audit.to_json(), encoding="utf-8", newline="\n")
    return destination


def audit_markdown(audit: OptimizationAudit) -> str:
    payload = audit.to_dict()
    lines = [
        "# Chroma3D Sculpt Controlled Optimization Audit", "", f"- Extension: `{audit.extension_version}`", f"- Blender: `{audit.blender_version or 'not recorded'}`", f"- Schema: `{audit.schema_version}`", f"- Source: `{audit.source_identity.get('object_name', '')}`", f"- Source signature: `{audit.source_signature}`", "", "## Safety", "", audit.advisory_disclaimer, "", "- Protected source is retained; operations are workspace-only.", "- No slicer, support generator, G-code, printer command, or physical validation is included.", "", "## Session evidence", "", f"- Candidates: `{len(audit.generated_candidates)}`", f"- Operations: `{len(audit.operation_history)}`", f"- Comparisons: `{len(audit.comparisons)}`", f"- Stale events: `{len(audit.stale_events)}`", f"- Acceptance: `{bool(audit.acceptance_outcome)}`", f"- Discard: `{bool(audit.discard_outcome)}`", "", "## Deterministic payload", "", "```json", json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), "```", "",
    ]
    return "\n".join(lines)


def write_markdown_audit(audit: OptimizationAudit, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(audit_markdown(audit), encoding="utf-8", newline="\n")
    return destination


__all__ = ("audit_markdown", "build_audit", "sanitize_optimization_filename", "write_json_audit", "write_markdown_audit")
