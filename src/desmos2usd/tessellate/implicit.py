from __future__ import annotations

from dataclasses import dataclass
import math

from desmos2usd.eval.context import EvalContext
from desmos2usd.parse.classify import ClassifiedExpression
from desmos2usd.parse.latex_subset import LatexExpression
from desmos2usd.parse.predicates import collect_constant_bounds
from desmos2usd.tessellate.cylinders import tessellate_circular_implicit_surface
from desmos2usd.tessellate.mesh import GeometryData, Point, linspace
from desmos2usd.tessellate.surfaces import axis_bounds, numeric_constants_for_item, point_from_variables

AXES = ("x", "y", "z")
ISO_TOL = 1e-9
QUADRIC_FIT_DELTA = 1.0
QUADRIC_FIT_TOLERANCE = 1e-5


@dataclass(frozen=True)
class AxisAlignedEllipsoid:
    center: tuple[float, float, float]
    radii: tuple[float, float, float]
    coefficients: tuple[float, float, float]


def _axis_referenced_by_predicates(item: ClassifiedExpression, axis: str) -> bool:
    for predicate in item.predicates:
        for term in predicate.terms:
            if axis in term.identifiers:
                return True
    return False


def tessellate_implicit_surface(item: ClassifiedExpression, context: EvalContext, resolution: int = 18) -> GeometryData:
    if item.expression is None:
        raise ValueError("implicit surface missing residual expression")
    residual_axes = tuple(axis for axis in AXES if axis in item.expression.identifiers)
    if len(residual_axes) == 3:
        geometry = tessellate_circular_implicit_surface(item, context, resolution=max(8, resolution * 2))
        if geometry is not None and geometry.point_count > 0:
            return geometry
        geometry = tessellate_axis_aligned_ellipsoid(item, context, resolution=max(8, resolution))
        if geometry is not None and geometry.point_count > 0:
            return geometry
        return tessellate_implicit_surface_3axis_marching(item, context, resolution)
    if len(residual_axes) == 1:
        shape_axes = _flat_implicit_curve_axes(item, residual_axes)
        if shape_axes is None:
            geometry = tessellate_one_axis_implicit_sheets(item, context, residual_axes[0], resolution)
            if geometry is not None and geometry.point_count > 0:
                return geometry
            raise ValueError("implicit surface extrusion requires exactly two equation axes")
        extrude_axis = next(axis for axis in AXES if axis not in shape_axes)
        bounds = collect_constant_bounds(item.predicates, context)
        a_axis, b_axis = shape_axes
        a_low, a_high = _implicit_curve_axis_bounds(item, a_axis, bounds)
        b_low, b_high = _implicit_curve_axis_bounds(item, b_axis, bounds)
        refined = _refine_iso_window(
            item.expression,
            context,
            a_axis,
            b_axis,
            extrude_axis,
            0.0,
            (a_low, a_high),
            (b_low, b_high),
        )
        if refined is not None:
            a_low, a_high, b_low, b_high = refined
        geometry = tessellate_implicit_curve_2d(
            item,
            context,
            a_axis,
            b_axis,
            extrude_axis,
            0.0,
            (a_low, a_high),
            (b_low, b_high),
            resolution,
        )
        if geometry.point_count > 0:
            return geometry
        raise ValueError("implicit surface requires a supported bounded one-axis contour")
    if len(residual_axes) != 2:
        raise ValueError("implicit surface extrusion requires exactly two equation axes")
    extrude_axis = next(axis for axis in AXES if axis not in residual_axes)
    bounds = collect_constant_bounds(item.predicates, context)
    viewport = item.ir.source.viewport_bounds
    a_axis, b_axis = residual_axes
    a_low, a_high = axis_bounds(a_axis, bounds, viewport)
    b_low, b_high = axis_bounds(b_axis, bounds, viewport)
    # Desmos 3D convention: an implicit equation that doesn't mention one of (x, y, z) and has
    # no restriction on it is a 2D shape rendered at that axis = 0, not extruded across the
    # full viewport. Without this, expressions like `abs(x-y)+abs(x+y)=2.4 {x^2+y^2 in annulus}`
    # become full-height vertical sheets that dominate the scene.
    if not _axis_referenced_by_predicates(item, extrude_axis):
        e_low, e_high = 0.0, 0.0
    else:
        e_low, e_high = implicit_axis_bounds(extrude_axis, bounds, viewport)
    # When a residual axis falls back to the viewport (no predicate constraint), refine it
    # toward the iso-curve so a small contour (e.g. radius 1.27 in viewport ±12) is not lost
    # entirely between coarse cells.
    a_predicate_bounded = a_axis in bounds and bounds[a_axis] != (None, None)
    b_predicate_bounded = b_axis in bounds and bounds[b_axis] != (None, None)
    if not (a_predicate_bounded and b_predicate_bounded):
        refined = _refine_iso_window(
            item.expression,
            context,
            a_axis,
            b_axis,
            extrude_axis,
            (e_low + e_high) / 2.0,
            (a_low, a_high),
            (b_low, b_high),
        )
        if refined is not None:
            a_low, a_high, b_low, b_high = refined
    if e_low == e_high:
        geometry = tessellate_implicit_curve_2d(
            item,
            context,
            a_axis,
            b_axis,
            extrude_axis,
            e_low,
            (a_low, a_high),
            (b_low, b_high),
            resolution,
        )
        if geometry.point_count > 0:
            return geometry
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


