from __future__ import annotations

import argparse
import ast
import json
import math
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from desmos2usd.eval.context import EvalContext
from desmos2usd.parse.latex_subset import LatexExpression, find_top_level, normalize_identifier
from desmos2usd.parse.predicates import parse_predicates, split_restrictions

AXES = ("x", "y", "z")
PRIM_START_RE = re.compile(r'^\s*def\s+(Mesh|BasisCurves)\s+"([^"]+)"')
CUSTOM_STRING_RE = re.compile(r'^\s*custom\s+string\s+desmos:([A-Za-z]+)\s+=\s+(.+)$')
CUSTOM_INT_RE = re.compile(r'^\s*custom\s+int\s+desmos:([A-Za-z]+)\s+=\s+(-?\d+)\s*$')
CUSTOM_BOOL_RE = re.compile(r'^\s*custom\s+bool\s+desmos:([A-Za-z]+)\s+=\s+(true|false)\s*$')
COMPARISON_OP_RE = re.compile(r"(\\leq?(?![A-Za-z])|\\geq?(?![A-Za-z])|\\lt(?![A-Za-z])|\\gt(?![A-Za-z])|<=|>=|≤|≥|<|>)")
AXIS_TOKEN_RE = re.compile(r"^\s*([xyz])\s*$")
IDENTIFIER_TOKEN_RE = re.compile(r"^\s*[A-Za-z\\][A-Za-z0-9_\\{}]*\s*$")
NUMERIC_CONSTANT_RE = re.compile(r"^[0-9+\-*/().\s]+$")
LEFT_RIGHT_RE = re.compile(r"\\left|\\right")
REACHABILITY_TOLERANCE = 1e-6
BOUNDARY_EDGE_KEY_DECIMALS = 5
BOUNDARY_BBOX_TOLERANCE = 1e-5
BOUNDARY_NEAR_CANDIDATE_LIMIT = 5
SAMPLED_DOMAIN_BOUND_TOLERANCE = 1e-5
Point3 = tuple[float, float, float]
BoundaryEdgeKey = tuple[Point3, Point3]
BoundaryPlaneKey = tuple[str, float]
BoundaryLineKey = tuple[BoundaryPlaneKey, BoundaryPlaneKey]


@dataclass(frozen=True)
class ParsedUsdPrim:
    name: str
    usd_kind: str
    expr_id: str
    order: int | None
    source_kind: str
    latex: str
    constraints: str
    color: str
    hidden: bool | None
    points: list[tuple[float, float, float]]
    face_count: int
    curve_count: int
    face_vertex_counts: list[int]
    face_vertex_indices: list[int]


@dataclass
class ConstantRestrictionBound:
    axis: str
    min: float | None = None
    max: float | None = None
    min_inclusive: bool | None = None
    max_inclusive: bool | None = None
    min_expr: str | None = None
    max_expr: str | None = None


def parse_usda_prims(path: Path) -> list[ParsedUsdPrim]:
    prims: list[ParsedUsdPrim] = []
    current: dict[str, Any] | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        start_match = PRIM_START_RE.match(raw_line)
        if start_match:
            if current is not None:
                prims.append(parsed_prim_from_current(current))
            current = {
                "usd_kind": start_match.group(1),
                "name": start_match.group(2),
                "metadata": {},
                "points": [],
                "face_vertex_counts": [],
                "face_vertex_indices": [],
                "curve_count": 0,
            }
            continue

        if current is None:
            continue

        string_match = CUSTOM_STRING_RE.match(raw_line)
        if string_match:
            current["metadata"][string_match.group(1)] = json.loads(string_match.group(2))
            continue

        int_match = CUSTOM_INT_RE.match(raw_line)
        if int_match:
            current["metadata"][int_match.group(1)] = int(int_match.group(2))
            continue

        bool_match = CUSTOM_BOOL_RE.match(raw_line)
        if bool_match:
            current["metadata"][bool_match.group(1)] = bool_match.group(2) == "true"
            continue

        if "point3f[] points =" in raw_line:
            current["points"] = parse_points(raw_line)
            continue

        if "int[] faceVertexCounts =" in raw_line:
            current["face_vertex_counts"] = parse_int_list(raw_line)
            continue

        if "int[] faceVertexIndices =" in raw_line:
            current["face_vertex_indices"] = parse_int_list(raw_line)
            continue

        if "int[] curveVertexCounts =" in raw_line:
            current["curve_count"] = len(parse_int_list(raw_line))

    if current is not None:
        prims.append(parsed_prim_from_current(current))

    return prims


def parsed_prim_from_current(current: dict[str, Any]) -> ParsedUsdPrim:
    metadata = current["metadata"]
    return ParsedUsdPrim(
        name=str(current["name"]),
        usd_kind=str(current["usd_kind"]),
        expr_id=str(metadata.get("exprId", "")),
        order=metadata.get("order") if isinstance(metadata.get("order"), int) else None,
        source_kind=str(metadata.get("kind", "")),
        latex=str(metadata.get("latex", "")),
        constraints=str(metadata.get("constraints", "")),
        color=str(metadata.get("color", "")),
        hidden=metadata.get("hidden") if isinstance(metadata.get("hidden"), bool) else None,
        points=current["points"],
        face_count=len(current["face_vertex_counts"]),
        curve_count=int(current["curve_count"]),
        face_vertex_counts=list(current["face_vertex_counts"]),
        face_vertex_indices=list(current["face_vertex_indices"]),
    )


def parse_points(line: str) -> list[tuple[float, float, float]]:
    rhs = line.split("=", 1)[1]
    points = []
    for match in re.finditer(r"\(([^()]*)\)", rhs):
        coords = [float(part.strip()) for part in match.group(1).split(",")]
        if len(coords) != 3:
            raise ValueError(f"Expected point3f tuple with 3 coordinates, got {match.group(0)!r}")
        if all(math.isfinite(coord) for coord in coords):
            points.append((coords[0], coords[1], coords[2]))
    return points


def parse_int_list(line: str) -> list[int]:
    rhs = line.split("=", 1)[1].strip()
    if not rhs.startswith("[") or not rhs.endswith("]"):
        raise ValueError(f"Expected USD int array, got {rhs!r}")
    body = rhs[1:-1].strip()
    if not body:
        return []
    return [int(part.strip()) for part in body.split(",")]


def parse_constant_restriction_bounds(constraints: str) -> dict[str, dict[str, Any]]:
    bounds: dict[str, ConstantRestrictionBound] = {}
    for fragment in constraints.split(";"):
        normalized_fragment = normalize_constraint_fragment(fragment)
        parts = [part.strip() for part in COMPARISON_OP_RE.split(normalized_fragment) if part.strip()]
        if len(parts) < 3 or len(parts) % 2 == 0:
            continue
        for index in range(0, len(parts) - 2, 2):
            apply_constant_relation(parts[index], parts[index + 1], parts[index + 2], bounds)
    return {axis: asdict(bound) for axis, bound in sorted(bounds.items())}


def normalize_constraint_fragment(fragment: str) -> str:
    return LEFT_RIGHT_RE.sub("", fragment)


def apply_constant_relation(
    left: str,
    operator_text: str,
    right: str,
    bounds: dict[str, ConstantRestrictionBound],
) -> None:
    operator = normalize_comparison_operator(operator_text)
    if operator is None:
        return

    left_axis = isolated_axis(left)
    right_axis = isolated_axis(right)
    if left_axis and not right_axis:
        constant = parse_numeric_constant(right)
        if constant is None:
            return
        if operator in ("<", "<="):
            update_constant_bound(bounds, left_axis, "max", constant, operator == "<=", right)
        else:
            update_constant_bound(bounds, left_axis, "min", constant, operator == ">=", right)
        return

    if right_axis and not left_axis:
        constant = parse_numeric_constant(left)
        if constant is None:
            return
        if operator in ("<", "<="):
            update_constant_bound(bounds, right_axis, "min", constant, operator == "<=", left)
        else:
            update_constant_bound(bounds, right_axis, "max", constant, operator == ">=", left)


def normalize_comparison_operator(operator_text: str) -> str | None:
    operator = operator_text.strip()
    if operator in ("<", ">", "<=", ">="):
        return operator
    if operator in (r"\le", r"\leq", "≤"):
        return "<="
    if operator in (r"\ge", r"\geq", "≥"):
        return ">="
    if operator == r"\lt":
        return "<"
    if operator == r"\gt":
        return ">"
    return None


def isolated_axis(text: str) -> str | None:
    match = AXIS_TOKEN_RE.match(text)
    return match.group(1) if match else None


def parse_numeric_constant(text: str) -> float | None:
    expression = text.strip()
    if not expression or not NUMERIC_CONSTANT_RE.fullmatch(expression):
        return None
    try:
        parsed = ast.parse(expression, mode="eval")
        value = eval_numeric_ast(parsed.body)
    except (SyntaxError, ValueError, ZeroDivisionError):
        return None
    if not math.isfinite(value):
        return None
    return value


