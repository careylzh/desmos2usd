from __future__ import annotations

import ast
from dataclasses import dataclass, replace
from math import ceil, cos, floor, isfinite, pi, sin

from desmos2usd.eval.context import EvalContext
from desmos2usd.eval.numeric import CONSTANTS
from desmos2usd.parse.classify import ClassifiedExpression
from desmos2usd.parse.latex_subset import LatexExpression
from desmos2usd.parse.predicates import ComparisonPredicate, collect_constant_bounds, single_identifier
from desmos2usd.tessellate.cylinders import tessellate_circular_inequality_extrusion
from desmos2usd.tessellate.implicit import (
    AxisAlignedEllipsoid,
    build_axis_aligned_ellipsoid_mesh,
    fit_axis_aligned_ellipsoid,
)
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
    modulo = tessellate_modulo_repeated_region(item, context, resolution)
    if modulo is not None:
        return modulo
    ellipsoid = tessellate_axis_aligned_ellipsoid_region(item, context, resolution=max(8, resolution * 4))
    if ellipsoid is not None and mesh_vertices_satisfy_predicates(item, context, ellipsoid):
        return ellipsoid
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
        if (geometry.face_count or is_empty_mesh(geometry)) and mesh_vertices_satisfy_predicates(item, context, geometry):
            return geometry
    except Exception:
        pass
    try:
        return tessellate_box(item, context)
    except Exception:
        return tessellate_sampled_inequality_region(item, context, resolution=max(8, resolution * 2))


def tessellate_axis_aligned_ellipsoid_region(
    item: ClassifiedExpression,
    context: EvalContext,
    resolution: int,
) -> GeometryData | None:
    if item.inequality is None:
        return None
    residual = ellipsoid_interior_residual(item.inequality)
    if residual is None:
        return None
    profile = fit_axis_aligned_ellipsoid(residual, context)
    if profile is None:
        return None

    latitude_segments = max(8, min(32, resolution))
    longitude_segments = max(16, min(64, resolution * 2))
    surface = build_axis_aligned_ellipsoid_mesh(profile, latitude_segments, longitude_segments)
    points: list[Point] = []
    counts: list[int] = []
    indices: list[int] = []
    append_predicate_faces(points, counts, indices, surface, item, context)
    append_axis_aligned_ellipsoid_caps(points, counts, indices, profile, item, context, longitude_segments)
    if not counts:
        return None
    return GeometryData(kind="Mesh", points=points, face_vertex_counts=counts, face_vertex_indices=indices)


def ellipsoid_interior_residual(predicate: ComparisonPredicate) -> LatexExpression | None:
    if len(predicate.terms) != 2 or len(predicate.ops) != 1:
        return None
    left, right = predicate.terms
    op = predicate.ops[0]
    if op in {"<", "<="}:
        return LatexExpression.parse(f"({left.latex})-({right.latex})")
    if op in {">", ">="}:
        return LatexExpression.parse(f"({right.latex})-({left.latex})")
    return None


def append_predicate_faces(
    points: list[Point],
    counts: list[int],
    indices: list[int],
    surface: GeometryData,
    item: ClassifiedExpression,
    context: EvalContext,
) -> None:
    remap: dict[int, int] = {}
    cursor = 0
    for count in surface.face_vertex_counts:
        face = surface.face_vertex_indices[cursor : cursor + count]
        cursor += count
        if len(face) != count:
            continue
        if not all(point_satisfies_predicates(surface.points[index], item, context) for index in face):
            continue
        counts.append(count)
        for index in face:
            if index not in remap:
                remap[index] = len(points)
                points.append(surface.points[index])
            indices.append(remap[index])


def append_axis_aligned_ellipsoid_caps(
    points: list[Point],
    counts: list[int],
    indices: list[int],
    profile: AxisAlignedEllipsoid,
    item: ClassifiedExpression,
    context: EvalContext,
    segment_count: int,
) -> None:
    bounds = collect_constant_bounds(item.predicates, context)
    for axis_index, axis in enumerate(("x", "y", "z")):
        low, high = bounds.get(axis, (None, None))
        if low is not None:
            append_axis_aligned_ellipsoid_cap(
                points, counts, indices, profile, item, context, axis_index, low, segment_count, reverse=True
            )
        if high is not None:
            append_axis_aligned_ellipsoid_cap(
                points, counts, indices, profile, item, context, axis_index, high, segment_count, reverse=False
            )