def _flat_implicit_curve_axes(item: ClassifiedExpression, residual_axes: tuple[str, ...]) -> tuple[str, str] | None:
    referenced = set(residual_axes)
    for predicate in item.predicates:
        for term in predicate.terms:
            referenced.update(term.identifiers & set(AXES))
    if len(referenced) != 2:
        return None
    return tuple(axis for axis in AXES if axis in referenced)  # type: ignore[return-value]


def _implicit_curve_axis_bounds(
    item: ClassifiedExpression,
    axis: str,
    bounds: dict[str, tuple[float | None, float | None]],
) -> tuple[float, float]:
    low, high = bounds.get(axis, (None, None))
    if low is not None and high is not None and low < high:
        return low, high
    constants = numeric_constants_for_item(item)
    magnitudes = [abs(value) for value in constants]
    magnitudes += [value ** 0.5 for value in magnitudes]
    span = max(magnitudes) if magnitudes else 1.0
    span = max(span * 1.25, 0.5)
    return -span, span


def tessellate_one_axis_implicit_sheets(
    item: ClassifiedExpression,
    context: EvalContext,
    residual_axis: str,
    resolution: int,
) -> GeometryData | None:
    if item.expression is None:
        return None
    bounds = collect_constant_bounds(item.predicates, context)
    residual_bounds = _implicit_curve_axis_bounds(item, residual_axis, bounds)
    roots = one_axis_roots(item.expression, context, residual_axis, residual_bounds, max(257, resolution * 24 + 1))
    if not roots:
        return None

    sheet_axes = [axis for axis in AXES if axis != residual_axis]
    viewport = item.ir.source.viewport_bounds
    ranges = {axis: implicit_axis_bounds(axis, bounds, viewport) for axis in sheet_axes}
    if any(low >= high for low, high in ranges.values()):
        return None

    points: list[Point] = []
    counts: list[int] = []
    indices: list[int] = []
    a_axis, b_axis = sheet_axes
    a_low, a_high = ranges[a_axis]
    b_low, b_high = ranges[b_axis]
    for root in roots:
        corners = [
            point_from_variables({residual_axis: root, a_axis: a_low, b_axis: b_low}),
            point_from_variables({residual_axis: root, a_axis: a_high, b_axis: b_low}),
            point_from_variables({residual_axis: root, a_axis: a_high, b_axis: b_high}),
            point_from_variables({residual_axis: root, a_axis: a_low, b_axis: b_high}),
        ]
        variables = [dict(zip(AXES, point, strict=True)) for point in corners]
        if not all(all(predicate.evaluate(context, variable, tol=1e-5) for predicate in item.predicates) for variable in variables):
            continue
        base = len(points)
        points.extend(corners)
        counts.append(4)
        indices.extend([base, base + 1, base + 2, base + 3])
    if not counts:
        return None
    return GeometryData(kind="Mesh", points=points, face_vertex_counts=counts, face_vertex_indices=indices)


def one_axis_roots(
    expression: LatexExpression,
    context: EvalContext,
    axis: str,
    bounds: tuple[float, float],
    sample_count: int,
) -> list[float]:
    low, high = bounds
    values: list[tuple[float, float | None]] = []
    for value in linspace(low, high, sample_count):
        try:
            evaluated = float(expression.eval(context, {axis: value}))
        except Exception:
            evaluated = None
        values.append((value, evaluated))

    roots: list[float] = []
    tolerance = 1e-6
    for (left_x, left_y), (right_x, right_y) in zip(values[:-1], values[1:], strict=True):
        if left_y is None or right_y is None:
            continue
        if abs(left_y) <= tolerance:
            roots.append(left_x)
        if left_y == 0.0 or right_y == 0.0:
            continue
        if (left_y < 0.0) == (right_y < 0.0):
            continue
        roots.append(bisect_one_axis_root(expression, context, axis, left_x, right_x, left_y))
    last_x, last_y = values[-1]
    if last_y is not None and abs(last_y) <= tolerance:
        roots.append(last_x)
    return dedupe_roots(roots)


