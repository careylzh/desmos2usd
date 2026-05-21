from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import dataclass, replace
from math import cos, isfinite, pi, sin, sqrt
from typing import Any

from desmos2usd.eval.context import EvalContext
from desmos2usd.parse.classify import ClassifiedExpression
from desmos2usd.parse.latex_subset import LatexExpression
from desmos2usd.parse.predicates import ComparisonPredicate, collect_constant_bounds
from desmos2usd.tessellate.mesh import GeometryData, Point, linspace, quad_faces


DEFAULT_BOUNDS = (-5.0, 5.0)
INFERENCE_SAMPLES = 64
SINGLE_AXIS_INFERENCE_SAMPLES = 1024
BOUNDARY_REFINE_ITERATIONS = 60
QUAD_BOUNDARY_REFINE_ITERATIONS = 8
HALF_OPEN_TOL = 1e-5
BOUNDARY_NUDGE = 2e-5
DEGENERATE_AXIS_HALF_WIDTH = 5e-4
STEEP_EXPLICIT_SURFACE_SLOPE = 1e8


def tessellate_explicit_surface(
    item: ClassifiedExpression,
    context: EvalContext,
    resolution: int = 18,
    axis_samples: dict[str, list[float]] | None = None,
) -> GeometryData:
    if not item.axis or not item.expression:
        raise ValueError("explicit surface missing axis or expression")
    flat_disk = tessellate_constant_explicit_surface_disk(item, context, resolution)
    if flat_disk is not None:
        return flat_disk
    domain_axes = [axis for axis in ("x", "y", "z") if axis != item.axis]
    reoriented = reorient_steep_explicit_surface(item, context, domain_axes)
    if reoriented is not None:
        geometry = tessellate_explicit_surface(reoriented, context, resolution=resolution)
        if geometry.face_count:
            return geometry
    surface_bounds = explicit_surface_domain_bounds(item, context)
    constant_bounds = collect_constant_bounds(item.predicates, context)
    flat_axis = _explicit_flat_axis(item, domain_axes, constant_bounds)
    a0, a1 = surface_bounds[domain_axes[0]]
    b0, b1 = surface_bounds[domain_axes[1]]
    # If a domain axis was intentionally collapsed by the 2D-in-3D rule, expand it to a
    # thin strip so quad_faces (which needs two distinct samples per dimension) still
    # produces geometry. We do NOT nudge predicate-derived degenerate ranges (e.g. a
    # ``z=18`` predicate or a strict ``18<z<18`` band): those legitimately mean "this
    # surface lives at exactly z=18", and silently expanding them produces points that
    # violate their own predicate.
    if flat_axis == domain_axes[0] and a0 == a1:
        a0, a1 = a0 - DEGENERATE_AXIS_HALF_WIDTH, a1 + DEGENERATE_AXIS_HALF_WIDTH
    if flat_axis == domain_axes[1] and b0 == b1:
        b0, b1 = b0 - DEGENERATE_AXIS_HALF_WIDTH, b1 + DEGENERATE_AXIS_HALF_WIDTH
    axis_samples = axis_samples or {}
    a_values = sample_axis_values(a0, a1, resolution, axis_samples.get(domain_axes[0]))
    b_values = sample_axis_values(b0, b1, resolution, axis_samples.get(domain_axes[1]))
    points: list[Point] = []
    valid_grid: list[list[bool]] = []
    for b in b_values:
        row_valid: list[bool] = []
        for a in a_values:
            point, valid = explicit_surface_sample(
                item,
                context,
                {domain_axes[0]: a, domain_axes[1]: b},
            )
            points.append(point)
            row_valid.append(valid)
        valid_grid.append(row_valid)
    if _surface_predicates_constrain_solved_axis(item):
        points, counts, indices = refined_quad_faces(
            item,
            context,
            domain_axes[0],
            a_values,
            domain_axes[1],
            b_values,
            points,
            valid_grid,
        )
    else:
        # Predicates only restrict the domain axes (or are absent), so the surface
        # boundary already aligns with the grid edges where the constraints become
        # active. Bisecting individual cells would not refine that boundary, so
        # skip the refinement to keep this fast.
        counts, indices = quad_faces(len(a_values), len(b_values), valid_grid)
    if not counts and resolution < 64:
        return tessellate_explicit_surface(
            item,
            context,
            resolution=min(64, resolution * 2),
            axis_samples=axis_samples,
        )
    if (
        counts
        and not (
            _has_constant_solved_axis_value(item)
            and _domain_axes_have_finite_constant_bounds(constant_bounds, domain_axes)
        )
        and _solved_axis_entirely_outside_viewport(item, points, indices)
    ):
        return GeometryData(kind="Mesh", points=[], face_vertex_counts=[], face_vertex_indices=[])
    return GeometryData(kind="Mesh", points=points, face_vertex_counts=counts, face_vertex_indices=indices)


def tessellate_constant_explicit_surface_disk(
    item: ClassifiedExpression,
    context: EvalContext,
    resolution: int,
) -> GeometryData | None:
    if not item.axis or not item.expression or item.expression.identifiers & {"x", "y", "z"}:
        return None
    try:
        flat_value = float(item.expression.eval(context, {}))
    except Exception:
        return None
    if not isfinite(flat_value):
        return None
    shape_axes = tuple(axis for axis in ("x", "y", "z") if axis != item.axis)
    segment_count = max(24, min(160, resolution * 4))
    for predicate in item.predicates:
        residual = signed_residual_for_disk_predicate(predicate)
        if residual is None:
            continue
        profile = fit_constant_surface_disk_profile(context, residual, shape_axes, item.axis, flat_value)
        if profile is None:
            continue
        geometry = build_flat_disk_mesh(shape_axes, item.axis, flat_value, profile, segment_count)
        if constant_disk_vertices_satisfy_predicates(item, context, geometry):
            return geometry
    return None


