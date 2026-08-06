"""Central, validated Sprint 4 performance policy with no algorithm-local caps."""

from __future__ import annotations

from .metadata import PERFORMANCE_REGISTRY_VERSION
from .models.advanced_preparation_models import PerformanceLimit
from .models.printability_models import PrintabilityMode


SIZE_CLASS_LIMITS = (
    ("Tiny", 10_000),
    ("Small", 50_000),
    ("Medium", 250_000),
    ("Large", 500_000),
    ("Huge", 1_000_000),
    ("Extreme", 2**63 - 1),
)
CHECK_TYPES = (
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
    "optimization_candidate_generation",
    "optimization_comparison",
    "optimization_checkpoint",
    "optimization_operation",
    "intelligent_strategy_generation",
    "intelligent_constraint_evaluation",
    "intelligent_virtual_evaluation",
    "intelligent_workspace_evaluation",
    "intelligent_pareto_construction",
    "intelligent_ranking",
    "intelligent_explanation",
    "intelligent_history",
    "intelligent_export",
)

OPTIMIZATION_PERFORMANCE_LIMITS = {
    "candidate_generation_seconds": 30.0,
    "comparison_seconds": 120.0,
    "checkpoint_count": 4,
    "operation_count": 8,
    "evidence_items": 256,
}

# Sprint 6 search limits are centralized here so no strategy service can
# silently widen the bounded search envelope.
INTELLIGENT_OPTIMIZATION_LIMITS = {
    "FAST": {
        "max_generated_strategies": 12, "max_evaluated_strategies": 8, "max_workspace_previews": 1,
        "max_strategy_depth": 2, "max_branch_factor": 4, "max_pareto_points": 8,
        "max_wall_time_seconds": 10.0, "max_per_strategy_seconds": 2.0, "max_memory_observation_mb": 512.0,
    },
    "STANDARD": {
        "max_generated_strategies": 32, "max_evaluated_strategies": 16, "max_workspace_previews": 2,
        "max_strategy_depth": 3, "max_branch_factor": 6, "max_pareto_points": 16,
        "max_wall_time_seconds": 30.0, "max_per_strategy_seconds": 5.0, "max_memory_observation_mb": 512.0,
    },
    "DEEP": {
        "max_generated_strategies": 96, "max_evaluated_strategies": 64, "max_workspace_previews": 4,
        "max_strategy_depth": 5, "max_branch_factor": 10, "max_pareto_points": 32,
        "max_wall_time_seconds": 90.0, "max_per_strategy_seconds": 8.0, "max_memory_observation_mb": 1024.0,
    },
}

# Sprint 7 consumes summaries only and exports zero geometry.  These values are
# compiled maxima from docs/sprint7/PERFORMANCE_POLICY.md; provider and local
# phase measurements remain separate.
AI_ASSISTANCE_LIMITS = {
    "FAST": {
        "context_bytes": 32 * 1024, "intent_bytes": 2 * 1024, "response_bytes": 64 * 1024,
        "recommendations": 4, "evidence_links": 64, "json_depth": 16,
        "local_wall_seconds": 5.0, "provider_timeout_seconds": 15.0,
        "automatic_retries": 0, "explicit_retries": 1, "report_bytes": 512 * 1024,
        "geometry_elements_exported": 0,
    },
    "STANDARD": {
        "context_bytes": 128 * 1024, "intent_bytes": 4 * 1024, "response_bytes": 256 * 1024,
        "recommendations": 8, "evidence_links": 256, "json_depth": 20,
        "local_wall_seconds": 15.0, "provider_timeout_seconds": 45.0,
        "automatic_retries": 0, "explicit_retries": 1, "report_bytes": 1024 * 1024,
        "geometry_elements_exported": 0,
    },
    "DEEP": {
        "context_bytes": 512 * 1024, "intent_bytes": 8 * 1024, "response_bytes": 512 * 1024,
        "recommendations": 16, "evidence_links": 1024, "json_depth": 24,
        "local_wall_seconds": 45.0, "provider_timeout_seconds": 120.0,
        "automatic_retries": 0, "explicit_retries": 1, "report_bytes": 2 * 1024 * 1024,
        "geometry_elements_exported": 0,
    },
}

