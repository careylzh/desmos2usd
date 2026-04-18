from __future__ import annotations

import ast

from desmos2usd.eval.context import EvalContext
from desmos2usd.parse.classify import ClassifiedExpression
from desmos2usd.parse.latex_subset import LatexExpression
from desmos2usd.parse.predicates import collect_constant_bounds
from desmos2usd.tessellate.mesh import GeometryData, Point, linspace, quad_faces


DEFAULT_BOUNDS = (-5.0, 5.0)
INFERENCE_SAMPLES = 64
SINGLE_AXIS_INFERENCE_SAMPLES = 1024
BOUNDARY_REFINE_ITERATIONS = 60


def tessellate_explicit_surface(
    item: ClassifiedExpression,
    context: EvalContext,
    resolution: int = 18,
    axis_samples: dict[str, list[float]] | None = None,
) -> GeometryData:
    if not item.axis or not item.expression:
        raise ValueError("explicit surface missing axis or expression")
    domain_axes = [axis for axis in ("x", "y", "z") if axis != item.axis]
    surface_bounds = explicit_surface_domain_bounds(item, context)
    a0, a1 = surface_bounds[domain_axes[0]]
    b0, b1 = surface_bounds[domain_axes[1]]
    axis_samples = axis_samples or {}
    a_values = sample_axis_values(a0, a1, resolution, axis_samples.get(domain_axes[0]))
    b_values = sample_axis_values(b0, b1, resolution, axis_samples.get(domain_axes[1]))
    points: list[Point] = []
    valid_grid: list[list[bool]] = []
    for b in b_values:
        row_valid: list[bool] = []
        for a in a_values:
            variables = {domain_axes[0]: a, domain_axes[1]: b}
            target = item.expression.eval(context, variables)
            variables[item.axis] = target
            point = point_from_variables(variables)
            points.append(point)
            row_valid.append(all(predicate.evaluate_half_open(context, variables, tol=1e-5) for predicate in item.predicates))
        valid_grid.append(row_valid)
    counts, indices = quad_faces(len(a_values), len(b_values), valid_grid)
    if not counts and resolution < 64:
        return tessellate_explicit_surface(
            item,
            context,
            resolution=min(64, resolution * 2),
            axis_samples=axis_samples,
        )
    if counts and _solved_axis_entirely_outside_viewport(item, points, indices):
        return GeometryData(kind="Mesh", points=[], face_vertex_counts=[], face_vertex_indices=[])
    return GeometryData(kind="Mesh", points=points, face_vertex_counts=counts, face_vertex_indices=indices)


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
    for axis in domain_axes:
        if axis_has_complete_bounds(axis, inferred):
            continue
        if explicit_axis_is_unconstrained(item, axis):
            fallback = viewport_bounds.get(axis)
            if fallback is not None:
                inferred[axis] = fallback
    if all(axis_has_complete_bounds(axis, inferred) for axis in domain_axes):
        return inferred

    constants = numeric_constants_for_item(item)
    broad_low, broad_high = broad_bounds_from_constants(constants)
    ranges: dict[str, tuple[float, float]] = {}
    steps: dict[str, float] = {}
    for axis in domain_axes:
        low, high = inferred.get(axis, (None, None))
        sample_low = broad_low if low is None else low
        sample_high = broad_high if high is None else high
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
        return all(predicate.evaluate(context, full_variables, tol=tol) for predicate in item.predicates)
    except Exception:
        return False


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
