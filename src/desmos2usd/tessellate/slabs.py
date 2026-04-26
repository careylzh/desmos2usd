from __future__ import annotations

import ast

from desmos2usd.eval.context import EvalContext
from desmos2usd.parse.classify import ClassifiedExpression
from desmos2usd.parse.latex_subset import LatexExpression
from desmos2usd.parse.predicates import ComparisonPredicate, collect_constant_bounds, single_identifier
from desmos2usd.tessellate.cylinders import tessellate_circular_inequality_extrusion
from desmos2usd.tessellate.mesh import GeometryData, Point, linspace
from desmos2usd.tessellate.surfaces import (
    DEFAULT_BOUNDS,
    axis_bounds,
    broad_bounds_from_constants,
    numeric_constants,
    numeric_constants_for_item,
    point_from_variables,
)


def tessellate_inequality_region(item: ClassifiedExpression, context: EvalContext, resolution: int = 14) -> GeometryData:
    if not item.inequality:
        raise ValueError("inequality region missing predicate")
    flat = _flat_region_geometry(item, context, resolution)
    if flat is not None:
        return flat
    circular = tessellate_circular_inequality_extrusion(item, context, resolution=max(16, resolution * 4))
    if circular is not None and mesh_vertices_satisfy_predicates(item, context, circular):
        return circular
    band = extract_band(item.inequality)
    if band:
        axis, lower, upper, lower_closed, upper_closed = band
        geometry = tessellate_band(
            item,
            context,
            axis,
            lower,
            upper,
            lower_closed,
            upper_closed,
            resolution,
        )
        if geometry.face_count and mesh_vertices_satisfy_predicates(item, context, geometry):
            return geometry
    try:
        geometry = tessellate_extruded_2d_region(item, context, resolution=max(16, resolution * 6))
        if geometry.face_count and mesh_vertices_satisfy_predicates(item, context, geometry):
            return geometry
    except Exception:
        pass
    try:
        return tessellate_box(item, context)
    except Exception:
        return tessellate_sampled_inequality_region(item, context, resolution=max(8, resolution * 2))


def extract_band(predicate: ComparisonPredicate) -> tuple[str, LatexExpression, LatexExpression, bool, bool] | None:
    if len(predicate.terms) == 3 and len(predicate.ops) == 2:
        axis = single_identifier(predicate.terms[1])
        if axis in {"x", "y", "z"} and predicate.ops[0] in {"<=", "<"} and predicate.ops[1] in {"<=", "<"}:
            return (
                axis,
                predicate.terms[0],
                predicate.terms[2],
                predicate.ops[0] == "<=",
                predicate.ops[1] == "<=",
            )
        if axis in {"x", "y", "z"} and predicate.ops[0] in {">=", ">"} and predicate.ops[1] in {">=", ">"}:
            return (
                axis,
                predicate.terms[2],
                predicate.terms[0],
                predicate.ops[1] == ">=",
                predicate.ops[0] == ">=",
            )
    return None


