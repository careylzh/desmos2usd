from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import quote

import _path  # noqa: F401
from desmos2usd.desmos_state import REQUIRED_SAMPLE_URLS
from desmos2usd.validate import sample_suite


class SampleSuiteSummaryTests(unittest.TestCase):
    def write_required_reports(
        self,
        out_dir: Path,
        artifact_dir: Path | None = None,
        write_artifacts: bool = False,
        renderable_count_overrides: dict[str, int] | None = None,
        geometry_diagnostics_by_hash: dict[str, dict] | None = None,
    ) -> list[dict]:
        output_dir = artifact_dir or out_dir
        frozen_metadata = sample_suite.load_frozen_sample_metadata(
            REQUIRED_SAMPLE_URLS,
            sample_suite.project_root_from_cwd(),
        )
        renderable_count_overrides = renderable_count_overrides or {}
        geometry_diagnostics_by_hash = geometry_diagnostics_by_hash or {}
        reports = []
        for index, url in enumerate(REQUIRED_SAMPLE_URLS):
            graph_hash = sample_suite.sample_hash(url)
            renderable_count = renderable_count_overrides.get(
                graph_hash,
                int(frozen_metadata[url]["renderable_expression_count"]),
            )
            usda_path = output_dir / f"{graph_hash}.usda"
            ppm_path = output_dir / f"{graph_hash}.ppm"
            report = {
                "url": "" if index == 0 else url,
                "graph_hash": "" if index == 0 else graph_hash,
                "output": str(usda_path),
                "renderable_expression_count": renderable_count,
                "prim_count": renderable_count - 1,
                "unsupported_count": 1,
                "valid": True,
                "complete": False,
                "validations": [{"expr_id": f"expr-{index}", "valid": True}],
                "unsupported": [{"expr_id": f"unsupported-{index}", "reason": "fake"}],
                "sample_index": index,
            }
            if graph_hash in geometry_diagnostics_by_hash:
                report["geometry_diagnostics"] = geometry_diagnostics_by_hash[graph_hash]
            (out_dir / f"{graph_hash}.report.json").write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            if write_artifacts:
                usda_path.write_text(f"#usda {graph_hash}\n", encoding="utf-8")
                ppm_path.write_text("P3\n1 1\n255\n0 0 0\n", encoding="utf-8")
            reports.append(report)
        return reports

    def compare_sheet_row(self, compare_sheet: str, graph_hash: str) -> str:
        row_prefix = f"| {graph_hash} |"
        for line in compare_sheet.splitlines():
            if line.startswith(row_prefix):
                return line
        self.fail(f"Missing compare sheet row for {graph_hash}")

    def compare_sheet_section(self, compare_sheet: str, heading: str) -> str:
        marker = f"### {heading}"
        start = compare_sheet.find(marker)
        if start < 0:
            self.fail(f"Missing compare sheet section for {heading}")
        next_section = compare_sheet.find("\n<a id=", start + len(marker))
        next_top_level = compare_sheet.find("\n## ", start + len(marker))
        candidates = [index for index in (next_section, next_top_level) if index >= 0]
        end = min(candidates) if candidates else len(compare_sheet)
        return compare_sheet[start:end]

    def test_summary_only_rewrites_summary_from_required_reports_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            reports = self.write_required_reports(out_dir)

            (out_dir / "summary.json").write_text('{"stale": true}\n', encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = sample_suite.main(["--out", str(out_dir), "--summary-only"])

            self.assertEqual(exit_code, 0)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["sample_count"], len(REQUIRED_SAMPLE_URLS))
            self.assertEqual(summary["all_valid"], True)
            self.assertEqual(summary["all_complete"], False)
            self.assertEqual(summary["all_report_counts_match_current_frozen_fixture"], True)
            self.assertEqual(summary["stale_report_count"], 0)
            self.assertEqual(summary["unsupported_count"], len(REQUIRED_SAMPLE_URLS))
            self.assertEqual(summary["reports"][1]["sample_index"], reports[1]["sample_index"])
            self.assertEqual(
                summary["reports"][1]["current_frozen_fixture_renderable_expression_count"],
                reports[1]["renderable_expression_count"],
            )
            self.assertEqual(summary["reports"][1]["renderable_expression_count_matches_current_frozen_fixture"], True)
            self.assertEqual(summary["reports"][1]["stale_report"], False)
            self.assertEqual(summary["reports"][1]["report_count_check"], "matches frozen fixture")
            self.assertEqual(summary["reports"][0]["graph_hash"], sample_suite.sample_hash(REQUIRED_SAMPLE_URLS[0]))
            self.assertEqual(summary["reports"][0]["url"], REQUIRED_SAMPLE_URLS[0])
            self.assertEqual(summary["reports"][0]["unsupported_source_triage"]["untriaged_count"], 1)

    def test_summary_only_reports_geometry_diagnostics_coverage_from_required_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            self.write_required_reports(
                out_dir,
                geometry_diagnostics_by_hash={
                    "ghnr7txz47": {"outlier_count": 2, "outliers": []},
                    "yuqwjsfvsc": {"outlier_count": 0, "outliers": []},
                    "k0fbxxwkqf": {"outlier_count": 11, "outliers": []},
                },
            )

            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = sample_suite.main(["--out", str(out_dir), "--summary-only"])

            self.assertEqual(exit_code, 0)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(
                summary["geometry_diagnostics_summary"],
                {
                    "required_report_count": 5,
                    "recorded_report_count": 3,
                    "missing_report_count": 2,
                    "zero_outlier_report_count": 1,
                    "outlier_report_count": 2,
                    "total_outlier_count": 13,
                    "reports_with_diagnostics": ["ghnr7txz47", "yuqwjsfvsc", "k0fbxxwkqf"],
                    "reports_missing_diagnostics": ["zaqxhna15w", "vyp9ogyimt"],
                    "reports_with_zero_outliers": ["yuqwjsfvsc"],
                    "reports_with_outliers": ["ghnr7txz47", "k0fbxxwkqf"],
                    "outlier_counts_by_report": {
                        "ghnr7txz47": 2,
                        "yuqwjsfvsc": 0,
                        "k0fbxxwkqf": 11,
                    },
                },
            )

    def test_summary_reports_real_geometry_diagnostics_coverage_from_required_reports(self) -> None:
        reports = sample_suite.load_required_reports(Path("artifacts/acceptance"))

        summary = sample_suite.build_summary(reports, REQUIRED_SAMPLE_URLS)

        self.assertEqual(
            summary["geometry_diagnostics_summary"],
            {
                "required_report_count": 5,
                "recorded_report_count": 5,
                "missing_report_count": 0,
                "zero_outlier_report_count": 4,
                "outlier_report_count": 1,
                "total_outlier_count": 11,
                "reports_with_diagnostics": ["zaqxhna15w", "ghnr7txz47", "yuqwjsfvsc", "vyp9ogyimt", "k0fbxxwkqf"],
                "reports_missing_diagnostics": [],
                "reports_with_zero_outliers": ["zaqxhna15w", "ghnr7txz47", "yuqwjsfvsc", "vyp9ogyimt"],
                "reports_with_outliers": ["k0fbxxwkqf"],
                "outlier_counts_by_report": {
                    "zaqxhna15w": 0,
                    "ghnr7txz47": 0,
                    "yuqwjsfvsc": 0,
                    "vyp9ogyimt": 0,
                    "k0fbxxwkqf": 11,
                },
            },
        )

    def test_vyp9ogyimt_unsupported_entries_are_annotated_as_contradictory_source(self) -> None:
        url = "https://www.desmos.com/3d/vyp9ogyimt"
        report = {
            "url": url,
            "graph_hash": "vyp9ogyimt",
            "output": "artifacts/acceptance/vyp9ogyimt.usda",
            "renderable_expression_count": 558,
            "prim_count": 553,
            "unsupported_count": 5,
            "valid": True,
            "complete": False,
            "validations": [],
            "unsupported": [
                {"expr_id": "223", "kind": "inequality_region", "latex": "real fixture entry", "reason": "sampled cells"},
                {"expr_id": "360", "kind": "inequality_region", "latex": "real fixture entry", "reason": "sampled cells"},
                {"expr_id": "293", "kind": "inequality_region", "latex": "real fixture entry", "reason": "sampled cells"},
                {"expr_id": "181", "kind": "inequality_region", "latex": "real fixture entry", "reason": "sampled cells"},
                {"expr_id": "273", "kind": "inequality_region", "latex": "real fixture entry", "reason": "sampled cells"},
            ],
        }

        annotated = sample_suite.annotate_report_unsupported_source_triage(
            report,
            url,
            sample_suite.project_root_from_cwd(),
        )

        self.assertEqual(
            annotated["unsupported_source_triage"],
            {
                "contradictory_source_count": 5,
                "residual_converter_limitation_count": 0,
                "untriaged_count": 0,
            },
        )
        by_expr_id = {item["expr_id"]: item["source_triage"] for item in annotated["unsupported"]}
        self.assertEqual({triage["classification"] for triage in by_expr_id.values()}, {"contradictory_source"})
        self.assertEqual(by_expr_id["223"]["contradictions"][0]["axis"], "y")
        self.assertEqual(by_expr_id["223"]["contradictions"][0]["lower"]["value"], 17.0)
        self.assertEqual(by_expr_id["223"]["contradictions"][0]["upper"]["value"], -17.0)
        self.assertEqual(by_expr_id["293"]["contradictions"][0]["axis"], "x")
        self.assertEqual(by_expr_id["293"]["contradictions"][0]["lower"]["value"], 391.0)
        self.assertEqual(by_expr_id["293"]["contradictions"][0]["upper"]["value"], 388.0)

        evidence = sample_suite.unsupported_contradiction_evidence_lines(annotated)
        self.assertEqual(
            sample_suite.unsupported_evidence_cell(annotated),
            "5 contradiction details: [details](#unsupported-evidence-vyp9ogyimt)",
        )
        self.assertIn(
            "expr `223`: axis y contradiction: lower bound 17 from `17\\le y\\le20` "
            "is above upper bound -17 from `-20\\le y\\le-17`",
            evidence,
        )
        self.assertIn(
            "expr `293`: axis x contradiction: lower bound 391 from `391\\le x\\le388` "
            "is above upper bound 388 from `391\\le x\\le388`",
            evidence,
        )
        self.assertFalse(any("empty interval: lower" in line for line in evidence))

    def test_sample_export_refreshes_one_required_report_then_rebuilds_aggregates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            self.write_required_reports(out_dir, write_artifacts=True)
            selected_url = REQUIRED_SAMPLE_URLS[0]
            selected_hash = sample_suite.sample_hash(selected_url)
            current_count = int(
                sample_suite.load_frozen_sample_metadata(REQUIRED_SAMPLE_URLS)[selected_url][
                    "renderable_expression_count"
                ]
            )

            def fake_convert_url(
                url: str,
                output: Path,
                project_root: Path,
                refresh: bool,
                resolution: int,
                write_preview: bool,
            ) -> SimpleNamespace:
                output.write_text(f"#usda refreshed {sample_suite.sample_hash(url)}\n", encoding="utf-8")
                output.with_suffix(".ppm").write_text("P3\n1 1\n255\n0 0 0\n", encoding="utf-8")
                return SimpleNamespace(
                    url=url,
                    graph_hash=sample_suite.sample_hash(url),
                    output=str(output),
                    view_metadata={},
                    renderable_expression_count=current_count,
                    prim_count=current_count,
                    unsupported_count=0,
                    valid=True,
                    complete=True,
                    validations=[],
                    unsupported=[],
                    refreshed=True,
                )

            with patch.object(sample_suite, "convert_url", side_effect=fake_convert_url) as convert_url:
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    exit_code = sample_suite.main(
                        ["--out", str(out_dir), "--sample", selected_hash, "--resolution", "9"]
                    )

            self.assertEqual(exit_code, 0)
            convert_url.assert_called_once()
            called_args, called_kwargs = convert_url.call_args
            self.assertEqual(called_args[0], selected_url)
            self.assertEqual(called_args[1], out_dir / f"{selected_hash}.usda")
            self.assertEqual(called_kwargs["refresh"], False)
            self.assertEqual(called_kwargs["resolution"], 9)
            self.assertEqual(called_kwargs["write_preview"], True)

            refreshed_report = json.loads((out_dir / f"{selected_hash}.report.json").read_text(encoding="utf-8"))
            self.assertEqual(refreshed_report["renderable_expression_count"], current_count)
            self.assertEqual(refreshed_report["prim_count"], current_count)
            self.assertEqual(refreshed_report["unsupported_count"], 0)
            self.assertEqual(refreshed_report["refreshed"], True)

            untouched_hash = sample_suite.sample_hash(REQUIRED_SAMPLE_URLS[1])
            untouched_report = json.loads((out_dir / f"{untouched_hash}.report.json").read_text(encoding="utf-8"))
            self.assertEqual(untouched_report["sample_index"], 1)
            self.assertNotIn("refreshed", untouched_report)

            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary, json.loads(stdout.getvalue()))
            self.assertEqual(summary["sample_count"], len(REQUIRED_SAMPLE_URLS))
            self.assertEqual(summary["all_report_counts_match_current_frozen_fixture"], True)
            self.assertEqual(summary["stale_report_count"], 0)
            self.assertEqual(summary["reports"][0]["graph_hash"], selected_hash)
            self.assertEqual(summary["reports"][0]["renderable_expression_count"], current_count)
            self.assertEqual(summary["reports"][0]["current_frozen_fixture_renderable_expression_count"], current_count)
            self.assertEqual(summary["reports"][0]["renderable_expression_count_matches_current_frozen_fixture"], True)
            self.assertEqual(summary["reports"][0]["stale_report"], False)
            self.assertEqual(summary["reports"][0]["complete"], True)
            self.assertEqual(summary["reports"][1]["sample_index"], 1)

            compare_sheet = (out_dir / sample_suite.COMPARE_SHEET_FILENAME).read_text(encoding="utf-8")
            selected_row = self.compare_sheet_row(compare_sheet, selected_hash)
            self.assertIn(f"| {current_count} | {current_count} | matches frozen fixture |", selected_row)
            self.assertIn("USDA present<br>PPM present<br>report present", selected_row)

    def test_summary_flags_stale_report_counts_without_redefining_valid_or_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            stale_counts = {
                "yuqwjsfvsc": 7,
                "vyp9ogyimt": 8,
            }
            reports = self.write_required_reports(out_dir, renderable_count_overrides=stale_counts)
            for report in reports:
                report["prim_count"] = report["renderable_expression_count"]
                report["unsupported_count"] = 0
                report["unsupported"] = []
                report["complete"] = True

            summary = sample_suite.build_summary(reports, REQUIRED_SAMPLE_URLS)

            self.assertEqual(summary["all_valid"], True)
            self.assertEqual(summary["all_complete"], True)
            self.assertEqual(summary["all_report_counts_match_current_frozen_fixture"], False)
            self.assertEqual(summary["stale_report_count"], 2)

            reports_by_hash = {report["graph_hash"]: report for report in summary["reports"]}
            self.assertEqual(reports_by_hash["zaqxhna15w"]["stale_report"], False)
            self.assertEqual(reports_by_hash["yuqwjsfvsc"]["stale_report"], True)
            self.assertEqual(reports_by_hash["yuqwjsfvsc"]["current_frozen_fixture_renderable_expression_count"], 341)
            self.assertEqual(
                reports_by_hash["yuqwjsfvsc"]["report_count_check"],
                "stale report count: report 7, frozen fixture 341",
            )
            self.assertEqual(reports_by_hash["vyp9ogyimt"]["stale_report"], True)
            self.assertEqual(reports_by_hash["vyp9ogyimt"]["current_frozen_fixture_renderable_expression_count"], 558)
            self.assertEqual(
                reports_by_hash["vyp9ogyimt"]["report_count_check"],
                "stale report count: report 8, frozen fixture 558",
            )

    def test_compare_sheet_only_writes_manual_scaffold_for_required_reports(self) -> None:
        project_root = sample_suite.project_root_from_cwd().resolve()
        with tempfile.TemporaryDirectory(dir=project_root) as tmp:
            tmp_root = Path(tmp)
            out_dir = tmp_root / "sample-reports"
            artifact_dir = tmp_root / "sample-artifacts"
            out_dir.mkdir()
            artifact_dir.mkdir()
            self.write_required_reports(out_dir, artifact_dir, write_artifacts=True)
            (out_dir / "extra.report.json").write_text('{"graph_hash": "not-required-sample"}\n', encoding="utf-8")
            (out_dir / "summary.json").write_text('{"stale": true}\n', encoding="utf-8")

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = sample_suite.main(["--out", str(out_dir), "--compare-sheet-only"])

            self.assertEqual(exit_code, 0)
            compare_sheet_path = out_dir / sample_suite.COMPARE_SHEET_FILENAME
            compare_sheet = compare_sheet_path.read_text(encoding="utf-8")
            self.assertEqual(compare_sheet, stdout.getvalue())
            self.assertIn("Manual compare scaffold", compare_sheet)
            self.assertIn("Frozen view metadata is read from the in-repo required sample states", compare_sheet)
            self.assertIn("not proof of visual parity", compare_sheet)
            self.assertIn("does not claim the USDA/PPM render matches Desmos", compare_sheet)
            self.assertIn("report renderables", compare_sheet)
            self.assertIn("frozen fixture renderables", compare_sheet)
            self.assertIn("report count check", compare_sheet)
            self.assertIn("geometry diagnostics", compare_sheet)
            self.assertIn("unsupported triage", compare_sheet)
            self.assertIn("unsupported evidence", compare_sheet)
            self.assertIn("matches frozen fixture", compare_sheet)
            self.assertIn("viewer USDA", compare_sheet)
            self.assertIn("artifact presence", compare_sheet)
            self.assertIn("Serve the repository root for viewer links", compare_sheet)
            self.assertIn(
                f"http://localhost:8765/{out_dir.relative_to(project_root).as_posix()}/compare-sheet.md",
                compare_sheet,
            )
            self.assertIn("`viewer/` and the generated artifacts both being served", compare_sheet)
            self.assertIn("--verify-artifacts", compare_sheet)
            self.assertIn("fix any `missing` item before manual comparison", compare_sheet)
            self.assertNotIn("artifacts/acceptance/compare-sheet.md", compare_sheet)
            self.assertIn("frozen Desmos view", compare_sheet)
            self.assertIn("Geometry diagnostics are copied from existing report `geometry_diagnostics` fields", compare_sheet)
            self.assertIn("stale-report consistency signal, not proof of visual mismatch", compare_sheet)
            self.assertIn("Unsupported evidence is copied from report `source_triage` entries", compare_sheet)
            self.assertIn(
                "viewport x[-152.132, 152.132] y[-152.132, 152.132] z[-152.132, 152.132]",
                compare_sheet,
            )
            self.assertIn("worldRotation3D [0.82576, -0.529959, 0.19304", compare_sheet)
            self.assertIn("axis3D [-0.529959, 0.848023, 0]", compare_sheet)
            self.assertIn("showPlane3D=false", compare_sheet)
            self.assertNotIn("not-required-sample", compare_sheet)
            self.assertEqual(json.loads((out_dir / "summary.json").read_text(encoding="utf-8")), {"stale": True})

            row_lines = [
                line
                for line in compare_sheet.splitlines()
                if line.startswith("| ") and not line.startswith("| ---") and "Desmos 3D sample" not in line
            ]
            self.assertEqual(len(row_lines), len(REQUIRED_SAMPLE_URLS))
            self.assertEqual(
                compare_sheet.count("USDA present<br>PPM present<br>report present"),
                len(REQUIRED_SAMPLE_URLS),
            )
            self.assertEqual(compare_sheet.count("0 contradictory source, 0 residual limitation, 1 untriaged"), len(REQUIRED_SAMPLE_URLS))
            self.assertEqual(compare_sheet.count("not recorded"), len(REQUIRED_SAMPLE_URLS))
            for url in REQUIRED_SAMPLE_URLS:
                graph_hash = sample_suite.sample_hash(url)
                usda_path = artifact_dir / f"{graph_hash}.usda"
                usda_query = quote(f"../{usda_path.relative_to(project_root).as_posix()}", safe="")
                self.assertIn(f"[{url}]({url})", compare_sheet)
                self.assertIn(
                    f"[open USDA](../../viewer/?usda={usda_query})",
                    compare_sheet,
                )
                self.assertIn(f"[{graph_hash}.usda](../sample-artifacts/{graph_hash}.usda)", compare_sheet)
                self.assertIn(f"[{graph_hash}.ppm](../sample-artifacts/{graph_hash}.ppm)", compare_sheet)
                self.assertIn(f"[{graph_hash}.report.json]({graph_hash}.report.json)", compare_sheet)

    def test_compare_sheet_reports_real_geometry_diagnostics_from_required_reports(self) -> None:
        out_dir = Path("artifacts/acceptance")
        reports = sample_suite.load_required_reports(out_dir)

        compare_sheet = sample_suite.build_compare_sheet(
            reports,
            REQUIRED_SAMPLE_URLS,
            compare_sheet_path=out_dir / sample_suite.COMPARE_SHEET_FILENAME,
        )

        k0_row = self.compare_sheet_row(compare_sheet, "k0fbxxwkqf")
        self.assertIn(
            "11 viewport outliers; strongest expr `3`: x low 85.613, high 85.613 "
            "(margin 27.8774): [details](#geometry-diagnostics-k0fbxxwkqf)",
            k0_row,
        )
        self.assertIn("## Geometry Diagnostics Details", compare_sheet)
        self.assertIn('<a id="geometry-diagnostics-k0fbxxwkqf"></a>', compare_sheet)
        self.assertIn("### k0fbxxwkqf", compare_sheet)
        self.assertIn(
            "- frozen source viewport bbox: min [-139.387, -139.387, -139.387], "
            "max [139.387, 139.387, 139.387], span [278.774, 278.774, 278.774]",
            compare_sheet,
        )
        self.assertIn(
            "- report global bbox: min [-225, -23, -139.387], max [225, 23, 139.387], "
            "span [450, 46, 278.774]",
            compare_sheet,
        )
        self.assertIn(
            "- outlier axis/direction summary: x low 7 (max 85.613), high 7 (max 85.613)",
            compare_sheet,
        )
        self.assertIn(
            "- expr `3` (`expr_0001__3`, explicit_surface): max overshoot 85.613; "
            "x low 85.613, high 85.613 (margin 27.8774)",
            compare_sheet,
        )
        k0_section = self.compare_sheet_section(compare_sheet, "k0fbxxwkqf")
        self.assertEqual(k0_section.count("- expr `"), 11)
        self.assertIn(
            "- expr `323` (`expr_0264__323`, explicit_surface): max overshoot 37.613; "
            "x low 37.613 (margin 27.8774)",
            k0_section,
        )
        self.assertNotIn("additional viewport outliers omitted", k0_section)

        ghn_row = self.compare_sheet_row(compare_sheet, "ghnr7txz47")
        self.assertIn("0 viewport outliers", ghn_row)

    def test_compare_sheet_omits_geometry_diagnostics_only_above_detail_limit(self) -> None:
        def outlier(index: int) -> dict:
            return {
                "expr_id": str(index),
                "prim_name": f"expr_{index:04d}__{index}",
                "kind": "explicit_surface",
                "order": index,
                "max_viewport_overshoot": float(index + 1),
                "outside_viewport_axes": [
                    {
                        "axis": "x",
                        "high_overshoot": float(index + 1),
                        "threshold_margin": 1.0,
                    },
                ],
            }

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            graph_hash = sample_suite.sample_hash(REQUIRED_SAMPLE_URLS[0])
            limit = sample_suite.GEOMETRY_OUTLIER_DETAIL_LIMIT
            reports = self.write_required_reports(
                out_dir,
                geometry_diagnostics_by_hash={
                    graph_hash: {
                        "outlier_count": limit,
                        "outlier_rule": "synthetic threshold rule",
                        "outliers": [outlier(index) for index in range(limit)],
                    },
                },
            )

            compare_sheet = sample_suite.build_compare_sheet(
                reports,
                REQUIRED_SAMPLE_URLS,
                compare_sheet_path=out_dir / sample_suite.COMPARE_SHEET_FILENAME,
            )

            section = self.compare_sheet_section(compare_sheet, graph_hash)
            self.assertEqual(section.count("- expr `"), limit)
            self.assertNotIn("additional viewport outliers omitted", section)

            reports[0]["geometry_diagnostics"] = {
                "outlier_count": limit + 1,
                "outlier_rule": "synthetic threshold rule",
                "outliers": [outlier(index) for index in range(limit + 1)],
            }
            compare_sheet = sample_suite.build_compare_sheet(
                reports,
                REQUIRED_SAMPLE_URLS,
                compare_sheet_path=out_dir / sample_suite.COMPARE_SHEET_FILENAME,
            )

            section = self.compare_sheet_section(compare_sheet, graph_hash)
            self.assertEqual(section.count("- expr `"), limit)
            self.assertIn("- 1 additional viewport outliers omitted from this section", section)

    def test_compare_sheet_reports_unsupported_source_triage_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            reports = self.write_required_reports(out_dir)
            reports[3]["unsupported"] = [
                {
                    "expr_id": "223",
                    "reason": "sampled cells",
                    "source_triage": {
                        "classification": sample_suite.SOURCE_TRIAGE_CONTRADICTORY,
                        "contradictions": [
                            {
                                "axis": "y",
                                "lower": {"value": 17.0, "predicate": "17\\le y\\le20"},
                                "upper": {"value": -17.0, "predicate": "-20\\le y\\le-17"},
                            },
                        ],
                    },
                },
                {
                    "expr_id": "future",
                    "reason": "sampled cells",
                    "source_triage": {"classification": sample_suite.SOURCE_TRIAGE_RESIDUAL_LIMITATION},
                },
            ]
            reports[3]["unsupported_count"] = 2

            compare_sheet = sample_suite.build_compare_sheet(
                reports,
                REQUIRED_SAMPLE_URLS,
                compare_sheet_path=out_dir / sample_suite.COMPARE_SHEET_FILENAME,
            )

            row = self.compare_sheet_row(compare_sheet, "vyp9ogyimt")
            self.assertIn("2 | 1 contradictory source, 1 residual limitation, 0 untriaged |", row)
            self.assertIn("1 contradiction detail: [details](#unsupported-evidence-vyp9ogyimt)", row)
            self.assertNotIn("lower bound 17", row)
            self.assertIn("## Unsupported Evidence Details", compare_sheet)
            self.assertIn('<a id="unsupported-evidence-vyp9ogyimt"></a>', compare_sheet)
            self.assertIn(
                "- expr `223`: axis y contradiction: lower bound 17 from `17\\le y\\le20` "
                "is above upper bound -17 from `-20\\le y\\le-17`",
                compare_sheet,
            )

    def test_compare_sheet_uses_collision_safe_unsupported_evidence_detail_anchors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            expected_urls = [
                "https://www.desmos.com/3d/vyp9ogyimt!",
                "https://www.desmos.com/3d/vyp9ogyimt@",
            ]
            reports = [
                {
                    "url": expected_urls[0],
                    "graph_hash": "vyp9ogyimt!",
                    "output": str(out_dir / "vyp9ogyimt-bang.usda"),
                    "renderable_expression_count": 558,
                    "prim_count": 557,
                    "unsupported_count": 1,
                    "valid": True,
                    "complete": False,
                    "validations": [],
                    "unsupported": [
                        {
                            "expr_id": "223",
                            "reason": "sampled cells",
                            "source_triage": {
                                "classification": sample_suite.SOURCE_TRIAGE_CONTRADICTORY,
                                "contradictions": [
                                    {
                                        "axis": "y",
                                        "lower": {"value": 17.0, "predicate": "17\\le y\\le20"},
                                        "upper": {"value": -17.0, "predicate": "-20\\le y\\le-17"},
                                    },
                                ],
                            },
                        },
                    ],
                },
                {
                    "url": expected_urls[1],
                    "graph_hash": "vyp9ogyimt@",
                    "output": str(out_dir / "vyp9ogyimt-at.usda"),
                    "renderable_expression_count": 558,
                    "prim_count": 557,
                    "unsupported_count": 1,
                    "valid": True,
                    "complete": False,
                    "validations": [],
                    "unsupported": [
                        {
                            "expr_id": "293",
                            "reason": "sampled cells",
                            "source_triage": {
                                "classification": sample_suite.SOURCE_TRIAGE_CONTRADICTORY,
                                "contradictions": [
                                    {
                                        "axis": "x",
                                        "lower": {"value": 391.0, "predicate": "391\\le x\\le388"},
                                        "upper": {"value": 388.0, "predicate": "391\\le x\\le388"},
                                    },
                                ],
                            },
                        },
                    ],
                },
            ]
            frozen_metadata = {
                url: {"view_metadata": {}, "renderable_expression_count": 558}
                for url in expected_urls
            }

            with patch.object(sample_suite, "load_frozen_sample_metadata", return_value=frozen_metadata):
                compare_sheet = sample_suite.build_compare_sheet(
                    reports,
                    expected_urls,
                    compare_sheet_path=out_dir / sample_suite.COMPARE_SHEET_FILENAME,
                )

            first_row = self.compare_sheet_row(compare_sheet, "vyp9ogyimt!")
            second_row = self.compare_sheet_row(compare_sheet, "vyp9ogyimt@")
            self.assertIn("1 contradiction detail: [details](#unsupported-evidence-vyp9ogyimt)", first_row)
            self.assertIn("1 contradiction detail: [details](#unsupported-evidence-vyp9ogyimt-2)", second_row)
            self.assertEqual(compare_sheet.count('<a id="unsupported-evidence-vyp9ogyimt"></a>'), 1)
            self.assertEqual(compare_sheet.count('<a id="unsupported-evidence-vyp9ogyimt-2"></a>'), 1)
            self.assertIn("### vyp9ogyimt!", compare_sheet)
            self.assertIn("### vyp9ogyimt@", compare_sheet)

    def test_compare_sheet_flags_stale_report_renderable_counts_against_frozen_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            out_dir.mkdir(exist_ok=True)
            stale_hash = "zaqxhna15w"
            reports = self.write_required_reports(out_dir, renderable_count_overrides={stale_hash: 7})

            compare_sheet = sample_suite.build_compare_sheet(
                reports,
                REQUIRED_SAMPLE_URLS,
                compare_sheet_path=out_dir / sample_suite.COMPARE_SHEET_FILENAME,
            )

            stale_row = self.compare_sheet_row(compare_sheet, stale_hash)
            current_count = int(
                sample_suite.load_frozen_sample_metadata(REQUIRED_SAMPLE_URLS)[REQUIRED_SAMPLE_URLS[0]][
                    "renderable_expression_count"
                ]
            )
            self.assertEqual(current_count, 268)
            self.assertIn(f"| 7 | {current_count} | stale report count: report 7, frozen fixture {current_count} |", stale_row)

    def test_compare_sheet_reports_missing_artifact_presence_per_row(self) -> None:
        project_root = sample_suite.project_root_from_cwd().resolve()
        with tempfile.TemporaryDirectory(dir=project_root) as tmp:
            tmp_root = Path(tmp)
            out_dir = tmp_root / "sample-reports"
            artifact_dir = tmp_root / "sample-artifacts"
            out_dir.mkdir()
            artifact_dir.mkdir()
            reports = self.write_required_reports(out_dir, artifact_dir, write_artifacts=True)
            missing_hash = sample_suite.sample_hash(REQUIRED_SAMPLE_URLS[0])
            present_hash = sample_suite.sample_hash(REQUIRED_SAMPLE_URLS[1])
            (artifact_dir / f"{missing_hash}.usda").unlink()
            (artifact_dir / f"{missing_hash}.ppm").unlink()
            (out_dir / f"{missing_hash}.report.json").unlink()

            compare_sheet = sample_suite.build_compare_sheet(
                reports,
                REQUIRED_SAMPLE_URLS,
                compare_sheet_path=out_dir / sample_suite.COMPARE_SHEET_FILENAME,
            )

            missing_row = self.compare_sheet_row(compare_sheet, missing_hash)
            present_row = self.compare_sheet_row(compare_sheet, present_hash)
            self.assertIn("USDA missing<br>PPM missing<br>report missing", missing_row)
            self.assertIn("USDA present<br>PPM present<br>report present", present_row)
            self.assertIn(f"[{missing_hash}.usda](../sample-artifacts/{missing_hash}.usda)", missing_row)
            self.assertIn(f"[{missing_hash}.ppm](../sample-artifacts/{missing_hash}.ppm)", missing_row)
            self.assertIn(f"[{missing_hash}.report.json]({missing_hash}.report.json)", missing_row)

    def test_verify_artifacts_passes_for_required_compare_paths_without_regeneration(self) -> None:
        project_root = sample_suite.project_root_from_cwd().resolve()
        with tempfile.TemporaryDirectory(dir=project_root) as tmp:
            tmp_root = Path(tmp)
            out_dir = tmp_root / "sample-reports"
            artifact_dir = tmp_root / "sample-artifacts"
            out_dir.mkdir()
            artifact_dir.mkdir()
            self.write_required_reports(out_dir, artifact_dir, write_artifacts=True)
            (out_dir / "summary.json").write_text('{"stale": true}\n', encoding="utf-8")
            (out_dir / "extra.report.json").write_text('{"graph_hash": "not-required-sample"}\n', encoding="utf-8")

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = sample_suite.main(["--out", str(out_dir), "--verify-artifacts"])

            verification = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(verification["ok"], True)
            self.assertEqual(verification["sample_count"], len(REQUIRED_SAMPLE_URLS))
            self.assertEqual(verification["missing_count"], 0)
            self.assertEqual(verification["error_count"], 0)
            self.assertFalse((out_dir / sample_suite.COMPARE_SHEET_FILENAME).exists())
            self.assertEqual(json.loads((out_dir / "summary.json").read_text(encoding="utf-8")), {"stale": True})
            self.assertNotIn("not-required-sample", stdout.getvalue())

            first = verification["samples"][0]
            graph_hash = sample_suite.sample_hash(REQUIRED_SAMPLE_URLS[0])
            self.assertEqual(first["graph_hash"], graph_hash)
            self.assertEqual(first["artifacts"]["usda"]["present"], True)
            self.assertEqual(
                first["artifacts"]["usda"]["path"],
                (artifact_dir / f"{graph_hash}.usda").relative_to(project_root).as_posix(),
            )
            self.assertEqual(first["artifacts"]["ppm"]["present"], True)
            self.assertEqual(first["artifacts"]["report"]["present"], True)
            self.assertEqual(first["renderable_expression_count_check"]["matches_current_frozen_fixture"], True)

    def test_verify_artifacts_fails_when_report_renderable_count_is_stale(self) -> None:
        project_root = sample_suite.project_root_from_cwd().resolve()
        with tempfile.TemporaryDirectory(dir=project_root) as tmp:
            tmp_root = Path(tmp)
            out_dir = tmp_root / "sample-reports"
            artifact_dir = tmp_root / "sample-artifacts"
            out_dir.mkdir()
            artifact_dir.mkdir()
            stale_hash = "zaqxhna15w"
            self.write_required_reports(
                out_dir,
                artifact_dir,
                write_artifacts=True,
                renderable_count_overrides={stale_hash: 7},
            )

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = sample_suite.main(["--out", str(out_dir), "--verify-artifacts"])

            verification = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 1)
            self.assertEqual(verification["ok"], False)
            self.assertEqual(verification["missing_count"], 0)
            self.assertEqual(verification["error_count"], 1)
            first = verification["samples"][0]
            self.assertEqual(first["graph_hash"], stale_hash)
            self.assertEqual(
                first["errors"],
                ["report renderable_expression_count 7 does not match current frozen fixture renderable count 268"],
            )
            self.assertEqual(
                first["renderable_expression_count_check"],
                {
                    "current_frozen_fixture": 268,
                    "matches_current_frozen_fixture": False,
                    "stored_report": 7,
                },
            )

    def test_verify_artifacts_fails_when_required_compare_artifact_is_missing(self) -> None:
        project_root = sample_suite.project_root_from_cwd().resolve()
        with tempfile.TemporaryDirectory(dir=project_root) as tmp:
            tmp_root = Path(tmp)
            out_dir = tmp_root / "sample-reports"
            artifact_dir = tmp_root / "sample-artifacts"
            out_dir.mkdir()
            artifact_dir.mkdir()
            self.write_required_reports(out_dir, artifact_dir, write_artifacts=True)
            missing_hash = sample_suite.sample_hash(REQUIRED_SAMPLE_URLS[0])
            (artifact_dir / f"{missing_hash}.ppm").unlink()

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = sample_suite.main(["--out", str(out_dir), "--verify-artifacts"])

            verification = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 1)
            self.assertEqual(verification["ok"], False)
            self.assertEqual(verification["missing_count"], 1)
            first = verification["samples"][0]
            self.assertEqual(first["graph_hash"], missing_hash)
            self.assertEqual(first["missing"], ["ppm"])
            self.assertEqual(first["artifacts"]["usda"]["present"], True)
            self.assertEqual(first["artifacts"]["report"]["present"], True)
            self.assertEqual(first["artifacts"]["ppm"]["present"], False)
            self.assertEqual(
                first["artifacts"]["ppm"]["path"],
                (artifact_dir / f"{missing_hash}.ppm").relative_to(project_root).as_posix(),
            )


if __name__ == "__main__":
    unittest.main()
