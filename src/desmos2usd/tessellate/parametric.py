from __future__ import annotations

from desmos2usd.eval.context import EvalContext
from desmos2usd.parse.classify import ClassifiedExpression
from desmos2usd.tessellate.mesh import GeometryData, linspace, quad_faces


def tessellate_parametric_curve(item: ClassifiedExpression, context: EvalContext, resolution: int = 32) -> GeometryData:
    if not item.vector:
        raise ValueError("parametric curve missing vector")
    low, high = item.t_bounds
    points = []
    params = []
    parameter = item.parameter or "t"
    for value in linspace(low, high, resolution):
        variables = {parameter: value}
        point = item.vector.eval(context, variables)
        points.append(point)
        params.append(variables)
    return GeometryData(kind="BasisCurves", points=points, curve_vertex_counts=[len(points)], sample_parameters=params)


def tessellate_parametric_surface(item: ClassifiedExpression, context: EvalContext, resolution: int = 18) -> GeometryData:
    if not item.vector:
        raise ValueError("parametric surface missing vector")
    u_values = linspace(item.u_bounds[0], item.u_bounds[1], resolution)
    v_values = linspace(item.v_bounds[0], item.v_bounds[1], resolution)
    points = []
    params = []
    valid = []
    for v in v_values:
        valid_row = []
        for u in u_values:
            variables = {"u": u, "v": v}
            point = item.vector.eval(context, variables)
            points.append(point)
            params.append(variables)
            validation_variables = {"x": point[0], "y": point[1], "z": point[2], **variables}
            valid_row.append(all(predicate.evaluate(context, validation_variables) for predicate in item.predicates))
        valid.append(valid_row)
    counts, indices = quad_faces(len(u_values), len(v_values), valid=valid)
    return GeometryData(
        kind="Mesh",
        points=points,
        face_vertex_counts=counts,
        face_vertex_indices=indices,
        sample_parameters=params,
    )
