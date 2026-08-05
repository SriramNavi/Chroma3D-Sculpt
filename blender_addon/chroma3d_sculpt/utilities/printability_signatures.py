"""Full Sprint 3 source, geometry, transform, profile, and settings signatures."""

from __future__ import annotations

from hashlib import sha256
import json
import struct
from typing import Any

import bpy

from .repair_signatures import geometry_sha256, protected_source_snapshot


def _pointer(value: Any | None) -> int:
    try:
        return int(value.as_pointer()) if value is not None else 0
    except (AttributeError, ReferenceError, TypeError):
        return 0


def geometry_signature(obj: Any) -> str:
    mesh = obj.data
    payload = {
        "object_identity": _pointer(obj),
        "mesh_identity": _pointer(mesh),
        "object_name": str(obj.name),
        "mesh_name": str(mesh.name),
        "geometry_sha256": geometry_sha256(obj),
        "counts": [len(mesh.vertices), len(mesh.edges), len(mesh.polygons), len(mesh.loops)],
    }
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def transform_signature(obj: Any) -> str:
    digest = sha256()
    digest.update(struct.pack("<Q", _pointer(obj)))
    for row in obj.matrix_world:
        digest.update(struct.pack("<dddd", *(float(value) for value in row)))
    for values in (obj.location, obj.rotation_euler, obj.scale):
        digest.update(struct.pack("<ddd", *(float(value) for value in values)))
    return digest.hexdigest()


def printability_source_snapshot(obj: Any, blend_file_path: str = "") -> dict[str, Any]:
    snapshot = protected_source_snapshot(obj, blend_file_path)
    snapshot["file_is_dirty"] = bool(getattr(bpy.data, "is_dirty", False))
    protected = {key: value for key, value in snapshot.items() if key not in {"selected", "protected_sha256", "printability_sha256"}}
    snapshot["printability_sha256"] = sha256(
        json.dumps(protected, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return snapshot


def source_is_unchanged(obj: Any, expected: dict[str, Any], blend_file_path: str = "") -> bool:
    return printability_source_snapshot(obj, blend_file_path).get("printability_sha256") == expected.get("printability_sha256")
