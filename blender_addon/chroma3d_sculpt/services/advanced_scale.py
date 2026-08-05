"""Material-aware uniform scale intervals without applying object scale."""

from __future__ import annotations

from ..models.advanced_preparation_models import AdvancedScaleRecommendation, ComposedProcessContext, ScaleInterval
from ..models.printability_models import PrintabilityConfidence, PrintabilityResult, PrintabilityStatus


NO_FEASIBLE_RECOMMENDED_SCALE = "NO_FEASIBLE_RECOMMENDED_SCALE"


def recommend_scale(base: PrintabilityResult, process: ComposedProcessContext) -> AdvancedScaleRecommendation:
    fit_maximum = max(0.0, base.scale_evaluation.maximum_uniform_fit_scale_percent)
    wall_minimum = None
    feature_minimum = None
    wall_sample = base.wall_thickness.minimum_sampled_thickness_mm
    feature_sample = base.thin_features.minimum_diameter_mm
    if wall_sample is not None and wall_sample > 0.0:
        wall_minimum = process.effective_thresholds["wall_thickness_warning_mm"] / wall_sample * 100.0
    if feature_sample is not None and feature_sample > 0.0:
        feature_minimum = process.effective_thresholds["minimum_feature_warning_mm"] / feature_sample * 100.0
    lower_values = [value for value in (wall_minimum, feature_minimum) if value is not None]
    minimum = max(lower_values, default=0.0)
    warnings: list[str] = []
    if wall_minimum is None:
        warnings.append("A minimum wall-preserving scale could not be derived from the bounded wall samples.")
    if feature_minimum is None:
        warnings.append("A minimum feature-preserving scale could not be derived from the experimental feature proxy.")
    if minimum > fit_maximum + 1e-9:
        interval = ScaleInterval(None, None, NO_FEASIBLE_RECOMMENDED_SCALE)
        status = PrintabilityStatus.CRITICAL
        warnings.append("Fit and feature-preservation conditions conflict; no feasible recommended scale interval exists.")
    else:
        interval = ScaleInterval(minimum, fit_maximum, "FEASIBLE")
        status = PrintabilityStatus.WARNING if minimum > 100.0 or fit_maximum < 100.0 else PrintabilityStatus.PASS
    samples = sorted({round(value, 6) for value in (minimum, 50.0, 75.0, 100.0, fit_maximum) if value > 0.0 and value <= max(fit_maximum, 100.0)})
    projected: list[dict[str, object]] = []
    current_score = base.score_details.score
    for scale in samples[:8]:
        fit = scale <= fit_maximum + 1e-9
        wall_ok = wall_minimum is None or scale >= wall_minimum - 1e-9
        feature_ok = feature_minimum is None or scale >= feature_minimum - 1e-9
        penalties = (0 if fit else 25) + (0 if wall_ok else 15) + (0 if feature_ok else 15)
        projected.append(
            {
                "scale_percent": scale,
                "projected_score": None if current_score is None else max(0, current_score - penalties),
                "fit": fit, "wall_threshold_preserved": wall_ok, "feature_threshold_preserved": feature_ok,
                "classification": "CONSERVATIVE_ARITHMETIC_PROJECTION",
            }
        )
    return AdvancedScaleRecommendation(
        status=status, confidence=PrintabilityConfidence.LOW if wall_minimum is None or feature_minimum is None else PrintabilityConfidence.MEDIUM,
        maximum_uniform_fit_scale_percent=fit_maximum, minimum_wall_preserving_scale_percent=wall_minimum,
        minimum_feature_preserving_scale_percent=feature_minimum, recommended_interval=interval,
        current_score=current_score, sampled_scale_scores=tuple(projected), warnings=tuple(warnings),
        limitations=(
            "Scale recommendations are uniform mathematical comparisons only; the Blender object and its transform are never changed.",
            "Projected scores do not rerun a slicer, material model, support solution, or physical simulation.",
        ),
    )
