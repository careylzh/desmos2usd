from __future__ import annotations

import colorsys
import hashlib
import math
import random as py_random
import re
from dataclasses import dataclass, field
from itertools import product
from math import isfinite

from desmos2usd.eval.context import EvalContext, FunctionDef
from desmos2usd.ir import ExpressionIR, GraphIR
from desmos2usd.parse.latex_subset import (
    LatexExpression,
    find_top_level,
    normalize_identifier,
    normalize_latex_delimiters,
    split_top_level,
    strip_wrapping_parens,
)
from desmos2usd.parse.predicates import ComparisonPredicate, looks_like_restriction, parse_predicate, parse_predicates, split_restrictions


GRAPH_VARIABLES = {"x", "y", "z", "t", "u", "v"}


@dataclass
class VectorExpression:
    raw: str
    components: tuple[LatexExpression, LatexExpression, LatexExpression]

    def eval(self, context: EvalContext, variables: dict[str, float]) -> tuple[float, float, float]:
        return tuple(component.eval(context, variables) for component in self.components)  # type: ignore[return-value]


@dataclass
class TriangleMeshExpression:
    raw: str
    triangles: tuple[tuple[VectorExpression, VectorExpression, VectorExpression], ...]


@dataclass
class ClassifiedExpression:
    ir: ExpressionIR
    kind: str
    predicates: list[ComparisonPredicate] = field(default_factory=list)
    axis: str | None = None
    expression: LatexExpression | None = None
    inequality: ComparisonPredicate | None = None
    vector: VectorExpression | None = None
    point_list: tuple[VectorExpression, ...] | None = None
    triangle_mesh: TriangleMeshExpression | None = None
    parameter: str = "t"
    t_bounds: tuple[float, float] = (0.0, 1.0)
    u_bounds: tuple[float, float] = (0.0, 1.0)
    v_bounds: tuple[float, float] = (0.0, 1.0)

    @property
    def metadata_constraints(self) -> str:
        return "; ".join(predicate.raw for predicate in self.predicates)


@dataclass
class ClassificationResult:
    context: EvalContext
    classified: list[ClassifiedExpression]
    definitions: list[ExpressionIR]


@dataclass
class DefinitionRegistrationResult:
    definitions: list[ExpressionIR]
    definition_ids: set[str]
    failures: list[tuple[ExpressionIR, Exception]]


def classify_graph(graph: GraphIR) -> ClassificationResult:
    context = EvalContext(
        degree_mode=bool(graph.source.view_metadata.get("degree_mode")),
        random_seed=str(graph.raw_state.get("randomSeed") or graph.source.graph_hash or ""),
    )
    classified: list[ClassifiedExpression] = []
    registration = register_definitions(graph.expressions, context)
    for expr, exc in registration.failures:
        if expr.renderable_candidate:
            raise ValueError(f"Failed to parse definition {expr.expr_id} {expr.latex!r}: {exc}") from exc

    for expr in graph.expressions:
        if not expr.renderable_candidate or expr.expr_id in registration.definition_ids:
            continue
        resolved = resolve_color_latex(expr.color_latex, context)
        effective_color = f"#{resolved[0]:02x}{resolved[1]:02x}{resolved[2]:02x}" if resolved else expr.color
        candidate = expr if effective_color == expr.color else ExpressionIR(
            source=expr.source,
            expr_id=expr.expr_id,
            order=expr.order,
            latex=expr.latex,
            color=effective_color,
            color_latex=expr.color_latex,
            hidden=expr.hidden,
            folder_id=expr.folder_id,
            type=expr.type,
            raw=expr.raw,
        )
        for expanded in expand_list_expression(candidate, context):
            try:
                classified.append(classify_expression(expanded, context))
            except Exception as exc:
                raise ValueError(f"Unsupported expression {expanded.expr_id} {expanded.latex!r}: {exc}") from exc

    return ClassificationResult(context=context, classified=classified, definitions=registration.definitions)


def register_definitions(expressions: list[ExpressionIR], context: EvalContext) -> DefinitionRegistrationResult:
    pending = [expr for expr in expressions if expr.type == "expression" and expr.latex.strip()]
    definitions: list[ExpressionIR] = []
    definition_ids: set[str] = set()
    failures: dict[str, tuple[ExpressionIR, Exception]] = {}

    while pending:
        next_pending: list[ExpressionIR] = []
        progressed = False
        for expr in pending:
            try:
                registered = register_definition(expr, context)
            except Exception as exc:
                failures[expr.expr_id] = (expr, exc)
                next_pending.append(expr)
                continue
            failures.pop(expr.expr_id, None)
            if registered:
                definition_ids.add(expr.expr_id)
                if expr.renderable_candidate:
                    definitions.append(expr)
                progressed = True
        if not next_pending or not progressed:
            break
        pending = next_pending

    unresolved_ids = {expr.expr_id for expr in pending}
    unresolved_failures = [failure for expr_id, failure in failures.items() if expr_id in unresolved_ids]
    return DefinitionRegistrationResult(definitions=definitions, definition_ids=definition_ids, failures=unresolved_failures)


def register_definition(expr: ExpressionIR, context: EvalContext) -> bool:
    main, restrictions = split_restrictions(expr.latex)
    if restrictions:
        return False
    equals = find_top_level(main, "=")
    if equals < 0:
        return False
    lhs = main[:equals].strip()
    rhs = main[equals + 1 :].strip()
    function_match = re.match(r"^([A-Za-z\\][A-Za-z0-9_\\{}]*)\(([^()]*)\)$", lhs)
    if function_match:
        name = normalize_identifier(function_match.group(1))
        params = tuple(normalize_identifier(part) for part in split_top_level(function_match.group(2), ",") if part)
        if not params:
            return False
        context.functions[name] = FunctionDef(name=name, params=params, body=LatexExpression.parse(rhs))
        return True
    if not looks_like_definition_identifier(lhs):
        return False
    name = normalize_identifier(lhs)
    if name in {"x", "y", "z"}:
        return False

    tuple_components = parse_tuple_definition_components(rhs)
    if tuple_components is not None:
        register_component_definition(name, tuple_components, context)
        return True

    point_list = parse_point_list_definition(rhs, context)
    if point_list is not None:
        register_point_list_definition(name, point_list, context)
        return True

    if looks_like_ignored_definition(rhs):
        color = parse_color_definition(rhs, context)
        if color is not None:
            context.colors[name] = color
        return True

    try:
        value = eval_numeric_sequence(rhs, context)
    except GraphVariableDependency:
        return False
    if isinstance(value, tuple):
        context.lists[name] = value
        return True
    context.scalars[name] = value
    return True


def looks_like_definition_identifier(text: str) -> bool:
    normalized = normalize_latex_delimiters(text).strip()
    return re.fullmatch(r"[A-Za-z\\][A-Za-z0-9_\\{}]*", normalized) is not None


NumericSequence = float | tuple[float, ...]


class GraphVariableDependency(ValueError):
    pass


