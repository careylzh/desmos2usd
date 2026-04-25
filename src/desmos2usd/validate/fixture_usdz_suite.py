from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from desmos2usd.converter import UnsupportedExpression, export_graph
from desmos2usd.desmos_state import project_root_from_cwd
from desmos2usd.eval.context import EvalContext
from desmos2usd.ir import ExpressionIR, GraphIR, graph_ir_from_state
from desmos2usd.parse.classify import (
    ClassificationResult,
    classify_expression,
    expand_list_expression,
    register_definition,
    resolve_color_latex,
)
from desmos2usd.usd.package import package_usdz, validate_usdz_arkit

SUMMARY_FILENAME = "summary.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a local USDZ sweep over fixture JSON files")
    parser.add_argument("--out", default="artifacts/fixture_usdz", help="Output artifact directory")
    parser.add_argument("--resolution", type=int, default=8)
    parser.add_argument("--limit", type=int, help="Optional max number of fixtures to process")
    parser.add_argument(
        "--fixture",
        action="append",
        dest="fixtures",
        help="Exact fixture filename to process (repeatable). Defaults to all fixtures/states/*.json files.",
    )
    parser.add_argument(
        "--no-validate-usdz",
        action="store_true",
        help="Skip usdchecker --arkit after packaging .usdz files",
    )
    return parser


def artifact_stem(fixture_path: Path) -> str:
    return fixture_path.stem


def report_path_for_fixture(out_dir: Path, fixture_path: Path) -> Path:
    return out_dir / f"{artifact_stem(fixture_path)}.report.json"


def load_fixture_paths(project_root: Path, selected_names: list[str] | None = None) -> list[Path]:
    fixture_dir = project_root / "fixtures" / "states"
    all_fixtures = sorted(fixture_dir.glob("*.json"))
    if not selected_names:
        return all_fixtures

    by_name = {path.name: path for path in all_fixtures}
    missing = [name for name in selected_names if name not in by_name]
    if missing:
        available = ", ".join(path.name for path in all_fixtures)
        raise ValueError(f"Unknown fixture(s) {missing!r}; expected exact names from fixtures/states: {available}")
    return [by_name[name] for name in selected_names]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def classify_fixture_status(report: dict[str, Any]) -> str:
    if report.get("acceptance_success"):
        return "success"
    if report.get("usda_exists") or report.get("usdz_exists"):
        return "partial"
    return "error"


