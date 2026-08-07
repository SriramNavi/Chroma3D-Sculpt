"""Small dependency-free STL/OBJ/ASCII-PLY reader for CGB engineering metrics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct


Vec3 = tuple[float, float, float]
Face = tuple[int, int, int]


@dataclass(frozen=True)
class Mesh:
    vertices: tuple[Vec3, ...]
    faces: tuple[Face, ...]

    def validate(self) -> None:
        if not self.vertices or not self.faces:
            raise ValueError("Mesh must contain vertices and triangle faces.")
        for face in self.faces:
            if len(set(face)) != 3 or min(face) < 0 or max(face) >= len(self.vertices):
                raise ValueError("Mesh contains an invalid triangle index.")


def _dedupe_triangles(triangles: list[tuple[Vec3, Vec3, Vec3]]) -> Mesh:
    vertices: list[Vec3] = []
    lookup: dict[Vec3, int] = {}
    faces: list[Face] = []
    for triangle in triangles:
        indices = []
        for vertex in triangle:
            normalized = tuple(0.0 if value == 0.0 else float(value) for value in vertex)
            if normalized not in lookup:
                lookup[normalized] = len(vertices)
                vertices.append(normalized)
            indices.append(lookup[normalized])
        if len(set(indices)) == 3:
            faces.append((indices[0], indices[1], indices[2]))
    mesh = Mesh(tuple(vertices), tuple(faces))
    mesh.validate()
    return mesh


def _load_binary_stl(data: bytes) -> Mesh:
    if len(data) < 84:
        raise ValueError("Binary STL is truncated.")
    count = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + count * 50:
        raise ValueError("Binary STL byte count does not match its triangle header.")
    triangles = []
    offset = 84
    for _ in range(count):
        values = struct.unpack_from("<12fH", data, offset)
        triangles.append(((values[3], values[4], values[5]), (values[6], values[7], values[8]), (values[9], values[10], values[11])))
        offset += 50
    return _dedupe_triangles(triangles)


def _load_ascii_stl(text: str) -> Mesh:
    vertices = []
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) == 4 and parts[0].lower() == "vertex":
            vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
    if len(vertices) < 3 or len(vertices) % 3:
        raise ValueError("ASCII STL has an invalid vertex sequence.")
    return _dedupe_triangles([(vertices[index], vertices[index + 1], vertices[index + 2]) for index in range(0, len(vertices), 3)])


def load_stl(path: Path) -> Mesh:
    data = path.read_bytes()
    if len(data) >= 84:
        count = struct.unpack_from("<I", data, 80)[0]
        if len(data) == 84 + count * 50:
            return _load_binary_stl(data)
    try:
        return _load_ascii_stl(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("STL is neither a valid binary nor ASCII mesh.") from exc


def load_obj(path: Path) -> Mesh:
    vertices: list[Vec3] = []
    faces: list[Face] = []
    for raw in path.read_text(encoding="utf-8", errors="strict").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0] == "v" and len(parts) >= 4:
            vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif parts[0] == "f" and len(parts) >= 4:
            polygon = []
            for item in parts[1:]:
                index = int(item.split("/", 1)[0])
                polygon.append(index - 1 if index > 0 else len(vertices) + index)
            for offset in range(1, len(polygon) - 1):
                faces.append((polygon[0], polygon[offset], polygon[offset + 1]))
    mesh = Mesh(tuple(vertices), tuple(faces))
    mesh.validate()
    return mesh


def load_ascii_ply(path: Path) -> Mesh:
    lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    if not lines or lines[0].strip() != "ply":
        raise ValueError("PLY header is missing.")
    vertex_count = face_count = None
    header_end = None
    for index, line in enumerate(lines):
        parts = line.split()
        if parts[:2] == ["format", "binary_little_endian"] or parts[:2] == ["format", "binary_big_endian"]:
            raise ValueError("Only ASCII PLY is supported by the dependency-free evaluator.")
        if parts[:2] == ["element", "vertex"]:
            vertex_count = int(parts[2])
        if parts[:2] == ["element", "face"]:
            face_count = int(parts[2])
        if line.strip() == "end_header":
            header_end = index + 1
            break
    if vertex_count is None or face_count is None or header_end is None:
        raise ValueError("PLY element counts are incomplete.")
    vertices = [tuple(map(float, lines[header_end + index].split()[:3])) for index in range(vertex_count)]
    faces: list[Face] = []
    start = header_end + vertex_count
    for line in lines[start:start + face_count]:
        values = [int(item) for item in line.split()]
        polygon = values[1:1 + values[0]]
        for offset in range(1, len(polygon) - 1):
            faces.append((polygon[0], polygon[offset], polygon[offset + 1]))
    mesh = Mesh(tuple(vertices), tuple(faces))
    mesh.validate()
    return mesh


def load_mesh(path: Path) -> Mesh:
    suffix = path.suffix.lower()
    if suffix == ".stl":
        return load_stl(path)
    if suffix == ".obj":
        return load_obj(path)
    if suffix == ".ply":
        return load_ascii_ply(path)
    raise ValueError(f"Unsupported dependency-free mesh format: {suffix or '<none>'}")
