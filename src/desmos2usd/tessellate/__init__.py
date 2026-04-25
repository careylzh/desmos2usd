from __future__ import annotations

from desmos2usd.eval.context import EvalContext
from desmos2usd.parse.classify import ClassifiedExpression
from desmos2usd.tessellate.implicit import tessellate_implicit_surface
from desmos2usd.tessellate.mesh import GeometryData
from desmos2usd.tessellate.parametric import tessellate_parametric_curve
from desmos2usd.tessellate.slabs import tessellate_inequality_region
from desmos2usd.tessellate.surfaces import tessellate_explicit_surface
from desmos2usd.tessellate.triangles import tessellate_triangle_mesh


def tessellate(
    item: ClassifiedExpression,
    context: EvalContext,
    resolution: int = 18,
    explicit_surface_axis_samples: dict[str, list[float]] | None = None,
) -> GeometryData:
    if item.kind == "explicit_surface":
        return tessellate_explicit_surface(
            item,
            context,
            resolution=resolution,
            axis_samples=explicit_surface_axis_samples,
        )
    if item.kind == "implicit_surface":
        return tessellate_implicit_surface(item, context, resolution=max(8, resolution))
    if item.kind == "inequality_region":
        return tessellate_inequality_region(item, context, resolution=max(4, resolution - 4))
    if item.kind == "parametric_curve":
        return tessellate_parametric_curve(item, context, resolution=max(8, resolution * 2))
    if item.kind == "triangle_mesh":
        return tessellate_triangle_mesh(item, context)
    raise ValueError(f"Unsupported classified geometry kind {item.kind}")
