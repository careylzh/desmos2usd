from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit

from desmos2usd.converter import convert_url
from desmos2usd.desmos_state import REQUIRED_SAMPLE_URLS, load_fixture_state, load_state_for_url, project_root_from_cwd
from desmos2usd.ir import graph_ir_from_state
from desmos2usd.parse.classify import ClassifiedExpression, classify_graph
from desmos2usd.parse.predicates import ComparisonPredicate, single_identifier

COMPARE_SHEET_FILENAME = "compare-sheet.md"
COMPARE_SHEET_TITLE = "desmos2usd acceptance manual compare sheet"
GEOMETRY_OUTLIER_DETAIL_LIMIT = 12
SOURCE_TRIAGE_CONTRADICTORY = "contradictory_source"
SOURCE_TRIAGE_RESIDUAL_LIMITATION = "residual_converter_limitation"
SOURCE_TRIAGE_UNTRIAGED = "untriaged"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the required desmos2usd acceptance sample suite")
    parser.add_argument("--out", default="artifacts/acceptance", help="Output artifact directory")
    parser.add_argument("--refresh", action="store_true", help="Fetch live Desmos states instead of frozen fixtures")
    parser.add_argument("--resolution", type=int, default=18)
    parser.add_argument(
        "--sample",
        help=(
            "Export exactly one required sample by graph hash or URL, then refresh summary.json and "
            f"{COMPARE_SHEET_FILENAME} from the existing required reports"
        ),
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Regenerate summary.json from existing required *.report.json files without exporting samples",
    )
    parser.add_argument(
        "--compare-sheet-only",
        action="store_true",
        help=f"Regenerate {COMPARE_SHEET_FILENAME} from existing required *.report.json files without exporting samples",
    )
    parser.add_argument(
        "--verify-artifacts",
        action="store_true",
        help="Verify required compare USDA/PPM/report artifacts and viewer USDA link targets from existing required *.report.json files without regenerating outputs",
    )
    return parser


