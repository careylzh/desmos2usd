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
        if len(self.terms) == 3 and len(self.ops) == 2:
            middle = single_identifier(self.terms[1])
            if middle and self.ops[0] in {"<=", "<"} and self.ops[1] in {"<=", "<"}:
                bounds[middle] = (self.terms[0], self.terms[2])
            if middle and self.ops[0] in {">=", ">"} and self.ops[1] in {">=", ">"}:
                bounds[middle] = (self.terms[2], self.terms[0])
        if len(self.terms) == 2 and len(self.ops) == 1:
            left_id = single_identifier(self.terms[0])
            right_id = single_identifier(self.terms[1])
            op = self.ops[0]
            if left_id and op in {"<=", "<"}:
                bounds[left_id] = (None, self.terms[1])
            elif left_id and op in {">=", ">"}:
                bounds[left_id] = (self.terms[1], None)
            elif right_id and op in {"<=", "<"}:
                bounds[right_id] = (self.terms[0], None)
            elif right_id and op in {">=", ">"}:
                bounds[right_id] = (None, self.terms[0])
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
                    restrictions.append(inner)
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
        for variable, (lower, upper) in predicate.variable_bounds().items():
            try:
                low_value = lower.eval(context, {}) if lower else None
                high_value = upper.eval(context, {}) if upper else None
            except Exception:
                continue
            previous = bounds.get(variable, (None, None))
            low = low_value if previous[0] is None else (max(previous[0], low_value) if low_value is not None else previous[0])
            high = high_value if previous[1] is None else (min(previous[1], high_value) if high_value is not None else previous[1])
            bounds[variable] = (low, high)
    return bounds
