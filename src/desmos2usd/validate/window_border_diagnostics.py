from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from desmos2usd.validate.prim_diagnostics import (
    AXES,
    ParsedUsdPrim,
    bbox_for_points,
    format_bbox,
    format_float,
    format_vector,
    load_report,
    markdown_escape,
    parse_constant_restriction_bounds,
    parse_usda_prims,
    source_viewport_bbox_from_report,
)

DEFAULT_TARGET_EXPR_IDS = ("3", "10", "13", "46", "79", "80", "81", "294", "298", "312", "323")
DEFAULT_BORDER_PLANES = (("y", -20.0), ("y", 20.0), ("y", -18.0), ("y", 18.0))
ROUND_DIGITS = 6


@dataclass(frozen=True)
class AxisAlignedFace:
    prim_name: str
    expr_id: str
    order: int | None
    kind: str
    latex: str
    face_index: int
    plane_axis: str
    plane_value: float
    u_axis: str
    v_axis: str
    u_min: float
    u_max: float
    v_min: float
    v_max: float
    area: float

    @property
    def plane_key(self) -> tuple[str, float]:
        return (self.plane_axis, rounded(self.plane_value))

    @property
    def signature(self) -> tuple[Any, ...]:
        return (
            self.plane_axis,
            rounded(self.plane_value),
            self.u_axis,
            rounded(self.u_min),
            rounded(self.u_max),
            self.v_axis,
            rounded(self.v_min),
            rounded(self.v_max),
        )


def build_window_border_diagnostics(
    usda_path: Path,
    report_path: Path | None = None,
    target_expr_ids: tuple[str, ...] = DEFAULT_TARGET_EXPR_IDS,
    border_planes: tuple[tuple[str, float], ...] = DEFAULT_BORDER_PLANES,
    limit: int = 30,
    epsilon: float = 1e-6,
) -> dict[str, Any]:
    prims = parse_usda_prims(usda_path)
    report = load_report(report_path)
    source_viewport_bbox = source_viewport_bbox_from_report(report)
    target_expr_id_set = set(target_expr_ids)
    border_plane_keys = {(axis, rounded(value)) for axis, value in border_planes}
    prim_by_name = {prim.name: prim for prim in prims}
    target_prims = [prim for prim in prims if prim.expr_id in target_expr_id_set]
    faces = [face for prim in prims for face in axis_aligned_faces_for_prim(prim, epsilon=epsilon)]
    faces_by_plane: dict[tuple[str, float], list[AxisAlignedFace]] = defaultdict(list)
    area_by_prim_plane: dict[tuple[str, tuple[str, float]], float] = defaultdict(float)
    for face in faces:
        faces_by_plane[face.plane_key].append(face)
        area_by_prim_plane[(face.prim_name, face.plane_key)] += face.area

    overlap_pairs = aggregate_target_overlap_pairs(
        faces_by_plane=faces_by_plane,
        target_expr_ids=target_expr_id_set,
        border_plane_keys=border_plane_keys,
        area_by_prim_plane=area_by_prim_plane,
        epsilon=epsilon,
    )
    overlap_pairs.sort(key=overlap_sort_key)

    full_coverage_pairs = [
        pair
        for pair in overlap_pairs
        if pair["coverage_of_prim_a_on_plane"] >= 1.0 - 1e-5
        and pair["coverage_of_prim_b_on_plane"] >= 1.0 - 1e-5
    ]
    exact_duplicate_full_pairs = [pair for pair in full_coverage_pairs if pair["duplicate_face_count"] > 0]

    target_summaries = [
        target_prim_summary(
            prim,
            faces,
            area_by_prim_plane,
            overlap_pairs,
            border_plane_keys,
            source_viewport_bbox,
            epsilon=epsilon,
        )
        for prim in target_prims
    ]
    target_summaries.sort(key=lambda item: (int(item["order"] or 0), str(item["prim_name"])))

    yz_projections = yz_side_view_projections(target_summaries, source_viewport_bbox)

    view_metadata = view_metadata_from_report(report)
    frozen_view_proj = frozen_view_projections(target_summaries, view_metadata)

    viewport_clipped_target_prims = [
        {
            "prim_name": summary["prim_name"],
            "expr_id": summary["expr_id"],
            "order": summary["order"],
            "axes": [axis["axis"] for axis in summary["viewport_clipped_unbounded_axes"]],
        }
        for summary in target_summaries
        if summary["viewport_clipped_unbounded_axes"]
    ]

    overlapping_target_expr_ids = {
        expr_id
        for pair in overlap_pairs
        for expr_id in (pair["prim_a"]["expr_id"], pair["prim_b"]["expr_id"])
        if expr_id in target_expr_id_set
    }
    target_expr_ids_without_overlap = [
        summary["expr_id"] for summary in target_summaries if summary["expr_id"] not in overlapping_target_expr_ids
    ]
    viewport_outlier_correlation = build_viewport_outlier_correlation(
        report,
        target_summaries,
        target_expr_id_set,
    )

    return {
        "usda_path": str(usda_path),
        "report_path": str(report_path) if report_path else None,
        "graph_hash": report.get("graph_hash") if isinstance(report, dict) else None,
        "source_viewport_bbox": source_viewport_bbox,
        "target_expr_ids": list(target_expr_ids),
        "border_planes": [{"axis": axis, "value": value} for axis, value in border_planes],
        "prim_count": len(prims),
        "target_prim_count": len(target_prims),
        "axis_aligned_face_count": len(faces),
        "border_axis_aligned_face_count": sum(1 for face in faces if face.plane_key in border_plane_keys),
        "overlap_rule": (
            "axis-aligned mesh faces on selected border planes are projected to 2D rectangles; "
            "pairs are reported when a target expr shares positive projected area with any other prim"
        ),
        "coplanar_overlap_pair_count": len(overlap_pairs),
        "full_coverage_pair_count": len(full_coverage_pairs),
        "exact_duplicate_full_pair_count": len(exact_duplicate_full_pairs),
        "strongest_full_coverage_pairs": full_coverage_pairs[:limit],
        "strongest_exact_duplicate_full_pairs": exact_duplicate_full_pairs[:limit],
        "top_coplanar_overlap_pairs": overlap_pairs[:limit],
        "target_prims": target_summaries,
        "viewport_clipped_unbounded_target_prim_count": len(viewport_clipped_target_prims),
        "viewport_clipped_unbounded_target_prims": viewport_clipped_target_prims,
        "target_expr_ids_without_coplanar_face_overlap": target_expr_ids_without_overlap,
        "viewport_outlier_correlation": viewport_outlier_correlation,
        "frozen_view_projections": frozen_view_proj,
        "yz_side_view_projections": yz_projections,
        "non_target_prim_count": len(prims) - len(target_prims),
        "all_overlap_pairs": overlap_pairs,
        "all_target_prim_names": [prim.name for prim in target_prims],
        "all_prim_names": sorted(prim_by_name),
    }