def signed_residual_for_disk_predicate(
    predicate: ComparisonPredicate,
) -> Callable[[EvalContext, dict[str, float]], float] | None:
    if len(predicate.terms) != 2 or len(predicate.ops) != 1:
        return None
    left, right = predicate.terms
    op = predicate.ops[0]
    if op in {"<", "<="}:
        return lambda ctx, variables: left.eval(ctx, variables) - right.eval(ctx, variables)
    if op in {">", ">="}:
        return lambda ctx, variables: right.eval(ctx, variables) - left.eval(ctx, variables)
    return None


def fit_constant_surface_disk_profile(
    context: EvalContext,
    residual: Callable[[EvalContext, dict[str, float]], float],
    shape_axes: tuple[str, str],
    flat_axis: str,
    flat_value: float,
) -> Any | None:
    from desmos2usd.tessellate.cylinders import fit_circle_profile

    return fit_circle_profile(context, residual, shape_axes, flat_axis, flat_value)


def build_flat_disk_mesh(
    shape_axes: tuple[str, str],
    flat_axis: str,
    flat_value: float,
    profile: Any,
    segment_count: int,
) -> GeometryData:
    points: list[Point] = []
    radius_a, radius_b = profile.radii
    for segment in range(segment_count):
        angle = 2.0 * pi * segment / segment_count
        variables = {
            shape_axes[0]: profile.center[0] + radius_a * cos(angle),
            shape_axes[1]: profile.center[1] + radius_b * sin(angle),
            flat_axis: flat_value,
        }
        points.append(point_from_variables(variables))
    center_index = len(points)
    points.append(
        point_from_variables(
            {
                shape_axes[0]: profile.center[0],
                shape_axes[1]: profile.center[1],
                flat_axis: flat_value,
            }
        )
    )
    counts: list[int] = []
    indices: list[int] = []
    for segment in range(segment_count):
        next_segment = (segment + 1) % segment_count
        counts.append(3)
        indices.extend([center_index, segment, next_segment])
    return GeometryData(kind="Mesh", points=points, face_vertex_counts=counts, face_vertex_indices=indices)


def constant_disk_vertices_satisfy_predicates(
    item: ClassifiedExpression,
    context: EvalContext,
    geometry: GeometryData,
) -> bool:
    for index in set(geometry.face_vertex_indices):
        point = geometry.points[index]
        variables = {"x": point[0], "y": point[1], "z": point[2]}
        if not explicit_surface_predicates_satisfied(item, context, variables):
            return False
    return True


def reorient_steep_explicit_surface(
    item: ClassifiedExpression,
    context: EvalContext,
    domain_axes: list[str],
) -> ClassifiedExpression | None:
    """Solve near-vertical affine explicit surfaces for the better sampling axis.

    A generated surface like ``y=m*x+b`` with ``abs(m)`` in the trillions is really a
    near-vertical sheet. Sampling x as a domain axis can miss all predicate-valid
    points because the allowed x interval is sub-float-grid wide. Re-solving it as
    ``x=(y-b)/m`` lets the existing explicit-surface sampler use the wide y domain
    while preserving the same predicates and original metadata.
    """
    if not item.axis or not item.expression:
        return None
    graph_domain_axes = [axis for axis in domain_axes if axis in item.expression.identifiers]
    if len(graph_domain_axes) != 1:
        return None
    reoriented_axis = graph_domain_axes[0]
    fit = affine_fit_for_axis(item.expression, context, reoriented_axis)
    if fit is None:
        return None
    slope, intercept = fit
    if not isfinite(slope) or not isfinite(intercept) or abs(slope) <= STEEP_EXPLICIT_SURFACE_SLOPE:
        return None
    expression = LatexExpression.parse(f"({item.axis}-({intercept:.17g}))/({slope:.17g})")
    return replace(item, axis=reoriented_axis, expression=expression)


def _surface_predicates_constrain_solved_axis(item: ClassifiedExpression) -> bool:
    """True if any predicate references ``item.axis`` (the dependent variable).

    When the only restrictions are on domain axes, cell boundaries already follow
    the constraint edges and bisecting mixed cells gives no improvement. The
    expensive marching-squares refinement only earns its keep when the predicate
    is a constraint on the dependent axis itself (e.g. ``z>3`` clipping a
    paraboloid cap), where the true boundary is a contour curve in the (a, b)
    domain rather than an axis-aligned grid edge.
    """
    if not item.axis:
        return False
    for predicate in item.predicates:
        for term in predicate.terms:
            if item.axis in term.identifiers:
                return True
    return False


