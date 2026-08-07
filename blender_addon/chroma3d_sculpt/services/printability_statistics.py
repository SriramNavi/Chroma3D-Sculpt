"""Shared deterministic statistics for printability evidence."""

from __future__ import annotations


def percentiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    return {
        label: ordered[min(round((len(ordered) - 1) * fraction), len(ordered) - 1)]
        for label, fraction in (("p05", 0.05), ("p25", 0.25), ("p50", 0.5), ("p75", 0.75), ("p95", 0.95))
    }
