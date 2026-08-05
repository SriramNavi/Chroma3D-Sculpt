"""Source/workspace/stale-state fingerprints for controlled optimization."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

from .repair_signatures import geometry_sha256, protected_source_is_current, protected_source_snapshot


IMPLEMENTATION_FINGERPRINT = "sprint5-controlled-optimization-1.0"


def _pointer(value: Any | None) -> int:
    try:
        return int(value.as_pointer()) if value is not None else 0
    except (AttributeError, ReferenceError, TypeError):
        return 0


def _hash(payload: Mapping[str, Any]) -> str:
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def source_signature(obj: Any, blend_file_path: str = "") -> dict[str, Any]:
    snapshot = protected_source_snapshot(obj, blend_file_path)
    snapshot["source_signature"] = snapshot["protected_sha256"]
    # Blender exposes the file dirty flag as read-only. Record it for audit
    # provenance, while deliberately excluding it from the source geometry
    # hash because creating an isolated workspace may dirty an unsaved file.
    try:
        import bpy
        snapshot["blend_file_dirty_state"] = bool(bpy.data.is_dirty)
    except (ImportError, AttributeError, RuntimeError):
        snapshot["blend_file_dirty_state"] = None
    return snapshot


def workspace_signature(obj: Any) -> str:
    mesh = obj.data
    payload = {
        "geometry_sha256": geometry_sha256(obj),
        "location": [round(float(value), 12) for value in obj.location],
        "rotation_euler": [round(float(value), 12) for value in obj.rotation_euler],
        "scale": [round(float(value), 12) for value in obj.scale],
        "counts": [len(mesh.vertices), len(mesh.edges), len(mesh.polygons), len(mesh.loops)],
    }
    return _hash(payload)


def workspace_snapshot(obj: Any) -> dict[str, Any]:
    return {
        "object_name": str(obj.name),
        "object_identity": _pointer(obj),
        "mesh_name": str(obj.data.name),
        "mesh_identity": _pointer(obj.data),
        "workspace_signature": workspace_signature(obj),
    }


def stale_key(
    source: Mapping[str, Any],
    workspace: Any,
    *,
    hardware_profile_hash: str = "",
    material_profile_hash: str = "",
    process_context_hash: str = "",
    feature_flag_hash: str = "",
    performance_registry_version: str = "",
    optimization_policy_hash: str = "",
    objective_weight_hash: str = "",
    selected_plan_hash: str = "",
    implementation_fingerprint: str = IMPLEMENTATION_FINGERPRINT,
) -> str:
    payload = {
        "source_object_identity": source.get("object_identity", 0),
        "source_mesh_identity": source.get("mesh_identity", 0),
        "source_geometry_signature": source.get("geometry_sha256", ""),
        "source_transform_signature": _hash({
            "location": source.get("location", []), "rotation_euler": source.get("rotation_euler", []), "scale": source.get("scale", []),
        }),
        "workspace_object_identity": _pointer(workspace),
        "workspace_mesh_identity": _pointer(getattr(workspace, "data", None)),
        "workspace_signature": workspace_signature(workspace),
        "hardware_profile_hash": hardware_profile_hash,
        "material_profile_hash": material_profile_hash,
        "process_context_hash": process_context_hash,
        "feature_flag_hash": feature_flag_hash,
        "performance_registry_version": performance_registry_version,
        "optimization_policy_hash": optimization_policy_hash,
        "objective_weight_hash": objective_weight_hash,
        "selected_plan_hash": selected_plan_hash,
        "implementation_fingerprint": implementation_fingerprint,
    }
    return _hash(payload)


def source_is_current(obj: Any, expected: Mapping[str, Any], blend_file_path: str = "") -> bool:
    return protected_source_is_current(obj, dict(expected), blend_file_path)


__all__ = (
    "IMPLEMENTATION_FINGERPRINT", "source_signature", "source_is_current", "stale_key", "workspace_signature", "workspace_snapshot",
)