def eval_numeric_sequence(text: str, context: EvalContext) -> NumericSequence:
    stripped = strip_wrapping_parens(normalize_latex_delimiters(text).strip())
    stripped = stripped.replace("\\cdot", "*").replace("\\times", "*")
    if not stripped:
        raise ValueError("Empty numeric definition")

    split_at = find_top_level_numeric_operator(stripped, "+-")
    if split_at > 0:
        left = eval_numeric_sequence(stripped[:split_at], context)
        right = eval_numeric_sequence(stripped[split_at + 1 :], context)
        return apply_sequence_operator(left, right, stripped[split_at])

    split_at = find_top_level_numeric_operator(stripped, "*/")
    if split_at > 0:
        left = eval_numeric_sequence(stripped[:split_at], context)
        right = eval_numeric_sequence(stripped[split_at + 1 :], context)
        return apply_sequence_operator(left, right, stripped[split_at])

    if stripped.startswith("+"):
        return eval_numeric_sequence(stripped[1:], context)
    if stripped.startswith("-"):
        return negate_sequence(eval_numeric_sequence(stripped[1:], context))

    if looks_like_scalar_list(stripped):
        return parse_scalar_list(stripped, context)

    join_args = parse_join_call_args(stripped)
    if join_args is not None:
        values: list[float] = []
        for arg in join_args:
            value = eval_numeric_sequence(arg, context)
            if isinstance(value, tuple):
                values.extend(value)
            else:
                values.append(value)
        return tuple(values)

    parsed = LatexExpression.parse(stripped)
    if parsed.identifiers & GRAPH_VARIABLES:
        raise GraphVariableDependency(f"Definition depends on graph variables: {stripped!r}")
    list_names = parsed.identifiers & set(context.lists)
    if list_names:
        lengths = {len(context.lists[list_name]) for list_name in list_names}
        if len(lengths) != 1:
            raise ValueError(f"List definition references lists with mismatched lengths: {', '.join(sorted(list_names))}")
        count = lengths.pop()
        values = []
        for index in range(count):
            variables = {list_name: context.lists[list_name][index] for list_name in list_names}
            values.append(parsed.eval(context, variables))
        return tuple(values)
    return parsed.eval(context, {})


def find_top_level_numeric_operator(text: str, operators: str) -> int:
    depth = 0
    for index in range(len(text) - 1, -1, -1):
        char = text[index]
        if char in ")}]":
            depth += 1
        elif char in "({[":
            depth -= 1
        elif depth == 0 and char in operators:
            if char in "+-" and is_unary_numeric_operator(text, index):
                continue
            return index
    return -1


def is_unary_numeric_operator(text: str, index: int) -> bool:
    if index == 0:
        return True
    previous = text[index - 1]
    return previous in "+-*/("


def apply_sequence_operator(left: NumericSequence, right: NumericSequence, op: str) -> NumericSequence:
    if isinstance(left, tuple) or isinstance(right, tuple):
        if isinstance(left, tuple) and isinstance(right, tuple):
            if len(left) != len(right):
                raise ValueError("List operation references lists with mismatched lengths")
            left_values = left
            right_values = right
        elif isinstance(left, tuple):
            left_values = left
            right_values = tuple(float(right) for _ in left)
        else:
            right_values = right
            left_values = tuple(float(left) for _ in right)
        return tuple(apply_scalar_operator(a, b, op) for a, b in zip(left_values, right_values, strict=True))
    return apply_scalar_operator(left, right, op)


def apply_scalar_operator(left: float, right: float, op: str) -> float:
    if op == "+":
        return float(left) + float(right)
    if op == "-":
        return float(left) - float(right)
    if op == "*":
        return float(left) * float(right)
    if op == "/":
        return float(left) / float(right)
    raise ValueError(f"Unsupported numeric operator {op!r}")


def negate_sequence(value: NumericSequence) -> NumericSequence:
    if isinstance(value, tuple):
        return tuple(-item for item in value)
    return -value


def parse_join_call_args(text: str) -> list[str] | None:
    normalized = normalize_latex_delimiters(text).strip()
    prefixes = ("\\operatorname{join}", "join")
    prefix = next((candidate for candidate in prefixes if normalized.startswith(candidate)), None)
    if prefix is None:
        return None
    open_at = len(prefix)
    while open_at < len(normalized) and normalized[open_at].isspace():
        open_at += 1
    if open_at >= len(normalized) or normalized[open_at] != "(":
        return None
    close_at = matching_paren(normalized, open_at)
    if normalized[close_at + 1 :].strip():
        return None
    return split_top_level(normalized[open_at + 1 : close_at], ",")


def parse_tuple_definition_components(text: str) -> list[str] | None:
    stripped = strip_extra_trailing_closing_parens(normalize_latex_delimiters(text).strip())
    while stripped.startswith("("):
        try:
            close_at = matching_paren(stripped, 0)
        except ValueError:
            return None
        if close_at != len(stripped) - 1:
            return None
        inner = stripped[1:close_at].strip()
        parts = split_top_level(inner, ",")
        if len(parts) in {2, 3}:
            return parts
        stripped = inner
    return None


def register_component_definition(name: str, components: list[str], context: EvalContext) -> None:
    values = [eval_numeric_sequence(component, context) for component in components]
    lengths = {len(value) for value in values if isinstance(value, tuple)}
    if len(lengths) > 1:
        raise ValueError(f"Point definition {name} references lists with mismatched lengths")
    axes = "xyz"[: len(values)]
    if not lengths:
        for axis, value in zip(axes, values, strict=True):
            context.scalars[f"{name}_{axis}"] = float(value)
        if len(values) == 3:
            context.vectors[name] = tuple(float(value) for value in values)  # type: ignore[arg-type]
        return
    count = lengths.pop()
    for axis, value in zip(axes, values, strict=True):
        if isinstance(value, tuple):
            context.lists[f"{name}_{axis}"] = value
        else:
            context.lists[f"{name}_{axis}"] = tuple(float(value) for _ in range(count))


def parse_point_list_definition(text: str, context: EvalContext) -> list[tuple[float, ...]] | None:
    stripped = normalize_latex_delimiters(text).strip()
    bracketed = stripped.startswith("[") and stripped.endswith("]")
    if bracketed:
        body = stripped[1:-1]
    else:
        body = stripped
        if len(split_top_level(body, ",")) < 2:
            return None
    if not body:
        return None
    points: list[tuple[float, ...]] = []
    for part in split_top_level(body, ","):
        if not part:
            continue
        components = parse_tuple_definition_components(part)
        if components is None:
            return None
        values = [eval_numeric_sequence(component, context) for component in components]
        if any(isinstance(value, tuple) for value in values):
            raise ValueError(f"Point list entry references nested lists: {part!r}")
        points.append(tuple(float(value) for value in values))
    return points


def register_point_list_definition(name: str, points: list[tuple[float, ...]], context: EvalContext) -> None:
    if not points:
        return
    widths = {len(point) for point in points}
    if len(widths) != 1:
        raise ValueError(f"Point list {name} has inconsistent tuple sizes")
    context.point_lists[name] = tuple(points)
    axes = "xyz"[: widths.pop()]
    for axis_index, axis in enumerate(axes):
        context.lists[f"{name}_{axis}"] = tuple(point[axis_index] for point in points)


