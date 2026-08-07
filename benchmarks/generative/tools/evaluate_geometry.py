"""Deterministic CGB geometry health, alignment, fidelity, and detail evidence."""

from __future__ import annotations

import argparse
from bisect import bisect_left
from collections import defaultdict, deque
import itertools
import json
from math import sqrt
from pathlib import Path
from typing import Any, Iterable

from evaluate_silhouettes import evaluate_silhouettes
from mesh_io import Mesh, Vec3, load_mesh


EVALUATOR_VERSION = "cgb-geometry-evaluator-1.0.0"
SAMPLE_COUNT = 256
EVALUATION_SETTINGS = {
    "surface_sample_count": SAMPLE_COUNT,
    "orientation_candidates": 24,
    "silhouette_resolution": 128,
    "alignment_method": "bounded_24_orientation_uniform_scale_v1",
    "silhouette_method": "canonical_orthographic_triangle_mask_v1",
}


def _add(a: Vec3, b: Vec3) -> Vec3:
    return a[0] + b[0], a[1] + b[1], a[2] + b[2]


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def _scale(a: Vec3, value: float) -> Vec3:
    return a[0] * value, a[1] * value, a[2] * value


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def _length(a: Vec3) -> float:
    return sqrt(_dot(a, a))


def _normal(a: Vec3, b: Vec3, c: Vec3) -> Vec3:
    value = _cross(_sub(b, a), _sub(c, a))
    length = _length(value)
    return (0.0, 0.0, 0.0) if length <= 1e-15 else _scale(value, 1.0 / length)


def bounds(vertices: Iterable[Vec3]) -> tuple[Vec3, Vec3, Vec3, float]:
    values = tuple(vertices)
    minimum = tuple(min(vertex[axis] for vertex in values) for axis in range(3))
    maximum = tuple(max(vertex[axis] for vertex in values) for axis in range(3))
    dimensions = tuple(maximum[axis] - minimum[axis] for axis in range(3))
    return minimum, maximum, dimensions, _length(dimensions)


def center(vertices: Iterable[Vec3]) -> Vec3:
    minimum, maximum, _, _ = bounds(vertices)
    return tuple((minimum[axis] + maximum[axis]) * 0.5 for axis in range(3))


def _edge_counts(mesh: Mesh) -> dict[tuple[int, int], int]:
    counts: dict[tuple[int, int], int] = defaultdict(int)
    for face in mesh.faces:
        for left, right in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            counts[tuple(sorted((left, right)))] += 1
    return counts


def _component_count(mesh: Mesh) -> int:
    adjacency: dict[int, set[int]] = defaultdict(set)
    used: set[int] = set()
    for face in mesh.faces:
        used.update(face)
        for left, right in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            adjacency[left].add(right)
            adjacency[right].add(left)
    count = 0
    while used:
        count += 1
        queue = deque([used.pop()])
        while queue:
            for neighbor in adjacency[queue.popleft()]:
                if neighbor in used:
                    used.remove(neighbor)
                    queue.append(neighbor)
    return count


def geometry_health(mesh: Mesh) -> dict[str, Any]:
    edge_counts = _edge_counts(mesh)
    boundary = sum(count == 1 for count in edge_counts.values())
    high_incidence = sum(count > 2 for count in edge_counts.values())
    area = 0.0
    signed_volume = 0.0
    degenerate = 0
    aspect_ratios = []
    for face in mesh.faces:
        a, b, c = (mesh.vertices[index] for index in face)
        cross = _cross(_sub(b, a), _sub(c, a))
        triangle_area = _length(cross) * 0.5
        area += triangle_area
        signed_volume += _dot(a, _cross(b, c)) / 6.0
        lengths = (_length(_sub(a, b)), _length(_sub(b, c)), _length(_sub(c, a)))
        if triangle_area <= 1e-15 or min(lengths) <= 1e-15:
            degenerate += 1
        else:
            aspect_ratios.append(max(lengths) / min(lengths))
    minimum, maximum, dimensions, diagonal = bounds(mesh.vertices)
    components = _component_count(mesh)
    watertight = boundary == 0 and high_incidence == 0
    penalty = min(100.0, boundary * 0.02 + high_incidence * 2.0 + degenerate * 0.5 + max(0, components - 1) * 3.0)
    return {
        "vertex_count": len(mesh.vertices), "edge_count": len(edge_counts), "face_count": len(mesh.faces),
        "triangle_count": len(mesh.faces), "dimensions": dimensions, "bounding_box_minimum": minimum,
        "bounding_box_maximum": maximum, "bounding_diagonal": diagonal,
        "connected_components": components, "shell_count": components,
        "boundary_edges": boundary, "high_incidence_non_manifold_edges": high_incidence,
        "non_manifold_evidence": boundary + high_incidence, "watertightness": "TOPOLOGICALLY_WATERTIGHT" if watertight else "NOT_WATERTIGHT",
        "orientation_consistency": "NOT_EVALUATED", "degenerate_geometry": degenerate,
        "self_intersection_candidates": "NOT_EVALUATED", "tiny_shells": "NOT_EVALUATED",
        "loose_geometry": max(0, len(mesh.vertices) - len({index for face in mesh.faces for index in face})),
        "surface_area": area, "volume_when_reliable": abs(signed_volume) if watertight else None,
        "thin_feature_evidence": "NOT_EVALUATED", "repair_issue_count": boundary + high_incidence + degenerate + max(0, components - 1),
        "printability_status": "PASS_WITH_LIMITATIONS" if watertight else "REVIEW_REQUIRED",
        "geometry_health_score": max(0.0, 100.0 - penalty),
        "score_formula": "100 - min(100, 0.02*boundary + 2*high_incidence + 0.5*degenerate + 3*(components-1))",
        "extreme_aspect_ratio_faces": sum(value > 20.0 for value in aspect_ratios),
    }


