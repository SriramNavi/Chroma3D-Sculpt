"""Small explicit Sprint 7 provider registry."""

from __future__ import annotations

from typing import Any

from .openai_provider import OpenAIProvider


_providers: dict[str, Any] = {"openai": OpenAIProvider()}


def register_provider(provider_id: str, provider: Any, *, replace: bool = False) -> None:
    if not provider_id or provider_id in _providers and not replace:
        raise ValueError("Provider ID is invalid or already registered.")
    _providers[provider_id] = provider


def unregister_provider(provider_id: str) -> None:
    if provider_id == "openai":
        raise ValueError("The built-in OpenAI provider cannot be unregistered.")
    _providers.pop(provider_id, None)


def provider_for(provider_id: str) -> Any:
    try:
        return _providers[provider_id]
    except KeyError as exc:
        raise KeyError(f"Unknown AI provider: {provider_id}") from exc


def available_provider_ids() -> tuple[str, ...]:
    return tuple(sorted(_providers))


def reset_test_providers() -> None:
    for provider_id in tuple(_providers):
        if provider_id != "openai":
            _providers.pop(provider_id, None)


__all__ = ("available_provider_ids", "provider_for", "register_provider", "reset_test_providers", "unregister_provider")
