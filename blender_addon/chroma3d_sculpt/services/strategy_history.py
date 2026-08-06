"""Local, explicit, deterministic strategy history; never telemetry or learning."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Mapping

from ..models.intelligent_optimization_models import StrategyHistory, StrategyHistoryEntry, stable_hash


_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def history_entry(
    *,
    source_identity: Mapping[str, Any],
    source_signature: str,
    strategy_fingerprint: str,
    objective_profile: Mapping[str, Any],
    search_policy: Mapping[str, Any],
    constraints: Mapping[str, Any],
    evaluation: Mapping[str, Any],
    rank: int | None = None,
    recommendation_state: str = "",
    preview_state: str = "NOT_RUN",
    execution_state: str = "NOT_RUN",
    comparison: Mapping[str, Any] | None = None,
    accepted_state: str = "NOT_DECIDED",
    software_version: str = "",
    schema_versions: Mapping[str, str] | None = None,
    recorded_at: str | None = None,
) -> StrategyHistoryEntry:
    entry_payload = {"source_signature": source_signature, "strategy_fingerprint": strategy_fingerprint, "evaluation": evaluation}
    entry_id = f"history-{stable_hash(entry_payload)[:20]}"
    return StrategyHistoryEntry(
        entry_id=entry_id,
        recorded_at=recorded_at or _now(),
        source_identity=dict(source_identity),
        source_signature=source_signature,
        strategy_fingerprint=strategy_fingerprint,
        objective_profile=dict(objective_profile),
        search_policy=dict(search_policy),
        constraints=dict(constraints),
        evaluation=dict(evaluation),
        rank=rank,
        recommendation_state=recommendation_state,
        preview_state=preview_state,
        execution_state=execution_state,
        comparison=dict(comparison or {}),
        accepted_state=accepted_state,
        software_version=software_version,
        schema_versions=dict(schema_versions or {}),
    )


def add_history_entry(history: StrategyHistory, entry: StrategyHistoryEntry, *, maximum_entries: int = 128) -> bool:
    if isinstance(maximum_entries, bool) or not isinstance(maximum_entries, int) or maximum_entries < 1:
        raise ValueError("maximum_entries must be a positive integer.")
    if any(item.source_signature == entry.source_signature and item.strategy_fingerprint == entry.strategy_fingerprint for item in history.entries):
        return False
    history.entries.append(entry)
    if len(history.entries) > maximum_entries:
        del history.entries[:-maximum_entries]
    return True


def compare_history(history: StrategyHistory, *, source_signature: str = "") -> dict[str, Any]:
    entries = [item for item in history.entries if not source_signature or item.source_signature == source_signature]
    return {
        "entry_count": len(entries),
        "accepted": sum(item.accepted_state == "ACCEPTED" for item in entries),
        "discarded": sum(item.accepted_state == "DISCARDED" for item in entries),
        "recommended": sum(bool(item.recommendation_state) for item in entries),
        "strategy_fingerprints": tuple(item.strategy_fingerprint for item in entries),
        "limitations": tuple(history.limitations),
    }


def mark_history_state(history: StrategyHistory, entry_id: str, *, preview_state: str | None = None, execution_state: str | None = None, accepted_state: str | None = None, comparison: Mapping[str, Any] | None = None) -> None:
    entry = next((item for item in history.entries if item.entry_id == entry_id), None)
    if entry is None:
        raise KeyError(f"Unknown history entry: {entry_id}")
    if preview_state is not None:
        object.__setattr__(entry, "preview_state", preview_state)
    if execution_state is not None:
        object.__setattr__(entry, "execution_state", execution_state)
    if accepted_state is not None:
        object.__setattr__(entry, "accepted_state", accepted_state)
    if comparison is not None:
        object.__setattr__(entry, "comparison", dict(comparison))


def sanitize_history_filename(name: str) -> str:
    value = Path(str(name)).name
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip(" ._") or "chroma3d_strategy_history"
    stem = value.split(".", 1)[0].upper()
    if stem in _WINDOWS_RESERVED:
        value = f"_{value}"
    return value


def write_history_json(history: StrategyHistory, path: str | Path) -> Path:
    target = Path(path)
    if ".." in str(path).replace("\\", "/").split("/"):
        raise ValueError("Path traversal is not allowed in history exports.")
    safe_name = sanitize_history_filename(target.name)
    if safe_name != target.name:
        target = target.with_name(safe_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = history.to_json().encode("utf-8")
    target.write_bytes(data)
    return target


def history_markdown(history: StrategyHistory) -> str:
    lines = ["# Chroma3D Sculpt Intelligent Optimization History", "", "Local session history only; no telemetry, cloud sync, or hidden policy learning.", "", f"Entries: `{len(history.entries)}`", ""]
    for entry in history.entries:
        lines.extend([f"## `{entry.strategy_fingerprint[:16]}`", "", f"- Recorded: `{entry.recorded_at}`", f"- Source signature: `{entry.source_signature}`", f"- Rank: `{entry.rank if entry.rank is not None else 'not ranked'}`", f"- Recommendation: `{entry.recommendation_state or 'none'}`", f"- Accepted state: `{entry.accepted_state}`", ""])
    return "\n".join(lines) + "\n"


def write_history_markdown(history: StrategyHistory, path: str | Path) -> Path:
    target = Path(path)
    if ".." in str(path).replace("\\", "/").split("/"):
        raise ValueError("Path traversal is not allowed in history exports.")
    safe_name = sanitize_history_filename(target.name)
    if safe_name != target.name:
        target = target.with_name(safe_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(history_markdown(history), encoding="utf-8", newline="\n")
    return target


def history_is_current(history: StrategyHistory, *, source_signature: str, objective_profile_hash: str, search_policy_hash: str) -> tuple[bool, str]:
    for entry in history.entries:
        if entry.source_signature != source_signature:
            continue
        if str(entry.objective_profile.get("profile_hash", "")) != objective_profile_hash:
            return False, "OBJECTIVE_PROFILE_CHANGED"
        if str(entry.search_policy.get("policy_hash", "")) != search_policy_hash:
            return False, "SEARCH_POLICY_CHANGED"
    return True, "CURRENT"


__all__ = (
    "add_history_entry", "compare_history", "history_entry", "history_is_current", "history_markdown",
    "mark_history_state", "sanitize_history_filename", "write_history_json", "write_history_markdown",
)