def bisect_one_axis_root(
    expression: LatexExpression,
    context: EvalContext,
    axis: str,
    low: float,
    high: float,
    low_value: float,
) -> float:
    for _ in range(64):
        mid = (low + high) / 2.0
        mid_value = float(expression.eval(context, {axis: mid}))
        if abs(mid_value) <= 1e-10:
            return mid
        if (low_value < 0.0) == (mid_value < 0.0):
            low = mid
            low_value = mid_value
        else:
            high = mid
    return (low + high) / 2.0


def dedupe_roots(roots: list[float]) -> list[float]:
    deduped: list[float] = []
    for root in sorted(roots):
        if deduped and abs(root - deduped[-1]) <= 1e-5:
            deduped[-1] = (deduped[-1] + root) / 2.0
            continue
        deduped.append(root)
    return deduped


def tessellate_implicit_curve_2d(
    item: ClassifiedExpression,
    context: EvalContext,
    a_axis: str,
    b_axis: str,
    extrude_axis: str,
    extrude_value: float,
    a_bounds: tuple[float, float],
    b_bounds: tuple[float, float],
    resolution: int,
) -> GeometryData:
    if item.expression is None:
        raise ValueError("implicit surface missing residual expression")
    grid_resolution = max(24, resolution * 4)
    a_values = linspace(a_bounds[0], a_bounds[1], grid_resolution)
    b_values = linspace(b_bounds[0], b_bounds[1], grid_resolution)
    values: list[list[float | None]] = []
    for b in b_values:
        row: list[float | None] = []
        for a in a_values:
            variables = {a_axis: a, b_axis: b, extrude_axis: extrude_value}
            try:
                row.append(float(item.expression.eval(context, variables)))
            except Exception:
                row.append(None)
        values.append(row)

    points: list[Point] = []
    counts: list[int] = []
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
                append_valid_curve_subsegments(
                    points,
                    counts,
                    item,
                    context,
                    a_axis,
                    b_axis,
                    extrude_axis,
                    extrude_value,
                    hits[0],
                    hits[1],
                )
            elif len(hits) == 4:
                append_valid_curve_subsegments(
                    points,
                    counts,
                    item,
                    context,
                    a_axis,
                    b_axis,
                    extrude_axis,
                    extrude_value,
                    hits[0],
                    hits[1],
                )
                append_valid_curve_subsegments(
                    points,
                    counts,
                    item,
                    context,
                    a_axis,
                    b_axis,
                    extrude_axis,
                    extrude_value,
                    hits[2],
                    hits[3],
                )
    return GeometryData(kind="BasisCurves", points=points, curve_vertex_counts=counts)


def append_valid_curve_subsegments(
    points: list[Point],
    counts: list[int],
    item: ClassifiedExpression,
    context: EvalContext,
    a_axis: str,
    b_axis: str,
    extrude_axis: str,
    extrude_value: float,
    start: tuple[float, float],
    end: tuple[float, float],
) -> None:
    if not item.predicates:
        points.extend(
            [
                make_point(a_axis, b_axis, extrude_axis, start[0], start[1], extrude_value),
                make_point(a_axis, b_axis, extrude_axis, end[0], end[1], extrude_value),
            ]
        )
        counts.append(2)
        return

    samples: list[tuple[Point, bool]] = []
    subdivisions = 16
    for index in range(subdivisions + 1):
        t = index / subdivisions
        a = start[0] + (end[0] - start[0]) * t
        b = start[1] + (end[1] - start[1]) * t
        variables = {a_axis: a, b_axis: b, extrude_axis: extrude_value}
        valid = all(predicate.evaluate(context, variables, tol=1e-5) for predicate in item.predicates)
        samples.append((make_point(a_axis, b_axis, extrude_axis, a, b, extrude_value), valid))

    for left, right in zip(samples[:-1], samples[1:], strict=True):
        if not (left[1] and right[1]):
            continue
        if squared_distance(left[0], right[0]) <= 1e-12:
            continue
        points.extend([left[0], right[0]])
        counts.append(2)


def squared_distance(left: Point, right: Point) -> float:
    return sum((a - b) ** 2 for a, b in zip(left, right, strict=True))


