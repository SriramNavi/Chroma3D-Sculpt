"""Deterministic canonical orthographic triangle-mask silhouette metrics."""

from __future__ import annotations

import argparse
import json
from math import ceil, floor, sqrt
from pathlib import Path
from typing import Iterable

from mesh_io import Mesh, Vec3, load_mesh


VIEWS = ("front", "front_three_quarter", "side", "back")


def _project(vertex: Vec3, view: str) -> tuple[float, float]:
    x, y, z = vertex
    if view == "front":
        return x, z
    if view == "front_three_quarter":
        return (x - y) / sqrt(2.0), z
    if view == "side":
        return y, z
    if view == "back":
        return -x, z
    raise ValueError(f"Unknown view: {view}")


def _edge(a: tuple[float, float], b: tuple[float, float], p: tuple[float, float]) -> float:
    return (p[0] - a[0]) * (b[1] - a[1]) - (p[1] - a[1]) * (b[0] - a[0])


def rasterize_mask(mesh: Mesh, view: str, *, resolution: int = 128, extent: float = 0.8) -> frozenset[int]:
    if resolution < 16 or resolution > 1024 or extent <= 0:
        raise ValueError("Invalid silhouette raster settings.")
    projected = [_project(vertex, view) for vertex in mesh.vertices]
    pixels: set[int] = set()
    scale = (resolution - 1) / (2.0 * extent)
    for face in mesh.faces:
        points = [((projected[index][0] + extent) * scale, (projected[index][1] + extent) * scale) for index in face]
        area = _edge(points[0], points[1], points[2])
        if abs(area) < 1e-12:
            continue
        minimum_x = max(0, floor(min(point[0] for point in points)))
        maximum_x = min(resolution - 1, ceil(max(point[0] for point in points)))
        minimum_y = max(0, floor(min(point[1] for point in points)))
        maximum_y = min(resolution - 1, ceil(max(point[1] for point in points)))
        for y in range(minimum_y, maximum_y + 1):
            for x in range(minimum_x, maximum_x + 1):
                sample = (x + 0.5, y + 0.5)
                signs = (_edge(points[0], points[1], sample), _edge(points[1], points[2], sample), _edge(points[2], points[0], sample))
                if all(value >= -1e-9 for value in signs) or all(value <= 1e-9 for value in signs):
                    pixels.add(y * resolution + x)
    return frozenset(pixels)


def mask_iou(left: Iterable[int], right: Iterable[int]) -> float:
    a, b = set(left), set(right)
    union = a | b
    return 1.0 if not union else len(a & b) / len(union)


def evaluate_silhouettes(ground_truth: Mesh, generated: Mesh, *, resolution: int = 128) -> dict[str, object]:
    per_view = {
        view: mask_iou(rasterize_mask(ground_truth, view, resolution=resolution), rasterize_mask(generated, view, resolution=resolution))
        for view in VIEWS
    }
    return {
        "method": "canonical_orthographic_triangle_mask_v1", "resolution": resolution,
        "views": per_view, "mean_iou": sum(per_view.values()) / len(per_view),
        "worst_view_iou": min(per_view.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ground_truth", type=Path)
    parser.add_argument("generated", type=Path)
    parser.add_argument("--resolution", type=int, default=128)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate_silhouettes(load_mesh(args.ground_truth), load_mesh(args.generated), resolution=args.resolution)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8", newline="\n")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