def append_axis_aligned_ellipsoid_cap(
    points: list[Point],
    counts: list[int],
    indices: list[int],
    profile: AxisAlignedEllipsoid,
    item: ClassifiedExpression,
    context: EvalContext,
    axis_index: int,
    value: float,
    segment_count: int,
    reverse: bool,
) -> None:
    center = profile.center
    radii = profile.radii
    radius = radii[axis_index]
    if radius <= 0.0:
        return
    normalized = (value - center[axis_index]) / radius
    if normalized < -1.0 - 1e-8 or normalized > 1.0 + 1e-8:
        return
    scale = max(0.0, 1.0 - normalized * normalized) ** 0.5
    if scale <= 1e-8:
        return
    other_axes = [index for index in range(3) if index != axis_index]
    ring: list[Point] = []
    for segment in range(segment_count):
        angle = 2.0 * pi * segment / segment_count
        values = [center[0], center[1], center[2]]
        values[axis_index] = value
        values[other_axes[0]] = center[other_axes[0]] + radii[other_axes[0]] * scale * cos(angle)
        values[other_axes[1]] = center[other_axes[1]] + radii[other_axes[1]] * scale * sin(angle)
        ring.append((values[0], values[1], values[2]))
    if not all(point_satisfies_predicates(point, item, context) for point in ring):
        return
    if reverse:
        ring.reverse()
    base = len(points)
    points.extend(ring)
    counts.append(len(ring))
    indices.extend(range(base, base + len(ring)))


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
        empty = analytically_empty_function_band(item, context, shape_axes, shape_bounds)
        if empty is not None:
            return empty
        geometry = tessellate_affine_polygon_extrusion(
            item,
            context,
            shape_axes,
            extrude_axis,
            (low, high),
            shape_bounds,
        )
        if geometry is not None and (geometry.face_count or is_empty_mesh(geometry)):
            return geometry
        geometry = sampled_extrusion_mesh(item, context, shape_axes, extrude_axis, (low, high), shape_bounds, resolution)
        if geometry.face_count:
            return geometry
    raise ValueError(f"Inequality region for {item.ir.expr_id} did not resolve to an extruded 2D region")


def is_empty_mesh(geometry: GeometryData) -> bool:
    return geometry.kind == "Mesh" and not geometry.points and not geometry.face_vertex_counts and not geometry.face_vertex_indices


def analytically_empty_function_band(
    item: ClassifiedExpression,
    context: EvalContext,
    shape_axes: list[str],
    bounds: dict[str, tuple[float | None, float | None]],
) -> GeometryData | None:
    """Return an empty mesh when affine band bounds prove the region has no area."""
    if not is_generated_expression_expansion(item):
        return None
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
        feasible = affine_function_band_feasible_interval(
            context,
            param_axis,
            (param_low, param_high),
            lower_exprs,
            upper_exprs,
        )
        if feasible is None:
            continue
        if feasible[0] >= feasible[1]:
            return GeometryData(kind="Mesh", points=[])
    return None


def is_generated_expression_expansion(item: ClassifiedExpression) -> bool:
    return any(
        key in item.ir.raw
        for key in (
            "expandedFromListExpression",
            "expandedFromLiteralListExpression",
            "expandedFromRestrictionAlternative",
        )
    )


def affine_function_band_feasible_interval(
    context: EvalContext,
    param_axis: str,
    param_bounds: tuple[float, float],
    lower_exprs: list[LatexExpression],
    upper_exprs: list[LatexExpression],
    tol: float = 1e-9,
) -> tuple[float, float] | None:
    low, high = param_bounds
    for lower in lower_exprs:
        lower_coeffs = affine_coefficients(lower, context, param_axis)
        if lower_coeffs is None:
            return None
        for upper in upper_exprs:
            upper_coeffs = affine_coefficients(upper, context, param_axis)
            if upper_coeffs is None:
                return None
            slope = lower_coeffs[0] - upper_coeffs[0]
            intercept = lower_coeffs[1] - upper_coeffs[1]
            if abs(slope) <= tol:
                if intercept >= -tol:
                    return (low, low)
                continue
            root = -intercept / slope
            if slope > 0:
                high = min(high, root)
            else:
                low = max(low, root)
            if low >= high - tol:
                return (low, low)
    return (low, high)