def implicit_axis_bounds(axis: str, bounds: dict[str, tuple[float | None, float | None]], viewport: dict[str, tuple[float, float]]) -> tuple[float, float]:
    low, high = axis_bounds(axis, bounds, viewport)
    if low < high:
        return low, high
    return low, low


def _refine_iso_window(
    expression,
    context: EvalContext,
    a_axis: str,
    b_axis: str,
    extrude_axis: str,
    extrude_value: float,
    a_seed: tuple[float, float],
    b_seed: tuple[float, float],
    scan: int = 32,
) -> tuple[float, float, float, float] | None:
    """Tighten residual axes around the iso-curve sign change for unrestricted 2D contours.

    For a viewport-default residual axis, an ``abs(x)+abs(y)=1.27`` contour can fall entirely
    inside a single coarse cell (no sign change between corners → marching squares emits
    nothing). We coarse-scan the seed window for sign changes and shrink to the bbox of
    those changes so the main pass actually crosses the iso-line.
    """
    a_samples = linspace(a_seed[0], a_seed[1], scan)
    b_samples = linspace(b_seed[0], b_seed[1], scan)
    rows: list[list[float | None]] = []
    for b in b_samples:
        row: list[float | None] = []
        for a in a_samples:
            variables = {a_axis: a, b_axis: b, extrude_axis: extrude_value}
            try:
                row.append(float(expression.eval(context, variables)))
            except Exception:
                row.append(None)
        rows.append(row)
    a_min: float | None = None
    a_max: float | None = None
    b_min: float | None = None
    b_max: float | None = None
    for row in range(len(b_samples)):
        for col in range(len(a_samples)):
            value = rows[row][col]
            if value is None:
                continue
            neighbors: list[float] = []
            if col + 1 < len(a_samples):
                right = rows[row][col + 1]
                if right is not None:
                    neighbors.append(right)
            if row + 1 < len(b_samples):
                below = rows[row + 1][col]
                if below is not None:
                    neighbors.append(below)
            for neighbor in neighbors:
                if value == 0 or neighbor == 0 or (value < 0) != (neighbor < 0):
                    a_val = a_samples[col]
                    b_val = b_samples[row]
                    a_min = a_val if a_min is None else min(a_min, a_val)
                    a_max = a_val if a_max is None else max(a_max, a_val)
                    b_min = b_val if b_min is None else min(b_min, b_val)
                    b_max = b_val if b_max is None else max(b_max, b_val)
                    break
    if a_min is None or b_min is None:
        return None
    pad_a = (a_seed[1] - a_seed[0]) / max(1, scan - 1)
    pad_b = (b_seed[1] - b_seed[0]) / max(1, scan - 1)
    return (
        max(a_seed[0], a_min - 2 * pad_a),
        min(a_seed[1], a_max + 2 * pad_a),
        max(b_seed[0], b_min - 2 * pad_b),
        min(b_seed[1], b_max + 2 * pad_b),
    )


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


def tessellate_axis_aligned_ellipsoid(
    item: ClassifiedExpression,
    context: EvalContext,
    resolution: int,
) -> GeometryData | None:
    if item.expression is None:
        return None
    profile = fit_axis_aligned_ellipsoid(item.expression, context)
    if profile is None:
        return None
    latitude_segments = max(8, min(32, resolution))
    longitude_segments = max(16, min(48, resolution * 2))
    geometry = build_axis_aligned_ellipsoid_mesh(profile, latitude_segments, longitude_segments)
    if item.predicates:
        return clip_mesh_faces_to_predicates(geometry, item, context)
    return geometry


def clip_mesh_faces_to_predicates(
    geometry: GeometryData,
    item: ClassifiedExpression,
    context: EvalContext,
) -> GeometryData:
    points: list[Point] = []
    counts: list[int] = []
    indices: list[int] = []
    remap: dict[int, int] = {}
    cursor = 0
    for count in geometry.face_vertex_counts:
        face = geometry.face_vertex_indices[cursor : cursor + count]
        cursor += count
        if len(face) != count:
            continue
        if not all(point_satisfies_predicates(geometry.points[index], item, context) for index in face):
            continue
        counts.append(count)
        for index in face:
            if index not in remap:
                remap[index] = len(points)
                points.append(geometry.points[index])
            indices.append(remap[index])
    return GeometryData(kind="Mesh", points=points, face_vertex_counts=counts, face_vertex_indices=indices)


