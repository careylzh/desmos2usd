from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class FunctionDef:
    name: str
    params: tuple[str, ...]
    body: object


@dataclass
class EvalContext:
    degree_mode: bool = False
    random_seed: str = ""
    random_list_limit: int = 128
    scalars: dict[str, float] = field(default_factory=dict)
    lists: dict[str, tuple[float, ...]] = field(default_factory=dict)
    point_lists: dict[str, tuple[tuple[float, ...], ...]] = field(default_factory=dict)
    vectors: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    functions: dict[str, FunctionDef] = field(default_factory=dict)
    colors: dict[str, tuple[int, int, int]] = field(default_factory=dict)

    def child_vars(self, values: dict[str, float]) -> dict[str, float]:
        merged = dict(self.scalars)
        merged.update(values)
        return merged

    def function_callables(self) -> dict[str, Callable[..., float]]:
        callables: dict[str, Callable[..., float]] = {}
        for name, definition in self.functions.items():
            callables[name] = self._make_callable(definition)
        return callables

    def _make_callable(self, definition: FunctionDef) -> Callable[..., float]:
        def call(*args: float) -> float:
            if len(args) != len(definition.params):
                raise ValueError(f"Function {definition.name} expected {len(definition.params)} args, got {len(args)}")
            variables = dict(zip(definition.params, args, strict=True))
            return definition.body.eval(self, variables)  # type: ignore[attr-defined]

        return call