def affine_coefficients(
    expression: LatexExpression,
    context: EvalContext,
    variable: str,
) -> tuple[float, float] | None:
    if expression.identifiers - {variable} - set(context.scalars):
        return None
    coeffs = affine_node_coefficients(expression.tree.body, context, variable)
    if coeffs is None or not all(isfinite(value) for value in coeffs):
        return None
    return coeffs


def affine_node_coefficients(
    node: ast.AST,
    context: EvalContext,
    variable: str,
) -> tuple[float, float] | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return (0.0, float(node.value))
    if isinstance(node, ast.Name):
        if node.id == variable:
            return (1.0, 0.0)
        if node.id in context.scalars:
            return (0.0, float(context.scalars[node.id]))
        if node.id in CONSTANTS:
            return (0.0, float(CONSTANTS[node.id]))
        return None
    if isinstance(node, ast.UnaryOp):
        coeffs = affine_node_coefficients(node.operand, context, variable)
        if coeffs is None:
            return None
        if isinstance(node.op, ast.USub):
            return (-coeffs[0], -coeffs[1])
        if isinstance(node.op, ast.UAdd):
            return coeffs
        return None
    if isinstance(node, ast.BinOp):
        left = affine_node_coefficients(node.left, context, variable)
        right = affine_node_coefficients(node.right, context, variable)
        if left is None or right is None:
            return None
        if isinstance(node.op, ast.Add):
            return (left[0] + right[0], left[1] + right[1])
        if isinstance(node.op, ast.Sub):
            return (left[0] - right[0], left[1] - right[1])
        if isinstance(node.op, ast.Mult):
            if abs(left[0]) > 0 and abs(right[0]) > 0:
                return None
            if abs(left[0]) > 0:
                return (left[0] * right[1], left[1] * right[1])
            return (right[0] * left[1], right[1] * left[1])
        if isinstance(node.op, ast.Div):
            if abs(right[0]) > 0 or abs(right[1]) <= 1e-12:
                return None
            return (left[0] / right[1], left[1] / right[1])
    return None


def predicate_identifiers(predicate: ComparisonPredicate) -> set[str]:
    identifiers: set[str] = set()
    for term in predicate.terms:
        identifiers.update(term.identifiers & {"x", "y", "z"})
    return identifiers


@dataclass(frozen=True)
class ModuloStripe:
    predicate: ComparisonPredicate
    axis: str
    coefficient: float
    intercept: float
    period: float
    width: float


def tessellate_modulo_repeated_region(
    item: ClassifiedExpression,
    context: EvalContext,
    resolution: int,
) -> GeometryData | None:
    stripe = first_modulo_stripe(item, context)
    if stripe is None:
        return None

    bounds = collect_constant_bounds(item.predicates, context)
    axis_low, axis_high = axis_bounds(stripe.axis, bounds, item.ir.source.viewport_bounds)
    if axis_low >= axis_high:
        return None
    intervals = modulo_axis_intervals(stripe, axis_low, axis_high)
    if not intervals:
        return None

    geometries: list[GeometryData] = []
    for low, high in intervals:
        narrowed = item_with_axis_interval(item, stripe.axis, low, high)
        geometry = tessellate_modulo_interval_region(
            item,
            narrowed,
            context,
            stripe,
            resolution,
        )
        if geometry is not None and geometry.kind == "Mesh" and geometry.face_count:
            geometries.append(geometry)
    if not geometries:
        return None
    return combine_meshes(geometries)


