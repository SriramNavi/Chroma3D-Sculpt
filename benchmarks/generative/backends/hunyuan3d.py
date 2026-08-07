"""Benchmark-only Hunyuan3D-2.1 adapter; never downloads weights implicitly."""

from __future__ import annotations

from .base import BackendDescriptor
from .open_model import OpenModelBackend


class Hunyuan3DBackend(OpenModelBackend):
    adapter_version = "1.0.0"
    module_name = "hy3dshape"
    checkpoint_env = "G0_HUNYUAN3D_CHECKPOINT"
    minimum_vram_mib = 10 * 1024
    supported_systems = ("Windows", "Linux", "Darwin")

    def backend_info(self) -> BackendDescriptor:
        return BackendDescriptor(
            backend_id="hunyuan3d_2_1", provider="Tencent Hunyuan", model_version="Hunyuan3D-2.1",
            backend_type="OPEN_LOCAL", supported_input_modes=("image",), supported_output_formats=("glb", "obj"),
            supports_texture=True, supports_pbr=True, supports_multiview=False, supports_seed=False,
            supports_text=False, supports_image=True, supports_local=True, supports_remote=False,
            license_id="Tencent Hunyuan 3D 2.1 Community License", training_code_available=True,
            weights_available=True, min_vram_documented="10 GB shape; 21 GB texture; 29 GB combined",
            request_cost_model={"state": "KNOWN", "usd_per_job": "0", "scope": "local compute only"},
            enabled=True, availability_state="INSUFFICIENT_HARDWARE",
            provenance="Official repository checked 2026-08-07; full weights/training code and PBR pipeline are published; license has territory/use restrictions.",
            official_sources=(
                {"title": "Tencent Hunyuan3D-2.1", "url": "https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1"},
                {"title": "Tencent Hunyuan3D-2.1 license", "url": "https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/main/LICENSE"},
            ),
        )
