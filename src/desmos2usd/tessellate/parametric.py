from __future__ import annotations

from desmos2usd.eval.context import EvalContext
from desmos2usd.parse.classify import ClassifiedExpression
from desmos2usd.tessellate.mesh import GeometryData, linspace


def tessellate_parametric_curve(item: ClassifiedExpression, context: EvalContext, resolution: int = 32) -> GeometryData:
    if not item.vector:
        raise ValueError("parametric curve missing vector")
    low, high = item.t_bounds
    points = []
    params = []
    for t in linspace(low, high, resolution):
        variables = {"t": t}
        point = item.vector.eval(context, variables)
        points.append(point)
        params.append(variables)
    return GeometryData(kind="BasisCurves", points=points, curve_vertex_counts=[len(points)], sample_parameters=params)