def tessellate_modulo_interval_region(
    original: ClassifiedExpression,
    narrowed: ClassifiedExpression,
    context: EvalContext,
    stripe: ModuloStripe,
    resolution: int,
) -> GeometryData | None:
    if narrowed.inequality is not stripe.predicate:
        circular = tessellate_circular_inequality_extrusion(narrowed, context, resolution=max(16, resolution * 4))
        if circular is not None and mesh_vertices_satisfy_predicates(original, context, circular):
            return circular
    try:
        box = tessellate_box(narrowed, context)
        if box.face_count and mesh_vertices_satisfy_predicates(original, context, box):
            return box
    except Exception:
        pass
    try:
        extruded = tessellate_extruded_2d_region(narrowed, context, resolution=max(16, resolution * 4))
        if extruded.face_count and mesh_vertices_satisfy_predicates(original, context, extruded):
            return extruded
    except Exception:
        pass
    return None


def first_modulo_stripe(item: ClassifiedExpression, context: EvalContext) -> ModuloStripe | None:
    for predicate in item.predicates:
        stripe = modulo_stripe_from_predicate(predicate, context)
        if stripe is not None:
            return stripe
    return None


def modulo_stripe_from_predicate(predicate: ComparisonPredicate, context: EvalContext) -> ModuloStripe | None:
    if len(predicate.terms) != 2 or len(predicate.ops) != 1:
        return None
    left, right = predicate.terms
    op = predicate.ops[0]
    if op in {"<", "<="}:
        modulo = modulo_term_info(left, context)
        width = constant_expression_value(right, context)
    elif op in {">", ">="}:
        modulo = modulo_term_info(right, context)
        width = constant_expression_value(left, context)
    else:
        return None
    if modulo is None or width is None:
        return None
    axis, coefficient, intercept, period = modulo
    if abs(coefficient) <= 1e-12 or period <= 0.0 or width <= 0.0 or width >= period:
        return None
    return ModuloStripe(
        predicate=predicate,
        axis=axis,
        coefficient=coefficient,
        intercept=intercept,
        period=period,
        width=width,
    )


def modulo_term_info(
    expression: LatexExpression,
    context: EvalContext,
) -> tuple[str, float, float, float] | None:
    node = expression.tree.body
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "mod":
        return None
    if len(node.args) != 2:
        return None
    graph_axes = expression.identifiers & {"x", "y", "z"}
    if len(graph_axes) != 1:
        return None
    axis = next(iter(graph_axes))
    affine = affine_node_coefficients(node.args[0], context, axis)
    period = constant_node_value(node.args[1], context, axis)
    if affine is None or period is None:
        return None
    coefficient, intercept = affine
    return axis, coefficient, intercept, period


def constant_expression_value(expression: LatexExpression, context: EvalContext) -> float | None:
    if expression.identifiers & {"x", "y", "z"}:
        return None
    try:
        value = expression.eval(context, {})
    except Exception:
        return None
    return value if isfinite(value) else None


def constant_node_value(node: ast.AST, context: EvalContext, variable: str) -> float | None:
    coeffs = affine_node_coefficients(node, context, variable)
    if coeffs is None or abs(coeffs[0]) > 1e-12 or not isfinite(coeffs[1]):
        return None
    return coeffs[1]


def modulo_axis_intervals(stripe: ModuloStripe, axis_low: float, axis_high: float) -> list[tuple[float, float]]:
    u0 = stripe.coefficient * axis_low + stripe.intercept
    u1 = stripe.coefficient * axis_high + stripe.intercept
    u_low, u_high = (min(u0, u1), max(u0, u1))
    first_k = floor((u_low - stripe.width) / stripe.period) - 1
    last_k = ceil(u_high / stripe.period) + 1
    intervals: list[tuple[float, float]] = []
    for k in range(first_k, last_k + 1):
        active_low = k * stripe.period
        active_high = active_low + stripe.width
        endpoint_a = (active_low - stripe.intercept) / stripe.coefficient
        endpoint_b = (active_high - stripe.intercept) / stripe.coefficient
        low = max(axis_low, min(endpoint_a, endpoint_b))
        high = min(axis_high, max(endpoint_a, endpoint_b))
        if high - low > 1e-9:
            intervals.append((low, high))
    intervals.sort()
    return intervals


