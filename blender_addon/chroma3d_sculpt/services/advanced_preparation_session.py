"""Session-only Sprint 4 result cache and expanded stale-state checks."""

from __future__ import annotations

from typing import Any

from ..metadata import PERFORMANCE_REGISTRY_VERSION
from ..models.advanced_preparation_models import AdvancedPreparationResult, ComposedProcessContext, FeatureFlagSet, HardwareProfile, MaterialProfile
from ..models.printability_models import StaleState
from ..printability_settings import PrintabilitySettings
from ..utilities.context import object_session_key
from ..utilities.printability_signatures import geometry_signature, transform_signature
from .process_context import legacy_profile_for_context


STALE_PREPARATION_MESSAGE = "Advanced Preparation results are stale. Run analysis again."
_MAX_RESULTS = 32
_results: dict[int, AdvancedPreparationResult] = {}
_latest_key: int | None = None


def store_preparation_result(obj: Any, result: AdvancedPreparationResult) -> None:
    global _latest_key
    key = object_session_key(obj)
    if key is None:
        raise ValueError("Cannot cache advanced preparation for an invalid Blender object.")
    if key not in _results and len(_results) >= _MAX_RESULTS:
        _results.pop(next(iter(_results)), None)
    _results[key] = result
    _latest_key = key


def get_preparation_result(obj: Any | None = None) -> AdvancedPreparationResult | None:
    key = object_session_key(obj) if obj is not None else _latest_key
    return _results.get(key) if key is not None else None


def preparation_stale_state(
    obj: Any,
    result: AdvancedPreparationResult,
    hardware: HardwareProfile,
    material: MaterialProfile,
    process: ComposedProcessContext,
    flags: FeatureFlagSet,
    settings: PrintabilitySettings,
) -> StaleState:
    try:
        if int(obj.as_pointer()) != int(result.object_metadata["object_identity"]) or int(obj.data.as_pointer()) != int(result.object_metadata["mesh_identity"]):
            return StaleState.STALE_GEOMETRY
        if geometry_signature(obj) != result.geometry_signature:
            return StaleState.STALE_GEOMETRY
        if transform_signature(obj) != result.transform_signature:
            return StaleState.STALE_TRANSFORM
    except (AttributeError, ReferenceError, TypeError, ValueError):
        return StaleState.STALE_GEOMETRY
    snapshot = result.process_context_snapshot.context
    if hardware.profile_hash != snapshot.hardware_profile.profile_hash:
        return StaleState.STALE_HARDWARE_PROFILE
    if material.profile_hash != snapshot.material_profile.profile_hash:
        return StaleState.STALE_MATERIAL_PROFILE
    if process.context_hash != snapshot.context_hash:
        return StaleState.STALE_PROCESS_CONTEXT
    if flags.flag_hash != result.feature_flags.flag_hash:
        return StaleState.STALE_FEATURE_FLAGS
    if result.performance_registry_version != PERFORMANCE_REGISTRY_VERSION:
        return StaleState.STALE_PERFORMANCE_POLICY
    try:
        settings_hash = settings.snapshot(legacy_profile_for_context(process)).settings_hash
    except (TypeError, ValueError):
        return StaleState.STALE_PROCESS_CONTEXT
    recorded_hash = result.base_printability.get("settings_snapshot", {}).get("settings_hash")
    if settings_hash != recorded_hash:
        return StaleState.STALE_PROCESS_CONTEXT
    return StaleState.CURRENT


def require_current_preparation(
    obj: Any, hardware: HardwareProfile, material: MaterialProfile, process: ComposedProcessContext,
    flags: FeatureFlagSet, settings: PrintabilitySettings,
) -> AdvancedPreparationResult:
    result = get_preparation_result(obj)
    if result is None:
        raise ValueError("Run Advanced Preparation before using its evidence.")
    if preparation_stale_state(obj, result, hardware, material, process, flags, settings) != StaleState.CURRENT:
        raise ValueError(STALE_PREPARATION_MESSAGE)
    return result


def clear_runtime() -> None:
    global _latest_key
    _results.clear()
    _latest_key = None
