"""Advisory current-orientation build-volume and uniform-scale evaluation."""

from __future__ import annotations

from time import perf_counter

from ..models.printability_models import (
    PrintabilityConfidence,
    PrintabilityStatus,
    PrinterProfile,
    ScaleEvaluation,
    ThinFeatureResult,
    WallThicknessResult,
)
from ..printability_settings import PrintabilitySettings
from .geometry_facts import GeometryContext


def evaluate_scale_and_volume(
    context: GeometryContext,
    profile: PrinterProfile,
    settings: PrintabilitySettings,
    wall: WallThicknessResult | None = None,
    features: ThinFeatureResult | None = None,
) -> ScaleEvaluation:
    started = perf_counter()
    dimensions = context.facts.dimensions_mm
    build = profile.build_volume_mm.dimensions
    margin = profile.dimensional_safety_margin_mm.value
    usable = tuple(max(value - margin, 0.0) for value in build)
    tolerance = settings.exact_boundary_tolerance_mm
    axis_fit = tuple(model <= available + tolerance for model, available in zip(dimensions, usable))
    overflow = tuple(max(model - available, 0.0) for model, available in zip(dimensions, usable))
    ratios = [available / model for model, available in zip(dimensions, usable) if model > tolerance]
    maximum_scale = min(ratios, default=0.0) * 100.0
    required_scale = min(100.0, maximum_scale)
    warnings: list[str] = []
    scale_factor = required_scale / 100.0
    if scale_factor < 1.0 and wall is not None and wall.minimum_sampled_thickness_mm is not None:
        scaled_wall = wall.minimum_sampled_thickness_mm * scale_factor
        if scaled_wall <= profile.wall_thickness_warning_mm.value:
            warnings.append("Scaling down to fit may move sampled wall thickness below the configured warning threshold.")
    if scale_factor < 1.0 and features is not None and features.minimum_diameter_mm is not None:
        scaled_feature = features.minimum_diameter_mm * scale_factor
        if scaled_feature <= profile.minimum_feature_warning_mm.value:
            warnings.append("Scaling down to fit may move the experimental minimum-feature estimate below the configured warning threshold.")
    overall = all(axis_fit)
    return ScaleEvaluation(
        status=PrintabilityStatus.PASS if overall else PrintabilityStatus.WARNING,
        confidence=PrintabilityConfidence.HIGH,
        current_dimensions_mm=dimensions,
        profile_build_volume_mm=build,
        usable_build_volume_mm=usable,
        axis_fit=axis_fit,  # type: ignore[arg-type]
        overflow_mm=overflow,  # type: ignore[arg-type]
        overall_fit=overall,
        maximum_uniform_fit_scale_percent=maximum_scale,
        required_scale_percent=required_scale,
        consequence_warnings=tuple(warnings),
        duration_seconds=perf_counter() - started,
        limitations=(
            "Fit is a rectangular current-orientation comparison against the profile volume minus its configured margin.",
            "Scale is advisory arithmetic only; no object transform is changed and slicer behavior is not evaluated.",
        ),
    )
