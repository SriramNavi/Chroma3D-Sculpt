"""Central conservative settings for Sprint 2 controlled repairs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models.repair_models import RepairSettingsSnapshot


@dataclass(frozen=True, slots=True)
class RepairSettings:
    merge_distance_mm: float = 0.001
    zero_length_edge_tolerance_mm: float = 0.000001
    degenerate_face_area_tolerance_mm2: float = 0.00000001
    maximum_stored_candidate_indices: int = 10_000
    maximum_repair_checkpoints: int = 3
    small_hole_maximum_edge_count: int = 12
    small_hole_maximum_perimeter_mm: float = 2.0
    small_hole_maximum_diagonal_mm: float = 1.0

    def __post_init__(self) -> None:
        positive = {
            "merge_distance_mm": self.merge_distance_mm,
            "zero_length_edge_tolerance_mm": self.zero_length_edge_tolerance_mm,
            "degenerate_face_area_tolerance_mm2": self.degenerate_face_area_tolerance_mm2,
            "small_hole_maximum_perimeter_mm": self.small_hole_maximum_perimeter_mm,
            "small_hole_maximum_diagonal_mm": self.small_hole_maximum_diagonal_mm,
        }
        for name, value in positive.items():
            if not 0.0 < float(value) < 1_000_000.0:
                raise ValueError(f"{name} must be positive and within a conservative finite range.")
        if not 1 <= self.maximum_stored_candidate_indices <= 100_000:
            raise ValueError("maximum_stored_candidate_indices must be between 1 and 100000.")
        if not 1 <= self.maximum_repair_checkpoints <= 20:
            raise ValueError("maximum_repair_checkpoints must be between 1 and 20.")
        if not 3 <= self.small_hole_maximum_edge_count <= 1_000:
            raise ValueError("small_hole_maximum_edge_count must be between 3 and 1000.")

    def snapshot(self) -> RepairSettingsSnapshot:
        return RepairSettingsSnapshot(
            merge_distance_mm=self.merge_distance_mm,
            zero_length_edge_tolerance_mm=self.zero_length_edge_tolerance_mm,
            degenerate_face_area_tolerance_mm2=self.degenerate_face_area_tolerance_mm2,
            maximum_stored_candidate_indices=self.maximum_stored_candidate_indices,
            maximum_repair_checkpoints=self.maximum_repair_checkpoints,
            small_hole_maximum_edge_count=self.small_hole_maximum_edge_count,
            small_hole_maximum_perimeter_mm=self.small_hole_maximum_perimeter_mm,
            small_hole_maximum_diagonal_mm=self.small_hole_maximum_diagonal_mm,
        )


def settings_from_repair_property_group(state: Any) -> RepairSettings:
    return RepairSettings(
        merge_distance_mm=float(state.repair_merge_distance_mm),
        zero_length_edge_tolerance_mm=float(state.repair_zero_length_tolerance_mm),
        degenerate_face_area_tolerance_mm2=float(state.repair_degenerate_area_tolerance_mm2),
        maximum_stored_candidate_indices=int(state.repair_candidate_index_cap),
        maximum_repair_checkpoints=int(state.repair_checkpoint_depth),
        small_hole_maximum_edge_count=int(state.repair_hole_max_edges),
        small_hole_maximum_perimeter_mm=float(state.repair_hole_max_perimeter_mm),
        small_hole_maximum_diagonal_mm=float(state.repair_hole_max_diagonal_mm),
    )