def classify_expression(expr: ExpressionIR, context: EvalContext) -> ClassifiedExpression:
    main, restriction_texts = split_restrictions(expr.latex)
    predicates: list[ComparisonPredicate] = []
    for restriction in restriction_texts:
        predicates.extend(parse_predicates(restriction))

    if looks_like_segment(main):
        vector = parse_segment_curve(main, context)
        return ClassifiedExpression(ir=expr, kind="parametric_curve", predicates=predicates, vector=vector, t_bounds=(0.0, 1.0))

    if looks_like_triangle(main):
        triangle_mesh = parse_triangle_mesh(main, context)
        return ClassifiedExpression(ir=expr, kind="triangle_mesh", predicates=predicates, triangle_mesh=triangle_mesh)

    if looks_like_sphere(main):
        expression = parse_sphere_surface(main, context)
        return ClassifiedExpression(ir=expr, kind="implicit_surface", predicates=predicates, expression=expression)

    point_list = parse_renderable_vector_list_expression(main, context)
    if point_list is not None:
        return ClassifiedExpression(
            ir=expr,
            kind="point_list_curve",
            predicates=predicates,
            point_list=point_list,
        )

    vector = parse_renderable_vector_expression(main, context)
    if vector is not None:
        vector_identifiers = set().union(*(component.identifiers for component in vector.components))
        if {"u", "v"} <= vector_identifiers:
            return ClassifiedExpression(
                ir=expr,
                kind="parametric_surface",
                predicates=predicates,
                vector=vector,
                u_bounds=find_parameter_bounds(
                    predicates,
                    context,
                    "u",
                    raw_domain=expr.raw.get("parametricDomain3Du"),
                ),
                v_bounds=find_parameter_bounds(
                    predicates,
                    context,
                    "v",
                    raw_domain=expr.raw.get("parametricDomain3Dv"),
                ),
            )
        parameter = "t"
        for candidate_parameter in ("t", "u", "v"):
            if candidate_parameter in vector_identifiers:
                parameter = candidate_parameter
                break
        return ClassifiedExpression(
            ir=expr,
            kind="parametric_curve",
            predicates=predicates,
            vector=vector,
            parameter=parameter,
            t_bounds=find_parameter_bounds(
                predicates,
                context,
                parameter,
                raw_domain=expr.raw.get("parametricDomain"),
            ),
        )

    if has_top_level_comparison(main):
        inequality = parse_predicate(main)
        return ClassifiedExpression(ir=expr, kind="inequality_region", predicates=[inequality, *predicates], inequality=inequality)

    equals = find_top_level(main, "=")
    if equals >= 0:
        lhs = main[:equals].strip()
        rhs = main[equals + 1 :].strip()
        lhs_id = normalize_identifier(lhs)
        if lhs_id in {"x", "y", "z"}:
            return ClassifiedExpression(
                ir=expr,
                kind="explicit_surface",
                predicates=predicates,
                axis=lhs_id,
                expression=LatexExpression.parse(rhs),
            )
        rhs_id = normalize_identifier(rhs) if re.match(r"^[A-Za-z\\][A-Za-z0-9_\\{}]*$", rhs) else None
        if rhs_id in {"x", "y", "z"}:
            return ClassifiedExpression(
                ir=expr,
                kind="explicit_surface",
                predicates=predicates,
                axis=rhs_id,
                expression=LatexExpression.parse(lhs),
            )
        residual = LatexExpression.parse(f"({lhs})-({rhs})")
        residual_axes = residual.identifiers & {"x", "y", "z"}
        if 2 <= len(residual_axes) <= 3:
            return ClassifiedExpression(
                ir=expr,
                kind="implicit_surface",
                predicates=predicates,
                expression=residual,
            )
        predicate_axes = predicate_identifiers(predicates)
        if len(residual_axes) == 1 and 2 <= len(residual_axes | predicate_axes) <= 3:
            return ClassifiedExpression(
                ir=expr,
                kind="implicit_surface",
                predicates=predicates,
                expression=residual,
            )
    raise ValueError("not a supported renderable geometry form")


def predicate_identifiers(predicates: list[ComparisonPredicate]) -> set[str]:
    identifiers: set[str] = set()
    for predicate in predicates:
        for term in predicate.terms:
            identifiers.update(term.identifiers & {"x", "y", "z"})
    return identifiers


def looks_like_ignored_definition(rhs: str) -> bool:
    normalized = normalize_latex_delimiters(rhs)
    return color_function_call(normalized) is not None


COLOR_FUNCTION_NAMES = ("rgb", "hsv", "okhsv")


def parse_rgb_definition(rhs: str, context: EvalContext) -> tuple[int, int, int] | None:
    return parse_color_definition(rhs, context, allowed_names={"rgb"})


def parse_color_definition(
    rhs: str,
    context: EvalContext,
    *,
    allowed_names: set[str] | None = None,
) -> tuple[int, int, int] | None:
    call = color_function_call(rhs)
    if call is None:
        return None
    name, args = call
    if allowed_names is not None and name not in allowed_names:
        return None
    if len(args) != 3:
        return None
    values: list[float] = []
    for arg in args:
        if not arg:
            return None
        try:
            values.append(LatexExpression.parse(arg).eval(context, {}))
        except Exception:
            return None
    if name == "rgb":
        return (clamp_rgb8(values[0]), clamp_rgb8(values[1]), clamp_rgb8(values[2]))
    hue, saturation, value = values
    if name == "hsv":
        return hsv_to_rgb8(hue, saturation, value)
    if name == "okhsv":
        return okhsv_to_rgb8(hue, saturation, value)
    return None


def color_function_call(text: str) -> tuple[str, list[str]] | None:
    normalized = normalize_latex_delimiters(text).strip()
    for name in COLOR_FUNCTION_NAMES:
        for prefix in (f"\\operatorname{{{name}}}", name):
            if not normalized.startswith(prefix):
                continue
            remainder = normalized[len(prefix):].lstrip()
            if not remainder.startswith("(") or not remainder.endswith(")"):
                return None
            return name, split_top_level(remainder[1:-1], ",")
    return None


def clamp_rgb8(value: float) -> int:
    return max(0, min(255, int(round(value))))


def clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def rgb_float_to_rgb8(red: float, green: float, blue: float) -> tuple[int, int, int]:
    return (
        clamp_rgb8(clamp_unit(red) * 255.0),
        clamp_rgb8(clamp_unit(green) * 255.0),
        clamp_rgb8(clamp_unit(blue) * 255.0),
    )


def hsv_to_rgb8(hue: float, saturation: float, value: float) -> tuple[int, int, int]:
    red, green, blue = colorsys.hsv_to_rgb(
        (float(hue) % 360.0) / 360.0,
        clamp_unit(saturation),
        clamp_unit(value),
    )
    return rgb_float_to_rgb8(red, green, blue)


def okhsv_to_rgb8(hue: float, saturation: float, value: float) -> tuple[int, int, int]:
    red, green, blue = okhsv_to_srgb(
        (float(hue) % 360.0) / 360.0,
        clamp_unit(saturation),
        clamp_unit(value),
    )
    return rgb_float_to_rgb8(red, green, blue)


def okhsv_to_srgb(hue: float, saturation: float, value: float) -> tuple[float, float, float]:
    # Python port of Bjorn Ottosson's MIT-licensed OKHSV reference algorithm,
    # Copyright (c) 2021 Bjorn Ottosson.
    if value <= 0.0:
        return (0.0, 0.0, 0.0)
    a_ = math.cos(2.0 * math.pi * hue)
    b_ = math.sin(2.0 * math.pi * hue)

    cusp_l, cusp_c = ok_find_cusp(a_, b_)
    s_max = cusp_c / cusp_l
    t_max = cusp_c / (1.0 - cusp_l)
    s_0 = 0.5
    k = 1.0 - s_0 / s_max
    denominator = s_0 + t_max - t_max * k * saturation
    if denominator == 0.0:
        return (0.0, 0.0, 0.0)

    l_v = 1.0 - saturation * s_0 / denominator
    c_v = saturation * t_max * s_0 / denominator
    lightness = value * l_v
    chroma = value * c_v
    if lightness <= 0.0:
        return (0.0, 0.0, 0.0)

    l_vt = ok_toe_inv(l_v)
    c_vt = c_v * l_vt / l_v
    lightness_new = ok_toe_inv(lightness)
    chroma = chroma * lightness_new / lightness
    lightness = lightness_new

    scale_rgb = ok_oklab_to_linear_srgb(l_vt, a_ * c_vt, b_ * c_vt)
    scale_max = max(scale_rgb[0], scale_rgb[1], scale_rgb[2], 0.0)
    if scale_max <= 0.0:
        return (0.0, 0.0, 0.0)
    scale_l = (1.0 / scale_max) ** (1.0 / 3.0)

    lightness *= scale_l
    chroma *= scale_l
    linear = ok_oklab_to_linear_srgb(lightness, chroma * a_, chroma * b_)
    return (
        ok_srgb_transfer(linear[0]),
        ok_srgb_transfer(linear[1]),
        ok_srgb_transfer(linear[2]),
    )


