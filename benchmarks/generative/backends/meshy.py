"""Meshy-6 benchmark adapter pinned to official OpenAPI v1 endpoints."""

from __future__ import annotations

import base64
from decimal import Decimal
import mimetypes
from pathlib import Path
from typing import Any, Mapping

from .base import BackendDescriptor, CostEstimate, GenerationJob, GenerationRequest
from .remote import RemoteGenerationBackend


class MeshyBackend(RemoteGenerationBackend):
    adapter_version = "1.0.0"
    credential_env = "MESHY_API_KEY"
    base_url = "https://api.meshy.ai/openapi/v1"

    def backend_info(self) -> BackendDescriptor:
        return BackendDescriptor(
            backend_id="meshy", provider="Meshy", model_version="meshy-6",
            backend_type="COMMERCIAL_API", supported_input_modes=("text", "image", "multiview"),
            supported_output_formats=("glb", "obj", "fbx", "stl", "usdz", "3mf"),
            supports_texture=True, supports_pbr=True, supports_multiview=True, supports_seed=False,
            supports_text=True, supports_image=True, supports_local=False, supports_remote=True,
            license_id="PROPRIETARY_SERVICE_TERMS", training_code_available=False, weights_available=False,
            min_vram_documented=None,
            request_cost_model={"state": "UNKNOWN_USD", "unit": "credits", "meshy6_untextured": 20, "meshy6_textured": 30, "meshy6_8k": 35},
            enabled=True, availability_state="SPEND_NOT_AUTHORIZED",
            provenance="Official API docs checked 2026-08-07; Meshy-6 is the current latest standard image model and exposes PBR plus six output formats.",
            official_sources=(
                {"title": "Meshy Image to 3D", "url": "https://docs.meshy.ai/en/api/image-to-3d"},
                {"title": "Meshy Multi-Image to 3D", "url": "https://docs.meshy.ai/en/api/multi-image-to-3d"},
                {"title": "Meshy API pricing", "url": "https://docs.meshy.ai/en/api/pricing"},
            ),
        )

    def estimate_cost(self, request_value: GenerationRequest) -> CostEstimate:
        request_value.validate()
        textured = bool(request_value.parameters.get("should_texture", False))
        resolution = str(request_value.parameters.get("texture_resolution", "2k"))
        credits = Decimal("35" if textured and resolution == "8k" else "30" if textured else "20")
        return CostEstimate("UNKNOWN", None, credits, "Official credit cost is known; USD conversion is account-dependent.")

    def _endpoint(self, request_value: GenerationRequest) -> str:
        return "text-to-3d" if request_value.track == "C" else "multi-image-to-3d" if request_value.track == "B" else "image-to-3d"

    def request_preview(self, request_value: GenerationRequest) -> Mapping[str, Any]:
        common: dict[str, Any] = {
            "ai_model": "meshy-6", "should_texture": bool(request_value.parameters.get("should_texture", False)),
            "enable_pbr": bool(request_value.parameters.get("enable_pbr", False)),
            "texture_resolution": request_value.parameters.get("texture_resolution", "2k"),
            "target_formats": list(request_value.parameters.get("target_formats", ["glb"])),
        }
        if request_value.track == "C":
            common["mode"], common["prompt"] = "preview", request_value.prompt or ""
        elif request_value.track == "B":
            common["image_urls"] = ["[DATA_URI_REDACTED]"] * len(request_value.input_paths)
        else:
            common["image_url"] = "[DATA_URI_REDACTED]"
        return common

    @staticmethod
    def _data_uri(path: Path) -> str:
        content = path.read_bytes()
        if len(content) > 20 * 1024 * 1024:
            raise ValueError("Meshy reference exceeds the documented 20 MiB input limit.")
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        return f"data:{mime};base64,{base64.b64encode(content).decode('ascii')}"

    def _submit_live(self, request_value: GenerationRequest) -> GenerationJob:
        payload = dict(self.request_preview(request_value))
        if request_value.track == "B":
            payload["image_urls"] = [self._data_uri(item) for item in request_value.input_paths]
        elif request_value.track != "C":
            if len(request_value.input_paths) != 1:
                raise ValueError("Meshy single-image track requires exactly one reference.")
            payload["image_url"] = self._data_uri(request_value.input_paths[0])
        endpoint = self._endpoint(request_value)
        response = self._request_json("POST", f"{self.base_url}/{endpoint}", payload)
        task_id = str(response.get("result", ""))
        if not task_id:
            raise RuntimeError("Meshy response did not include result task id.")
        return GenerationJob("meshy", task_id, "SUBMITTED", request_value, {"endpoint": endpoint})

    def _poll_live(self, job: GenerationJob) -> GenerationJob:
        endpoint = str(job.metadata.get("endpoint", self._endpoint(job.request)))
        data = self._request_json("GET", f"{self.base_url}/{endpoint}/{job.task_id}", None)
        status = str(data.get("status", ""))
        job.metadata.update({"provider_status": status, "progress": data.get("progress"), "consumed_credits": data.get("consumed_credits")})
        job.status = {"SUCCEEDED": "PASS", "FAILED": "PROVIDER_ERROR", "CANCELED": "NOT_RUN"}.get(status, "RUNNING")
        urls = data.get("model_urls", {})
        if isinstance(urls, dict) and isinstance(urls.get("glb"), str):
            job.metadata["artifact_url"] = urls["glb"]
        return job

    def _cancel_live(self, job: GenerationJob) -> GenerationJob:
        endpoint = str(job.metadata.get("endpoint", self._endpoint(job.request)))
        self._request_json("DELETE", f"{self.base_url}/{endpoint}/{job.task_id}", None)
        job.status, job.error_class = "NOT_RUN", "CANCELLED_AND_DELETED"
        return job

    def _retrieve_live(self, job: GenerationJob, output_directory: Path) -> GenerationJob:
        url = job.metadata.get("artifact_url")
        if not isinstance(url, str):
            raise RuntimeError("Meshy artifact URL is unavailable; poll the successful job first.")
        job.artifact_path = self._download(url, output_directory / f"{job.task_id}.glb")
        return job