def refined_quad_faces(
    item: ClassifiedExpression,
    context: EvalContext,
    a_axis: str,
    a_values: list[float],
    b_axis: str,
    b_values: list[float],
    points: list[Point],
    valid_grid: list[list[bool]],
) -> tuple[list[Point], list[int], list[int]]:
    """Like quad_faces but emits boundary-refined triangles for partial-valid quads.

    For grid cells whose four corners straddle the predicate boundary (e.g. the rim of
    a paraboloid cap clipped by ``z>3``), bisect along each mixed-validity edge to find
    the predicate transition, then emit triangles connecting valid corners and the
    boundary points. Without this, the surface boundary follows the grid edges and
    appears as scattered 'fins' at low resolution. The bisection cost is O(mixed cells)
    per surface and is bounded by ``QUAD_BOUNDARY_REFINE_ITERATIONS``.
    """
    width = len(a_values)
    height = len(b_values)
    refined_points = list(points)
    counts: list[int] = []
    indices: list[int] = []
    # Fast path: if every grid corner is valid, no cell needs the bisection
    # branch and we can skip the per-cell setup work. Common for unconstrained
    # surfaces and for surfaces whose domain is already clipped exactly to the
    # validity region (so all corners pass).
    all_valid = all(all(row) for row in valid_grid)
    if all_valid:
        for row in range(height - 1):
            for col in range(width - 1):
                a = row * width + col
                counts.append(4)
                indices.extend([a, a + 1, a + width + 1, a + width])
        return refined_points, counts, indices
    for row in range(height - 1):
        for col in range(width - 1):
            corner_grid = [
                (col, row),
                (col + 1, row),
                (col + 1, row + 1),
                (col, row + 1),
            ]
            corner_indices = [r * width + c for c, r in corner_grid]
            valid_flags = [valid_grid[r][c] for c, r in corner_grid]
            valid_count = sum(1 for flag in valid_flags if flag)
            if valid_count == 0:
                continue
            if valid_count == 4:
                counts.append(4)
                indices.extend(corner_indices)
                continue
            edge_points: dict[int, int] = {}
            for i in range(4):
                j = (i + 1) % 4
                if valid_flags[i] == valid_flags[j]:
                    continue
                if valid_flags[i]:
                    valid_corner = corner_grid[i]
                    invalid_corner = corner_grid[j]
                else:
                    valid_corner = corner_grid[j]
                    invalid_corner = corner_grid[i]
                crossing = _bisect_predicate_crossing(
                    item,
                    context,
                    a_axis,
                    b_axis,
                    a_values[valid_corner[0]],
                    b_values[valid_corner[1]],
                    a_values[invalid_corner[0]],
                    b_values[invalid_corner[1]],
                )
                if crossing is None:
                    continue
                refined_points.append(crossing)
                edge_points[i] = len(refined_points) - 1
            polygon: list[int] = []
            for i in range(4):
                if valid_flags[i]:
                    polygon.append(corner_indices[i])
                if i in edge_points:
                    polygon.append(edge_points[i])
            if len(polygon) < 3:
                continue
            for k in range(1, len(polygon) - 1):
                counts.append(3)
                indices.extend([polygon[0], polygon[k], polygon[k + 1]])
    return refined_points, counts, indices


def _bisect_predicate_crossing(
    item: ClassifiedExpression,
    context: EvalContext,
    a_axis: str,
    b_axis: str,
    valid_a: float,
    valid_b: float,
    invalid_a: float,
    invalid_b: float,
) -> Point | None:
    """Bisect along the segment from a valid sample to an invalid one until the predicate
    transition is localized; return the last sample that still satisfies the predicate."""
    if not item.axis or not item.expression:
        return None
    inside_a, inside_b = valid_a, valid_b
    outside_a, outside_b = invalid_a, invalid_b
    last_valid_point: Point | None = None
    for _ in range(QUAD_BOUNDARY_REFINE_ITERATIONS):
        mid_a = (inside_a + outside_a) / 2.0
        mid_b = (inside_b + outside_b) / 2.0
        variables: dict[str, float] = {a_axis: mid_a, b_axis: mid_b}
        try:
            target = item.expression.eval(context, variables)
        except Exception:
            return None
        variables[item.axis] = target
        if explicit_surface_predicates_satisfied_half_open(item, context, variables):
            inside_a, inside_b = mid_a, mid_b
            last_valid_point = point_from_variables(variables)
        else:
            outside_a, outside_b = mid_a, mid_b
    if last_valid_point is None:
        # Fall back to the originally-valid corner sample so the boundary at least
        # tracks the cell edge instead of degenerating to a missing fin.
        variables = {a_axis: valid_a, b_axis: valid_b}
        try:
            target = item.expression.eval(context, variables)
        except Exception:
            return None
        variables[item.axis] = target
        last_valid_point = point_from_variables(variables)
    return last_valid_point


def explicit_surface_domain_bounds(
    item: ClassifiedExpression,
    context: EvalContext,
) -> dict[str, tuple[float, float]]:
    if not item.axis or not item.expression:
        raise ValueError("explicit surface missing axis or expression")
    bounds = collect_constant_bounds(item.predicates, context)
    domain_axes = [axis for axis in ("x", "y", "z") if axis != item.axis]
    inferred_bounds = infer_explicit_domain_bounds(item, context, domain_axes, bounds)
    return {
        axis: axis_bounds(axis, inferred_bounds, item.ir.source.viewport_bounds)
        for axis in domain_axes
    }


def sample_axis_values(
    low: float,
    high: float,
    resolution: int,
    extra_values: list[float] | None = None,
) -> list[float]:
    values = {round(value, 10): value for value in linspace(low, high, resolution)}
    for value in extra_values or []:
        if value < low - 1e-8 or value > high + 1e-8:
            continue
        clamped = low if abs(value - low) <= 1e-8 else high if abs(value - high) <= 1e-8 else value
        values[round(clamped, 10)] = clamped
    # Add boundary-nudge samples just inside each endpoint so that the
    # half-open predicate evaluation keeps the mesh within ~BOUNDARY_NUDGE
    # of the domain edge.  Without these, the exclusive side of a strict
    # bound loses an entire grid cell (multi-unit gap).
    if high - low > BOUNDARY_NUDGE * 4:
        for nudge in (low + BOUNDARY_NUDGE, high - BOUNDARY_NUDGE):
            key = round(nudge, 10)
            if key not in values:
                values[key] = nudge
    return [values[key] for key in sorted(values)]