def tessellate_band(
    item: ClassifiedExpression,
    context: EvalContext,
    axis: str,
    lower: LatexExpression,
    upper: LatexExpression,
    lower_closed: bool,
    upper_closed: bool,
    resolution: int,
) -> GeometryData:
    domain_axes = [name for name in ("x", "y", "z") if name != axis]
    bounds = collect_constant_bounds(item.predicates, context)
    fallback_bounds = item.ir.source.viewport_bounds
    a0, a1 = axis_bounds(domain_axes[0], bounds, fallback_bounds)
    b0, b1 = axis_bounds(domain_axes[1], bounds, fallback_bounds)
    points: list[Point] = []
    params: list[dict[str, float]] = []
    for layer, surface in enumerate([lower, upper]):
        for b in linspace(b0, b1, resolution):
            for a in linspace(a0, a1, resolution):
                variables = {domain_axes[0]: a, domain_axes[1]: b}
                variables[axis] = surface.eval(context, variables)
                points.append(point_from_variables(variables))
                params.append(dict(variables))
    counts: list[int] = []
    indices: list[int] = []
    layer_size = resolution * resolution
    for layer_offset, reverse in [(0, False), (layer_size, True)]:
        for row in range(resolution - 1):
            for col in range(resolution - 1):
                a = layer_offset + row * resolution + col
                quad = [a, a + 1, a + resolution + 1, a + resolution]
                if reverse:
                    quad.reverse()
                counts.append(4)
                indices.extend(quad)
    for row in [0, resolution - 1]:
        for col in range(resolution - 1):
            low_a = row * resolution + col
            low_b = low_a + 1
            high_b = layer_size + low_b
            high_a = layer_size + low_a
            counts.append(4)
            indices.extend([low_a, low_b, high_b, high_a])
    for col in [0, resolution - 1]:
        for row in range(resolution - 1):
            low_a = row * resolution + col
            low_b = low_a + resolution
            high_b = layer_size + low_b
            high_a = layer_size + low_a
            counts.append(4)
            indices.extend([low_a, low_b, high_b, high_a])
    return GeometryData(kind="Mesh", points=points, face_vertex_counts=counts, face_vertex_indices=indices, sample_parameters=params)


def tessellate_box(item: ClassifiedExpression, context: EvalContext) -> GeometryData:
    bounds = collect_constant_bounds(item.predicates, context)
    fallback_bounds = item.ir.source.viewport_bounds
    xb = axis_bounds("x", bounds, fallback_bounds)
    yb = axis_bounds("y", bounds, fallback_bounds)
    zb = axis_bounds("z", bounds, fallback_bounds)
    points: list[Point] = [
        (xb[0], yb[0], zb[0]),
        (xb[1], yb[0], zb[0]),
        (xb[1], yb[1], zb[0]),
        (xb[0], yb[1], zb[0]),
        (xb[0], yb[0], zb[1]),
        (xb[1], yb[0], zb[1]),
        (xb[1], yb[1], zb[1]),
        (xb[0], yb[1], zb[1]),
    ]
    counts = [4, 4, 4, 4, 4, 4]
    indices = [
        0,
        1,
        2,
        3,
        4,
        7,
        6,
        5,
        0,
        4,
        5,
        1,
        1,
        5,
        6,
        2,
        2,
        6,
        7,
        3,
        3,
        7,
        4,
        0,
    ]
    valid_points = []
    for point in points:
        variables = {"x": point[0], "y": point[1], "z": point[2]}
        valid_points.append(all(predicate.evaluate(context, variables, tol=1e-5) for predicate in item.predicates))
    if not all(valid_points):
        raise ValueError(f"Inequality region for {item.ir.expr_id} did not resolve to a bounded box")
    return GeometryData(kind="Mesh", points=points, face_vertex_counts=counts, face_vertex_indices=indices)


def tessellate_extruded_2d_region(item: ClassifiedExpression, context: EvalContext, resolution: int) -> GeometryData:
    if not item.inequality:
        raise ValueError("inequality region missing predicate")
    bounds = collect_constant_bounds(item.predicates, context)
    for extrude_axis in ("x", "y", "z"):
        low, high = bounds.get(extrude_axis, (None, None))
        if low is None or high is None or low >= high:
            continue
        shape_axes = [axis for axis in ("x", "y", "z") if axis != extrude_axis]
        if not predicate_identifiers(item.inequality).issubset(set(shape_axes)):
            continue
        try:
            geometry = tessellate_function_band_extrusion(
                item,
                context,
                shape_axes,
                extrude_axis,
                (low, high),
                bounds,
                resolution,
            )
            if geometry.face_count:
                return geometry
        except Exception:
            pass
        shape_bounds = infer_2d_region_bounds(item, context, shape_axes, extrude_axis, bounds)
        try:
            geometry = tessellate_function_band_extrusion(
                item,
                context,
                shape_axes,
                extrude_axis,
                (low, high),
                shape_bounds,
                resolution,
            )
            if geometry.face_count:
                return geometry
        except Exception:
            pass
        geometry = sampled_extrusion_mesh(item, context, shape_axes, extrude_axis, (low, high), shape_bounds, resolution)
        if geometry.face_count:
            return geometry
    raise ValueError(f"Inequality region for {item.ir.expr_id} did not resolve to an extruded 2D region")