def item_with_axis_interval(
    item: ClassifiedExpression,
    axis: str,
    low: float,
    high: float,
) -> ClassifiedExpression:
    return replace(
        item,
        predicates=[*item.predicates, axis_interval_predicate(axis, low, high)],
    )


def axis_interval_predicate(axis: str, low: float, high: float) -> ComparisonPredicate:
    raw = f"{low:.17g}<={axis}<={high:.17g}"
    return ComparisonPredicate(
        raw=raw,
        terms=(
            LatexExpression.parse(f"{low:.17g}"),
            LatexExpression.parse(axis),
            LatexExpression.parse(f"{high:.17g}"),
        ),
        ops=("<=", "<="),
    )


def combine_meshes(geometries: list[GeometryData]) -> GeometryData:
    points: list[Point] = []
    counts: list[int] = []
    indices: list[int] = []
    sample_parameters: list[dict[str, float]] = []
    include_samples = any(geometry.sample_parameters for geometry in geometries)
    for geometry in geometries:
        offset = len(points)
        points.extend(geometry.points)
        counts.extend(geometry.face_vertex_counts)
        indices.extend(offset + index for index in geometry.face_vertex_indices)
        if include_samples:
            sample_parameters.extend(geometry.sample_parameters)
            sample_parameters.extend({} for _ in range(len(geometry.points) - len(geometry.sample_parameters)))
    return GeometryData(kind="Mesh", points=points, face_vertex_counts=counts, face_vertex_indices=indices, sample_parameters=sample_parameters)


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
    """Render a 2D inequality region at constant flat-axis when its third axis is locked.

    Desmos 3D renders expressions like ``20>y>-20 {-225<x<225}`` (third axis missing)
    or ``x^2+y^2<=4 {z=0}`` (third axis locked to a constant) as a flat region in the
    other two axes — not as a viewport-sized 3D volume. Two cases satisfy this:

    * The third axis is entirely absent from the inequality and its restrictions; we
      flatten that axis at 0.
    * The third axis appears only as a constant equality (e.g. ``z=0``); we flatten at
      that constant.

    Without this, ``x^2+y^2<=4 {z=0}`` falls through every 3D extrusion path and is
    reported as ``did not resolve to sampled cells``.
    """
    bounds = collect_constant_bounds(item.predicates, context)
    flat_axis, flat_value = _detect_flat_axis(item, bounds)
    if flat_axis is None or flat_value is None:
        return None
    shape_axes = [axis for axis in ("x", "y", "z") if axis != flat_axis]
    seed_ranges: dict[str, tuple[float, float]] = {}
    for axis in shape_axes:
        low, high = bounds.get(axis, (None, None))
        if low is None or high is None or low >= high:
            seed_ranges[axis] = _flat_shape_axis_range(item, context, axis)
        else:
            seed_ranges[axis] = (low, high)
        if seed_ranges[axis][0] >= seed_ranges[axis][1]:
            return None
    a_axis, b_axis = shape_axes
    # Pre-scan the seed bbox for satisfied points and tighten the sampling window.
    # Without this, a small region (e.g. radius 2 inside a span-of-5 seed) wastes most
    # of the grid on the invalid corners and produces only a single inner cell.
    sampling = _refine_flat_region_window(
        item,
        context,
        a_axis,
        b_axis,
        flat_axis,
        flat_value,
        seed_ranges[a_axis],
        seed_ranges[b_axis],
    )
    if sampling is None:
        return None
    a_low, a_high, b_low, b_high = sampling
    grid = max(resolution, 16)
    a_values = linspace(a_low, a_high, grid)
    b_values = linspace(b_low, b_high, grid)
    points: list[Point] = []
    valid_grid: list[list[bool]] = []
    for b in b_values:
        row_valid: list[bool] = []
        for a in a_values:
            variables = {a_axis: a, b_axis: b, flat_axis: flat_value}
            points.append((variables["x"], variables["y"], variables["z"]))
            row_valid.append(all(predicate.evaluate(context, variables, tol=1e-5) for predicate in item.predicates))
        valid_grid.append(row_valid)
    counts: list[int] = []
    indices: list[int] = []
    width = grid
    for row in range(grid - 1):
        for col in range(grid - 1):
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


