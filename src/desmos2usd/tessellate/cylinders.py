from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import cos, isfinite, pi, sin, sqrt

from desmos2usd.eval.context import EvalContext
from desmos2usd.parse.classify import ClassifiedExpression
from desmos2usd.parse.latex_subset import LatexExpression
from desmos2usd.parse.predicates import ComparisonPredicate, collect_constant_bounds
from desmos2usd.tessellate.mesh import GeometryData, Point, linspace
from desmos2usd.tessellate.surfaces import point_from_variables


AXES = ("x", "y", "z")
FIT_DELTA = 1.0
QUADRATIC_TOLERANCE = 1e-5


ResidualFunction = Callable[[EvalContext, dict[str, float]], float]


@dataclass(frozen=True)
class CircleProfile:
    center: tuple[float, float]
    radius: float


def tessellate_circular_inequality_extrusion(
    item: ClassifiedExpression,
    context: EvalContext,
    resolution: int,
) -> GeometryData | None:
    residual = signed_residual_for_predicate(item.inequality)
    if residual is None:
        return None
    return tessellate_circular_extrusion(item, context, residual, resolution=resolution, caps=True)


def tessellate_circular_implicit_surface(
    item: ClassifiedExpression,
    context: EvalContext,
    resolution: int,
) -> GeometryData | None:
    if item.expression is None:
        return None

    def residual(ctx: EvalContext, variables: dict[str, float]) -> float:
        return item.expression.eval(ctx, variables)

    return tessellate_circular_extrusion(item, context, residual, resolution=resolution, caps=False)


def signed_residual_for_predicate(predicate: ComparisonPredicate | None) -> ResidualFunction | None:
    if predicate is None or len(predicate.terms) != 2 or len(predicate.ops) != 1:
        return None
    left, right = predicate.terms
    op = predicate.ops[0]
    if op in {"<", "<="}:
        return lambda context, variables: left.eval(context, variables) - right.eval(context, variables)
    if op in {">", ">="}:
        return lambda context, variables: right.eval(context, variables) - left.eval(context, variables)
    return None


def tessellate_circular_extrusion(
    item: ClassifiedExpression,
    context: EvalContext,
    residual: ResidualFunction,
    resolution: int,
    caps: bool,
) -> GeometryData | None:
    bounds = collect_constant_bounds(item.predicates, context)
    for extrude_axis in AXES:
        low, high = bounds.get(extrude_axis, (None, None))
        if low is None or high is None or low >= high:
            continue
        shape_axes = tuple(axis for axis in AXES if axis != extrude_axis)
        layer_count = max(3, min(96, resolution))
        profiles = [
            (value, fit_circle_profile(context, residual, shape_axes, extrude_axis, value))
            for value in linspace(low, high, layer_count)
        ]
        if any(profile is None for _, profile in profiles):
            continue
        segment_count = max(16, min(128, resolution * 2))
        return build_circular_mesh(shape_axes, extrude_axis, profiles, segment_count, caps)
    return None


def fit_circle_profile(
    context: EvalContext,
    residual: ResidualFunction,
    shape_axes: tuple[str, str],
    extrude_axis: str,
    extrude_value: float,
) -> CircleProfile | None:
    def evaluate(a: float, b: float) -> float:
        variables = {shape_axes[0]: a, shape_axes[1]: b, extrude_axis: extrude_value}
        value = residual(context, variables)
        if not isfinite(value):
            raise ValueError("non-finite residual")
        return value

    try:
        f00 = evaluate(0.0, 0.0)
        fpx = evaluate(FIT_DELTA, 0.0)
        fmx = evaluate(-FIT_DELTA, 0.0)
        fpy = evaluate(0.0, FIT_DELTA)
        fmy = evaluate(0.0, -FIT_DELTA)
        fpypy = evaluate(FIT_DELTA, FIT_DELTA)
    except Exception:
        return None

    ax = (fpx + fmx - 2.0 * f00) / (2.0 * FIT_DELTA * FIT_DELTA)
    ay = (fpy + fmy - 2.0 * f00) / (2.0 * FIT_DELTA * FIT_DELTA)
    bx = (fpx - fmx) / (2.0 * FIT_DELTA)
    by = (fpy - fmy) / (2.0 * FIT_DELTA)
    cross = fpypy - fpx - fpy + f00
    orientation = 1.0
    if ax < -QUADRATIC_TOLERANCE and ay < -QUADRATIC_TOLERANCE:
        orientation = -1.0
        f00, fpx, fmx, fpy, fmy, fpypy = (-f00, -fpx, -fmx, -fpy, -fmy, -fpypy)
        ax, ay, bx, by, cross = (-ax, -ay, -bx, -by, -cross)
    scale = (ax + ay) / 2.0
    if scale <= QUADRATIC_TOLERANCE:
        return None
    if abs(ax - ay) > max(QUADRATIC_TOLERANCE, abs(scale) * 0.05):
        return None
    if abs(cross) > max(QUADRATIC_TOLERANCE, abs(scale) * 0.05):
        return None

    center_a = -bx / (2.0 * ax)
    center_b = -by / (2.0 * ay)
    try:
        center_value = orientation * evaluate(center_a, center_b)
    except Exception:
        return None
    radius_squared = -center_value / scale
    if radius_squared <= 0.0:
        return None
    radius = sqrt(radius_squared)
    if not all(isfinite(value) for value in (center_a, center_b, radius)):
        return None
    if not circle_boundary_matches(context, residual, orientation, shape_axes, extrude_axis, extrude_value, center_a, center_b, radius):
        return None
    return CircleProfile(center=(center_a, center_b), radius=radius)


