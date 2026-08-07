"""Focused standard-library tests for the H2 suspicious-reference analyzer."""

from __future__ import annotations

import ast
from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_suspicious_references as analyzer  # noqa: E402


class SuspiciousReferenceAnalyzerTests(unittest.TestCase):
    def test_resolves_relative_import_and_binding(self) -> None:
        text = "from ..models.values import Active, Unused\nprint(Active)\n"
        bindings = analyzer._find_bindings(text, "chroma3d_sculpt.operators.sample", "Unused")
        self.assertEqual(len(bindings), 1)
        self.assertEqual(bindings[0].source_module, "chroma3d_sculpt.models.values")
        self.assertEqual(bindings[0].alias_count, 2)

    def test_detects_direct_name_load(self) -> None:
        self.assertEqual(analyzer._name_load_count("from json import loads\nloads('{}')\n", "loads"), 1)

    def test_detects_explicit_export(self) -> None:
        tree = ast.parse("from pkg import value\n__all__ = ('value',)\n")
        self.assertIn("value", analyzer._all_exports(tree))

    def test_string_annotation_is_dynamic_risk(self) -> None:
        tree = ast.parse("def f(value: 'ExternalType') -> None:\n    pass\n")
        self.assertIn("string_annotation:1", analyzer._dynamic_module_risks(tree, "ExternalType"))

    def test_function_local_namespace_check_does_not_block_unrelated_import(self) -> None:
        tree = ast.parse("def f():\n    return 'value' in locals()\n")
        self.assertEqual(analyzer._dynamic_module_risks(tree, "UnusedImport"), [])

    def test_module_globals_export_is_dynamic_risk(self) -> None:
        tree = ast.parse("__all__ = [name for name in globals()]\n")
        self.assertIn("globals_namespace_access", analyzer._dynamic_module_risks(tree, "UnusedImport"))

    def test_proven_unused_requires_safe_import_side_effect(self) -> None:
        classification, _ = analyzer._classify({
            "h1_name_loads": 0,
            "current_name_loads": 0,
            "exported_by___all__": False,
            "dynamic_module_risks": [],
            "external_references": [],
            "side_effect_disposition": "SAFE_PLATFORM_OR_STDLIB_IMPORT",
        })
        self.assertEqual(classification, "PROVEN_UNUSED")

    def test_sole_internal_import_remains_ambiguous(self) -> None:
        classification, _ = analyzer._classify({
            "h1_name_loads": 0,
            "current_name_loads": 0,
            "exported_by___all__": False,
            "dynamic_module_risks": [],
            "external_references": [],
            "side_effect_disposition": "IMPORT_SIDE_EFFECT_NOT_DISPROVEN",
        })
        self.assertEqual(classification, "AMBIGUOUS")

    def test_test_reference_blocks_removal(self) -> None:
        classification, _ = analyzer._classify({
            "h1_name_loads": 0,
            "current_name_loads": 0,
            "exported_by___all__": False,
            "dynamic_module_risks": [],
            "external_references": [{"kind": "test", "mechanism": "from_import"}],
            "side_effect_disposition": "PRESERVED_BY_REMAINING_IMPORT",
        })
        self.assertEqual(classification, "TEST_ONLY")


if __name__ == "__main__":
    unittest.main()