_MODE_BASE = {
    PrintabilityMode.FAST: dict(triangles=100_000, samples=256, candidates=4, evidence=256, batch=16, warning=15.0, memory="LOW"),
    PrintabilityMode.STANDARD: dict(triangles=500_000, samples=2_048, candidates=8, evidence=2_048, batch=32, warning=45.0, memory="MEDIUM"),
    PrintabilityMode.DEEP: dict(triangles=1_000_000, samples=16_384, candidates=12, evidence=10_000, batch=64, warning=120.0, memory="HIGH"),
}
_CHECK_FACTORS = {
    "wall_thickness": 1.0,
    "thin_features": 1.0,
    "overhangs": 2.0,
    "floating_components": 2.0,
    "build_contact": 2.0,
    "scale_evaluation": 2.0,
    "orientation_recommendations": 1.0,
    "bridge_risk": 1.0,
    "support_risk": 1.0,
    "resin_advisory": 1.0,
    "batch_analysis": 1.0,
    "optimization_candidate_generation": 1.0,
    "optimization_comparison": 1.0,
    "optimization_checkpoint": 1.0,
    "optimization_operation": 1.0,
    "intelligent_strategy_generation": 1.0,
    "intelligent_constraint_evaluation": 1.0,
    "intelligent_virtual_evaluation": 1.0,
    "intelligent_workspace_evaluation": 2.0,
    "intelligent_pareto_construction": 1.0,
    "intelligent_ranking": 1.0,
    "intelligent_explanation": 1.0,
    "intelligent_history": 1.0,
    "intelligent_export": 1.0,
}
_SIZE_FACTORS = {"Tiny": 1.0, "Small": 1.0, "Medium": 1.0, "Large": 0.75, "Huge": 0.5, "Extreme": 0.25}


def size_class_for(triangle_count: int) -> str:
    if isinstance(triangle_count, bool) or not isinstance(triangle_count, int) or triangle_count < 0:
        raise ValueError("triangle_count must be a non-negative integer.")
    return next(name for name, upper in SIZE_CLASS_LIMITS if triangle_count <= upper)


def _build_registry() -> dict[tuple[PrintabilityMode, str, str], PerformanceLimit]:
    registry: dict[tuple[PrintabilityMode, str, str], PerformanceLimit] = {}
    for mode, base in _MODE_BASE.items():
        for size_class, _upper in SIZE_CLASS_LIMITS:
            size_factor = _SIZE_FACTORS[size_class]
            for check_type in CHECK_TYPES:
                factor = _CHECK_FACTORS[check_type]
                triangles = max(1, int(base["triangles"] * factor))
                registry[(mode, size_class, check_type)] = PerformanceLimit(
                    mode=mode,
                    size_class=size_class,
                    check_type=check_type,
                    maximum_triangles=triangles,
                    maximum_samples=max(1, int(base["samples"] * size_factor)),
                    maximum_candidate_count=max(1, int(base["candidates"] * size_factor)),
                    maximum_region_evidence=max(1, int(base["evidence"] * size_factor)),
                    maximum_batch_size=int(base["batch"]),
                    recommended_warning_time_seconds=float(base["warning"]),
                    hard_skip_limit=triangles,
                    expected_memory_class=str(base["memory"]),
                )
    return registry


REGISTRY = _build_registry()


def validate_registry() -> None:
    expected = len(PrintabilityMode) * len(SIZE_CLASS_LIMITS) * len(CHECK_TYPES)
    if len(REGISTRY) != expected:
        raise ValueError("Performance registry is incomplete or contains duplicate keys.")
    for key, item in REGISTRY.items():
        if key != (item.mode, item.size_class, item.check_type):
            raise ValueError("Performance registry key does not match its value.")
        integer_values = (
            item.maximum_triangles,
            item.maximum_samples,
            item.maximum_candidate_count,
            item.maximum_region_evidence,
            item.maximum_batch_size,
            item.hard_skip_limit,
        )
        if any(isinstance(value, bool) or value <= 0 for value in integer_values):
            raise ValueError("Performance registry limits must be positive integers.")
        if item.hard_skip_limit < item.maximum_triangles or item.recommended_warning_time_seconds <= 0.0:
            raise ValueError("Performance registry skip/time policy is invalid.")


def limit_for(mode: PrintabilityMode | str, triangle_count: int, check_type: str) -> PerformanceLimit:
    normalized_mode = mode if isinstance(mode, PrintabilityMode) else PrintabilityMode(str(mode))
    if check_type not in CHECK_TYPES:
        raise ValueError(f"Unknown performance check type: {check_type!r}")
    return REGISTRY[(normalized_mode, size_class_for(triangle_count), check_type)]


def limit_for_size(mode: PrintabilityMode | str, size_class: str, check_type: str) -> PerformanceLimit:
    normalized_mode = mode if isinstance(mode, PrintabilityMode) else PrintabilityMode(str(mode))
    try:
        return REGISTRY[(normalized_mode, size_class, check_type)]
    except KeyError as exc:
        raise ValueError("Unsupported performance registry lookup.") from exc


def legacy_mode_limits(mode: PrintabilityMode) -> tuple[int, int, int, int]:
    item = limit_for_size(mode, "Medium", "orientation_recommendations")
    wall = limit_for_size(mode, "Medium", "wall_thickness")
    return (wall.maximum_samples, item.maximum_triangles, item.maximum_candidate_count, item.maximum_region_evidence)


validate_registry()

__all__ = (
    "AI_ASSISTANCE_LIMITS",
    "CHECK_TYPES",
    "INTELLIGENT_OPTIMIZATION_LIMITS",
    "OPTIMIZATION_PERFORMANCE_LIMITS",
    "PERFORMANCE_REGISTRY_VERSION",
    "REGISTRY",
    "SIZE_CLASS_LIMITS",
    "legacy_mode_limits",
    "limit_for",
    "limit_for_size",
    "size_class_for",
    "validate_registry",
)
