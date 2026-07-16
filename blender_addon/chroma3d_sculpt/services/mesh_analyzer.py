"""Non-destructive analysis of an object's original Blender mesh datablock."""

from __future__ import annotations

from array import array
from dataclasses import dataclass
from datetime import datetime, timezone
import math
import platform
from time import perf_counter
from typing import Any

from ..metadata import DISPLAY_VERSION, SCHEMA_VERSION
from ..models.analysis_result import (
    AnalysisResult,
    AnalysisSeverity,
    CheckResult,
    DimensionMetrics,
    EvaluationStatus,
    GeometryMetrics,
    NormalConsistencyState,
    ObjectMetadata,
    TopologyMetrics,
    TransformMetrics,
)
from ..utilities.context import is_valid_mesh_object, object_session_key
from ..utilities.logging import get_logger
from ..utilities.units import object_dimensions_mm

TRANSFORM_TOLERANCE = 1e-6
ZERO_LENGTH_TOLERANCE = 1e-9
DEGENERATE_AREA_TOLERANCE = 1e-18
DUPLICATE_VERTEX_TOLERANCE = 1e-6
DIMENSION_MM_TOLERANCE = 1e-6
DUPLICATE_VERTEX_LIMIT = 500_000

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
    obj: Any | None = None,
) -> AnalysisResult:
    return AnalysisResult(
        schema_version=SCHEMA_VERSION,
        extension_version=DISPLAY_VERSION,
        blender_version=blender_version or "Unknown",
        operating_system=f"{platform.system()} {platform.release()}".strip(),
        analyzed_at=started_at,
        duration_ms=(perf_counter() - started_timer) * 1000.0,
        severity=AnalysisSeverity.FAIL,
        summary="Analysis failed.",
        object_metadata=_metadata(obj, blend_file_path),
        checks=(CheckResult("mesh_input", EvaluationStatus.FAILED, message),),
        errors=(message,),
    )


def _connected_component_count(vertex_count: int, edges: Any) -> int:
    if vertex_count == 0:
        return 0
    parent = array("I", range(vertex_count))
    rank = bytearray(vertex_count)

    def find(index: int) -> int:
        root = index
        while parent[root] != root:
            root = parent[root]
        while parent[index] != index:
            next_index = parent[index]
            parent[index] = root
            index = next_index
        return root

    for edge in edges:
        left, right = int(edge.vertices[0]), int(edge.vertices[1])
        root_left, root_right = find(left), find(right)
        if root_left == root_right:
            continue
        if rank[root_left] < rank[root_right]:
            root_left, root_right = root_right, root_left
        parent[root_right] = root_left
        if rank[root_left] == rank[root_right]:
            rank[root_left] += 1
    return sum(1 for index in range(vertex_count) if find(index) == index)


def _potential_duplicate_count(vertices: Any) -> tuple[int, EvaluationStatus, str]:
    vertex_count = len(vertices)
    if vertex_count > DUPLICATE_VERTEX_LIMIT:
        return (
            0,
            EvaluationStatus.SKIPPED,
            f"Skipped above the {DUPLICATE_VERTEX_LIMIT:,}-vertex Sprint 0 safety limit.",
        )

    inverse = 1.0 / DUPLICATE_VERTEX_TOLERANCE
    tolerance_squared = DUPLICATE_VERTEX_TOLERANCE**2
    buckets: dict[tuple[int, int, int], list[tuple[float, float, float]]] = {}
    duplicates = 0
    for vertex in vertices:
        coordinate = _vector3(vertex.co)
        cell = tuple(math.floor(value * inverse) for value in coordinate)
        matched = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for candidate in buckets.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), ()):
                        distance_squared = sum((a - b) ** 2 for a, b in zip(coordinate, candidate))
                        if distance_squared <= tolerance_squared:
                            duplicates += 1
                            matched = True
                            break
                    if matched:
                        break
                if matched:
                    break
            if matched:
                break
        if not matched:
            buckets.setdefault(cell, []).append(coordinate)
    return duplicates, EvaluationStatus.COMPLETED, "Spatial-hash check completed in object-local coordinates."


def _edge_face_data(mesh: Any) -> tuple[array, bytearray, bool]:
    face_counts = array("I", [0]) * len(mesh.edges)
    first_orientations = bytearray(len(mesh.edges))
    has_first = bytearray(len(mesh.edges))
    inconsistent = False
    loops = mesh.loops
    edges = mesh.edges

    for polygon in mesh.polygons:
        loop_start = int(polygon.loop_start)
        loop_total = int(polygon.loop_total)
        for offset in range(loop_total):
            loop_index = loop_start + offset
            next_loop_index = loop_start + ((offset + 1) % loop_total)
            edge_index = int(loops[loop_index].edge_index)
            start_vertex = int(loops[loop_index].vertex_index)
            end_vertex = int(loops[next_loop_index].vertex_index)
            edge = edges[edge_index]
            orientation = 1 if (start_vertex == edge.vertices[0] and end_vertex == edge.vertices[1]) else 0
            face_counts[edge_index] += 1
            if not has_first[edge_index]:
                first_orientations[edge_index] = orientation
                has_first[edge_index] = 1
            elif first_orientations[edge_index] == orientation:
                inconsistent = True
    return face_counts, first_orientations, inconsistent


