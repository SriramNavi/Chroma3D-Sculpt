"""Deterministic offline backend that copies known geometry into the raw cache."""

from __future__ import annotations

from decimal import Decimal
import hashlib
from pathlib import Path
import shutil

from .base import BackendDescriptor, CostEstimate, GenerationBackend, GenerationJob, GenerationRequest


class FakeGeneratorBackend(GenerationBackend):
    adapter_version = "1.0.0"

    def backend_info(self) -> BackendDescriptor:
        return BackendDescriptor(
            backend_id="fake_generator", provider="Chroma3D", model_version="fake-generator-1.0",
            backend_type="FAKE", supported_input_modes=("image", "multiview", "text"),
            supported_output_formats=("stl", "obj"), supports_texture=False, supports_pbr=False,
            supports_multiview=True, supports_seed=True, supports_text=True, supports_image=True,
            supports_local=True, supports_remote=False, license_id="INTERNAL_TEST_FIXTURE",
            training_code_available=False, weights_available=False, min_vram_documented=None,
            request_cost_model={"state": "KNOWN", "usd_per_job": "0"}, enabled=True,
            availability_state="READY_LOCAL", provenance="Deterministic offline CGB fixture; excluded from model rankings.",
            official_sources=({"title": "CGB specification", "url": "benchmarks/generative/CGB_SPECIFICATION.md"},),
        )

    def validate_environment(self) -> dict[str, object]:
        return {**self.base_environment(), "availability_state": "READY_LOCAL", "network_required": False}

    def estimate_cost(self, request: GenerationRequest) -> CostEstimate:
        request.validate()
        return CostEstimate("KNOWN", Decimal("0"), Decimal("0"), "Offline fixture")

    def submit(self, request: GenerationRequest, output_directory: Path) -> GenerationJob:
        request.validate()
        unsupported = self.unsupported_track_job(request)
        if unsupported is not None:
            return unsupported
        mode = str(request.parameters.get("fake_mode", "success"))
        task_id = hashlib.sha256(
            f"{request.case_id}:{request.track}:{request.attempt}:{request.seed}:{mode}".encode("utf-8")
        ).hexdigest()[:24]
        job = GenerationJob("fake_generator", task_id, "SUBMITTED", request, {"fake_mode": mode, "network_calls": 0})
        if request.dry_run:
            job.status = "PASS"
            job.metadata["dry_run"] = True
            return job
        if mode == "failure":
            job.status, job.error_class, job.error_message = "GENERATION_FAILED", "FAKE_FAILURE", "Requested fake failure."
            return job
        if mode == "timeout":
            job.status, job.error_class, job.error_message = "TIMEOUT", "FAKE_TIMEOUT", "Requested fake timeout."
            return job
        output_directory.mkdir(parents=True, exist_ok=True)
        suffix = request.input_paths[0].suffix.lower() if request.input_paths else ".obj"
        target = output_directory / f"{request.case_id}-attempt-{request.attempt}{suffix}"
        if mode == "invalid":
            target.write_bytes(b"not a valid 3d artifact\n")
            job.status, job.error_class = "INVALID_ARTIFACT", "FAKE_INVALID_ARTIFACT"
        elif request.input_paths:
            shutil.copyfile(request.input_paths[0], target)
            job.status = "PASS"
        else:
            target.write_text(
                "v -1 -1 0\nv 1 -1 0\nv 0 1 0\nf 1 2 3\n",
                encoding="utf-8", newline="\n",
            )
            job.status = "PASS"
        job.artifact_path = target
        job.metadata["artifact_bytes"] = target.stat().st_size
        return job

    def poll(self, job: GenerationJob) -> GenerationJob:
        return job

    def cancel(self, job: GenerationJob) -> GenerationJob:
        if job.status in {"SUBMITTED", "RUNNING"}:
            job.status = "NOT_RUN"
            job.error_class = "CANCELLED"
        return job

    def retrieve(self, job: GenerationJob, output_directory: Path) -> GenerationJob:
        return job