def _refine_flat_region_window(
    item: ClassifiedExpression,
    context: EvalContext,
    a_axis: str,
    b_axis: str,
    flat_axis: str,
    flat_value: float,
    a_seed: tuple[float, float],
    b_seed: tuple[float, float],
) -> tuple[float, float, float, float] | None:
    scan = 32
    a_samples = linspace(a_seed[0], a_seed[1], scan)
    b_samples = linspace(b_seed[0], b_seed[1], scan)
    a_min: float | None = None
    a_max: float | None = None
    b_min: float | None = None
    b_max: float | None = None
    for b in b_samples:
        for a in a_samples:
            variables = {a_axis: a, b_axis: b, flat_axis: flat_value}
            if all(predicate.evaluate(context, variables, tol=1e-5) for predicate in item.predicates):
                a_min = a if a_min is None else min(a_min, a)
                a_max = a if a_max is None else max(a_max, a)
                b_min = b if b_min is None else min(b_min, b)
                b_max = b if b_max is None else max(b_max, b)
    if a_min is None:
        return None
    pad_a = (a_seed[1] - a_seed[0]) / max(1, scan - 1)
    pad_b = (b_seed[1] - b_seed[0]) / max(1, scan - 1)
    return (
        max(a_seed[0], a_min - 2 * pad_a),
        min(a_seed[1], a_max + 2 * pad_a),
        max(b_seed[0], b_min - 2 * pad_b),
        min(b_seed[1], b_max + 2 * pad_b),
    )


def _detect_flat_axis(
    item: ClassifiedExpression,
    bounds: dict[str, tuple[float | None, float | None]],
) -> tuple[str | None, float | None]:
    referenced = _referenced_axes(item)
    missing = [axis for axis in ("x", "y", "z") if axis not in referenced]
    if len(missing) == 1:
        return missing[0], 0.0
    constant_axes = [
        axis
        for axis in ("x", "y", "z")
        if bounds.get(axis, (None, None))[0] is not None
        and bounds[axis][0] == bounds[axis][1]
    ]
    if len(constant_axes) == 1:
        axis = constant_axes[0]
        return axis, float(bounds[axis][0])
    return None, None


def _flat_shape_axis_range(
    item: ClassifiedExpression,
    context: EvalContext,
    axis: str,
) -> tuple[float, float]:
    """Bound a shape axis from the inequality's numeric constants.

    For inequalities like ``x^2+y^2<=4`` no axis bounds appear in predicates, but the
    constants in the inequality terms (4 → sqrt(4)=2) imply a tight enclosing range.
    Using the viewport here would re-introduce the very tall-sheet bug we are fixing
    (the disk would sample a 24-unit window for a radius-2 region).
    """
    constants: list[float] = list(numeric_constants_for_item(item))
    if not constants:
        viewport = item.ir.source.viewport_bounds or {}
        return viewport.get(axis, DEFAULT_BOUNDS)
    abs_constants = [abs(value) for value in constants if value is not None]
    abs_constants += [abs(value) ** 0.5 for value in abs_constants]
    span = max(abs_constants) if abs_constants else 1.0
    span = max(span * 1.25, 0.5)
    return (-span, span)


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