def ok_toe_inv(value: float) -> float:
    k_1 = 0.206
    k_2 = 0.03
    k_3 = (1.0 + k_1) / (1.0 + k_2)
    return (value * value + k_1 * value) / (k_3 * (value + k_2))


def ok_oklab_to_linear_srgb(lightness: float, a: float, b: float) -> tuple[float, float, float]:
    l_ = lightness + 0.3963377774 * a + 0.2158037573 * b
    m_ = lightness - 0.1055613458 * a - 0.0638541728 * b
    s_ = lightness - 0.0894841775 * a - 1.2914855480 * b

    l = l_ * l_ * l_
    m = m_ * m_ * m_
    s = s_ * s_ * s_

    return (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )


def ok_srgb_transfer(value: float) -> float:
    if value <= 0.0031308:
        return 12.92 * value
    return 1.055 * (value ** (1.0 / 2.4)) - 0.055


def ok_compute_max_saturation(a: float, b: float) -> float:
    if -1.88170328 * a - 0.80936493 * b > 1.0:
        k0, k1, k2, k3, k4 = 1.19086277, 1.76576728, 0.59662641, 0.75515197, 0.56771245
        wl, wm, ws = 4.0767416621, -3.3077115913, 0.2309699292
    elif 1.81444104 * a - 1.19445276 * b > 1.0:
        k0, k1, k2, k3, k4 = 0.73956515, -0.45954404, 0.08285427, 0.12541070, 0.14503204
        wl, wm, ws = -1.2684380046, 2.6097574011, -0.3413193965
    else:
        k0, k1, k2, k3, k4 = 1.35733652, -0.00915799, -1.15130210, -0.50559606, 0.00692167
        wl, wm, ws = -0.0041960863, -0.7034186147, 1.7076147010

    sat = k0 + k1 * a + k2 * b + k3 * a * a + k4 * a * b
    k_l = 0.3963377774 * a + 0.2158037573 * b
    k_m = -0.1055613458 * a - 0.0638541728 * b
    k_s = -0.0894841775 * a - 1.2914855480 * b

    l_ = 1.0 + sat * k_l
    m_ = 1.0 + sat * k_m
    s_ = 1.0 + sat * k_s
    l = l_ * l_ * l_
    m = m_ * m_ * m_
    s = s_ * s_ * s_
    l_ds = 3.0 * k_l * l_ * l_
    m_ds = 3.0 * k_m * m_ * m_
    s_ds = 3.0 * k_s * s_ * s_
    l_ds2 = 6.0 * k_l * k_l * l_
    m_ds2 = 6.0 * k_m * k_m * m_
    s_ds2 = 6.0 * k_s * k_s * s_
    f = wl * l + wm * m + ws * s
    f1 = wl * l_ds + wm * m_ds + ws * s_ds
    f2 = wl * l_ds2 + wm * m_ds2 + ws * s_ds2
    return sat - f * f1 / (f1 * f1 - 0.5 * f * f2)


def ok_find_cusp(a: float, b: float) -> tuple[float, float]:
    saturation = ok_compute_max_saturation(a, b)
    rgb_at_max = ok_oklab_to_linear_srgb(1.0, saturation * a, saturation * b)
    max_component = max(rgb_at_max)
    if max_component <= 0.0:
        return (1.0, 0.0)
    cusp_l = (1.0 / max_component) ** (1.0 / 3.0)
    return cusp_l, cusp_l * saturation


def resolve_color_latex(color_latex: str | None, context: EvalContext) -> tuple[int, int, int] | None:
    if not color_latex:
        return None
    text = color_latex.strip()
    if not text:
        return None
    normalized = normalize_latex_delimiters(text).strip()
    color = parse_color_definition(normalized, context)
    if color is not None:
        return color
    try:
        identifier = normalize_identifier(normalized)
    except Exception:
        identifier = None
    if identifier and identifier in context.colors:
        return context.colors[identifier]
    try:
        expression = LatexExpression.parse(text)
    except Exception:
        return None
    if expression.identifiers - set(context.colors.keys()) - {"x", "y", "z", "t"}:
        return None
    return None


def looks_like_scalar_list(text: str) -> bool:
    stripped = normalize_latex_delimiters(text)
    return stripped.startswith("[") and stripped.endswith("]")


def parse_scalar_list(text: str, context: EvalContext) -> tuple[float, ...]:
    stripped = normalize_latex_delimiters(text)
    if not (stripped.startswith("[") and stripped.endswith("]")):
        raise ValueError(f"Expected scalar list, got {text!r}")
    return tuple(parse_scalar_list_body(stripped[1:-1], context))


def parse_scalar_list_body(body: str, context: EvalContext) -> list[float]:
    parts = [part for part in split_top_level(body, ",") if part]
    values: list[float] = []
    index = 0
    while index < len(parts):
        part = parts[index]
        if part == "...":
            if not values or index + 1 >= len(parts):
                raise ValueError(f"Malformed scalar list range: {body!r}")
            values.extend(scalar_range(values[-1], None, parse_scalar_value(parts[index + 1], context))[1:])
            index += 2
            continue
        if "..." in part:
            left, right = part.split("...", 1)
            if not left or not right:
                raise ValueError(f"Malformed scalar list range: {body!r}")
            end = parse_scalar_value(right, context)
            if values:
                second = parse_scalar_value(left, context)
                values.extend(scalar_range(values[-1], second, end)[1:])
            else:
                start = parse_scalar_value(left, context)
                values.extend(scalar_range(start, None, end))
            index += 1
            continue
        if index + 1 < len(parts) and parts[index + 1] == "...":
            start = parse_scalar_value(part, context)
            if index + 2 >= len(parts):
                raise ValueError(f"Malformed scalar list range: {body!r}")
            end = parse_scalar_value(parts[index + 2], context)
            if values:
                values.extend(scalar_range(values[-1], start, end)[1:])
            else:
                values.extend(scalar_range(start, None, end))
            index += 3
            continue
        if index + 2 < len(parts) and parts[index + 2] == "...":
            start = parse_scalar_value(part, context)
            second = parse_scalar_value(parts[index + 1], context)
            if index + 3 >= len(parts):
                raise ValueError(f"Malformed scalar list range: {body!r}")
            end = parse_scalar_value(parts[index + 3], context)
            if values:
                values.extend(scalar_range(values[-1], start, end)[1:])
            else:
                values.extend(scalar_range(start, second, end))
            index += 4
            continue
        values.append(parse_scalar_value(part, context))
        index += 1
    return values


def parse_scalar_value(part: str, context: EvalContext) -> float:
    parsed = LatexExpression.parse(part)
    if parsed.identifiers & {"x", "y", "z", "t", "u", "v"}:
        raise ValueError(f"List value depends on graph variables: {part!r}")
    return parsed.eval(context, {})


def scalar_range(start: float, second: float | None, end: float) -> list[float]:
    step = (second - start) if second is not None else (1.0 if end >= start else -1.0)
    if abs(step) < 1e-12:
        raise ValueError("Scalar list range step cannot be zero")
    if (end - start) * step < -1e-12:
        raise ValueError(f"Scalar list range step {step!r} does not move from {start!r} toward {end!r}")
    values: list[float] = []
    current = start
    tolerance = max(1e-9, abs(step) * 1e-9)
    limit = 10000
    while (step > 0 and current <= end + tolerance) or (step < 0 and current >= end - tolerance):
        values.append(round(current, 12))
        if len(values) > limit:
            raise ValueError(f"Scalar list range has more than {limit} values")
        current += step
    return values