def axis_bounds(
    axis: str,
    bounds: dict[str, tuple[float | None, float | None]],
    fallback_bounds: dict[str, tuple[float, float]] | None = None,
) -> tuple[float, float]:
    low, high = bounds.get(axis, (None, None))
    fallback_low, fallback_high = (fallback_bounds or {}).get(axis, DEFAULT_BOUNDS)
    return (fallback_low if low is None else low, fallback_high if high is None else high)


def point_from_variables(variables: dict[str, float]) -> Point:
    return (float(variables["x"]), float(variables["y"]), float(variables["z"]))


def infer_explicit_domain_bounds(
    item: ClassifiedExpression,
    context: EvalContext,
    domain_axes: list[str],
    bounds: dict[str, tuple[float | None, float | None]],
) -> dict[str, tuple[float | None, float | None]]:
    if not item.axis or not item.expression:
        return bounds
    if all(axis_has_complete_bounds(axis, bounds) for axis in domain_axes):
        return bounds

    inferred = dict(bounds)
    viewport_bounds = item.ir.source.viewport_bounds or {}
    flat_axis = _explicit_flat_axis(item, domain_axes, inferred)
    for axis in domain_axes:
        if axis_has_complete_bounds(axis, inferred):
            continue
        if explicit_axis_is_unconstrained(item, axis):
            if axis == flat_axis:
                inferred[axis] = (0.0, 0.0)
                continue
            fallback = viewport_bounds.get(axis)
            if fallback is not None:
                inferred[axis] = fallback
    if all(axis_has_complete_bounds(axis, inferred) for axis in domain_axes):
        return inferred

    sqrt_bounds = infer_single_axis_symmetric_sqrt_bounds(item, context, domain_axes, inferred)
    if sqrt_bounds is not None:
        return sqrt_bounds

    affine_bounds = infer_affine_clipped_domain_bounds(item, context, domain_axes, inferred)
    if affine_bounds is not None and all(axis_has_complete_bounds(axis, affine_bounds) for axis in domain_axes):
        return affine_bounds
    if affine_bounds is not None:
        inferred = affine_bounds

    constants = numeric_constants_for_item(item)
    broad_low, broad_high = broad_bounds_from_constants(constants)
    ranges: dict[str, tuple[float, float]] = {}
    steps: dict[str, float] = {}
    viewport_bounds = item.ir.source.viewport_bounds or {}
    for axis in domain_axes:
        low, high = inferred.get(axis, (None, None))
        viewport = viewport_bounds.get(axis)
        sample_low = (viewport[0] if viewport is not None else broad_low) if low is None else low
        sample_high = (viewport[1] if viewport is not None else broad_high) if high is None else high
        if low is None and high is not None and sample_low >= high:
            sample_low = high - max(5.0, abs(high) * 0.75)
        if high is None and low is not None and sample_high <= low:
            sample_high = low + max(5.0, abs(low) * 0.75)
        if sample_low >= sample_high:
            continue
        ranges[axis] = (sample_low, sample_high)
        steps[axis] = (sample_high - sample_low) / float(INFERENCE_SAMPLES - 1)
    if len(ranges) != 2:
        return inferred

    single_axis = infer_single_missing_axis_bounds(item, context, domain_axes, inferred, ranges)
    if single_axis is not None:
        return single_axis

    active: dict[str, list[float]] = {axis: [] for axis in domain_axes}
    a_axis, b_axis = domain_axes
    a0, a1 = ranges[a_axis]
    b0, b1 = ranges[b_axis]
    for b in linspace(b0, b1, INFERENCE_SAMPLES):
        for a in linspace(a0, a1, INFERENCE_SAMPLES):
            variables = {a_axis: a, b_axis: b}
            if explicit_point_satisfies(item, context, variables):
                active[a_axis].append(a)
                active[b_axis].append(b)

    if not any(active.values()):
        return inferred

    for axis in domain_axes:
        previous_low, previous_high = inferred.get(axis, (None, None))
        values = active[axis]
        if not values:
            continue
        step = steps.get(axis, 0.0)
        low = previous_low if previous_low is not None else max(ranges[axis][0], min(values) - step)
        high = previous_high if previous_high is not None else min(ranges[axis][1], max(values) + step)
        if low < high:
            inferred[axis] = (low, high)
    return inferred


@dataclass(frozen=True)
class AffineHalfPlane:
    a: float
    b: float
    c: float

    def evaluate(self, point: tuple[float, float]) -> float:
        return self.a * point[0] + self.b * point[1] + self.c


