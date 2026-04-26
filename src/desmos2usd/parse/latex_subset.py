from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass
from typing import Any

from desmos2usd.eval.context import EvalContext
from desmos2usd.eval.numeric import ALLOWED_FUNCTIONS, CONSTANTS


class LatexSyntaxError(ValueError):
    pass


FUNCTION_NAMES = set(ALLOWED_FUNCTIONS)

DEGREE_MODE_FUNCTIONS = {
    "acos": lambda value: math.degrees(math.acos(value)),
    "asin": lambda value: math.degrees(math.asin(value)),
    "atan": lambda value: math.degrees(math.atan(value)),
    "cos": lambda value: math.cos(math.radians(value)),
    "sin": lambda value: math.sin(math.radians(value)),
    "tan": lambda value: math.tan(math.radians(value)),
}


def normalize_latex_delimiters(text: str) -> str:
    value = text.strip()
    value = value.replace("\\left", "").replace("\\right", "")
    value = value.replace("\\{", "{").replace("\\}", "}")
    value = re.sub(r"\\[ ,;:!]", "", value)
    return value


def normalize_identifier(name: str) -> str:
    value = name.strip()
    value = value.replace("\\", "")
    value = re.sub(r"_\{([^{}]+)\}", r"_\1", value)
    value = value.replace("{", "").replace("}", "")
    value = re.sub(r"[^0-9A-Za-z_]", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    if not value:
        raise LatexSyntaxError(f"Empty identifier from {name!r}")
    if value[0].isdigit():
        value = f"v_{value}"
    return value


def strip_wrapping_parens(text: str) -> str:
    s = text.strip()
    changed = True
    while changed and s.startswith("(") and s.endswith(")"):
        changed = False
        depth = 0
        for index, char in enumerate(s):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0 and index != len(s) - 1:
                    return s
        if depth == 0:
            s = s[1:-1].strip()
            changed = True
    return s


def find_top_level(text: str, needle: str) -> int:
    depth = 0
    i = 0
    while i < len(text):
        char = text[i]
        if char in "({[":
            depth += 1
        elif char in ")}]":
            depth -= 1
        elif depth == 0 and text.startswith(needle, i):
            return i
        i += 1
    return -1


def split_top_level(text: str, delimiter: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    i = 0
    while i < len(text):
        char = text[i]
        if char in "({[":
            depth += 1
        elif char in ")}]":
            depth -= 1
        elif depth == 0 and text.startswith(delimiter, i):
            parts.append(text[start:i].strip())
            i += len(delimiter)
            start = i
            continue
        i += 1
    parts.append(text[start:].strip())
    return parts


def replace_command_with_braced_arg(text: str, command: str, replacement: str) -> str:
    target = f"\\{command}"
    i = 0
    output = ""
    while i < len(text):
        if text.startswith(target, i):
            j = i + len(target)
            if j < len(text) and text[j] == "{":
                end = matching_brace(text, j)
                inner = convert_latex_to_python(text[j + 1 : end])
                output += f"{replacement}({inner})"
                i = end + 1
                continue
        output += text[i]
        i += 1
    return output


def replace_frac(text: str) -> str:
    i = 0
    output = ""
    while i < len(text):
        if text.startswith("\\frac", i):
            j = i + len("\\frac")
            if j >= len(text) or text[j] != "{":
                raise LatexSyntaxError(f"Malformed fraction in {text!r}")
            end_num = matching_brace(text, j)
            k = end_num + 1
            if k >= len(text) or text[k] != "{":
                raise LatexSyntaxError(f"Malformed fraction denominator in {text!r}")
            end_den = matching_brace(text, k)
            numerator = convert_latex_to_python(text[j + 1 : end_num])
            denominator = convert_latex_to_python(text[k + 1 : end_den])
            output += f"(({numerator})/({denominator}))"
            i = end_den + 1
            continue
        output += text[i]
        i += 1
    return output


def matching_brace(text: str, start: int) -> int:
    open_char = text[start]
    close_char = {"{": "}", "(": ")", "[": "]"}[open_char]
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return index
    raise LatexSyntaxError(f"Unmatched {open_char!r} in {text!r}")


def convert_powers(text: str) -> str:
    output = ""
    i = 0
    while i < len(text):
        if text[i] != "^":
            output += text[i]
            i += 1
            continue
        if i + 1 >= len(text):
            raise LatexSyntaxError(f"Dangling exponent in {text!r}")
        if text[i + 1] == "{":
            end = matching_brace(text, i + 1)
            output += "**(" + convert_latex_to_python(text[i + 2 : end]) + ")"
            i = end + 1
        elif text[i + 1] == "(":
            end = matching_brace(text, i + 1)
            output += "**(" + convert_latex_to_python(text[i + 2 : end]) + ")"
            i = end + 1
        else:
            match = re.match(r"\^([A-Za-z_][A-Za-z0-9_]*|[0-9]+(?:\.[0-9]+)?)", text[i:])
            if not match:
                raise LatexSyntaxError(f"Unsupported exponent in {text!r}")
            output += "**" + match.group(1)
            i += len(match.group(0))
    return output


def replace_abs_bars(text: str) -> str:
    if "|" not in text:
        return text
    output = ""
    open_at: int | None = None
    last = 0
    for i, char in enumerate(text):
        if char != "|":
            continue
        if open_at is None:
            output += text[last:i] + "abs("
            open_at = i
        else:
            output += convert_latex_to_python(text[open_at + 1 : i]) + ")"
            open_at = None
            last = i + 1
    if open_at is not None:
        raise LatexSyntaxError(f"Unmatched absolute value bar in {text!r}")
    output += text[last:]
    return output


def insert_implicit_multiplication(expr: str) -> str:
    token_re = re.compile(r"\d+(?:\.\d*)?|\.\d+|[A-Za-z_][A-Za-z0-9_]*|\*\*|[()+\-*/,]")
    tokens = token_re.findall(expr)
    if not tokens:
        return expr
    rebuilt: list[str] = []
    for index, token in enumerate(tokens):
        if index:
            prev = tokens[index - 1]
            if needs_multiply(prev, token, index, tokens):
                rebuilt.append("*")
        rebuilt.append(token)
    return "".join(rebuilt)


def split_concatenated_symbols(expr: str) -> str:
    keep = FUNCTION_NAMES | set(CONSTANTS)
    function_names = sorted(FUNCTION_NAMES, key=len, reverse=True)

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if token in keep or "_" in token or len(token) == 1:
            return token
        if match.end() < len(expr) and expr[match.end()] == "(":
            for function_name in function_names:
                if token.endswith(function_name):
                    prefix = token[: -len(function_name)]
                    if prefix:
                        return "*".join(prefix) + "*" + function_name
        return "*".join(token)

    return re.sub(r"[A-Za-z][A-Za-z0-9_]*", replace, expr)


def is_value_end(token: str) -> bool:
    return bool(re.match(r"\d|\w|\)", token))


def is_value_start(token: str) -> bool:
    return bool(re.match(r"\d|\w|\(", token))


def needs_multiply(prev: str, token: str, index: int, tokens: list[str]) -> bool:
    if prev in {"(", "+", "-", "*", "/", ",", "**"} or token in {")", "+", "-", "*", "/", ",", "**"}:
        return False
    if prev in {"x", "y", "z", "t", "u", "v"} and token == "(":
        return True
    if re.match(r"[A-Za-z_]", prev) and token == "(":
        return False
    if prev == ")" and token == "(":
        return True
    if is_value_end(prev) and is_value_start(token):
        if re.match(r"[A-Za-z_]", prev) and token == "(":
            return False
        return True
    return False


def convert_latex_to_python(latex: str) -> str:
    text = normalize_latex_delimiters(latex)
    text = text.replace("\\cdot", "*").replace("\\times", "*")
    text = text.replace("\\le", "<=").replace("\\ge", ">=")
    text = text.replace("≤", "<=").replace("≥", ">=")
    text = text.replace("\\pi", "pi")
    text = text.replace("\\operatorname{ln}", "ln")
    text = text.replace("\\operatorname{log}", "log")
    text = re.sub(r"\\operatorname\{([^{}]+)\}", r"\1", text)
    text = replace_frac(text)
    text = replace_command_with_braced_arg(text, "sqrt", "sqrt")
    text = replace_command_with_braced_arg(text, "abs", "abs")
    for command in ["sin", "cos", "tan", "arcsin", "arccos", "arctan", "sinh", "cosh", "tanh"]:
        py_name = {"arcsin": "asin", "arccos": "acos", "arctan": "atan"}.get(command, command)
        text = text.replace(f"\\{command}", py_name)
    text = re.sub(r"pi(?=[A-Za-z_])", "pi*", text)
    text = replace_abs_bars(text)
    text = re.sub(r"([A-Za-z]_\{[^{}]+\})(?=[A-Za-z])", lambda m: normalize_identifier(m.group(1)) + "*", text)
    text = re.sub(r"([A-Za-z])_\{([^{}]+)\}", lambda m: normalize_identifier(m.group(0)), text)
    text = re.sub(r"([A-Za-z])_([A-Za-z0-9]+)", lambda m: normalize_identifier(m.group(0)), text)
    text = re.sub(r"([A-Za-z]_[0-9]+)(?=[A-Za-z])", r"\1*", text)
    text = text.replace("{", "(").replace("}", ")")
    text = convert_powers(text)
    text = split_concatenated_symbols(text)
    text = insert_implicit_multiplication(text)
    return text


class SafeExpressionValidator(ast.NodeVisitor):
    allowed_nodes = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Call,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Pow,
        ast.Mod,
        ast.USub,
        ast.UAdd,
    )

    def visit(self, node: ast.AST) -> Any:
        if not isinstance(node, self.allowed_nodes):
            raise LatexSyntaxError(f"Unsupported expression node {node.__class__.__name__}")
        return super().visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name):
            raise LatexSyntaxError("Only direct function calls are supported")
        for arg in node.args:
            self.visit(arg)
        if node.keywords:
            raise LatexSyntaxError("Keyword arguments are not supported")


