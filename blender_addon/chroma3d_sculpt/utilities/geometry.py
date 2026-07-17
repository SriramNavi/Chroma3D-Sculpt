"""World-space mesh geometry helpers shared by diagnostic services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mathutils import Vector


@dataclass(frozen=True, slots=True)
class WorldTriangle:
    triangle_index: int
    face_index: int
    vertex_indices: tuple[int, int, int]
    coordinates: tuple[Vector, Vector, Vector]


def world_vertices(obj: Any) -> tuple[Vector, ...]:
    matrix = obj.matrix_world
    return tuple(matrix @ vertex.co for vertex in obj.data.vertices)


def world_triangles(mesh: Any, coordinates: tuple[Vector, ...]) -> tuple[WorldTriangle, ...]:
    mesh.calc_loop_triangles()
    return tuple(
        WorldTriangle(
            triangle_index=index,
            face_index=int(triangle.polygon_index),
            vertex_indices=tuple(int(item) for item in triangle.vertices),
            coordinates=tuple(coordinates[int(item)] for item in triangle.vertices),
        )
        for index, triangle in enumerate(mesh.loop_triangles)
    )


def bounding_box(points: tuple[Vector, ...]) -> tuple[Vector, Vector]:
    if not points:
        zero = Vector((0.0, 0.0, 0.0))
        return zero.copy(), zero.copy()
    minimum = Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points)))
    maximum = Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points)))
    return minimum, maximum
