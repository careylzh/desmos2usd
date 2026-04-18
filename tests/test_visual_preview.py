from __future__ import annotations

import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path

import _path  # noqa: F401
from desmos2usd.ir import ExpressionIR, SourceInfo
from desmos2usd.parse.classify import ClassifiedExpression
from desmos2usd.tessellate.mesh import GeometryData, Point
from desmos2usd.usd.writer import ExportedPrim
from desmos2usd.validate.visual import contact_sheet_gutter, write_preview_ppm


Rgb = tuple[int, int, int]


class VisualPreviewTests(unittest.TestCase):
    def test_preview_is_three_projection_color_contact_sheet(self) -> None:
        size = 24
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "preview.ppm"
            write_preview_ppm(
                path,
                [
                    curve_prim("#c74440", [(0.0, 0.0, 0.0), (10.0, 0.0, 12.0)]),
                    curve_prim("#388c46", [(-4.0, 5.0, 0.0), (-4.0, 5.0, 12.0)]),
                ],
                size=size,
            )

            width, height, pixels = read_ppm(path)

        gutter = contact_sheet_gutter(size)
        self.assertEqual(width, size * 3 + gutter * 2)
        self.assertEqual(height, size)

        for panel_index in range(3):
            panel = panel_pixels(pixels, panel_index, size, gutter)
            self.assertGreater(count_matching(panel, red_pixel), 0, f"missing red pixels in panel {panel_index}")
            self.assertGreater(count_matching(panel, green_pixel), 0, f"missing green pixels in panel {panel_index}")

    def test_side_projections_expose_z_extent(self) -> None:
        size = 40
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "preview.ppm"
            write_preview_ppm(
                path,
                [
                    mesh_prim(
                        "#c74440",
                        [
                            (0.0, 0.0, -6.0),
                            (10.0, 0.0, -6.0),
                            (10.0, 0.0, 6.0),
                            (0.0, 0.0, 6.0),
                        ],
                    )
                ],
                size=size,
            )
            _, _, pixels = read_ppm(path)

        gutter = contact_sheet_gutter(size)
        xz_panel = panel_pixels(pixels, 1, size, gutter)
        yz_panel = panel_pixels(pixels, 2, size, gutter)
        self.assertGreater(colored_y_span(xz_panel, red_pixel), size // 2)
        self.assertGreater(colored_y_span(yz_panel, red_pixel), size // 2)


def curve_prim(color: str, points: list[Point]) -> ExportedPrim:
    source = SourceInfo(url="", graph_hash="sample", state_url="", title="sample")
    ir = ExpressionIR(source=source, expr_id=f"expr_{color}", order=0, latex="", color=color)
    item = ClassifiedExpression(ir=ir, kind="parametric_curve")
    geometry = GeometryData(kind="BasisCurves", points=points, curve_vertex_counts=[len(points)])
    return ExportedPrim(item=item, geometry=geometry)


def mesh_prim(color: str, points: list[Point]) -> ExportedPrim:
    source = SourceInfo(url="", graph_hash="sample", state_url="", title="sample")
    ir = ExpressionIR(source=source, expr_id=f"expr_{color}", order=0, latex="", color=color)
    item = ClassifiedExpression(ir=ir, kind="explicit_surface")
    geometry = GeometryData(
        kind="Mesh",
        points=points,
        face_vertex_counts=[4],
        face_vertex_indices=[0, 1, 2, 3],
    )
    return ExportedPrim(item=item, geometry=geometry)


def read_ppm(path: Path) -> tuple[int, int, list[list[Rgb]]]:
    tokens = path.read_text(encoding="ascii").split()
    if tokens[0] != "P3":
        raise AssertionError(f"unexpected PPM magic: {tokens[0]}")
    width = int(tokens[1])
    height = int(tokens[2])
    max_value = int(tokens[3])
    if max_value != 255:
        raise AssertionError(f"unexpected PPM max value: {max_value}")
    values = [int(token) for token in tokens[4:]]
    pixels = []
    offset = 0
    for _ in range(height):
        row = []
        for _ in range(width):
            row.append((values[offset], values[offset + 1], values[offset + 2]))
            offset += 3
        pixels.append(row)
    return width, height, pixels


def panel_pixels(pixels: list[list[Rgb]], panel_index: int, size: int, gutter: int) -> list[list[Rgb]]:
    start = panel_index * (size + gutter)
    return [row[start : start + size] for row in pixels]


def count_matching(pixels: list[list[Rgb]], predicate: Callable[[Rgb], bool]) -> int:
    return sum(1 for row in pixels for pixel in row if predicate(pixel))


def colored_y_span(pixels: list[list[Rgb]], predicate: Callable[[Rgb], bool]) -> int:
    ys = [y for y, row in enumerate(pixels) for pixel in row if predicate(pixel)]
    if not ys:
        return 0
    return max(ys) - min(ys)


def red_pixel(pixel: Rgb) -> bool:
    red, green, blue = pixel
    return red > 150 and green < 100 and blue < 100


def green_pixel(pixel: Rgb) -> bool:
    red, green, blue = pixel
    return red < 100 and green > 100 and blue < 100


if __name__ == "__main__":
    unittest.main()