def axis_aligned_faces_for_prim(prim: ParsedUsdPrim, epsilon: float = 1e-6) -> list[AxisAlignedFace]:
    faces: list[AxisAlignedFace] = []
    offset = 0
    for face_index, count in enumerate(prim.face_vertex_counts):
        indices = prim.face_vertex_indices[offset : offset + count]
        offset += count
        if len(indices) < 3 or any(index < 0 or index >= len(prim.points) for index in indices):
            continue
        points = [prim.points[index] for index in indices]
        face = axis_aligned_face_from_points(prim, face_index, points, epsilon=epsilon)
        if face is not None:
            faces.append(face)
    return faces


def axis_aligned_face_from_points(
    prim: ParsedUsdPrim,
    face_index: int,
    points: list[tuple[float, float, float]],
    epsilon: float,
) -> AxisAlignedFace | None:
    spans = []
    for axis_index in range(3):
        values = [point[axis_index] for point in points]
        spans.append(max(values) - min(values))
    constant_axes = [axis_index for axis_index, span in enumerate(spans) if span <= epsilon]
    if len(constant_axes) != 1:
        return None
    plane_axis_index = constant_axes[0]
    u_axis_index, v_axis_index = [axis_index for axis_index in range(3) if axis_index != plane_axis_index]
    u_values = [point[u_axis_index] for point in points]
    v_values = [point[v_axis_index] for point in points]
    u_min, u_max = min(u_values), max(u_values)
    v_min, v_max = min(v_values), max(v_values)
    area = (u_max - u_min) * (v_max - v_min)
    if area <= epsilon:
        return None
    plane_value = sum(point[plane_axis_index] for point in points) / float(len(points))
    return AxisAlignedFace(
        prim_name=prim.name,
        expr_id=prim.expr_id,
        order=prim.order,
        kind=prim.source_kind,
        latex=prim.latex,
        face_index=face_index,
        plane_axis=AXES[plane_axis_index],
        plane_value=plane_value,
        u_axis=AXES[u_axis_index],
        v_axis=AXES[v_axis_index],
        u_min=u_min,
        u_max=u_max,
        v_min=v_min,
        v_max=v_max,
        area=area,
    )


