"""Bounded, deterministic, resumable multi-object advanced preparation."""

from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable
from uuid import uuid4

from ..metadata import BATCH_PREPARATION_SCHEMA_VERSION
from ..models.advanced_preparation_models import (
    AdvancedPreparationResult, BatchPreparationResult, BatchPreparationState, ComposedProcessContext,
    FeatureFlagSet, HardwareProfile, MaterialProfile,
)
from ..models.printability_models import PrintabilityStatus, StaleState
from ..performance_registry import limit_for_size
from ..printability_settings import PrintabilitySettings
from .advanced_preparation_coordinator import analyze_advanced_preparation
from .advanced_preparation_session import preparation_stale_state, store_preparation_result


ProgressCallback = Callable[[int, int, str], None]
CancellationCallback = Callable[[], bool]


def analyze_preparation_batch(
    objects: list[Any] | tuple[Any, ...],
    scene: Any,
    hardware: HardwareProfile,
    material: MaterialProfile,
    process: ComposedProcessContext,
    flags: FeatureFlagSet,
    settings: PrintabilitySettings,
    *,
    progress: ProgressCallback | None = None,
    cancelled: CancellationCallback | None = None,
    resume_results: dict[str, AdvancedPreparationResult] | None = None,
    blender_version: str = "",
    blend_file_path: str = "",
) -> BatchPreparationResult:
    started = perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    ordered = sorted(objects, key=lambda item: (str(getattr(item, "name", "")), str(getattr(getattr(item, "data", None), "name", ""))))
    batch_limit = limit_for_size(settings.mode, "Medium", "batch_analysis").maximum_batch_size
    if not ordered:
        return BatchPreparationResult(
            BATCH_PREPARATION_SCHEMA_VERSION, str(uuid4()), BatchPreparationState.FAILED, started_at,
            datetime.now(timezone.utc).isoformat(), 0, 0, 0, 0, perf_counter() - started,
            process.context_hash, flags.flag_hash, process.to_dict(), flags.to_dict(), {}, (), (),
            ("No mesh objects were selected for explicit batch analysis.",),
        )
    if len(ordered) > batch_limit:
        return BatchPreparationResult(
            BATCH_PREPARATION_SCHEMA_VERSION, str(uuid4()), BatchPreparationState.FAILED, started_at,
            datetime.now(timezone.utc).isoformat(), len(ordered), 0, 0, len(ordered), perf_counter() - started,
            process.context_hash, flags.flag_hash, process.to_dict(), flags.to_dict(), {}, (), (),
            (f"Batch size {len(ordered)} exceeds the centralized {settings.mode.value} limit of {batch_limit}; no object was analyzed.",),
        )
    resumed = resume_results or {}
    summaries: list[dict[str, Any]] = []
    source_signatures: dict[str, str] = {}
    critical: list[dict[str, Any]] = []
    completed_count = 0
    failed_count = 0
    skipped_count = 0
    was_cancelled = False
    for index, obj in enumerate(ordered):
        name = str(getattr(obj, "name", f"object-{index}"))
        if cancelled and cancelled():
            was_cancelled = True
            skipped_count += len(ordered) - index
            break
        if progress:
            progress(index, len(ordered), name)
        try:
            previous = resumed.get(name)
            if previous and preparation_stale_state(obj, previous, hardware, material, process, flags, settings) == StaleState.CURRENT:
                result = previous
                resumed_state = True
            else:
                result = analyze_advanced_preparation(
                    obj, scene, hardware, material, process, flags, settings,
                    blender_version=blender_version, blend_file_path=blend_file_path,
                )
                resumed_state = False
            store_preparation_result(obj, result)
            source_signatures[name] = result.source_signature
            completed_count += 1
            summary = {
                "object_name": name, "status": result.status.value, "score": result.score,
                "confidence": result.confidence.value, "source_signature": result.source_signature,
                "geometry_signature": result.geometry_signature, "transform_signature": result.transform_signature,
                "bridge_risk_state": result.bridge_risk.status.value, "bridge_risk_count": result.bridge_risk.candidate_region_count,
                "support_risk_state": result.support_risk.status.value, "support_risk_area_mm2": result.support_risk.total_risk_area_mm2,
                "resin_advisory_state": result.resin_advisory.status.value, "resumed": resumed_state,
                "duration_seconds": result.timings["total"],
            }
            summaries.append(summary)
            if result.status == PrintabilityStatus.CRITICAL:
                critical.append({"object_name": name, "status": result.status.value, "score": result.score})
        except (MemoryError, AttributeError, ReferenceError, RuntimeError, TypeError, ValueError) as exc:
            failed_count += 1
            summaries.append({"object_name": name, "status": "FAILED", "score": None, "error": f"{type(exc).__name__}: {exc}"})
    if progress:
        progress(len(ordered), len(ordered), "complete")
    if was_cancelled:
        state = BatchPreparationState.CANCELLED
    elif failed_count and completed_count:
        state = BatchPreparationState.PARTIAL
    elif failed_count:
        state = BatchPreparationState.FAILED
    elif critical or any(item.get("status") in {"WARNING", "INDETERMINATE"} for item in summaries):
        state = BatchPreparationState.COMPLETED_WITH_WARNINGS
    else:
        state = BatchPreparationState.COMPLETED
    return BatchPreparationResult(
        schema_version=BATCH_PREPARATION_SCHEMA_VERSION, batch_id=str(uuid4()), state=state,
        started_at=started_at, completed_at=datetime.now(timezone.utc).isoformat(), object_count=len(ordered),
        completed_count=completed_count, failed_count=failed_count, skipped_count=skipped_count,
        total_time_seconds=perf_counter() - started, process_context_hash=process.context_hash,
        feature_flag_hash=flags.flag_hash, process_context_snapshot=process.to_dict(), feature_flags=flags.to_dict(),
        source_signatures=source_signatures,
        object_results=tuple(summaries), critical_risks=tuple(critical),
        limitations=(
            "Batch processing is sequential, bounded, isolated per object, and preserves partial failures; no source object is mutated.",
            "Cancellation is cooperative between objects; an in-progress synchronous Blender check is allowed to finish safely.",
        ),
    )
