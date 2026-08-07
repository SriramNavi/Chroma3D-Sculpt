"""Deterministic no-network provider used only for tests and local validation."""

from __future__ import annotations

from typing import Any, Mapping

from ..models.ai_assistance_models import ContextManifest, ProviderSettings, canonical_json, stable_hash
from .ai_provider import PreparedProviderRequest, ProviderCapabilities, ProviderInvocationResult
from .provider_transport import CancellationToken, TransportError
from ..models.ai_assistance_models import FailureClass


class FakeAIProvider:
    def __init__(self, response: Mapping[str, Any] | str, *, failure: str = "", usage: Mapping[str, Any] | None = None) -> None:
        self.response = response
        self.failure = failure
        self.usage = dict(usage or {})
        self.invocation_count = 0

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities("fake", True, True, "SUPPORTED", "No retention; deterministic in-process fixture.", "FIXTURE", "local-test-adapter", ("SYNTHETIC_CONTEXT",))

    def validate_configuration(self, settings: ProviderSettings) -> None:
        if settings.provider_id != "fake":
            raise ValueError("Fake adapter requires provider_id='fake'.")

    def prepare(self, context: ContextManifest, settings: ProviderSettings) -> PreparedProviderRequest:
        self.validate_configuration(settings)
        if not context.consent.approved:
            raise ValueError("Consent is required for fake-provider contract parity.")
        body = canonical_json({"context_hash": context.context_hash, "fixture": True}).encode("utf-8")
        return PreparedProviderRequest("fake-request", "fake", settings.model_id, body, stable_hash(body.decode("utf-8")), context.context_hash, {"network": False})

    def invoke(self, request: PreparedProviderRequest, settings: ProviderSettings, *, key: str, cancellation: CancellationToken | None = None) -> ProviderInvocationResult:
        self.validate_configuration(settings)
        self.invocation_count += 1
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        if self.failure == "TIMEOUT":
            raise TransportError(FailureClass.TIMEOUT, "Fake provider timed out.")
        if self.failure:
            raise TransportError(FailureClass.PROVIDER, "Fake provider failed.")
        text = self.response if isinstance(self.response, str) else canonical_json(self.response)
        encoded = text.encode("utf-8")
        if len(encoded) > settings.maximum_output_bytes:
            raise TransportError(FailureClass.RESPONSE_LIMIT, "Fake provider response exceeds limit.")
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        return ProviderInvocationResult(request.request_id, text, stable_hash(text), len(encoded), "fake-provider-request", {"classification": "FIXTURE", **self.usage})

    def cancel(self, cancellation: CancellationToken) -> bool:
        cancellation.cancel()
        return True


__all__ = ("FakeAIProvider",)
