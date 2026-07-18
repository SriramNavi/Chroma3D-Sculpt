"""Repair audit schema 1.0 generation and Windows-safe JSON export."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import re

import bpy

from ..metadata import DISPLAY_VERSION, REPAIR_AUDIT_SCHEMA_VERSION, SCHEMA_VERSION
from ..models.repair_models import RepairAudit, RepairOperationStatus, RepairSession


_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{index}" for index in range(1, 10)), *(f"LPT{index}" for index in range(1, 10))}


def sanitize_repair_audit_filename(source_name: str) -> str:
    stem = _INVALID.sub("_", source_name).strip(" .") or "mesh"
    if stem.split(".", 1)[0].upper() in _RESERVED:
        stem = f"_{stem}_"
    return f"{stem}_chroma3d_repair_audit.json"


def build_repair_audit(session: RepairSession) -> dict[str, object]:
    audit = RepairAudit(
        schema_version=REPAIR_AUDIT_SCHEMA_VERSION,
        extension_version=DISPLAY_VERSION,
        analysis_schema_version=SCHEMA_VERSION,
        blender_version=bpy.app.version_string,
        operating_system=f"{platform.system()} {platform.release()}".strip(),
        exported_at=datetime.now(timezone.utc),
        session=session.to_dict(),
        source_protection_signature=session.source_signature,
        initial_workspace_signature=session.initial_workspace_signature,
        final_workspace_signature=session.current_workspace_signature,
        final_decision=session.decision,
        failure_records=tuple(
            {
                "operation_id": record.operation_id,
                "operation_type": record.operation_type.value,
                "error": record.error,
            }
            for record in session.operation_records
            if record.status == RepairOperationStatus.FAILED
        ),
        known_limitations=tuple(session.limitations),
    )
    return audit.to_dict()


def write_repair_audit(session: RepairSession, path: Path) -> Path:
    output = path.expanduser().resolve()
    if output.suffix.lower() != ".json":
        output = output.with_suffix(".json")
    output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(build_repair_audit(session), ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    output.write_text(text, encoding="utf-8", newline="\n")
    return output