def eval_numeric_ast(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp):
        operand = eval_numeric_ast(node.operand)
        if isinstance(node.op, ast.UAdd):
            return operand
        if isinstance(node.op, ast.USub):
            return -operand
    if isinstance(node, ast.BinOp):
        left = eval_numeric_ast(node.left)
        right = eval_numeric_ast(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
    raise ValueError(f"Unsupported constant expression node: {ast.dump(node)}")


def update_constant_bound(
    bounds: dict[str, ConstantRestrictionBound],
    axis: str,
    side: str,
    value: float,
    inclusive: bool,
    source_expr: str,
) -> None:
    bound = bounds.setdefault(axis, ConstantRestrictionBound(axis=axis))
    if side == "min":
        if bound.min is None or value > bound.min or (value == bound.min and not inclusive):
            bound.min = value
            bound.min_inclusive = inclusive
            bound.min_expr = source_expr.strip()
        return
    if bound.max is None or value < bound.max or (value == bound.max and not inclusive):
        bound.max = value
        bound.max_inclusive = inclusive
        bound.max_expr = source_expr.strip()


def build_prim_diagnostics(
    usda_path: Path,
    report_path: Path | None = None,
    limit: int = 20,
    viewport_margin_fraction: float = 0.10,
    include_boundary_near_candidates: bool = False,
) -> dict[str, Any]:
    prims = parse_usda_prims(usda_path)
    report = load_report(report_path)
    source_viewport_bbox = source_viewport_bbox_from_report(report)
    prim_bboxes = [bbox_for_points(prim.points) if prim.points else None for prim in prims]
    global_bbox = combined_bbox([bbox for bbox in prim_bboxes if bbox is not None])
    boundary_adjacency_by_prim = build_boundary_adjacency_by_prim(
        prims,
        global_bbox,
        include_near_candidates=include_boundary_near_candidates,
    )
    source_center = bbox_center(source_viewport_bbox) if source_viewport_bbox else bbox_center(global_bbox)
    source_diagonal = diagonal_length(source_viewport_bbox) if source_viewport_bbox else diagonal_length(global_bbox)

    prim_metrics = []
    for index, prim in enumerate(prims):
        if not prim.points:
            continue
        bbox = prim_bboxes[index]
        if bbox is None:
            continue
        center = bbox_center(bbox)
        constant_restriction_bounds = parse_constant_restriction_bounds(prim.constraints)
        restriction_inset = restriction_inset_for_bbox(bbox, constant_restriction_bounds)
        metrics = {
            "prim_name": prim.name,
            "usd_kind": prim.usd_kind,
            "expr_id": prim.expr_id,
            "order": prim.order,
            "kind": prim.source_kind,
            "point_count": len(prim.points),
            "face_count": prim.face_count,
            "curve_count": prim.curve_count,
            "bbox": bbox,
            "center": center,
            "center_distance_from_source_center": distance(center, source_center) if source_center else None,
            "largest_axis_span": max(bbox["span"]),
            "global_span_contribution": global_span_contribution(index, prim_bboxes, global_bbox),
            "viewport_overshoot": viewport_overshoot(bbox, source_viewport_bbox, viewport_margin_fraction),
            "boundary_adjacency": boundary_adjacency_by_prim[index],
            "constant_restriction_bounds": constant_restriction_bounds,
            "restriction_inset": restriction_inset,
            "latex": prim.latex,
            "constraints": prim.constraints,
            "color": prim.color,
            "hidden": prim.hidden,
        }
        if restriction_inset["positive_side_count"]:
            metrics["restriction_bound_reachability"] = restriction_bound_reachability(
                prim,
                restriction_inset,
                constant_restriction_bounds,
            )
        metrics["suspicion_score"] = suspicion_score(metrics, source_diagonal)
        prim_metrics.append(metrics)

    viewport_outliers = [item for item in prim_metrics if item["viewport_overshoot"]["outside_axes"]]
    viewport_outliers.sort(key=suspicion_sort_key)
    center_distance = sorted(prim_metrics, key=center_distance_sort_key)
    largest_span = sorted(prim_metrics, key=largest_span_sort_key)
    top_suspicious = sorted(prim_metrics, key=suspicion_sort_key)
    restriction_insets = [item for item in prim_metrics if item["restriction_inset"]["positive_side_count"]]
    restriction_insets.sort(key=restriction_inset_sort_key)
    boundary_gaps = [
        item for item in prim_metrics if item["boundary_adjacency"]["internal_unmatched_boundary_edge_count"] > 0
    ]
    boundary_gaps.sort(key=boundary_gap_sort_key)
    unexplained_boundary_gaps = [
        item
        for item in boundary_gaps
        if item["boundary_adjacency"]["unexplained_internal_unmatched_boundary_edge_count"] > 0
    ]
    source_bound_supported_boundary_gaps = [
        item
        for item in boundary_gaps
        if item["boundary_adjacency"]["source_bound_supported_internal_unmatched_boundary_edge_count"] > 0
    ]
    source_bound_supported_only_boundary_gaps = [
        item
        for item in source_bound_supported_boundary_gaps
        if item["boundary_adjacency"]["unexplained_internal_unmatched_boundary_edge_count"] == 0
        and item["boundary_adjacency"]["sampled_domain_bound_internal_unmatched_boundary_edge_count"] == 0
        and item["boundary_adjacency"].get("sampled_predicate_clip_internal_unmatched_boundary_edge_count", 0) == 0
    ]
    source_bound_supported_only_boundary_gaps.sort(key=source_bound_supported_only_sort_key)
    sampled_domain_bound_boundary_gaps = [
        item
        for item in boundary_gaps
        if item["boundary_adjacency"]["sampled_domain_bound_internal_unmatched_boundary_edge_count"] > 0
    ]
    sampled_domain_bound_boundary_gaps.sort(key=sampled_domain_bound_sort_key)
    sampled_predicate_clip_boundary_gaps = [
        item
        for item in boundary_gaps
        if item["boundary_adjacency"]["sampled_predicate_clip_internal_unmatched_boundary_edge_count"] > 0
    ]
    sampled_predicate_clip_boundary_gaps.sort(key=sampled_predicate_clip_sort_key)
    same_line_partition_mismatch_rows = [
        item for item in boundary_gaps if item["boundary_adjacency"].get("same_line_partition_mismatch_count", 0) > 0
    ]
    parsed_restriction_count = sum(1 for item in prim_metrics if item["constant_restriction_bounds"])
    reachability_counts = restriction_inset_reachability_counts(restriction_insets)

    return {
        "usda_path": str(usda_path),
        "report_path": str(report_path) if report_path else None,
        "graph_hash": report.get("graph_hash") if isinstance(report, dict) else None,
        "prim_count": len(prims),
        "measured_prim_count": len(prim_metrics),
        "global_bbox": global_bbox,
        "source_viewport_bbox": source_viewport_bbox,
        "source_center": source_center,
        "source_diagonal": source_diagonal,
        "ranking_rule": (
            "suspicion_score desc, then source order, then prim name; score favors source viewport overshoot, "
            "center distance beyond half the source viewport diagonal, and contribution to global bbox span"
        ),
        "viewport_outlier_count": len(viewport_outliers),
        "viewport_outliers": [compact_all_prims_metric(item) for item in viewport_outliers[:limit]],
        "constant_restriction_prim_count": parsed_restriction_count,
        "restriction_inset_count": len(restriction_insets),
        "restriction_inset_reachability_counts": reachability_counts,
        "top_restriction_insets": [compact_all_prims_metric(item) for item in restriction_insets[:limit]],
        "boundary_gap_rule": (
            "mesh boundary edges are exact-supported only when another prim has the same rounded endpoint pair; "
            "internal unmatched excludes edges whose midpoint lies on a nondegenerate exported global bbox side"
        ),
        "boundary_source_bound_support_rule": (
            "an internal unmatched boundary edge is source-bound-supported when the whole edge lies on one of the "
            "source expression's own parsed strict constant restriction planes"
        ),
        "boundary_sampled_domain_bound_rule": (
            "after source-bound support, an explicit-surface internal unmatched boundary edge is sampled-domain-bound "
            "supported when it lies on the first or last face-used sample value for a domain axis side proven by a "
            "parsed constant restriction bound or parsed predicate bound; remaining internal unmatched edges are "
            "unexplained"
        ),
        "boundary_sampled_predicate_clip_rule": (
            "after sampled-domain-bound support, an explicit-surface internal unmatched boundary edge is "
            "sampled-predicate-clip supported when it lies on the first or last face-used sample value for a domain "
            "axis side that has no direct domain-axis bound proof, but the explicit axis has a parsed predicate bound "
            "whose expression depends on that domain axis"
        ),
        "boundary_near_candidate_rule": (
            "for each unexplained internal unmatched mesh boundary edge, the nearest candidate is chosen from other "
            "prim boundary edges sharing at least one rounded axis-aligned plane; candidates sort by midpoint distance, then "
            "unordered endpoint-pair distance, then length delta"
        ),
        "same_line_partition_mismatch_rule": (
            "for unexplained internal unmatched axis-aligned boundary edges, group by the exact rounded line from two shared "
            "planes; report another prim when its boundary edges overlap that line but do not provide exact matching "
            "edge partitions"
        ),
        "boundary_near_candidate_enabled": include_boundary_near_candidates,
        "boundary_edge_match_decimals": BOUNDARY_EDGE_KEY_DECIMALS,
        "boundary_gap_count": len(boundary_gaps),
        "unexplained_boundary_gap_count": len(unexplained_boundary_gaps),
        "source_bound_supported_boundary_gap_count": len(source_bound_supported_boundary_gaps),
        "source_bound_supported_only_boundary_gap_count": len(source_bound_supported_only_boundary_gaps),
        "sampled_domain_bound_boundary_gap_count": len(sampled_domain_bound_boundary_gaps),
        "sampled_predicate_clip_boundary_gap_count": len(sampled_predicate_clip_boundary_gaps),
        "same_line_partition_mismatch_prim_count": len(same_line_partition_mismatch_rows),
        "top_boundary_gaps": boundary_gaps[:limit],
        "top_source_bound_supported_only_boundary_gaps": source_bound_supported_only_boundary_gaps[:limit],
        "top_sampled_domain_bound_boundary_gaps": sampled_domain_bound_boundary_gaps[:limit],
        "top_sampled_predicate_clip_boundary_gaps": sampled_predicate_clip_boundary_gaps[:limit],
        "top_suspicious": [compact_all_prims_metric(item) for item in top_suspicious[:limit]],
        "top_center_distance": [compact_all_prims_metric(item) for item in center_distance[:limit]],
        "top_largest_span": [compact_all_prims_metric(item) for item in largest_span[:limit]],
        "all_prims": [compact_all_prims_metric(item) for item in prim_metrics],
    }


def load_report(report_path: Path | None) -> dict[str, Any]:
    if report_path is None:
        return {}
    return json.loads(report_path.read_text(encoding="utf-8"))


def source_viewport_bbox_from_report(report: dict[str, Any]) -> dict[str, list[float]] | None:
    diagnostics = report.get("geometry_diagnostics")
    if not isinstance(diagnostics, dict):
        return None
    bbox = diagnostics.get("source_viewport_bbox")
    if not isinstance(bbox, dict):
        return None
    return normalized_bbox(bbox)


def normalized_bbox(bbox: dict[str, Any]) -> dict[str, list[float]]:
    mins = [float(value) for value in bbox["min"]]
    maxs = [float(value) for value in bbox["max"]]
    return {"min": mins, "max": maxs, "span": [maxs[index] - mins[index] for index in range(3)]}


def bbox_for_points(points: list[tuple[float, float, float]]) -> dict[str, list[float]]:
    mins = [min(point[index] for point in points) for index in range(3)]
    maxs = [max(point[index] for point in points) for index in range(3)]
    return {"min": mins, "max": maxs, "span": [maxs[index] - mins[index] for index in range(3)]}


def combined_bbox(boxes: list[dict[str, list[float]]]) -> dict[str, list[float]] | None:
    if not boxes:
        return None
    mins = [min(box["min"][index] for box in boxes) for index in range(3)]
    maxs = [max(box["max"][index] for box in boxes) for index in range(3)]
    return {"min": mins, "max": maxs, "span": [maxs[index] - mins[index] for index in range(3)]}


def bbox_center(bbox: dict[str, list[float]] | None) -> list[float] | None:
    if bbox is None:
        return None
    return [(bbox["min"][index] + bbox["max"][index]) / 2.0 for index in range(3)]


def diagonal_length(bbox: dict[str, list[float]] | None) -> float | None:
    if bbox is None:
        return None
    return math.sqrt(sum(span * span for span in bbox["span"]))


def distance(left: list[float] | None, right: list[float] | None) -> float | None:
    if left is None or right is None:
        return None
    return math.sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))


def viewport_overshoot(
    bbox: dict[str, list[float]],
    source_viewport_bbox: dict[str, list[float]] | None,
    margin_fraction: float,
) -> dict[str, Any]:
    outside_axes = []
    max_overshoot = 0.0
    if source_viewport_bbox is None:
        return {"max": 0.0, "outside_axes": outside_axes}
    for index, axis in enumerate(AXES):
        margin = source_viewport_bbox["span"][index] * margin_fraction
        low_overshoot = max(0.0, source_viewport_bbox["min"][index] - bbox["min"][index])
        high_overshoot = max(0.0, bbox["max"][index] - source_viewport_bbox["max"][index])
        axis_overshoot = max(low_overshoot, high_overshoot)
        max_overshoot = max(max_overshoot, axis_overshoot)
        if axis_overshoot > margin:
            outside_axes.append(
                {
                    "axis": axis,
                    "low_overshoot": low_overshoot,
                    "high_overshoot": high_overshoot,
                    "threshold_margin": margin,
                }
            )
    return {"max": max_overshoot, "outside_axes": outside_axes}


def global_span_contribution(
    prim_index: int,
    prim_bboxes: list[dict[str, list[float]] | None],
    global_bbox: dict[str, list[float]] | None,
) -> dict[str, Any]:
    if global_bbox is None:
        return {"max": 0.0, "by_axis": []}
    boxes = [bbox for index, bbox in enumerate(prim_bboxes) if index != prim_index and bbox is not None]
    without = combined_bbox(boxes)
    if without is None:
        return {"max": 0.0, "by_axis": []}
    by_axis = []
    max_contribution = 0.0
    for index, axis in enumerate(AXES):
        contribution = global_bbox["span"][index] - without["span"][index]
        max_contribution = max(max_contribution, contribution)
        by_axis.append({"axis": axis, "span_reduction_if_removed": contribution})
    return {"max": max_contribution, "by_axis": by_axis}


def build_boundary_adjacency_by_prim(
    prims: list[ParsedUsdPrim],
    global_bbox: dict[str, list[float]] | None,
    include_near_candidates: bool,
) -> list[dict[str, Any]]:
    boundary_edges_by_prim = [boundary_edges_for_prim(index, prim) for index, prim in enumerate(prims)]
    constant_bounds_by_prim = [parse_constant_restriction_bounds(prim.constraints) for prim in prims]
    edges_by_key: dict[BoundaryEdgeKey, list[dict[str, Any]]] = defaultdict(list)
    edges_by_plane: dict[BoundaryPlaneKey, list[dict[str, Any]]] = defaultdict(list)
    edges_by_line: dict[BoundaryLineKey, list[dict[str, Any]]] = defaultdict(list)
    for edges in boundary_edges_by_prim:
        for edge in edges:
            edges_by_key[edge["key"]].append(edge)
            if include_near_candidates:
                for plane_key in edge["plane_keys"]:
                    edges_by_plane[plane_key].append(edge)
                line_key = boundary_edge_line_key(edge)
                if line_key is not None:
                    edges_by_line[line_key].append(edge)

    return [
        boundary_adjacency_for_prim(
            edges,
            edges_by_key,
            edges_by_plane,
            edges_by_line,
            prims[index],
            prims,
            global_bbox,
            constant_bounds_by_prim[index],
            include_near_candidates=include_near_candidates,
        )
        for index, edges in enumerate(boundary_edges_by_prim)
    ]


