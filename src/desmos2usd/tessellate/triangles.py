from __future__ import annotations

from desmos2usd.eval.context import EvalContext
from desmos2usd.parse.classify import ClassifiedExpression
from desmos2usd.tessellate.mesh import GeometryData


def tessellate_triangle_mesh(item: ClassifiedExpression, context: EvalContext) -> GeometryData:
    if not item.triangle_mesh:
        raise ValueError("triangle mesh missing triangle expression")
    points = []
    counts = []
    indices = []
    for triangle in item.triangle_mesh.triangles:
        base = len(points)
        for vertex in triangle:
            points.append(vertex.eval(context, {}))
        counts.append(3)
        indices.extend([base, base + 1, base + 2])
    return GeometryData(kind="Mesh", points=points, face_vertex_counts=counts, face_vertex_indices=indices)
