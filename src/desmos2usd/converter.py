from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from pathlib import Path
from typing import Any

from desmos2usd.desmos_state import load_state_for_url
from desmos2usd.eval.context import EvalContext
from desmos2usd.ir import GraphIR, graph_ir_from_state
from desmos2usd.parse.classify import ClassificationResult, classify_graph
from desmos2usd.tessellate import tessellate
from desmos2usd.tessellate.mesh import linspace
from desmos2usd.tessellate.surfaces import explicit_surface_domain_bounds
from desmos2usd.usd.metadata import prim_name
from desmos2usd.usd.package import package_usdz, validate_usdz_arkit
from desmos2usd.usd.writer import ExportedPrim, write_usda
from desmos2usd.validate.equations import ValidationReport, validate_geometry
from desmos2usd.validate.visual import write_preview_ppm


@dataclass
class ConversionReport:
    url: str
    graph_hash: str
    output: str
    usdz_output: str | None
    usdz_package: dict[str, Any] | None
    usdz_validation: dict[str, Any] | None
    view_metadata: dict[str, Any]
    renderable_expression_count: int
    prim_count: int
    unsupported_count: int
    geometry_diagnostics: dict[str, Any]
    valid: bool
    complete: bool
    validations: list[dict]
    unsupported: list[dict]


def convert_url(
    url: str,
    output: Path,
    project_root: Path,
    refresh: bool = False,
    resolution: int = 18,
    write_preview: bool = False,
    usdz_output: Path | None = None,
    validate_usdz: bool = False,
) -> ConversionReport:
    if validate_usdz and usdz_output is None:
        raise ValueError("validate_usdz requires usdz_output")
    state = load_state_for_url(url, project_root=project_root, refresh=refresh)
    graph = graph_ir_from_state(state)
    classification = classify_graph(graph)
    prims, validations, unsupported = export_graph(graph, classification, output, resolution=resolution)
    if write_preview:
        write_preview_ppm(output.with_suffix(".ppm"), prims)
    usdz_package = None
    usdz_validation = None
    if usdz_output is not None:
        usdz_package = package_usdz(output, usdz_output).to_dict()
        if validate_usdz:
            usdz_validation = validate_usdz_arkit(usdz_output).to_dict()
    return ConversionReport(
        url=graph.source.url,
        graph_hash=graph.source.graph_hash,
        output=str(output),
        usdz_output=str(usdz_output) if usdz_output is not None else None,
        usdz_package=usdz_package,
        usdz_validation=usdz_validation,
        view_metadata=graph.source.view_metadata,
        renderable_expression_count=len(classification.classified),
        prim_count=len(prims),
        unsupported_count=len(unsupported),
        geometry_diagnostics=build_geometry_diagnostics(prims, graph.source.viewport_bounds),
        valid=all(report.valid for report in validations),
        complete=not unsupported,
        validations=[asdict(report) for report in validations],
        unsupported=[asdict(item) for item in unsupported],
    )


@dataclass
class UnsupportedExpression:
    expr_id: str
    kind: str
    latex: str
    reason: str


def export_graph(
    graph: GraphIR,
    classification: ClassificationResult,
    output: Path,
    resolution: int = 18,
) -> tuple[list[ExportedPrim], list[ValidationReport], list[UnsupportedExpression]]:
    prims: list[ExportedPrim] = []
    validations: list[ValidationReport] = []
    unsupported: list[UnsupportedExpression] = []
    explicit_surface_axis_samples = build_explicit_surface_partition_hints(
        classification.classified,
        classification.context,
        resolution,
    )
    for item in classification.classified:
        try:
            geometry = tessellate(
                item,
                classification.context,
                resolution=resolution,
                explicit_surface_axis_samples=explicit_surface_axis_samples.get(classified_expression_key(item)),
            )
            report = validate_geometry(item, geometry, classification.context)
        except Exception as exc:
            unsupported.append(
                UnsupportedExpression(expr_id=item.ir.expr_id, kind=item.kind, latex=item.ir.latex, reason=str(exc))
            )
            continue
        if not report.valid:
            unsupported.append(
                UnsupportedExpression(
                    expr_id=item.ir.expr_id,
                    kind=item.kind,
                    latex=item.ir.latex,
                    reason="; ".join(report.errors),
                )
            )
            continue
        validations.append(report)
        prims.append(ExportedPrim(item=item, geometry=geometry))
    write_usda(output, graph, prims)
    return prims, validations, unsupported


