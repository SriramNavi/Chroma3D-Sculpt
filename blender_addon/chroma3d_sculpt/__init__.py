"""Chroma3D Sculpt Blender extension registration entrypoint."""

from __future__ import annotations

import bpy
from bpy.props import PointerProperty

from .metadata import DISPLAY_VERSION, EXTENSION_NAME, EXTENSION_VERSION
from .operators import ANALYZE_CLASSES, EXPORT_CLASSES
from .session import clear as clear_session
from .ui import PANEL_CLASSES, PROPERTY_CLASSES
from .utilities.logging import get_logger

bl_info = {
    "name": EXTENSION_NAME,
    "author": "Chroma3D",
    "version": tuple(int(part) for part in EXTENSION_VERSION.split(".")),
    "blender": (4, 4, 0),
    "location": "3D Viewport > Sidebar > Chroma3D",
    "description": f"Read-only mesh analysis ({DISPLAY_VERSION})",
    "category": "Mesh",
}

logger = get_logger()
_RUNTIME_CLASSES = ANALYZE_CLASSES + EXPORT_CLASSES + PANEL_CLASSES


def register() -> None:
    logger.info("Registering Chroma3D Sculpt %s", DISPLAY_VERSION)
    for cls in PROPERTY_CLASSES:
        bpy.utils.register_class(cls)
    if hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state"):
        del bpy.types.WindowManager.chroma3d_sculpt_state
    bpy.types.WindowManager.chroma3d_sculpt_state = PointerProperty(type=PROPERTY_CLASSES[0])
    for cls in _RUNTIME_CLASSES:
        bpy.utils.register_class(cls)
    logger.info("Chroma3D Sculpt registered")


def unregister() -> None:
    logger.info("Unregistering Chroma3D Sculpt")
    for cls in reversed(_RUNTIME_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            logger.debug("Class was not registered during unload: %s", cls.__name__)
    if hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state"):
        del bpy.types.WindowManager.chroma3d_sculpt_state
    for cls in reversed(PROPERTY_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            logger.debug("Property class was not registered during unload: %s", cls.__name__)
    clear_session()
    logger.info("Chroma3D Sculpt unregistered")