def tessellate_affine_polygon_extrusion(
    item: ClassifiedExpression,
    context: EvalContext,
    shape_axes: list[str],
    extrude_axis: str,
    extrude_bounds: tuple[float, float],
    bounds: dict[str, tuple[float | None, float | None]],
) -> GeometryData | None:
    halfplanes = affine_halfplanes_for_shape(item, context, shape_axes, extrude_axis)
    if halfplanes is None:
        return None
    if not halfplanes:
        return None

    constants = shape_numeric_constants(item, set(shape_axes))
    if not constants:
        constants = numeric_constants_for_item(item)
    broad_low, broad_high = broad_bounds_from_constants(constants)
    a_bounds = bounded_or_broad_range(bounds, shape_axes[0], broad_low, broad_high)
    b_bounds = bounded_or_broad_range(bounds, shape_axes[1], broad_low, broad_high)
    polygon: list[tuple[float, float]] = [
        (a_bounds[0], b_bounds[0]),
        (a_bounds[1], b_bounds[0]),
        (a_bounds[1], b_bounds[1]),
        (a_bounds[0], b_bounds[1]),
    ]
    for a_coeff, b_coeff, c_coeff in halfplanes:
        polygon = clip_polygon_to_halfplane(polygon, a_coeff, b_coeff, c_coeff)
        if len(polygon) < 3:
            return GeometryData(kind="Mesh", points=[])
    polygon = dedupe_polygon_points(polygon)
    if len(polygon) < 3 or abs(polygon_area(polygon)) <= 1e-10:
        return GeometryData(kind="Mesh", points=[])

    geometry = extrude_polygon(shape_axes, extrude_axis, polygon, extrude_bounds)
    if not mesh_vertices_satisfy_predicates(item, context, geometry):
        return None
    return geometry


def bounded_or_broad_range(
    bounds: dict[str, tuple[float | None, float | None]],
    axis: str,
    broad_low: float,
    broad_high: float,
) -> tuple[float, float]:
    low, high = bounds.get(axis, (None, None))
    return (broad_low if low is None else low, broad_high if high is None else high)


def affine_halfplanes_for_shape(
    item: ClassifiedExpression,
    context: EvalContext,
    shape_axes: list[str],
    extrude_axis: str,
) -> list[tuple[float, float, float]] | None:
    shape_set = set(shape_axes)
    halfplanes: list[tuple[float, float, float]] = []
    for predicate in item.predicates:
        identifiers = predicate_identifiers(predicate)
        if not identifiers:
            try:
                if predicate.evaluate(context, {}, tol=1e-9):
                    continue
            except Exception:
                return None
            return []
        if identifiers.issubset({extrude_axis}):
            continue
        if not identifiers.issubset(shape_set):
            return None
        predicate_halfplanes = affine_halfplanes_for_predicate(predicate, context, shape_axes)
        if predicate_halfplanes is None:
            return None
        halfplanes.extend(predicate_halfplanes)
    return halfplanes


def affine_halfplanes_for_predicate(
    predicate: ComparisonPredicate,
    context: EvalContext,
    shape_axes: list[str],
) -> list[tuple[float, float, float]] | None:
    halfplanes: list[tuple[float, float, float]] = []
    for left, op, right in zip(predicate.terms[:-1], predicate.ops, predicate.terms[1:], strict=True):
        left_coeffs = affine_coefficients_2d(left, context, shape_axes)
        right_coeffs = affine_coefficients_2d(right, context, shape_axes)
        if left_coeffs is None or right_coeffs is None:
            return None
        if op in {"<=", "<"}:
            halfplanes.append(subtract_affine_coefficients(left_coeffs, right_coeffs))
        elif op in {">=", ">"}:
            halfplanes.append(subtract_affine_coefficients(right_coeffs, left_coeffs))
        elif op == "=":
            delta = subtract_affine_coefficients(left_coeffs, right_coeffs)
            halfplanes.append(delta)
            halfplanes.append((-delta[0], -delta[1], -delta[2]))
        else:
            return None
    return halfplanes


def affine_coefficients_2d(
    expression: LatexExpression,
    context: EvalContext,
    axes: list[str],
    tol: float = 1e-8,
) -> tuple[float, float, float] | None:
    if expression.identifiers - set(axes) - set(context.scalars):
        return None
    try:
        origin = expression.eval(context, {axes[0]: 0.0, axes[1]: 0.0})
        a_value = expression.eval(context, {axes[0]: 1.0, axes[1]: 0.0}) - origin
        b_value = expression.eval(context, {axes[0]: 0.0, axes[1]: 1.0}) - origin
    except Exception:
        return None
    if not all(isfinite(value) for value in (a_value, b_value, origin)):
        return None
    for a_sample, b_sample in ((2.0, -3.0), (-1.5, 4.0), (3.25, 2.5)):
        try:
            actual = expression.eval(context, {axes[0]: a_sample, axes[1]: b_sample})
        except Exception:
            return None
        predicted = a_value * a_sample + b_value * b_sample + origin
        scale = max(1.0, abs(actual), abs(predicted))
        if abs(actual - predicted) > tol * scale:
            return None
    return (a_value, b_value, origin)