def infer_affine_clipped_domain_bounds(
    item: ClassifiedExpression,
    context: EvalContext,
    domain_axes: list[str],
    bounds: dict[str, tuple[float | None, float | None]],
) -> dict[str, tuple[float | None, float | None]] | None:
    if not item.axis or not item.expression or len(domain_axes) != 2:
        return None
    halfplanes = affine_domain_halfplanes(item, context, domain_axes)
    if len(halfplanes) < 2:
        return None

    constants = numeric_constants_for_item(item)
    broad_low, broad_high = broad_bounds_from_constants(constants)
    viewport_bounds = item.ir.source.viewport_bounds or {}
    ranges: dict[str, tuple[float, float]] = {}
    for axis in domain_axes:
        low, high = bounds.get(axis, (None, None))
        viewport = viewport_bounds.get(axis)
        sample_low = (viewport[0] if viewport is not None else broad_low) if low is None else low
        sample_high = (viewport[1] if viewport is not None else broad_high) if high is None else high
        if sample_low >= sample_high:
            return None
        ranges[axis] = (sample_low, sample_high)

    a_axis, b_axis = domain_axes
    a0, a1 = ranges[a_axis]
    b0, b1 = ranges[b_axis]
    polygon = [(a0, b0), (a1, b0), (a1, b1), (a0, b1)]
    for halfplane in halfplanes:
        polygon = clip_polygon_to_halfplane(polygon, halfplane)
        if not polygon:
            return None

    a_values = [point[0] for point in polygon]
    b_values = [point[1] for point in polygon]
    if not a_values or not b_values:
        return None
    inferred = dict(bounds)
    changed = False
    for axis, values in ((a_axis, a_values), (b_axis, b_values)):
        previous_low, previous_high = inferred.get(axis, (None, None))
        range_low, range_high = ranges[axis]
        polygon_low = min(values)
        polygon_high = max(values)
        low = previous_low
        high = previous_high
        if low is None and polygon_low > range_low + POLYNOMIAL_FIT_TOLERANCE:
            low = polygon_low
            changed = True
        if high is None and polygon_high < range_high - POLYNOMIAL_FIT_TOLERANCE:
            high = polygon_high
            changed = True
        if low is not None and high is not None and low >= high:
            return None
        if low is not None or high is not None:
            inferred[axis] = (low, high)
    return inferred if changed else None


def affine_domain_halfplanes(
    item: ClassifiedExpression,
    context: EvalContext,
    domain_axes: list[str],
) -> list[AffineHalfPlane]:
    halfplanes: list[AffineHalfPlane] = []
    for predicate in item.predicates:
        for left, op, right in zip(predicate.terms[:-1], predicate.ops, predicate.terms[1:], strict=True):
            if op in {"<", "<="}:
                fit = fit_affine_domain_residual(item, context, domain_axes, left, right)
            elif op in {">", ">="}:
                fit = fit_affine_domain_residual(item, context, domain_axes, right, left)
            else:
                continue
            if fit is None:
                continue
            a, b, c = fit
            if abs(a) <= POLYNOMIAL_FIT_TOLERANCE and abs(b) <= POLYNOMIAL_FIT_TOLERANCE:
                continue
            halfplanes.append(AffineHalfPlane(a, b, c))
    return halfplanes


def fit_affine_domain_residual(
    item: ClassifiedExpression,
    context: EvalContext,
    domain_axes: list[str],
    left: LatexExpression,
    right: LatexExpression,
) -> tuple[float, float, float] | None:
    if not item.axis or not item.expression:
        return None
    a_axis, b_axis = domain_axes
    samples = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0), (-1.0, 2.0)]
    observed: list[tuple[float, float, float]] = []
    for a_value, b_value in samples:
        variables = {a_axis: a_value, b_axis: b_value}
        try:
            variables[item.axis] = item.expression.eval(context, variables)
            value = left.eval(context, variables) - right.eval(context, variables)
        except Exception:
            return None
        if not isfinite(value):
            return None
        observed.append((a_value, b_value, value))
    c = observed[0][2]
    a = observed[1][2] - c
    b = observed[2][2] - c
    for a_value, b_value, value in observed:
        predicted = a * a_value + b * b_value + c
        if abs(predicted - value) > POLYNOMIAL_FIT_TOLERANCE * max(1.0, abs(value)):
            return None
    return (a, b, c)


def clip_polygon_to_halfplane(
    polygon: list[tuple[float, float]],
    halfplane: AffineHalfPlane,
) -> list[tuple[float, float]]:
    clipped: list[tuple[float, float]] = []
    if not polygon:
        return clipped
    previous = polygon[-1]
    previous_value = halfplane.evaluate(previous)
    previous_inside = previous_value <= POLYNOMIAL_FIT_TOLERANCE
    for current in polygon:
        current_value = halfplane.evaluate(current)
        current_inside = current_value <= POLYNOMIAL_FIT_TOLERANCE
        if current_inside != previous_inside:
            denominator = previous_value - current_value
            if abs(denominator) > QUADRATIC_SOLVE_TOLERANCE:
                t = previous_value / denominator
                clipped.append(
                    (
                        previous[0] + t * (current[0] - previous[0]),
                        previous[1] + t * (current[1] - previous[1]),
                    )
                )
        if current_inside:
            clipped.append(current)
        previous = current
        previous_value = current_value
        previous_inside = current_inside
    return clipped


def explicit_axis_is_unconstrained(item: ClassifiedExpression, axis: str) -> bool:
    if item.expression and axis in item.expression.identifiers:
        return False
    if item.inequality and axis in item.inequality.identifiers:
        return False
    for predicate in item.predicates:
        for term in predicate.terms:
            if axis in term.identifiers:
                return False
    return True


FLAT_AXIS_RANGE_FRACTION = 0.10


