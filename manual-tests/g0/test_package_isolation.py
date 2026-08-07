from __future__ import annotations

import ast
import unittest

from _support import PROJECT_ROOT
import _project


class PackageIsolationTests(unittest.TestCase):
    def test_package_source_root_is_shipping_addon_only(self) -> None:
        expected = (PROJECT_ROOT / "blender_addon" / "chroma3d_sculpt").resolve()
        self.assertEqual(_project.SOURCE_ROOT.resolve(), expected)
        for forbidden in ("benchmarks", "manual-tests", "docs", ".validation-assets"):
            self.assertNotIn(forbidden, _project.SOURCE_ROOT.parts)

    def test_product_version_remains_h4_value(self) -> None:
        metadata = PROJECT_ROOT / "blender_addon" / "chroma3d_sculpt" / "metadata.py"
        tree = ast.parse(metadata.read_text(encoding="utf-8"))
        values = {
            node.targets[0].id: ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in {"EXTENSION_VERSION", "STAGE_LABEL"}
        }
        self.assertEqual(values, {"EXTENSION_VERSION": "0.8.0", "STAGE_LABEL": "alpha.1"})

    def test_g0_roots_are_outside_shipping_source(self) -> None:
        for relative in (
            "benchmarks/generative", "manual-tests/g0", "docs/generative",
            ".validation-assets/generative-benchmark",
        ):
            path = PROJECT_ROOT / relative
            self.assertFalse(path.resolve().is_relative_to(_project.SOURCE_ROOT.resolve()))


if __name__ == "__main__":
    unittest.main()