def parse_literal_scalar_list(text: str, context: EvalContext) -> tuple[float, ...] | None:
    stripped = normalize_latex_delimiters(text)
    if not (stripped.startswith("[") and stripped.endswith("]")):
        return None
    try:
        return tuple(parse_scalar_list_body(stripped[1:-1], context))
    except Exception:
        return None


def replace_list_index_references(text: str, context: EvalContext) -> str:
    resolved = normalize_latex_delimiters(text)
    changed = False
    for name in sorted(context.point_lists, key=len, reverse=True):
        pattern = latex_identifier_index_pattern(name)

        def replace_point(match: re.Match[str]) -> str:
            nonlocal changed
            index_text = match.group(1)
            try:
                value = LatexExpression.parse(index_text).eval(context, {})
            except Exception:
                return match.group(0)
            index = int(round(value))
            if abs(value - index) > 1e-9:
                return match.group(0)
            zero_based = index - 1
            values = context.point_lists[name]
            if zero_based < 0 or zero_based >= len(values):
                raise ValueError(f"Point list index {index} out of range for {name}")
            changed = True
            return "(" + ",".join(repr(component) for component in values[zero_based]) + ")"

        resolved = re.sub(pattern, replace_point, resolved)
    for name in sorted(context.lists, key=len, reverse=True):
        pattern = latex_identifier_index_pattern(name)

        def replace(match: re.Match[str]) -> str:
            nonlocal changed
            index_text = match.group(1)
            try:
                value = LatexExpression.parse(index_text).eval(context, {})
            except Exception:
                return match.group(0)
            index = int(round(value))
            if abs(value - index) > 1e-9:
                return match.group(0)
            zero_based = index - 1
            values = context.lists[name]
            if zero_based < 0 or zero_based >= len(values):
                raise ValueError(f"List index {index} out of range for {name}")
            changed = True
            return repr(values[zero_based])

        resolved = re.sub(pattern, replace, resolved)
    return resolved if changed else text


def literal_scalar_list_spans(text: str, context: EvalContext) -> list[tuple[int, int, tuple[float, ...]]]:
    spans: list[tuple[int, int, tuple[float, ...]]] = []
    index = 0
    while index < len(text):
        if text[index] != "[":
            index += 1
            continue
        if is_latex_index_bracket(text, index):
            index += 1
            continue
        end = find_matching_square_bracket(text, index)
        if end < 0:
            index += 1
            continue
        values = parse_literal_scalar_list(text[index : end + 1], context)
        if values is not None:
            spans.append((index, end + 1, values))
            index = end + 1
            continue
        index += 1
    return spans


def is_latex_index_bracket(text: str, bracket_index: int) -> bool:
    index = bracket_index - 1
    while index >= 0 and text[index].isspace():
        index -= 1
    if index < 0:
        return False
    command_start = index
    while command_start >= 0 and text[command_start].isalpha():
        command_start -= 1
    if command_start >= 0 and text[command_start] == "\\":
        command_name = text[command_start + 1 : index + 1]
        if command_name != "left":
            return False
        before_command = command_start - 1
        while before_command >= 0 and text[before_command].isspace():
            before_command -= 1
        if before_command < 0:
            return False
        previous = text[before_command]
        if is_latex_command_word_at(text, before_command):
            return False
        return previous.isalnum() or previous in "_}"
    previous = text[index]
    if is_latex_command_word_at(text, index):
        return False
    return previous.isalnum() or previous in "_}"


def is_latex_command_word_at(text: str, index: int) -> bool:
    if index < 0 or not text[index].isalpha():
        return False
    word_start = index
    while word_start >= 0 and text[word_start].isalpha():
        word_start -= 1
    return word_start >= 0 and text[word_start] == "\\"


def find_matching_square_bracket(text: str, start: int) -> int:
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return index
    return -1


def replace_literal_scalar_lists(text: str, spans: list[tuple[int, int, tuple[float, ...]]], list_index: int) -> str:
    if not spans:
        return text
    output: list[str] = []
    cursor = 0
    for start, end, values in spans:
        output.append(text[cursor:start])
        output.append(repr(values[list_index]))
        cursor = end
    output.append(text[cursor:])
    return "".join(output)


def join_latex_with_restrictions(main: str, restrictions: list[str]) -> str:
    return main + "".join(r"\left\{" + restriction + r"\right\}" for restriction in restrictions)


def select_broadcast_restriction(restriction: str, index: int, count: int) -> str:
    parts = restriction_alternative_parts(restriction)
    if parts is not None and len(parts) == count:
        return parts[index]
    return restriction


def restriction_alternative_parts(restriction: str) -> list[str] | None:
    parts = [part for part in split_top_level(restriction, ",") if part]
    if len(parts) < 2 or not all(looks_like_restriction(part) for part in parts):
        return None
    variables: set[str] = set()
    for part in parts:
        try:
            predicates = parse_predicates(part)
        except Exception:
            return None
        part_variables: set[str] = set()
        for predicate in predicates:
            part_variables.update(predicate.variable_bounds())
        if len(part_variables) != 1:
            return None
        variables.update(part_variables)
    if len(variables) != 1:
        return None
    return parts


def restriction_union_alternative_parts(restriction: str, context: EvalContext) -> list[str] | None:
    parts = restriction_alternative_parts(restriction)
    if parts is None:
        return None
    ranges: list[tuple[float, float]] = []
    for part in parts:
        try:
            predicates = parse_predicates(part)
        except Exception:
            return None
        if len(predicates) != 1:
            return None
        bounds = predicates[0].variable_bounds()
        if len(bounds) != 1:
            return None
        lower, upper = next(iter(bounds.values()))
        if lower is None or upper is None:
            return None
        try:
            low_value = lower.eval(context, {})
            high_value = upper.eval(context, {})
        except Exception:
            return None
        if not (isfinite(low_value) and isfinite(high_value)) or low_value > high_value:
            return None
        ranges.append((low_value, high_value))
    sorted_ranges = sorted(ranges)
    for previous, current in zip(sorted_ranges, sorted_ranges[1:]):
        if previous[1] > current[0] - 1e-9:
            return None
    return parts


def expand_restriction_union_alternatives(expr: ExpressionIR, context: EvalContext) -> list[ExpressionIR]:
    main, restriction_texts = split_restrictions(expr.latex)
    options: list[list[str]] = []
    has_alternative = False
    for restriction in restriction_texts:
        alternatives = restriction_union_alternative_parts(restriction, context)
        if alternatives is None:
            options.append([restriction])
            continue
        has_alternative = True
        options.append(alternatives)
    if not has_alternative:
        return [expr]

    expanded: list[ExpressionIR] = []
    for index, selected_restrictions in enumerate(product(*options)):
        raw = dict(expr.raw)
        raw["expandedFromRestrictionAlternative"] = expr.expr_id
        raw["restrictionAlternativeIndex"] = index
        expanded.append(
            ExpressionIR(
                source=expr.source,
                expr_id=f"{expr.expr_id}_alt{index}",
                order=expr.order,
                latex=join_latex_with_restrictions(main, list(selected_restrictions)),
                color=expr.color,
                color_latex=expr.color_latex,
                hidden=expr.hidden,
                folder_id=expr.folder_id,
                type=expr.type,
                raw=raw,
            )
        )
    return expanded