def _explicit_flat_axis(
    item: ClassifiedExpression,
    domain_axes: list[str],
    bounds: dict[str, tuple[float | None, float | None]],
) -> str | None:
    """Return the axis that should collapse to 0 because the surface is 2D-in-3D.

    Desmos 3D renders an explicit surface like ``y=0.4 {-1.8 <= x <= -1.21}`` as a 1D
    line/strip at z=0 — not a wall extending across the full z viewport. We trigger the
    flat treatment when *all* of:

    * the dependent axis is x or y (not z) — z-axis surfaces are typically planes;
    * one domain axis is fully constrained by predicates (the user is "thinking 2D");
    * the other domain axis is completely unreferenced anywhere;
    * the constrained range is small relative to the viewport (< ``FLAT_AXIS_RANGE_FRACTION``).
      The size guard preserves wall-like geometry such as ``y=20 {-225<x<225}`` whose
      x range exceeds the viewport — those are intended to extrude across z. A tiny
      x-range, by contrast, signals a localized 2D detail at z=0.

    Without this, fixtures whose 2D detail expressions don't mention z get extruded
    across the full ``viewport_bounds["z"]`` and produce tall sheets that dominate the
    scene; conversely, blanket-flattening regresses 3D-wall semantics.
    """
    if not item.axis or item.axis == "z":
        return None
    if "z" not in domain_axes:
        return None
    if not explicit_axis_is_unconstrained(item, "z"):
        return None
    viewport = item.ir.source.viewport_bounds or {}
    z_view = viewport.get("z")
    if z_view is None or z_view[1] <= z_view[0]:
        return None
    z_span = z_view[1] - z_view[0]
    for axis in domain_axes:
        if axis == "z":
            continue
        low, high = bounds.get(axis, (None, None))
        if low is None or high is None or low >= high:
            continue
        if (high - low) <= z_span * FLAT_AXIS_RANGE_FRACTION:
            return "z"
    return None


POLYNOMIAL_FIT_TOLERANCE = 1e-7
QUADRATIC_SOLVE_TOLERANCE = 1e-12


def infer_single_axis_symmetric_sqrt_bounds(
    item: ClassifiedExpression,
    context: EvalContext,
    domain_axes: list[str],
    bounds: dict[str, tuple[float | None, float | None]],
) -> dict[str, tuple[float | None, float | None]] | None:
    """Infer a missing domain interval from sqrt-bounded solved-axis restrictions.

    Fixtures often contain generated chord surfaces such as
    ``y=m*x+c {-sqrt(r^2-x^2)<y<sqrt(r^2-x^2)} {z0<z<z1}``.
    A uniform scan over the full viewport can miss these when the chord is tangent
    and only a sub-unit x interval is visible.  When the solved-axis bounds are a
    symmetric sqrt band, solve the equivalent quadratic interval analytically.
    """
    if not item.axis or not item.expression:
        return None
    missing_axes = [axis for axis in domain_axes if not axis_has_complete_bounds(axis, bounds)]
    if len(missing_axes) != 1:
        return None
    axis = missing_axes[0]
    surface_affine = affine_fit_for_axis(item.expression, context, axis)
    if surface_affine is None:
        return None
    surface_slope, surface_intercept = surface_affine
    inferred = dict(bounds)
    for predicate in item.predicates:
        if len(predicate.terms) != 3 or len(predicate.ops) != 2:
            continue
        if predicate.ops[0] not in {"<", "<="} or predicate.ops[1] not in {"<", "<="}:
            continue
        if predicate.terms[1].python != item.axis:
            continue
        if predicate_identifiers_outside_axis(predicate.terms[0], axis) or predicate_identifiers_outside_axis(predicate.terms[2], axis):
            continue
        band = sqrt_band_fit(predicate.terms[0], predicate.terms[2], context, axis)
        if band is None:
            continue
        center_slope, center_intercept, radius_a, radius_b, radius_c = band
        interval = solve_quadratic_less_than_zero(
            (surface_slope - center_slope) ** 2 - radius_a,
            2.0 * (surface_slope - center_slope) * (surface_intercept - center_intercept) - radius_b,
            (surface_intercept - center_intercept) ** 2 - radius_c,
        )
        if interval is None:
            continue
        low, high = interval
        previous_low, previous_high = inferred.get(axis, (None, None))
        if previous_low is not None:
            low = max(low, previous_low)
        if previous_high is not None:
            high = min(high, previous_high)
        viewport = (item.ir.source.viewport_bounds or {}).get(axis)
        if viewport is not None:
            low = max(low, viewport[0])
            high = min(high, viewport[1])
        if low < high:
            inferred[axis] = (low, high)
            return inferred
    return None


def predicate_identifiers_outside_axis(expression: LatexExpression, axis: str) -> bool:
    return bool((expression.identifiers & {"x", "y", "z"}) - {axis})


def sqrt_band_fit(
    lower: LatexExpression,
    upper: LatexExpression,
    context: EvalContext,
    axis: str,
) -> tuple[float, float, float, float, float] | None:
    sample_sets = (
        (-1.0, 0.0, 1.0, -0.5, 0.5),
        (-0.5, 0.0, 0.5, -0.25, 0.25),
        (-2.0, 0.0, 2.0, -1.0, 1.0),
        (-0.25, 0.0, 0.25, -0.125, 0.125),
    )
    for samples in sample_sets:
        center_samples: list[tuple[float, float]] = []
        radius_samples: list[tuple[float, float]] = []
        for value in samples:
            try:
                low = float(lower.eval(context, {axis: value}))
                high = float(upper.eval(context, {axis: value}))
            except Exception:
                break
            if not all(isfinite(candidate) for candidate in (low, high)) or low > high:
                break
            center = (low + high) / 2.0
            half_width = (high - low) / 2.0
            center_samples.append((value, center))
            radius_samples.append((value, half_width * half_width))
        else:
            center = fit_affine_samples(center_samples)
            radius = fit_quadratic_samples(radius_samples)
            if center is None or radius is None:
                continue
            if all(
                abs((center[0] * value + center[1]) - observed) <= POLYNOMIAL_FIT_TOLERANCE * max(1.0, abs(observed))
                for value, observed in center_samples
            ) and all(
                abs((radius[0] * value * value + radius[1] * value + radius[2]) - observed)
                <= POLYNOMIAL_FIT_TOLERANCE * max(1.0, abs(observed))
                for value, observed in radius_samples
            ):
                return (center[0], center[1], radius[0], radius[1], radius[2])
    return None


