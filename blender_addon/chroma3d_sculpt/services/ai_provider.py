"""Vendor-neutral provider contract for Sprint 7."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from ..models.ai_assistance_models import ContextManifest, ProviderSettings
from .provider_transport import CancellationToken


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    provider_id: str
    structured_json: bool
    synchronous: bool
    cancellation: str
    retention_statement: str
    usage_reporting: str
    destination: str
    data_categories: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PreparedProviderRequest:
    request_id: str
    provider_id: str
    model_id: str
    canonical_body: bytes
    request_hash: str
    context_hash: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProviderInvocationResult:
    request_id: str
    response_text: str
    raw_response_hash: str
    response_bytes: int
    provider_request_id: str
    usage: Mapping[str, Any]
    status: str = "COMPLETED"


class AIProvider(Protocol):
    def capabilities(self) -> ProviderCapabilities: ...

    def validate_configuration(self, settings: ProviderSettings) -> None: ...

    def prepare(self, context: ContextManifest, settings: ProviderSettings) -> PreparedProviderRequest: ...

    def invoke(
        self,
        request: PreparedProviderRequest,
        settings: ProviderSettings,
        *,
        key: str,
        cancellation: CancellationToken | None = None,
    ) -> ProviderInvocationResult: ...

    def cancel(self, cancellation: CancellationToken) -> bool: ...


__all__ = (
    "AIProvider", "PreparedProviderRequest", "ProviderCapabilities", "ProviderInvocationResult",
)