def point_satisfies_predicates(
    point: Point,
    item: ClassifiedExpression,
    context: EvalContext,
) -> bool:
    variables = dict(zip(AXES, point, strict=True))
    return all(predicate.evaluate(context, variables, tol=1e-5) for predicate in item.predicates)


def fit_axis_aligned_ellipsoid(
    expression: LatexExpression,
    context: EvalContext,
) -> AxisAlignedEllipsoid | None:
    def evaluate(variables: dict[str, float]) -> float:
        value = expression.eval(context, variables)
        if not math.isfinite(value):
            raise ValueError("non-finite residual")
        return float(value)

    origin = {axis: 0.0 for axis in AXES}
    try:
        f0 = evaluate(origin)
        plus: dict[str, float] = {}
        minus: dict[str, float] = {}
        for axis in AXES:
            plus_vars = dict(origin)
            minus_vars = dict(origin)
            plus_vars[axis] = QUADRIC_FIT_DELTA
            minus_vars[axis] = -QUADRIC_FIT_DELTA
            plus[axis] = evaluate(plus_vars)
            minus[axis] = evaluate(minus_vars)
    except Exception:
        return None

    coefficients: list[float] = []
    linear_terms: list[float] = []
    for axis in AXES:
        a = (plus[axis] + minus[axis] - 2.0 * f0) / (2.0 * QUADRIC_FIT_DELTA * QUADRIC_FIT_DELTA)
        b = (plus[axis] - minus[axis]) / (2.0 * QUADRIC_FIT_DELTA)
        coefficients.append(a)
        linear_terms.append(b)

    tolerance = max(QUADRIC_FIT_TOLERANCE, max(abs(value) for value in [f0, *plus.values(), *minus.values()]) * 1e-6)
    for left_index, left_axis in enumerate(AXES):
        for right_axis in AXES[left_index + 1 :]:
            pair_vars = dict(origin)
            pair_vars[left_axis] = QUADRIC_FIT_DELTA
            pair_vars[right_axis] = QUADRIC_FIT_DELTA
            try:
                cross = evaluate(pair_vars) - plus[left_axis] - plus[right_axis] + f0
            except Exception:
                return None
            if abs(cross) > tolerance:
                return None

    if all(coefficient < -QUADRIC_FIT_TOLERANCE for coefficient in coefficients):
        coefficients = [-coefficient for coefficient in coefficients]
        linear_terms = [-term for term in linear_terms]
        orientation = -1.0
    elif all(coefficient > QUADRIC_FIT_TOLERANCE for coefficient in coefficients):
        orientation = 1.0
    else:
        return None

    center = tuple(-term / (2.0 * coefficient) for term, coefficient in zip(linear_terms, coefficients, strict=True))
    try:
        center_value = orientation * evaluate(dict(zip(AXES, center, strict=True)))
    except Exception:
        return None
    if center_value >= -QUADRIC_FIT_TOLERANCE:
        return None

    radii_squared = [-center_value / coefficient for coefficient in coefficients]
    if any(value <= 0.0 or not math.isfinite(value) for value in radii_squared):
        return None
    radii = tuple(math.sqrt(value) for value in radii_squared)
    profile = AxisAlignedEllipsoid(center=center, radii=radii, coefficients=tuple(coefficients))
    if not axis_aligned_ellipsoid_boundary_matches(expression, context, orientation, profile):
        return None
    return profile


def axis_aligned_ellipsoid_boundary_matches(
    expression: LatexExpression,
    context: EvalContext,
    orientation: float,
    profile: AxisAlignedEllipsoid,
) -> bool:
    scale = max(abs(coefficient) for coefficient in profile.coefficients)
    tolerance = max(1e-4, scale * max(profile.radii) ** 2 * 1e-5)
    samples: list[tuple[float, float, float]] = []
    for axis_index in range(3):
        for sign in (-1.0, 1.0):
            point = list(profile.center)
            point[axis_index] += sign * profile.radii[axis_index]
            samples.append(tuple(point))
    diagonal_scale = 1.0 / math.sqrt(3.0)
    samples.append(
        tuple(
            center + radius * diagonal_scale
            for center, radius in zip(profile.center, profile.radii, strict=True)
        )
    )
    for point in samples:
        variables = dict(zip(AXES, point, strict=True))
        try:
            residual = orientation * float(expression.eval(context, variables))
        except Exception:
            return False
        if abs(residual) > tolerance:
            return False
    return True


