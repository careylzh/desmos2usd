from __future__ import annotations

import re
from dataclasses import dataclass, field

from desmos2usd.eval.context import EvalContext, FunctionDef
from desmos2usd.ir import ExpressionIR, GraphIR
from desmos2usd.parse.latex_subset import (
    LatexExpression,
    find_top_level,
    normalize_identifier,
    normalize_latex_delimiters,
    split_top_level,
)
from desmos2usd.parse.predicates import ComparisonPredicate, parse_predicate, parse_predicates, split_restrictions


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


def classify_graph(graph: GraphIR) -> ClassificationResult:
    context = EvalContext(degree_mode=bool(graph.source.view_metadata.get("degree_mode")))
    classified: list[ClassifiedExpression] = []
    definitions: list[ExpressionIR] = []
    definition_ids: set[str] = set()

    for expr in graph.expressions:
        if expr.type != "expression" or not expr.latex.strip():
            continue
        try:
            if register_definition(expr, context):
                definition_ids.add(expr.expr_id)
                if expr.renderable_candidate:
                    definitions.append(expr)
        except Exception as exc:
            if expr.renderable_candidate:
                raise ValueError(f"Failed to parse definition {expr.expr_id} {expr.latex!r}: {exc}") from exc

    for expr in graph.expressions:
        if not expr.renderable_candidate or expr.expr_id in definition_ids:
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

    return ClassificationResult(context=context, classified=classified, definitions=definitions)


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
    name = normalize_identifier(lhs)
    if name in {"x", "y", "z"}:
        return False
    if looks_like_vector(rhs):
        vector = parse_vector(rhs, context)
        context.vectors[name] = vector.eval(context, {})
        return True
    if looks_like_scalar_list(rhs):
        context.lists[name] = parse_scalar_list(rhs, context)
        return True
    if looks_like_ignored_definition(rhs):
        rgb = parse_rgb_definition(rhs, context)
        if rgb is not None:
            context.colors[name] = rgb
        return True
    parsed = LatexExpression.parse(rhs)
    list_names = parsed.identifiers & set(context.lists)
    if list_names:
        if parsed.identifiers & {"x", "y", "z", "t", "u", "v"}:
            return False
        lengths = {len(context.lists[list_name]) for list_name in list_names}
        if len(lengths) != 1:
            raise ValueError(f"List definition references lists with mismatched lengths: {', '.join(sorted(list_names))}")
        count = lengths.pop()
        values = []
        for index in range(count):
            variables = {list_name: context.lists[list_name][index] for list_name in list_names}
            values.append(parsed.eval(context, variables))
        context.lists[name] = tuple(values)
        return True
    if parsed.identifiers & {"x", "y", "z", "t", "u", "v"}:
        return False
    context.scalars[name] = parsed.eval(context, {})
    return True


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

    if looks_like_vector(main):
        vector = parse_vector(main, context)
        vector_identifiers = set().union(*(component.identifiers for component in vector.components))
        if {"u", "v"} <= vector_identifiers:
            return ClassifiedExpression(
                ir=expr,
                kind="parametric_surface",
                predicates=predicates,
                vector=vector,
                u_bounds=find_parameter_bounds(predicates, context, "u"),
                v_bounds=find_parameter_bounds(predicates, context, "v"),
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
            t_bounds=find_parameter_bounds(predicates, context, parameter),
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
    raise ValueError("not a supported renderable geometry form")


def looks_like_ignored_definition(rhs: str) -> bool:
    normalized = normalize_latex_delimiters(rhs)
    return normalized.startswith("\\operatorname{rgb}")


RGB_PREFIX = "\\operatorname{rgb}"


def parse_rgb_definition(rhs: str, context: EvalContext) -> tuple[int, int, int] | None:
    normalized = normalize_latex_delimiters(rhs).strip()
    if not normalized.startswith(RGB_PREFIX):
        return None
    remainder = normalized[len(RGB_PREFIX):].lstrip()
    if not remainder.startswith("(") or not remainder.endswith(")"):
        return None
    parts = split_top_level(remainder[1:-1], ",")
    if len(parts) != 3:
        return None
    channels: list[int] = []
    for part in parts:
        if not part:
            return None
        try:
            value = LatexExpression.parse(part).eval(context, {})
        except Exception:
            return None
        channels.append(max(0, min(255, int(round(value)))))
    return (channels[0], channels[1], channels[2])


def resolve_color_latex(color_latex: str | None, context: EvalContext) -> tuple[int, int, int] | None:
    if not color_latex:
        return None
    text = color_latex.strip()
    if not text:
        return None
    normalized = normalize_latex_delimiters(text).strip()
    if normalized.startswith(RGB_PREFIX):
        return parse_rgb_definition(normalized, context)
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


def expand_literal_list_expression(expr: ExpressionIR, context: EvalContext) -> list[ExpressionIR]:
    main, restriction_texts = split_restrictions(expr.latex)
    equals = find_top_level(main, "=")
    if equals < 0:
        return [expr]
    lhs = main[:equals].strip()
    rhs = main[equals + 1 :].strip()
    lhs_list = parse_literal_scalar_list(lhs, context)
    rhs_list = parse_literal_scalar_list(rhs, context)
    if lhs_list is None and rhs_list is None:
        return [expr]
    values = lhs_list if lhs_list is not None else rhs_list
    assert values is not None
    template_lhs = "{}" if lhs_list is not None else lhs
    template_rhs = rhs if lhs_list is not None else "{}"
    restrictions = "".join(r"\left\{" + restriction + r"\right\}" for restriction in restriction_texts)
    expanded: list[ExpressionIR] = []
    for index, value in enumerate(values):
        raw = dict(expr.raw)
        raw["expandedFromListExpression"] = expr.expr_id
        raw["listIndex"] = index
        expanded.append(
            ExpressionIR(
                source=expr.source,
                expr_id=f"{expr.expr_id}_{index}",
                order=expr.order,
                latex=f"{template_lhs.format(repr(value))}={template_rhs.format(repr(value))}{restrictions}",
                color=expr.color,
                color_latex=expr.color_latex,
                hidden=expr.hidden,
                folder_id=expr.folder_id,
                type=expr.type,
                raw=raw,
            )
        )
    return expanded


def expand_list_expression(expr: ExpressionIR, context: EvalContext) -> list[ExpressionIR]:
    names = [name for name in context.lists if latex_identifier_present(expr.latex, name)]
    if not names:
        return expand_literal_list_expression(expr, context)
    lengths = {len(context.lists[name]) for name in names}
    if len(lengths) != 1:
        raise ValueError(f"Expression references lists with mismatched lengths: {', '.join(names)}")
    count = lengths.pop()
    expanded: list[ExpressionIR] = []
    for index in range(count):
        latex = expr.latex
        for name in names:
            latex = replace_latex_identifier(latex, name, repr(context.lists[name][index]))
        raw = dict(expr.raw)
        raw["expandedFromListExpression"] = expr.expr_id
        raw["listIndex"] = index
        expanded.append(
            ExpressionIR(
                source=expr.source,
                expr_id=f"{expr.expr_id}_{index}",
                order=expr.order,
                latex=latex,
                color=expr.color,
                color_latex=expr.color_latex,
                hidden=expr.hidden,
                folder_id=expr.folder_id,
                type=expr.type,
                raw=raw,
            )
        )
    return expanded


def latex_identifier_present(text: str, identifier: str) -> bool:
    return re.search(latex_identifier_pattern(identifier), text) is not None


def replace_latex_identifier(text: str, identifier: str, replacement: str) -> str:
    replaced = re.sub(latex_identifier_pattern(identifier), replacement, text)
    if re.match(r"^[a-z]$", identifier):
        # Desmos commonly writes products such as `nh` without `*`.  The normal
        # identifier boundary intentionally avoids replacing inside longer names,
        # so add the narrow single-letter implicit-multiplication case here.
        replaced = re.sub(rf"(?<![A-Za-z0-9_\\]){re.escape(identifier)}(?=[A-Za-z\\])", replacement, replaced)
    return replaced


def latex_identifier_pattern(identifier: str) -> str:
    if re.match(r"^[A-Za-z]_[A-Za-z0-9]+$", identifier):
        base, sub = identifier.split("_", 1)
        raw = rf"{re.escape(base)}(?:_\{{{re.escape(sub)}\}}|_{re.escape(sub)})"
    else:
        raw = re.escape(identifier)
    return rf"(?<![A-Za-z0-9_\\]){raw}(?![A-Za-z0-9_])"


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
    name = normalize_identifier_safe(s)
    if name in context.vectors:
        return "(" + ",".join(repr(v) for v in context.vectors[name]) + ")"
    return s


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


def find_parameter_bounds(predicates: list[ComparisonPredicate], context: EvalContext, parameter: str) -> tuple[float, float]:
    low, high = 0.0, 1.0
    for predicate in predicates:
        for variable, (lower, upper) in predicate.variable_bounds().items():
            if variable != parameter:
                continue
            if lower:
                low = lower.eval(context, {})
            if upper:
                high = upper.eval(context, {})
    return low, high
