"""Deterministic topology signatures for stale-analysis protection."""

from __future__ import annotations

from hashlib import sha256
import struct
from typing import Any

from ..models.analysis_result import TopologySignature


def topology_signature(obj: Any, analysis_id: str = "") -> TopologySignature:
    mesh = obj.data
    digest = sha256()
    digest.update(struct.pack("<QQQ", len(mesh.vertices), len(mesh.edges), len(mesh.polygons)))
    for edge in mesh.edges:
        digest.update(struct.pack("<QQ", int(edge.vertices[0]), int(edge.vertices[1])))
    for polygon in mesh.polygons:
        vertices = tuple(int(index) for index in polygon.vertices)
        digest.update(struct.pack("<Q", len(vertices)))
        for index in vertices:
            digest.update(struct.pack("<Q", index))
    return TopologySignature(
        analysis_id=analysis_id,
        object_name=str(obj.name),
        mesh_data_name=str(mesh.name),
        vertex_count=len(mesh.vertices),
        edge_count=len(mesh.edges),
        polygon_count=len(mesh.polygons),
        topology_sha256=digest.hexdigest(),
    )


def is_topology_signature_current(obj: Any, expected: TopologySignature) -> bool:
    current = topology_signature(obj)
    return (
        current.object_name == expected.object_name
        and current.mesh_data_name == expected.mesh_data_name
        and current.vertex_count == expected.vertex_count
        and current.edge_count == expected.edge_count
        and current.polygon_count == expected.polygon_count
        and current.topology_sha256 == expected.topology_sha256
    )
