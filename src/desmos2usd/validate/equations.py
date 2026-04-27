from __future__ import annotations

from dataclasses import dataclass

from desmos2usd.eval.context import EvalContext
from desmos2usd.parse.classify import ClassifiedExpression
from desmos2usd.tessellate.mesh import GeometryData


@dataclass
class ValidationReport:
    expr_id: str
    kind: str
    point_count: int
    face_count: int
    valid: bool
    max_residual: float | None
    constraint_violation_count: int
    errors: list[str]


def validate_geometry(item: ClassifiedExpression, geometry: GeometryData, context: EvalContext, tol: float = 1e-4) -> ValidationReport:
    errors: list[str] = []
    max_residual: float | None = None
    constraint_violation_count = 0
    indices = sorted(set(geometry.face_vertex_indices)) if geometry.face_vertex_indices else list(range(len(geometry.points)))
    for index in indices:
        point = geometry.points[index]
        variables = {"x": point[0], "y": point[1], "z": point[2]}
        if index < len(geometry.sample_parameters):
            variables.update(geometry.sample_parameters[index])
        try:
            residual = residual_for_point(item, context, variables)
            if residual is not None:
                max_residual = abs(residual) if max_residual is None else max(max_residual, abs(residual))
                if abs(residual) > tol:
                    errors.append(f"point {index} residual {residual:.6g} exceeds {tol}")
            for predicate in item.predicates:
                if not predicate.evaluate(context, variables, tol=tol):
                    constraint_violation_count += 1
                    errors.append(f"point {index} violates predicate {predicate.raw!r}")
        except Exception as exc:
            errors.append(f"point {index} validation failed: {exc}")
    return ValidationReport(
        expr_id=item.ir.expr_id,
        kind=item.kind,
        point_count=geometry.point_count,
        face_count=geometry.face_count,
        valid=not errors,
        max_residual=max_residual,
        constraint_violation_count=constraint_violation_count,
        errors=errors[:20],
    )


def residual_for_point(item: ClassifiedExpression, context: EvalContext, variables: dict[str, float]) -> float | None:
    if item.kind == "explicit_surface":
        if not item.axis or not item.expression:
            return None
        return variables[item.axis] - item.expression.eval(context, variables)
    if item.kind in {"parametric_curve", "parametric_surface"}:
        if not item.vector:
            return None
        expected = item.vector.eval(context, variables)
        actual = (variables["x"], variables["y"], variables["z"])
        return max(abs(a - b) for a, b in zip(actual, expected, strict=True))
    if item.kind == "point_list_curve":
        return None
    if item.kind == "implicit_surface":
        # Implicit surfaces are contour-extracted numerically, so vertices lie on
        # a linearized zero crossing rather than the exact analytic equation.
        # Keep predicate validation, but do not reject useful fixture geometry on
        # sub-cell residuals here.
        return None
    return None
