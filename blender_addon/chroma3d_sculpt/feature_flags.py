"""Explicit, hash-bound Sprint 4 feature flags."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from .metadata import FEATURE_FLAG_SCHEMA_VERSION
from .models.advanced_preparation_models import FeatureFlagSet


FLAG_NAMES = (
    "wall_thickness",
    "thin_features",
    "overhangs",
    "floating_components",
    "build_contact",
    "scale_evaluation",
    "orientation_recommendations",
    "bridge_risk",
    "support_risk",
    "resin_advisory",
    "batch_analysis",
    "baseline_generation",
    "dashboard_generation",
    "experimental_material_modifiers",
)
EXPERIMENTAL_FLAGS = ("resin_advisory", "experimental_material_modifiers")
DEFAULT_FLAGS: dict[str, bool] = {
    "wall_thickness": True,
    "thin_features": True,
    "overhangs": True,
    "floating_components": True,
    "build_contact": True,
    "scale_evaluation": True,
    "orientation_recommendations": True,
    "bridge_risk": True,
    "support_risk": True,
    "resin_advisory": False,
    "batch_analysis": True,
    "baseline_generation": True,
    "dashboard_generation": True,
    "experimental_material_modifiers": False,
}


def build_feature_flags(
    overrides: dict[str, Any] | None = None,
    *,
    allow_experimental: bool = False,
) -> FeatureFlagSet:
    values = dict(DEFAULT_FLAGS)
    supplied = overrides or {}
    unknown = set(supplied) - set(FLAG_NAMES)
    if unknown:
        raise ValueError(f"Unknown feature flag(s): {sorted(unknown)}")
    for name, value in supplied.items():
        if not isinstance(value, bool):
            raise ValueError(f"Feature flag {name!r} must be a boolean.")
        if name in EXPERIMENTAL_FLAGS and value and not allow_experimental:
            raise ValueError(f"Experimental feature flag {name!r} requires explicit user enablement.")
        values[name] = value
    payload = {
        "schema_version": FEATURE_FLAG_SCHEMA_VERSION,
        **values,
        "experimental_flags": EXPERIMENTAL_FLAGS,
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return FeatureFlagSet(**payload, flag_hash=digest)


def flags_from_property_group(state: Any) -> FeatureFlagSet:
    return build_feature_flags(
        {
            "bridge_risk": bool(state.preparation_bridge_risk),
            "support_risk": bool(state.preparation_support_risk),
            "resin_advisory": bool(state.preparation_resin_advisory),
            "baseline_generation": bool(state.preparation_baseline_enabled),
            "experimental_material_modifiers": bool(state.preparation_experimental_modifiers),
        },
        allow_experimental=bool(state.preparation_resin_advisory or state.preparation_experimental_modifiers),
    )
