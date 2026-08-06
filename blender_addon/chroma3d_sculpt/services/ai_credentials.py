"""Ephemeral BYOK credential boundary for Sprint 7.

The key value is held only in this module's process memory or read from the
environment at the instant of an explicit request.  Only redacted state leaves
this module.
"""

from __future__ import annotations

import os
from typing import Mapping


ENVIRONMENT_VARIABLE = "OPENAI_API_KEY"
_session_key: str | None = None


def _validate_key(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("The session key must be text.")
    clean = value.strip()
    if not 8 <= len(clean) <= 512 or any(ord(char) < 33 or ord(char) > 126 for char in clean):
        raise ValueError("The session key format is invalid.")
    return clean


def set_session_key(value: str) -> None:
    global _session_key
    _session_key = _validate_key(value)


def clear_session_key() -> None:
    global _session_key
    _session_key = None


def resolve_key(environment: Mapping[str, str] | None = None) -> tuple[str | None, str]:
    if _session_key is not None:
        return _session_key, "SESSION"
    source = os.environ if environment is None else environment
    value = source.get(ENVIRONMENT_VARIABLE, "")
    if value:
        return _validate_key(value), "ENVIRONMENT"
    return None, "NOT_CONFIGURED"


def credential_status(environment: Mapping[str, str] | None = None) -> dict[str, str | bool]:
    value, source = resolve_key(environment)
    return {
        "configured": value is not None,
        "source": source,
        "masked_suffix": "",
        "persistence": "SESSION_ONLY" if source == "SESSION" else ("PROCESS_ENVIRONMENT" if source == "ENVIRONMENT" else "NONE"),
    }


__all__ = (
    "ENVIRONMENT_VARIABLE", "clear_session_key", "credential_status", "resolve_key", "set_session_key",
)