def expand_literal_list_expression(expr: ExpressionIR, context: EvalContext) -> list[ExpressionIR]:
    main, restriction_texts = split_restrictions(expr.latex)
    main_spans = literal_scalar_list_spans(main, context)
    restriction_spans = [literal_scalar_list_spans(restriction, context) for restriction in restriction_texts]
    lengths = {len(values) for _, _, values in main_spans}
    for spans in restriction_spans:
        lengths.update(len(values) for _, _, values in spans)
    if not lengths:
        return expand_restriction_union_alternatives(expr, context)
    if len(lengths) != 1:
        raise ValueError("Literal scalar lists in expression have mismatched lengths")
    count = lengths.pop()
    expanded: list[ExpressionIR] = []
    for index in range(count):
        expanded_main = replace_literal_scalar_lists(main, main_spans, index)
        expanded_restrictions = [
            select_broadcast_restriction(replace_literal_scalar_lists(restriction, spans, index), index, count)
            for restriction, spans in zip(restriction_texts, restriction_spans, strict=True)
        ]
        raw = dict(expr.raw)
        raw["expandedFromLiteralListExpression"] = expr.expr_id
        raw["listIndex"] = index
        expanded.extend(
            expand_restriction_union_alternatives(
                ExpressionIR(
                    source=expr.source,
                    expr_id=f"{expr.expr_id}_{index}",
                    order=expr.order,
                    latex=join_latex_with_restrictions(expanded_main, expanded_restrictions),
                    color=expr.color,
                    color_latex=expr.color_latex,
                    hidden=expr.hidden,
                    folder_id=expr.folder_id,
                    type=expr.type,
                    raw=raw,
                ),
                context,
            )
        )
    return expanded


@dataclass(frozen=True)
class RandomCallSpan:
    start: int
    end: int
    values: tuple[float, ...]


def expand_list_expression(expr: ExpressionIR, context: EvalContext) -> list[ExpressionIR]:
    resolved_latex = replace_list_index_references(expr.latex, context)
    if resolved_latex != expr.latex:
        raw = dict(expr.raw)
        raw["resolvedListIndexReferences"] = True
        expr = ExpressionIR(
            source=expr.source,
            expr_id=expr.expr_id,
            order=expr.order,
            latex=resolved_latex,
            color=expr.color,
            color_latex=expr.color_latex,
            hidden=expr.hidden,
            folder_id=expr.folder_id,
            type=expr.type,
            raw=raw,
        )
    main, restriction_texts = split_restrictions(expr.latex)
    random_main_spans, next_random_occurrence = random_call_spans(main, context, expr.expr_id)
    random_restriction_spans: list[list[RandomCallSpan]] = []
    for restriction in restriction_texts:
        spans, next_random_occurrence = random_call_spans(restriction, context, expr.expr_id, next_random_occurrence)
        random_restriction_spans.append(spans)
    has_random_calls = bool(random_main_spans) or any(random_restriction_spans)
    names = [name for name in context.lists if latex_identifier_present(expr.latex, name)]
    if not names and not has_random_calls:
        return expand_literal_list_expression(expr, context)

    lengths = {len(context.lists[name]) for name in names}
    lengths.update(len(span.values) for span in random_main_spans)
    for spans in random_restriction_spans:
        lengths.update(len(span.values) for span in spans)
    if len(lengths) != 1:
        sources = [*names]
        if has_random_calls:
            sources.append("random")
        raise ValueError(f"Expression references lists with mismatched lengths: {', '.join(sources)}")
    count = lengths.pop()
    expanded: list[ExpressionIR] = []
    for index in range(count):
        latex = replace_random_calls(main, random_main_spans, index)
        for name in names:
            latex = replace_latex_identifier(latex, name, repr(context.lists[name][index]))
        latex = replace_list_index_references(latex, context)
        expanded_restrictions: list[str] = []
        for restriction, random_spans in zip(restriction_texts, random_restriction_spans, strict=True):
            replaced_restriction = replace_random_calls(restriction, random_spans, index)
            for name in names:
                replaced_restriction = replace_latex_identifier(replaced_restriction, name, repr(context.lists[name][index]))
            replaced_restriction = replace_list_index_references(replaced_restriction, context)
            expanded_restrictions.append(select_broadcast_restriction(replaced_restriction, index, count))
        raw = dict(expr.raw)
        if names:
            raw["expandedFromListExpression"] = expr.expr_id
        if has_random_calls:
            raw["expandedFromRandomExpression"] = expr.expr_id
            raw["randomListLimit"] = context.random_list_limit
        raw["listIndex"] = index
        expanded.extend(
            expand_literal_list_expression(
                ExpressionIR(
                    source=expr.source,
                    expr_id=f"{expr.expr_id}_{index}",
                    order=expr.order,
                    latex=join_latex_with_restrictions(latex, expanded_restrictions),
                    color=expr.color,
                    color_latex=expr.color_latex,
                    hidden=expr.hidden,
                    folder_id=expr.folder_id,
                    type=expr.type,
                    raw=raw,
                ),
                context,
            )
        )
    return expanded


def random_call_spans(
    text: str,
    context: EvalContext,
    expr_id: str,
    occurrence_start: int = 0,
) -> tuple[list[RandomCallSpan], int]:
    spans: list[RandomCallSpan] = []
    occurrence = occurrence_start
    index = 0
    while index < len(text):
        match = random_call_prefix_at(text, index)
        if match is None:
            index += 1
            continue
        prefix_start, prefix_end = match
        open_at = prefix_end
        while open_at < len(text) and text[open_at].isspace():
            open_at += 1
        if open_at >= len(text) or text[open_at] != "(":
            index += 1
            continue
        close_at = matching_paren(text, open_at)
        count = random_call_count(text[open_at + 1 : close_at], context)
        values = deterministic_random_values(context, expr_id, occurrence, count)
        spans.append(RandomCallSpan(prefix_start, close_at + 1, values))
        occurrence += 1
        index = close_at + 1
    return spans, occurrence


def random_call_prefix_at(text: str, index: int) -> tuple[int, int] | None:
    prefixes = (r"\operatorname{random}", "random")
    for prefix in prefixes:
        if not text.startswith(prefix, index):
            continue
        before = text[index - 1] if index > 0 else ""
        after = text[index + len(prefix)] if index + len(prefix) < len(text) else ""
        if prefix == "random" and (before.isalnum() or before in "_\\"):
            continue
        if after and (after.isalnum() or after == "_"):
            continue
        return index, index + len(prefix)
    return None


def random_call_count(arg_text: str, context: EvalContext) -> int:
    value = LatexExpression.parse(arg_text).eval(context, {})
    count = int(round(value))
    if abs(value - count) > 1e-9 or count <= 0:
        raise ValueError(f"random() expects a positive integer count, got {arg_text!r}")
    return count


def deterministic_random_values(context: EvalContext, expr_id: str, occurrence: int, count: int) -> tuple[float, ...]:
    capped_count = min(count, max(1, context.random_list_limit))
    seed = context.random_seed or "desmos2usd"
    material = f"{seed}:{expr_id}:{occurrence}:{count}".encode("utf-8")
    seed_int = int.from_bytes(hashlib.blake2b(material, digest_size=16).digest(), "big")
    rng = py_random.Random(seed_int)
    return tuple(rng.random() for _ in range(capped_count))


def replace_random_calls(text: str, spans: list[RandomCallSpan], list_index: int) -> str:
    if not spans:
        return text
    output: list[str] = []
    cursor = 0
    for span in spans:
        output.append(text[cursor : span.start])
        output.append(repr(span.values[list_index]))
        cursor = span.end
    output.append(text[cursor:])
    return "".join(output)


def latex_identifier_present(text: str, identifier: str) -> bool:
    if re.search(latex_identifier_pattern(identifier), text) is not None:
        return True
    if re.match(r"^[a-z]$", identifier):
        return (
            re.search(rf"(?<![A-Za-z0-9_\\{{]){re.escape(identifier)}(?=[A-Za-z\\])", text) is not None
            or re.search(rf"(?<=[0-9.)\]}}]){re.escape(identifier)}(?![A-Za-z0-9_\[])", text) is not None
        )
    return False


