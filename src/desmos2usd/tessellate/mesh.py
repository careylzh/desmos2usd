from __future__ import annotations

from dataclasses import dataclass, field


Point = tuple[float, float, float]


@dataclass
class GeometryData:
    kind: str
    points: list[Point]
    face_vertex_counts: list[int] = field(default_factory=list)
    face_vertex_indices: list[int] = field(default_factory=list)
    curve_vertex_counts: list[int] = field(default_factory=list)
    sample_parameters: list[dict[str, float]] = field(default_factory=list)

    @property
    def face_count(self) -> int:
        return len(self.face_vertex_counts)

    @property
    def point_count(self) -> int:
        return len(self.points)

    def deterministic_key(self) -> tuple:
        rounded = tuple(tuple(round(coord, 9) for coord in point) for point in self.points)
        return (self.kind, rounded, tuple(self.face_vertex_counts), tuple(self.face_vertex_indices), tuple(self.curve_vertex_counts))


def quad_faces(width: int, height: int, valid: list[list[bool]] | None = None) -> tuple[list[int], list[int]]:
    counts: list[int] = []
    indices: list[int] = []
    for row in range(height - 1):
        for col in range(width - 1):
            if valid and not all([valid[row][col], valid[row][col + 1], valid[row + 1][col + 1], valid[row + 1][col]]):
                continue
            a = row * width + col
            b = a + 1
            c = a + width + 1
            d = a + width
            counts.append(4)
            indices.extend([a, b, c, d])
    return counts, indices


def linspace(low: float, high: float, count: int) -> list[float]:
    if count <= 1:
        return [(low + high) / 2.0]
    step = (high - low) / float(count - 1)
    return [low + step * index for index in range(count)]

