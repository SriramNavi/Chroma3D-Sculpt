"""Full geometry and protected-source signatures used by repair safety gates."""

from __future__ import annotations

from array import array
from hashlib import sha256
import json
import struct
import sys
from typing import Any


def _pointer(value: Any | None) -> int:
    try:
        return int(value.as_pointer()) if value is not None else 0
    except (AttributeError, ReferenceError, TypeError):
        return 0


def _simple(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "name"):
        return {"name": str(value.name), "identity": _pointer(value)}
    try:
        return [_simple(item) for item in value]
    except TypeError:
        return repr(value)


def geometry_sha256(obj: Any) -> str:
    """Hash vertex coordinates, edge connectivity, and ordered face winding."""

    mesh = obj.data
    digest = sha256()
    digest.update(struct.pack("<QQQ", len(mesh.vertices), len(mesh.edges), len(mesh.polygons)))
    coordinates = array("d", [0.0]) * (len(mesh.vertices) * 3)
    mesh.vertices.foreach_get("co", coordinates)
    if sys.byteorder != "little":
        coordinates.byteswap()
    digest.update(coordinates.tobytes())

    edge_vertices = array("i", [0]) * (len(mesh.edges) * 2)
    mesh.edges.foreach_get("vertices", edge_vertices)
    edge_values = array("Q", (int(value) for value in edge_vertices))
    if sys.byteorder != "little":
        edge_values.byteswap()
    digest.update(edge_values.tobytes())

    loop_vertices = array("i", [0]) * len(mesh.loops)
    mesh.loops.foreach_get("vertex_index", loop_vertices)
    starts = array("i", [0]) * len(mesh.polygons)
    totals = array("i", [0]) * len(mesh.polygons)
    mesh.polygons.foreach_get("loop_start", starts)
    mesh.polygons.foreach_get("loop_total", totals)
    for start, total in zip(starts, totals):
        digest.update(struct.pack("<Q", int(total)))
        indices = array("Q", (int(value) for value in loop_vertices[start:start + total]))
        if sys.byteorder != "little":
            indices.byteswap()
        digest.update(indices.tobytes())
    return digest.hexdigest()


def repair_workspace_signature(obj: Any) -> str:
    mesh = obj.data
    payload = {
        "object_identity": _pointer(obj),
        "mesh_identity": _pointer(mesh),
        "object_name": str(obj.name),
        "mesh_name": str(mesh.name),
        "vertex_count": len(mesh.vertices),
        "edge_count": len(mesh.edges),
        "face_count": len(mesh.polygons),
        "geometry_sha256": geometry_sha256(obj),
    }
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _modifier_summary(modifier: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "name": str(modifier.name),
        "type": str(modifier.type),
        "show_viewport": bool(modifier.show_viewport),
        "show_render": bool(modifier.show_render),
    }
    for prop in getattr(getattr(modifier, "bl_rna", None), "properties", ()):
        identifier = str(getattr(prop, "identifier", ""))
        if not identifier or identifier == "rna_type" or bool(getattr(prop, "is_readonly", False)):
            continue
        try:
            summary[identifier] = _simple(getattr(modifier, identifier))
        except (AttributeError, ReferenceError, TypeError, ValueError):
            continue
    return summary


def _constraint_summary(constraint: Any) -> dict[str, Any]:
    return {
        "name": str(getattr(constraint, "name", "")),
        "type": str(getattr(constraint, "type", "")),
        "mute": bool(getattr(constraint, "mute", False)),
        "influence": float(getattr(constraint, "influence", 0.0)),
        "target_identity": _pointer(getattr(constraint, "target", None)),
        "subtarget": str(getattr(constraint, "subtarget", "")),
    }


def _vertex_group_summary(obj: Any) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for group in obj.vertex_groups:
        weights: list[list[float]] = []
        for vertex in obj.data.vertices:
            try:
                weights.append([int(vertex.index), round(float(group.weight(vertex.index)), 12)])
            except (RuntimeError, ReferenceError):
                continue
        groups.append({"name": str(group.name), "index": int(group.index), "weights": weights})
    return groups