def _radical_inverse(index: int, base: int) -> float:
    inverse = 1.0 / base
    value = 0.0
    fraction = inverse
    while index:
        index, digit = divmod(index, base)
        value += digit * fraction
        fraction *= inverse
    return value


def sample_surface(mesh: Mesh, count: int = SAMPLE_COUNT) -> tuple[tuple[Vec3, Vec3], ...]:
    areas = []
    normals = []
    cumulative = []
    total = 0.0
    for face in mesh.faces:
        a, b, c = (mesh.vertices[index] for index in face)
        area = _length(_cross(_sub(b, a), _sub(c, a))) * 0.5
        areas.append(area)
        normals.append(_normal(a, b, c))
        total += area
        cumulative.append(total)
    if total <= 0:
        raise ValueError("Mesh surface area is zero.")
    samples = []
    for index in range(count):
        target = (index + 0.5) * total / count
        face_index = min(bisect_left(cumulative, target), len(mesh.faces) - 1)
        face = mesh.faces[face_index]
        a, b, c = (mesh.vertices[item] for item in face)
        u, v = _radical_inverse(index + 1, 2), _radical_inverse(index + 1, 3)
        if u + v > 1.0:
            u, v = 1.0 - u, 1.0 - v
        point = _add(a, _add(_scale(_sub(b, a), u), _scale(_sub(c, a), v)))
        samples.append((point, normals[face_index]))
    return tuple(samples)


Orientation = tuple[tuple[int, int], tuple[int, int], tuple[int, int]]


def _permutation_sign(permutation: tuple[int, int, int]) -> int:
    inversions = sum(permutation[left] > permutation[right] for left in range(3) for right in range(left + 1, 3))
    return -1 if inversions % 2 else 1


def orientations() -> tuple[Orientation, ...]:
    identity: Orientation = ((0, 1), (1, 1), (2, 1))
    values = [identity]
    for permutation in itertools.permutations(range(3)):
        for signs in itertools.product((-1, 1), repeat=3):
            if _permutation_sign(permutation) * signs[0] * signs[1] * signs[2] != 1:
                continue
            candidate = tuple((permutation[axis], signs[axis]) for axis in range(3))
            if candidate != identity:
                values.append(candidate)  # type: ignore[arg-type]
    return tuple(values)


def _orient(value: Vec3, orientation: Orientation) -> Vec3:
    return tuple(value[source] * sign for source, sign in orientation)


def _transform(value: Vec3, source_center: Vec3, target_center: Vec3, scale: float, orientation: Orientation) -> Vec3:
    return _add(target_center, _scale(_orient(_sub(value, source_center), orientation), scale))


def _nearest(source: tuple[tuple[Vec3, Vec3], ...], target: tuple[tuple[Vec3, Vec3], ...]) -> tuple[list[float], list[int]]:
    distances, indices = [], []
    for point, _ in source:
        best_distance, best_index = float("inf"), -1
        for index, (candidate, _) in enumerate(target):
            distance = _dot(_sub(point, candidate), _sub(point, candidate))
            if distance < best_distance:
                best_distance, best_index = distance, index
        distances.append(sqrt(best_distance))
        indices.append(best_index)
    return distances, indices


