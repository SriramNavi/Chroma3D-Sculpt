"""Blender scene-unit conversion helpers."""

from __future__ import annotations

from typing import Any


def millimetres_per_blender_unit(scene: Any | None) -> tuple[float, str, float]:
    """Return mm/BU, unit-system label, and scene scale.

    Blender's scale_length is metres per Blender unit for physical unit systems.
    Unitless scenes use the documented Sprint 0 convention of 1 BU = 1 metre.
    """

    settings = getattr(scene, "unit_settings", None)
    unit_system = str(getattr(settings, "system", "NONE") or "NONE")
    scale_length = float(getattr(settings, "scale_length", 1.0) or 1.0)
    if scale_length <= 0.0:
        scale_length = 1.0
    if unit_system == "NONE":
        scale_length = 1.0
    return scale_length * 1000.0, unit_system, scale_length


def object_dimensions_mm(obj: Any, scene: Any | None) -> tuple[float, float, float, str, float, float]:
    """Convert scaled object dimensions to millimetres without applying scale."""

    factor, unit_system, scale_length = millimetres_per_blender_unit(scene)
    values = tuple(abs(float(value)) * factor for value in obj.dimensions)
    return values[0], values[1], values[2], unit_system, scale_length, factor