def predicate_identifiers(predicate: ComparisonPredicate) -> set[str]:
    identifiers: set[str] = set()
    for term in predicate.terms:
        identifiers.update(term.identifiers & {"x", "y", "z"})
    return identifiers


def _referenced_axes(item: ClassifiedExpression) -> set[str]:
    axes: set[str] = set()
    for predicate in item.predicates:
        axes.update(predicate_identifiers(predicate))
    if item.inequality:
        axes.update(predicate_identifiers(item.inequality))
    return axes


def _flat_region_geometry(
    item: ClassifiedExpression,
    context: EvalContext,
    resolution: int,
) -> GeometryData | None:
    """Render a 2D inequality region at z=0 when no predicate mentions the third axis.

    Desmos 3D renders expressions like `20>y>-20 {-225<x<225}` as a flat ground-plane
    rectangle rather than extruding to a viewport-sized 3D volume. We mirror that: when
    exactly one of (x, y, z) is entirely absent from the inequality and its restrictions,
    tessellate a flat rectangle at that axis = 0.
    """
    referenced = _referenced_axes(item)
    missing = [axis for axis in ("x", "y", "z") if axis not in referenced]
    if len(missing) != 1:
        return None
    flat_axis = missing[0]
    bounds = collect_constant_bounds(item.predicates, context)
    shape_axes = [axis for axis in ("x", "y", "z") if axis != flat_axis]
    ranges: dict[str, tuple[float, float]] = {}
    for axis in shape_axes:
        low, high = bounds.get(axis, (None, None))
        if low is None or high is None or low >= high:
            return None
        ranges[axis] = (low, high)
    a_axis, b_axis = shape_axes
    a_values = linspace(ranges[a_axis][0], ranges[a_axis][1], resolution)
    b_values = linspace(ranges[b_axis][0], ranges[b_axis][1], resolution)
    points: list[Point] = []
    valid_grid: list[list[bool]] = []
    for b in b_values:
        row_valid: list[bool] = []
        for a in a_values:
            variables = {a_axis: a, b_axis: b, flat_axis: 0.0}
            points.append((variables["x"], variables["y"], variables["z"]))
            row_valid.append(all(predicate.evaluate(context, variables, tol=1e-5) for predicate in item.predicates))
        valid_grid.append(row_valid)
    counts: list[int] = []
    indices: list[int] = []
    width = resolution
    for row in range(resolution - 1):
        for col in range(resolution - 1):
            if not all(
                (
                    valid_grid[row][col],
                    valid_grid[row][col + 1],
                    valid_grid[row + 1][col + 1],
                    valid_grid[row + 1][col],
                )
            ):
                continue
            a = row * width + col
            counts.append(4)
            indices.extend([a, a + 1, a + width + 1, a + width])
    if not counts:
        return None
    return GeometryData(kind="Mesh", points=points, face_vertex_counts=counts, face_vertex_indices=indices)


