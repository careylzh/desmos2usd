from __future__ import annotations

from desmos2usd.eval.context import EvalContext
from desmos2usd.parse.classify import ClassifiedExpression
from desmos2usd.parse.predicates import collect_constant_bounds
from desmos2usd.tessellate.mesh import GeometryData, Point, linspace
from desmos2usd.tessellate.surfaces import axis_bounds, point_from_variables

AXES = ("x", "y", "z")
ISO_TOL = 1e-9


def tessellate_implicit_surface(item: ClassifiedExpression, context: EvalContext, resolution: int = 18) -> GeometryData:
    if item.expression is None:
        raise ValueError("implicit surface missing residual expression")
    residual_axes = tuple(axis for axis in AXES if axis in item.expression.identifiers)
    if len(residual_axes) != 2:
        raise ValueError("implicit surface extrusion requires exactly two equation axes")
    extrude_axis = next(axis for axis in AXES if axis not in residual_axes)
    bounds = collect_constant_bounds(item.predicates, context)
    viewport = item.ir.source.viewport_bounds
    a_axis, b_axis = residual_axes
    a_low, a_high = axis_bounds(a_axis, bounds, viewport)
    b_low, b_high = axis_bounds(b_axis, bounds, viewport)
    e_low, e_high = implicit_axis_bounds(extrude_axis, bounds, viewport)
    if e_low == e_high:
        e_high = e_low + 1e-4
    a_values = linspace(a_low, a_high, max(6, resolution))
    b_values = linspace(b_low, b_high, max(6, resolution))
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    values: list[list[float | None]] = []
    for b in b_values:
        row: list[float | None] = []
        for a in a_values:
            variables = {a_axis: a, b_axis: b, extrude_axis: (e_low + e_high) / 2.0}
            try:
                row.append(float(item.expression.eval(context, variables)))
            except Exception:
                row.append(None)
        values.append(row)

    for row in range(len(b_values) - 1):
        for col in range(len(a_values) - 1):
            corners = [
                (a_values[col], b_values[row], values[row][col]),
                (a_values[col + 1], b_values[row], values[row][col + 1]),
                (a_values[col + 1], b_values[row + 1], values[row + 1][col + 1]),
                (a_values[col], b_values[row + 1], values[row + 1][col]),
            ]
            if any(value is None for _, _, value in corners):
                continue
            hits = contour_cell_edges(corners)  # type: ignore[arg-type]
            if len(hits) == 2:
                segments.append((hits[0], hits[1]))
            elif len(hits) == 4:
                segments.append((hits[0], hits[1]))
                segments.append((hits[2], hits[3]))

    points: list[Point] = []
    counts: list[int] = []
    indices: list[int] = []
    for start, end in segments:
        base = len(points)
        p0 = make_point(a_axis, b_axis, extrude_axis, start[0], start[1], e_low)
        p1 = make_point(a_axis, b_axis, extrude_axis, end[0], end[1], e_low)
        p2 = make_point(a_axis, b_axis, extrude_axis, end[0], end[1], e_high)
        p3 = make_point(a_axis, b_axis, extrude_axis, start[0], start[1], e_high)
        variables = [dict(zip(AXES, p, strict=True)) for p in (p0, p1, p2, p3)]
        if not all(all(predicate.evaluate(context, variable, tol=1e-5) for predicate in item.predicates) for variable in variables):
            continue
        points.extend([p0, p1, p2, p3])
        counts.append(4)
        indices.extend([base, base + 1, base + 2, base + 3])
    return GeometryData(kind="Mesh", points=points, face_vertex_counts=counts, face_vertex_indices=indices)


def implicit_axis_bounds(axis: str, bounds: dict[str, tuple[float | None, float | None]], viewport: dict[str, tuple[float, float]]) -> tuple[float, float]:
    low, high = axis_bounds(axis, bounds, viewport)
    if low < high:
        return low, high
    return low, low


def contour_cell_edges(corners: list[tuple[float, float, float]]) -> list[tuple[float, float]]:
    hits: list[tuple[float, float]] = []
    edges = ((0, 1), (1, 2), (2, 3), (3, 0))
    for left_index, right_index in edges:
        a0, b0, v0 = corners[left_index]
        a1, b1, v1 = corners[right_index]
        if abs(v0) <= ISO_TOL and abs(v1) <= ISO_TOL:
            hits.extend([(a0, b0), (a1, b1)])
        elif abs(v0) <= ISO_TOL:
            hits.append((a0, b0))
        elif abs(v1) <= ISO_TOL:
            hits.append((a1, b1))
        elif (v0 < 0 < v1) or (v1 < 0 < v0):
            t = abs(v0) / (abs(v0) + abs(v1))
            hits.append((a0 + (a1 - a0) * t, b0 + (b1 - b0) * t))
    deduped: list[tuple[float, float]] = []
    seen: set[tuple[int, int]] = set()
    for a, b in hits:
        key = (round(a, 9), round(b, 9))
        if key in seen:
            continue
        seen.add(key)
        deduped.append((a, b))
    return deduped


def make_point(a_axis: str, b_axis: str, extrude_axis: str, a: float, b: float, e: float) -> Point:
    variables = {a_axis: a, b_axis: b, extrude_axis: e}
    return point_from_variables(variables)