def boundary_edges_for_prim(prim_index: int, prim: ParsedUsdPrim) -> list[dict[str, Any]]:
    if prim.usd_kind != "Mesh" or not prim.face_vertex_counts or not prim.face_vertex_indices:
        return []

    edge_use_counts: dict[tuple[int, int], int] = defaultdict(int)
    offset = 0
    for face_vertex_count in prim.face_vertex_counts:
        face_indices = prim.face_vertex_indices[offset : offset + face_vertex_count]
        offset += face_vertex_count
        if len(face_indices) < 2:
            continue
        for local_index, start_index in enumerate(face_indices):
            end_index = face_indices[(local_index + 1) % len(face_indices)]
            edge_use_counts[tuple(sorted((start_index, end_index)))] += 1

    edges = []
    boundary_edge_index = 0
    for start_index, end_index in sorted(edge_use_counts):
        if edge_use_counts[(start_index, end_index)] != 1:
            continue
        if start_index >= len(prim.points) or end_index >= len(prim.points):
            continue
        start = prim.points[start_index]
        end = prim.points[end_index]
        edge = {
            "edge_index": boundary_edge_index,
            "prim_index": prim_index,
            "start": start,
            "end": end,
            "midpoint": tuple((start[axis] + end[axis]) / 2.0 for axis in range(3)),
            "length": distance(start, end),
            "key": boundary_edge_key(start, end),
        }
        edge["plane_keys"] = boundary_edge_plane_keys(edge)
        edges.append(edge)
        boundary_edge_index += 1
    return edges


def boundary_edge_plane_keys(edge: dict[str, Any]) -> list[BoundaryPlaneKey]:
    keys = []
    start = edge["start"]
    end = edge["end"]
    for axis_index, axis in enumerate(AXES):
        if abs(start[axis_index] - end[axis_index]) <= BOUNDARY_BBOX_TOLERANCE:
            keys.append((axis, round((start[axis_index] + end[axis_index]) / 2.0, BOUNDARY_EDGE_KEY_DECIMALS)))
    return keys


def boundary_edge_line_key(edge: dict[str, Any]) -> BoundaryLineKey | None:
    plane_keys = edge["plane_keys"]
    if len(plane_keys) != 2:
        return None
    first, second = sorted(plane_keys)
    return first, second


def boundary_plane_key_detail(plane_key: BoundaryPlaneKey) -> dict[str, Any]:
    axis, value = plane_key
    return {"axis": axis, "value": value}


def boundary_edge_identity(edge: dict[str, Any]) -> tuple[int, int]:
    return int(edge["prim_index"]), int(edge["edge_index"])


def boundary_adjacency_for_prim(
    edges: list[dict[str, Any]],
    edges_by_key: dict[BoundaryEdgeKey, list[dict[str, Any]]],
    edges_by_plane: dict[BoundaryPlaneKey, list[dict[str, Any]]],
    edges_by_line: dict[BoundaryLineKey, list[dict[str, Any]]],
    prim: ParsedUsdPrim,
    prims: list[ParsedUsdPrim],
    global_bbox: dict[str, list[float]] | None,
    source_constant_bounds: dict[str, dict[str, Any]],
    include_near_candidates: bool,
) -> dict[str, Any]:
    matched_edges = []
    unmatched_edges = []
    internal_unmatched_edges = []
    for edge in edges:
        matched_by_other_prim = any(other["prim_index"] != edge["prim_index"] for other in edges_by_key[edge["key"]])
        if matched_by_other_prim:
            matched_edges.append(edge)
            continue
        unmatched_edges.append(edge)
        if not edge_midpoint_on_global_bbox(edge, global_bbox):
            internal_unmatched_edges.append(edge)

    source_bound_support = source_bound_support_for_internal_edges(internal_unmatched_edges, source_constant_bounds)
    sampled_domain_bound_support = sampled_domain_bound_support_for_internal_edges(
        source_bound_support["unexplained_edges"],
        prim,
        source_constant_bounds,
    )
    sampled_predicate_clip_support = sampled_predicate_clip_support_for_internal_edges(
        sampled_domain_bound_support["unexplained_edges"],
        prim,
        source_constant_bounds,
    )
    unexplained_internal_edges = sampled_predicate_clip_support["unexplained_edges"]
    longest_internal = max(internal_unmatched_edges, key=lambda item: float(item["length"]), default=None)
    longest_unexplained = max(unexplained_internal_edges, key=lambda item: float(item["length"]), default=None)
    near_candidates = []
    same_line_partition_mismatches = []
    longest_internal_near_candidate = None
    if include_near_candidates:
        near_candidates = near_boundary_candidates_for_internal_edges(
            unexplained_internal_edges,
            edges_by_plane,
            prims,
            limit=BOUNDARY_NEAR_CANDIDATE_LIMIT,
        )
        same_line_partition_mismatches = same_line_partition_mismatches_for_internal_edges(
            unexplained_internal_edges,
            edges_by_line,
            prims,
            limit=BOUNDARY_NEAR_CANDIDATE_LIMIT,
        )
        if longest_unexplained is not None:
            longest_internal_near_candidate = best_near_boundary_candidate_for_edge(
                longest_unexplained,
                edges_by_plane,
                prims,
            )
    return {
        "boundary_edge_count": len(edges),
        "boundary_edge_length": sum(float(edge["length"]) for edge in edges),
        "exact_matched_boundary_edge_count": len(matched_edges),
        "exact_matched_boundary_edge_length": sum(float(edge["length"]) for edge in matched_edges),
        "unmatched_boundary_edge_count": len(unmatched_edges),
        "unmatched_boundary_edge_length": sum(float(edge["length"]) for edge in unmatched_edges),
        "internal_unmatched_boundary_edge_count": len(internal_unmatched_edges),
        "internal_unmatched_boundary_edge_length": sum(float(edge["length"]) for edge in internal_unmatched_edges),
        "longest_internal_unmatched_boundary_edge": edge_summary(longest_internal),
        "source_bound_supported_internal_unmatched_boundary_edge_count": len(
            source_bound_support["supported_edges"]
        ),
        "source_bound_supported_internal_unmatched_boundary_edge_length": sum(
            float(edge["length"]) for edge in source_bound_support["supported_edges"]
        ),
        "source_bound_supported_internal_unmatched_boundary_edge_refs": source_bound_support["supports"],
        "sampled_domain_bound_internal_unmatched_boundary_edge_count": len(
            sampled_domain_bound_support["supported_edges"]
        ),
        "sampled_domain_bound_internal_unmatched_boundary_edge_length": sum(
            float(edge["length"]) for edge in sampled_domain_bound_support["supported_edges"]
        ),
        "sampled_domain_bound_internal_unmatched_boundary_edge_refs": sampled_domain_bound_support["supports"],
        "sampled_predicate_clip_internal_unmatched_boundary_edge_count": len(
            sampled_predicate_clip_support["supported_edges"]
        ),
        "sampled_predicate_clip_internal_unmatched_boundary_edge_length": sum(
            float(edge["length"]) for edge in sampled_predicate_clip_support["supported_edges"]
        ),
        "sampled_predicate_clip_internal_unmatched_boundary_edge_refs": sampled_predicate_clip_support["supports"],
        "unexplained_internal_unmatched_boundary_edge_count": len(unexplained_internal_edges),
        "unexplained_internal_unmatched_boundary_edge_length": sum(
            float(edge["length"]) for edge in unexplained_internal_edges
        ),
        "longest_unexplained_internal_unmatched_boundary_edge": edge_summary(longest_unexplained),
        "longest_internal_unmatched_boundary_edge_near_candidate": longest_internal_near_candidate,
        "near_neighbor_candidate_count": len(near_candidates),
        "best_near_neighbor_boundary_edges": near_candidates,
        "same_line_partition_mismatch_count": len(same_line_partition_mismatches),
        "best_same_line_partition_mismatches": same_line_partition_mismatches,
    }


def near_boundary_candidates_for_internal_edges(
    internal_edges: list[dict[str, Any]],
    edges_by_plane: dict[BoundaryPlaneKey, list[dict[str, Any]]],
    prims: list[ParsedUsdPrim],
    limit: int,
) -> list[dict[str, Any]]:
    best_candidates = []
    for edge in internal_edges:
        candidate = best_near_boundary_candidate_for_edge(edge, edges_by_plane, prims)
        if candidate is not None:
            best_candidates.append(candidate)
    best_candidates.sort(key=near_candidate_sort_key)
    return best_candidates[:limit]


def best_near_boundary_candidate_for_edge(
    edge: dict[str, Any],
    edges_by_plane: dict[BoundaryPlaneKey, list[dict[str, Any]]],
    prims: list[ParsedUsdPrim],
) -> dict[str, Any] | None:
    candidates_by_identity: dict[tuple[int, int], dict[str, Any]] = {}
    for plane_key in edge["plane_keys"]:
        for candidate_edge in edges_by_plane.get(plane_key, []):
            if candidate_edge["prim_index"] == edge["prim_index"]:
                continue
            candidate_identity = boundary_edge_identity(candidate_edge)
            if candidate_identity in candidates_by_identity:
                continue
            candidate = near_boundary_candidate_summary(edge, candidate_edge, prims)
            if candidate is not None:
                candidates_by_identity[candidate_identity] = candidate

    if not candidates_by_identity:
        return None
    return min(candidates_by_identity.values(), key=near_candidate_sort_key)


def same_line_partition_mismatches_for_internal_edges(
    internal_edges: list[dict[str, Any]],
    edges_by_line: dict[BoundaryLineKey, list[dict[str, Any]]],
    prims: list[ParsedUsdPrim],
    limit: int,
) -> list[dict[str, Any]]:
    source_edges_by_line: dict[BoundaryLineKey, list[dict[str, Any]]] = defaultdict(list)
    for edge in internal_edges:
        line_key = boundary_edge_line_key(edge)
        if line_key is not None:
            source_edges_by_line[line_key].append(edge)

    mismatches = []
    for line_key, source_edges in source_edges_by_line.items():
        candidate_edges_by_prim: dict[int, list[dict[str, Any]]] = defaultdict(list)
        source_prim_index = int(source_edges[0]["prim_index"])
        for candidate_edge in edges_by_line.get(line_key, []):
            candidate_prim_index = int(candidate_edge["prim_index"])
            if candidate_prim_index == source_prim_index:
                continue
            candidate_edges_by_prim[candidate_prim_index].append(candidate_edge)

        for candidate_prim_index, candidate_edges in candidate_edges_by_prim.items():
            mismatch = same_line_partition_mismatch_summary(
                line_key,
                source_edges,
                candidate_edges,
                prims[candidate_prim_index],
            )
            if mismatch is not None:
                mismatches.append(mismatch)

    mismatches.sort(key=same_line_partition_mismatch_sort_key)
    return mismatches[:limit]