def aggregate_target_overlap_pairs(
    faces_by_plane: dict[tuple[str, float], list[AxisAlignedFace]],
    target_expr_ids: set[str],
    border_plane_keys: set[tuple[str, float]],
    area_by_prim_plane: dict[tuple[str, tuple[str, float]], float],
    epsilon: float,
) -> list[dict[str, Any]]:
    pairs: dict[tuple[str, str, tuple[str, float]], dict[str, Any]] = {}
    seen_face_pairs: set[tuple[tuple[str, int], tuple[str, int], tuple[str, float]]] = set()
    for plane_key in sorted(border_plane_keys):
        plane_faces = faces_by_plane.get(plane_key, [])
        target_faces = [face for face in plane_faces if face.expr_id in target_expr_ids]
        for target_face in target_faces:
            for other_face in plane_faces:
                if target_face.prim_name == other_face.prim_name:
                    continue
                face_pair_key = normalized_face_pair_key(target_face, other_face, plane_key)
                if face_pair_key in seen_face_pairs:
                    continue
                seen_face_pairs.add(face_pair_key)
                overlap = rectangle_overlap(target_face, other_face, epsilon=epsilon)
                if overlap is None:
                    continue
                prim_a, prim_b = sorted([target_face.prim_name, other_face.prim_name])
                pair_key = (prim_a, prim_b, plane_key)
                if pair_key not in pairs:
                    left = target_face if target_face.prim_name == prim_a else other_face
                    right = other_face if left is target_face else target_face
                    area_a = area_by_prim_plane[(prim_a, plane_key)]
                    area_b = area_by_prim_plane[(prim_b, plane_key)]
                    pairs[pair_key] = {
                        "plane": {"axis": plane_key[0], "value": plane_key[1]},
                        "prim_a": prim_ref(left),
                        "prim_b": prim_ref(right),
                        "overlap_area": 0.0,
                        "face_overlap_count": 0,
                        "duplicate_face_count": 0,
                        "area_of_prim_a_on_plane": area_a,
                        "area_of_prim_b_on_plane": area_b,
                        "coverage_of_prim_a_on_plane": 0.0,
                        "coverage_of_prim_b_on_plane": 0.0,
                        "sample_overlaps": [],
                    }
                pair = pairs[pair_key]
                pair["overlap_area"] += overlap["area"]
                pair["face_overlap_count"] += 1
                if target_face.signature == other_face.signature:
                    pair["duplicate_face_count"] += 1
                if len(pair["sample_overlaps"]) < 5:
                    pair["sample_overlaps"].append(overlap_sample(target_face, other_face, overlap))

    for pair in pairs.values():
        area_a = float(pair["area_of_prim_a_on_plane"])
        area_b = float(pair["area_of_prim_b_on_plane"])
        pair["coverage_of_prim_a_on_plane"] = pair["overlap_area"] / area_a if area_a > epsilon else 0.0
        pair["coverage_of_prim_b_on_plane"] = pair["overlap_area"] / area_b if area_b > epsilon else 0.0
    return list(pairs.values())


def normalized_face_pair_key(
    left: AxisAlignedFace,
    right: AxisAlignedFace,
    plane_key: tuple[str, float],
) -> tuple[tuple[str, int], tuple[str, int], tuple[str, float]]:
    a = (left.prim_name, left.face_index)
    b = (right.prim_name, right.face_index)
    return (a, b, plane_key) if a <= b else (b, a, plane_key)


def rectangle_overlap(
    left: AxisAlignedFace,
    right: AxisAlignedFace,
    epsilon: float,
) -> dict[str, Any] | None:
    if left.u_axis != right.u_axis or left.v_axis != right.v_axis:
        return None
    u_min = max(left.u_min, right.u_min)
    u_max = min(left.u_max, right.u_max)
    v_min = max(left.v_min, right.v_min)
    v_max = min(left.v_max, right.v_max)
    if u_max - u_min <= epsilon or v_max - v_min <= epsilon:
        return None
    return {
        "u_axis": left.u_axis,
        "v_axis": left.v_axis,
        "u_min": u_min,
        "u_max": u_max,
        "v_min": v_min,
        "v_max": v_max,
        "area": (u_max - u_min) * (v_max - v_min),
    }


def overlap_sample(
    left: AxisAlignedFace,
    right: AxisAlignedFace,
    overlap: dict[str, Any],
) -> dict[str, Any]:
    return {
        "left_face": {"prim_name": left.prim_name, "face_index": left.face_index},
        "right_face": {"prim_name": right.prim_name, "face_index": right.face_index},
        "u_range": [overlap["u_min"], overlap["u_max"]],
        "v_range": [overlap["v_min"], overlap["v_max"]],
        "area": overlap["area"],
        "exact_duplicate_face": left.signature == right.signature,
    }


def prim_ref(face: AxisAlignedFace) -> dict[str, Any]:
    return {
        "prim_name": face.prim_name,
        "expr_id": face.expr_id,
        "order": face.order,
        "kind": face.kind,
        "latex": face.latex,
    }