def infer_2d_region_bounds(
    item: ClassifiedExpression,
    context: EvalContext,
    shape_axes: list[str],
    extrude_axis: str,
    bounds: dict[str, tuple[float | None, float | None]],
) -> dict[str, tuple[float | None, float | None]]:
    constants = shape_numeric_constants(item, set(shape_axes))
    if not constants:
        constants = numeric_constants_for_item(item)
    broad_low, broad_high = broad_bounds_from_constants(constants)
    inferred = dict(bounds)
    apply_function_band_bounds(item, context, shape_axes, inferred, broad_low, broad_high)

    ranges: dict[str, tuple[float, float]] = {}
    for axis in shape_axes:
        low, high = inferred.get(axis, (None, None))
        ranges[axis] = (broad_low if low is None else low, broad_high if high is None else high)

    active: dict[str, list[float]] = {axis: [] for axis in shape_axes}
    a_axis, b_axis = shape_axes
    a0, a1 = ranges[a_axis]
    b0, b1 = ranges[b_axis]
    extrude_low, extrude_high = bounds[extrude_axis]
    assert extrude_low is not None and extrude_high is not None
    extrude_mid = (extrude_low + extrude_high) / 2.0
    scan_count = 96
    for b in linspace(b0, b1, scan_count):
        for a in linspace(a0, a1, scan_count):
            variables = {a_axis: a, b_axis: b, extrude_axis: extrude_mid}
            if all(predicate.evaluate(context, variables, tol=1e-5) for predicate in item.predicates):
                active[a_axis].append(a)
                active[b_axis].append(b)

    for axis in shape_axes:
        existing_low, existing_high = inferred.get(axis, (None, None))
        values = active[axis]
        if not values:
            continue
        step = (ranges[axis][1] - ranges[axis][0]) / float(scan_count - 1)
        low = existing_low if existing_low is not None else max(ranges[axis][0], min(values) - step)
        high = existing_high if existing_high is not None else min(ranges[axis][1], max(values) + step)
        if low < high:
            inferred[axis] = (low, high)
    return inferred


def shape_numeric_constants(item: ClassifiedExpression, shape_axes: set[str]) -> list[float]:
    expressions: list[LatexExpression] = []
    if item.inequality:
        expressions.extend(item.inequality.terms)
    for predicate in item.predicates:
        if predicate_identifiers(predicate).issubset(shape_axes):
            expressions.extend(predicate.terms)
    constants: list[float] = []
    for expression in expressions:
        constants.extend(numeric_constants(expression))
    return constants


def apply_function_band_bounds(
    item: ClassifiedExpression,
    context: EvalContext,
    shape_axes: list[str],
    bounds: dict[str, tuple[float | None, float | None]],
    broad_low: float,
    broad_high: float,
) -> None:
    for axis in shape_axes:
        lower_exprs, upper_exprs = function_bounds_for_axis(item.predicates, axis)
        if not lower_exprs and not upper_exprs:
            continue
        other_axes = [other for other in shape_axes if other != axis]
        samples = variable_samples(other_axes, bounds, broad_low, broad_high)
        low_candidates = evaluate_bound_expressions(lower_exprs, context, samples)
        high_candidates = evaluate_bound_expressions(upper_exprs, context, samples)
        previous_low, previous_high = bounds.get(axis, (None, None))
        low = previous_low
        high = previous_high
        if low_candidates:
            candidate_low = min(low_candidates)
            low = candidate_low if low is None else max(low, candidate_low)
        if high_candidates:
            candidate_high = max(high_candidates)
            high = candidate_high if high is None else min(high, candidate_high)
        if low is not None and high is not None and (previous_low is None or previous_high is None):
            pad = max(0.05, (high - low) * 0.05)
            low -= pad
            high += pad
        if low is not None or high is not None:
            bounds[axis] = (low, high)


