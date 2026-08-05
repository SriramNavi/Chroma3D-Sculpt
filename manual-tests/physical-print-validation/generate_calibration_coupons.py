"""Generate lightweight local Sprint 3.5 calibration STL coupons."""

from __future__ import annotations

from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "artifacts" / "calibration-coupons"
Triangle = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]


def box(x0: float, y0: float, z0: float, sx: float, sy: float, sz: float) -> list[Triangle]:
    points = [
        (x0, y0, z0), (x0 + sx, y0, z0), (x0 + sx, y0 + sy, z0), (x0, y0 + sy, z0),
        (x0, y0, z0 + sz), (x0 + sx, y0, z0 + sz), (x0 + sx, y0 + sy, z0 + sz), (x0, y0 + sy, z0 + sz),
    ]
    quads = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))
    return [(points[a], points[b], points[c]) for a, b, c, d in quads for a, b, c in ((a, b, c), (a, c, d))]


def cylinder(cx: float, cy: float, z0: float, diameter: float, height: float, segments: int = 20) -> list[Triangle]:
    radius = diameter / 2.0
    lower = [(cx + radius * math.cos(2 * math.pi * index / segments), cy + radius * math.sin(2 * math.pi * index / segments), z0) for index in range(segments)]
    upper = [(x, y, z0 + height) for x, y, _ in lower]
    triangles: list[Triangle] = []
    for index in range(segments):
        nxt = (index + 1) % segments
        triangles.extend(((lower[index], lower[nxt], upper[nxt]), (lower[index], upper[nxt], upper[index]), ((cx, cy, z0), lower[nxt], lower[index]), ((cx, cy, z0 + height), upper[index], upper[nxt])))
    return triangles


def wedge(x0: float, y0: float, z0: float, length: float, width: float, angle_deg: float) -> list[Triangle]:
    height = max(1.0, length * math.tan(math.radians(angle_deg)))
    points = [(x0, y0, z0), (x0 + length, y0, z0), (x0 + length, y0, z0 + height), (x0, y0 + width, z0), (x0 + length, y0 + width, z0), (x0 + length, y0 + width, z0 + height)]
    faces = ((0, 1, 2), (3, 5, 4), (0, 3, 4), (0, 4, 1), (1, 4, 5), (1, 5, 2), (0, 2, 5), (0, 5, 3))
    return [(points[a], points[b], points[c]) for a, b, c in faces]


def normal(triangle: Triangle) -> tuple[float, float, float]:
    a, b, c = triangle
    u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    length = math.sqrt(sum(value * value for value in cross)) or 1.0
    return tuple(value / length for value in cross)


def write_ascii_stl(path: Path, name: str, triangles: Iterable[Triangle]) -> None:
    lines = [f"solid {name}"]
    for triangle in triangles:
        nx, ny, nz = normal(triangle)
        lines.extend((f"  facet normal {nx:.9g} {ny:.9g} {nz:.9g}", "    outer loop"))
        lines.extend(f"      vertex {x:.9g} {y:.9g} {z:.9g}" for x, y, z in triangle)
        lines.extend(("    endloop", "  endfacet"))
    lines.extend((f"endsolid {name}", ""))
    path.write_text("\n".join(lines), encoding="ascii", newline="\n")


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    coupons: dict[str, list[Triangle]] = {}
    walls = box(0, 0, 0, 70, 30, 1)
    for index, thickness in enumerate((0.4, 0.6, 0.8, 1.2, 2.0)):
        walls.extend(box(5 + index * 13, 5, 1, thickness, 20, 20))
    coupons["wall-thickness-coupon"] = walls
    features = box(0, 0, 0, 70, 30, 1)
    for index, diameter in enumerate((0.4, 0.6, 0.8, 1.2, 2.0)):
        features.extend(cylinder(7 + index * 13, 15, 1, diameter, 20))
    coupons["thin-feature-coupon"] = features
    overhangs = box(0, 0, 0, 90, 35, 1)
    for index, angle in enumerate((20.0, 30.0, 45.0, 60.0)):
        overhangs.extend(wedge(5 + index * 21, 5, 1, 16, 25, angle))
    coupons["overhang-angle-coupon"] = overhangs
    contact = box(0, 0, 0, 80, 30, 1)
    contact.extend(box(5, 5, 1, 18, 18, 12))
    contact.extend(wedge(32, 5, 1, 18, 18, 45))
    contact.extend(cylinder(65, 14, 1, 2.0, 18))
    coupons["contact-class-coupon"] = contact
    manifest = {"schema_version": "1.0.0", "units": "mm", "printer": "Bambu Lab X1 Carbon", "nozzle_mm": 0.4, "physical_results": "NOT_RUN", "files": []}
    for name, triangles in coupons.items():
        path = OUTPUT / f"{name}.stl"
        write_ascii_stl(path, name, triangles)
        manifest["files"].append({"path": path.name, "sha256": sha256(path.read_bytes()).hexdigest(), "triangle_count": len(triangles)})
    (OUTPUT / "coupon_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Generated {len(coupons)} local calibration coupons in {OUTPUT}")
    print("Physical results: NOT_RUN; printer commands sent: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
