"""Deterministic allow-list redaction for Sprint 7 request context."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Mapping

from ..models.ai_assistance_models import plain_value


_SECRET_PATTERN = re.compile(r"(?i)(?:sk-[A-Za-z0-9_-]{8,}|bearer\s+[A-Za-z0-9._-]{8,}|api[_ -]?key\s*[:=]\s*\S+)")
_WINDOWS_PATH = re.compile(r"(?i)(?:[a-z]:[\\/]|\\\\)[^\s\"'<>|?*]+")
_POSIX_HOME = re.compile(r"(?i)/(?:home|users)/[^/\s]+(?:/[^\s\"']*)?")
_URL = re.compile(r"(?i)\b(?:https?|file|ftp)://\S+")
_FORBIDDEN_KEYS = {
    "api_key", "authorization", "credential", "credentials", "password", "secret", "token",
    "vertices", "edges", "faces", "polygons", "loops", "coordinates", "geometry", "raw_geometry",
    "blend_file", "file_contents", "screenshot", "source_code", "logs", "custom_properties",
}


def sanitize_text(value: str, *, maximum: int, label: str = "text") -> tuple[str, tuple[str, ...]]:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text.")
    reasons: list[str] = []
    clean = "".join(char for char in value if unicodedata.category(char) not in {"Cc", "Cf"} or char in "\n\t")
    if clean != value:
        reasons.append("CONTROL_CHARACTERS_REMOVED")
    for pattern, replacement, reason in (
        (_SECRET_PATTERN, "[REDACTED_SECRET]", "SECRET_REDACTED"),
        (_WINDOWS_PATH, "[REDACTED_PATH]", "PATH_REDACTED"),
        (_POSIX_HOME, "[REDACTED_PATH]", "PATH_REDACTED"),
        (_URL, "[REDACTED_URL]", "URL_REDACTED"),
    ):
        updated = pattern.sub(replacement, clean)
        if updated != clean:
            reasons.append(reason)
        clean = updated
    encoded = clean.encode("utf-8")
    if len(encoded) > maximum:
        encoded = encoded[:maximum]
        while True:
            try:
                clean = encoded.decode("utf-8")
                break
            except UnicodeDecodeError:
                encoded = encoded[:-1]
        reasons.append("TRUNCATED")
    return clean, tuple(dict.fromkeys(reasons))


def safe_display_name(value: str) -> tuple[str, tuple[str, ...]]:
    clean, reasons = sanitize_text(value, maximum=128, label="display name")
    clean = re.sub(r"\s+", " ", clean).strip()
    return (clean or "Selected mesh", reasons)


def assert_allow_list_payload(value: Any, path: str = "context") -> None:
    plain = plain_value(value)

    def walk(item: Any, current: str) -> None:
        if isinstance(item, Mapping):
            for key, nested in item.items():
                lowered = str(key).lower()
                if lowered in _FORBIDDEN_KEYS:
                    raise ValueError(f"{current}.{key} is prohibited from assistance context.")
                walk(nested, f"{current}.{key}")
        elif isinstance(item, list):
            for index, nested in enumerate(item):
                walk(nested, f"{current}[{index}]")
        elif isinstance(item, str):
            if _SECRET_PATTERN.search(item) or _WINDOWS_PATH.search(item) or _POSIX_HOME.search(item) or _URL.search(item):
                raise ValueError(f"{current} contains unredacted secret, path, or URL data.")

    walk(plain, path)


__all__ = ("assert_allow_list_payload", "safe_display_name", "sanitize_text")