def affine_fit_for_axis(
    expression: LatexExpression,
    context: EvalContext,
    axis: str,
) -> tuple[float, float] | None:
    if predicate_identifiers_outside_axis(expression, axis):
        return None
    samples = [(-2.0, None), (-1.0, None), (0.0, None), (1.0, None), (2.0, None)]
    observed: list[tuple[float, float]] = []
    for value, _ in samples:
        try:
            evaluated = float(expression.eval(context, {axis: value}))
        except Exception:
            return None
        if not isfinite(evaluated):
            return None
        observed.append((value, evaluated))
    return fit_affine_samples(observed)


def fit_affine_samples(samples: list[tuple[float, float]]) -> tuple[float, float] | None:
    if len(samples) < 2:
        return None
    x0, y0 = samples[0]
    x1, y1 = next(((x, y) for x, y in samples[1:] if abs(x - x0) > QUADRATIC_SOLVE_TOLERANCE), (x0, y0))
    if abs(x1 - x0) <= QUADRATIC_SOLVE_TOLERANCE:
        return None
    slope = (y1 - y0) / (x1 - x0)
    intercept = y0 - slope * x0
    for x, y in samples:
        if abs((slope * x + intercept) - y) > POLYNOMIAL_FIT_TOLERANCE * max(1.0, abs(y)):
            return None
    return (slope, intercept)


def fit_quadratic_samples(samples: list[tuple[float, float]]) -> tuple[float, float, float] | None:
    if len(samples) < 3:
        return None
    x0, y0 = samples[0]
    x1, y1 = samples[1]
    x2, y2 = samples[2]
    denominator = (x0 - x1) * (x0 - x2) * (x1 - x2)
    if abs(denominator) <= QUADRATIC_SOLVE_TOLERANCE:
        return None
    a = (x2 * (y1 - y0) + x1 * (y0 - y2) + x0 * (y2 - y1)) / denominator
    b = (x2 * x2 * (y0 - y1) + x1 * x1 * (y2 - y0) + x0 * x0 * (y1 - y2)) / denominator
    c = (
        x1 * x2 * (x1 - x2) * y0
        + x2 * x0 * (x2 - x0) * y1
        + x0 * x1 * (x0 - x1) * y2
    ) / denominator
    for x, y in samples:
        predicted = a * x * x + b * x + c
        if abs(predicted - y) > POLYNOMIAL_FIT_TOLERANCE * max(1.0, abs(y)):
            return None
    return (a, b, c)


def solve_quadratic_less_than_zero(
    a: float,
    b: float,
    c: float,
) -> tuple[float, float] | None:
    if abs(a) <= QUADRATIC_SOLVE_TOLERANCE:
        if abs(b) <= QUADRATIC_SOLVE_TOLERANCE:
            return None
        root = -c / b
        if b > 0:
            return (-float("inf"), root)
        return (root, float("inf"))
    discriminant = b * b - 4.0 * a * c
    if discriminant <= QUADRATIC_SOLVE_TOLERANCE:
        return None
    root_span = sqrt(discriminant)
    root_a = (-b - root_span) / (2.0 * a)
    root_b = (-b + root_span) / (2.0 * a)
    low, high = (root_a, root_b) if root_a <= root_b else (root_b, root_a)
    if a < 0:
        return None
    return (low, high)


def infer_single_missing_axis_bounds(
    item: ClassifiedExpression,
    context: EvalContext,
    domain_axes: list[str],
    bounds: dict[str, tuple[float | None, float | None]],
    ranges: dict[str, tuple[float, float]],
) -> dict[str, tuple[float | None, float | None]] | None:
    missing_axes = [axis for axis in domain_axes if not axis_has_complete_bounds(axis, bounds)]
    if len(missing_axes) != 1:
        return None
    axis = missing_axes[0]
    fixed_axis = next(candidate for candidate in domain_axes if candidate != axis)
    if not axis_has_complete_bounds(fixed_axis, bounds):
        return None
    fixed_low, fixed_high = ranges[fixed_axis]
    fixed_values = [fixed_low, (fixed_low + fixed_high) / 2.0, fixed_high]
    low, high = ranges[axis]
    samples = linspace(low, high, SINGLE_AXIS_INFERENCE_SAMPLES)
    active_flags = [
        any(
            explicit_point_satisfies(item, context, {axis: value, fixed_axis: fixed_value}, tol=0.0)
            for fixed_value in fixed_values
        )
        for value in samples
    ]
    active_indices = [index for index, is_active in enumerate(active_flags) if is_active]
    if not active_indices:
        return None
    previous_low, previous_high = bounds.get(axis, (None, None))
    first_active = active_indices[0]
    last_active = active_indices[-1]
    inferred_low = previous_low
    inferred_high = previous_high
    if inferred_low is None:
        if first_active == 0:
            inferred_low = low
        else:
            inferred_low = refine_single_axis_boundary(
                item,
                context,
                axis,
                fixed_axis,
                fixed_values,
                samples[first_active - 1],
                samples[first_active],
            )
    if inferred_high is None:
        if last_active == len(samples) - 1:
            inferred_high = high
        else:
            inferred_high = refine_single_axis_boundary(
                item,
                context,
                axis,
                fixed_axis,
                fixed_values,
                samples[last_active + 1],
                samples[last_active],
            )
    if inferred_low >= inferred_high:
        return None
    inferred = dict(bounds)
    inferred[axis] = (inferred_low, inferred_high)
    return inferred