def artifact_display_path(path: Path, project_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def classify_graph_tolerant(graph: GraphIR) -> tuple[ClassificationResult, list[UnsupportedExpression]]:
    context = EvalContext()
    classified = []
    definitions = []
    definition_ids: set[str] = set()
    unsupported: list[UnsupportedExpression] = []

    for expr in graph.expressions:
        if expr.type != "expression" or not expr.latex.strip():
            continue
        try:
            if register_definition(expr, context):
                definition_ids.add(expr.expr_id)
                if expr.renderable_candidate:
                    definitions.append(expr)
        except Exception as exc:
            if expr.renderable_candidate:
                definition_ids.add(expr.expr_id)
                unsupported.append(
                    UnsupportedExpression(
                        expr_id=expr.expr_id,
                        kind="definition",
                        latex=expr.latex,
                        reason=f"Failed to parse definition: {exc}",
                    )
                )

    for expr in graph.expressions:
        if not expr.renderable_candidate or expr.expr_id in definition_ids:
            continue
        try:
            resolved = resolve_color_latex(expr.color_latex, context)
            effective_color = f"#{resolved[0]:02x}{resolved[1]:02x}{resolved[2]:02x}" if resolved else expr.color
            candidate = expr if effective_color == expr.color else ExpressionIR(
                source=expr.source,
                expr_id=expr.expr_id,
                order=expr.order,
                latex=expr.latex,
                color=effective_color,
                color_latex=expr.color_latex,
                hidden=expr.hidden,
                folder_id=expr.folder_id,
                type=expr.type,
                raw=expr.raw,
            )
            for expanded in expand_list_expression(candidate, context):
                try:
                    classified.append(classify_expression(expanded, context))
                except Exception as exc:
                    unsupported.append(
                        UnsupportedExpression(
                            expr_id=expanded.expr_id,
                            kind="classification",
                            latex=expanded.latex,
                            reason=str(exc),
                        )
                    )
        except Exception as exc:
            unsupported.append(
                UnsupportedExpression(
                    expr_id=expr.expr_id,
                    kind="classification",
                    latex=expr.latex,
                    reason=str(exc),
                )
            )

    return ClassificationResult(context=context, classified=classified, definitions=definitions), unsupported


def process_fixture(
    fixture_path: Path,
    project_root: Path,
    out_dir: Path,
    resolution: int,
    validate_usdz: bool,
) -> dict[str, Any]:
    stem = artifact_stem(fixture_path)
    usda_path = out_dir / f"{stem}.usda"
    usdz_path = out_dir / f"{stem}.usdz"
    report_path = report_path_for_fixture(out_dir, fixture_path)
    stage = "load"
    report: dict[str, Any] = {
        "fixture": fixture_path.name,
        "fixture_path": str(fixture_path.relative_to(project_root)),
        "output": artifact_display_path(usda_path, project_root),
        "usdz_output": artifact_display_path(usdz_path, project_root),
        "resolution": resolution,
    }

    try:
        state = json.loads(fixture_path.read_text(encoding="utf-8"))
        graph = graph_ir_from_state(state)
        report["graph_hash"] = graph.source.graph_hash or None
        report["title"] = graph.source.title

        stage = "classify"
        classification, classification_unsupported = classify_graph_tolerant(graph)
        report["renderable_expression_count"] = len(classification.classified) + len(classification_unsupported)
        report["classified_expression_count"] = len(classification.classified)

        stage = "export"
        prims, validations, export_unsupported = export_graph(graph, classification, usda_path, resolution=resolution)
        unsupported = [*classification_unsupported, *export_unsupported]
        report["prim_count"] = len(prims)
        report["unsupported_count"] = len(unsupported)
        report["valid"] = all(item.valid for item in validations)
        report["complete"] = not unsupported
        report["validations"] = [asdict(item) for item in validations]
        report["unsupported"] = [asdict(item) for item in unsupported]
        report["usda_exists"] = usda_path.exists()

        stage = "package_usdz"
        package_result = package_usdz(usda_path, usdz_path)
        report["usdz_package"] = package_result.to_dict()

        if validate_usdz:
            stage = "validate_usdz"
            validation_result = validate_usdz_arkit(usdz_path)
            report["usdz_validation"] = validation_result.to_dict()
        else:
            report["usdz_validation"] = None

        report["usda_exists"] = usda_path.exists()
        report["usdz_exists"] = usdz_path.exists()
        report["acceptance_success"] = bool(report["usdz_exists"] and report["valid"] and report["complete"])
        report["status"] = classify_fixture_status(report)
    except Exception as exc:
        report["error_stage"] = stage
        report["error_type"] = exc.__class__.__name__
        report["error"] = str(exc)
        report["usda_exists"] = usda_path.exists()
        report["usdz_exists"] = usdz_path.exists()
        report["acceptance_success"] = False
        report["status"] = classify_fixture_status(report)

    write_json(report_path, report)
    return report


def build_summary(reports: list[dict[str, Any]], out_dir: Path, project_root: Path | None = None) -> dict[str, Any]:
    counts = {"success": 0, "partial": 0, "error": 0}
    error_stage_counts: dict[str, int] = {}
    unsupported_fixture_names: list[str] = []
    for report in reports:
        status = str(report.get("status") or "error")
        counts[status] = counts.get(status, 0) + 1
        stage = report.get("error_stage")
        if isinstance(stage, str):
            error_stage_counts[stage] = error_stage_counts.get(stage, 0) + 1
        if int(report.get("unsupported_count") or 0) > 0:
            unsupported_fixture_names.append(str(report.get("fixture") or "unknown"))

    return {
        "out_dir": artifact_display_path(out_dir, project_root) if project_root is not None else str(out_dir),
        "fixture_count": len(reports),
        "success_count": counts.get("success", 0),
        "partial_count": counts.get("partial", 0),
        "error_count": counts.get("error", 0),
        "acceptance_met": len(reports) > 0 and counts.get("success", 0) == len(reports),
        "fixtures_with_usdz_count": sum(1 for report in reports if report.get("usdz_exists")),
        "unsupported_fixture_count": len(unsupported_fixture_names),
        "unsupported_fixture_names": unsupported_fixture_names,
        "error_stage_counts": error_stage_counts,
        "reports": reports,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    project_root = project_root_from_cwd()
    out_dir = (project_root / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
    fixtures = load_fixture_paths(project_root, args.fixtures)
    if args.limit is not None:
        fixtures = fixtures[: args.limit]

    reports = [
        process_fixture(
            fixture_path=fixture,
            project_root=project_root,
            out_dir=out_dir,
            resolution=args.resolution,
            validate_usdz=not args.no_validate_usdz,
        )
        for fixture in fixtures
    ]
    summary = build_summary(reports, out_dir, project_root)
    write_json(out_dir / SUMMARY_FILENAME, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
