"""Full geometry and protected-source signatures used by repair safety gates."""

from __future__ import annotations

from hashlib import sha256
import json
import struct
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
    for vertex in mesh.vertices:
        digest.update(struct.pack("<ddd", float(vertex.co.x), float(vertex.co.y), float(vertex.co.z)))
    for edge in mesh.edges:
        digest.update(struct.pack("<QQ", int(edge.vertices[0]), int(edge.vertices[1])))
    for polygon in mesh.polygons:
        indices = tuple(int(index) for index in polygon.vertices)
        digest.update(struct.pack("<Q", len(indices)))
        for index in indices:
            digest.update(struct.pack("<Q", index))
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
        "materials": [
            {"name": str(getattr(slot.material, "name", "")), "identity": _pointer(slot.material)}
            for slot in obj.material_slots
        ],
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