def same_line_partition_mismatch_summary(
    line_key: BoundaryLineKey,
    source_edges: list[dict[str, Any]],
    candidate_edges: list[dict[str, Any]],
    candidate_prim: ParsedUsdPrim,
) -> dict[str, Any] | None:
    varying_axis = varying_axis_for_line_key(line_key)
    if varying_axis is None:
        return None
    axis_index = AXES.index(varying_axis)
    source_intervals = merged_intervals(edge_interval(edge, axis_index) for edge in source_edges)
    candidate_intervals = merged_intervals(edge_interval(edge, axis_index) for edge in candidate_edges)
    source_length = interval_set_length(source_intervals)
    candidate_length = interval_set_length(candidate_intervals)
    overlap_intervals = interval_set_intersection(source_intervals, candidate_intervals)
    overlap_length = interval_set_length(overlap_intervals)
    if source_length <= BOUNDARY_BBOX_TOLERANCE or overlap_length <= BOUNDARY_BBOX_TOLERANCE:
        return None

    candidate_union = candidate_intervals
    source_union = source_intervals
    source_edges_overlapped = [
        edge
        for edge in source_edges
        if interval_overlap_length(edge_interval(edge, axis_index), candidate_union) > BOUNDARY_BBOX_TOLERANCE
    ]
    candidate_edges_overlapping = [
        edge
        for edge in candidate_edges
        if interval_overlap_length(edge_interval(edge, axis_index), source_union) > BOUNDARY_BBOX_TOLERANCE
    ]
    candidate_keys = {edge["key"] for edge in candidate_edges}
    exact_matched_source_edges = [edge for edge in source_edges_overlapped if edge["key"] in candidate_keys]
    exact_matched_length = sum(float(edge["length"]) for edge in exact_matched_source_edges)
    if exact_matched_length >= overlap_length - BOUNDARY_BBOX_TOLERANCE:
        return None

    overlap_bbox = interval_bounds(overlap_intervals)
    source_bbox = interval_bounds(source_intervals)
    candidate_bbox = interval_bounds(candidate_intervals)
    return {
        "candidate_prim_name": candidate_prim.name,
        "candidate_expr_id": candidate_prim.expr_id,
        "candidate_order": candidate_prim.order,
        "candidate_kind": candidate_prim.source_kind,
        "line_planes": [boundary_plane_key_detail(plane_key) for plane_key in line_key],
        "varying_axis": varying_axis,
        "source_interval": source_bbox,
        "candidate_interval": candidate_bbox,
        "overlap_interval": overlap_bbox,
        "source_line_length": source_length,
        "candidate_line_length": candidate_length,
        "overlap_length": overlap_length,
        "source_coverage_ratio": overlap_length / source_length,
        "candidate_overlap_ratio": overlap_length / candidate_length if candidate_length > 0.0 else None,
        "source_edge_count": len(source_edges),
        "candidate_edge_count": len(candidate_edges),
        "source_edges_overlapped_count": len(source_edges_overlapped),
        "candidate_edges_overlapping_source_count": len(candidate_edges_overlapping),
        "exact_overlapping_edge_match_count": len(exact_matched_source_edges),
        "exact_overlapping_edge_match_length": exact_matched_length,
        "source_partition_points_in_overlap": partition_points_in_interval(source_edges, axis_index, overlap_bbox),
        "candidate_partition_points_in_overlap": partition_points_in_interval(candidate_edges, axis_index, overlap_bbox),
    }


def varying_axis_for_line_key(line_key: BoundaryLineKey) -> str | None:
    fixed_axes = {axis for axis, _value in line_key}
    varying_axes = [axis for axis in AXES if axis not in fixed_axes]
    return varying_axes[0] if len(varying_axes) == 1 else None


def edge_interval(edge: dict[str, Any], axis_index: int) -> tuple[float, float]:
    low = min(float(edge["start"][axis_index]), float(edge["end"][axis_index]))
    high = max(float(edge["start"][axis_index]), float(edge["end"][axis_index]))
    return low, high


def merged_intervals(intervals: Any) -> list[tuple[float, float]]:
    normalized = sorted((float(low), float(high)) for low, high in intervals if high - low > BOUNDARY_BBOX_TOLERANCE)
    merged: list[tuple[float, float]] = []
    for low, high in normalized:
        if not merged or low > merged[-1][1] + BOUNDARY_BBOX_TOLERANCE:
            merged.append((low, high))
            continue
        merged[-1] = (merged[-1][0], max(merged[-1][1], high))
    return merged