def replace_latex_identifier(text: str, identifier: str, replacement: str) -> str:
    replaced = re.sub(latex_identifier_pattern(identifier), replacement, text)
    if re.match(r"^[a-z]$", identifier):
        # Desmos commonly writes products such as `nh` without `*`.  The normal
        # identifier boundary intentionally avoids replacing inside longer names,
        # so add the narrow single-letter implicit-multiplication case here.
        replaced = re.sub(rf"(?<![A-Za-z0-9_\\{{]){re.escape(identifier)}(?=[A-Za-z\\])", replacement, replaced)
        replaced = re.sub(rf"(?<=[0-9.)\]}}]){re.escape(identifier)}(?![A-Za-z0-9_\[])", f"*{replacement}", replaced)
    return replaced


def latex_identifier_raw_pattern(identifier: str) -> str:
    property_match = re.match(r"^(.+)_([xyz])$", identifier)
    if property_match:
        base = property_match.group(1)
        component = property_match.group(2)
        base_raw = latex_identifier_raw_pattern(base)
        normal_raw = latex_identifier_raw_pattern_no_property(identifier)
        return rf"(?:{normal_raw}|{base_raw}\s*\.\s*{component})"
    return latex_identifier_raw_pattern_no_property(identifier)


def latex_identifier_raw_pattern_no_property(identifier: str) -> str:
    if re.match(r"^[A-Za-z]_[A-Za-z0-9]+$", identifier):
        base, sub = identifier.split("_", 1)
        return rf"{re.escape(base)}(?:_\{{{re.escape(sub)}\}}|_{re.escape(sub)})"
    return re.escape(identifier)


def latex_identifier_pattern(identifier: str) -> str:
    raw = latex_identifier_raw_pattern(identifier)
    return rf"(?:(?<![A-Za-z0-9_\\])|(?<=\\le)|(?<=\\ge)|(?<=\\lt)|(?<=\\gt)){raw}(?![A-Za-z0-9_\[])"


def latex_identifier_index_pattern(identifier: str) -> str:
    raw = latex_identifier_raw_pattern(identifier)
    return rf"(?<![A-Za-z0-9_\\]){raw}\[([^\[\]]+)\]"


def has_top_level_comparison(text: str) -> bool:
    normalized = text.replace("\\le", "<=").replace("\\ge", ">=").replace("≤", "<=").replace("≥", ">=")
    return any(find_top_level(normalized, op) >= 0 for op in ["<=", ">=", "<", ">"])


def looks_like_vector(text: str) -> bool:
    stripped = strip_extra_trailing_closing_parens(normalize_latex_delimiters(text))
    while stripped.startswith("("):
        try:
            close_at = matching_paren(stripped, 0)
        except ValueError:
            return False
        inner = stripped[1:close_at].strip()
        if len(split_top_level(inner, ",")) == 3:
            return True
        if close_at != len(stripped) - 1:
            return False
        stripped = inner
    return False


def parse_renderable_vector_expression(text: str, context: EvalContext) -> VectorExpression | None:
    if not looks_like_vector(text) and not references_known_vector(text, context):
        return None
    try:
        return parse_vector(text, context)
    except Exception:
        if looks_like_vector(text):
            raise
        return None


def parse_renderable_vector_list_expression(text: str, context: EvalContext) -> tuple[VectorExpression, ...] | None:
    if not looks_like_vector_list(text):
        return None
    vectors = tuple(parse_vector_list(text, context))
    if len(vectors) < 2:
        raise ValueError("Vector list renderable requires at least two points")
    identifiers = {
        identifier
        for vector in vectors
        for component in vector.components
        for identifier in component.identifiers
    }
    if identifiers & GRAPH_VARIABLES:
        raise ValueError("Vector list renderable entries must be static 3D points")
    return vectors


def references_known_vector(text: str, context: EvalContext) -> bool:
    normalized = normalize_latex_delimiters(text)
    return any(latex_identifier_present(normalized, name) for name in context.vectors)


def matching_paren(text: str, start: int) -> int:
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError(f"Unmatched parenthesis in {text!r}")


def parse_vector(text: str, context: EvalContext) -> VectorExpression:
    raw = strip_extra_trailing_closing_parens(normalize_latex_delimiters(text))
    components = parse_vector_components(raw, context)
    return VectorExpression(raw=raw, components=tuple(LatexExpression.parse(component) for component in components))  # type: ignore[arg-type]


def parse_vector_components(text: str, context: EvalContext) -> list[str]:
    expanded = expand_vector_expression(normalize_latex_delimiters(text), context)
    if not expanded.startswith("("):
        name = normalize_identifier(expanded)
        if name in context.vectors:
            return [repr(v) for v in context.vectors[name]]
        raise ValueError(f"Expected vector expression, got {text!r}")
    end = matching_paren(expanded, 0)
    if end != len(expanded) - 1:
        raise ValueError(f"Unsupported vector expression tail in {text!r}")
    parts = split_top_level(expanded[1:end], ",")
    if len(parts) != 3:
        raise ValueError(f"Expected 3D vector, got {text!r}")
    return parts


def expand_vector_expression(text: str, context: EvalContext) -> str:
    s = strip_extra_trailing_closing_parens(normalize_latex_delimiters(text))
    if s.startswith("(") and matching_paren(s, 0) == len(s) - 1:
        inner = s[1:-1]
        parts = split_top_level(inner, ",")
        if len(parts) == 3:
            return "(" + ",".join(parts) + ")"
        return expand_vector_expression(inner, context)
    for op in ["+", "-"]:
        split_at = find_binary_vector_op(s, op)
        if split_at > 0:
            left = parse_vector_components(s[:split_at], context)
            right = parse_vector_components(s[split_at + 1 :], context)
            sign = "1" if op == "+" else "-1"
            return "(" + ",".join(f"(({a})+({sign})*({b}))" for a, b in zip(left, right, strict=True)) + ")"
    split_at = find_binary_vector_op(s, "*")
    if split_at > 0:
        left_text = s[:split_at]
        right_text = s[split_at + 1 :]
        if looks_like_vector(left_text) or normalize_identifier_safe(left_text) in context.vectors:
            vector = parse_vector_components(left_text, context)
            scalar = right_text
        else:
            scalar = left_text
            vector = parse_vector_components(right_text, context)
        return "(" + ",".join(f"(({scalar})*({component}))" for component in vector) + ")"
    implicit_product = split_implicit_vector_product(s, context)
    if implicit_product is not None:
        scalar, vector_text = implicit_product
        vector = parse_vector_components(vector_text, context)
        return "(" + ",".join(f"(({scalar})*({component}))" for component in vector) + ")"
    name = normalize_identifier_safe(s)
    if name in context.vectors:
        return "(" + ",".join(repr(v) for v in context.vectors[name]) + ")"
    return s


def split_implicit_vector_product(text: str, context: EvalContext) -> tuple[str, str] | None:
    open_at = find_top_level_implicit_vector_product_open(text)
    if open_at <= 0:
        return None
    try:
        close_at = matching_paren(text, open_at)
    except ValueError:
        return None
    if close_at != len(text) - 1:
        return None
    scalar = text[:open_at].strip()
    vector_text = text[open_at + 1 : close_at].strip()
    if not scalar or not vector_text:
        return None
    try:
        scalar_expr = LatexExpression.parse(scalar)
    except Exception:
        return None
    if scalar_expr.identifiers & set(context.vectors):
        return None
    if not references_known_vector(vector_text, context) and not looks_like_vector(vector_text):
        return None
    return scalar, vector_text


def find_top_level_implicit_vector_product_open(text: str) -> int:
    depth = 0
    for index, char in enumerate(text):
        if char == "(":
            if depth == 0:
                return index
            depth += 1
        elif char == ")":
            depth -= 1
    return -1