def build_axis_aligned_ellipsoid_mesh(
    profile: AxisAlignedEllipsoid,
    latitude_segments: int,
    longitude_segments: int,
) -> GeometryData:
    points: list[Point] = []
    counts: list[int] = []
    indices: list[int] = []
    center_x, center_y, center_z = profile.center
    radius_x, radius_y, radius_z = profile.radii

    north_index = len(points)
    points.append((center_x, center_y, center_z + radius_z))
    ring_starts: list[int] = []
    for lat_index in range(1, latitude_segments):
        theta = math.pi * lat_index / latitude_segments
        ring_starts.append(len(points))
        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)
        for lon_index in range(longitude_segments):
            phi = 2.0 * math.pi * lon_index / longitude_segments
            points.append(
                (
                    center_x + radius_x * sin_theta * math.cos(phi),
                    center_y + radius_y * sin_theta * math.sin(phi),
                    center_z + radius_z * cos_theta,
                )
            )
    south_index = len(points)
    points.append((center_x, center_y, center_z - radius_z))

    first_ring = ring_starts[0]
    for lon_index in range(longitude_segments):
        next_lon = (lon_index + 1) % longitude_segments
        counts.append(3)
        indices.extend([north_index, first_ring + lon_index, first_ring + next_lon])

    for ring_index in range(len(ring_starts) - 1):
        lower = ring_starts[ring_index]
        upper = ring_starts[ring_index + 1]
        for lon_index in range(longitude_segments):
            next_lon = (lon_index + 1) % longitude_segments
            counts.append(4)
            indices.extend([lower + lon_index, upper + lon_index, upper + next_lon, lower + next_lon])

    last_ring = ring_starts[-1]
    for lon_index in range(longitude_segments):
        next_lon = (lon_index + 1) % longitude_segments
        counts.append(3)
        indices.extend([south_index, last_ring + next_lon, last_ring + lon_index])
    return GeometryData(kind="Mesh", points=points, face_vertex_counts=counts, face_vertex_indices=indices)


def tessellate_implicit_surface_3axis_marching(
    item: ClassifiedExpression,
    context: EvalContext,
    resolution: int,
) -> GeometryData:
    """Marching-squares slice-and-stitch fallback for 3-axis implicit surfaces.

    Used when the quadratic-profile fast path cannot fit the cross-section. Picks the
    shortest constant-bounded predicate axis as the slicing axis, marches squares at each
    slice, and stitches adjacent slices via nearest-segment matching. Bbox is adaptively
    zoomed so very small features remain visible.
    """
    if item.expression is None:
        raise ValueError("implicit surface missing residual expression")
    bounds = collect_constant_bounds(item.predicates, context)
    viewport = item.ir.source.viewport_bounds
    extrude_axis = _pick_3axis_extrude_axis(bounds, item.ir.expr_id)
    a_axis, b_axis = (axis for axis in AXES if axis != extrude_axis)
    a_low, a_high = axis_bounds(a_axis, bounds, viewport)
    b_low, b_high = axis_bounds(b_axis, bounds, viewport)
    e_low, e_high = axis_bounds(extrude_axis, bounds, viewport)
    if e_low == e_high:
        e_high = e_low + 1e-6
    grid_resolution = max(8, resolution)
    a_low, a_high, b_low, b_high = _refine_3axis_bbox(
        item, context, a_axis, b_axis, extrude_axis,
        a_low, a_high, b_low, b_high, e_low, e_high,
    )
    a_values = linspace(a_low, a_high, grid_resolution)
    b_values = linspace(b_low, b_high, grid_resolution)
    span_a = max(1e-6, (a_high - a_low) / grid_resolution)
    target_slices = max(2, int(round((e_high - e_low) / span_a)))
    slice_count = max(2, min(grid_resolution * 2, target_slices))
    e_values = linspace(e_low, e_high, slice_count)
    slice_segments: list[list[tuple[tuple[float, float], tuple[float, float]]]] = []
    for e in e_values:
        slice_segments.append(_contour_segments_at_slice(item, context, a_axis, b_axis, extrude_axis, e, a_values, b_values))

    points: list[Point] = []
    counts: list[int] = []
    indices: list[int] = []
    for layer in range(len(e_values) - 1):
        s_low = slice_segments[layer]
        s_high = slice_segments[layer + 1]
        if not s_low or not s_high:
            continue
        e0 = e_values[layer]
        e1 = e_values[layer + 1]
        for seg_low in s_low:
            seg_high = _nearest_segment(seg_low, s_high)
            if seg_high is None:
                continue
            seg_high = _orient_to(seg_low, seg_high)
            p0 = make_point(a_axis, b_axis, extrude_axis, seg_low[0][0], seg_low[0][1], e0)
            p1 = make_point(a_axis, b_axis, extrude_axis, seg_low[1][0], seg_low[1][1], e0)
            p2 = make_point(a_axis, b_axis, extrude_axis, seg_high[1][0], seg_high[1][1], e1)
            p3 = make_point(a_axis, b_axis, extrude_axis, seg_high[0][0], seg_high[0][1], e1)
            quad = [p0, p1, p2, p3]
            variables = [dict(zip(AXES, p, strict=True)) for p in quad]
            if not all(all(predicate.evaluate(context, variable, tol=5e-3) for predicate in item.predicates) for variable in variables):
                continue
            base = len(points)
            points.extend(quad)
            counts.append(4)
            indices.extend([base, base + 1, base + 2, base + 3])
    if not counts:
        raise ValueError("implicit surface requires a supported bounded three-axis form")
    return GeometryData(kind="Mesh", points=points, face_vertex_counts=counts, face_vertex_indices=indices)