def interval_set_intersection(
    left: list[tuple[float, float]],
    right: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    intersections = []
    left_index = 0
    right_index = 0
    while left_index < len(left) and right_index < len(right):
        low = max(left[left_index][0], right[right_index][0])
        high = min(left[left_index][1], right[right_index][1])
        if high - low > BOUNDARY_BBOX_TOLERANCE:
            intersections.append((low, high))
        if left[left_index][1] < right[right_index][1]:
            left_index += 1
        else:
            right_index += 1
    return intersections


def interval_set_length(intervals: list[tuple[float, float]]) -> float:
    return sum(high - low for low, high in intervals)


def interval_overlap_length(interval: tuple[float, float], intervals: list[tuple[float, float]]) -> float:
    low, high = interval
    return sum(max(0.0, min(high, other_high) - max(low, other_low)) for other_low, other_high in intervals)


def interval_bounds(intervals: list[tuple[float, float]]) -> list[float] | None:
    if not intervals:
        return None
    return [intervals[0][0], intervals[-1][1]]


def partition_points_in_interval(
    edges: list[dict[str, Any]],
    axis_index: int,
    interval: list[float] | None,
) -> list[float]:
    if interval is None:
        return []
    low, high = interval
    points = {low, high}
    for edge in edges:
        for endpoint in (float(edge["start"][axis_index]), float(edge["end"][axis_index])):
            if low - BOUNDARY_BBOX_TOLERANCE <= endpoint <= high + BOUNDARY_BBOX_TOLERANCE:
                points.add(endpoint)
    return sorted(points)


def same_line_partition_mismatch_sort_key(mismatch: dict[str, Any]) -> tuple[float, float, int, int, str]:
    return (
        -float(mismatch["source_coverage_ratio"]),
        -float(mismatch["overlap_length"]),
        -int(mismatch["source_edges_overlapped_count"]),
        int(mismatch["candidate_order"] or 0),
        str(mismatch["candidate_prim_name"]),
    )


def near_boundary_candidate_summary(
    edge: dict[str, Any],
    candidate_edge: dict[str, Any],
    prims: list[ParsedUsdPrim],
) -> dict[str, Any] | None:
    shared_plane_keys = sorted(set(edge["plane_keys"]) & set(candidate_edge["plane_keys"]))
    if not shared_plane_keys:
        return None
    candidate_prim = prims[int(candidate_edge["prim_index"])]
    endpoint_pair_distance = unordered_endpoint_pair_distance(edge, candidate_edge)
    midpoint_distance = distance(edge["midpoint"], candidate_edge["midpoint"])
    length_delta = abs(float(edge["length"]) - float(candidate_edge["length"]))
    return {
        "source_edge": edge_summary(edge),
        "candidate_prim_name": candidate_prim.name,
        "candidate_expr_id": candidate_prim.expr_id,
        "candidate_order": candidate_prim.order,
        "candidate_kind": candidate_prim.source_kind,
        "candidate_edge": edge_summary(candidate_edge),
        "shared_planes": [boundary_plane_key_detail(plane_key) for plane_key in shared_plane_keys],
        "endpoint_pair_distance": endpoint_pair_distance,
        "midpoint_distance": midpoint_distance,
        "length_delta": length_delta,
        "score": endpoint_pair_distance + midpoint_distance + length_delta,
    }


def unordered_endpoint_pair_distance(edge: dict[str, Any], candidate_edge: dict[str, Any]) -> float:
    same_direction = distance(edge["start"], candidate_edge["start"]) + distance(edge["end"], candidate_edge["end"])
    opposite_direction = distance(edge["start"], candidate_edge["end"]) + distance(edge["end"], candidate_edge["start"])
    return min(same_direction, opposite_direction)


def near_candidate_sort_key(candidate: dict[str, Any]) -> tuple[float, float, float, int, str, str]:
    return (
        float(candidate["midpoint_distance"]),
        float(candidate["endpoint_pair_distance"]),
        float(candidate["length_delta"]),
        int(candidate["candidate_order"] or 0),
        str(candidate["candidate_prim_name"]),
        format_boundary_edge(candidate.get("source_edge")),
    )


def compact_all_prims_metric(metrics: dict[str, Any]) -> dict[str, Any]:
    compacted = dict(metrics)
    compacted["boundary_adjacency"] = compact_boundary_adjacency(metrics["boundary_adjacency"])
    return compacted


def compact_boundary_adjacency(adjacency: dict[str, Any]) -> dict[str, Any]:
    compacted = dict(adjacency)
    compacted.pop("best_near_neighbor_boundary_edges", None)
    compacted.pop("longest_internal_unmatched_boundary_edge_near_candidate", None)
    compacted.pop("best_same_line_partition_mismatches", None)
    compacted.pop("near_neighbor_candidate_count", None)
    compacted.pop("same_line_partition_mismatch_count", None)
    compacted.pop("source_bound_supported_internal_unmatched_boundary_edge_refs", None)
    compacted.pop("sampled_domain_bound_internal_unmatched_boundary_edge_refs", None)
    compacted.pop("sampled_predicate_clip_internal_unmatched_boundary_edge_refs", None)
    return compacted


def boundary_edge_key(
    start: Point3,
    end: Point3,
) -> BoundaryEdgeKey:
    rounded = sorted((rounded_point(start), rounded_point(end)))
    return (rounded[0], rounded[1])


def rounded_point(point: Point3) -> Point3:
    return (
        round(point[0], BOUNDARY_EDGE_KEY_DECIMALS),
        round(point[1], BOUNDARY_EDGE_KEY_DECIMALS),
        round(point[2], BOUNDARY_EDGE_KEY_DECIMALS),
    )


def edge_midpoint_on_global_bbox(edge: dict[str, Any], global_bbox: dict[str, list[float]] | None) -> bool:
    if global_bbox is None:
        return False
    midpoint = edge["midpoint"]
    for axis_index in range(3):
        if global_bbox["span"][axis_index] <= BOUNDARY_BBOX_TOLERANCE:
            continue
        if abs(midpoint[axis_index] - global_bbox["min"][axis_index]) <= BOUNDARY_BBOX_TOLERANCE:
            return True
        if abs(midpoint[axis_index] - global_bbox["max"][axis_index]) <= BOUNDARY_BBOX_TOLERANCE:
            return True
    return False


def source_bound_support_for_internal_edges(
    edges: list[dict[str, Any]],
    bounds: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    supported_edges = []
    unexplained_edges = []
    supports_by_key: dict[tuple[str, str, float, str | None], dict[str, Any]] = {}
    for edge in edges:
        refs = strict_source_bound_refs_for_edge(edge, bounds)
        if not refs:
            unexplained_edges.append(edge)
            continue
        supported_edges.append(edge)
        for ref in refs:
            key = (str(ref["axis"]), str(ref["side"]), float(ref["bound"]), ref.get("bound_expr"))
            summary = supports_by_key.setdefault(
                key,
                {
                    "axis": ref["axis"],
                    "side": ref["side"],
                    "bound": ref["bound"],
                    "bound_expr": ref.get("bound_expr"),
                    "edge_count": 0,
                    "edge_length": 0.0,
                    "longest_edge": None,
                },
            )
            summary["edge_count"] += 1
            summary["edge_length"] += float(edge["length"])
            longest = summary["longest_edge"]
            if longest is None or float(edge["length"]) > float(longest["length"]):
                summary["longest_edge"] = edge_summary(edge)

    supports = sorted(
        supports_by_key.values(),
        key=lambda item: (-float(item["edge_length"]), str(item["axis"]), str(item["side"]), float(item["bound"])),
    )
    return {
        "supported_edges": supported_edges,
        "unexplained_edges": unexplained_edges,
        "supports": supports,
    }


def sampled_domain_bound_support_for_internal_edges(
    edges: list[dict[str, Any]],
    prim: ParsedUsdPrim,
    bounds: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    sampled_bounds = sampled_domain_bound_refs_for_prim(prim, bounds)
    supported_edges = []
    unexplained_edges = []
    supports_by_key: dict[tuple[str, str, float, float | None, str | None, str | None, str | None], dict[str, Any]] = {}
    for edge in edges:
        refs = sampled_domain_bound_refs_for_edge(edge, sampled_bounds)
        if not refs:
            unexplained_edges.append(edge)
            continue
        supported_edges.append(edge)
        for ref in refs:
            key = (
                str(ref["axis"]),
                str(ref["side"]),
                float(ref["sampled_value"]),
                ref.get("source_bound"),
                ref.get("source_bound_expr"),
                ref.get("support_kind"),
                ref.get("support_bound_expr"),
            )
            summary = supports_by_key.setdefault(
                key,
                {
                    "axis": ref["axis"],
                    "side": ref["side"],
                    "sampled_value": ref["sampled_value"],
                    "source_bound": ref.get("source_bound"),
                    "source_bound_expr": ref.get("source_bound_expr"),
                    "sample_offset_from_source_bound": ref.get("sample_offset_from_source_bound"),
                    "support_kind": ref.get("support_kind"),
                    "support_predicate": ref.get("support_predicate"),
                    "support_bound_expr": ref.get("support_bound_expr"),
                    "support_bound_identifiers": ref.get("support_bound_identifiers", []),
                    "edge_count": 0,
                    "edge_length": 0.0,
                    "longest_edge": None,
                },
            )
            summary["edge_count"] += 1
            summary["edge_length"] += float(edge["length"])
            longest = summary["longest_edge"]
            if longest is None or float(edge["length"]) > float(longest["length"]):
                summary["longest_edge"] = edge_summary(edge)

    supports = sorted(
        supports_by_key.values(),
        key=lambda item: (-float(item["edge_length"]), str(item["axis"]), str(item["side"])),
    )
    return {
        "supported_edges": supported_edges,
        "unexplained_edges": unexplained_edges,
        "supports": supports,
    }


def sampled_domain_bound_refs_for_prim(
    prim: ParsedUsdPrim,
    bounds: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    parsed_equation = parse_explicit_surface_equation(prim.latex)
    if prim.source_kind != "explicit_surface" or parsed_equation is None:
        return []
    explicit_axis, _expression = parsed_equation
    domain_axes = [axis for axis in AXES if axis != explicit_axis]
    used_indices = sorted({index for index in prim.face_vertex_indices if 0 <= index < len(prim.points)})
    if not used_indices:
        return []

    bound_proofs = parsed_sampled_domain_bound_proofs(prim.constraints, bounds)
    refs = []
    for axis in domain_axes:
        axis_proofs = bound_proofs.get(axis, {})
        axis_index = AXES.index(axis)
        values = sorted({round(float(prim.points[index][axis_index]), BOUNDARY_EDGE_KEY_DECIMALS) for index in used_indices})
        if len(values) < 2:
            continue
        side_specs = [("low", values[0], "min", "min_expr"), ("high", values[-1], "max", "max_expr")]
        for side, sampled_value, bound_key, expr_key in side_specs:
            proof = axis_proofs.get(side)
            if proof is None:
                continue
            source_bound = bounds.get(axis, {}).get(bound_key)
            if source_bound is not None and abs(float(source_bound) - sampled_value) <= SAMPLED_DOMAIN_BOUND_TOLERANCE:
                continue
            refs.append(
                {
                    "axis": axis,
                    "side": side,
                    "sampled_value": sampled_value,
                    "source_bound": float(source_bound) if source_bound is not None else None,
                    "source_bound_expr": bounds.get(axis, {}).get(expr_key),
                    "sample_offset_from_source_bound": (
                        abs(sampled_value - float(source_bound)) if source_bound is not None else None
                    ),
                    "support_kind": proof["kind"],
                    "support_predicate": proof.get("predicate"),
                    "support_bound_expr": proof.get("bound_expr"),
                    "support_bound_identifiers": proof.get("bound_identifiers", []),
                }
            )
    return refs


def parsed_sampled_domain_bound_proofs(
    constraints: str,
    bounds: dict[str, dict[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    proofs: dict[str, dict[str, dict[str, Any]]] = {}
    for axis, bound in bounds.items():
        if axis not in AXES:
            continue
        axis_proofs = proofs.setdefault(axis, {})
        for side, value_key, expr_key in (("low", "min", "min_expr"), ("high", "max", "max_expr")):
            if bound.get(value_key) is None:
                continue
            axis_proofs[side] = {
                "kind": "parsed_constant_bound",
                "axis": axis,
                "side": side,
                "bound": float(bound[value_key]),
                "bound_expr": bound.get(expr_key),
                "bound_identifiers": [],
            }

    for fragment in constraints.split(";"):
        normalized_fragment = normalize_constraint_fragment(fragment).strip()
        if not normalized_fragment:
            continue
        try:
            predicates = parse_predicates(normalized_fragment)
        except Exception:
            continue
        for predicate in predicates:
            for axis, (lower, upper) in predicate.variable_bounds().items():
                if axis not in AXES:
                    continue
                axis_proofs = proofs.setdefault(axis, {})
                if lower is not None:
                    axis_proofs.setdefault("low", parsed_predicate_bound_proof(axis, "low", lower, predicate.raw))
                if upper is not None:
                    axis_proofs.setdefault("high", parsed_predicate_bound_proof(axis, "high", upper, predicate.raw))
    return proofs


def parsed_predicate_bound_proof(
    axis: str,
    side: str,
    expression: LatexExpression,
    predicate: str,
) -> dict[str, Any]:
    return {
        "kind": "parsed_predicate_bound",
        "axis": axis,
        "side": side,
        "predicate": predicate,
        "bound_expr": expression.latex,
        "bound_identifiers": sorted(expression.identifiers),
    }


def sampled_domain_bound_refs_for_edge(
    edge: dict[str, Any],
    sampled_bounds: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    refs = []
    for ref in sampled_bounds:
        axis_index = AXES.index(ref["axis"])
        if edge_lies_on_axis_value(edge, axis_index, float(ref["sampled_value"])):
            refs.append(ref)
    return refs


def sampled_predicate_clip_support_for_internal_edges(
    edges: list[dict[str, Any]],
    prim: ParsedUsdPrim,
    bounds: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Classify internal unmatched boundary edges that lie on domain-axis extreme
    sample values where the explicit axis has a predicate bound depending on that
    domain axis, indirectly limiting the valid domain."""
    clip_refs = sampled_predicate_clip_refs_for_prim(prim, bounds)
    supported_edges: list[dict[str, Any]] = []
    unexplained_edges: list[dict[str, Any]] = []
    supports_by_key: dict[tuple[str, str, float, str | None, str | None], dict[str, Any]] = {}
    for edge in edges:
        matched = [ref for ref in clip_refs if edge_lies_on_axis_value(edge, AXES.index(ref["axis"]), float(ref["sampled_value"]))]
        if not matched:
            unexplained_edges.append(edge)
            continue
        supported_edges.append(edge)
        for ref in matched:
            key = (
                str(ref["axis"]),
                str(ref["side"]),
                float(ref["sampled_value"]),
                ref.get("explicit_axis"),
                ref.get("bound_expr"),
            )
            summary = supports_by_key.setdefault(
                key,
                {
                    "axis": ref["axis"],
                    "side": ref["side"],
                    "sampled_value": ref["sampled_value"],
                    "explicit_axis": ref.get("explicit_axis"),
                    "explicit_axis_side": ref.get("explicit_axis_side"),
                    "predicate": ref.get("predicate"),
                    "bound_expr": ref.get("bound_expr"),
                    "depends_on": ref.get("depends_on", []),
                    "edge_count": 0,
                    "edge_length": 0.0,
                },
            )
            summary["edge_count"] += 1
            summary["edge_length"] += float(edge["length"])

    supports = sorted(
        supports_by_key.values(),
        key=lambda item: (-float(item["edge_length"]), str(item["axis"]), str(item["side"])),
    )
    return {
        "supported_edges": supported_edges,
        "unexplained_edges": unexplained_edges,
        "supports": supports,
    }


def sampled_predicate_clip_refs_for_prim(
    prim: ParsedUsdPrim,
    bounds: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Identify domain axis extreme sample values where the domain is indirectly
    limited by a predicate on the explicit axis that depends on that domain axis."""
    parsed_equation = parse_explicit_surface_equation(prim.latex)
    if prim.source_kind != "explicit_surface" or parsed_equation is None:
        return []
    explicit_axis, _expression = parsed_equation
    domain_axes = [axis for axis in AXES if axis != explicit_axis]
    used_indices = sorted({index for index in prim.face_vertex_indices if 0 <= index < len(prim.points)})
    if not used_indices:
        return []

    existing_proofs = parsed_sampled_domain_bound_proofs(prim.constraints, bounds)
    explicit_axis_proofs = existing_proofs.get(explicit_axis, {})

    refs: list[dict[str, Any]] = []
    for axis in domain_axes:
        domain_axis_proofs = existing_proofs.get(axis, {})
        axis_index = AXES.index(axis)
        values = sorted({round(float(prim.points[index][axis_index]), BOUNDARY_EDGE_KEY_DECIMALS) for index in used_indices})
        if len(values) < 2:
            continue

        side_specs = [("low", values[0], "min"), ("high", values[-1], "max")]
        for side, sampled_value, bound_key in side_specs:
            if domain_axis_proofs.get(side) is not None:
                continue

            source_bound = bounds.get(axis, {}).get(bound_key)
            if source_bound is not None and abs(float(source_bound) - sampled_value) <= SAMPLED_DOMAIN_BOUND_TOLERANCE:
                continue

            for ea_side, ea_proof in explicit_axis_proofs.items():
                if ea_proof.get("kind") != "parsed_predicate_bound":
                    continue
                if axis not in ea_proof.get("bound_identifiers", []):
                    continue
                refs.append({
                    "axis": axis,
                    "side": side,
                    "sampled_value": sampled_value,
                    "explicit_axis": explicit_axis,
                    "explicit_axis_side": ea_side,
                    "predicate": ea_proof.get("predicate"),
                    "bound_expr": ea_proof.get("bound_expr"),
                    "depends_on": ea_proof.get("bound_identifiers", []),
                })
    return refs


def strict_source_bound_refs_for_edge(edge: dict[str, Any], bounds: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    refs = []
    for axis_index, axis in enumerate(AXES):
        bound = bounds.get(axis)
        if not bound:
            continue
        side_specs = [
            ("low", "min", "min_inclusive", "min_expr"),
            ("high", "max", "max_inclusive", "max_expr"),
        ]
        for side, value_key, inclusive_key, expr_key in side_specs:
            if bound.get(value_key) is None or bound.get(inclusive_key) is not False:
                continue
            value = float(bound[value_key])
            if edge_lies_on_axis_value(edge, axis_index, value):
                refs.append(
                    {
                        "axis": axis,
                        "side": side,
                        "bound": value,
                        "bound_expr": bound.get(expr_key),
                    }
                )
    return refs


def edge_lies_on_axis_value(edge: dict[str, Any], axis_index: int, value: float) -> bool:
    return (
        abs(float(edge["start"][axis_index]) - value) <= BOUNDARY_BBOX_TOLERANCE
        and abs(float(edge["end"][axis_index]) - value) <= BOUNDARY_BBOX_TOLERANCE
    )


def edge_summary(edge: dict[str, Any] | None) -> dict[str, Any] | None:
    if edge is None:
        return None
    return {
        "length": edge["length"],
        "start": edge["start"],
        "end": edge["end"],
        "midpoint": edge["midpoint"],
    }


def restriction_inset_for_bbox(
    bbox: dict[str, list[float]],
    bounds: dict[str, dict[str, Any]],
    epsilon: float = 1e-6,
) -> dict[str, Any]:
    positive_sides = []
    max_inset = 0.0
    max_strict_inset = 0.0
    total_inset = 0.0
    for axis_index, axis in enumerate(AXES):
        bound = bounds.get(axis)
        if not bound:
            continue
        restriction_span = None
        if bound.get("min") is not None and bound.get("max") is not None:
            restriction_span = float(bound["max"]) - float(bound["min"])
        side_specs = [
            ("low", "min", "min_inclusive", "min_expr", bbox["min"][axis_index], 1.0),
            ("high", "max", "max_inclusive", "max_expr", bbox["max"][axis_index], -1.0),
        ]
        for side, bound_key, inclusive_key, expr_key, bbox_edge, direction in side_specs:
            if bound.get(bound_key) is None:
                continue
            bound_value = float(bound[bound_key])
            inset = (float(bbox_edge) - bound_value) * direction
            if inset <= epsilon:
                continue
            inclusive = bool(bound.get(inclusive_key))
            normalized = inset / restriction_span if restriction_span and restriction_span > 0.0 else None
            positive_sides.append(
                {
                    "axis": axis,
                    "side": side,
                    "bound": bound_value,
                    "bound_expr": bound.get(expr_key),
                    "inclusive": inclusive,
                    "bbox_edge": float(bbox_edge),
                    "inset": inset,
                    "normalized_to_restriction_span": normalized,
                }
            )
            max_inset = max(max_inset, inset)
            total_inset += inset
            if not inclusive:
                max_strict_inset = max(max_strict_inset, inset)
    return {
        "max": max_inset,
        "max_strict": max_strict_inset,
        "total": total_inset,
        "score": (max_strict_inset * 10.0) + max_inset + total_inset,
        "positive_side_count": len(positive_sides),
        "strict_positive_side_count": sum(1 for side in positive_sides if not side["inclusive"]),
        "positive_sides": positive_sides,
    }


def restriction_bound_reachability(
    prim: ParsedUsdPrim,
    restriction_inset: dict[str, Any],
    bounds: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    sides = [reachability_for_inset_side(prim, side, bounds) for side in restriction_inset.get("positive_sides", [])]
    counts: dict[str, int] = {}
    for side in sides:
        classification = str(side["classification"])
        counts[classification] = counts.get(classification, 0) + 1
    return {
        "method": "constant or single-variable affine explicit-surface endpoint check excluding the compared bound",
        "side_count": len(sides),
        "classification_counts": counts,
        "equation_limited_side_count": counts.get("equation_limited_by_other_restrictions", 0),
        "sides": sides,
    }


def reachability_for_inset_side(
    prim: ParsedUsdPrim,
    side: dict[str, Any],
    bounds: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    result = {
        "axis": side["axis"],
        "side": side["side"],
        "bound": side["bound"],
        "bound_expr": side.get("bound_expr"),
        "classification": "unknown",
        "reason": "",
    }
    if prim.source_kind != "explicit_surface":
        result["reason"] = f"unsupported kind {prim.source_kind!r}"
        return result

    parsed = parse_explicit_surface_equation(prim.latex)
    if parsed is None:
        result["reason"] = "could not parse explicit surface equation"
        return result
    explicit_axis, expression = parsed
    result["explicit_axis"] = explicit_axis
    result["expression"] = expression.latex
    if explicit_axis != side["axis"]:
        result["reason"] = "inset axis is not the explicit equation axis"
        return result

    return classify_affine_reachability(result, expression, side, bounds)


def parse_explicit_surface_equation(latex: str) -> tuple[str, LatexExpression] | None:
    main, _restrictions = split_restrictions(latex)
    equals = find_top_level(main, "=")
    if equals < 0:
        return None
    lhs = main[:equals].strip()
    rhs = main[equals + 1 :].strip()
    lhs_axis = normalized_axis_identifier(lhs)
    rhs_axis = normalized_axis_identifier(rhs)
    try:
        if lhs_axis in AXES:
            return lhs_axis, LatexExpression.parse(rhs)
        if rhs_axis in AXES:
            return rhs_axis, LatexExpression.parse(lhs)
    except Exception:
        return None
    return None


def normalized_axis_identifier(text: str) -> str | None:
    if not IDENTIFIER_TOKEN_RE.fullmatch(text):
        return None
    try:
        identifier = normalize_identifier(text)
    except Exception:
        return None
    return identifier if identifier in AXES else None


def classify_affine_reachability(
    result: dict[str, Any],
    expression: LatexExpression,
    side: dict[str, Any],
    bounds: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    identifiers = sorted(expression.identifiers)
    target_side = "max" if side["side"] == "high" else "min"
    compared_bound = float(side["bound"])
    if len(identifiers) > 1:
        result["reason"] = f"expression depends on multiple variables: {', '.join(identifiers)}"
        return result

    if not identifiers:
        try:
            value = expression.eval(EvalContext(), {})
        except Exception as exc:
            result["reason"] = f"could not evaluate constant expression: {exc}"
            return result
        return finish_reachability_classification(result, target_side, compared_bound, value)

    variable = identifiers[0]
    affine = single_variable_affine_characteristics(expression, variable)
    if affine is None:
        result["reason"] = "expression is not single-variable affine by deterministic samples"
        return result
    intercept, slope = affine
    result["variable"] = variable
    result["affine_intercept"] = intercept
    result["affine_slope"] = slope

    if abs(slope) <= REACHABILITY_TOLERANCE:
        return finish_reachability_classification(result, target_side, compared_bound, intercept)

    optimizing_side = "max" if (target_side == "max") == (slope > 0.0) else "min"
    variable_bound = bounds.get(variable, {}).get(optimizing_side)
    if variable_bound is None:
        result["reason"] = f"no finite {variable} {optimizing_side} bound for affine endpoint check"
        return result

    variable_bound = float(variable_bound)
    reachable_extreme = expression.eval(EvalContext(), {variable: variable_bound})
    bound_info = bounds.get(variable, {})
    result["limiting_axis"] = variable
    result["limiting_side"] = optimizing_side
    result["limiting_bound"] = variable_bound
    result["limiting_bound_expr"] = bound_info.get(f"{optimizing_side}_expr")
    result["limiting_bound_inclusive"] = bound_info.get(f"{optimizing_side}_inclusive")
    return finish_reachability_classification(result, target_side, compared_bound, reachable_extreme)


def single_variable_affine_characteristics(expression: LatexExpression, variable: str) -> tuple[float, float] | None:
    try:
        f0 = expression.eval(EvalContext(), {variable: 0.0})
        f1 = expression.eval(EvalContext(), {variable: 1.0})
        f2 = expression.eval(EvalContext(), {variable: 2.0})
    except Exception:
        return None
    slope = f1 - f0
    if abs((f2 - f1) - slope) > REACHABILITY_TOLERANCE:
        return None
    return f0, slope


def finish_reachability_classification(
    result: dict[str, Any],
    target_side: str,
    compared_bound: float,
    reachable_extreme: float,
) -> dict[str, Any]:
    result["target_side"] = target_side
    result["reachable_extreme_without_compared_bound"] = reachable_extreme
    if target_side == "max":
        gap = compared_bound - reachable_extreme
        result["gap_to_compared_bound"] = gap
        if gap > REACHABILITY_TOLERANCE:
            result["classification"] = "equation_limited_by_other_restrictions"
            result["reason"] = "explicit equation maximum under the other finite restriction bound is below the compared bound"
        else:
            result["classification"] = "compared_bound_reachable_without_compared_restriction"
            result["reason"] = "explicit equation can reach or exceed the compared upper bound"
        return result

    gap = reachable_extreme - compared_bound
    result["gap_to_compared_bound"] = gap
    if gap > REACHABILITY_TOLERANCE:
        result["classification"] = "equation_limited_by_other_restrictions"
        result["reason"] = "explicit equation minimum under the other finite restriction bound is above the compared bound"
    else:
        result["classification"] = "compared_bound_reachable_without_compared_restriction"
        result["reason"] = "explicit equation can reach or go below the compared lower bound"
    return result


def restriction_inset_reachability_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for side in row.get("restriction_bound_reachability", {}).get("sides", []):
            classification = str(side["classification"])
            counts[classification] = counts.get(classification, 0) + 1
    return dict(sorted(counts.items()))


def suspicion_score(metrics: dict[str, Any], source_diagonal: float | None) -> float:
    overshoot = float(metrics["viewport_overshoot"]["max"])
    center_distance = metrics.get("center_distance_from_source_center")
    distance_excess = 0.0
    if center_distance is not None and source_diagonal is not None:
        distance_excess = max(0.0, float(center_distance) - (source_diagonal / 2.0))
    return (overshoot * 10.0) + distance_excess + float(metrics["global_span_contribution"]["max"])


def suspicion_sort_key(metrics: dict[str, Any]) -> tuple[float, int, str]:
    return (-float(metrics["suspicion_score"]), int(metrics["order"] or 0), str(metrics["prim_name"]))


def center_distance_sort_key(metrics: dict[str, Any]) -> tuple[float, int, str]:
    value = metrics.get("center_distance_from_source_center")
    distance_value = float(value) if value is not None else -1.0
    return (-distance_value, int(metrics["order"] or 0), str(metrics["prim_name"]))


def largest_span_sort_key(metrics: dict[str, Any]) -> tuple[float, int, str]:
    return (-float(metrics["largest_axis_span"]), int(metrics["order"] or 0), str(metrics["prim_name"]))


def restriction_inset_sort_key(metrics: dict[str, Any]) -> tuple[float, float, float, int, str]:
    inset = metrics["restriction_inset"]
    return (
        -float(inset["score"]),
        -float(inset["max_strict"]),
        -float(inset["max"]),
        int(metrics["order"] or 0),
        str(metrics["prim_name"]),
    )


def boundary_gap_sort_key(metrics: dict[str, Any]) -> tuple[float, float, int, str]:
    adjacency = metrics["boundary_adjacency"]
    longest = adjacency.get("longest_unexplained_internal_unmatched_boundary_edge") or {}
    return (
        -float(adjacency["unexplained_internal_unmatched_boundary_edge_length"]),
        -float(longest.get("length") or 0.0),
        int(metrics["order"] or 0),
        str(metrics["prim_name"]),
    )


def source_bound_supported_only_sort_key(metrics: dict[str, Any]) -> tuple[float, float, int, str]:
    adjacency = metrics["boundary_adjacency"]
    longest = adjacency.get("longest_internal_unmatched_boundary_edge") or {}
    return (
        -float(adjacency["source_bound_supported_internal_unmatched_boundary_edge_length"]),
        -float(longest.get("length") or 0.0),
        int(metrics["order"] or 0),
        str(metrics["prim_name"]),
    )


def sampled_domain_bound_sort_key(metrics: dict[str, Any]) -> tuple[float, float, int, str]:
    adjacency = metrics["boundary_adjacency"]
    return (
        -float(adjacency["sampled_domain_bound_internal_unmatched_boundary_edge_length"]),
        -float(adjacency["unexplained_internal_unmatched_boundary_edge_length"]),
        int(metrics["order"] or 0),
        str(metrics["prim_name"]),
    )


def sampled_predicate_clip_sort_key(metrics: dict[str, Any]) -> tuple[float, float, int, str]:
    adjacency = metrics["boundary_adjacency"]
    return (
        -float(adjacency["sampled_predicate_clip_internal_unmatched_boundary_edge_length"]),
        -float(adjacency["unexplained_internal_unmatched_boundary_edge_length"]),
        int(metrics["order"] or 0),
        str(metrics["prim_name"]),
    )


def write_diagnostics_json(path: Path, diagnostics: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(diagnostics, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_diagnostics_markdown(path: Path, diagnostics: dict[str, Any], limit: int = 20) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = markdown_for_diagnostics(diagnostics, limit=limit)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def markdown_for_diagnostics(diagnostics: dict[str, Any], limit: int = 20) -> list[str]:
    lines = [
        f"# {diagnostics.get('graph_hash') or 'USDA'} prim outlier diagnostics",
        "",
        "Deterministic diagnostic generated from the acceptance USDA currently served to the viewer.",
        "",
        "## Inputs",
        f"- USDA: `{diagnostics['usda_path']}`",
        f"- report: `{diagnostics.get('report_path') or 'none'}`",
        f"- prims parsed: {diagnostics['prim_count']}",
        f"- measured prims with finite points: {diagnostics['measured_prim_count']}",
        "",
        "## Bounding Boxes",
        f"- source viewport bbox: {format_bbox(diagnostics.get('source_viewport_bbox'))}",
        f"- exported global bbox: {format_bbox(diagnostics.get('global_bbox'))}",
        "",
        "## Strongest Culprit",
    ]
    strongest = diagnostics["top_suspicious"][0] if diagnostics["top_suspicious"] else None
    if strongest:
        lines.extend(
            [
                f"- prim: `{strongest['prim_name']}`",
                f"- source expression id/order/kind: `{strongest['expr_id']}` / `{strongest['order']}` / `{strongest['kind']}`",
                f"- bbox: {format_bbox(strongest['bbox'])}",
                f"- center: `{format_vector(strongest['center'])}`",
                f"- center distance from source viewport center: `{format_float(strongest['center_distance_from_source_center'])}`",
                f"- max viewport overshoot: `{format_float(strongest['viewport_overshoot']['max'])}`",
                f"- max global span reduction if removed: `{format_float(strongest['global_span_contribution']['max'])}`",
                f"- latex: `{markdown_escape(strongest['latex'])}`",
            ]
        )
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Restriction Inset Hypothesis",
            (
                "- parsed constant restriction bounds for "
                f"{diagnostics['constant_restriction_prim_count']} measured prims"
            ),
            (
                "- prims whose exported bbox stops short of at least one parsed bound: "
                f"{diagnostics['restriction_inset_count']}"
            ),
            f"- inset-side reachability classifications: `{format_reachability_counts(diagnostics['restriction_inset_reachability_counts'])}`",
            strongest_restriction_inset_summary(diagnostics),
            "",
            "## Boundary Gap Hypothesis",
            f"- exact boundary match rule: `{diagnostics['boundary_gap_rule']}`",
            f"- source-bound support rule: `{diagnostics.get('boundary_source_bound_support_rule', 'none')}`",
            f"- sampled-domain-bound support rule: `{diagnostics.get('boundary_sampled_domain_bound_rule', 'none')}`",
            f"- sampled-predicate-clip support rule: `{diagnostics.get('boundary_sampled_predicate_clip_rule', 'none')}`",
            f"- near-neighbor candidates enabled: `{diagnostics.get('boundary_near_candidate_enabled', False)}`",
            f"- near-neighbor candidate rule: `{diagnostics.get('boundary_near_candidate_rule', 'none')}`",
            f"- same-line partition mismatch rule: `{diagnostics.get('same_line_partition_mismatch_rule', 'none')}`",
            f"- boundary endpoint rounding decimals: `{diagnostics['boundary_edge_match_decimals']}`",
            f"- prims with internal unmatched boundary edges: `{diagnostics['boundary_gap_count']}`",
            f"- prims with unexplained internal unmatched boundary edges: `{diagnostics.get('unexplained_boundary_gap_count', 0)}`",
            (
                "- prims with sampled-domain-bound internal unmatched boundary edges: "
                f"`{diagnostics.get('sampled_domain_bound_boundary_gap_count', 0)}`"
            ),
            (
                "- prims with sampled-predicate-clip internal unmatched boundary edges: "
                f"`{diagnostics.get('sampled_predicate_clip_boundary_gap_count', 0)}`"
            ),
            (
                "- prims with only source-bound-supported internal unmatched boundary edges: "
                f"`{diagnostics.get('source_bound_supported_only_boundary_gap_count', 0)}`"
            ),
            (
                "- prims with same-line partition mismatches: "
                f"`{diagnostics.get('same_line_partition_mismatch_prim_count', 0)}`"
            ),
            strongest_boundary_gap_summary(diagnostics),
            strongest_sampled_domain_bound_boundary_gap_summary(diagnostics),
            strongest_sampled_predicate_clip_boundary_gap_summary(diagnostics),
            strongest_source_bound_supported_only_boundary_gap_summary(diagnostics),
            "",
            f"## Viewport Outliers ({diagnostics['viewport_outlier_count']})",
            markdown_table(
                diagnostics["viewport_outliers"][:limit],
                include_overshoot=True,
            ),
            "",
            f"## Top Restriction Insets ({min(limit, len(diagnostics['top_restriction_insets']))})",
            restriction_inset_table(diagnostics["top_restriction_insets"][:limit]),
            "",
            f"## Top Boundary Gaps ({min(limit, len(diagnostics['top_boundary_gaps']))})",
            boundary_gap_table(diagnostics["top_boundary_gaps"][:limit]),
            "",
            (
                "## Top Source-Bound-Supported Only Boundary Gaps "
                f"({min(limit, len(diagnostics.get('top_source_bound_supported_only_boundary_gaps', [])))})"
            ),
            boundary_gap_table(diagnostics.get("top_source_bound_supported_only_boundary_gaps", [])[:limit]),
            "",
            (
                "## Top Sampled-Domain-Bound Boundary Gaps "
                f"({min(limit, len(diagnostics.get('top_sampled_domain_bound_boundary_gaps', [])))})"
            ),
            boundary_gap_table(diagnostics.get("top_sampled_domain_bound_boundary_gaps", [])[:limit]),
            "",
            (
                "## Top Sampled-Predicate-Clip Boundary Gaps "
                f"({min(limit, len(diagnostics.get('top_sampled_predicate_clip_boundary_gaps', [])))})"
            ),
            boundary_gap_table(diagnostics.get("top_sampled_predicate_clip_boundary_gaps", [])[:limit]),
            "",
            f"## Top Suspicious ({min(limit, len(diagnostics['top_suspicious']))})",
            markdown_table(diagnostics["top_suspicious"][:limit], include_overshoot=True),
            "",
            f"## Top Center Distance ({min(limit, len(diagnostics['top_center_distance']))})",
            markdown_table(diagnostics["top_center_distance"][:limit], include_overshoot=False),
            "",
            f"## Top Largest Span ({min(limit, len(diagnostics['top_largest_span']))})",
            markdown_table(diagnostics["top_largest_span"][:limit], include_overshoot=False),
        ]
    )
    return lines


def strongest_restriction_inset_summary(diagnostics: dict[str, Any]) -> str:
    rows = diagnostics.get("top_restriction_insets") or []
    if not rows:
        return "- strongest restriction inset: none"
    strongest = rows[0]
    inset = strongest["restriction_inset"]
    return (
        "- strongest restriction inset: "
        f"`{strongest['prim_name']}` expr `{strongest['expr_id']}` order `{strongest['order']}`; "
        f"score `{format_float(inset['score'])}`, max strict inset `{format_float(inset['max_strict'])}`, "
        f"max inset `{format_float(inset['max'])}`; {format_restriction_inset(inset)}; "
        f"reachability: {format_restriction_bound_reachability(strongest.get('restriction_bound_reachability'))}"
    )


def strongest_boundary_gap_summary(diagnostics: dict[str, Any]) -> str:
    rows = diagnostics.get("top_boundary_gaps") or []
    if not rows:
        return "- strongest boundary gap signal: none"
    strongest = rows[0]
    adjacency = strongest["boundary_adjacency"]
    return (
        "- strongest boundary gap signal: "
        f"`{strongest['prim_name']}` expr `{strongest['expr_id']}` order `{strongest['order']}`; "
        f"unexplained internal length `{format_float(adjacency['unexplained_internal_unmatched_boundary_edge_length'])}`, "
        f"unexplained edges `{adjacency['unexplained_internal_unmatched_boundary_edge_count']}`, "
        f"sampled-domain-bound length "
        f"`{format_float(adjacency['sampled_domain_bound_internal_unmatched_boundary_edge_length'])}`, "
        f"sampled-domain-bound edges `{adjacency['sampled_domain_bound_internal_unmatched_boundary_edge_count']}`, "
        f"sampled-predicate-clip length "
        f"`{format_float(adjacency.get('sampled_predicate_clip_internal_unmatched_boundary_edge_length', 0))}`, "
        f"sampled-predicate-clip edges `{adjacency.get('sampled_predicate_clip_internal_unmatched_boundary_edge_count', 0)}`, "
        f"source-bound-supported length "
        f"`{format_float(adjacency['source_bound_supported_internal_unmatched_boundary_edge_length'])}`, "
        f"source-bound-supported edges `{adjacency['source_bound_supported_internal_unmatched_boundary_edge_count']}`, "
        f"internal unmatched length `{format_float(adjacency['internal_unmatched_boundary_edge_length'])}`, "
        f"internal unmatched edges `{adjacency['internal_unmatched_boundary_edge_count']}`, "
        f"longest unexplained edge "
        f"`{format_boundary_edge(adjacency['longest_unexplained_internal_unmatched_boundary_edge'])}`, "
        f"source-bound support `{format_source_bound_supports(adjacency)}`, "
        f"sampled-domain-bound support `{format_sampled_domain_bound_supports(adjacency)}`, "
        f"longest-unexplained-edge candidate "
        f"`{format_near_boundary_candidate(adjacency.get('longest_internal_unmatched_boundary_edge_near_candidate'))}`, "
        f"nearest candidate `{format_near_boundary_candidate(first_near_boundary_candidate(adjacency))}`, "
        f"same-line partition `{format_same_line_partition_mismatch(first_same_line_partition_mismatch(adjacency))}`"
    )


def strongest_sampled_domain_bound_boundary_gap_summary(diagnostics: dict[str, Any]) -> str:
    rows = diagnostics.get("top_sampled_domain_bound_boundary_gaps") or []
    if not rows:
        return "- strongest sampled-domain-bound boundary signal: none"
    strongest = rows[0]
    adjacency = strongest["boundary_adjacency"]
    return (
        "- strongest sampled-domain-bound boundary signal: "
        f"`{strongest['prim_name']}` expr `{strongest['expr_id']}` order `{strongest['order']}`; "
        f"sampled-domain-bound length "
        f"`{format_float(adjacency['sampled_domain_bound_internal_unmatched_boundary_edge_length'])}`, "
        f"sampled-domain-bound edges `{adjacency['sampled_domain_bound_internal_unmatched_boundary_edge_count']}`, "
        f"unexplained length `{format_float(adjacency['unexplained_internal_unmatched_boundary_edge_length'])}`, "
        f"sampled-domain-bound support `{format_sampled_domain_bound_supports(adjacency)}`"
    )


def strongest_sampled_predicate_clip_boundary_gap_summary(diagnostics: dict[str, Any]) -> str:
    rows = diagnostics.get("top_sampled_predicate_clip_boundary_gaps") or []
    if not rows:
        return "- strongest sampled-predicate-clip boundary signal: none"
    strongest = rows[0]
    adjacency = strongest["boundary_adjacency"]
    return (
        "- strongest sampled-predicate-clip boundary signal: "
        f"`{strongest['prim_name']}` expr `{strongest['expr_id']}` order `{strongest['order']}`; "
        f"sampled-predicate-clip length "
        f"`{format_float(adjacency['sampled_predicate_clip_internal_unmatched_boundary_edge_length'])}`, "
        f"sampled-predicate-clip edges `{adjacency['sampled_predicate_clip_internal_unmatched_boundary_edge_count']}`, "
        f"unexplained length `{format_float(adjacency['unexplained_internal_unmatched_boundary_edge_length'])}`, "
        f"sampled-predicate-clip support `{format_sampled_predicate_clip_supports(adjacency)}`"
    )


def strongest_source_bound_supported_only_boundary_gap_summary(diagnostics: dict[str, Any]) -> str:
    rows = diagnostics.get("top_source_bound_supported_only_boundary_gaps") or []
    if not rows:
        return "- strongest source-bound-supported-only boundary signal: none"
    strongest = rows[0]
    adjacency = strongest["boundary_adjacency"]
    return (
        "- strongest source-bound-supported-only boundary signal: "
        f"`{strongest['prim_name']}` expr `{strongest['expr_id']}` order `{strongest['order']}`; "
        f"source-bound-supported length "
        f"`{format_float(adjacency['source_bound_supported_internal_unmatched_boundary_edge_length'])}`, "
        f"source-bound-supported edges `{adjacency['source_bound_supported_internal_unmatched_boundary_edge_count']}`, "
        f"unexplained length `{format_float(adjacency['unexplained_internal_unmatched_boundary_edge_length'])}`, "
        f"source-bound support `{format_source_bound_supports(adjacency)}`, "
        f"sampled-domain-bound support `{format_sampled_domain_bound_supports(adjacency)}`"
    )


def markdown_table(rows: list[dict[str, Any]], include_overshoot: bool) -> str:
    if not rows:
        return "none"
    headers = [
        "rank",
        "prim",
        "expr",
        "order",
        "kind",
        "score",
        "center_dist",
        "span",
        "bbox_min",
        "bbox_max",
    ]
    if include_overshoot:
        headers.append("overshoot")
    headers.append("latex")
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for index, row in enumerate(rows, start=1):
        values = [
            str(index),
            f"`{row['prim_name']}`",
            f"`{row['expr_id']}`",
            f"`{row['order']}`",
            f"`{row['kind']}`",
            f"`{format_float(row['suspicion_score'])}`",
            f"`{format_float(row['center_distance_from_source_center'])}`",
            f"`{format_vector(row['bbox']['span'])}`",
            f"`{format_vector(row['bbox']['min'])}`",
            f"`{format_vector(row['bbox']['max'])}`",
        ]
        if include_overshoot:
            values.append(f"`{format_overshoot(row['viewport_overshoot'])}`")
        values.append(f"`{markdown_escape(row['latex'])}`")
        lines.append("| " + " | ".join(markdown_escape(value) for value in values) + " |")
    return "\n".join(lines)


def restriction_inset_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "none"
    headers = [
        "rank",
        "prim",
        "expr",
        "order",
        "kind",
        "score",
        "max_strict",
        "max_inset",
        "insets",
        "reachability",
        "bounds",
        "bbox_min",
        "bbox_max",
        "latex",
    ]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for index, row in enumerate(rows, start=1):
        inset = row["restriction_inset"]
        values = [
            str(index),
            f"`{row['prim_name']}`",
            f"`{row['expr_id']}`",
            f"`{row['order']}`",
            f"`{row['kind']}`",
            f"`{format_float(inset['score'])}`",
            f"`{format_float(inset['max_strict'])}`",
            f"`{format_float(inset['max'])}`",
            f"`{format_restriction_inset(inset)}`",
            f"`{format_restriction_bound_reachability(row.get('restriction_bound_reachability'))}`",
            f"`{format_constant_bounds(row['constant_restriction_bounds'])}`",
            f"`{format_vector(row['bbox']['min'])}`",
            f"`{format_vector(row['bbox']['max'])}`",
            f"`{markdown_escape(row['latex'])}`",
        ]
        lines.append("| " + " | ".join(markdown_escape(value) for value in values) + " |")
    return "\n".join(lines)


def boundary_gap_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "none"
    headers = [
        "rank",
        "prim",
        "expr",
        "order",
        "kind",
        "unexplained_len",
        "unexplained_edges",
        "source_bound_len",
        "source_bound_edges",
        "sampled_domain_len",
        "sampled_domain_edges",
        "predicate_clip_len",
        "predicate_clip_edges",
        "internal_unmatched_len",
        "internal_unmatched_edges",
        "source_bound_support",
        "sampled_domain_support",
        "predicate_clip_support",
        "longest_unexplained_edge",
        "longest_unexplained_edge_candidate",
        "nearest_candidate",
        "same_line_partition",
        "unmatched_len",
        "exact_matched_edges",
        "bbox_min",
        "bbox_max",
        "latex",
    ]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for index, row in enumerate(rows, start=1):
        adjacency = row["boundary_adjacency"]
        values = [
            str(index),
            f"`{row['prim_name']}`",
            f"`{row['expr_id']}`",
            f"`{row['order']}`",
            f"`{row['kind']}`",
            f"`{format_float(adjacency['unexplained_internal_unmatched_boundary_edge_length'])}`",
            f"`{adjacency['unexplained_internal_unmatched_boundary_edge_count']}`",
            f"`{format_float(adjacency['source_bound_supported_internal_unmatched_boundary_edge_length'])}`",
            f"`{adjacency['source_bound_supported_internal_unmatched_boundary_edge_count']}`",
            f"`{format_float(adjacency['sampled_domain_bound_internal_unmatched_boundary_edge_length'])}`",
            f"`{adjacency['sampled_domain_bound_internal_unmatched_boundary_edge_count']}`",
            f"`{format_float(adjacency.get('sampled_predicate_clip_internal_unmatched_boundary_edge_length', 0))}`",
            f"`{adjacency.get('sampled_predicate_clip_internal_unmatched_boundary_edge_count', 0)}`",
            f"`{format_float(adjacency['internal_unmatched_boundary_edge_length'])}`",
            f"`{adjacency['internal_unmatched_boundary_edge_count']}`",
            f"`{format_source_bound_supports(adjacency)}`",
            f"`{format_sampled_domain_bound_supports(adjacency)}`",
            f"`{format_sampled_predicate_clip_supports(adjacency)}`",
            f"`{format_boundary_edge(adjacency['longest_unexplained_internal_unmatched_boundary_edge'])}`",
            f"`{format_near_boundary_candidate(adjacency.get('longest_internal_unmatched_boundary_edge_near_candidate'))}`",
            f"`{format_near_boundary_candidate(first_near_boundary_candidate(adjacency))}`",
            f"`{format_same_line_partition_mismatch(first_same_line_partition_mismatch(adjacency))}`",
            f"`{format_float(adjacency['unmatched_boundary_edge_length'])}`",
            f"`{adjacency['exact_matched_boundary_edge_count']}`",
            f"`{format_vector(row['bbox']['min'])}`",
            f"`{format_vector(row['bbox']['max'])}`",
            f"`{markdown_escape(row['latex'])}`",
        ]
        lines.append("| " + " | ".join(markdown_escape(value) for value in values) + " |")
    return "\n".join(lines)


def format_bbox(bbox: dict[str, list[float]] | None) -> str:
    if bbox is None:
        return "`none`"
    return (
        f"min `{format_vector(bbox['min'])}`, "
        f"max `{format_vector(bbox['max'])}`, "
        f"span `{format_vector(bbox['span'])}`"
    )


def format_vector(values: list[float] | None) -> str:
    if values is None:
        return "none"
    return ", ".join(format_float(value) for value in values)


def format_float(value: object) -> str:
    if value is None:
        return "none"
    numeric = float(value)
    if abs(numeric) < 5e-13:
        numeric = 0.0
    return f"{numeric:.9g}"


def format_overshoot(overshoot: dict[str, Any]) -> str:
    axes = overshoot.get("outside_axes")
    if not axes:
        return "none"
    parts = []
    for axis in axes:
        parts.append(
            f"{axis['axis']}:low={format_float(axis['low_overshoot'])},high={format_float(axis['high_overshoot'])}"
        )
    return "; ".join(parts)


def format_constant_bounds(bounds: dict[str, dict[str, Any]]) -> str:
    if not bounds:
        return "none"
    parts = []
    for axis in AXES:
        bound = bounds.get(axis)
        if not bound:
            continue
        low = format_bound_side(bound, "min")
        high = format_bound_side(bound, "max")
        parts.append(f"{axis}:{low}..{high}")
    return "; ".join(parts)


def format_bound_side(bound: dict[str, Any], side: str) -> str:
    value = bound.get(side)
    if value is None:
        return "none"
    inclusive = bound.get(f"{side}_inclusive")
    bracket = "inclusive" if inclusive else "strict"
    return f"{format_float(value)} {bracket}"


def format_restriction_inset(inset: dict[str, Any]) -> str:
    sides = inset.get("positive_sides")
    if not sides:
        return "none"
    parts = []
    for side in sides:
        strictness = "inclusive" if side["inclusive"] else "strict"
        parts.append(
            f"{side['axis']}:{side['side']} {strictness} bound={format_float(side['bound'])} "
            f"bbox={format_float(side['bbox_edge'])} inset={format_float(side['inset'])}"
        )
    return "; ".join(parts)


def format_reachability_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return "; ".join(f"{key}={value}" for key, value in counts.items())


def format_restriction_bound_reachability(reachability: dict[str, Any] | None) -> str:
    if not reachability or not reachability.get("sides"):
        return "none"
    parts = []
    for side in reachability["sides"]:
        details = [
            f"{side['axis']}:{side['side']} {side['classification']}",
        ]
        if side.get("reachable_extreme_without_compared_bound") is not None:
            details.append(f"reachable_extreme={format_float(side['reachable_extreme_without_compared_bound'])}")
        if side.get("gap_to_compared_bound") is not None:
            details.append(f"gap={format_float(side['gap_to_compared_bound'])}")
        if side.get("limiting_axis") is not None:
            details.append(
                f"limited_by={side['limiting_axis']}:{side['limiting_side']}={format_float(side['limiting_bound'])}"
            )
        parts.append(" ".join(details))
    return "; ".join(parts)


def format_source_bound_supports(adjacency: dict[str, Any]) -> str:
    refs = adjacency.get("source_bound_supported_internal_unmatched_boundary_edge_refs") or []
    if not refs:
        return "none"
    parts = []
    for ref in refs:
        parts.append(
            f"{ref['axis']}:{ref['side']} strict bound={format_float(ref['bound'])} "
            f"edges={ref['edge_count']} len={format_float(ref['edge_length'])}"
        )
    return "; ".join(parts)


def format_sampled_domain_bound_supports(adjacency: dict[str, Any]) -> str:
    refs = adjacency.get("sampled_domain_bound_internal_unmatched_boundary_edge_refs") or []
    if not refs:
        return "none"
    parts = []
    for ref in refs:
        source_bound = ref.get("source_bound")
        source = format_sampled_domain_bound_proof(ref)
        if source_bound is not None:
            source = (
                f"source_bound={format_float(source_bound)} "
                f"offset={format_float(ref.get('sample_offset_from_source_bound'))} "
                f"{source}"
            )
        parts.append(
            f"{ref['axis']}:{ref['side']} sample={format_float(ref['sampled_value'])} "
            f"{source} edges={ref['edge_count']} len={format_float(ref['edge_length'])}"
        )
    return "; ".join(parts)


def format_sampled_domain_bound_proof(ref: dict[str, Any]) -> str:
    kind = ref.get("support_kind")
    if kind == "parsed_constant_bound":
        return "proof=parsed_constant_bound"
    if kind == "parsed_predicate_bound":
        expr = ref.get("support_bound_expr") or "unknown"
        identifiers = ref.get("support_bound_identifiers") or []
        depends = ",".join(str(identifier) for identifier in identifiers) if identifiers else "constant"
        return f"proof=parsed_predicate_bound expr={expr} depends={depends}"
    return "proof=unknown"


def format_sampled_predicate_clip_supports(adjacency: dict[str, Any]) -> str:
    refs = adjacency.get("sampled_predicate_clip_internal_unmatched_boundary_edge_refs") or []
    if not refs:
        return "none"
    parts = []
    for ref in refs:
        depends = ",".join(str(d) for d in ref.get("depends_on", [])) if ref.get("depends_on") else "none"
        parts.append(
            f"{ref['axis']}:{ref['side']} sample={format_float(ref['sampled_value'])} "
            f"explicit={ref.get('explicit_axis')} "
            f"expr={ref.get('bound_expr') or 'unknown'} depends={depends} "
            f"edges={ref['edge_count']} len={format_float(ref['edge_length'])}"
        )
    return "; ".join(parts)


def format_boundary_edge(edge: dict[str, Any] | None) -> str:
    if not edge:
        return "none"
    return (
        f"len={format_float(edge['length'])} "
        f"mid={format_vector(edge['midpoint'])} "
        f"start={format_vector(edge['start'])} "
        f"end={format_vector(edge['end'])}"
    )


def first_near_boundary_candidate(adjacency: dict[str, Any]) -> dict[str, Any] | None:
    candidates = adjacency.get("best_near_neighbor_boundary_edges") or []
    return candidates[0] if candidates else None


def first_same_line_partition_mismatch(adjacency: dict[str, Any]) -> dict[str, Any] | None:
    mismatches = adjacency.get("best_same_line_partition_mismatches") or []
    return mismatches[0] if mismatches else None


def format_near_boundary_candidate(candidate: dict[str, Any] | None) -> str:
    if not candidate:
        return "none"
    return (
        f"{candidate['candidate_prim_name']} expr {candidate['candidate_expr_id']} "
        f"planes={format_shared_planes(candidate.get('shared_planes') or [])} "
        f"mid_gap={format_float(candidate['midpoint_distance'])} "
        f"endpoint_gap={format_float(candidate['endpoint_pair_distance'])} "
        f"len_delta={format_float(candidate['length_delta'])} "
        f"source_mid={format_vector(candidate['source_edge']['midpoint'])} "
        f"candidate_mid={format_vector(candidate['candidate_edge']['midpoint'])}"
    )


def format_same_line_partition_mismatch(mismatch: dict[str, Any] | None) -> str:
    if not mismatch:
        return "none"
    return (
        f"{mismatch['candidate_prim_name']} expr {mismatch['candidate_expr_id']} "
        f"line={format_shared_planes(mismatch.get('line_planes') or [])} "
        f"var={mismatch['varying_axis']} "
        f"source_interval={format_interval(mismatch.get('source_interval'))} "
        f"candidate_interval={format_interval(mismatch.get('candidate_interval'))} "
        f"overlap={format_interval(mismatch.get('overlap_interval'))} "
        f"overlap_len={format_float(mismatch['overlap_length'])} "
        f"source_coverage={format_float(mismatch['source_coverage_ratio'])} "
        f"source_segments={mismatch['source_edges_overlapped_count']} "
        f"candidate_segments={mismatch['candidate_edges_overlapping_source_count']} "
        f"exact_matches={mismatch['exact_overlapping_edge_match_count']} "
        f"source_partition={format_partition_points(mismatch.get('source_partition_points_in_overlap') or [])} "
        f"candidate_partition={format_partition_points(mismatch.get('candidate_partition_points_in_overlap') or [])}"
    )


def format_interval(values: list[float] | None) -> str:
    if not values:
        return "none"
    return f"{format_float(values[0])}..{format_float(values[1])}"


def format_partition_points(values: list[float]) -> str:
    if not values:
        return "none"
    return "[" + ", ".join(format_float(value) for value in values) + "]"


def format_shared_planes(planes: list[dict[str, Any]]) -> str:
    if not planes:
        return "none"
    return ",".join(f"{plane['axis']}={format_float(plane['value'])}" for plane in planes)


def markdown_escape(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rank suspicious exported USDA prims by deterministic bbox metrics")
    parser.add_argument("usda", help="Input USDA artifact")
    parser.add_argument("--report", help="Optional acceptance report JSON for source viewport bounds")
    parser.add_argument("--out", required=True, help="Output Markdown diagnostics path")
    parser.add_argument("--json-out", help="Optional output JSON diagnostics path")
    parser.add_argument("--limit", type=int, default=20, help="Rows per Markdown ranking table")
    parser.add_argument(
        "--boundary-near-candidates",
        action="store_true",
        help="Include nearest same-plane boundary-edge candidates for internal unmatched boundary edges",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    diagnostics = build_prim_diagnostics(
        Path(args.usda),
        report_path=Path(args.report) if args.report else None,
        limit=args.limit,
        include_boundary_near_candidates=args.boundary_near_candidates,
    )
    write_diagnostics_markdown(Path(args.out), diagnostics, limit=args.limit)
    if args.json_out:
        write_diagnostics_json(Path(args.json_out), diagnostics)
    print(
        json.dumps(
            {
                key: diagnostics[key]
                for key in ("prim_count", "viewport_outlier_count", "restriction_inset_count", "boundary_gap_count")
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
