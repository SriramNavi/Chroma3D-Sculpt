"""Chroma3D Sculpt Blender extension registration entrypoint."""

from __future__ import annotations

import bpy
from bpy.props import PointerProperty

from .metadata import DISPLAY_VERSION, EXTENSION_NAME, EXTENSION_VERSION
from .operators import ADVANCED_PREPARATION_CLASSES, AI_ASSISTANCE_CLASSES, ANALYZE_CLASSES, EXPORT_CLASSES, INTELLIGENT_OPTIMIZATION_CLASSES, OPTIMIZATION_CLASSES, PRINTABILITY_CLASSES, REPAIR_CLASSES, SELECTION_CLASSES
from .session import clear as clear_session
from .services.repair_session import clear_runtime as clear_repair_runtime
from .services.printability_session import clear_runtime as clear_printability_runtime
from .services.advanced_preparation_session import clear_runtime as clear_preparation_runtime
from .services.batch_preparation_session import clear_runtime as clear_batch_runtime
from .services.optimization_session import clear_runtime as clear_optimization_runtime
from .services.optimization_workspace import clear_runtime as clear_optimization_workspace_runtime
from .services.intelligent_optimization_session import clear_runtime as clear_intelligent_optimization_runtime
from .services.ai_assistance_session import clear_runtime as clear_ai_assistance_session_runtime
from .services.ai_assistance_coordinator import clear_runtime as clear_ai_assistance_runtime
from .services.ai_credentials import clear_session_key
from .services.provider_registry import reset_test_providers
from .ui import ADVANCED_PREPARATION_PANEL_CLASSES, AI_ASSISTANCE_PANEL_CLASSES, INTELLIGENT_OPTIMIZATION_PANEL_CLASSES, OPTIMIZATION_PANEL_CLASSES, PANEL_CLASSES, PRINTABILITY_PANEL_CLASSES, PROPERTY_CLASSES, REPAIR_PANEL_CLASSES, SESSION_STATE_CLASS
from .utilities.logging import get_logger

bl_info = {
    "name": EXTENSION_NAME,
    "author": "Chroma3D",
    "version": tuple(int(part) for part in EXTENSION_VERSION.split(".")),
    "blender": (4, 4, 0),
    "location": "3D Viewport > Sidebar > Chroma3D",
    "description": f"Mesh diagnostics, protected optimization, and optional advisory AI recommendations ({DISPLAY_VERSION})",
    "category": "Mesh",
}

logger = get_logger()
_RUNTIME_CLASSES = ANALYZE_CLASSES + EXPORT_CLASSES + SELECTION_CLASSES + REPAIR_CLASSES + PRINTABILITY_CLASSES + ADVANCED_PREPARATION_CLASSES + OPTIMIZATION_CLASSES + INTELLIGENT_OPTIMIZATION_CLASSES + AI_ASSISTANCE_CLASSES + PANEL_CLASSES + REPAIR_PANEL_CLASSES + PRINTABILITY_PANEL_CLASSES + ADVANCED_PREPARATION_PANEL_CLASSES + OPTIMIZATION_PANEL_CLASSES + INTELLIGENT_OPTIMIZATION_PANEL_CLASSES + AI_ASSISTANCE_PANEL_CLASSES
_ALL_CLASSES = PROPERTY_CLASSES + _RUNTIME_CLASSES


def _clear_runtime() -> None:
    clear_session()
    clear_repair_runtime()
    clear_printability_runtime()
    clear_preparation_runtime()
    clear_batch_runtime()
    clear_optimization_runtime()
    clear_optimization_workspace_runtime()
    clear_intelligent_optimization_runtime()
    clear_ai_assistance_session_runtime()
    clear_ai_assistance_runtime()
    clear_session_key()
    reset_test_providers()


def register() -> None:
    logger.info("Registering Chroma3D Sculpt %s", DISPLAY_VERSION)
    registered = tuple(bool(getattr(cls, "is_registered", False)) for cls in _ALL_CLASSES)
    has_state = hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state")
    if all(registered) and has_state:
        logger.debug("Chroma3D Sculpt is already registered")
        return
    if any(registered) or has_state:
        unregister()

    completed: list[type] = []
    try:
        for cls in PROPERTY_CLASSES:
            bpy.utils.register_class(cls)
            completed.append(cls)
        bpy.types.WindowManager.chroma3d_sculpt_state = PointerProperty(type=SESSION_STATE_CLASS)
        for cls in _RUNTIME_CLASSES:
            bpy.utils.register_class(cls)
            completed.append(cls)
    except Exception:
        if hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state"):
            del bpy.types.WindowManager.chroma3d_sculpt_state
        for cls in reversed(completed):
            try:
                bpy.utils.unregister_class(cls)
            except RuntimeError:
                logger.debug("Class was not registered during rollback: %s", cls.__name__)
        _clear_runtime()
        logger.exception("Chroma3D Sculpt registration failed; partial state was rolled back")
        raise
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
    _clear_runtime()
    logger.info("Chroma3D Sculpt unregistered")