def _pick_3axis_extrude_axis(
    bounds: dict[str, tuple[float | None, float | None]],
    expr_id: str,
) -> str:
    bounded: list[tuple[float, str]] = []
    degenerate: list[str] = []
    for axis in AXES:
        low, high = bounds.get(axis, (None, None))
        if low is None or high is None:
            continue
        if low >= high:
            degenerate.append(axis)
            continue
        bounded.append((high - low, axis))
    if bounded:
        bounded.sort()
        return bounded[0][1]
    if degenerate:
        return degenerate[0]
    raise ValueError(f"Implicit surface {expr_id} with 3-axis residual has no constant-bounded axis")


def _refine_3axis_bbox(
    item: ClassifiedExpression,
    context: EvalContext,
    a_axis: str,
    b_axis: str,
    extrude_axis: str,
    a_low: float,
    a_high: float,
    b_low: float,
    b_high: float,
    e_low: float,
    e_high: float,
) -> tuple[float, float, float, float]:
    """Two-stage scan: coarse, then if no sign change found, zoom around argmin |residual|.

    Without bbox refinement, a tiny implicit surface (e.g. radius 0.06 in viewport ±12)
    is invisible to a fixed-resolution marching grid because every cell straddles the
    surface or is fully outside.
    """
    if item.expression is None:
        return a_low, a_high, b_low, b_high
    bbox = _scan_for_sign_change(item, context, a_axis, b_axis, extrude_axis, a_low, a_high, b_low, b_high, e_low, e_high, scan=32)
    if bbox is not None:
        return bbox
    near = _argmin_abs_residual(item, context, a_axis, b_axis, extrude_axis, a_low, a_high, b_low, b_high, e_low, e_high, scan=64)
    if near is None:
        return a_low, a_high, b_low, b_high
    a_center, b_center, scale = near
    half = max(scale * 4.0, 1e-3)
    bbox = _scan_for_sign_change(
        item, context, a_axis, b_axis, extrude_axis,
        max(a_low, a_center - half), min(a_high, a_center + half),
        max(b_low, b_center - half), min(b_high, b_center + half),
        e_low, e_high, scan=48,
    )
    if bbox is not None:
        return bbox
    half = max(half * 0.25, 1e-4)
    return (
        max(a_low, a_center - half),
        min(a_high, a_center + half),
        max(b_low, b_center - half),
        min(b_high, b_center + half),
    )


