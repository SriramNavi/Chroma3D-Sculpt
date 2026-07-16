"""Small, side-effect-free Blender context helpers."""

from __future__ import annotations

from typing import Any


def is_valid_mesh_object(obj: Any | None) -> bool:
    return obj is not None and getattr(obj, "type", None) == "MESH" and getattr(obj, "data", None) is not None


def active_mesh_object(context: Any) -> Any | None:
    obj = getattr(context, "active_object", None)
    return obj if is_valid_mesh_object(obj) else None


def object_session_key(obj: Any | None) -> int | None:
    if obj is None:
        return None
    try:
        return int(obj.as_pointer())
    except (AttributeError, ReferenceError, TypeError):
        return None


def capture_context_identity(context: Any) -> tuple[int | None, tuple[int, ...]]:
    active_key = object_session_key(getattr(context, "active_object", None))
    selected = tuple(
        sorted(
            key
            for key in (object_session_key(obj) for obj in getattr(context, "selected_objects", ()))
            if key is not None
        )
    )
    return active_key, selected

