"""Strict CGB backend registry and environment-aware matrix export."""

from __future__ import annotations

from typing import Any

from .base import ExecutionPolicy, GenerationBackend
from .fake import FakeGeneratorBackend
from .hunyuan3d import Hunyuan3DBackend
from .meshy import MeshyBackend
from .rodin import RodinBackend
from .trellis2 import Trellis2Backend
from .tripo import TripoBackend


def backend_registry(policy: ExecutionPolicy | None = None) -> dict[str, GenerationBackend]:
    effective = policy or ExecutionPolicy.from_environment()
    backends: tuple[GenerationBackend, ...] = (
        Trellis2Backend(effective), Hunyuan3DBackend(effective), TripoBackend(effective),
        MeshyBackend(effective), RodinBackend(effective), FakeGeneratorBackend(effective),
    )
    registry: dict[str, GenerationBackend] = {}
    for backend in backends:
        descriptor = backend.backend_info()
        descriptor.validate()
        if descriptor.backend_id in registry:
            raise ValueError(f"Duplicate backend_id: {descriptor.backend_id}")
        registry[descriptor.backend_id] = backend
    return registry


def registry_matrix(policy: ExecutionPolicy | None = None) -> list[dict[str, Any]]:
    rows = []
    for backend_id, backend in backend_registry(policy).items():
        descriptor = backend.backend_info().to_dict()
        environment = dict(backend.validate_environment())
        descriptor["availability_state"] = environment["availability_state"]
        descriptor["environment"] = environment
        rows.append(descriptor)
    return rows