def sample_hash(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def resolve_required_sample_url(selection: str, expected_urls: list[str]) -> str:
    normalized_selection = selection.rstrip("/")
    for url in expected_urls:
        if normalized_selection in {url.rstrip("/"), sample_hash(url)}:
            return url
    allowed = ", ".join(sample_hash(url) for url in expected_urls)
    raise ValueError(f"Unknown required sample {selection!r}; expected one of: {allowed}")


def load_required_reports(out_dir: Path) -> list[dict]:
    reports = []
    missing = []
    for url in REQUIRED_SAMPLE_URLS:
        report_path = out_dir / f"{sample_hash(url)}.report.json"
        if not report_path.exists():
            missing.append(str(report_path))
            continue
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise ValueError(f"Acceptance report is not a JSON object: {report_path}")
        reports.append(report)
    if missing:
        raise FileNotFoundError("Missing required acceptance report(s): " + ", ".join(missing))
    return reports


def normalized_report(report: dict, expected_url: str | None = None) -> dict:
    normalized = dict(report)
    expected_hash = sample_hash(expected_url) if expected_url else None
    if expected_hash:
        actual_hash = str(normalized.get("graph_hash") or "")
        if actual_hash and actual_hash != expected_hash:
            raise ValueError(f"Report graph_hash {actual_hash!r} does not match required sample {expected_hash!r}")
        normalized["graph_hash"] = actual_hash or expected_hash
        normalized["url"] = str(normalized.get("url") or expected_url)

    unsupported_count = report_unsupported_count(normalized)
    normalized["unsupported_count"] = unsupported_count
    normalized["unsupported_source_triage"] = summarize_unsupported_source_triage(
        normalized.get("unsupported"),
        unsupported_count,
    )
    normalized.setdefault("complete", unsupported_count == 0)
    if "valid" not in normalized:
        validations = normalized.get("validations")
        normalized["valid"] = all(item.get("valid", False) for item in validations) if isinstance(validations, list) else False
    return normalized


def summarize_unsupported_source_triage(unsupported: object, unsupported_count: int | None = None) -> dict[str, int]:
    summary = {
        "contradictory_source_count": 0,
        "residual_converter_limitation_count": 0,
        "untriaged_count": 0,
    }
    if not isinstance(unsupported, list):
        summary["untriaged_count"] = int(unsupported_count or 0)
        return summary

    for item in unsupported:
        classification = None
        if isinstance(item, dict):
            source_triage = item.get("source_triage")
            if isinstance(source_triage, dict):
                classification = source_triage.get("classification")
        if classification == SOURCE_TRIAGE_CONTRADICTORY:
            summary["contradictory_source_count"] += 1
        elif classification == SOURCE_TRIAGE_RESIDUAL_LIMITATION:
            summary["residual_converter_limitation_count"] += 1
        else:
            summary["untriaged_count"] += 1
    return summary


def unsupported_triage_cell(report: dict) -> str:
    summary = report.get("unsupported_source_triage")
    if not isinstance(summary, dict):
        summary = summarize_unsupported_source_triage(report.get("unsupported"), report.get("unsupported_count", 0))
    return (
        f"{int(summary.get('contradictory_source_count', 0))} contradictory source, "
        f"{int(summary.get('residual_converter_limitation_count', 0))} residual limitation, "
        f"{int(summary.get('untriaged_count', 0))} untriaged"
    )


def unsupported_evidence_cell(report: dict, anchor: str | None = None) -> str:
    unsupported = report.get("unsupported")
    if not isinstance(unsupported, list) or not unsupported:
        return "none"

    detail_count = len(unsupported_contradiction_evidence_lines(report))
    if detail_count:
        detail_label = "contradiction detail" if detail_count == 1 else "contradiction details"
        graph_hash = str(report.get("graph_hash") or "").strip()
        target_anchor = anchor or (unsupported_evidence_anchor(graph_hash) if graph_hash else None)
        if target_anchor:
            return f"{detail_count} {detail_label}: [details](#{target_anchor})"
        return f"{detail_count} {detail_label}"
    entry_label = "entry" if len(unsupported) == 1 else "entries"
    return f"{len(unsupported)} unsupported {entry_label}; no contradiction details"


def unsupported_contradiction_evidence_lines(report: dict) -> list[str]:
    unsupported = report.get("unsupported")
    if not isinstance(unsupported, list) or not unsupported:
        return []

    evidence = []
    for item in unsupported:
        if not isinstance(item, dict):
            continue

        expr_id = str(item.get("expr_id") or "unknown")
        source_triage = item.get("source_triage")
        if not isinstance(source_triage, dict):
            continue

        classification = str(source_triage.get("classification") or SOURCE_TRIAGE_UNTRIAGED)
        contradictions = source_triage.get("contradictions")
        if classification != SOURCE_TRIAGE_CONTRADICTORY or not isinstance(contradictions, list):
            continue

        for contradiction in contradictions:
            if not isinstance(contradiction, dict):
                continue
            formatted = format_unsupported_contradiction(contradiction)
            if formatted:
                evidence.append(f"expr `{expr_id}`: {formatted}")

    return evidence


def unsupported_evidence_anchor(graph_hash: str) -> str:
    stable_hash = "".join(
        character if character.isalnum() or character in "-_" else "-"
        for character in graph_hash.lower()
    ).strip("-")
    return f"unsupported-evidence-{stable_hash or 'sample'}"


def unsupported_evidence_anchors(reports: list[dict]) -> list[str | None]:
    anchors: list[str | None] = []
    used_anchors: set[str] = set()
    for report in reports:
        if not unsupported_contradiction_evidence_lines(report):
            anchors.append(None)
            continue

        graph_hash = str(report.get("graph_hash") or "sample")
        base_anchor = unsupported_evidence_anchor(graph_hash)
        anchor = base_anchor
        suffix = 2
        while anchor in used_anchors:
            anchor = f"{base_anchor}-{suffix}"
            suffix += 1
        used_anchors.add(anchor)
        anchors.append(anchor)
    return anchors


def unsupported_evidence_details_section(reports: list[dict], anchors: list[str | None] | None = None) -> list[str]:
    if anchors is None:
        anchors = unsupported_evidence_anchors(reports)
    lines: list[str] = []
    for index, report in enumerate(reports):
        detail_lines = unsupported_contradiction_evidence_lines(report)
        if not detail_lines:
            continue
        graph_hash = str(report.get("graph_hash") or "sample")
        anchor = anchors[index] if index < len(anchors) and anchors[index] else unsupported_evidence_anchor(graph_hash)
        if not lines:
            lines.extend(["## Unsupported Evidence Details", ""])
        lines.extend(
            [
                f'<a id="{anchor}"></a>',
                f"### {graph_hash}",
                "",
            ]
        )
        lines.extend(f"- {line}" for line in detail_lines)
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def geometry_diagnostics_cell(report: dict, anchor: str | None = None) -> str:
    diagnostics = report.get("geometry_diagnostics")
    if not isinstance(diagnostics, dict):
        return "not recorded"

    outlier_count = geometry_outlier_count(diagnostics)
    if outlier_count == 0:
        return "0 viewport outliers"

    strongest = strongest_geometry_outlier(diagnostics)
    if strongest is None:
        outlier_label = "viewport outlier" if outlier_count == 1 else "viewport outliers"
        return f"{outlier_count} {outlier_label}; no stored outlier details"

    outlier_label = "viewport outlier" if outlier_count == 1 else "viewport outliers"
    summary = format_geometry_outlier_compact(strongest)
    graph_hash = str(report.get("graph_hash") or "").strip()
    target_anchor = anchor or (geometry_diagnostics_anchor(graph_hash) if graph_hash else None)
    if target_anchor:
        return f"{outlier_count} {outlier_label}; strongest {summary}: [details](#{target_anchor})"
    return f"{outlier_count} {outlier_label}; strongest {summary}"


def geometry_outlier_count(diagnostics: dict) -> int:
    try:
        return int(diagnostics.get("outlier_count", 0))
    except (TypeError, ValueError):
        return 0


def strongest_geometry_outlier(diagnostics: dict) -> dict | None:
    outliers = diagnostics.get("outliers")
    if not isinstance(outliers, list):
        return None
    candidates = [outlier for outlier in outliers if isinstance(outlier, dict)]
    if not candidates:
        return None
    return min(candidates, key=geometry_outlier_sort_key)


def geometry_outlier_sort_key(outlier: dict) -> tuple[float, int, str]:
    return (
        -geometry_outlier_max_overshoot(outlier),
        geometry_outlier_order(outlier),
        str(outlier.get("expr_id") or ""),
    )


def geometry_outlier_max_overshoot(outlier: dict) -> float:
    try:
        return float(outlier.get("max_viewport_overshoot", 0.0))
    except (TypeError, ValueError):
        return 0.0


def geometry_outlier_order(outlier: dict) -> int:
    try:
        return int(outlier.get("order", 0))
    except (TypeError, ValueError):
        return 0


def format_geometry_outlier_compact(outlier: dict) -> str:
    expr_id = str(outlier.get("expr_id") or "unknown")
    axes = format_geometry_outlier_axes(outlier)
    if axes:
        return f"expr `{expr_id}`: {axes}"
    return f"expr `{expr_id}`"


def format_geometry_outlier_detail(outlier: dict) -> str:
    expr_id = str(outlier.get("expr_id") or "unknown")
    prim_name = str(outlier.get("prim_name") or "unknown prim")
    kind = str(outlier.get("kind") or "unknown kind")
    max_overshoot = format_bound_value(geometry_outlier_max_overshoot(outlier))
    axes = format_geometry_outlier_axes(outlier) or "axis details unavailable"
    return f"expr `{expr_id}` (`{prim_name}`, {kind}): max overshoot {max_overshoot}; {axes}"


def format_geometry_bbox(bbox: object) -> str:
    if not isinstance(bbox, dict):
        return "not recorded"
    parts = []
    for key in ("min", "max", "span"):
        values = bbox.get(key)
        if not is_sequence_length(values, 3):
            return "not recorded"
        parts.append(f"{key} {format_float_sequence(values)}")
    return ", ".join(parts)


def format_geometry_outlier_axis_direction_summary(diagnostics: dict) -> str:
    outliers = diagnostics.get("outliers")
    if not isinstance(outliers, list):
        return "not recorded"

    stats: dict[str, dict[str, dict[str, float | int]]] = {}
    for outlier in outliers:
        if not isinstance(outlier, dict):
            continue
        outside_axes = outlier.get("outside_viewport_axes")
        if not isinstance(outside_axes, list):
            continue
        for item in outside_axes:
            if not isinstance(item, dict):
                continue
            axis = str(item.get("axis") or "?")
            axis_stats = stats.setdefault(axis, {})
            for direction, key in (("low", "low_overshoot"), ("high", "high_overshoot")):
                overshoot = positive_float(item.get(key))
                if overshoot <= 0:
                    continue
                direction_stats = axis_stats.setdefault(direction, {"count": 0, "max": 0.0})
                direction_stats["count"] = int(direction_stats["count"]) + 1
                direction_stats["max"] = max(float(direction_stats["max"]), overshoot)

    if not stats:
        return "not recorded"

    axis_order = {"x": 0, "y": 1, "z": 2}

    def axis_sort_key(axis: str) -> tuple[int, int, str]:
        total_count = sum(int(direction_stats["count"]) for direction_stats in stats[axis].values())
        return (-total_count, axis_order.get(axis, len(axis_order)), axis)

    def direction_sort_key(direction: str) -> tuple[int, str]:
        return (0 if direction == "low" else 1 if direction == "high" else 2, direction)

    parts = []
    for axis in sorted(stats, key=axis_sort_key):
        direction_parts = []
        for direction in sorted(stats[axis], key=direction_sort_key):
            direction_stats = stats[axis][direction]
            direction_parts.append(
                f"{direction} {int(direction_stats['count'])} "
                f"(max {format_bound_value(direction_stats['max'])})"
            )
        parts.append(f"{axis} {', '.join(direction_parts)}")
    return "; ".join(parts)


def format_geometry_outlier_axes(outlier: dict) -> str:
    outside_axes = outlier.get("outside_viewport_axes")
    if not isinstance(outside_axes, list):
        return ""

    formatted_axes = []
    for item in outside_axes:
        if not isinstance(item, dict):
            continue
        axis = str(item.get("axis") or "?")
        direction_parts = []
        low_overshoot = positive_float(item.get("low_overshoot"))
        high_overshoot = positive_float(item.get("high_overshoot"))
        if low_overshoot > 0:
            direction_parts.append(f"low {format_bound_value(low_overshoot)}")
        if high_overshoot > 0:
            direction_parts.append(f"high {format_bound_value(high_overshoot)}")
        if not direction_parts:
            continue

        margin = positive_float(item.get("threshold_margin"))
        margin_part = f" (margin {format_bound_value(margin)})" if margin > 0 else ""
        formatted_axes.append(f"{axis} {', '.join(direction_parts)}{margin_part}")
    return "; ".join(formatted_axes)


def positive_float(value: object) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(numeric, 0.0)


def geometry_diagnostics_anchor(graph_hash: str) -> str:
    stable_hash = "".join(
        character if character.isalnum() or character in "-_" else "-"
        for character in graph_hash.lower()
    ).strip("-")
    return f"geometry-diagnostics-{stable_hash or 'sample'}"


def geometry_diagnostics_anchors(reports: list[dict]) -> list[str | None]:
    anchors: list[str | None] = []
    used_anchors: set[str] = set()
    for report in reports:
        diagnostics = report.get("geometry_diagnostics")
        if not isinstance(diagnostics, dict) or geometry_outlier_count(diagnostics) == 0:
            anchors.append(None)
            continue

        graph_hash = str(report.get("graph_hash") or "sample")
        base_anchor = geometry_diagnostics_anchor(graph_hash)
        anchor = base_anchor
        suffix = 2
        while anchor in used_anchors:
            anchor = f"{base_anchor}-{suffix}"
            suffix += 1
        used_anchors.add(anchor)
        anchors.append(anchor)
    return anchors


def geometry_diagnostics_details_section(
    reports: list[dict],
    anchors: list[str | None] | None = None,
    detail_limit: int = GEOMETRY_OUTLIER_DETAIL_LIMIT,
) -> list[str]:
    if anchors is None:
        anchors = geometry_diagnostics_anchors(reports)
    lines: list[str] = []
    for index, report in enumerate(reports):
        diagnostics = report.get("geometry_diagnostics")
        if not isinstance(diagnostics, dict) or geometry_outlier_count(diagnostics) == 0:
            continue

        outliers = diagnostics.get("outliers")
        if not isinstance(outliers, list):
            continue
        sorted_outliers = sorted(
            [outlier for outlier in outliers if isinstance(outlier, dict)],
            key=geometry_outlier_sort_key,
        )
        if not sorted_outliers:
            continue

        graph_hash = str(report.get("graph_hash") or "sample")
        anchor = anchors[index] if index < len(anchors) and anchors[index] else geometry_diagnostics_anchor(graph_hash)
        if not lines:
            lines.extend(["## Geometry Diagnostics Details", ""])
        lines.extend(
            [
                f'<a id="{anchor}"></a>',
                f"### {graph_hash}",
                "",
                f"- outlier rule: {diagnostics.get('outlier_rule', 'not recorded')}",
                f"- frozen source viewport bbox: {format_geometry_bbox(diagnostics.get('source_viewport_bbox'))}",
                f"- report global bbox: {format_geometry_bbox(diagnostics.get('global_bbox'))}",
                f"- outlier axis/direction summary: {format_geometry_outlier_axis_direction_summary(diagnostics)}",
            ]
        )
        shown = sorted_outliers if len(sorted_outliers) <= detail_limit else sorted_outliers[:detail_limit]
        lines.extend(f"- {format_geometry_outlier_detail(outlier)}" for outlier in shown)
        omitted_count = max(len(sorted_outliers) - len(shown), 0)
        if omitted_count:
            lines.append(f"- {omitted_count} additional viewport outliers omitted from this section")
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def format_unsupported_contradiction(contradiction: dict) -> str | None:
    axis = contradiction.get("axis")
    lower = contradiction.get("lower")
    upper = contradiction.get("upper")
    if not isinstance(axis, str) or not isinstance(lower, dict) or not isinstance(upper, dict):
        return None
    lower_value = format_bound_value(lower.get("value"))
    upper_value = format_bound_value(upper.get("value"))
    return (
        f"axis {axis} contradiction: "
        f"lower bound {lower_value} from `{lower.get('predicate', 'unknown')}` "
        f"is above upper bound {upper_value} from `{upper.get('predicate', 'unknown')}`"
    )


def format_bound_value(value: object) -> str:
    try:
        return format_view_float(value)
    except (TypeError, ValueError):
        return str(value)


def annotate_report_unsupported_source_triage(
    report: dict,
    url: str,
    project_root: Path,
    refresh: bool = False,
) -> dict:
    annotated = dict(report)
    unsupported = report.get("unsupported")
    if not isinstance(unsupported, list):
        annotated["unsupported_source_triage"] = summarize_unsupported_source_triage(
            unsupported,
            report_unsupported_count(report),
        )
        return annotated

    triage_by_expr_id = source_triage_by_expr_id(url, project_root, refresh=refresh)
    annotated_unsupported = []
    for item in unsupported:
        if not isinstance(item, dict):
            annotated_unsupported.append(item)
            continue
        annotated_item = dict(item)
        expr_id = str(annotated_item.get("expr_id") or "")
        annotated_item["source_triage"] = triage_by_expr_id.get(expr_id, residual_limitation_triage())
        annotated_unsupported.append(annotated_item)
    annotated["unsupported"] = annotated_unsupported
    annotated["unsupported_source_triage"] = summarize_unsupported_source_triage(
        annotated_unsupported,
        report_unsupported_count(annotated),
    )
    return annotated


def source_triage_by_expr_id(url: str, project_root: Path, refresh: bool = False) -> dict[str, dict]:
    state = load_state_for_url(url, project_root=project_root, refresh=refresh)
    graph = graph_ir_from_state(state)
    classification = classify_graph(graph)
    return {
        item.ir.expr_id: source_triage_for_classified_expression(item, classification.context)
        for item in classification.classified
    }


def source_triage_for_classified_expression(item: ClassifiedExpression, context: Any) -> dict:
    contradictions = constant_axis_bound_contradictions(item.predicates, context)
    if contradictions:
        return {
            "classification": SOURCE_TRIAGE_CONTRADICTORY,
            "reason": "source predicates have an empty constant axis interval",
            "contradictions": contradictions,
        }
    return residual_limitation_triage()


def residual_limitation_triage() -> dict:
    return {
        "classification": SOURCE_TRIAGE_RESIDUAL_LIMITATION,
        "reason": "no source-side constant bound contradiction was detected",
        "contradictions": [],
    }


def constant_axis_bound_contradictions(predicates: list[ComparisonPredicate], context: Any) -> list[dict]:
    by_axis: dict[str, dict[str, list[dict]]] = {
        axis: {"lower": [], "upper": []}
        for axis in ("x", "y", "z")
    }
    for predicate in predicates:
        for contribution in constant_axis_bound_contributions(predicate, context):
            by_axis[contribution["axis"]][contribution["side"]].append(contribution)

    contradictions = []
    for axis in ("x", "y", "z"):
        lower_bounds = by_axis[axis]["lower"]
        upper_bounds = by_axis[axis]["upper"]
        if not lower_bounds or not upper_bounds:
            continue
        strongest_lower = max(lower_bounds, key=lambda bound: (bound["value"], bound["predicate"]))
        strongest_upper = min(upper_bounds, key=lambda bound: (bound["value"], bound["predicate"]))
        empty_from_order = strongest_lower["value"] > strongest_upper["value"] + 1e-9
        empty_from_strict_point = (
            abs(strongest_lower["value"] - strongest_upper["value"]) <= 1e-9
            and (not strongest_lower["inclusive"] or not strongest_upper["inclusive"])
        )
        if empty_from_order or empty_from_strict_point:
            contradictions.append(
                {
                    "axis": axis,
                    "kind": "empty_constant_interval",
                    "lower": bound_evidence(strongest_lower),
                    "upper": bound_evidence(strongest_upper),
                }
            )
    return contradictions


def constant_axis_bound_contributions(predicate: ComparisonPredicate, context: Any) -> list[dict]:
    if len(predicate.terms) == 3 and len(predicate.ops) == 2:
        middle = single_identifier(predicate.terms[1])
        if middle in {"x", "y", "z"} and predicate.ops[0] in {"<=", "<"} and predicate.ops[1] in {"<=", "<"}:
            lower = evaluated_bound(predicate.terms[0], context)
            upper = evaluated_bound(predicate.terms[2], context)
            if lower is not None and upper is not None:
                return [
                    bound_contribution(middle, "lower", lower, predicate, predicate.ops[0] == "<="),
                    bound_contribution(middle, "upper", upper, predicate, predicate.ops[1] == "<="),
                ]
        if middle in {"x", "y", "z"} and predicate.ops[0] in {">=", ">"} and predicate.ops[1] in {">=", ">"}:
            upper = evaluated_bound(predicate.terms[0], context)
            lower = evaluated_bound(predicate.terms[2], context)
            if lower is not None and upper is not None:
                return [
                    bound_contribution(middle, "lower", lower, predicate, predicate.ops[1] == ">="),
                    bound_contribution(middle, "upper", upper, predicate, predicate.ops[0] == ">="),
                ]

    if len(predicate.terms) == 2 and len(predicate.ops) == 1:
        left_id = single_identifier(predicate.terms[0])
        right_id = single_identifier(predicate.terms[1])
        op = predicate.ops[0]
        if left_id in {"x", "y", "z"}:
            value = evaluated_bound(predicate.terms[1], context)
            if value is None:
                return []
            if op in {"<=", "<"}:
                return [bound_contribution(left_id, "upper", value, predicate, op == "<=")]
            if op in {">=", ">"}:
                return [bound_contribution(left_id, "lower", value, predicate, op == ">=")]
        if right_id in {"x", "y", "z"}:
            value = evaluated_bound(predicate.terms[0], context)
            if value is None:
                return []
            if op in {"<=", "<"}:
                return [bound_contribution(right_id, "lower", value, predicate, op == "<=")]
            if op in {">=", ">"}:
                return [bound_contribution(right_id, "upper", value, predicate, op == ">=")]
    return []


def evaluated_bound(expression: Any, context: Any) -> float | None:
    try:
        return float(expression.eval(context, {}))
    except Exception:
        return None


def bound_contribution(axis: str, side: str, value: float, predicate: ComparisonPredicate, inclusive: bool) -> dict:
    return {
        "axis": axis,
        "side": side,
        "value": value,
        "predicate": predicate.raw,
        "inclusive": inclusive,
    }


def bound_evidence(bound: dict) -> dict:
    return {
        "value": bound["value"],
        "predicate": bound["predicate"],
        "inclusive": bound["inclusive"],
    }


def report_unsupported_count(report: dict) -> int:
    if "unsupported_count" in report:
        return int(report["unsupported_count"])
    unsupported = report.get("unsupported")
    if isinstance(unsupported, list):
        return len(unsupported)
    try:
        renderable_count = int(report["renderable_expression_count"])
        prim_count = int(report["prim_count"])
    except KeyError as exc:
        raise ValueError(f"Report cannot derive unsupported_count without {exc.args[0]!r}") from exc
    return max(renderable_count - prim_count, 0)


def report_renderable_expression_count(report: dict) -> int | None:
    try:
        return int(report["renderable_expression_count"])
    except (KeyError, TypeError, ValueError):
        return None


def renderable_count_consistency_cell(stored_count: int | None, frozen_count: int) -> str:
    if stored_count is None:
        return "report count missing"
    if stored_count == frozen_count:
        return "matches frozen fixture"
    return f"stale report count: report {stored_count}, frozen fixture {frozen_count}"


def build_summary(reports: list[dict], expected_urls: list[str] | None = None) -> dict:
    if expected_urls is not None and len(reports) != len(expected_urls):
        raise ValueError("Report count does not match required sample count")
    normalized_reports = [
        normalized_report(report, expected_urls[index] if expected_urls is not None else None)
        for index, report in enumerate(reports)
    ]
    count_matches: list[bool] = []
    if expected_urls is not None:
        frozen_metadata = load_frozen_sample_metadata(expected_urls)
        for report, expected_url in zip(normalized_reports, expected_urls, strict=True):
            frozen_renderable_count = int(frozen_metadata[expected_url]["renderable_expression_count"])
            stored_renderable_count = report_renderable_expression_count(report)
            count_matches_current = stored_renderable_count == frozen_renderable_count
            count_matches.append(count_matches_current)
            report["current_frozen_fixture_renderable_expression_count"] = frozen_renderable_count
            report["renderable_expression_count_matches_current_frozen_fixture"] = count_matches_current
            report["stale_report"] = not count_matches_current
            report["report_count_check"] = renderable_count_consistency_cell(
                stored_renderable_count,
                frozen_renderable_count,
            )
    stale_report_count = sum(1 for matches in count_matches if not matches)
    return {
        "sample_count": len(normalized_reports),
        "all_valid": all(report["valid"] for report in normalized_reports),
        "all_complete": all(report["complete"] for report in normalized_reports),
        "all_report_counts_match_current_frozen_fixture": all(count_matches) if expected_urls is not None else None,
        "stale_report_count": stale_report_count,
        "unsupported_count": sum(report["unsupported_count"] for report in normalized_reports),
        "geometry_diagnostics_summary": build_geometry_diagnostics_summary(normalized_reports),
        "reports": normalized_reports,
    }


def build_geometry_diagnostics_summary(reports: list[dict]) -> dict[str, object]:
    recorded: list[str] = []
    missing: list[str] = []
    zero_outliers: list[str] = []
    with_outliers: list[str] = []
    outlier_counts: dict[str, int] = {}

    for report in reports:
        graph_hash = str(report.get("graph_hash") or "unknown").strip() or "unknown"
        diagnostics = report.get("geometry_diagnostics")
        if not isinstance(diagnostics, dict):
            missing.append(graph_hash)
            continue

        outlier_count = geometry_outlier_count(diagnostics)
        recorded.append(graph_hash)
        outlier_counts[graph_hash] = outlier_count
        if outlier_count == 0:
            zero_outliers.append(graph_hash)
        else:
            with_outliers.append(graph_hash)

    return {
        "required_report_count": len(reports),
        "recorded_report_count": len(recorded),
        "missing_report_count": len(missing),
        "zero_outlier_report_count": len(zero_outliers),
        "outlier_report_count": len(with_outliers),
        "total_outlier_count": sum(outlier_counts.values()),
        "reports_with_diagnostics": recorded,
        "reports_missing_diagnostics": missing,
        "reports_with_zero_outliers": zero_outliers,
        "reports_with_outliers": with_outliers,
        "outlier_counts_by_report": outlier_counts,
    }


def markdown_cell(value: object) -> str:
    text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def markdown_link(label: str, target: str) -> str:
    return f"[{markdown_cell(label)}]({target.replace(')', '%29')})"


def artifact_presence_cell(paths: dict[str, Path]) -> str:
    return "<br>".join(
        f"{label} {'present' if path.exists() else 'missing'}"
        for label, path in paths.items()
    )


def absolute_path(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()


def relative_url_path(target: Path, start_dir: Path) -> str:
    return Path(os.path.relpath(target, start_dir)).as_posix()


def report_output_path(report: dict, graph_hash: str, compare_sheet_dir: Path) -> Path:
    output = report.get("output")
    if isinstance(output, str) and output.strip():
        return absolute_path(Path(output))
    return (compare_sheet_dir / f"{graph_hash}.usda").resolve()


def compare_artifact_paths(report: dict, graph_hash: str, compare_sheet_dir: Path) -> dict[str, Path]:
    usda_path = report_output_path(report, graph_hash, compare_sheet_dir)
    return {
        "usda": usda_path,
        "ppm": usda_path.with_suffix(".ppm"),
        "report": compare_sheet_dir / f"{graph_hash}.report.json",
    }


def display_path(path: Path, root: Path | None = None) -> str:
    base = absolute_path(root or Path.cwd())
    resolved = absolute_path(path)
    try:
        return resolved.relative_to(base).as_posix()
    except ValueError:
        return resolved.as_posix()


def resolve_viewer_usda_link(usda_path: Path, compare_sheet_path: Path, project_root: Path) -> dict[str, object]:
    href = viewer_deep_link(usda_path, compare_sheet_path, project_root)
    query = parse_qs(urlsplit(href).query, keep_blank_values=True)
    query_paths = query.get("usda", [])
    expected_path = absolute_path(usda_path)
    result: dict[str, object] = {
        "href": href,
        "expected_path": display_path(expected_path),
        "matches_expected": False,
        "target_exists": False,
    }
    if len(query_paths) != 1 or not query_paths[0]:
        result["error"] = "viewer link does not contain exactly one non-empty usda query path"
        return result

    usda_query_path = query_paths[0]
    target_path = absolute_path(project_root / "viewer" / usda_query_path)
    result.update(
        {
            "usda_query_path": usda_query_path,
            "target_path": display_path(target_path),
            "matches_expected": target_path == expected_path,
            "target_exists": target_path.exists(),
        }
    )
    return result


def verify_compare_artifacts(out_dir: Path, expected_urls: list[str]) -> dict:
    compare_sheet_dir = absolute_path(out_dir)
    compare_sheet_path = compare_sheet_dir / COMPARE_SHEET_FILENAME
    project_root = absolute_path(project_root_from_cwd())
    frozen_metadata = load_frozen_sample_metadata(expected_urls, project_root)
    samples = []
    missing_count = 0
    error_count = 0

    for url in expected_urls:
        graph_hash = sample_hash(url)
        report_path = compare_sheet_dir / f"{graph_hash}.report.json"
        report: dict[str, Any] = {}
        errors = []
        stored_renderable_count = None
        frozen_renderable_count = int(frozen_metadata[url]["renderable_expression_count"])

        if report_path.exists():
            try:
                loaded = json.loads(report_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"report JSON is invalid: {exc.msg}")
            else:
                if isinstance(loaded, dict):
                    report = loaded
                    actual_hash = str(report.get("graph_hash") or graph_hash)
                    if actual_hash != graph_hash:
                        errors.append(f"report graph_hash {actual_hash!r} does not match required sample {graph_hash!r}")
                    stored_renderable_count = report_renderable_expression_count(report)
                    if stored_renderable_count is None:
                        errors.append("report renderable_expression_count is missing or not an integer")
                    elif stored_renderable_count != frozen_renderable_count:
                        errors.append(
                            "report renderable_expression_count "
                            f"{stored_renderable_count} does not match current frozen fixture renderable count "
                            f"{frozen_renderable_count}"
                        )
                else:
                    errors.append("report is not a JSON object")

        paths = compare_artifact_paths(report, graph_hash, compare_sheet_dir)
        viewer_link = resolve_viewer_usda_link(paths["usda"], compare_sheet_path, project_root)
        artifacts = {}
        missing = []
        for name in ("usda", "ppm", "report"):
            path = paths[name]
            present = path.exists()
            artifacts[name] = {
                "path": display_path(path),
                "present": present,
            }
            if not present:
                missing.append(name)

        if not viewer_link["target_exists"] and "usda" not in missing:
            missing.append("viewer_usda_link_target")
        if not viewer_link["matches_expected"]:
            errors.append("viewer USDA link target does not match expected USDA artifact")
        if "error" in viewer_link:
            errors.append(str(viewer_link["error"]))

        missing_count += len(missing)
        if errors:
            error_count += len(errors)

        sample = {
            "graph_hash": graph_hash,
            "artifacts": artifacts,
            "viewer_link": viewer_link,
            "renderable_expression_count_check": {
                "stored_report": stored_renderable_count,
                "current_frozen_fixture": frozen_renderable_count,
                "matches_current_frozen_fixture": stored_renderable_count == frozen_renderable_count,
            },
        }
        if missing:
            sample["missing"] = missing
        if errors:
            sample["errors"] = errors
        samples.append(sample)

    return {
        "ok": missing_count == 0 and error_count == 0,
        "sample_count": len(samples),
        "missing_count": missing_count,
        "error_count": error_count,
        "samples": samples,
    }


def viewer_deep_link(usda_path: Path, compare_sheet_path: Path, project_root: Path) -> str:
    viewer_dir = project_root / "viewer"
    viewer_href = relative_url_path(viewer_dir, compare_sheet_path.parent)
    usda_query_path = relative_url_path(usda_path, viewer_dir)
    return f"{viewer_href}/?usda={quote(usda_query_path, safe='')}"


def repo_relative_url_path(path: Path, project_root: Path) -> str | None:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return None


def serving_note(compare_sheet_path: Path, project_root: Path, usda_paths: list[Path]) -> str:
    compare_url_path = repo_relative_url_path(compare_sheet_path, project_root)
    all_usda_under_root = all(repo_relative_url_path(path, project_root) is not None for path in usda_paths)
    if compare_url_path is None or not all_usda_under_root:
        return (
            "- Serve a directory that contains `viewer/` and the generated artifacts for viewer links. "
            "This compare sheet or at least one linked USDA is outside the repository root, so a repo-root URL "
            "cannot serve every generated link."
        )
    return (
        "- Serve the repository root for viewer links: run `python3 -m http.server 8765` from the repo root "
        f"and open `http://localhost:8765/{compare_url_path}`. The relative `usda` links rely on `viewer/` "
        "and the generated artifacts both being served from that repo-root layout."
    )


def build_compare_sheet(
    reports: list[dict],
    expected_urls: list[str],
    project_root: Path | None = None,
    compare_sheet_path: Path | None = None,
) -> str:
    if len(reports) != len(expected_urls):
        raise ValueError("Report count does not match required sample count")

    root = absolute_path(project_root or project_root_from_cwd())
    sheet_path = absolute_path(compare_sheet_path or Path(COMPARE_SHEET_FILENAME))
    compare_sheet_dir = sheet_path.parent
    normalized_reports = [
        normalized_report(report, expected_urls[index])
        for index, report in enumerate(reports)
    ]
    unsupported_detail_anchors = unsupported_evidence_anchors(normalized_reports)
    geometry_detail_anchors = geometry_diagnostics_anchors(normalized_reports)
    frozen_metadata = load_frozen_sample_metadata(expected_urls, root)
    usda_paths: list[Path] = []
    lines = [
        f"# {COMPARE_SHEET_TITLE}",
        "",
        "Manual compare scaffold generated from the five frozen required Desmos 3D samples.",
        "This sheet links each real Desmos sample to local acceptance artifacts for human side-by-side review.",
        "Frozen view metadata is read from the in-repo required sample states and is provided only to set up the manual comparison.",
        "It is not proof of visual parity, and it does not claim the USDA/PPM render matches Desmos.",
        "",
        "| sample | Desmos 3D sample | viewer USDA | local USDA | local PPM | report | artifact presence | frozen Desmos view | geometry diagnostics | report renderables | frozen fixture renderables | report count check | valid | complete | prims | unsupported | unsupported triage | unsupported evidence |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for index, report in enumerate(normalized_reports):
        graph_hash = str(report["graph_hash"])
        url = str(report["url"])
        frozen_renderable_count = int(frozen_metadata[url]["renderable_expression_count"])
        stored_renderable_count = report_renderable_expression_count(report)
        artifact_paths = compare_artifact_paths(report, graph_hash, compare_sheet_dir)
        usda_path = artifact_paths["usda"]
        ppm_path = artifact_paths["ppm"]
        report_path = artifact_paths["report"]
        usda_paths.append(usda_path)
        row = [
            markdown_cell(graph_hash),
            markdown_link(url, url),
            markdown_link("open USDA", viewer_deep_link(usda_path, sheet_path, root)),
            markdown_link(usda_path.name, relative_url_path(usda_path, compare_sheet_dir)),
            markdown_link(ppm_path.name, relative_url_path(ppm_path, compare_sheet_dir)),
            markdown_link(report_path.name, relative_url_path(report_path, compare_sheet_dir)),
            markdown_cell(
                artifact_presence_cell(
                    {
                        "USDA": artifact_paths["usda"],
                        "PPM": artifact_paths["ppm"],
                        "report": artifact_paths["report"],
                    }
                )
            ),
            markdown_cell(format_view_metadata(frozen_metadata.get(url, {}).get("view_metadata", {}))),
            markdown_cell(geometry_diagnostics_cell(report, geometry_detail_anchors[index])),
            markdown_cell(stored_renderable_count if stored_renderable_count is not None else "missing"),
            markdown_cell(frozen_renderable_count),
            markdown_cell(renderable_count_consistency_cell(stored_renderable_count, frozen_renderable_count)),
            markdown_cell(str(report["valid"]).lower()),
            markdown_cell(str(report["complete"]).lower()),
            markdown_cell(report["prim_count"]),
            markdown_cell(report["unsupported_count"]),
            markdown_cell(unsupported_triage_cell(report)),
            markdown_cell(unsupported_evidence_cell(report, unsupported_detail_anchors[index])),
        ]
        lines.append("| " + " | ".join(row) + " |")

    geometry_detail_lines = geometry_diagnostics_details_section(normalized_reports, geometry_detail_anchors)
    if geometry_detail_lines:
        lines.extend(["", *geometry_detail_lines])

    unsupported_detail_lines = unsupported_evidence_details_section(normalized_reports, unsupported_detail_anchors)
    if unsupported_detail_lines:
        lines.extend(["", *unsupported_detail_lines])

    lines.extend(
        [
            "",
            "Review notes:",
            "",
            "- Use this artifact to open the Desmos source and the local USDA/PPM artifacts for manual comparison.",
            serving_note(sheet_path, root, usda_paths),
            "- Re-check artifact freshness without regenerating this sheet: run `PYTHONPATH=src python3 -m desmos2usd.validate.sample_suite --out artifacts/acceptance --verify-artifacts`; fix any `missing` item before manual comparison.",
            "- The frozen view cell records Desmos viewport and world rotation values from `fixtures/states/*.json`; it is setup context, not a rendering verdict.",
            "- Geometry diagnostics are copied from existing report `geometry_diagnostics` fields and flag stored prim bounding boxes outside the frozen viewport margin; they are manual-diagnosis aids, not visual parity verdicts.",
            "- The frozen fixture renderable count is recomputed from `fixtures/states/*.json` with the current classifier. A mismatch is a stale-report consistency signal, not proof of visual mismatch.",
            "- Unsupported evidence is copied from report `source_triage` entries and is limited to the unsupported rows already present in the required sample reports.",
            "- `valid` and `complete` are export/validation signals from the generated reports, not visual parity verdicts.",
            "- The row set is intentionally limited to the frozen required samples; extra report files are ignored.",
            "",
        ]
    )
    return "\n".join(lines)


def write_summary(out_dir: Path, summary: dict) -> None:
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_frozen_sample_metadata(expected_urls: list[str], project_root: Path | None = None) -> dict[str, dict[str, Any]]:
    root = project_root or project_root_from_cwd()
    metadata_by_url: dict[str, dict[str, Any]] = {}
    for url in expected_urls:
        graph = graph_ir_from_state(load_fixture_state(url, root))
        metadata_by_url[url] = {
            "view_metadata": graph.source.view_metadata,
            "renderable_expression_count": len(classify_graph(graph).classified),
        }
    return metadata_by_url


def load_frozen_view_metadata(expected_urls: list[str], project_root: Path | None = None) -> dict[str, dict[str, Any]]:
    return {
        url: metadata["view_metadata"]
        for url, metadata in load_frozen_sample_metadata(expected_urls, project_root).items()
    }


def format_view_metadata(metadata: dict[str, Any]) -> str:
    parts = []
    viewport_bounds = metadata.get("viewport_bounds")
    if isinstance(viewport_bounds, dict):
        axis_parts = []
        for axis in ("x", "y", "z"):
            bounds = viewport_bounds.get(axis)
            if is_pair(bounds):
                axis_parts.append(f"{axis}[{format_view_float(bounds[0])}, {format_view_float(bounds[1])}]")
        if axis_parts:
            parts.append("viewport " + " ".join(axis_parts))

    world_rotation = metadata.get("world_rotation_3d")
    if is_sequence_length(world_rotation, 9):
        parts.append("worldRotation3D " + format_float_sequence(world_rotation))

    axis = metadata.get("axis_3d")
    if is_sequence_length(axis, 3):
        parts.append("axis3D " + format_float_sequence(axis))

    flags = []
    if isinstance(metadata.get("three_d_mode"), bool):
        flags.append(f"threeDMode={str(metadata['three_d_mode']).lower()}")
    if isinstance(metadata.get("show_plane_3d"), bool):
        flags.append(f"showPlane3D={str(metadata['show_plane_3d']).lower()}")
    if flags:
        parts.append("; ".join(flags))

    return "<br>".join(parts) if parts else "unavailable"


def is_pair(value: object) -> bool:
    return isinstance(value, list | tuple) and len(value) == 2


def is_sequence_length(value: object, length: int) -> bool:
    return isinstance(value, list | tuple) and len(value) == length


def format_float_sequence(values: object) -> str:
    if not isinstance(values, list | tuple):
        return "[]"
    return "[" + ", ".join(format_view_float(value) for value in values) + "]"


def format_view_float(value: object) -> str:
    numeric = float(value)
    if abs(numeric) < 1e-10:
        numeric = 0.0
    return f"{numeric:.6g}"


def write_compare_sheet(out_dir: Path, reports: list[dict], expected_urls: list[str]) -> str:
    compare_sheet_path = out_dir / COMPARE_SHEET_FILENAME
    compare_sheet = build_compare_sheet(reports, expected_urls, compare_sheet_path=compare_sheet_path)
    compare_sheet_path.write_text(compare_sheet, encoding="utf-8")
    return compare_sheet


def write_summary_for_reports(out_dir: Path, reports: list[dict], expected_urls: list[str] | None = None) -> dict:
    summary = build_summary(reports, expected_urls)
    write_summary(out_dir, summary)
    return summary


def regenerate_summary_from_reports(out_dir: Path) -> dict:
    return write_summary_for_reports(out_dir, load_required_reports(out_dir), REQUIRED_SAMPLE_URLS)


def regenerate_compare_sheet_from_reports(out_dir: Path) -> str:
    return write_compare_sheet(out_dir, load_required_reports(out_dir), REQUIRED_SAMPLE_URLS)


def export_required_sample(
    url: str,
    out_dir: Path,
    project_root: Path,
    refresh: bool,
    resolution: int,
) -> dict:
    graph_hash = sample_hash(url)
    output = out_dir / f"{graph_hash}.usda"
    report = convert_url(
        url,
        output,
        project_root=project_root,
        refresh=refresh,
        resolution=resolution,
        write_preview=True,
    )
    report_dict = report.__dict__
    report_dict = annotate_report_unsupported_source_triage(report_dict, url, project_root, refresh=refresh)
    report_path = out_dir / f"{graph_hash}.report.json"
    report_path.write_text(json.dumps(report_dict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report_dict


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    if sum([args.summary_only, args.compare_sheet_only, args.verify_artifacts]) > 1:
        parser.error("--summary-only, --compare-sheet-only, and --verify-artifacts are mutually exclusive")
    if args.sample and any([args.summary_only, args.compare_sheet_only, args.verify_artifacts]):
        parser.error("--sample can only be used when exporting acceptance artifacts")
    if args.summary_only:
        summary = regenerate_summary_from_reports(out_dir)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0 if summary["all_valid"] else 1
    if args.compare_sheet_only:
        compare_sheet = regenerate_compare_sheet_from_reports(out_dir)
        print(compare_sheet, end="")
        return 0
    if args.verify_artifacts:
        verification = verify_compare_artifacts(out_dir, REQUIRED_SAMPLE_URLS)
        print(json.dumps(verification, indent=2, sort_keys=True))
        return 0 if verification["ok"] else 1

    root = project_root_from_cwd()
    if args.sample:
        try:
            selected_urls = [resolve_required_sample_url(args.sample, REQUIRED_SAMPLE_URLS)]
        except ValueError as exc:
            parser.error(str(exc))
    else:
        selected_urls = REQUIRED_SAMPLE_URLS

    reports = [
        export_required_sample(
            url,
            out_dir,
            project_root=root,
            refresh=args.refresh,
            resolution=args.resolution,
        )
        for url in selected_urls
    ]
    if args.sample:
        reports = load_required_reports(out_dir)
    summary = write_summary_for_reports(out_dir, reports, REQUIRED_SAMPLE_URLS)
    write_compare_sheet(out_dir, reports, REQUIRED_SAMPLE_URLS)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["all_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