@dataclass(frozen=True)
class LatexExpression:
    latex: str
    python: str
    tree: ast.Expression
    identifiers: frozenset[str]

    @classmethod
    def parse(cls, latex: str) -> "LatexExpression":
        python = convert_latex_to_python(latex)
        try:
            tree = ast.parse(python, mode="eval")
        except SyntaxError as exc:
            raise LatexSyntaxError(f"Could not parse {latex!r} as {python!r}: {exc}") from exc
        SafeExpressionValidator().visit(tree)
        identifiers = frozenset(
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id not in FUNCTION_NAMES and node.id not in CONSTANTS
        )
        return cls(latex=latex, python=python, tree=tree, identifiers=identifiers)

    def eval(self, context: EvalContext | None = None, variables: dict[str, float] | None = None) -> float:
        ctx = context or EvalContext()
        env: dict[str, Any] = {}
        env.update(ALLOWED_FUNCTIONS)
        if ctx.degree_mode:
            env.update(DEGREE_MODE_FUNCTIONS)
        env.update(CONSTANTS)
        env.update(ctx.function_callables())
        env.update(ctx.scalars)
        if variables:
            env.update(variables)
        try:
            value = eval(compile(self.tree, "<desmos-latex>", "eval"), {"__builtins__": {}}, env)
        except Exception as exc:
            raise ValueError(f"Could not evaluate {self.latex!r} with variables {variables or {}}: {exc}") from exc
        if isinstance(value, complex) or not math.isfinite(float(value)):
            raise ValueError(f"Expression {self.latex!r} evaluated to non-finite value {value!r}")
        return float(value)