def circle_boundary_matches(
    context: EvalContext,
    residual: ResidualFunction,
    orientation: float,
    shape_axes: tuple[str, str],
    extrude_axis: str,
    extrude_value: float,
    center_a: float,
    center_b: float,
    radius: float,
) -> bool:
    tolerance = max(1e-4, radius * radius * 1e-5)
    for a, b in (
        (center_a + radius, center_b),
        (center_a - radius, center_b),
        (center_a, center_b + radius),
        (center_a, center_b - radius),
    ):
        variables = {shape_axes[0]: a, shape_axes[1]: b, extrude_axis: extrude_value}
        try:
            if abs(orientation * residual(context, variables)) > tolerance:
                return False
        except Exception:
            return False
    return True


def build_circular_mesh(
    shape_axes: tuple[str, str],
    extrude_axis: str,
    profiles: list[tuple[float, CircleProfile | None]],
    segment_count: int,
    caps: bool,
) -> GeometryData:
    points: list[Point] = []
    counts: list[int] = []
    indices: list[int] = []
    angles = [2.0 * pi * index / segment_count for index in range(segment_count)]
    for extrude_value, profile in profiles:
        assert profile is not None
        for angle in angles:
            variables = {
                shape_axes[0]: profile.center[0] + profile.radius * cos(angle),
                shape_axes[1]: profile.center[1] + profile.radius * sin(angle),
                extrude_axis: extrude_value,
            }
            points.append(point_from_variables(variables))

    for layer in range(len(profiles) - 1):
        lower = layer * segment_count
        upper = (layer + 1) * segment_count
        for segment in range(segment_count):
            next_segment = (segment + 1) % segment_count
            counts.append(4)
            indices.extend([lower + segment, lower + next_segment, upper + next_segment, upper + segment])

    if caps:
        add_cap(points, counts, indices, shape_axes, extrude_axis, profiles[0], ring_start=0, segment_count=segment_count, reverse=True)
        last_ring_start = (len(profiles) - 1) * segment_count
        add_cap(
            points,
            counts,
            indices,
            shape_axes,
            extrude_axis,
            profiles[-1],
            ring_start=last_ring_start,
            segment_count=segment_count,
            reverse=False,
        )

    return GeometryData(kind="Mesh", points=points, face_vertex_counts=counts, face_vertex_indices=indices)


def add_cap(
    points: list[Point],
    counts: list[int],
    indices: list[int],
    shape_axes: tuple[str, str],
    extrude_axis: str,
    profile_entry: tuple[float, CircleProfile | None],
    ring_start: int,
    segment_count: int,
    reverse: bool,
) -> None:
    extrude_value, profile = profile_entry
    assert profile is not None
    center_index = len(points)
    points.append(point_from_variables({shape_axes[0]: profile.center[0], shape_axes[1]: profile.center[1], extrude_axis: extrude_value}))
    for segment in range(segment_count):
        next_segment = (segment + 1) % segment_count
        counts.append(3)
        if reverse:
            indices.extend([center_index, ring_start + next_segment, ring_start + segment])
        else:
            indices.extend([center_index, ring_start + segment, ring_start + next_segment])
