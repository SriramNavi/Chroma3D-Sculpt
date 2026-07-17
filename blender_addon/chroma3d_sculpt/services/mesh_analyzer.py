"""Coordinator for non-destructive production diagnostics on an original mesh."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import platform
from time import perf_counter
from typing import Any
from uuid import uuid4

from ..analysis_settings import AnalysisSettings
from ..metadata import DISPLAY_VERSION, SCHEMA_VERSION
from ..models.analysis_result import (
    AnalysisProfile,
    AnalysisResult,
    AnalysisSeverity,
    BuildVolumeFitState,
    CheckResult,
    CheckTiming,
    DeepDiagnosticMetrics,
    DimensionMetrics,
    EvaluationStatus,
    GeometryMetrics,
    NormalConsistencyState,
    ObjectMetadata,
    SelfIntersectionState,
    ShellContainmentState,
    ShellOrientationState,
    TransformMetrics,
    VertexManifoldState,
    WatertightState,
)
from ..utilities.context import is_valid_mesh_object, object_session_key
from ..utilities.geometry import bounding_box, world_triangles, world_vertices
from ..utilities.logging import get_logger
from ..utilities.signatures import topology_signature
from ..utilities.units import millimetres_per_blender_unit
from .build_volume_analyzer import evaluate_build_volume
from .deep_diagnostics import DeepAnalysis, analyze_deep_diagnostics
from .shell_analyzer import analyze_shells
from .topology_analyzer import analyze_topology, potential_duplicate_count

TRANSFORM_TOLERANCE = 1e-6
DIMENSION_MM_TOLERANCE = 1e-6

logger = get_logger()


@dataclass(frozen=True, slots=True)
class _ObjectState:
    object_key: int | None
    mesh_key: int | None
    object_name: str
    mesh_name: str
    mode: str
    location: tuple[float, float, float]
    rotation: tuple[float, float, float]
    scale: tuple[float, float, float]
    counts: tuple[int, int, int, int]
    selected: bool


def _pointer(value: Any | None) -> int | None:
    try:
        return int(value.as_pointer()) if value is not None else None
    except (AttributeError, ReferenceError, TypeError):
        return None


def _vector3(value: Any) -> tuple[float, float, float]:
    return tuple(float(item) for item in value[:3])  # type: ignore[return-value]


def _snapshot(obj: Any, mesh: Any) -> _ObjectState:
    try:
        selected = bool(obj.select_get())
    except (AttributeError, RuntimeError):
        selected = False
    return _ObjectState(
        object_key=object_session_key(obj),
        mesh_key=_pointer(mesh),
        object_name=str(obj.name),
        mesh_name=str(mesh.name),
        mode=str(obj.mode),
        location=_vector3(obj.location),
        rotation=_vector3(obj.rotation_euler),
        scale=_vector3(obj.scale),
        counts=(len(mesh.vertices), len(mesh.edges), len(mesh.polygons), len(mesh.loops)),
        selected=selected,
    )


def _is_near(values: tuple[float, float, float], expected: tuple[float, float, float]) -> bool:
    return all(abs(value - target) <= TRANSFORM_TOLERANCE for value, target in zip(values, expected))


def _metadata(obj: Any | None, blend_file_path: str) -> ObjectMetadata:
    mesh = getattr(obj, "data", None)
    filepath = blend_file_path.strip()
    return ObjectMetadata(
        object_name=str(getattr(obj, "name", "")),
        mesh_data_name=str(getattr(mesh, "name", "")),
        object_mode=str(getattr(obj, "mode", "")),
        object_type=str(getattr(obj, "type", "")),
        material_slot_count=len(getattr(obj, "material_slots", ())),
        modifier_count=len(getattr(obj, "modifiers", ())),
        collection_names=tuple(sorted(str(item.name) for item in getattr(obj, "users_collection", ()))),
        blend_file_path=filepath or None,
        blend_file_unsaved=not bool(filepath),
    )


def _failure_result(
    started_at: datetime,
    started_timer: float,
    blender_version: str,
    blend_file_path: str,
    message: str,
    settings: AnalysisSettings,
    obj: Any | None = None,
) -> AnalysisResult:
    duration = (perf_counter() - started_timer) * 1000.0
    return AnalysisResult(
        schema_version=SCHEMA_VERSION,
        extension_version=DISPLAY_VERSION,
        blender_version=blender_version or "Unknown",
        operating_system=f"{platform.system()} {platform.release()}".strip(),
        analyzed_at=started_at,
        duration_ms=duration,
        severity=AnalysisSeverity.FAIL,
        summary="Analysis failed.",
        analysis_id=str(uuid4()),
        analysis_profile=settings.profile,
        settings_snapshot=settings.snapshot(blender_version),
        object_metadata=_metadata(obj, blend_file_path),
        checks=(CheckResult("mesh_input", EvaluationStatus.FAILED, message, duration),),
        timings=(CheckTiming("total_analysis", EvaluationStatus.FAILED, duration, message),),
        errors=(message,),
    )


def _transform_metrics(obj: Any) -> TransformMetrics:
    location = _vector3(obj.location)
    rotation = _vector3(obj.rotation_euler)
    scale = _vector3(obj.scale)
    return TransformMetrics(
        location_applied=_is_near(location, (0.0, 0.0, 0.0)),
        rotation_applied=_is_near(rotation, (0.0, 0.0, 0.0)),
        scale_applied=_is_near(scale, (1.0, 1.0, 1.0)),
        location=location,
        rotation_euler=rotation,
        scale=scale,
        tolerance=TRANSFORM_TOLERANCE,
    )


def _deep_failure(shells: tuple[Any, ...], message: str, duration_ms: float) -> DeepAnalysis:
    metrics = DeepDiagnosticMetrics(
        self_intersection_status=EvaluationStatus.FAILED,
        self_intersection_state=SelfIntersectionState.FAILED,
        containment_status=EvaluationStatus.FAILED,
        notes=(message,),
    )
    return DeepAnalysis(
        metrics=metrics,
        shells=shells,
        issue_evidence=(),
        checks=(
            CheckResult("self_intersection_candidates", EvaluationStatus.FAILED, message, duration_ms),
            CheckResult("containment_analysis", EvaluationStatus.FAILED, message, duration_ms),
        ),
        timings=(
            CheckTiming("self_intersection_candidate_detection", EvaluationStatus.FAILED, duration_ms, message),
            CheckTiming("containment_analysis", EvaluationStatus.FAILED, duration_ms, message),
        ),
    )


def _analyze(
    obj: Any,
    scene: Any | None,
    blender_version: str,
    blend_file_path: str,
    started_at: datetime,
    started_timer: float,
    settings: AnalysisSettings,
) -> AnalysisResult:
    mesh = obj.data
    before = _snapshot(obj, mesh)
    analysis_id = str(uuid4())
    checks: list[CheckResult] = [CheckResult("mesh_input", EvaluationStatus.COMPLETED, "Active original mesh datablock is valid.")]
    timings: list[CheckTiming] = []

    started = perf_counter()
    metadata = _metadata(obj, blend_file_path)
    transforms = _transform_metrics(obj)
    signature = topology_signature(obj, analysis_id)
    metadata_elapsed = (perf_counter() - started) * 1000.0
    checks.append(CheckResult("object_metadata", EvaluationStatus.COMPLETED, "Object metadata and topology signature collected.", metadata_elapsed))
    timings.append(CheckTiming("object_metadata", EvaluationStatus.COMPLETED, metadata_elapsed))

    started = perf_counter()
    factor, unit_system, scene_scale_length = millimetres_per_blender_unit(scene)
    coordinates = world_vertices(obj)
    triangles = world_triangles(mesh, coordinates)
    minimum, maximum = bounding_box(coordinates)
    dimension_vector = maximum - minimum
    dimensions_values = tuple(float(value) * factor for value in dimension_vector[:3])
    dimensions = DimensionMetrics(
        width_mm=dimensions_values[0],
        depth_mm=dimensions_values[1],
        height_mm=dimensions_values[2],
        unit_system=unit_system,
        scene_scale_length=scene_scale_length,
        millimetres_per_blender_unit=factor,
    )
    geometry = GeometryMetrics(
        vertex_count=len(mesh.vertices),
        edge_count=len(mesh.edges),
        polygon_count=len(mesh.polygons),
        triangle_count=len(triangles),
        loop_count=len(mesh.loops),
        material_slot_count=metadata.material_slot_count,
        modifier_count=metadata.modifier_count,
    )
    geometry_elapsed = (perf_counter() - started) * 1000.0
    checks.append(CheckResult("geometry_metrics", EvaluationStatus.COMPLETED, "World-space geometry and original-mesh triangle metrics collected.", geometry_elapsed))
    timings.append(CheckTiming("geometry_metrics", EvaluationStatus.COMPLETED, geometry_elapsed))

    topology_analysis = analyze_topology(mesh, settings)
    checks.extend(topology_analysis.checks)
    timings.extend(topology_analysis.timings)

    started = perf_counter()
    duplicates, duplicate_status, duplicate_detail = potential_duplicate_count(mesh.vertices, settings)
    duplicate_elapsed = (perf_counter() - started) * 1000.0
    topology_metrics = replace(
        topology_analysis.metrics,
        potential_duplicate_vertices=duplicates,
        duplicate_evaluation_status=duplicate_status,
    )
    checks.append(
        CheckResult(
            "potential_duplicates",
            duplicate_status,
            duplicate_detail,
            duplicate_elapsed,
            actual_size=len(mesh.vertices),
            configured_limit=settings.duplicate_vertex_limit,
        )
    )
    timings.append(CheckTiming("duplicate_position_detection", duplicate_status, duplicate_elapsed, duplicate_detail))

    shell_analysis = analyze_shells(mesh, topology_analysis, coordinates, triangles, factor, settings)
    checks.extend(shell_analysis.checks)
    timings.extend(shell_analysis.timings)

    started = perf_counter()
    build_volume = evaluate_build_volume(dimensions_values, settings)
    build_elapsed = (perf_counter() - started) * 1000.0
    checks.append(CheckResult("build_volume", build_volume.status, build_volume.message, build_elapsed))
    timings.append(CheckTiming("build_volume_evaluation", build_volume.status, build_elapsed, build_volume.message))

    try:
        deep = analyze_deep_diagnostics(coordinates, triangles, shell_analysis, settings)
    except Exception as exc:
        logger.exception("Deep diagnostics failed")
        deep_message = f"Deep diagnostics failed: {type(exc).__name__}: {exc}"
        deep = _deep_failure(shell_analysis.shells, deep_message, 0.0)
    checks.extend(deep.checks)
    timings.extend(deep.timings)

    after = _snapshot(obj, mesh)
    state_unchanged = before == after
    read_only_message = (
        "Relevant object, mesh, transform, mode, and selection state remained unchanged."
        if state_unchanged
        else "Object or mesh state changed during analysis; the result is not trusted."
    )
    checks.append(
        CheckResult(
            "read_only_state",
            EvaluationStatus.COMPLETED if state_unchanged else EvaluationStatus.FAILED,
            read_only_message,
        )
    )

    issue_evidence = topology_analysis.issue_evidence + shell_analysis.issue_evidence + deep.issue_evidence
    final_shells = deep.shells
    internal_ids = tuple(
        shell.shell_id for shell in final_shells if shell.classification == ShellContainmentState.POSSIBLY_INTERNAL
    )
    external_ids = tuple(
        shell.shell_id for shell in final_shells if shell.classification == ShellContainmentState.DISCONNECTED_EXTERNAL
    )
    warnings: list[str] = []
    errors: list[str] = []
    if geometry.vertex_count == 0:
        errors.append("Mesh has zero vertices.")
    if geometry.polygon_count == 0:
        errors.append("Mesh has zero faces.")
    if not state_unchanged:
        errors.append(read_only_message)

    warning_conditions = (
        (topology_metrics.boundary_edges > 0, f"{topology_metrics.boundary_edges} boundary edge(s) detected."),
        (topology_metrics.loose_edges > 0, f"{topology_metrics.loose_edges} loose edge(s) detected."),
        (topology_metrics.loose_vertices > 0, f"{topology_metrics.loose_vertices} loose vertex/vertices detected."),
        (
            topology_metrics.high_incidence_non_manifold_edges > 0,
            f"{topology_metrics.high_incidence_non_manifold_edges} high-incidence non-manifold edge(s) detected.",
        ),
        (
            topology_metrics.vertex_manifold_state == VertexManifoldState.ANOMALIES_DETECTED,
            f"{topology_metrics.vertex_manifold_anomalies} vertex-manifold anomaly/anomalies detected.",
        ),
        (topology_metrics.zero_length_edges > 0, f"{topology_metrics.zero_length_edges} zero-length edge(s) detected."),
        (topology_metrics.degenerate_faces > 0, f"{topology_metrics.degenerate_faces} degenerate face(s) detected."),
        (
            topology_metrics.watertight_state != WatertightState.TOPOLOGICALLY_WATERTIGHT,
            topology_metrics.watertight_detail,
        ),
        (
            topology_metrics.normal_consistency == NormalConsistencyState.INCONSISTENT,
            topology_metrics.normal_consistency_detail,
        ),
        (len(final_shells) > 1, f"{len(final_shells)} disconnected face shells require review."),
        (bool(shell_analysis.tiny_shell_ids), f"{len(shell_analysis.tiny_shell_ids)} tiny-shell candidate(s) require review."),
        (bool(internal_ids), f"{len(internal_ids)} possibly internal shell(s) require review."),
        (
            any(shell.orientation_state == ShellOrientationState.INWARD for shell in final_shells),
            "At least one closed shell is consistently oriented inward.",
        ),
        (
            deep.metrics.self_intersection_state == SelfIntersectionState.CANDIDATES_DETECTED,
            f"{deep.metrics.self_intersection_candidate_count} self-intersection candidate pair(s) require review.",
        ),
        (
            build_volume.fit_state == BuildVolumeFitState.DOES_NOT_FIT,
            "The model exceeds the configured rectangular build volume in its current orientation.",
        ),
        (not transforms.location_applied, "Object location is not approximately applied."),
        (not transforms.rotation_applied, "Object rotation is not approximately applied."),
        (not transforms.scale_applied, "Object scale is not approximately applied."),
        (
            geometry.vertex_count > 0 and min(dimensions_values) <= DIMENSION_MM_TOLERANCE,
            "At least one physical dimension is effectively zero.",
        ),
        (duplicate_status != EvaluationStatus.COMPLETED, f"Potential duplicate check: {duplicate_detail}"),
        (
            settings.profile == AnalysisProfile.DEEP
            and any(check.status in {EvaluationStatus.SKIPPED, EvaluationStatus.FAILED} for check in deep.checks),
            "One or more requested Deep diagnostics were skipped or failed; review explicit check states.",
        ),
    )
    warnings.extend(message for condition, message in warning_conditions if condition)

    skipped = tuple(check.message for check in checks if check.status == EvaluationStatus.SKIPPED)
    duration = (perf_counter() - started_timer) * 1000.0
    timings.append(
        CheckTiming(
            "total_analysis",
            EvaluationStatus.FAILED if errors else EvaluationStatus.COMPLETED,
            duration,
        )
    )
    severity = AnalysisSeverity.FAIL if errors else AnalysisSeverity.WARNING if warnings else AnalysisSeverity.PASS
    summary = {
        AnalysisSeverity.PASS: "Completed production mesh diagnostics with no review warnings.",
        AnalysisSeverity.WARNING: "Diagnostics completed; one or more findings require review.",
        AnalysisSeverity.FAIL: "Analysis failed or the mesh has no analyzable surface.",
    }[severity]
    return AnalysisResult(
        schema_version=SCHEMA_VERSION,
        extension_version=DISPLAY_VERSION,
        blender_version=blender_version or "Unknown",
        operating_system=f"{platform.system()} {platform.release()}".strip(),
        analyzed_at=started_at,
        duration_ms=duration,
        severity=severity,
        summary=summary,
        analysis_id=analysis_id,
        analysis_profile=settings.profile,
        settings_snapshot=settings.snapshot(blender_version),
        topology_signature=signature,
        object_metadata=metadata,
        geometry=geometry,
        dimensions=dimensions,
        transforms=transforms,
        topology=topology_metrics,
        surface_volume=shell_analysis.surface_volume,
        shells=final_shells,
        main_shell_id=shell_analysis.main_shell_id,
        tiny_shell_candidate_ids=shell_analysis.tiny_shell_ids,
        disconnected_external_shell_ids=external_ids,
        possible_internal_shell_ids=internal_ids,
        build_volume=build_volume,
        deep_diagnostics=deep.metrics,
        issue_evidence=issue_evidence,
        checks=tuple(checks),
        timings=tuple(timings),
        skipped_check_reasons=skipped,
        warnings=tuple(warnings),
        errors=tuple(errors),
    )


def analyze_mesh(
    obj: Any | None,
    scene: Any | None = None,
    *,
    settings: AnalysisSettings | None = None,
    blender_version: str = "",
    blend_file_path: str = "",
) -> AnalysisResult:
    """Analyze the original mesh datablock without modifying geometry or context."""

    started_at = datetime.now(timezone.utc)
    started_timer = perf_counter()
    effective_settings = settings or AnalysisSettings()
    object_name = str(getattr(obj, "name", "<none>"))
    logger.info("Analysis started: %s (%s)", object_name, effective_settings.profile.value)
    if not is_valid_mesh_object(obj):
        result = _failure_result(
            started_at,
            started_timer,
            blender_version,
            blend_file_path,
            "No valid active mesh object is available.",
            effective_settings,
            obj,
        )
        logger.warning("Analysis failed: %s", result.errors[0])
        return result
    try:
        result = _analyze(
            obj,
            scene,
            blender_version,
            blend_file_path,
            started_at,
            started_timer,
            effective_settings,
        )
    except MemoryError:
        logger.exception("Analysis exhausted available memory: %s", object_name)
        result = _failure_result(
            started_at,
            started_timer,
            blender_version,
            blend_file_path,
            "Analysis could not complete because available memory was exhausted.",
            effective_settings,
            obj,
        )
    except Exception as exc:
        logger.exception("Unexpected analysis failure: %s", object_name)
        result = _failure_result(
            started_at,
            started_timer,
            blender_version,
            blend_file_path,
            f"Analysis failed unexpectedly: {type(exc).__name__}: {exc}",
            effective_settings,
            obj,
        )
    logger.info("Analysis completed: %s (%s, %.2f ms)", object_name, result.severity.value, result.duration_ms)
    return result