def function_bounds_for_axis(
    predicates: list[ComparisonPredicate],
    axis: str,
) -> tuple[list[LatexExpression], list[LatexExpression]]:
    lower: list[LatexExpression] = []
    upper: list[LatexExpression] = []
    for predicate in predicates:
        if len(predicate.terms) == 3 and len(predicate.ops) == 2:
            middle_axis = single_identifier(predicate.terms[1])
            if middle_axis == axis and axis not in predicate.terms[0].identifiers and axis not in predicate.terms[2].identifiers:
                if predicate.ops[0] in {"<=", "<"} and predicate.ops[1] in {"<=", "<"}:
                    lower.append(predicate.terms[0])
                    upper.append(predicate.terms[2])
                elif predicate.ops[0] in {">=", ">"} and predicate.ops[1] in {">=", ">"}:
                    lower.append(predicate.terms[2])
                    upper.append(predicate.terms[0])
            continue
        if len(predicate.terms) != 2 or len(predicate.ops) != 1:
            continue
        left, right = predicate.terms
        op = predicate.ops[0]
        left_signed = signed_axis_identifier(left, axis)
        right_signed = signed_axis_identifier(right, axis)
        if left_signed is not None and axis not in right.identifiers:
            add_signed_bound(lower, upper, left_signed, op, right)
        elif right_signed is not None and axis not in left.identifiers:
            reversed_op = reverse_op(op)
            add_signed_bound(lower, upper, right_signed, reversed_op, left)
    return lower, upper


def signed_axis_identifier(expression: LatexExpression, axis: str) -> int | None:
    tree = expression.tree.body
    if isinstance(tree, ast.Name) and tree.id == axis:
        return 1
    if (
        isinstance(tree, ast.UnaryOp)
        and isinstance(tree.op, ast.USub)
        and isinstance(tree.operand, ast.Name)
        and tree.operand.id == axis
    ):
        return -1
    return None


def add_signed_bound(
    lower: list[LatexExpression],
    upper: list[LatexExpression],
    sign: int,
    op: str,
    expression: LatexExpression,
) -> None:
    if sign == 1:
        if op in {"<=", "<"}:
            upper.append(expression)
        elif op in {">=", ">"}:
            lower.append(expression)
    elif sign == -1:
        negated = LatexExpression.parse(f"-({expression.latex})")
        if op in {"<=", "<"}:
            lower.append(negated)
        elif op in {">=", ">"}:
            upper.append(negated)


def reverse_op(op: str) -> str:
    return {"<=": ">=", "<": ">", ">=": "<=", ">": "<"}.get(op, op)


def variable_samples(
    axes: list[str],
    bounds: dict[str, tuple[float | None, float | None]],
    broad_low: float,
    broad_high: float,
) -> list[dict[str, float]]:
    if not axes:
        return [{}]
    sample_axes: list[tuple[str, list[float]]] = []
    for axis in axes:
        low, high = bounds.get(axis, (None, None))
        sample_low = broad_low if low is None else low
        sample_high = broad_high if high is None else high
        sample_axes.append((axis, linspace(sample_low, sample_high, 24)))
    samples: list[dict[str, float]] = [{}]
    for axis, values in sample_axes:
        samples = [dict(sample, **{axis: value}) for sample in samples for value in values]
    return samples


def evaluate_bound_expressions(
    expressions: list[LatexExpression],
    context: EvalContext,
    samples: list[dict[str, float]],
) -> list[float]:
    values: list[float] = []
    for expression in expressions:
        for variables in samples:
            try:
                values.append(expression.eval(context, variables))
            except Exception:
                continue
    return values