def target_prim_summary(
    prim: ParsedUsdPrim,
    all_faces: list[AxisAlignedFace],
    area_by_prim_plane: dict[tuple[str, tuple[str, float]], float],
    overlap_pairs: list[dict[str, Any]],
    border_plane_keys: set[tuple[str, float]],
    source_viewport_bbox: dict[str, list[float]] | None,
    epsilon: float,
) -> dict[str, Any]:
    prim_faces = [face for face in all_faces if face.prim_name == prim.name]
    border_faces = [face for face in prim_faces if face.plane_key in border_plane_keys]
    border_area_by_plane = []
    for plane_key in sorted(border_plane_keys):
        area = area_by_prim_plane.get((prim.name, plane_key), 0.0)
        if area > 0.0:
            border_area_by_plane.append({"axis": plane_key[0], "value": plane_key[1], "area": area})
    overlap_area_by_plane: dict[tuple[str, float], float] = defaultdict(float)
    overlap_prim_names = set()
    for pair in overlap_pairs:
        if pair["prim_a"]["prim_name"] == prim.name:
            overlap_area_by_plane[(pair["plane"]["axis"], pair["plane"]["value"])] += pair["overlap_area"]
            overlap_prim_names.add(pair["prim_b"]["prim_name"])
        elif pair["prim_b"]["prim_name"] == prim.name:
            overlap_area_by_plane[(pair["plane"]["axis"], pair["plane"]["value"])] += pair["overlap_area"]
            overlap_prim_names.add(pair["prim_a"]["prim_name"])
    bbox = bbox_for_points(prim.points) if prim.points else None
    constant_restriction_bounds = parse_constant_restriction_bounds(prim.constraints)
    return {
        "prim_name": prim.name,
        "expr_id": prim.expr_id,
        "order": prim.order,
        "kind": prim.source_kind,
        "bbox": bbox,
        "constant_restriction_bounds": constant_restriction_bounds,
        "viewport_clipped_unbounded_axes": viewport_clipped_unbounded_axes(
            bbox,
            constant_restriction_bounds,
            source_viewport_bbox,
            epsilon=epsilon,
        ),
        "point_count": len(prim.points),
        "face_count": prim.face_count,
        "axis_aligned_face_count": len(prim_faces),
        "border_axis_aligned_face_count": len(border_faces),
        "border_area_by_plane": border_area_by_plane,
        "overlap_area_by_plane": [
            {"axis": key[0], "value": key[1], "area": value}
            for key, value in sorted(overlap_area_by_plane.items())
        ],
        "overlap_prim_names": sorted(overlap_prim_names),
        "latex": prim.latex,
        "constraints": prim.constraints,
    }


def viewport_clipped_unbounded_axes(
    bbox: dict[str, list[float]] | None,
    constant_restriction_bounds: dict[str, dict[str, Any]],
    source_viewport_bbox: dict[str, list[float]] | None,
    epsilon: float = 1e-6,
) -> list[dict[str, Any]]:
    if bbox is None or source_viewport_bbox is None:
        return []

    clipped_axes = []
    for axis_index, axis in enumerate(AXES):
        bound = constant_restriction_bounds.get(axis)
        side_specs = [
            ("min", "min", bbox["min"][axis_index], source_viewport_bbox["min"][axis_index]),
            ("max", "max", bbox["max"][axis_index], source_viewport_bbox["max"][axis_index]),
        ]
        sides = []
        for side, bound_key, bbox_value, viewport_value in side_specs:
            has_source_bound = bool(bound and bound.get(bound_key) is not None)
            if has_source_bound or abs(float(bbox_value) - float(viewport_value)) > epsilon:
                continue
            sides.append(
                {
                    "side": side,
                    "bbox_value": float(bbox_value),
                    "source_viewport_value": float(viewport_value),
                    "delta": float(bbox_value) - float(viewport_value),
                }
            )
        if sides:
            clipped_axes.append(
                {
                    "axis": axis,
                    "sides": sides,
                    "bbox_min": float(bbox["min"][axis_index]),
                    "bbox_max": float(bbox["max"][axis_index]),
                    "source_viewport_min": float(source_viewport_bbox["min"][axis_index]),
                    "source_viewport_max": float(source_viewport_bbox["max"][axis_index]),
                    "parsed_constant_restriction_bound": bound,
                }
            )
    return clipped_axes


def yz_side_view_projections(
    target_summaries: list[dict[str, Any]],
    source_viewport_bbox: dict[str, list[float]] | None,
) -> list[dict[str, Any]]:
    """Compute YZ bounding-box projection for each target prim.

    The YZ side view collapses the x axis, so the visible rectangle for each
    prim is determined by its y and z extent.  Prims whose z extent matches
    the viewport bounds (viewport-clipped) produce unnaturally large panels
    in this view.
    """
    y_axis_index, z_axis_index = 1, 2
    rows: list[dict[str, Any]] = []
    for summary in target_summaries:
        bbox = summary.get("bbox")
        if bbox is None:
            continue
        y_min = float(bbox["min"][y_axis_index])
        y_max = float(bbox["max"][y_axis_index])
        z_min = float(bbox["min"][z_axis_index])
        z_max = float(bbox["max"][z_axis_index])
        y_span = y_max - y_min
        z_span = z_max - z_min
        yz_area = y_span * z_span
        clipped_on_z = any(
            axis["axis"] == "z" for axis in summary.get("viewport_clipped_unbounded_axes", [])
        )
        viewport_z_min = float(source_viewport_bbox["min"][z_axis_index]) if source_viewport_bbox else None
        viewport_z_max = float(source_viewport_bbox["max"][z_axis_index]) if source_viewport_bbox else None
        rows.append({
            "prim_name": summary["prim_name"],
            "expr_id": summary["expr_id"],
            "order": summary["order"],
            "kind": summary["kind"],
            "y_min": y_min,
            "y_max": y_max,
            "y_span": y_span,
            "z_min": z_min,
            "z_max": z_max,
            "z_span": z_span,
            "yz_area": yz_area,
            "viewport_clipped_on_z": clipped_on_z,
            "viewport_z_min": viewport_z_min,
            "viewport_z_max": viewport_z_max,
            "latex": summary["latex"],
        })
    rows.sort(key=lambda r: (-r["yz_area"], int(r["order"] or 0)))
    return rows