def _normal_state(
    face_counts: array,
    manifold_edges: int,
    inconsistent: bool,
) -> tuple[NormalConsistencyState, str, EvaluationStatus]:
    if any(count == 0 or count > 2 for count in face_counts):
        return (
            NormalConsistencyState.NOT_EVALUATED,
            "Zero-face or over-connected edges prevent a reliable winding result.",
            EvaluationStatus.SKIPPED,
        )
    if manifold_edges == 0:
        return (
            NormalConsistencyState.NOT_EVALUATED,
            "No two-face adjacency exists for a reliable winding comparison.",
            EvaluationStatus.SKIPPED,
        )
    if inconsistent:
        return (
            NormalConsistencyState.POTENTIALLY_INCONSISTENT,
            "At least one two-face edge is traversed in the same direction by both faces.",
            EvaluationStatus.COMPLETED,
        )
    return (
        NormalConsistencyState.CONSISTENT,
        "All evaluated two-face adjacencies use opposite edge winding.",
        EvaluationStatus.COMPLETED,
    )


def _analyze(
    obj: Any,
    scene: Any | None,
    blender_version: str,
    blend_file_path: str,
    started_at: datetime,
    started_timer: float,
) -> AnalysisResult:
    mesh = obj.data
    before = _snapshot(obj, mesh)
    metadata = _metadata(obj, blend_file_path)
    vertex_count = len(mesh.vertices)
    edge_count = len(mesh.edges)
    polygon_count = len(mesh.polygons)
    loop_count = len(mesh.loops)

    triangle_count = sum(max(int(polygon.loop_total) - 2, 0) for polygon in mesh.polygons)
    geometry = GeometryMetrics(
        vertex_count=vertex_count,
        edge_count=edge_count,
        polygon_count=polygon_count,
        triangle_count=triangle_count,
        loop_count=loop_count,
        material_slot_count=metadata.material_slot_count,
        modifier_count=metadata.modifier_count,
    )

    width, depth, height, unit_system, scale_length, factor = object_dimensions_mm(obj, scene)
    dimensions = DimensionMetrics(width, depth, height, unit_system, scale_length, factor)

    location = _vector3(obj.location)
    rotation = _vector3(obj.rotation_euler)
    scale = _vector3(obj.scale)
    transforms = TransformMetrics(
        location_applied=_is_near(location, (0.0, 0.0, 0.0)),
        rotation_applied=_is_near(rotation, (0.0, 0.0, 0.0)),
        scale_applied=_is_near(scale, (1.0, 1.0, 1.0)),
        location=location,
        rotation_euler=rotation,
        scale=scale,
        tolerance=TRANSFORM_TOLERANCE,
    )

    face_counts, _orientations, inconsistent_normals = _edge_face_data(mesh)
    boundary_edges = sum(1 for count in face_counts if count == 1)
    manifold_edges = sum(1 for count in face_counts if count == 2)
    non_manifold_edges = sum(1 for count in face_counts if count == 0 or count > 2)
    loose_edges = sum(1 for count in face_counts if count == 0)

    degree = array("I", [0]) * vertex_count
    zero_length_edges = 0
    zero_length_squared = ZERO_LENGTH_TOLERANCE**2
    for edge in mesh.edges:
        left, right = int(edge.vertices[0]), int(edge.vertices[1])
        degree[left] += 1
        degree[right] += 1
        delta = mesh.vertices[left].co - mesh.vertices[right].co
        if float(delta.length_squared) <= zero_length_squared:
            zero_length_edges += 1
    loose_vertices = sum(1 for value in degree if value == 0)
    degenerate_faces = sum(1 for polygon in mesh.polygons if float(polygon.area) <= DEGENERATE_AREA_TOLERANCE)
    components = _connected_component_count(vertex_count, mesh.edges)
    duplicates, duplicate_status, duplicate_detail = _potential_duplicate_count(mesh.vertices)
    normal_state, normal_detail, normal_check_status = _normal_state(
        face_counts,
        manifold_edges,
        inconsistent_normals,
    )
    topology = TopologyMetrics(
        non_manifold_edges=non_manifold_edges,
        boundary_edges=boundary_edges,
        manifold_edges=manifold_edges,
        loose_vertices=loose_vertices,
        loose_edges=loose_edges,
        zero_length_edges=zero_length_edges,
        degenerate_faces=degenerate_faces,
        connected_components=components,
        disconnected_shells=max(components - 1, 0),
        potential_duplicate_vertices=duplicates,
        duplicate_evaluation_status=duplicate_status,
        normal_consistency=normal_state,
        normal_consistency_detail=normal_detail,
    )

    warnings: list[str] = []
    errors: list[str] = []
    if vertex_count == 0:
        errors.append("Mesh has zero vertices.")
    if polygon_count == 0:
        errors.append("Mesh has zero faces.")
    warning_conditions = (
        (boundary_edges > 0, f"{boundary_edges} boundary edge(s) detected."),
        (non_manifold_edges > 0, f"{non_manifold_edges} fully non-manifold edge(s) detected."),
        (loose_vertices > 0, f"{loose_vertices} loose vertex/vertices detected."),
        (loose_edges > 0, f"{loose_edges} loose edge(s) detected."),
        (zero_length_edges > 0, f"{zero_length_edges} zero-length edge(s) detected."),
        (degenerate_faces > 0, f"{degenerate_faces} degenerate face(s) detected."),
        (components > 1, f"{components} disconnected mesh components detected."),
        (duplicates > 0, f"{duplicates} potential duplicate vertex/vertices detected."),
        (not transforms.location_applied, "Object location is not approximately applied."),
        (not transforms.rotation_applied, "Object rotation is not approximately applied."),
        (not transforms.scale_applied, "Object scale is not approximately applied."),
        (min(width, depth, height) <= DIMENSION_MM_TOLERANCE, "At least one physical dimension is effectively zero."),
        (duplicate_status != EvaluationStatus.COMPLETED, f"Potential duplicate check: {duplicate_detail}"),
        (normal_state == NormalConsistencyState.POTENTIALLY_INCONSISTENT, normal_detail),
        (normal_check_status != EvaluationStatus.COMPLETED, f"Normal consistency: {normal_detail}"),
    )
    warnings.extend(message for condition, message in warning_conditions if condition)

    after = _snapshot(obj, mesh)
    state_unchanged = before == after
    if not state_unchanged:
        errors.append("Object or mesh state changed during analysis; the result is not trusted.")

    checks = (
        CheckResult("mesh_input", EvaluationStatus.COMPLETED, "Active mesh datablock is valid."),
        CheckResult("geometry_metrics", EvaluationStatus.COMPLETED, "Original mesh datablock metrics collected."),
        CheckResult("dimensions", EvaluationStatus.COMPLETED, "Scaled object dimensions converted to millimetres."),
        CheckResult("transform_state", EvaluationStatus.COMPLETED, "Transform values compared with centralized tolerances."),
        CheckResult("topology", EvaluationStatus.COMPLETED, "Linear edge, face, and component diagnostics completed."),
        CheckResult("potential_duplicates", duplicate_status, duplicate_detail),
        CheckResult("normal_consistency", normal_check_status, normal_detail),
        CheckResult(
            "read_only_state",
            EvaluationStatus.COMPLETED if state_unchanged else EvaluationStatus.FAILED,
            "Relevant object and mesh state remained unchanged." if state_unchanged else errors[-1],
        ),
    )

    severity = AnalysisSeverity.FAIL if errors else AnalysisSeverity.WARNING if warnings else AnalysisSeverity.PASS
    summary = {
        AnalysisSeverity.PASS: "No basic topology warnings detected.",
        AnalysisSeverity.WARNING: "Basic mesh warnings were detected; review the report.",
        AnalysisSeverity.FAIL: "Analysis failed or the mesh has no analyzable surface.",
    }[severity]
    return AnalysisResult(
        schema_version=SCHEMA_VERSION,
        extension_version=DISPLAY_VERSION,
        blender_version=blender_version or "Unknown",
        operating_system=f"{platform.system()} {platform.release()}".strip(),
        analyzed_at=started_at,
        duration_ms=(perf_counter() - started_timer) * 1000.0,
        severity=severity,
        summary=summary,
        object_metadata=metadata,
        geometry=geometry,
        dimensions=dimensions,
        transforms=transforms,
        topology=topology,
        checks=checks,
        warnings=tuple(warnings),
        errors=tuple(errors),
    )


def analyze_mesh(
    obj: Any | None,
    scene: Any | None = None,
    *,
    blender_version: str = "",
    blend_file_path: str = "",
) -> AnalysisResult:
    """Analyze a mesh without modifying the object, mesh datablock, or scene."""

    started_at = datetime.now(timezone.utc)
    started_timer = perf_counter()
    object_name = str(getattr(obj, "name", "<none>"))
    logger.info("Analysis started: %s", object_name)
    if not is_valid_mesh_object(obj):
        result = _failure_result(
            started_at,
            started_timer,
            blender_version,
            blend_file_path,
            "No valid active mesh object is available.",
            obj,
        )
        logger.warning("Analysis failed: %s", result.errors[0])
        return result
    try:
        result = _analyze(obj, scene, blender_version, blend_file_path, started_at, started_timer)
    except MemoryError:
        logger.exception("Analysis exhausted available memory: %s", object_name)
        result = _failure_result(
            started_at,
            started_timer,
            blender_version,
            blend_file_path,
            "Analysis could not complete because available memory was exhausted.",
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
            obj,
        )
    logger.info("Analysis completed: %s (%s, %.2f ms)", object_name, result.severity.value, result.duration_ms)
    return result