def sampled_extrusion_mesh(
    item: ClassifiedExpression,
    context: EvalContext,
    shape_axes: list[str],
    extrude_axis: str,
    extrude_bounds: tuple[float, float],
    bounds: dict[str, tuple[float | None, float | None]],
    resolution: int,
) -> GeometryData:
    a_axis, b_axis = shape_axes
    fallback_bounds = item.ir.source.viewport_bounds
    a0, a1 = axis_bounds(a_axis, bounds, fallback_bounds)
    b0, b1 = axis_bounds(b_axis, bounds, fallback_bounds)
    if a0 >= a1 or b0 >= b1:
        raise ValueError(f"Inequality region for {item.ir.expr_id} has empty inferred extrusion bounds")
    points: list[Point] = []
    counts: list[int] = []
    indices: list[int] = []
    a_values = linspace(a0, a1, resolution + 1)
    b_values = linspace(b0, b1, resolution + 1)
    low, high = extrude_bounds
    for ia in range(resolution):
        for ib in range(resolution):
            corners_2d = [
                (a_values[ia], b_values[ib]),
                (a_values[ia + 1], b_values[ib]),
                (a_values[ia + 1], b_values[ib + 1]),
                (a_values[ia], b_values[ib + 1]),
            ]
            if all(extruded_corner_satisfies(item, context, shape_axes, extrude_axis, pair, low, high) for pair in corners_2d):
                add_extruded_cell(points, counts, indices, shape_axes, extrude_axis, corners_2d, low, high)
    if not counts and resolution < 64:
        return sampled_extrusion_mesh(
            item,
            context,
            shape_axes,
            extrude_axis,
            extrude_bounds,
            bounds,
            min(64, resolution * 2),
        )
    if not counts:
        raise ValueError(f"Inequality region for {item.ir.expr_id} did not resolve to extruded cells")
    return GeometryData(kind="Mesh", points=points, face_vertex_counts=counts, face_vertex_indices=indices)


def tessellate_function_band_extrusion(
    item: ClassifiedExpression,
    context: EvalContext,
    shape_axes: list[str],
    extrude_axis: str,
    extrude_bounds: tuple[float, float],
    bounds: dict[str, tuple[float | None, float | None]],
    resolution: int,
) -> GeometryData:
    for band_axis in shape_axes:
        param_axes = [axis for axis in shape_axes if axis != band_axis]
        if len(param_axes) != 1:
            continue
        param_axis = param_axes[0]
        param_low, param_high = bounds.get(param_axis, (None, None))
        if param_low is None or param_high is None or param_low >= param_high:
            continue
        lower_exprs, upper_exprs = function_bounds_for_axis(item.predicates, band_axis)
        if not lower_exprs or not upper_exprs:
            continue
        geometry = build_function_band_cells(
            item,
            context,
            band_axis,
            param_axis,
            extrude_axis,
            lower_exprs,
            upper_exprs,
            (param_low, param_high),
            extrude_bounds,
            bounds.get(band_axis, (None, None)),
            resolution,
        )
        if geometry.face_count:
            return geometry
    raise ValueError(f"Inequality region for {item.ir.expr_id} did not resolve to a function band extrusion")


def build_function_band_cells(
    item: ClassifiedExpression,
    context: EvalContext,
    band_axis: str,
    param_axis: str,
    extrude_axis: str,
    lower_exprs: list[LatexExpression],
    upper_exprs: list[LatexExpression],
    param_bounds: tuple[float, float],
    extrude_bounds: tuple[float, float],
    band_bounds: tuple[float | None, float | None],
    resolution: int,
) -> GeometryData:
    points: list[Point] = []
    counts: list[int] = []
    indices: list[int] = []
    params = linspace(param_bounds[0], param_bounds[1], max(2, resolution + 1))
    for left_param, right_param in zip(params[:-1], params[1:], strict=True):
        left_band = evaluated_band_interval(context, band_axis, param_axis, left_param, lower_exprs, upper_exprs, band_bounds)
        right_band = evaluated_band_interval(context, band_axis, param_axis, right_param, lower_exprs, upper_exprs, band_bounds)
        if left_band is None or right_band is None:
            continue
        corners_2d = [
            (left_band[0], left_param),
            (left_band[1], left_param),
            (right_band[1], right_param),
            (right_band[0], right_param),
        ]
        low, high = extrude_bounds
        if all(
            band_extrusion_corner_satisfies(item, context, band_axis, param_axis, extrude_axis, pair, low, high)
            for pair in corners_2d
        ):
            add_extruded_cell(points, counts, indices, [band_axis, param_axis], extrude_axis, corners_2d, low, high)
    if not counts:
        raise ValueError(f"Inequality region for {item.ir.expr_id} did not resolve to function band cells")
    return GeometryData(kind="Mesh", points=points, face_vertex_counts=counts, face_vertex_indices=indices)


