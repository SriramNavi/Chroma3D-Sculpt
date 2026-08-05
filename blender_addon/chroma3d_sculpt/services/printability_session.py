"""Session-only printability cache with explicit stale-state classification."""

from __future__ import annotations

from typing import Any

from ..models.printability_models import PrintabilityResult, PrinterProfile, StaleState
from ..printability_settings import PrintabilitySettings
from ..utilities.context import object_session_key
from ..utilities.printability_signatures import geometry_signature, transform_signature


STALE_MESSAGE = "Printability results are stale. Run Printability Analysis again."
_MAX_RESULTS = 32
_results: dict[int, PrintabilityResult] = {}
_latest_key: int | None = None


def store_result(obj: Any, result: PrintabilityResult) -> None:
    global _latest_key
    key = object_session_key(obj)
    if key is None:
        raise ValueError("Cannot cache printability analysis for an invalid Blender object.")
    if key not in _results and len(_results) >= _MAX_RESULTS:
        _results.pop(next(iter(_results)), None)
    _results[key] = result
    _latest_key = key


def get_result(obj: Any | None = None) -> PrintabilityResult | None:
    key = object_session_key(obj) if obj is not None else _latest_key
    return _results.get(key) if key is not None else None


def stale_state(obj: Any, result: PrintabilityResult, profile: PrinterProfile, settings: PrintabilitySettings) -> StaleState:
    try:
        if geometry_signature(obj) != result.geometry_signature:
            return StaleState.STALE_GEOMETRY
        if transform_signature(obj) != result.transform_signature:
            return StaleState.STALE_TRANSFORM
    except (AttributeError, ReferenceError, TypeError):
        return StaleState.STALE_GEOMETRY
    if profile.profile_hash != result.printer_profile_snapshot.profile.profile_hash:
        return StaleState.STALE_PROFILE
    try:
        current_snapshot = settings.snapshot(profile)
    except (TypeError, ValueError):
        return StaleState.STALE_SETTINGS
    if current_snapshot.settings_hash != result.settings_snapshot.settings_hash:
        return StaleState.STALE_SETTINGS
    return StaleState.CURRENT


def require_current(obj: Any, profile: PrinterProfile, settings: PrintabilitySettings) -> PrintabilityResult:
    result = get_result(obj)
    if result is None:
        raise ValueError("Run Printability Analysis before using its evidence.")
    if stale_state(obj, result, profile, settings) != StaleState.CURRENT:
        raise ValueError(STALE_MESSAGE)
    return result


def clear_runtime() -> None:
    global _latest_key
    _results.clear()
    _latest_key = None