SEGMENT_PREFIX = "\\operatorname{segment}"


def looks_like_segment(text: str) -> bool:
    normalized = normalize_latex_delimiters(text).lstrip()
    return normalized.startswith(SEGMENT_PREFIX)


def parse_segment_curve(text: str, context: EvalContext) -> VectorExpression:
    normalized = normalize_latex_delimiters(text).strip()
    if not normalized.startswith(SEGMENT_PREFIX):
        raise ValueError(f"Expected segment expression, got {text!r}")
    open_at = len(SEGMENT_PREFIX)
    while open_at < len(normalized) and normalized[open_at].isspace():
        open_at += 1
    if open_at >= len(normalized) or normalized[open_at] != "(":
        raise ValueError(f"Malformed segment expression: {text!r}")
    close_at = matching_paren(normalized, open_at)
    tail = normalized[close_at + 1 :].strip()
    if tail and any(char != ")" for char in tail):
        raise ValueError(f"Unsupported segment expression tail: {tail!r}")
    args = split_top_level(normalized[open_at + 1 : close_at], ",")
    if len(args) != 2:
        raise ValueError(f"segment() expects 2 arguments, got {len(args)}")
    start = parse_vector_components(args[0], context)
    end = parse_vector_components(args[1], context)
    components = [f"(({a})+t*(({b})-({a})))" for a, b in zip(start, end, strict=True)]
    return VectorExpression(
        raw=normalized,
        components=tuple(LatexExpression.parse(component) for component in components),  # type: ignore[arg-type]
    )


def looks_like_triangle(text: str) -> bool:
    return normalize_latex_delimiters(text).startswith("\\operatorname{triangle}")


def parse_triangle_mesh(text: str, context: EvalContext) -> TriangleMeshExpression:
    normalized = normalize_latex_delimiters(text)
    prefix = "\\operatorname{triangle}"
    if not normalized.startswith(prefix):
        raise ValueError(f"Expected triangle expression, got {text!r}")
    open_at = len(prefix)
    if open_at >= len(normalized) or normalized[open_at] != "(":
        raise ValueError(f"Malformed triangle expression: {text!r}")
    close_at = matching_paren(normalized, open_at)
    tail = normalized[close_at + 1 :].strip()
    if tail and any(char != ")" for char in tail):
        raise ValueError(f"Unsupported triangle expression tail: {tail!r}")
    args = split_top_level(normalized[open_at + 1 : close_at], ",")
    if len(args) != 3:
        raise ValueError(f"triangle() expects 3 arguments, got {len(args)}")
    if looks_like_vector_list(args[1]) and looks_like_vector_list(args[2]):
        apex = parse_vector(args[0], context)
        left = parse_vector_list(args[1], context)
        right = parse_vector_list(args[2], context)
        if len(left) != len(right):
            raise ValueError("triangle vector lists must have the same length")
        triangles = tuple((apex, a, b) for a, b in zip(left, right, strict=True))
    else:
        triangles = ((parse_vector(args[0], context), parse_vector(args[1], context), parse_vector(args[2], context)),)
    return TriangleMeshExpression(raw=normalized, triangles=triangles)


SPHERE_PREFIX = "\\operatorname{sphere}"


def looks_like_sphere(text: str) -> bool:
    return normalize_latex_delimiters(text).lstrip().startswith(SPHERE_PREFIX)


def parse_sphere_surface(text: str, context: EvalContext) -> LatexExpression:
    normalized = normalize_latex_delimiters(text).strip()
    if not normalized.startswith(SPHERE_PREFIX):
        raise ValueError(f"Expected sphere expression, got {text!r}")
    open_at = len(SPHERE_PREFIX)
    while open_at < len(normalized) and normalized[open_at].isspace():
        open_at += 1
    if open_at >= len(normalized) or normalized[open_at] != "(":
        raise ValueError(f"Malformed sphere expression: {text!r}")
    close_at = matching_paren(normalized, open_at)
    tail = normalized[close_at + 1 :].strip()
    if tail and any(char != ")" for char in tail):
        raise ValueError(f"Unsupported sphere expression tail: {tail!r}")
    args = split_top_level(normalized[open_at + 1 : close_at], ",")
    if len(args) != 2:
        raise ValueError(f"sphere() expects 2 arguments, got {len(args)}")
    center = parse_vector_components(args[0], context)
    radius = LatexExpression.parse(args[1])
    if radius.identifiers & GRAPH_VARIABLES:
        raise ValueError("sphere() radius must be scalar")
    for component in center:
        parsed = LatexExpression.parse(component)
        if parsed.identifiers & GRAPH_VARIABLES:
            raise ValueError("sphere() center must be scalar")
    cx, cy, cz = center
    return LatexExpression.parse(f"(x-({cx}))^2+(y-({cy}))^2+(z-({cz}))^2-({args[1]})^2")


def looks_like_vector_list(text: str) -> bool:
    stripped = normalize_latex_delimiters(text)
    return stripped.startswith("[") and stripped.endswith("]")


def parse_vector_list(text: str, context: EvalContext) -> list[VectorExpression]:
    stripped = normalize_latex_delimiters(text)
    if not (stripped.startswith("[") and stripped.endswith("]")):
        raise ValueError(f"Expected vector list, got {text!r}")
    vectors: list[VectorExpression] = []
    for part in split_top_level(stripped[1:-1], ","):
        if part:
            vectors.append(parse_vector(part, context))
    return vectors


def strip_extra_trailing_closing_parens(text: str) -> str:
    stripped = text.strip()
    while stripped.endswith(")") and paren_balance(stripped) < 0:
        stripped = stripped[:-1].rstrip()
    return stripped


def paren_balance(text: str) -> int:
    balance = 0
    for char in text:
        if char == "(":
            balance += 1
        elif char == ")":
            balance -= 1
    return balance


def normalize_identifier_safe(text: str) -> str | None:
    try:
        return normalize_identifier(text)
    except Exception:
        return None


def find_binary_vector_op(text: str, op: str) -> int:
    depth = 0
    for index in range(len(text) - 1, -1, -1):
        char = text[index]
        if char in ")}]":
            depth += 1
        elif char in "({[":
            depth -= 1
        elif depth == 0 and char == op:
            if op in "+-" and index == 0:
                continue
            return index
    return -1


def find_parameter_bounds(
    predicates: list[ComparisonPredicate],
    context: EvalContext,
    parameter: str,
    raw_domain: object | None = None,
) -> tuple[float, float]:
    raw_bounds = parse_raw_parameter_domain(raw_domain, context)
    lower_values: list[float] = []
    upper_values: list[float] = []
    for predicate in predicates:
        for variable, (lower, upper) in predicate.variable_bounds().items():
            if variable != parameter:
                continue
            if lower:
                lower_values.append(lower.eval(context, {}))
            if upper:
                upper_values.append(upper.eval(context, {}))
    low, high = raw_bounds or (0.0, 1.0)
    if lower_values:
        low = max([low, *lower_values]) if raw_bounds else max(lower_values)
    if upper_values:
        high = min([high, *upper_values]) if raw_bounds else min(upper_values)
    return low, high


def parse_raw_parameter_domain(raw_domain: object | None, context: EvalContext) -> tuple[float, float] | None:
    if not isinstance(raw_domain, dict):
        return None
    if "min" not in raw_domain or "max" not in raw_domain:
        return None
    try:
        low = LatexExpression.parse(str(raw_domain["min"])).eval(context, {})
        high = LatexExpression.parse(str(raw_domain["max"])).eval(context, {})
    except Exception:
        return None
    if not isfinite(low) or not isfinite(high) or low >= high:
        return None
    return low, high