def subtract_affine_coefficients(
    left: tuple[float, float, float],
    right: tuple[float, float, float],
) -> tuple[float, float, float]:
    return (left[0] - right[0], left[1] - right[1], left[2] - right[2])


def clip_polygon_to_halfplane(
    polygon: list[tuple[float, float]],
    a_coeff: float,
    b_coeff: float,
    c_coeff: float,
    tol: float = 1e-8,
) -> list[tuple[float, float]]:
    if not polygon:
        return []
    clipped: list[tuple[float, float]] = []
    previous = polygon[-1]
    previous_value = halfplane_value(previous, a_coeff, b_coeff, c_coeff)
    previous_inside = previous_value <= tol
    for current in polygon:
        current_value = halfplane_value(current, a_coeff, b_coeff, c_coeff)
        current_inside = current_value <= tol
        if current_inside:
            if not previous_inside:
                clipped.append(intersect_halfplane_edge(previous, current, previous_value, current_value))
            clipped.append(current)
        elif previous_inside:
            clipped.append(intersect_halfplane_edge(previous, current, previous_value, current_value))
        previous = current
        previous_value = current_value
        previous_inside = current_inside
    return dedupe_polygon_points(clipped)


def halfplane_value(point: tuple[float, float], a_coeff: float, b_coeff: float, c_coeff: float) -> float:
    return a_coeff * point[0] + b_coeff * point[1] + c_coeff


def intersect_halfplane_edge(
    start: tuple[float, float],
    end: tuple[float, float],
    start_value: float,
    end_value: float,
) -> tuple[float, float]:
    denominator = start_value - end_value
    if abs(denominator) <= 1e-12:
        return end
    ratio = start_value / denominator
    return (start[0] + ratio * (end[0] - start[0]), start[1] + ratio * (end[1] - start[1]))


def dedupe_polygon_points(points: list[tuple[float, float]], tol: float = 1e-9) -> list[tuple[float, float]]:
    deduped: list[tuple[float, float]] = []
    for point in points:
        if not deduped or abs(point[0] - deduped[-1][0]) > tol or abs(point[1] - deduped[-1][1]) > tol:
            deduped.append(point)
    if len(deduped) > 1 and abs(deduped[0][0] - deduped[-1][0]) <= tol and abs(deduped[0][1] - deduped[-1][1]) <= tol:
        deduped.pop()
    return deduped


def polygon_area(points: list[tuple[float, float]]) -> float:
    total = 0.0
    for current, next_point in zip(points, points[1:] + points[:1], strict=True):
        total += current[0] * next_point[1] - next_point[0] * current[1]
    return total / 2.0


def extrude_polygon(
    shape_axes: list[str],
    extrude_axis: str,
    polygon: list[tuple[float, float]],
    extrude_bounds: tuple[float, float],
) -> GeometryData:
    points: list[Point] = []
    for extrude_value in extrude_bounds:
        for a_value, b_value in polygon:
            variables = {shape_axes[0]: a_value, shape_axes[1]: b_value, extrude_axis: extrude_value}
            points.append(point_from_variables(variables))
    vertex_count = len(polygon)
    bottom = list(range(vertex_count))
    top = list(range(vertex_count, vertex_count * 2))
    counts = [vertex_count, vertex_count]
    indices = list(reversed(bottom)) + top
    for index in range(vertex_count):
        next_index = (index + 1) % vertex_count
        counts.append(4)
        indices.extend([bottom[index], bottom[next_index], top[next_index], top[index]])
    return GeometryData(kind="Mesh", points=points, face_vertex_counts=counts, face_vertex_indices=indices)


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
    if not counts and resolution < 32:
        next_resolution = min(32, max(resolution + 1, resolution * 2))
        return tessellate_sampled_inequality_region(item, context, next_resolution)
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
