from __future__ import annotations

from collections.abc import Iterator
from math import isfinite
from pathlib import Path

from desmos2usd.tessellate.mesh import GeometryData, Point
from desmos2usd.usd.writer import ExportedPrim


Rgb = tuple[int, int, int]

BACKGROUND: Rgb = (255, 255, 255)
GUTTER: Rgb = (238, 238, 238)
FRAME: Rgb = (210, 210, 210)
LABEL: Rgb = (70, 70, 70)
FALLBACK_PRIM_COLOR: Rgb = (20, 20, 20)
PROJECTIONS = (("XY", 0, 1), ("XZ", 0, 2), ("YZ", 1, 2))
GLYPHS = {
    "X": ("101", "101", "010", "101", "101"),
    "Y": ("101", "101", "010", "010", "010"),
    "Z": ("111", "001", "010", "100", "111"),
}


def write_preview_ppm(path: Path, prims: list[ExportedPrim], size: int = 256) -> None:
    if size <= 0:
        raise ValueError("preview size must be positive")

    path.parent.mkdir(parents=True, exist_ok=True)
    gutter = contact_sheet_gutter(size)
    width = size * len(PROJECTIONS) + gutter * (len(PROJECTIONS) - 1)
    pixels = [[GUTTER for _ in range(width)] for _ in range(size)]
    points = [point for prim in prims for point in prim.geometry.points if finite_point(point)]
    bounds = axis_bounds(points)

    for panel_index, (label, x_axis, y_axis) in enumerate(PROJECTIONS):
        origin_x = panel_index * (size + gutter)
        fill_panel(pixels, origin_x, size)
        draw_frame(pixels, origin_x, size)
        for prim in prims:
            draw_prim_projection(pixels, origin_x, size, prim, x_axis, y_axis, bounds)
        draw_label(pixels, origin_x + 4, 4, label)

    with path.open("w", encoding="ascii") as handle:
        handle.write(f"P3\n{width} {size}\n255\n")
        for row in pixels:
            handle.write(" ".join(str(channel) for pixel in row for channel in pixel))
            handle.write("\n")


def contact_sheet_gutter(size: int) -> int:
    return max(2, size // 64)


def finite_point(point: Point) -> bool:
    return all(isfinite(coord) for coord in point)


def axis_bounds(points: list[Point]) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    if not points:
        return ((0.0, 1.0), (0.0, 1.0), (0.0, 1.0))
    return (
        (min(point[0] for point in points), max(point[0] for point in points)),
        (min(point[1] for point in points), max(point[1] for point in points)),
        (min(point[2] for point in points), max(point[2] for point in points)),
    )


def fill_panel(pixels: list[list[Rgb]], origin_x: int, size: int) -> None:
    for y in range(size):
        for x in range(origin_x, origin_x + size):
            pixels[y][x] = BACKGROUND


def draw_frame(pixels: list[list[Rgb]], origin_x: int, size: int) -> None:
    for offset in range(size):
        set_pixel(pixels, origin_x + offset, 0, FRAME)
        set_pixel(pixels, origin_x + offset, size - 1, FRAME)
        set_pixel(pixels, origin_x, offset, FRAME)
        set_pixel(pixels, origin_x + size - 1, offset, FRAME)


def draw_prim_projection(
    pixels: list[list[Rgb]],
    origin_x: int,
    size: int,
    prim: ExportedPrim,
    x_axis: int,
    y_axis: int,
    bounds: tuple[tuple[float, float], tuple[float, float], tuple[float, float]],
) -> None:
    color = prim_color(prim)
    for start, end in wire_segments(prim.geometry):
        if finite_point(start) and finite_point(end):
            draw_line(
                pixels,
                project_point(start, origin_x, size, x_axis, y_axis, bounds),
                project_point(end, origin_x, size, x_axis, y_axis, bounds),
                color,
            )
    radius = 1 if size >= 32 else 0
    for point in prim.geometry.points:
        if finite_point(point):
            draw_dot(pixels, project_point(point, origin_x, size, x_axis, y_axis, bounds), color, radius)


def prim_color(prim: ExportedPrim) -> Rgb:
    color = prim.item.ir.color
    if isinstance(color, str):
        text = color.strip()
        if len(text) == 7 and text.startswith("#"):
            try:
                return (int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16))
            except ValueError:
                pass
    return FALLBACK_PRIM_COLOR


def wire_segments(geometry: GeometryData) -> Iterator[tuple[Point, Point]]:
    points = geometry.points
    cursor = 0
    for count in geometry.face_vertex_counts:
        face_indices = geometry.face_vertex_indices[cursor : cursor + count]
        cursor += count
        if count < 2 or len(face_indices) != count or any(index < 0 or index >= len(points) for index in face_indices):
            continue
        for index, point_index in enumerate(face_indices):
            yield points[point_index], points[face_indices[(index + 1) % count]]

    cursor = 0
    for count in geometry.curve_vertex_counts:
        if count < 2 or cursor + count > len(points):
            cursor += count
            continue
        for index in range(cursor, cursor + count - 1):
            yield points[index], points[index + 1]
        cursor += count


def project_point(
    point: Point,
    origin_x: int,
    size: int,
    x_axis: int,
    y_axis: int,
    bounds: tuple[tuple[float, float], tuple[float, float], tuple[float, float]],
) -> tuple[int, int]:
    return (
        origin_x + scale_axis(point[x_axis], bounds[x_axis], size, invert=False),
        scale_axis(point[y_axis], bounds[y_axis], size, invert=True),
    )


def scale_axis(value: float, bounds: tuple[float, float], size: int, invert: bool) -> int:
    padding = max(2, min(16, size // 16))
    low, high = bounds
    span = high - low
    drawable = size - 1 - padding * 2
    if span <= 1e-9 or drawable <= 0:
        return size // 2
    ratio = (value - low) / span
    if invert:
        ratio = 1.0 - ratio
    return clamp(padding + int(round(ratio * drawable)), 0, size - 1)


def draw_line(pixels: list[list[Rgb]], start: tuple[int, int], end: tuple[int, int], color: Rgb) -> None:
    x0, y0 = start
    x1, y1 = end
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    error = dx + dy
    while True:
        set_pixel(pixels, x0, y0, color)
        if x0 == x1 and y0 == y1:
            break
        next_error = error * 2
        if next_error >= dy:
            error += dy
            x0 += sx
        if next_error <= dx:
            error += dx
            y0 += sy


def draw_dot(pixels: list[list[Rgb]], center: tuple[int, int], color: Rgb, radius: int) -> None:
    x, y = center
    for yy in range(y - radius, y + radius + 1):
        for xx in range(x - radius, x + radius + 1):
            set_pixel(pixels, xx, yy, color)


def draw_label(pixels: list[list[Rgb]], x: int, y: int, text: str) -> None:
    if len(pixels) < 16:
        return
    cursor = x
    for char in text:
        glyph = GLYPHS.get(char)
        if glyph is None:
            cursor += 4
            continue
        for row_index, row in enumerate(glyph):
            for col_index, value in enumerate(row):
                if value == "1":
                    set_pixel(pixels, cursor + col_index, y + row_index, LABEL)
        cursor += 4


def set_pixel(pixels: list[list[Rgb]], x: int, y: int, color: Rgb) -> None:
    if 0 <= y < len(pixels) and 0 <= x < len(pixels[y]):
        pixels[y][x] = color


def clamp(value: int, low: int, high: int) -> int:
    return min(high, max(low, value))