def _uv_summary(mesh: Any) -> list[dict[str, Any]]:
    return [
        {
            "name": str(layer.name),
            "data": [[round(float(item.uv.x), 12), round(float(item.uv.y), 12)] for item in layer.data],
        }
        for layer in mesh.uv_layers
    ]


def _attribute_summary(mesh: Any) -> list[dict[str, Any]]:
    attributes: list[dict[str, Any]] = []
    for attribute in getattr(mesh, "color_attributes", ()):
        values: list[Any] = []
        for item in attribute.data:
            values.append(_simple(getattr(item, "color", getattr(item, "value", None))))
        attributes.append({"name": str(attribute.name), "type": str(attribute.data_type), "domain": str(attribute.domain), "values": values})
    return attributes


def _shape_key_summary(mesh: Any) -> list[dict[str, Any]]:
    keys = getattr(mesh, "shape_keys", None)
    if keys is None:
        return []
    return [
        {
            "name": str(key.name),
            "value": round(float(key.value), 12),
            "relative_key": str(getattr(key.relative_key, "name", "")),
            "coordinates": [[round(float(point.co[index]), 12) for index in range(3)] for point in key.data],
        }
        for key in keys.key_blocks
    ]


def _polygon_normal_summary(mesh: Any) -> list[list[float]]:
    values = array("d", [0.0]) * (len(mesh.polygons) * 3)
    mesh.polygons.foreach_get("normal", values)
    return [
        [round(float(values[index]), 12), round(float(values[index + 1]), 12), round(float(values[index + 2]), 12)]
        for index in range(0, len(values), 3)
    ]


def protected_source_snapshot(obj: Any, blend_file_path: str = "") -> dict[str, Any]:
    mesh = obj.data
    custom = {str(key): _simple(obj[key]) for key in sorted(obj.keys()) if key != "_RNA_UI"}
    mesh_custom = {str(key): _simple(mesh[key]) for key in sorted(mesh.keys()) if key != "_RNA_UI"}
    payload = {
        "object_identity": _pointer(obj),
        "mesh_identity": _pointer(mesh),
        "object_name": str(obj.name),
        "mesh_name": str(mesh.name),
        "geometry_sha256": geometry_sha256(obj),
        "counts": [len(mesh.vertices), len(mesh.edges), len(mesh.polygons), len(mesh.loops)],
        "location": [float(value) for value in obj.location],
        "rotation_euler": [float(value) for value in obj.rotation_euler],
        "scale": [float(value) for value in obj.scale],
        "modifiers": [_modifier_summary(item) for item in obj.modifiers],
        "constraints": [_constraint_summary(item) for item in obj.constraints],
        "vertex_groups": _vertex_group_summary(obj),
        "uv_layers": _uv_summary(mesh),
        "color_attributes": _attribute_summary(mesh),
        "shape_keys": _shape_key_summary(mesh),
        "polygon_normals": _polygon_normal_summary(mesh),
        "materials": [
            {"name": str(getattr(slot.material, "name", "")), "identity": _pointer(slot.material)}
            for slot in obj.material_slots
        ],
        "active_material_index": int(getattr(obj, "active_material_index", 0)),
        "collections": sorted(str(item.name) for item in obj.users_collection),
        "custom_properties": custom,
        "mesh_custom_properties": mesh_custom,
        "hide_viewport": bool(obj.hide_viewport),
        "hide_render": bool(obj.hide_render),
        "hide_get": bool(obj.hide_get()),
        "display_type": str(obj.display_type),
        "selected": bool(obj.select_get()),
        "blend_file_path": str(blend_file_path),
    }
    protected_payload = {key: value for key, value in payload.items() if key != "selected"}
    encoded = json.dumps(protected_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["protected_sha256"] = sha256(encoded).hexdigest()
    return payload


def protected_source_is_current(obj: Any, expected: dict[str, Any], blend_file_path: str = "") -> bool:
    return protected_source_snapshot(obj, blend_file_path).get("protected_sha256") == expected.get("protected_sha256")
