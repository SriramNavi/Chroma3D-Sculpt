"""Session-only report cache that stores no Blender object references."""

from __future__ import annotations

from typing import Any

from .models.analysis_result import AnalysisResult
from .utilities.context import object_session_key

_MAX_CACHED_REPORTS = 32
_reports: dict[int, AnalysisResult] = {}
_latest_key: int | None = None


def store_result(obj: Any, result: AnalysisResult) -> None:
    global _latest_key
    key = object_session_key(obj)
    if key is None:
        raise ValueError("Cannot cache analysis for an invalid Blender object.")
    if key not in _reports and len(_reports) >= _MAX_CACHED_REPORTS:
        oldest_key = next(iter(_reports))
        _reports.pop(oldest_key, None)
    _reports[key] = result
    _latest_key = key


def get_result(obj: Any | None = None) -> AnalysisResult | None:
    key = object_session_key(obj) if obj is not None else _latest_key
    return _reports.get(key) if key is not None else None


def has_result(obj: Any | None = None) -> bool:
    return get_result(obj) is not None


def clear() -> None:
    global _latest_key
    _reports.clear()
    _latest_key = None