EXPLICIT_SURFACE_SEAM_TOLERANCE = 1e-6


@dataclass(frozen=True)
class ExplicitSurfaceDomainRecord:
    item: ClassifiedExpression
    domain_axes: tuple[str, str]
    bounds: dict[str, tuple[float, float]]


def build_explicit_surface_partition_hints(
    classified: list[ClassifiedExpression],
    context: EvalContext,
    resolution: int,
) -> dict[tuple[int, str], dict[str, list[float]]]:
    records = explicit_surface_domain_records(classified, context)
    hints: dict[tuple[int, str], dict[str, set[float]]] = {}
    for donor in records:
        donor_value = constant_explicit_surface_value(donor.item, context)
        if donor_value is None:
            continue
        for target_axis in donor.domain_axes:
            varying_axes = [axis for axis in donor.domain_axes if axis != target_axis]
            if len(varying_axes) != 1:
                continue
            varying_axis = varying_axes[0]
            donor_interval = donor.bounds[varying_axis]
            for target_value in donor.bounds[target_axis]:
                for candidate in records:
                    if candidate.item is donor.item:
                        continue
                    if candidate.item.axis != target_axis:
                        continue
                    if donor.item.axis not in candidate.domain_axes or varying_axis not in candidate.domain_axes:
                        continue
                    if not interval_contains(candidate.bounds[varying_axis], donor_interval):
                        continue
                    if not boundary_value_matches(candidate.bounds[donor.item.axis], donor_value):
                        continue
                    if not candidate_surface_matches_boundary(
                        candidate.item,
                        context,
                        boundary_axis=donor.item.axis,
                        boundary_value=donor_value,
                        varying_axis=varying_axis,
                        varying_interval=donor_interval,
                        target_value=target_value,
                    ):
                        continue
                    axis_hints = hints.setdefault(classified_expression_key(candidate.item), {})
                    values = axis_hints.setdefault(varying_axis, set())
                    values.update(round(value, 10) for value in linspace(*donor_interval, resolution))
    return {
        item_key: {
            axis: sorted(values)
            for axis, values in axis_hints.items()
        }
        for item_key, axis_hints in hints.items()
    }


def explicit_surface_domain_records(
    classified: list[ClassifiedExpression],
    context: EvalContext,
) -> list[ExplicitSurfaceDomainRecord]:
    records: list[ExplicitSurfaceDomainRecord] = []
    for item in classified:
        if item.kind != "explicit_surface" or not item.axis:
            continue
        domain_axis_values = [axis for axis in ("x", "y", "z") if axis != item.axis]
        if len(domain_axis_values) != 2:
            continue
        records.append(
            ExplicitSurfaceDomainRecord(
                item=item,
                domain_axes=(domain_axis_values[0], domain_axis_values[1]),
                bounds=explicit_surface_domain_bounds(item, context),
            )
        )
    return records


def constant_explicit_surface_value(item: ClassifiedExpression, context: EvalContext) -> float | None:
    if not item.expression or item.expression.identifiers & {"x", "y", "z"}:
        return None
    try:
        value = float(item.expression.eval(context, {}))
    except Exception:
        return None
    return value if isfinite(value) else None


def candidate_surface_matches_boundary(
    item: ClassifiedExpression,
    context: EvalContext,
    boundary_axis: str,
    boundary_value: float,
    varying_axis: str,
    varying_interval: tuple[float, float],
    target_value: float,
) -> bool:
    if not item.expression:
        return False
    low, high = varying_interval
    for varying_value in (low, (low + high) / 2.0, high):
        variables = {boundary_axis: boundary_value, varying_axis: varying_value}
        try:
            value = float(item.expression.eval(context, variables))
        except Exception:
            return False
        if not isfinite(value) or abs(value - target_value) > EXPLICIT_SURFACE_SEAM_TOLERANCE:
            return False
    return True


def interval_contains(container: tuple[float, float], contained: tuple[float, float]) -> bool:
    return (
        container[0] <= contained[0] + EXPLICIT_SURFACE_SEAM_TOLERANCE
        and contained[1] <= container[1] + EXPLICIT_SURFACE_SEAM_TOLERANCE
    )


def boundary_value_matches(bounds: tuple[float, float], value: float) -> bool:
    return any(abs(bound - value) <= EXPLICIT_SURFACE_SEAM_TOLERANCE for bound in bounds)


