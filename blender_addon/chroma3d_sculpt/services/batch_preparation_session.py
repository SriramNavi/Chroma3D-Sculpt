"""Session-only batch result with source/context stale rejection."""

from __future__ import annotations

from typing import Any

from ..models.advanced_preparation_models import BatchPreparationResult, ComposedProcessContext, FeatureFlagSet
from ..utilities.printability_signatures import printability_source_snapshot


_current: BatchPreparationResult | None = None


def store_batch_result(result: BatchPreparationResult) -> None:
    global _current
    _current = result


def get_batch_result() -> BatchPreparationResult | None:
    return _current


def batch_is_stale(objects: list[Any] | tuple[Any, ...], process: ComposedProcessContext, flags: FeatureFlagSet, blend_file_path: str = "") -> bool:
    if _current is None or _current.process_context_hash != process.context_hash or _current.feature_flag_hash != flags.flag_hash:
        return True
    current_names = {str(obj.name) for obj in objects}
    if current_names != set(_current.source_signatures):
        return True
    for obj in objects:
        snapshot = printability_source_snapshot(obj, blend_file_path)
        if str(snapshot["printability_sha256"]) != _current.source_signatures.get(str(obj.name)):
            return True
    return False


def require_current_batch(objects: list[Any] | tuple[Any, ...], process: ComposedProcessContext, flags: FeatureFlagSet, blend_file_path: str = "") -> BatchPreparationResult:
    if _current is None:
        raise ValueError("Run batch preparation before displaying or exporting its result.")
    if batch_is_stale(objects, process, flags, blend_file_path):
        raise ValueError("Batch preparation result is stale. Run the selected-object batch again.")
    return _current


def clear_runtime() -> None:
    global _current
    _current = None
