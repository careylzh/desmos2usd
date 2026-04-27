from __future__ import annotations

import re
from dataclasses import dataclass

from desmos2usd.eval.context import EvalContext
from desmos2usd.parse.latex_subset import LatexExpression, normalize_latex_delimiters, split_top_level


COMPARISON_RE = re.compile(r"(<=|>=|<|>|=)")


def _half_open_less(left: float, right: float, left_is_variable: bool, right_is_variable: bool, tol: float) -> bool:
    if left_is_variable and not right_is_variable:
        return left < right - tol
    if right_is_variable and not left_is_variable:
        return left < right + tol
    return left < right + tol


@dataclass(frozen=True)
class ComparisonPredicate:
    raw: str
    terms: tuple[LatexExpression, ...]
    ops: tuple[str, ...]

    def evaluate(self, context: EvalContext, variables: dict[str, float], tol: float = 1e-6) -> bool:
        values = [term.eval(context, variables) for term in self.terms]
        for left, op, right in zip(values[:-1], self.ops, values[1:], strict=True):
            if op == "<=" and not (left <= right + tol):
                return False
            if op == "<" and not (left < right + tol):
                return False
            if op == ">=" and not (left + tol >= right):
                return False
            if op == ">" and not (left + tol > right):
                return False
            if op == "=" and abs(left - right) > tol:
                return False
        return True

    def evaluate_half_open(self, context: EvalContext, variables: dict[str, float], tol: float = 1e-6) -> bool:
        """Like `evaluate` but strict operators treat constant bounds as half-open.

        For adjacent explicit-surface domains whose LaTeX shares a boundary (e.g. `-8<y<-7`
        and `-7<y<-6`), the symmetric-tolerant strict comparison accepts both sides of the
        shared boundary, producing overlapping meshes that z-fight as speckled artifacts.
        This variant keeps the lower bound inclusive (`C < x` accepts x=C) and makes the
        upper bound exclusive (`x < C` rejects x=C), so adjacent strict ranges tile without
        overlap while still reaching every derived/computed boundary where the variable
        sits on the inclusive side.
        """
        values = [term.eval(context, variables) for term in self.terms]
        for index, (left, op, right) in enumerate(zip(values[:-1], self.ops, values[1:], strict=True)):
            left_is_variable = bool(self.terms[index].identifiers)
            right_is_variable = bool(self.terms[index + 1].identifiers)
            if op == "<=" and not (left <= right + tol):
                return False
            if op == "<" and not _half_open_less(left, right, left_is_variable, right_is_variable, tol):
                return False
            if op == ">=" and not (left + tol >= right):
                return False
            if op == ">" and not _half_open_less(right, left, right_is_variable, left_is_variable, tol):
                return False
            if op == "=" and abs(left - right) > tol:
                return False
        return True

    def variable_bounds(self) -> dict[str, tuple[LatexExpression | None, LatexExpression | None]]:
        bounds: dict[str, tuple[LatexExpression | None, LatexExpression | None]] = {}
        for variable, lower, upper in self.iter_variable_bounds():
            previous = bounds.get(variable, (None, None))
            bounds[variable] = (
                previous[0] if previous[0] is not None else lower,
                previous[1] if previous[1] is not None else upper,
            )
        return bounds

    def iter_variable_bounds(self) -> list[tuple[str, LatexExpression | None, LatexExpression | None]]:
        bounds: list[tuple[str, LatexExpression | None, LatexExpression | None]] = []
        for left, op, right in zip(self.terms[:-1], self.ops, self.terms[1:], strict=True):
            left_id = single_identifier(left)
            right_id = single_identifier(right)
            if left_id and op in {"<=", "<"}:
                bounds.append((left_id, None, right))
            elif left_id and op in {">=", ">"}:
                bounds.append((left_id, right, None))
            elif right_id and op in {"<=", "<"}:
                bounds.append((right_id, left, None))
            elif right_id and op in {">=", ">"}:
                bounds.append((right_id, None, left))
            elif left_id and op == "=" and not right.identifiers:
                bounds.append((left_id, right, right))
            elif right_id and op == "=" and not left.identifiers:
                bounds.append((right_id, left, left))
        return bounds