def refine_single_axis_boundary(
    item: ClassifiedExpression,
    context: EvalContext,
    axis: str,
    fixed_axis: str,
    fixed_values: list[float],
    inactive_value: float,
    active_value: float,
) -> float:
    """Move a sampled one-axis inferred bound onto the predicate transition."""

    inactive = inactive_value
    active = active_value
    for _ in range(BOUNDARY_REFINE_ITERATIONS):
        mid = (inactive + active) / 2.0
        if any(
            explicit_point_satisfies(item, context, {axis: mid, fixed_axis: fixed_value}, tol=0.0)
            for fixed_value in fixed_values
        ):
            active = mid
        else:
            inactive = mid
    return active


def explicit_point_satisfies(
    item: ClassifiedExpression,
    context: EvalContext,
    variables: dict[str, float],
    tol: float = 1e-5,
) -> bool:
    if not item.axis or not item.expression:
        return False
    try:
        target = item.expression.eval(context, variables)
        full_variables = dict(variables)
        full_variables[item.axis] = target
        return explicit_surface_predicates_satisfied(item, context, full_variables, tol=tol)
    except Exception:
        return False


def explicit_surface_sample(
    item: ClassifiedExpression,
    context: EvalContext,
    variables: dict[str, float],
) -> tuple[Point, bool]:
    """Evaluate one explicit-surface grid sample.

    Desmos treats undefined expression/restriction samples as outside the plotted
    domain.  A sqrt restriction such as ``-sqrt(1-x^2)<y<sqrt(1-x^2)`` should clip
    samples with ``abs(x)>1`` instead of making the whole surface unsupported.
    """
    if not item.axis or not item.expression:
        raise ValueError("explicit surface missing axis or expression")
    full_variables = dict(variables)
    try:
        full_variables[item.axis] = item.expression.eval(context, variables)
    except ValueError:
        full_variables[item.axis] = 0.0
        return point_from_variables(full_variables), False
    return (
        point_from_variables(full_variables),
        explicit_surface_predicates_satisfied_half_open(item, context, full_variables),
    )


def explicit_surface_predicates_satisfied_half_open(
    item: ClassifiedExpression,
    context: EvalContext,
    variables: dict[str, float],
) -> bool:
    for predicate in item.predicates:
        try:
            if not predicate.evaluate_half_open(context, variables, tol=HALF_OPEN_TOL):
                return False
        except ValueError:
            return False
    return True


def explicit_surface_predicates_satisfied(
    item: ClassifiedExpression,
    context: EvalContext,
    variables: dict[str, float],
    tol: float = 1e-5,
) -> bool:
    for predicate in item.predicates:
        try:
            if not predicate.evaluate(context, variables, tol=tol):
                return False
        except ValueError:
            return False
    return True


def axis_has_complete_bounds(axis: str, bounds: dict[str, tuple[float | None, float | None]]) -> bool:
    low, high = bounds.get(axis, (None, None))
    return low is not None and high is not None


def numeric_constants_for_item(item: ClassifiedExpression) -> list[float]:
    expressions: list[LatexExpression] = []
    if item.expression:
        expressions.append(item.expression)
    if item.inequality:
        expressions.extend(item.inequality.terms)
    for predicate in item.predicates:
        expressions.extend(predicate.terms)
    constants: list[float] = []
    for expression in expressions:
        constants.extend(numeric_constants(expression))
    return constants


def numeric_constants(expression: LatexExpression) -> list[float]:
    constants: list[float] = []
    for node in ast.walk(expression.tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            constants.append(float(node.value))
    return constants


def broad_bounds_from_constants(constants: list[float]) -> tuple[float, float]:
    magnitude = max([abs(value) for value in constants] + [max(abs(DEFAULT_BOUNDS[0]), abs(DEFAULT_BOUNDS[1]))])
    padded = magnitude + max(5.0, magnitude * 0.75)
    return (-padded, padded)


def _solved_axis_entirely_outside_viewport(
    item: ClassifiedExpression,
    points: list[Point],
    face_indices: list[int],
) -> bool:
    """Return True if every face vertex on the solved axis lies entirely outside the viewport.

    This suppresses explicit surfaces whose solved-axis output has zero overlap
    with the source viewport — geometry that Desmos itself never renders because
    it falls outside the visible volume.  Only the solved axis is checked; domain
    axes are already bounded by restrictions or inference.
    """
    if not item.axis:
        return False
    viewport_bounds = item.ir.source.viewport_bounds
    if not viewport_bounds or item.axis not in viewport_bounds:
        return False
    vmin, vmax = viewport_bounds[item.axis]
    axis_index = {"x": 0, "y": 1, "z": 2}[item.axis]
    used_indices = set(face_indices)
    if not used_indices:
        return False
    values = [points[i][axis_index] for i in used_indices if i < len(points)]
    if not values:
        return False
    return min(values) > vmax or max(values) < vmin


def _domain_axes_have_finite_constant_bounds(
    bounds: dict[str, tuple[float | None, float | None]],
    domain_axes: list[str],
) -> bool:
    for axis in domain_axes:
        low, high = bounds.get(axis, (None, None))
        if low is None or high is None:
            return False
    return True


def _has_constant_solved_axis_value(item: ClassifiedExpression) -> bool:
    return bool(item.expression and not (item.expression.identifiers & {"x", "y", "z"}))
