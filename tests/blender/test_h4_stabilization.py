"""H4 release-stabilization regressions for registration and cleanup."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest
from typing import Any

import bpy


ROOT = Path(__file__).resolve().parents[2]
ADDON_ROOT = ROOT / "blender_addon"
if str(ADDON_ROOT) not in sys.path:
    sys.path.insert(0, str(ADDON_ROOT))

import chroma3d_sculpt  # noqa: E402


class H4StabilizationTests(unittest.TestCase):
    def setUp(self) -> None:
        chroma3d_sculpt.unregister()

    def tearDown(self) -> None:
        chroma3d_sculpt.unregister()

    def test_duplicate_registration_is_idempotent(self) -> None:
        chroma3d_sculpt.register()
        chroma3d_sculpt.register()
        classes = (*chroma3d_sculpt.PROPERTY_CLASSES, *chroma3d_sculpt._RUNTIME_CLASSES)
        self.assertTrue(all(getattr(item, "is_registered", False) for item in classes))
        self.assertTrue(hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state"))

    def test_failed_registration_rolls_back_partial_state(self) -> None:
        original = bpy.utils.register_class
        counter = 0

        def injected(cls: Any) -> None:
            nonlocal counter
            counter += 1
            if counter == 5:
                raise RuntimeError("H4 injected registration failure")
            original(cls)

        bpy.utils.register_class = injected
        try:
            with self.assertRaisesRegex(RuntimeError, "H4 injected"):
                chroma3d_sculpt.register()
        finally:
            bpy.utils.register_class = original
        classes = (*chroma3d_sculpt.PROPERTY_CLASSES, *chroma3d_sculpt._RUNTIME_CLASSES)
        self.assertFalse(any(getattr(item, "is_registered", False) for item in classes))
        self.assertFalse(hasattr(bpy.types.WindowManager, "chroma3d_sculpt_state"))
        chroma3d_sculpt.register()
        self.assertTrue(all(getattr(item, "is_registered", False) for item in classes))

    def test_unregister_clears_credential_and_provider_registry(self) -> None:
        from chroma3d_sculpt.services.ai_credentials import resolve_key, set_session_key
        from chroma3d_sculpt.services.provider_registry import available_provider_ids, register_provider

        chroma3d_sculpt.register()
        set_session_key("h4-test-session-key")
        register_provider("h4-test", object())
        chroma3d_sculpt.unregister()
        self.assertEqual((None, "NOT_CONFIGURED"), resolve_key({}))
        self.assertEqual(("openai",), available_provider_ids())


if __name__ == "__main__":
    unittest.main()