def view_metadata_from_report(report: dict[str, Any]) -> dict[str, Any] | None:
    vm = report.get("view_metadata")
    if not isinstance(vm, dict):
        return None
    rotation = vm.get("world_rotation_3d")
    if not isinstance(rotation, list) or len(rotation) != 9:
        return None
    return {
        "world_rotation_3d": [float(v) for v in rotation],
    }


def frozen_view_projections(
    target_summaries: list[dict[str, Any]],
    view_metadata: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Project target prim bounding boxes into the stored source-view camera basis.

    Uses the world_rotation_3d matrix from the report's view_metadata.  Rows 0
    and 1 of this 3×3 rotation matrix give the screen-right and screen-up
    directions.  For each prim we compute the projected 2D bounding-box span
    and area in the actual frozen source-view orientation, providing a tighter
    metric than the generic YZ side-view proxy.
    """
    if view_metadata is None:
        return []

    rot = view_metadata["world_rotation_3d"]
    # Row 0 = screen-right (u), Row 1 = screen-up (v), Row 2 = depth
    screen_u = (rot[0], rot[1], rot[2])
    screen_v = (rot[3], rot[4], rot[5])
    depth = (rot[6], rot[7], rot[8])

    rows: list[dict[str, Any]] = []
    for summary in target_summaries:
        bbox = summary.get("bbox")
        if bbox is None:
            continue
        mins = bbox["min"]
        maxs = bbox["max"]
        spans = [float(maxs[i]) - float(mins[i]) for i in range(3)]

        # For a linear function a*x + b*y + c*z over a box, the projected
        # span equals |a|*dx + |b|*dy + |c|*dz.
        u_span = sum(abs(screen_u[i]) * spans[i] for i in range(3))
        v_span = sum(abs(screen_v[i]) * spans[i] for i in range(3))
        depth_span = sum(abs(depth[i]) * spans[i] for i in range(3))
        screen_area = u_span * v_span

        # Project the bbox center to get screen-space center coordinates
        center = [(float(mins[i]) + float(maxs[i])) / 2.0 for i in range(3)]
        u_center = sum(screen_u[i] * center[i] for i in range(3))
        v_center = sum(screen_v[i] * center[i] for i in range(3))

        rows.append({
            "prim_name": summary["prim_name"],
            "expr_id": summary["expr_id"],
            "order": summary["order"],
            "kind": summary["kind"],
            "screen_u_span": rounded(u_span),
            "screen_v_span": rounded(v_span),
            "screen_area": rounded(screen_area),
            "depth_span": rounded(depth_span),
            "screen_u_center": rounded(u_center),
            "screen_v_center": rounded(v_center),
            "world_bbox_spans": [rounded(s) for s in spans],
            "rotation_screen_u": list(screen_u),
            "rotation_screen_v": list(screen_v),
            "latex": summary["latex"],
        })
    rows.sort(key=lambda r: (-r["screen_area"], int(r["order"] or 0)))
    return rows


def overlap_sort_key(pair: dict[str, Any]) -> tuple[float, int, float, int, str, str]:
    return (
        -float(pair["overlap_area"]),
        -int(pair["duplicate_face_count"]),
        -min(float(pair["coverage_of_prim_a_on_plane"]), float(pair["coverage_of_prim_b_on_plane"])),
        int(pair["prim_a"]["order"] or 0),
        str(pair["prim_a"]["prim_name"]),
        str(pair["prim_b"]["prim_name"]),
    )


def build_viewport_outlier_correlation(
    report: dict[str, Any],
    target_summaries: list[dict[str, Any]],
    target_expr_ids: set[str],
) -> dict[str, Any] | None:
    geometry_diagnostics = report.get("geometry_diagnostics") if isinstance(report, dict) else None
    if not isinstance(geometry_diagnostics, dict):
        return None
    outliers = geometry_diagnostics.get("outliers")
    if not isinstance(outliers, list):
        return None

    summary_by_expr = {str(summary["expr_id"]): summary for summary in target_summaries}
    rows = []
    for outlier in outliers:
        expr_id = str(outlier.get("expr_id"))
        if expr_id not in target_expr_ids:
            continue
        summary = summary_by_expr.get(expr_id)
        if summary is None:
            continue
        rows.append(
            {
                "expr_id": expr_id,
                "prim_name": str(outlier.get("prim_name") or summary["prim_name"]),
                "order": outlier.get("order"),
                "kind": str(outlier.get("kind") or summary["kind"]),
                "latex": str(outlier.get("latex") or summary["latex"]),
                "category": classify_target_outlier(summary),
                "max_viewport_overshoot": rounded(float(outlier.get("max_viewport_overshoot") or 0.0)),
                "outside_viewport_axes": outlier.get("outside_viewport_axes") or [],
                "border_planes": summary.get("border_area_by_plane") or [],
                "overlap_prim_names": summary.get("overlap_prim_names") or [],
                "viewport_clipped_unbounded_axes": summary.get("viewport_clipped_unbounded_axes") or [],
            }
        )

    rows.sort(key=lambda row: (-float(row["max_viewport_overshoot"]), int(row["order"] or 0), str(row["expr_id"])))
    grouped_expr_ids = {
        category: [row["expr_id"] for row in rows if row["category"] == category]
        for category in (
            "broad_wall_or_floor",
            "roof_arch_or_side_surface",
            "window_border_side_slab",
            "other_target_outlier",
        )
    }
    return {
        "total_report_outlier_count": int(geometry_diagnostics.get("outlier_count", len(outliers))),
        "target_report_outlier_count": len(rows),
        "target_report_outlier_expr_ids": [row["expr_id"] for row in rows],
        "broad_wall_or_floor_expr_ids": grouped_expr_ids["broad_wall_or_floor"],
        "roof_arch_or_side_surface_expr_ids": grouped_expr_ids["roof_arch_or_side_surface"],
        "window_border_side_slab_expr_ids": grouped_expr_ids["window_border_side_slab"],
        "other_target_outlier_expr_ids": grouped_expr_ids["other_target_outlier"],
        "rows": rows,
    }


def classify_target_outlier(summary: dict[str, Any]) -> str:
    border_planes = summary.get("border_area_by_plane") or []
    y_planes = {
        rounded(float(plane["value"]))
        for plane in border_planes
        if plane.get("axis") == "y"
    }
    if any(abs(value) == 18.0 for value in y_planes):
        return "window_border_side_slab"
    if summary.get("kind") == "inequality_region" or any(abs(value) == 20.0 for value in y_planes):
        return "broad_wall_or_floor"
    if summary.get("kind") == "explicit_surface":
        return "roof_arch_or_side_surface"
    return "other_target_outlier"


def write_window_border_diagnostics_json(path: Path, diagnostics: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(diagnostics, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_window_border_diagnostics_markdown(path: Path, diagnostics: dict[str, Any], limit: int = 30) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(markdown_for_window_border_diagnostics(diagnostics, limit=limit)) + "\n", encoding="utf-8")


def markdown_for_window_border_diagnostics(diagnostics: dict[str, Any], limit: int = 30) -> list[str]:
    full_coverage_pairs = diagnostics["strongest_full_coverage_pairs"][:limit]
    exact_duplicate_pairs = diagnostics["strongest_exact_duplicate_full_pairs"][:limit]
    overlap_pairs = diagnostics["top_coplanar_overlap_pairs"][:limit]
    lines = [
        f"# {diagnostics.get('graph_hash') or 'USDA'} window border diagnostics",
        "",
        "Deterministic narrowing artifact generated from exported USDA mesh faces.",
        "",
        "## Inputs",
        f"- USDA: `{diagnostics['usda_path']}`",
        f"- report: `{diagnostics.get('report_path') or 'none'}`",
        f"- target expr ids: `{', '.join(diagnostics['target_expr_ids'])}`",
        f"- border planes: `{format_border_planes(diagnostics['border_planes'])}`",
        f"- source viewport bbox: {format_bbox(diagnostics.get('source_viewport_bbox'))}",
        "",
        "## Finding",
        (
            "- full coplanar border overlap: "
            f"`{'yes' if diagnostics['full_coverage_pair_count'] else 'no'}`"
        ),
        (
            "- exact duplicate face grids among full overlaps: "
            f"`{'yes' if diagnostics['exact_duplicate_full_pair_count'] else 'no'}`"
        ),
        f"- full-coverage target-involved pairs: `{diagnostics['full_coverage_pair_count']}`",
        f"- exact duplicate full-coverage pairs: `{diagnostics['exact_duplicate_full_pair_count']}`",
        f"- target-involved coplanar overlap pairs: `{diagnostics['coplanar_overlap_pair_count']}`",
        (
            "- target expr ids with no coplanar face-area overlap on the selected border planes: "
            f"`{', '.join(diagnostics['target_expr_ids_without_coplanar_face_overlap']) or 'none'}`"
        ),
        (
            "- target prims viewport-clipped on otherwise unbounded axes: "
            f"`{format_viewport_clipped_target_prims(diagnostics['viewport_clipped_unbounded_target_prims'])}`"
        ),
        "",
        "## Strongest Full Coplanar Overlaps",
        overlap_pair_table(full_coverage_pairs),
        "",
        "## Exact Duplicate Face Grids",
        overlap_pair_table(exact_duplicate_pairs),
        "",
        f"## Top Coplanar Overlaps ({min(limit, len(overlap_pairs))})",
        overlap_pair_table(overlap_pairs),
        "",
        "## YZ Side-View Projections",
        yz_projection_table(diagnostics.get("yz_side_view_projections", [])),
        "",
        "## Frozen Source-View Projections",
        frozen_view_projection_table(diagnostics.get("frozen_view_projections", [])),
        "",
        *viewport_outlier_correlation_lines(diagnostics.get("viewport_outlier_correlation")),
        "## Target Prim Summary",
        target_summary_table(diagnostics["target_prims"]),
    ]
    return lines


def viewport_outlier_correlation_lines(correlation: dict[str, Any] | None) -> list[str]:
    if not isinstance(correlation, dict) or not correlation.get("rows"):
        return []
    return [
        "## Viewport Outlier Correlation",
        "",
        (
            "- report viewport outliers intersecting target expr set: "
            f"`{correlation['target_report_outlier_count']} / {correlation['total_report_outlier_count']}`"
        ),
        (
            "- broad wall or floor expr ids: "
            f"`{', '.join(correlation['broad_wall_or_floor_expr_ids']) or 'none'}`"
        ),
        (
            "- roof arch or side-surface expr ids: "
            f"`{', '.join(correlation['roof_arch_or_side_surface_expr_ids']) or 'none'}`"
        ),
        (
            "- window-border side slab expr ids: "
            f"`{', '.join(correlation['window_border_side_slab_expr_ids']) or 'none'}`"
        ),
        (
            "- other target outlier expr ids: "
            f"`{', '.join(correlation['other_target_outlier_expr_ids']) or 'none'}`"
        ),
        "",
        viewport_outlier_correlation_table(correlation["rows"]),
        "",
    ]


def viewport_outlier_correlation_table(rows: list[dict[str, Any]]) -> str:
    headers = [
        "expr",
        "category",
        "max_overshoot",
        "outlier_axes",
        "border_planes",
        "coplanar_overlaps",
        "viewport_clipped_unbounded_axes",
        "latex",
    ]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        values = [
            f"`{row['expr_id']}`",
            f"`{format_target_outlier_category(row['category'])}`",
            f"`{format_float(row['max_viewport_overshoot'])}`",
            f"`{format_outlier_axes(row['outside_viewport_axes'])}`",
            f"`{format_plane_areas(row['border_planes'])}`",
            f"`{', '.join(row['overlap_prim_names']) or 'none'}`",
            f"`{format_viewport_clipped_axes(row['viewport_clipped_unbounded_axes'])}`",
            f"`{markdown_escape(row['latex'])}`",
        ]
        lines.append("| " + " | ".join(markdown_escape(value) for value in values) + " |")
    return "\n".join(lines)


def format_target_outlier_category(category: str) -> str:
    return {
        "broad_wall_or_floor": "broad wall or floor",
        "roof_arch_or_side_surface": "roof arch or side surface",
        "window_border_side_slab": "window-border side slab",
        "other_target_outlier": "other target outlier",
    }.get(category, category)


def format_outlier_axes(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "none"
    parts = []
    for row in rows:
        parts.append(
            f"{row['axis']} low={format_float(row['low_overshoot'])}, high={format_float(row['high_overshoot'])}"
        )
    return "; ".join(parts)


def overlap_pair_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "none"
    headers = [
        "rank",
        "plane",
        "prim_a",
        "expr_a",
        "prim_b",
        "expr_b",
        "overlap_area",
        "dup_faces",
        "face_pairs",
        "coverage_a",
        "coverage_b",
        "sample",
    ]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for index, row in enumerate(rows, start=1):
        sample = row["sample_overlaps"][0] if row["sample_overlaps"] else None
        values = [
            str(index),
            f"`{row['plane']['axis']}={format_float(row['plane']['value'])}`",
            f"`{row['prim_a']['prim_name']}`",
            f"`{row['prim_a']['expr_id']}`",
            f"`{row['prim_b']['prim_name']}`",
            f"`{row['prim_b']['expr_id']}`",
            f"`{format_float(row['overlap_area'])}`",
            f"`{row['duplicate_face_count']}`",
            f"`{row['face_overlap_count']}`",
            f"`{format_percent(row['coverage_of_prim_a_on_plane'])}`",
            f"`{format_percent(row['coverage_of_prim_b_on_plane'])}`",
            f"`{format_overlap_sample(sample)}`",
        ]
        lines.append("| " + " | ".join(markdown_escape(value) for value in values) + " |")
    return "\n".join(lines)


def target_summary_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "none"
    headers = [
        "prim",
        "expr",
        "order",
        "kind",
        "bbox",
        "border_faces",
        "border_area",
        "overlaps",
        "viewport_clipped_unbounded_axes",
        "latex",
    ]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        values = [
            f"`{row['prim_name']}`",
            f"`{row['expr_id']}`",
            f"`{row['order']}`",
            f"`{row['kind']}`",
            f"`{format_bbox_compact(row['bbox'])}`",
            f"`{row['border_axis_aligned_face_count']}`",
            f"`{format_plane_areas(row['border_area_by_plane'])}`",
            f"`{', '.join(row['overlap_prim_names']) or 'none'}`",
            f"`{format_viewport_clipped_axes(row['viewport_clipped_unbounded_axes'])}`",
            f"`{markdown_escape(row['latex'])}`",
        ]
        lines.append("| " + " | ".join(markdown_escape(value) for value in values) + " |")
    return "\n".join(lines)


def yz_projection_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "none"
    headers = [
        "rank",
        "prim",
        "expr",
        "kind",
        "y_span",
        "z_span",
        "yz_area",
        "z_clipped",
        "latex",
    ]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for index, row in enumerate(rows, start=1):
        values = [
            str(index),
            f"`{row['prim_name']}`",
            f"`{row['expr_id']}`",
            f"`{row['kind']}`",
            f"`{format_float(row['y_min'])}..{format_float(row['y_max'])} ({format_float(row['y_span'])})`",
            f"`{format_float(row['z_min'])}..{format_float(row['z_max'])} ({format_float(row['z_span'])})`",
            f"`{format_float(row['yz_area'])}`",
            f"`{'yes' if row['viewport_clipped_on_z'] else 'no'}`",
            f"`{markdown_escape(row['latex'])}`",
        ]
        lines.append("| " + " | ".join(markdown_escape(value) for value in values) + " |")
    return "\n".join(lines)


def frozen_view_projection_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "none"
    headers = [
        "rank",
        "prim",
        "expr",
        "kind",
        "screen_u_span",
        "screen_v_span",
        "screen_area",
        "depth_span",
        "latex",
    ]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for index, row in enumerate(rows, start=1):
        values = [
            str(index),
            f"`{row['prim_name']}`",
            f"`{row['expr_id']}`",
            f"`{row['kind']}`",
            f"`{format_float(row['screen_u_span'])}`",
            f"`{format_float(row['screen_v_span'])}`",
            f"`{format_float(row['screen_area'])}`",
            f"`{format_float(row['depth_span'])}`",
            f"`{markdown_escape(row['latex'])}`",
        ]
        lines.append("| " + " | ".join(markdown_escape(value) for value in values) + " |")
    return "\n".join(lines)


def format_bbox_compact(bbox: dict[str, list[float]] | None) -> str:
    if bbox is None:
        return "none"
    return f"min {format_vector(bbox['min'])}; max {format_vector(bbox['max'])}"


def format_plane_areas(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "none"
    return "; ".join(f"{row['axis']}={format_float(row['value'])} area={format_float(row['area'])}" for row in rows)


def format_viewport_clipped_target_prims(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "none"
    return ", ".join(f"{row['expr_id']}:{'+'.join(row['axes'])}" for row in rows)


def format_viewport_clipped_axes(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "none"
    parts = []
    for row in rows:
        sides = "+".join(side["side"] for side in row["sides"])
        parts.append(f"{row['axis']}={sides} source viewport")
    return "; ".join(parts)


def format_border_planes(rows: list[dict[str, Any]]) -> str:
    return ", ".join(f"{row['axis']}={format_float(row['value'])}" for row in rows)


def format_percent(value: float) -> str:
    return f"{value * 100.0:.6g}%"


def format_overlap_sample(sample: dict[str, Any] | None) -> str:
    if sample is None:
        return "none"
    return (
        f"{sample['left_face']['prim_name']}[{sample['left_face']['face_index']}] x "
        f"{sample['right_face']['prim_name']}[{sample['right_face']['face_index']}], "
        f"{format_vector(sample['u_range'])} / {format_vector(sample['v_range'])}, "
        f"duplicate={sample['exact_duplicate_face']}"
    )


def rounded(value: float) -> float:
    if abs(value) < 10 ** (-(ROUND_DIGITS + 1)):
        value = 0.0
    return round(float(value), ROUND_DIGITS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Diagnose target-involved coplanar mesh overlap on window border planes")
    parser.add_argument("usda", help="Input USDA artifact")
    parser.add_argument("--report", help="Optional acceptance report JSON for source viewport bounds")
    parser.add_argument("--out", required=True, help="Output Markdown diagnostics path")
    parser.add_argument("--json-out", help="Optional output JSON diagnostics path")
    parser.add_argument("--limit", type=int, default=30, help="Rows per Markdown table")
    parser.add_argument(
        "--target-expr-ids",
        default=",".join(DEFAULT_TARGET_EXPR_IDS),
        help="Comma-separated expression ids to treat as suspicious targets",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    target_expr_ids = tuple(part.strip() for part in args.target_expr_ids.split(",") if part.strip())
    diagnostics = build_window_border_diagnostics(
        Path(args.usda),
        report_path=Path(args.report) if args.report else None,
        target_expr_ids=target_expr_ids,
        limit=args.limit,
    )
    write_window_border_diagnostics_markdown(Path(args.out), diagnostics, limit=args.limit)
    if args.json_out:
        write_window_border_diagnostics_json(Path(args.json_out), diagnostics)
    print(
        json.dumps(
            {
                "coplanar_overlap_pair_count": diagnostics["coplanar_overlap_pair_count"],
                "exact_duplicate_full_pair_count": diagnostics["exact_duplicate_full_pair_count"],
                "full_coverage_pair_count": diagnostics["full_coverage_pair_count"],
                "target_prim_count": diagnostics["target_prim_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