def _scan_for_sign_change(
    item: ClassifiedExpression,
    context: EvalContext,
    a_axis: str,
    b_axis: str,
    extrude_axis: str,
    a_low: float,
    a_high: float,
    b_low: float,
    b_high: float,
    e_low: float,
    e_high: float,
    scan: int,
) -> tuple[float, float, float, float] | None:
    if item.expression is None or scan < 3 or a_high <= a_low or b_high <= b_low:
        return None
    a_samples = linspace(a_low, a_high, scan)
    b_samples = linspace(b_low, b_high, scan)
    e_samples = linspace(e_low, e_high, max(3, scan // 4))
    a_min: float | None = None
    a_max: float | None = None
    b_min: float | None = None
    b_max: float | None = None
    for e in e_samples:
        prev_row: list[float | None] = []
        for b in b_samples:
            row: list[float | None] = []
            for a in a_samples:
                variables = {a_axis: a, b_axis: b, extrude_axis: e}
                try:
                    row.append(float(item.expression.eval(context, variables)))
                except Exception:
                    row.append(None)
            for col, value in enumerate(row):
                if value is None:
                    continue
                neighbors = []
                if col + 1 < len(row):
                    neighbors.append(row[col + 1])
                if prev_row and col < len(prev_row):
                    neighbors.append(prev_row[col])
                for neighbor in neighbors:
                    if neighbor is None:
                        continue
                    if (value <= 0) != (neighbor <= 0) or value == 0 or neighbor == 0:
                        a_val = a_samples[col]
                        a_min = a_val if a_min is None else min(a_min, a_val)
                        a_max = a_val if a_max is None else max(a_max, a_val)
                        b_min = b if b_min is None else min(b_min, b)
                        b_max = b if b_max is None else max(b_max, b)
                        break
            prev_row = row
    if a_min is None or b_min is None:
        return None
    a_step = (a_high - a_low) / max(1, scan - 1)
    b_step = (b_high - b_low) / max(1, scan - 1)
    a_min = max(a_low, a_min - 2 * a_step)
    a_max = min(a_high, a_max + 2 * a_step)
    b_min = max(b_low, b_min - 2 * b_step)
    b_max = min(b_high, b_max + 2 * b_step)
    if a_max - a_min < 1e-6 or b_max - b_min < 1e-6:
        return None
    return a_min, a_max, b_min, b_max


def _argmin_abs_residual(
    item: ClassifiedExpression,
    context: EvalContext,
    a_axis: str,
    b_axis: str,
    extrude_axis: str,
    a_low: float,
    a_high: float,
    b_low: float,
    b_high: float,
    e_low: float,
    e_high: float,
    scan: int,
) -> tuple[float, float, float] | None:
    if item.expression is None:
        return None
    a_samples = linspace(a_low, a_high, scan)
    b_samples = linspace(b_low, b_high, scan)
    e_mid = (e_low + e_high) / 2.0
    best_residual: float | None = None
    best_a: float | None = None
    best_b: float | None = None
    for b in b_samples:
        for a in a_samples:
            variables = {a_axis: a, b_axis: b, extrude_axis: e_mid}
            try:
                value = abs(float(item.expression.eval(context, variables)))
            except Exception:
                continue
            if best_residual is None or value < best_residual:
                best_residual = value
                best_a = a
                best_b = b
    if best_a is None or best_b is None:
        return None
    a_step = (a_high - a_low) / max(1, scan - 1)
    b_step = (b_high - b_low) / max(1, scan - 1)
    return best_a, best_b, max(a_step, b_step)


def _contour_segments_at_slice(
    item: ClassifiedExpression,
    context: EvalContext,
    a_axis: str,
    b_axis: str,
    extrude_axis: str,
    e: float,
    a_values: list[float],
    b_values: list[float],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    if item.expression is None:
        return []
    values: list[list[float | None]] = []
    for b in b_values:
        row: list[float | None] = []
        for a in a_values:
            variables = {a_axis: a, b_axis: b, extrude_axis: e}
            try:
                row.append(float(item.expression.eval(context, variables)))
            except Exception:
                row.append(None)
        values.append(row)
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
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
    return segments


def _segment_midpoint(segment: tuple[tuple[float, float], tuple[float, float]]) -> tuple[float, float]:
    return ((segment[0][0] + segment[1][0]) / 2.0, (segment[0][1] + segment[1][1]) / 2.0)


def _nearest_segment(
    target: tuple[tuple[float, float], tuple[float, float]],
    candidates: list[tuple[tuple[float, float], tuple[float, float]]],
) -> tuple[tuple[float, float], tuple[float, float]] | None:
    if not candidates:
        return None
    target_mid = _segment_midpoint(target)
    best = None
    best_distance = math.inf
    for segment in candidates:
        mid = _segment_midpoint(segment)
        distance = (mid[0] - target_mid[0]) ** 2 + (mid[1] - target_mid[1]) ** 2
        if distance < best_distance:
            best = segment
            best_distance = distance
    return best


def _orient_to(
    reference: tuple[tuple[float, float], tuple[float, float]],
    segment: tuple[tuple[float, float], tuple[float, float]],
) -> tuple[tuple[float, float], tuple[float, float]]:
    d_keep = (
        (reference[0][0] - segment[0][0]) ** 2
        + (reference[0][1] - segment[0][1]) ** 2
        + (reference[1][0] - segment[1][0]) ** 2
        + (reference[1][1] - segment[1][1]) ** 2
    )
    d_swap = (
        (reference[0][0] - segment[1][0]) ** 2
        + (reference[0][1] - segment[1][1]) ** 2
        + (reference[1][0] - segment[0][0]) ** 2
        + (reference[1][1] - segment[0][1]) ** 2
    )
    return segment if d_keep <= d_swap else (segment[1], segment[0])
