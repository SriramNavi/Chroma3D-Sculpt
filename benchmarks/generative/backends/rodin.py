"""Hyper3D Rodin Gen-2 benchmark adapter using official asynchronous endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .base import BackendDescriptor, CostEstimate, GenerationJob, GenerationRequest
from .remote import RemoteGenerationBackend


class RodinBackend(RemoteGenerationBackend):
    adapter_version = "1.0.0"
    credential_env = "RODIN_API_KEY"
    base_url = "https://api.hyper3d.com/api/v2"

    def backend_info(self) -> BackendDescriptor:
        return BackendDescriptor(
            backend_id="rodin", provider="Hyper3D", model_version="Rodin Gen-2",
            backend_type="COMMERCIAL_API", supported_input_modes=("text", "image", "multiview"),
            supported_output_formats=("glb", "obj", "fbx", "stl", "usdz"), supports_texture=True,
            supports_pbr=True, supports_multiview=True, supports_seed=True, supports_text=True,
            supports_image=True, supports_local=False, supports_remote=True,
            license_id="PROPRIETARY_SERVICE_TERMS", training_code_available=False, weights_available=False,
            min_vram_documented=None, request_cost_model={"state": "UNKNOWN_USD", "unit": "credits", "business_subscription_required": True},
            enabled=True, availability_state="SPEND_NOT_AUTHORIZED",
            provenance="Official public API docs checked 2026-08-07; Gen-2 pin supports text/image/multi-image, PBR, async status and download.",
            official_sources=(
                {"title": "Hyper3D Rodin overview", "url": "https://developer.hyper3d.ai/api-specification/overview"},
                {"title": "Rodin Gen-2 generation", "url": "https://developer.hyper3d.ai/api-specification/rodin-generation-gen2"},
                {"title": "Rodin status", "url": "https://developer.hyper3d.ai/api-specification/check-status"},
                {"title": "Rodin download", "url": "https://developer.hyper3d.ai/api-specification/download-results"},
            ),
        )

    def estimate_cost(self, request_value: GenerationRequest) -> CostEstimate:
        request_value.validate()
        return CostEstimate("UNKNOWN", None, None, "Official Gen-2 USD/credit cost was not publicly bounded in the pinned documentation.")

    def request_preview(self, request_value: GenerationRequest) -> Mapping[str, Any]:
        return {
            "tier": "Gen-2", "prompt": request_value.prompt or "",
            "image_count": len(request_value.input_paths), "seed": request_value.seed,
            "geometry_file_format": request_value.parameters.get("geometry_file_format", "glb"),
            "material": "PBR" if request_value.parameters.get("pbr", False) else "Shaded",
        }

    def _submit_live(self, request_value: GenerationRequest) -> GenerationJob:
        preview = self.request_preview(request_value)
        fields = {key: str(value) for key, value in preview.items() if key != "image_count" and value not in {None, ""}}
        files = tuple(("images", item) for item in request_value.input_paths)
        response = self._multipart_request(f"{self.base_url}/rodin", fields, files)
        task_id = str(response.get("uuid", ""))
        jobs = response.get("jobs", {})
        subscription_key = str(jobs.get("subscription_key", "")) if isinstance(jobs, dict) else ""
        if not task_id or not subscription_key:
            raise RuntimeError("Rodin response did not include uuid/subscription_key.")
        return GenerationJob("rodin", task_id, "SUBMITTED", request_value, {"subscription_key": subscription_key})

    def _poll_live(self, job: GenerationJob) -> GenerationJob:
        subscription_key = job.metadata.get("subscription_key")
        if not isinstance(subscription_key, str):
            raise RuntimeError("Rodin subscription_key is unavailable.")
        data = self._request_json("POST", f"{self.base_url}/status", {"subscription_key": subscription_key})
        statuses = [str(item.get("status")) for item in data.get("jobs", []) if isinstance(item, dict)]
        job.metadata["provider_statuses"] = statuses
        if statuses and all(item == "Done" for item in statuses):
            job.status = "PASS"
        elif any(item == "Failed" for item in statuses):
            job.status = "PROVIDER_ERROR"
        else:
            job.status = "RUNNING"
        return job

    def _cancel_live(self, job: GenerationJob) -> GenerationJob:
        job.error_class = "CANCELLATION_NOT_DOCUMENTED"
        job.error_message = "The pinned public Gen-2 documentation does not expose a cancellation endpoint."
        return job

    def _retrieve_live(self, job: GenerationJob, output_directory: Path) -> GenerationJob:
        data = self._request_json("POST", f"{self.base_url}/download", {"task_uuid": job.task_id})
        urls = data.get("list", data.get("urls", []))
        first = next((item for item in urls if isinstance(item, dict) and isinstance(item.get("url"), str)), None) if isinstance(urls, list) else None
        if first is None:
            raise RuntimeError("Rodin download response did not include an artifact URL.")
        suffix = Path(str(first.get("name", "model.glb"))).suffix or ".glb"
        job.artifact_path = self._download(str(first["url"]), output_directory / f"{job.task_id}{suffix}")
        return job
