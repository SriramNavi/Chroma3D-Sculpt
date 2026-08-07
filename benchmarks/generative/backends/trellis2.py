"""Benchmark-only TRELLIS.2 adapter; never downloads weights implicitly."""

from __future__ import annotations

from .base import BackendDescriptor
from .open_model import OpenModelBackend


class Trellis2Backend(OpenModelBackend):
    adapter_version = "1.0.0"
    module_name = "trellis2"
    checkpoint_env = "G0_TRELLIS2_CHECKPOINT"
    minimum_vram_mib = 24 * 1024
    supported_systems = ("Linux",)

    def backend_info(self) -> BackendDescriptor:
        return BackendDescriptor(
            backend_id="trellis2", provider="Microsoft", model_version="microsoft/TRELLIS.2-4B",
            backend_type="OPEN_LOCAL", supported_input_modes=("image",), supported_output_formats=("glb",),
            supports_texture=True, supports_pbr=True, supports_multiview=False, supports_seed=False,
            supports_text=False, supports_image=True, supports_local=True, supports_remote=False,
            license_id="MIT", training_code_available=True, weights_available=True,
            min_vram_documented=">=24 GB NVIDIA GPU; Linux tested", request_cost_model={"state": "KNOWN", "usd_per_job": "0", "scope": "local compute only"},
            enabled=True, availability_state="INSUFFICIENT_HARDWARE",
            provenance="Official repository checked 2026-08-07; 4B image-to-3D model, PBR GLB export, MIT code/model.",
            official_sources=(
                {"title": "Microsoft TRELLIS.2", "url": "https://github.com/microsoft/TRELLIS.2"},
                {"title": "TRELLIS.2 training entry point", "url": "https://github.com/microsoft/TRELLIS.2/blob/main/train.py"},
            ),
        )
