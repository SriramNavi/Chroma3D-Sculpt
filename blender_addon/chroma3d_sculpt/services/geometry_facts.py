"""Read-only world-space geometry facts shared by printability checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mathutils import Vector

from ..analysis_settings import AnalysisSettings
from ..models.analysis_result import WatertightState
from ..models.printability_models import GeometryFacts
from ..printability_settings import PrintabilitySettings
from ..utilities.context import is_valid_mesh_object
from ..utilities.geometry import WorldTriangle, world_triangles, world_vertices
from ..utilities.units import millimetres_per_blender_unit
from .shell_analyzer import ShellAnalysis, analyze_shells
from .topology_analyzer import TopologyAnalysis, analyze_topology


@dataclass(frozen=True, slots=True)
class GeometryContext:
    obj: Any
    mesh: Any
    factor_mm: float
    vertices_mm: tuple[Vector, ...]
    triangles_mm: tuple[WorldTriangle, ...]
    face_vertices: tuple[tuple[int, ...], ...]
    face_normals: tuple[Vector, ...]
    face_centroids_mm: tuple[Vector, ...]
    face_areas_mm2: tuple[float, ...]
    edge_vertices: tuple[tuple[int, int], ...]
    topology: TopologyAnalysis
    shells: ShellAnalysis
    facts: GeometryFacts


def _face_measurements(obj: Any, vertices_mm: tuple[Vector, ...], triangles: tuple[WorldTriangle, ...]) -> tuple[tuple[Vector, ...], tuple[Vector, ...], tuple[float, ...]]:
    mesh = obj.data
    normal_matrix = obj.matrix_world.to_3x3().inverted_safe().transposed()
    normals: list[Vector] = []
    centroids: list[Vector] = []
    areas = [0.0] * len(mesh.polygons)
    for triangle in triangles:
        a, b, c = triangle.coordinates
        areas[triangle.face_index] += float((b - a).cross(c - a).length) * 0.5
    for polygon in mesh.polygons:
        normal = normal_matrix @ polygon.normal
        normals.append(normal.normalized() if normal.length_squared > 1e-24 else Vector((0.0, 0.0, 0.0)))
        points = [vertices_mm[int(index)] for index in polygon.vertices]
        centroids.append(sum(points, Vector((0.0, 0.0, 0.0))) / max(len(points), 1))
    return tuple(normals), tuple(centroids), tuple(areas)


def build_geometry_facts(obj: Any, scene: Any, settings: PrintabilitySettings) -> GeometryContext:
    if not is_valid_mesh_object(obj):
        raise ValueError("No valid active mesh object is available.")
    mesh = obj.data
    if not mesh.vertices or not mesh.polygons:
        raise ValueError("The selected mesh has no analyzable surface.")
    factor, _unit_system, _scale_length = millimetres_per_blender_unit(scene)
    vertices_bu = world_vertices(obj)
    vertices_mm = tuple(point * factor for point in vertices_bu)
    triangles_bu = world_triangles(mesh, vertices_bu)
    triangles_mm = tuple(
        WorldTriangle(
            triangle_index=item.triangle_index,
            face_index=item.face_index,
            vertex_indices=item.vertex_indices,
            coordinates=tuple(point * factor for point in item.coordinates),
        )
        for item in triangles_bu
    )
    analysis_settings = AnalysisSettings(maximum_stored_issue_indices=int(settings.evidence_cap or 1))
    topology = analyze_topology(mesh, analysis_settings)
    shells = analyze_shells(mesh, topology, vertices_mm, triangles_mm, 1.0, analysis_settings)
    normals, centroids, areas = _face_measurements(obj, vertices_mm, triangles_mm)
    minimum = Vector((min(point.x for point in vertices_mm), min(point.y for point in vertices_mm), min(point.z for point in vertices_mm)))
    maximum = Vector((max(point.x for point in vertices_mm), max(point.y for point in vertices_mm), max(point.z for point in vertices_mm)))
    direction = Vector(settings.normalized_build_direction())
    lowest = min(float(point.dot(direction)) for point in vertices_mm)
    metrics = topology.metrics
    facts = GeometryFacts(
        dimensions_mm=tuple(float(value) for value in (maximum - minimum)),
        bbox_min_mm=tuple(float(value) for value in minimum),
        bbox_max_mm=tuple(float(value) for value in maximum),
        shell_count=len(shells.shells),
        main_shell_id=shells.main_shell_id,
        triangle_count=len(triangles_mm),
        vertex_count=len(mesh.vertices),
        edge_count=len(mesh.edges),
        face_count=len(mesh.polygons),
        surface_area_mm2=shells.surface_volume.total_surface_area_mm2,
        reliable_volume_mm3=shells.surface_volume.reliable_closed_shell_volume_mm3,
        boundary_edges=metrics.boundary_edges,
        non_manifold_edges=metrics.high_incidence_non_manifold_edges,
        vertex_manifold_anomalies=metrics.vertex_manifold_anomalies,
        watertight=metrics.watertight_state == WatertightState.TOPOLOGICALLY_WATERTIGHT,
        lowest_build_plane_offset_mm=lowest,
    )
    return GeometryContext(
        obj=obj,
        mesh=mesh,
        factor_mm=factor,
        vertices_mm=vertices_mm,
        triangles_mm=triangles_mm,
        face_vertices=tuple(tuple(int(index) for index in polygon.vertices) for polygon in mesh.polygons),
        face_normals=normals,
        face_centroids_mm=centroids,
        face_areas_mm2=areas,
        edge_vertices=tuple(tuple(int(index) for index in edge.vertices) for edge in mesh.edges),
        topology=topology,
        shells=shells,
        facts=facts,
    )
