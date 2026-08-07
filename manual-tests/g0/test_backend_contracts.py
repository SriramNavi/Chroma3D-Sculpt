from __future__ import annotations

import dataclasses
from pathlib import Path
import tempfile
import unittest

import _support

assert _support.GENERATIVE_ROOT.is_dir()
from backends.base import BackendDescriptor, ExecutionPolicy, GenerationRequest
from backends.registry import backend_registry


class BackendContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = backend_registry(ExecutionPolicy())

    def test_registry_is_complete_and_descriptors_are_strict(self) -> None:
        self.assertEqual(
            set(self.registry),
            {"trellis2", "hunyuan3d_2_1", "tripo", "meshy", "rodin", "fake_generator"},
        )
        expected = {field.name for field in dataclasses.fields(BackendDescriptor)}
        for backend in self.registry.values():
            descriptor = backend.backend_info()
            descriptor.validate()
            self.assertEqual(set(descriptor.to_dict()), expected)
            self.assertTrue(descriptor.model_version)
            self.assertTrue(descriptor.official_sources)

    def test_fake_backend_exercises_all_declared_failure_modes(self) -> None:
        backend = self.registry["fake_generator"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.obj"
            source.write_text("v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n", encoding="utf-8")
            for mode, expected in (
                ("success", "PASS"), ("failure", "GENERATION_FAILED"),
                ("timeout", "TIMEOUT"), ("invalid", "INVALID_ARTIFACT"),
            ):
                request = GenerationRequest(
                    case_id="fixture", track="A", input_paths=(source,), dry_run=False,
                    parameters={"fake_mode": mode}, seed=7,
                )
                self.assertEqual(backend.submit(request, root / mode).status, expected)

    def test_dry_run_is_offline_for_every_remote_backend(self) -> None:
        request = GenerationRequest(case_id="fixture", track="A", dry_run=True)
        with tempfile.TemporaryDirectory() as temporary:
            for backend_id in ("tripo", "meshy", "rodin"):
                backend = self.registry[backend_id]
                backend._request_json = lambda *args, **kwargs: self.fail("network attempted")  # type: ignore[attr-defined]
                job = backend.submit(request, Path(temporary))
                self.assertEqual(job.status, "PASS")
                self.assertEqual(job.metadata["network_calls"], 0)

    def test_unsupported_generation_track_is_not_scored_as_zero(self) -> None:
        request = GenerationRequest(case_id="fixture", track="C", prompt="test", dry_run=True)
        job = self.registry["trellis2"].submit(request, Path("unused"))
        self.assertEqual(job.status, "UNSUPPORTED_TRACK")
        self.assertEqual(job.error_class, "UNSUPPORTED_TRACK")


if __name__ == "__main__":
    unittest.main()
