"""Import and run selected Blender unittest modules without leaking Blender CLI args."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]


def _arguments() -> list[str]:
    if "--" not in sys.argv:
        raise SystemExit("Expected test paths after Blender's -- separator")
    return sys.argv[sys.argv.index("--") + 1:]


def main() -> int:
    suite = unittest.TestSuite()
    for index, value in enumerate(_arguments(), 1):
        path = (ROOT / value).resolve()
        if not path.is_file() or ROOT not in path.parents:
            raise SystemExit(f"Invalid focused test path: {value}")
        if str(path.parent) not in sys.path:
            sys.path.insert(0, str(path.parent))
        module_name = f"h2_focused_{index}_{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise SystemExit(f"Unable to import focused test: {value}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"H2 focused Blender tests: {result.testsRun}; status={'PASS' if result.wasSuccessful() else 'FAIL'}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
