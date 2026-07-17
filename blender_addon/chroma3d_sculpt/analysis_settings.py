"""Central Sprint 1 diagnostic thresholds and printer profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .metadata import DISPLAY_VERSION
from .models.analysis_result import AnalysisProfile, AnalysisSettingsSnapshot, PrinterProfile


BAMBU_X1_CARBON_BUILD_MM = (256.0, 256.0, 256.0)
BUILD_VOLUME_TOLERANCE_MM = 1e-4


@dataclass(frozen=True, slots=True)
class AnalysisSettings:
    profile: AnalysisProfile = AnalysisProfile.STANDARD
    duplicate_position_tolerance: float = 1e-6
    duplicate_vertex_limit: int = 500_000
    degenerate_edge_tolerance: float = 1e-9
    degenerate_face_tolerance: float = 1e-18
    tiny_shell_max_face_count: int = 12
    tiny_shell_max_volume_mm3: float = 1000.0
    tiny_shell_max_relative_volume_percent: float = 0.5
    tiny_shell_max_diagonal_mm: float = 10.0
    maximum_stored_issue_indices: int = 10_000
    self_intersection_triangle_limit: int = 50_000
    maximum_stored_self_intersection_pairs: int = 10_000
    containment_shell_limit: int = 64
    containment_triangle_limit: int = 100_000
    printer_profile: PrinterProfile = PrinterProfile.NONE
    custom_build_volume_mm: tuple[float, float, float] = (256.0, 256.0, 256.0)

    def build_volume_mm(self) -> tuple[float, float, float] | None:
        if self.printer_profile == PrinterProfile.BAMBU_X1_CARBON:
            return BAMBU_X1_CARBON_BUILD_MM
        if self.printer_profile == PrinterProfile.CUSTOM:
            return tuple(max(float(value), 0.001) for value in self.custom_build_volume_mm)
        return None

    def snapshot(self, blender_version: str) -> AnalysisSettingsSnapshot:
        return AnalysisSettingsSnapshot(
            analysis_profile=self.profile,
            duplicate_position_tolerance=self.duplicate_position_tolerance,
            duplicate_vertex_limit=self.duplicate_vertex_limit,
            degenerate_edge_tolerance=self.degenerate_edge_tolerance,
            degenerate_face_tolerance=self.degenerate_face_tolerance,
            tiny_shell_max_face_count=self.tiny_shell_max_face_count,
            tiny_shell_max_volume_mm3=self.tiny_shell_max_volume_mm3,
            tiny_shell_max_relative_volume_percent=self.tiny_shell_max_relative_volume_percent,
            tiny_shell_max_diagonal_mm=self.tiny_shell_max_diagonal_mm,
            maximum_stored_issue_indices=self.maximum_stored_issue_indices,
            self_intersection_triangle_limit=self.self_intersection_triangle_limit,
            maximum_stored_self_intersection_pairs=self.maximum_stored_self_intersection_pairs,
            containment_shell_limit=self.containment_shell_limit,
            containment_triangle_limit=self.containment_triangle_limit,
            printer_profile=self.printer_profile,
            build_volume_mm=self.build_volume_mm(),
            extension_version=DISPLAY_VERSION,
            blender_version=blender_version or "Unknown",
        )


def settings_from_property_group(state: Any) -> AnalysisSettings:
    """Build immutable runtime settings from Blender WindowManager properties."""

    return AnalysisSettings(
        profile=AnalysisProfile(str(state.analysis_profile)),
        duplicate_position_tolerance=float(state.duplicate_position_tolerance),
        duplicate_vertex_limit=int(state.duplicate_vertex_limit),
        degenerate_edge_tolerance=float(state.degenerate_edge_tolerance),
        degenerate_face_tolerance=float(state.degenerate_face_tolerance),
        tiny_shell_max_face_count=int(state.tiny_shell_max_face_count),
        tiny_shell_max_volume_mm3=float(state.tiny_shell_max_volume_mm3),
        tiny_shell_max_relative_volume_percent=float(state.tiny_shell_max_relative_volume_percent),
        tiny_shell_max_diagonal_mm=float(state.tiny_shell_max_diagonal_mm),
        maximum_stored_issue_indices=int(state.maximum_stored_issue_indices),
        self_intersection_triangle_limit=int(state.self_intersection_triangle_limit),
        maximum_stored_self_intersection_pairs=int(state.maximum_stored_self_intersection_pairs),
        containment_shell_limit=int(state.containment_shell_limit),
        containment_triangle_limit=int(state.containment_triangle_limit),
        printer_profile=PrinterProfile(str(state.printer_profile)),
        custom_build_volume_mm=(
            float(state.custom_build_width_mm),
            float(state.custom_build_depth_mm),
            float(state.custom_build_height_mm),
        ),
    )