def evaluated_band_interval(
    context: EvalContext,
    band_axis: str,
    param_axis: str,
    param_value: float,
    lower_exprs: list[LatexExpression],
    upper_exprs: list[LatexExpression],
    band_bounds: tuple[float | None, float | None],
) -> tuple[float, float] | None:
    variables = {param_axis: param_value}
    try:
        low = max(expression.eval(context, variables) for expression in lower_exprs)
        high = min(expression.eval(context, variables) for expression in upper_exprs)
    except Exception:
        return None
    constant_low, constant_high = band_bounds
    if constant_low is not None:
        low = max(low, constant_low)
    if constant_high is not None:
        high = min(high, constant_high)
    if low >= high:
        return None
    return low, high


def band_extrusion_corner_satisfies(
    item: ClassifiedExpression,
    context: EvalContext,
    band_axis: str,
    param_axis: str,
    extrude_axis: str,
    pair: tuple[float, float],
    low: float,
    high: float,
) -> bool:
    for extrude_value in (low, high, (low + high) / 2.0):
        variables = {band_axis: pair[0], param_axis: pair[1], extrude_axis: extrude_value}
        if not all(predicate.evaluate(context, variables, tol=1e-5) for predicate in item.predicates):
            return False
    return True


def extruded_corner_satisfies(
    item: ClassifiedExpression,
    context: EvalContext,
    shape_axes: list[str],
    extrude_axis: str,
    pair: tuple[float, float],
    low: float,
    high: float,
) -> bool:
    for extrude_value in (low, high, (low + high) / 2.0):
        variables = {shape_axes[0]: pair[0], shape_axes[1]: pair[1], extrude_axis: extrude_value}
        if not all(predicate.evaluate(context, variables, tol=1e-5) for predicate in item.predicates):
            return False
    return True


def add_extruded_cell(
    points: list[Point],
    counts: list[int],
    indices: list[int],
    shape_axes: list[str],
    extrude_axis: str,
    corners_2d: list[tuple[float, float]],
    low: float,
    high: float,
) -> None:
    corners: list[Point] = []
    for extrude_value in (low, high):
        for a, b in corners_2d:
            variables = {shape_axes[0]: a, shape_axes[1]: b, extrude_axis: extrude_value}
            corners.append(point_from_variables(variables))
    add_box(points, counts, indices, corners)


def mesh_vertices_satisfy_predicates(item: ClassifiedExpression, context: EvalContext, geometry: GeometryData) -> bool:
    for index in set(geometry.face_vertex_indices):
        point = geometry.points[index]
        variables = {"x": point[0], "y": point[1], "z": point[2]}
        if index < len(geometry.sample_parameters):
            variables.update(geometry.sample_parameters[index])
        if not all(predicate.evaluate(context, variables, tol=1e-5) for predicate in item.predicates):
            return False
    return True


def tessellate_sampled_inequality_region(item: ClassifiedExpression, context: EvalContext, resolution: int) -> GeometryData:
    bounds = collect_constant_bounds(item.predicates, context)
    fallback_bounds = item.ir.source.viewport_bounds
    xb = axis_bounds("x", bounds, fallback_bounds)
    yb = axis_bounds("y", bounds, fallback_bounds)
    zb = axis_bounds("z", bounds, fallback_bounds)
    xb, yb, zb = _refine_inequality_bbox(item, context, xb, yb, zb)
    xs = linspace(xb[0], xb[1], resolution + 1)
    ys = linspace(yb[0], yb[1], resolution + 1)
    zs = linspace(zb[0], zb[1], resolution + 1)
    points: list[Point] = []
    counts: list[int] = []
    indices: list[int] = []
    for ix in range(resolution):
        for iy in range(resolution):
            for iz in range(resolution):
                corners = [
                    (xs[ix], ys[iy], zs[iz]),
                    (xs[ix + 1], ys[iy], zs[iz]),
                    (xs[ix + 1], ys[iy + 1], zs[iz]),
                    (xs[ix], ys[iy + 1], zs[iz]),
                    (xs[ix], ys[iy], zs[iz + 1]),
                    (xs[ix + 1], ys[iy], zs[iz + 1]),
                    (xs[ix + 1], ys[iy + 1], zs[iz + 1]),
                    (xs[ix], ys[iy + 1], zs[iz + 1]),
                ]
                if all(point_satisfies_predicates(point, item, context) for point in corners):
                    add_box(points, counts, indices, corners)
    if not counts:
        raise ValueError(f"Inequality region for {item.ir.expr_id} did not resolve to sampled cells")
    return GeometryData(kind="Mesh", points=points, face_vertex_counts=counts, face_vertex_indices=indices)