def align_and_compare(ground_truth: Mesh, generated: Mesh) -> tuple[dict[str, Any], Mesh, Mesh]:
    gt_center, generated_center = center(ground_truth.vertices), center(generated.vertices)
    gt_diagonal = bounds(ground_truth.vertices)[3]
    generated_diagonal = bounds(generated.vertices)[3]
    if gt_diagonal <= 0 or generated_diagonal <= 0:
        raise ValueError("ALIGNMENT_INDETERMINATE: zero bounding diagonal")
    uniform_scale = gt_diagonal / generated_diagonal
    gt_samples = sample_surface(ground_truth)
    generated_samples = sample_surface(generated)
    best: tuple[float, Orientation, tuple[tuple[Vec3, Vec3], ...], list[float], list[int], list[float], list[int]] | None = None
    for orientation in orientations():
        transformed = tuple((
            _transform(point, generated_center, gt_center, uniform_scale, orientation),
            _orient(normal, orientation),
        ) for point, normal in generated_samples)
        generated_to_gt, generated_indices = _nearest(transformed, gt_samples)
        gt_to_generated, gt_indices = _nearest(gt_samples, transformed)
        chamfer = (sum(generated_to_gt) / len(generated_to_gt) + sum(gt_to_generated) / len(gt_to_generated)) * 0.5
        if best is None or chamfer < best[0] - 1e-12:
            best = chamfer, orientation, transformed, generated_to_gt, generated_indices, gt_to_generated, gt_indices
    assert best is not None
    chamfer, orientation, transformed_samples, generated_to_gt, generated_indices, gt_to_generated, gt_indices = best
    f_scores = {}
    for percent in (1, 2, 5):
        threshold = gt_diagonal * percent / 100.0
        precision = sum(value <= threshold for value in generated_to_gt) / len(generated_to_gt)
        recall = sum(value <= threshold for value in gt_to_generated) / len(gt_to_generated)
        f_scores[f"{percent}_percent"] = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    consistency_terms = []
    for index, (_, normal) in enumerate(transformed_samples):
        consistency_terms.append(abs(_dot(normal, gt_samples[generated_indices[index]][1])))
    for index, (_, normal) in enumerate(gt_samples):
        consistency_terms.append(abs(_dot(normal, transformed_samples[gt_indices[index]][1])))
    aligned_vertices = tuple(_transform(vertex, generated_center, gt_center, uniform_scale, orientation) for vertex in generated.vertices)
    aligned_mesh = Mesh(aligned_vertices, generated.faces)
    normalized_gt = Mesh(tuple(_scale(_sub(vertex, gt_center), 1.0 / gt_diagonal) for vertex in ground_truth.vertices), ground_truth.faces)
    normalized_generated = Mesh(tuple(_scale(_sub(vertex, gt_center), 1.0 / gt_diagonal) for vertex in aligned_vertices), generated.faces)
    gt_health, generated_health = geometry_health(ground_truth), geometry_health(aligned_mesh)
    gt_dimensions = gt_health["dimensions"]
    generated_dimensions = generated_health["dimensions"]
    proportion_error = sum(abs(generated_dimensions[index] - gt_dimensions[index]) / max(gt_dimensions[index], 1e-12) for index in range(3)) / 3.0
    area_ratio = generated_health["surface_area"] / max(gt_health["surface_area"], 1e-12)
    gt_volume, generated_volume = gt_health["volume_when_reliable"], generated_health["volume_when_reliable"]
    return {
        "status": "PASS", "method": "bounded_24_orientation_uniform_scale_v1",
        "translation_centers": {"generated": generated_center, "ground_truth": gt_center},
        "uniform_scale": uniform_scale, "orientation": orientation,
        "symmetric_chamfer": chamfer, "normalized_symmetric_chamfer": chamfer / gt_diagonal,
        "f_score": f_scores, "normal_consistency": sum(consistency_terms) / len(consistency_terms),
        "bounding_box_proportion_error": proportion_error, "surface_area_ratio": area_ratio,
        "volume_ratio": None if gt_volume is None or generated_volume is None else generated_volume / max(gt_volume, 1e-12),
        "component_count_difference": generated_health["connected_components"] - gt_health["connected_components"],
    }, normalized_gt, normalized_generated


def evaluate_geometry(ground_truth: Mesh, generated: Mesh) -> dict[str, Any]:
    raw = geometry_health(generated)
    ground_truth_health = geometry_health(ground_truth)
    alignment, normalized_gt, normalized_generated = align_and_compare(ground_truth, generated)
    silhouettes = evaluate_silhouettes(normalized_gt, normalized_generated)
    triangle_ratio = len(generated.faces) / max(len(ground_truth.faces), 1)
    detail = {
        "status": "EXPERIMENTAL", "included_in_primary_ranking": False,
        "triangle_density_ratio": triangle_ratio,
        "high_frequency_silhouette_retention_proxy": silhouettes["worst_view_iou"],
        "limitations": ["CGB v0.1 does not claim a validated curvature/detail-accuracy metric."],
    }
    return {
        "evaluator_version": EVALUATOR_VERSION, "status": "PASS",
        "raw_geometry": raw, "ground_truth_geometry": ground_truth_health,
        "alignment": {key: value for key, value in alignment.items() if key not in {"symmetric_chamfer", "normalized_symmetric_chamfer", "f_score", "normal_consistency", "bounding_box_proportion_error", "surface_area_ratio", "volume_ratio", "component_count_difference"}},
        "shape_fidelity": {key: alignment[key] for key in ("symmetric_chamfer", "normalized_symmetric_chamfer", "f_score", "normal_consistency", "bounding_box_proportion_error", "surface_area_ratio", "volume_ratio", "component_count_difference")},
        "silhouette": silhouettes, "detail": detail,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ground_truth", type=Path)
    parser.add_argument("generated", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = evaluate_geometry(load_mesh(args.ground_truth), load_mesh(args.generated))
    except Exception as exc:
        result = {"evaluator_version": EVALUATOR_VERSION, "status": "ANALYSIS_FAILED", "error_class": type(exc).__name__, "error": str(exc)}
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8", newline="\n")
    else:
        print(payload, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
