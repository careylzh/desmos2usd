from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class SourceInfo:
    url: str
    graph_hash: str
    state_url: str
    title: str
    viewport_bounds: dict[str, tuple[float, float]] = field(default_factory=dict)
    view_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExpressionIR:
    source: SourceInfo
    expr_id: str
    order: int
    latex: str
    color: str | None = None
    color_latex: str | None = None
    hidden: bool = False
    folder_id: str | None = None
    type: str = "expression"
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def renderable_candidate(self) -> bool:
        if self.type not in {"expression", "table"}:
            return False
        return bool(self.latex.strip()) and not self.hidden


@dataclass
class GraphIR:
    source: SourceInfo
    expressions: list[ExpressionIR]
    raw_state: dict[str, Any]

    @property
    def renderable_candidates(self) -> list[ExpressionIR]:
        return [expr for expr in self.expressions if expr.renderable_candidate]


def graph_ir_from_state(state: dict[str, Any]) -> GraphIR:
    graph = state.get("graph", {})
    source = SourceInfo(
        url=str(graph.get("url") or ""),
        graph_hash=str(graph.get("hash") or ""),
        state_url=str(graph.get("state_url") or ""),
        title=str(graph.get("title") or graph.get("hash") or "Desmos graph"),
        viewport_bounds=parse_viewport_bounds(graph.get("viewport", {})),
        view_metadata=parse_view_metadata(graph),
    )
    raw_list = state.get("expressions", {}).get("list", [])
    expressions: list[ExpressionIR] = []
    for index, item in enumerate(raw_list):
        expr_type = str(item.get("type") or "expression")
        latex = str(item.get("latex") or item.get("text") or "")
        expressions.append(
            ExpressionIR(
                source=source,
                expr_id=str(item.get("id") or f"expr_{index:04d}"),
                order=index,
                latex=latex,
                color=item.get("color"),
                color_latex=item.get("colorLatex"),
                hidden=bool(item.get("hidden", False)),
                folder_id=item.get("folderId"),
                type=expr_type,
                raw=dict(item),
            )
        )
    return GraphIR(source=source, expressions=expressions, raw_state=state)


def parse_viewport_bounds(viewport: Any) -> dict[str, tuple[float, float]]:
    if not isinstance(viewport, dict):
        return {}
    bounds: dict[str, tuple[float, float]] = {}
    for axis in ("x", "y", "z"):
        try:
            low = float(viewport[f"{axis}min"])
            high = float(viewport[f"{axis}max"])
        except (KeyError, TypeError, ValueError):
            continue
        if isfinite(low) and isfinite(high) and low < high:
            bounds[axis] = (low, high)
    return bounds


def parse_view_metadata(graph: Any) -> dict[str, Any]:
    if not isinstance(graph, dict):
        return {}

    metadata: dict[str, Any] = {}
    viewport_bounds = parse_viewport_bounds(graph.get("viewport", {}))
    if viewport_bounds:
        metadata["viewport_bounds"] = viewport_bounds

    world_rotation = parse_finite_float_sequence(graph.get("worldRotation3D"), expected_length=9)
    if world_rotation is not None:
        metadata["world_rotation_3d"] = world_rotation

    axis = parse_finite_float_sequence(graph.get("axis3D"), expected_length=3)
    if axis is not None:
        metadata["axis_3d"] = axis

    if isinstance(graph.get("threeDMode"), bool):
        metadata["three_d_mode"] = graph["threeDMode"]
    if isinstance(graph.get("degreeMode"), bool):
        metadata["degree_mode"] = graph["degreeMode"]
    if isinstance(graph.get("showPlane3D"), bool):
        metadata["show_plane_3d"] = graph["showPlane3D"]
    return metadata


def parse_finite_float_sequence(value: Any, expected_length: int) -> tuple[float, ...] | None:
    if not isinstance(value, list | tuple) or len(value) != expected_length:
        return None
    parsed = []
    for item in value:
        if isinstance(item, bool):
            return None
        try:
            parsed_item = float(item)
        except (TypeError, ValueError):
            return None
        if not isfinite(parsed_item):
            return None
        parsed.append(parsed_item)
    return tuple(parsed)