def point_satisfies_predicates(point: Point, item: ClassifiedExpression, context: EvalContext) -> bool:
    variables = {"x": point[0], "y": point[1], "z": point[2]}
    return all(predicate.evaluate(context, variables, tol=1e-5) for predicate in item.predicates)


def _refine_inequality_bbox(
    item: ClassifiedExpression,
    context: EvalContext,
    xb: tuple[float, float],
    yb: tuple[float, float],
    zb: tuple[float, float],
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """Coarse-scan the predicate region for inequality voxel sampling.

    Without this, a small inequality region (e.g. radius 3 in viewport ±100) is missed
    because each voxel cell width is larger than the region. We sample a 24x24x24 grid;
    if any point satisfies all predicates, we tighten the bbox to the satisfied region
    plus a small pad. When nothing satisfies, returns the original bounds so the caller
    still raises the existing "did not resolve" error.
    """
    scan = 24
    xs = linspace(xb[0], xb[1], scan)
    ys = linspace(yb[0], yb[1], scan)
    zs = linspace(zb[0], zb[1], scan)
    x_min: float | None = None
    x_max: float | None = None
    y_min: float | None = None
    y_max: float | None = None
    z_min: float | None = None
    z_max: float | None = None
    for z in zs:
        for y in ys:
            for x in xs:
                if point_satisfies_predicates((x, y, z), item, context):
                    x_min = x if x_min is None else min(x_min, x)
                    x_max = x if x_max is None else max(x_max, x)
                    y_min = y if y_min is None else min(y_min, y)
                    y_max = y if y_max is None else max(y_max, y)
                    z_min = z if z_min is None else min(z_min, z)
                    z_max = z if z_max is None else max(z_max, z)
    if x_min is None:
        return xb, yb, zb
    pad_x = (xb[1] - xb[0]) / max(1, scan - 1)
    pad_y = (yb[1] - yb[0]) / max(1, scan - 1)
    pad_z = (zb[1] - zb[0]) / max(1, scan - 1)
    new_xb = (max(xb[0], x_min - 2 * pad_x), min(xb[1], x_max + 2 * pad_x))
    new_yb = (max(yb[0], y_min - 2 * pad_y), min(yb[1], y_max + 2 * pad_y))
    new_zb = (max(zb[0], z_min - 2 * pad_z), min(zb[1], z_max + 2 * pad_z))
    if new_xb[1] - new_xb[0] < 1e-6 or new_yb[1] - new_yb[0] < 1e-6 or new_zb[1] - new_zb[0] < 1e-6:
        return xb, yb, zb
    return new_xb, new_yb, new_zb


def add_box(points: list[Point], counts: list[int], indices: list[int], corners: list[Point]) -> None:
    base = len(points)
    points.extend(corners)
    faces = [
        [0, 1, 2, 3],
        [4, 7, 6, 5],
        [0, 4, 5, 1],
        [1, 5, 6, 2],
        [2, 6, 7, 3],
        [3, 7, 4, 0],
    ]
    for face in faces:
        counts.append(4)
        indices.extend(base + index for index in face)
