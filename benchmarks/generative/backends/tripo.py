"""Tripo v3.1 benchmark adapter pinned to the official v2 OpenAPI surface."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from .base import BackendDescriptor, CostEstimate, GenerationJob, GenerationRequest
from .remote import RemoteGenerationBackend


class TripoBackend(RemoteGenerationBackend):
    adapter_version = "1.0.0"
    credential_env = "TRIPO_API_KEY"
    base_url = "https://api.tripo3d.ai/v2/openapi"

    def backend_info(self) -> BackendDescriptor:
        return BackendDescriptor(
            backend_id="tripo", provider="Tripo AI", model_version="v3.1-20260211",
            backend_type="COMMERCIAL_API", supported_input_modes=("text", "image", "multiview"),
            supported_output_formats=("glb", "fbx"), supports_texture=True, supports_pbr=True,
            supports_multiview=True, supports_seed=True, supports_text=True, supports_image=True,
            supports_local=False, supports_remote=True, license_id="PROPRIETARY_SERVICE_TERMS",
            training_code_available=False, weights_available=False, min_vram_documented=None,
            request_cost_model={"state": "UNKNOWN_USD", "unit": "credits", "image_untextured": 20, "image_standard_texture": 30, "benchmark_pin": "v3.1"},
            enabled=True, availability_state="SPEND_NOT_AUTHORIZED",
            provenance="Official API generation/billing docs checked 2026-08-07; benchmark pin favors high-detail v3.1 over the P1 smart-mesh track.",
            official_sources=(
                {"title": "Tripo generation API", "url": "https://platform.tripo3d.ai/docs/generation"},
                {"title": "Tripo task API", "url": "https://platform.tripo3d.ai/docs/task"},
                {"title": "Tripo billing", "url": "https://platform.tripo3d.ai/docs/billing"},
            ),
        )

    def estimate_cost(self, request_value: GenerationRequest) -> CostEstimate:
        request_value.validate()
        textured = bool(request_value.parameters.get("texture", False) or request_value.parameters.get("pbr", False))
        credits = Decimal("30" if textured else "20")
        return CostEstimate("UNKNOWN", None, credits, "Official credit cost is known; USD conversion is account-dependent.")

    def request_preview(self, request_value: GenerationRequest) -> Mapping[str, Any]:
        if request_value.track == "C":
            payload: dict[str, Any] = {"type": "text_to_model", "prompt": request_value.prompt or ""}
        elif request_value.track == "B":
            payload = {"type": "multiview_to_model", "files": ["[OWNER_AUTHORIZED_UPLOAD]"] * len(request_value.input_paths)}
        else:
            payload = {"type": "image_to_model", "file": {"type": "png", "url": "[OWNER_AUTHORIZED_REFERENCE_URL]"}}
        payload.update({
            "model_version": "v3.1-20260211", "model_seed": request_value.seed,
            "texture": bool(request_value.parameters.get("texture", False)),
            "pbr": bool(request_value.parameters.get("pbr", False)),
            "geometry_quality": request_value.parameters.get("geometry_quality", "standard"),
        })
        return payload

    def _submit_live(self, request_value: GenerationRequest) -> GenerationJob:
        payload = dict(self.request_preview(request_value))
        if request_value.track in {"A", "B"}:
            input_url = request_value.parameters.get("input_url")
            input_urls = request_value.parameters.get("input_urls")
            if request_value.track == "A" and isinstance(input_url, str):
                payload["file"] = {"type": "png", "url": input_url}
            elif request_value.track == "B" and isinstance(input_urls, list) and all(isinstance(item, str) for item in input_urls):
                payload["files"] = [{"type": "png", "url": item} for item in input_urls]
            else:
                raise ValueError("Authorized Tripo execution requires owner-supplied HTTPS input_url/input_urls.")
        response = self._request_json("POST", f"{self.base_url}/task", payload)
        data = response.get("data", response)
        task_id = str(data.get("task_id", "")) if isinstance(data, dict) else ""
        if not task_id:
            raise RuntimeError("Tripo response did not include task_id.")
        return GenerationJob("tripo", task_id, "SUBMITTED", request_value, {"provider_status": "submitted"})

    def _poll_live(self, job: GenerationJob) -> GenerationJob:
        response = self._request_json("GET", f"{self.base_url}/task/{job.task_id}", None)
        data = response.get("data", {})
        status = str(data.get("status", "unknown")) if isinstance(data, dict) else "unknown"
        job.metadata.update({"provider_status": status, "progress": data.get("progress"), "consumed_credits": data.get("consumed_credit")})
        job.status = {"success": "PASS", "failed": "PROVIDER_ERROR", "cancelled": "NOT_RUN", "expired": "TIMEOUT"}.get(status, "RUNNING")
        output = data.get("output", {}) if isinstance(data, dict) else {}
        if isinstance(output, dict) and isinstance(output.get("model"), str):
            job.metadata["artifact_url"] = output["model"]
        return job

    def _cancel_live(self, job: GenerationJob) -> GenerationJob:
        job.error_class = "CANCELLATION_NOT_DOCUMENTED"
        job.error_message = "The pinned public task documentation does not expose a cancellation endpoint."
        return job

    def _retrieve_live(self, job: GenerationJob, output_directory: Path) -> GenerationJob:
        url = job.metadata.get("artifact_url")
        if not isinstance(url, str):
            raise RuntimeError("Tripo artifact URL is unavailable; poll the successful job first.")
        job.artifact_path = self._download(url, output_directory / f"{job.task_id}.glb")
        return job