def classified_expression_key(item: ClassifiedExpression) -> tuple[int, str]:
    return (item.ir.order, item.ir.expr_id)


AXES = ("x", "y", "z")


def build_geometry_diagnostics(
    prims: list[ExportedPrim],
    viewport_bounds: dict[str, tuple[float, float]],
    outlier_margin_fraction: float = 0.10,
    outlier_limit: int = 20,
) -> dict[str, Any]:
    prim_extents = [prim_extent(prim) for prim in prims]
    prim_extents = [extent for extent in prim_extents if extent is not None]
    viewport_bbox = viewport_bounds_bbox(viewport_bounds)
    outliers = [
        with_viewport_outlier_metrics(extent, viewport_bounds, outlier_margin_fraction)
        for extent in prim_extents
    ]
    outliers = [outlier for outlier in outliers if outlier is not None]
    outliers.sort(key=lambda item: (-float(item["max_viewport_overshoot"]), int(item["order"]), str(item["expr_id"])))
    return {
        "global_bbox": combined_bbox([extent["bbox"] for extent in prim_extents]),
        "source_viewport_bbox": viewport_bbox,
        "outlier_rule": (
            "prim bbox outside frozen source viewport by more than "
            f"{outlier_margin_fraction:.0%} of that axis span"
        ),
        "outlier_count": len(outliers),
        "outliers": outliers[:outlier_limit],
    }


def prim_extent(prim: ExportedPrim) -> dict[str, Any] | None:
    points = [point for point in prim.geometry.points if all(isfinite(coord) for coord in point)]
    if not points:
        return None
    bbox = bbox_for_points(points)
    item = prim.item
    return {
        "expr_id": item.ir.expr_id,
        "order": item.ir.order,
        "prim_name": prim_name(item),
        "kind": item.kind,
        "point_count": prim.geometry.point_count,
        "face_count": prim.geometry.face_count,
        "bbox": bbox,
        "latex": item.ir.latex,
    }


def bbox_for_points(points: list[tuple[float, float, float]]) -> dict[str, list[float]]:
    mins = [min(point[index] for point in points) for index in range(3)]
    maxs = [max(point[index] for point in points) for index in range(3)]
    return {
        "min": mins,
        "max": maxs,
        "span": [maxs[index] - mins[index] for index in range(3)],
    }


def combined_bbox(boxes: list[dict[str, list[float]]]) -> dict[str, list[float]] | None:
    if not boxes:
        return None
    mins = [min(box["min"][index] for box in boxes) for index in range(3)]
    maxs = [max(box["max"][index] for box in boxes) for index in range(3)]
    return {
        "min": mins,
        "max": maxs,
        "span": [maxs[index] - mins[index] for index in range(3)],
    }


def viewport_bounds_bbox(viewport_bounds: dict[str, tuple[float, float]]) -> dict[str, list[float]] | None:
    if any(axis not in viewport_bounds for axis in AXES):
        return None
    mins = [viewport_bounds[axis][0] for axis in AXES]
    maxs = [viewport_bounds[axis][1] for axis in AXES]
    return {
        "min": mins,
        "max": maxs,
        "span": [maxs[index] - mins[index] for index in range(3)],
    }


def with_viewport_outlier_metrics(
    extent: dict[str, Any],
    viewport_bounds: dict[str, tuple[float, float]],
    margin_fraction: float,
) -> dict[str, Any] | None:
    outside_axes = []
    for axis_index, axis in enumerate(AXES):
        if axis not in viewport_bounds:
            continue
        viewport_low, viewport_high = viewport_bounds[axis]
        margin = (viewport_high - viewport_low) * margin_fraction
        bbox_min = extent["bbox"]["min"][axis_index]
        bbox_max = extent["bbox"]["max"][axis_index]
        low_overshoot = max(0.0, viewport_low - bbox_min)
        high_overshoot = max(0.0, bbox_max - viewport_high)
        if max(low_overshoot, high_overshoot) > margin:
            outside_axes.append(
                {
                    "axis": axis,
                    "low_overshoot": low_overshoot,
                    "high_overshoot": high_overshoot,
                    "threshold_margin": margin,
                }
            )
    if not outside_axes:
        return None
    outlier = dict(extent)
    outlier["outside_viewport_axes"] = outside_axes
    outlier["max_viewport_overshoot"] = max(
        max(axis["low_overshoot"], axis["high_overshoot"]) for axis in outside_axes
    )
    return outlier
