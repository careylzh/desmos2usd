from __future__ import annotations

import math


ALLOWED_FUNCTIONS = {
    "abs": abs,
    "acos": math.acos,
    "asin": math.asin,
    "atan": math.atan,
    "ceil": math.ceil,
    "cos": math.cos,
    "cosh": math.cosh,
    "exp": math.exp,
    "floor": math.floor,
    "ln": math.log,
    "log": math.log10,
    "max": max,
    "min": min,
    "mod": lambda value, modulus: value % modulus,
    "pow": pow,
    "round": round,
    "sin": math.sin,
    "sinh": math.sinh,
    "sqrt": math.sqrt,
    "tan": math.tan,
    "tanh": math.tanh,
}


CONSTANTS = {
    "e": math.e,
    "pi": math.pi,
}
