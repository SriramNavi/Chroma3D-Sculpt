"""Fail-closed bounded JSON decoding for untrusted provider output."""

from __future__ import annotations

import json
from typing import Any


class RecommendationDecodeError(ValueError):
    pass


def _reject_constant(value: str) -> None:
    raise RecommendationDecodeError(f"Non-finite JSON number is prohibited: {value}.")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RecommendationDecodeError(f"Duplicate JSON field is prohibited: {key}.")
        result[key] = value
    return result


def _measure(value: Any, *, maximum_depth: int, maximum_nodes: int, maximum_string: int) -> int:
    nodes = 0
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > maximum_nodes:
            raise RecommendationDecodeError("Provider JSON exceeds the node limit.")
        if depth > maximum_depth:
            raise RecommendationDecodeError("Provider JSON exceeds the nesting-depth limit.")
        if isinstance(item, str):
            if len(item) > maximum_string or any(ord(char) < 32 and char not in "\n\r\t" for char in item):
                raise RecommendationDecodeError("Provider JSON contains an oversized or prohibited string.")
        elif isinstance(item, dict):
            stack.extend((key, depth + 1) for key in item)
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
    return nodes


def decode_recommendation_json(
    value: bytes | str,
    *,
    maximum_bytes: int,
    maximum_depth: int,
    maximum_nodes: int = 16_384,
    maximum_string: int = 16_384,
) -> dict[str, Any]:
    if isinstance(maximum_bytes, bool) or not 1 <= maximum_bytes <= 1_048_576:
        raise ValueError("maximum_bytes is invalid.")
    if isinstance(value, str):
        try:
            encoded = value.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise RecommendationDecodeError("Provider output contains invalid Unicode.") from exc
    elif isinstance(value, bytes):
        encoded = value
    else:
        raise RecommendationDecodeError("Provider output must be bytes or text.")
    if len(encoded) > maximum_bytes:
        raise RecommendationDecodeError("Provider output exceeds the byte limit.")
    if encoded.startswith(b"\xef\xbb\xbf"):
        raise RecommendationDecodeError("A UTF-8 BOM is prohibited.")
    try:
        text = encoded.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise RecommendationDecodeError("Provider output is not strict UTF-8.") from exc
    stripped = text.strip()
    if not stripped.startswith("{") or not stripped.endswith("}") or "```" in stripped:
        raise RecommendationDecodeError("Provider output must contain exactly one JSON object and no prose or fences.")
    decoder = json.JSONDecoder(object_pairs_hook=_pairs, parse_constant=_reject_constant)
    try:
        parsed, end = decoder.raw_decode(stripped)
    except RecommendationDecodeError:
        raise
    except json.JSONDecodeError as exc:
        raise RecommendationDecodeError("Provider output is not valid JSON.") from exc
    if stripped[end:].strip():
        raise RecommendationDecodeError("Trailing data after the provider JSON object is prohibited.")
    if not isinstance(parsed, dict):
        raise RecommendationDecodeError("Provider output root must be an object.")
    _measure(parsed, maximum_depth=maximum_depth, maximum_nodes=maximum_nodes, maximum_string=maximum_string)
    return parsed


__all__ = ("RecommendationDecodeError", "decode_recommendation_json")
