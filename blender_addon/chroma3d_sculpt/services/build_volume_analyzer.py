"""Current-orientation rectangular printer build-volume evaluation."""

from __future__ import annotations

from ..analysis_settings import AnalysisSettings, BUILD_VOLUME_TOLERANCE_MM
from ..models.analysis_result import BuildVolumeFitState, BuildVolumeMetrics, EvaluationStatus


def evaluate_build_volume(
    model_dimensions_mm: tuple[float, float, float],
    settings: AnalysisSettings,
) -> BuildVolumeMetrics:
    build = settings.build_volume_mm()
    if build is None:
        return BuildVolumeMetrics(
            status=EvaluationStatus.NOT_APPLICABLE,
            fit_state=BuildVolumeFitState.NO_PROFILE,
            printer_profile=settings.printer_profile,
            model_dimensions_mm=model_dimensions_mm,
            message="No printer build-volume profile is selected.",
        )
    fits = tuple(model <= limit + BUILD_VOLUME_TOLERANCE_MM for model, limit in zip(model_dimensions_mm, build))
    excess = tuple(0.0 if axis_fits else max(model - limit, 0.0) for model, limit, axis_fits in zip(model_dimensions_mm, build, fits))
    ratios = [limit / model for model, limit in zip(model_dimensions_mm, build) if model > 0.0]
    overall = all(fits)
    maximum_scale = 100.0 if overall or not ratios else min(ratios) * 100.0
    return BuildVolumeMetrics(
        status=EvaluationStatus.COMPLETED,
        fit_state=BuildVolumeFitState.FITS if overall else BuildVolumeFitState.DOES_NOT_FIT,
        printer_profile=settings.printer_profile,
        model_dimensions_mm=model_dimensions_mm,
        build_dimensions_mm=build,
        fits_x=fits[0],
        fits_y=fits[1],
        fits_z=fits[2],
        overall_fit=overall,
        excess_mm=excess,
        maximum_uniform_scale_percent=maximum_scale,
        current_orientation_only=True,
        message=(
            "Fits configured rectangular build volume in current orientation."
            if overall
            else "Does not fit configured rectangular build volume in current orientation; no rotation or scaling was applied."
        ),
    )
