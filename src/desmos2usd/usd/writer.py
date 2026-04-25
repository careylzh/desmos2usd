from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from desmos2usd.ir import GraphIR
from desmos2usd.parse.classify import ClassifiedExpression
from desmos2usd.tessellate.mesh import GeometryData
from desmos2usd.usd.metadata import custom_metadata_lines, prim_name, usd_string


@dataclass(frozen=True)
class ExportedPrim:
    item: ClassifiedExpression
    geometry: GeometryData


def write_usda(path: Path, graph: GraphIR, prims: list[ExportedPrim]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "#usda 1.0",
        "(",
        '    defaultPrim = "DesmosGraph"',
        "    metersPerUnit = 1",
        '    upAxis = "Z"',
        "    customLayerData = {",
        f"        string \"desmos:url\" = {usd_string(graph.source.url)}",
        f"        string \"desmos:hash\" = {usd_string(graph.source.graph_hash)}",
        f"        string \"desmos:title\" = {usd_string(graph.source.title)}",
        f"        string \"desmos:stateUrl\" = {usd_string(graph.source.state_url)}",
        f"        string \"desmos:viewportBounds\" = {usd_string(json.dumps(graph.source.viewport_bounds, sort_keys=True))}",
        "    }",
        ")",
        "",
        'def Xform "DesmosGraph"',
        "{",
    ]
    for prim in prims:
        lines.extend(write_prim(prim, indent="    "))
    lines.append("}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_prim(prim: ExportedPrim, indent: str) -> list[str]:
    item = prim.item
    geometry = prim.geometry
    name = prim_name(item)
    if geometry.kind == "Mesh":
        return write_mesh(name, item, geometry, indent)
    if geometry.kind == "BasisCurves":
        return write_curve(name, item, geometry, indent)
    raise ValueError(f"Unsupported USD geometry kind: {geometry.kind}")


def write_mesh(name: str, item: ClassifiedExpression, geometry: GeometryData, indent: str) -> list[str]:
    lines = [f'{indent}def Mesh "{name}"', f"{indent}{{"]
    for metadata in custom_metadata_lines(item):
        lines.append(f"{indent}    {metadata}")
    lines.extend(
        [
            f"{indent}    uniform bool doubleSided = true",
            *display_color_lines(item, indent),
            f"{indent}    point3f[] points = {format_points(geometry.points)}",
            f"{indent}    int[] faceVertexCounts = {format_ints(geometry.face_vertex_counts)}",
            f"{indent}    int[] faceVertexIndices = {format_ints(geometry.face_vertex_indices)}",
            f"{indent}}}",
            "",
        ]
    )
    return lines


def write_curve(name: str, item: ClassifiedExpression, geometry: GeometryData, indent: str) -> list[str]:
    lines = [f'{indent}def BasisCurves "{name}"', f"{indent}{{"]
    for metadata in custom_metadata_lines(item):
        lines.append(f"{indent}    {metadata}")
    lines.extend(
        [
            f'{indent}    uniform token type = "linear"',
            *display_color_lines(item, indent),
            f"{indent}    int[] curveVertexCounts = {format_ints(geometry.curve_vertex_counts)}",
            f"{indent}    point3f[] points = {format_points(geometry.points)}",
            f"{indent}    float[] widths = [0.025]",
            f"{indent}}}",
            "",
        ]
    )
    return lines


def display_color_lines(item: ClassifiedExpression, indent: str) -> list[str]:
    rgb = parse_hex_color(item.ir.color)
    if rgb is None:
        return []
    r, g, b = rgb
    return [
        f"{indent}    color3f[] primvars:displayColor = [({format_float(r)}, {format_float(g)}, {format_float(b)})] (",
        f'{indent}        interpolation = "constant"',
        f"{indent}    )",
    ]


def parse_hex_color(value: str | None) -> tuple[float, float, float] | None:
    if not value:
        return None
    text = value.strip()
    if len(text) == 7 and text.startswith("#"):
        try:
            return tuple(int(text[index : index + 2], 16) / 255.0 for index in (1, 3, 5))  # type: ignore[return-value]
        except ValueError:
            return None
    return None


def format_points(points: list[tuple[float, float, float]]) -> str:
    return "[" + ", ".join(f"({format_float(x)}, {format_float(y)}, {format_float(z)})" for x, y, z in points) + "]"


def format_ints(values: list[int]) -> str:
    return "[" + ", ".join(str(value) for value in values) + "]"


def format_float(value: float) -> str:
    if abs(value) < 5e-13:
        value = 0.0
    return f"{value:.9g}"