def single_identifier(expr: LatexExpression) -> str | None:
    if len(expr.identifiers) == 1 and expr.python == next(iter(expr.identifiers)):
        return next(iter(expr.identifiers))
    return None


def normalize_comparators(text: str) -> str:
    return (
        text.replace("\\le", "<=")
        .replace("\\ge", ">=")
        .replace("≤", "<=")
        .replace("≥", ">=")
        .replace("\\lt", "<")
        .replace("\\gt", ">")
    )


def parse_predicate(text: str) -> ComparisonPredicate:
    raw = text.strip()
    normalized = normalize_comparators(raw)
    pieces = COMPARISON_RE.split(normalized)
    if len(pieces) < 3:
        raise ValueError(f"Predicate has no comparison operator: {text}")
    terms = tuple(LatexExpression.parse(piece.strip()) for piece in pieces[0::2])
    ops = tuple(piece.strip() for piece in pieces[1::2])
    if len(terms) != len(ops) + 1:
        raise ValueError(f"Malformed predicate: {text}")
    return ComparisonPredicate(raw=raw, terms=terms, ops=ops)


def parse_predicates(text: str) -> list[ComparisonPredicate]:
    predicates: list[ComparisonPredicate] = []
    for part in split_top_level(text, ","):
        if not part:
            continue
        predicates.append(parse_predicate(part))
    return predicates


def split_restrictions(latex: str) -> tuple[str, list[str]]:
    text = normalize_latex_delimiters(latex)
    restrictions: list[str] = []
    output: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == "{":
            end = find_matching_close_brace(text, i)
            if end >= 0:
                inner = text[i + 1 : end].strip()
                if looks_like_restriction(inner):
                    while output and output[-1].isspace():
                        output.pop()
                    if output and output[-1] in "+-*/":
                        output.pop()
                    flattened, nested_restrictions = split_nested_restrictions(inner)
                    restrictions.append(flattened)
                    restrictions.extend(nested_restrictions)
                    i = end + 1
                    continue
        output.append(text[i])
        i += 1
    return "".join(output).strip(), restrictions


def split_nested_restrictions(text: str) -> tuple[str, list[str]]:
    restrictions: list[str] = []
    output: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == "{":
            end = find_matching_close_brace(text, i)
            if end >= 0:
                inner = text[i + 1 : end].strip()
                if looks_like_restriction(inner):
                    while output and output[-1].isspace():
                        output.pop()
                    if output and output[-1] in "+-*/":
                        output.pop()
                    flattened, nested = split_nested_restrictions(inner)
                    restrictions.append(flattened)
                    restrictions.extend(nested)
                    i = end + 1
                    continue
        output.append(text[i])
        i += 1
    return "".join(output).strip(), restrictions


def find_matching_close_brace(text: str, start: int) -> int:
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return -1


def find_matching_open_brace(text: str, end: int) -> int:
    depth = 0
    for index in range(end, -1, -1):
        char = text[index]
        if char == "}":
            depth += 1
        elif char == "{":
            depth -= 1
            if depth == 0:
                return index
    return -1


def looks_like_restriction(text: str) -> bool:
    normalized = normalize_comparators(text)
    return any(op in normalized for op in ["<=", ">=", "<", ">", "="])


def collect_constant_bounds(predicates: list[ComparisonPredicate], context: EvalContext) -> dict[str, tuple[float | None, float | None]]:
    bounds: dict[str, tuple[float | None, float | None]] = {}
    for predicate in predicates:
        for variable, lower, upper in predicate.iter_variable_bounds():
            low_value = None
            high_value = None
            if lower:
                try:
                    low_value = lower.eval(context, {})
                except Exception:
                    pass
            if upper:
                try:
                    high_value = upper.eval(context, {})
                except Exception:
                    pass
            if low_value is None and high_value is None:
                continue
            previous = bounds.get(variable, (None, None))
            low = low_value if previous[0] is None else (max(previous[0], low_value) if low_value is not None else previous[0])
            high = high_value if previous[1] is None else (min(previous[1], high_value) if high_value is not None else previous[1])
            bounds[variable] = (low, high)
    return bounds
