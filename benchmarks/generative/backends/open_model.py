"""Hardware and checkpoint detection shared by open-model adapters."""

from __future__ import annotations

from decimal import Decimal
import importlib.util
import os
from pathlib import Path
import platform
import shutil
import subprocess
from typing import Any

from .base import BenchmarkPolicyError, CostEstimate, GenerationBackend, GenerationJob, GenerationRequest


def nvidia_inventory() -> dict[str, Any]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return {"available": False, "gpus": []}
    completed = subprocess.run(
        [executable, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10, check=False,
    )
    rows = []
    if completed.returncode == 0:
        for line in completed.stdout.splitlines():
            parts = [item.strip() for item in line.split(",")]
            if len(parts) == 3 and parts[1].isdigit():
                rows.append({"name": parts[0], "vram_mib": int(parts[1]), "driver": parts[2]})
    return {"available": completed.returncode == 0, "gpus": rows}


class OpenModelBackend(GenerationBackend):
    module_name = ""
    checkpoint_env = ""
    minimum_vram_mib = 0
    supported_systems: tuple[str, ...] = ()

    def validate_environment(self) -> dict[str, Any]:
        inventory = nvidia_inventory()
        system = platform.system()
        checkpoint_raw = os.environ.get(self.checkpoint_env, "")
        checkpoint_present = bool(checkpoint_raw and Path(checkpoint_raw).is_file())
        package_present = bool(self.module_name and importlib.util.find_spec(self.module_name))
        maximum_vram = max((int(item["vram_mib"]) for item in inventory["gpus"]), default=0)
        if self.supported_systems and system not in self.supported_systems:
            state, feasibility = "UNSUPPORTED_PLATFORM", "LOCAL_NOT_FEASIBLE"
        elif maximum_vram and maximum_vram < self.minimum_vram_mib:
            state, feasibility = "INSUFFICIENT_HARDWARE", "LOCAL_NOT_FEASIBLE"
        elif not package_present:
            state, feasibility = "NOT_INSTALLED", "LOCAL_POSSIBLE_WITH_LIMITATIONS"
        elif not checkpoint_present:
            state, feasibility = "WEIGHTS_NOT_PRESENT", "LOCAL_POSSIBLE_WITH_LIMITATIONS"
        else:
            state, feasibility = "READY_LOCAL", "LOCAL_READY"
        return {
            **self.base_environment(), "availability_state": state, "feasibility": feasibility,
            "runtime_package_present": package_present, "checkpoint_present": checkpoint_present,
            "checkpoint_path_disclosed": False, "gpu": inventory,
            "minimum_vram_mib": self.minimum_vram_mib,
        }

    def estimate_cost(self, request: GenerationRequest) -> CostEstimate:
        request.validate()
        return CostEstimate("KNOWN", Decimal("0"), None, "Local compute; electricity not priced by CGB v0.1")

    def submit(self, request: GenerationRequest, output_directory: Path) -> GenerationJob:
        request.validate()
        unsupported = self.unsupported_track_job(request)
        if unsupported is not None:
            return unsupported
        descriptor = self.backend_info()
        environment = self.validate_environment()
        if request.dry_run:
            return GenerationJob(descriptor.backend_id, "dry-run", "PASS", request, {"dry_run": True, "environment": environment})
        if environment["availability_state"] != "READY_LOCAL":
            state = str(environment["availability_state"])
            failure = "INSUFFICIENT_HARDWARE" if state in {"INSUFFICIENT_HARDWARE", "UNSUPPORTED_PLATFORM"} else "MODEL_NOT_INSTALLED"
            raise BenchmarkPolicyError(failure, f"{descriptor.backend_id} is not locally ready: {state}")
        raise BenchmarkPolicyError("MODEL_NOT_INSTALLED", "G0 adapter validation is implemented; model inference is not installed in this checkout.")

    def poll(self, job: GenerationJob) -> GenerationJob:
        return job

    def cancel(self, job: GenerationJob) -> GenerationJob:
        return job

    def retrieve(self, job: GenerationJob, output_directory: Path) -> GenerationJob:
        return job
