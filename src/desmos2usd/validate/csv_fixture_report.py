from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from desmos2usd.desmos_state import project_root_from_cwd
from desmos2usd.desmos_url import parse_desmos_url


DEFAULT_CSV_PATH = "/Users/chek/.openclaw/workspace/tmp/desmos2usd-ralph-control/desmos_urls_latest.csv"
DEFAULT_SUMMARY_PATH = "artifacts/fixture_usdz/summary.json"
DEFAULT_OUTPUT_PATH = "artifacts/fixture_usdz/url_fixture_comparison.md"
DEFAULT_LIVE_NOTE = "No live Desmos visual comparison was attempted by this structural report."


@dataclass(frozen=True)
class ComparisonRow:
    index: int
    source_url: str
    url_hash: str
    fixture: str
    frozen_state_exists: bool
    sweep_status: str
    usdz_present: bool
    unsupported_count: int | None
    classified_count: int | None
    prim_count: int | None
    unsupported_kinds: str
    notes: str


@dataclass(frozen=True)
class ReportResult:
    markdown: str
    rows: list[ComparisonRow]
    status_counts: Counter[str]
    unsupported_kind_counts: Counter[str]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a CSV URL to frozen-fixture comparison report")
    parser.add_argument("--csv", default=DEFAULT_CSV_PATH, help="CSV with file_name,url columns")
    parser.add_argument("--summary", default=DEFAULT_SUMMARY_PATH, help="Fixture USDZ suite summary.json")
    parser.add_argument("--fixture-dir", default="fixtures/states", help="Directory containing frozen fixture JSON files")
    parser.add_argument("--artifact-dir", default="artifacts/fixture_usdz", help="Directory containing USDZ artifacts")
    parser.add_argument("--out", default=DEFAULT_OUTPUT_PATH, help="Markdown report path")
    parser.add_argument("--expect-rows", type=int, help="Fail if the CSV row count does not match")
    parser.add_argument(
        "--live-note",
        default=DEFAULT_LIVE_NOTE,
        help="Short note describing live Desmos/browser verification status",
    )
    return parser


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = {"file_name", "url"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing required column(s): {', '.join(sorted(missing))}")
        return [dict(row) for row in reader]


def load_summary(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def csv_file_to_fixture(file_name: str) -> str:
    clean_name = file_name.strip()
    if clean_name.lower().endswith(".docx"):
        clean_name = clean_name[:-5]
    return f"{clean_name}.json"


def markdown_cell(value: object) -> str:
    text = str(value)
    return text.replace("\n", " ").replace("|", "\\|")


def count_or_none(report: dict[str, Any] | None, key: str) -> int | None:
    if report is None or report.get(key) is None:
        return None
    return int(report[key])


def count_display(value: int | None) -> str:
    return "n/a" if value is None else str(value)


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def display_path(path: Path, root: Path | None) -> str:
    if root is not None:
        try:
            return str(path.resolve().relative_to(root.resolve()))
        except ValueError:
            pass
    return str(path)


def unsupported_kind_counter(report: dict[str, Any] | None) -> Counter[str]:
    counter: Counter[str] = Counter()
    if not report:
        return counter
    for unsupported in report.get("unsupported") or []:
        kind = unsupported.get("kind") or "unknown"
        counter[str(kind)] += 1
    return counter


def format_kind_summary(counter: Counter[str], limit: int = 3) -> str:
    return ", ".join(f"{kind} {count}" for kind, count in counter.most_common(limit))


def row_note(
    *,
    frozen_state_exists: bool,
    report: dict[str, Any] | None,
    url_error: str | None,
    usdz_present: bool,
    unsupported_count: int | None,
    prim_count: int | None,
    kind_summary: str,
) -> str:
    notes: list[str] = []
    if url_error:
        notes.append(f"invalid CSV URL: {url_error}")
    if not frozen_state_exists:
        notes.append("missing frozen fixture state")
    if report is None:
        notes.append("missing sweep report")
    if report is not None and not usdz_present:
        notes.append("missing USDZ artifact")

    if report is not None:
        status = str(report.get("status") or "unknown")
        unsupported = unsupported_count or 0
        prims = prim_count or 0
        if status == "success" and unsupported == 0:
            notes.append("structural success; live visual parity unverified")
        else:
            details: list[str] = [f"{status} export"]
            if prims == 0:
                details.append("0 prims")
            if unsupported:
                details.append(f"{unsupported} unsupported")
                if kind_summary:
                    details.append(kind_summary)
            details.append("needs live Desmos visual verification")
            notes.append("; ".join(details))

    return "; ".join(notes)


def build_comparison_rows(
    csv_rows: list[dict[str, str]],
    summary: dict[str, Any],
    fixture_dir: Path,
    artifact_dir: Path,
) -> tuple[list[ComparisonRow], Counter[str]]:
    reports_by_fixture = {str(report.get("fixture")): report for report in summary.get("reports") or []}
    unsupported_totals: Counter[str] = Counter()
    rows: list[ComparisonRow] = []

    for index, csv_row in enumerate(csv_rows, start=1):
        source_url = (csv_row.get("url") or "").strip()
        try:
            url_hash = parse_desmos_url(source_url).graph_hash
            url_error = None
        except Exception as exc:
            url_hash = "invalid"
            url_error = str(exc)

        fixture = csv_file_to_fixture(csv_row.get("file_name") or "")
        state_exists = (fixture_dir / fixture).exists()
        report = reports_by_fixture.get(fixture)
        status = str(report.get("status") or "missing-report") if report else "missing-report"
        unsupported_count = count_or_none(report, "unsupported_count")
        classified_count = count_or_none(report, "classified_expression_count")
        prim_count = count_or_none(report, "prim_count")
        usdz_present = bool(report and report.get("usdz_exists"))
        kind_counter = unsupported_kind_counter(report)
        unsupported_totals.update(kind_counter)
        kind_summary = format_kind_summary(kind_counter)
        notes = row_note(
            frozen_state_exists=state_exists,
            report=report,
            url_error=url_error,
            usdz_present=usdz_present,
            unsupported_count=unsupported_count,
            prim_count=prim_count,
            kind_summary=kind_summary,
        )

        rows.append(
            ComparisonRow(
                index=index,
                source_url=source_url,
                url_hash=url_hash,
                fixture=fixture,
                frozen_state_exists=state_exists,
                sweep_status=status,
                usdz_present=usdz_present,
                unsupported_count=unsupported_count,
                classified_count=classified_count,
                prim_count=prim_count,
                unsupported_kinds=kind_summary or "none",
                notes=notes,
            )
        )

    return rows, unsupported_totals


def status_counter(rows: list[ComparisonRow]) -> Counter[str]:
    return Counter(row.sweep_status for row in rows)


def sum_known(rows: list[ComparisonRow], attr: str) -> int:
    total = 0
    for row in rows:
        value = getattr(row, attr)
        if value is not None:
            total += value
    return total


def format_status_counts(counter: Counter[str]) -> str:
    order = ["success", "partial", "error", "missing-report"]
    parts = [f"{key} {counter[key]}" for key in order if counter.get(key)]
    extras = sorted(key for key in counter if key not in order)
    parts.extend(f"{key} {counter[key]}" for key in extras)
    return ", ".join(parts) if parts else "none"


def format_priority_table(rows: list[ComparisonRow], title: str) -> list[str]:
    lines = [f"### {title}", "", "| Fixture | URL hash | Status | Unsupported | Prims | Unsupported kinds | Notes |"]
    lines.append("| --- | --- | --- | ---: | ---: | --- | --- |")
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(row.fixture),
                    markdown_cell(row.url_hash),
                    markdown_cell(row.sweep_status),
                    count_display(row.unsupported_count),
                    count_display(row.prim_count),
                    markdown_cell(row.unsupported_kinds),
                    markdown_cell(row.notes),
                ]
            )
            + " |"
        )
    return lines


def build_markdown_report(
    *,
    csv_path: Path,
    summary_path: Path,
    fixture_dir: Path,
    artifact_dir: Path,
    display_root: Path | None,
    live_note: str,
    rows: list[ComparisonRow],
    status_counts: Counter[str],
    unsupported_kind_counts: Counter[str],
) -> str:
    csv_count = len(rows)
    frozen_count = sum(1 for row in rows if row.frozen_state_exists)
    usdz_count = sum(1 for row in rows if row.usdz_present)
    report_count = sum(1 for row in rows if row.sweep_status != "missing-report")
    partial_rows = [row for row in rows if row.sweep_status != "success" or (row.unsupported_count or 0) > 0]
    highest_unsupported = sorted(
        partial_rows,
        key=lambda row: (row.unsupported_count or -1, -(row.prim_count or 0), row.fixture),
        reverse=True,
    )[:12]
    low_prim = sorted(
        [row for row in partial_rows if row.prim_count is not None],
        key=lambda row: (row.prim_count or 0, -(row.unsupported_count or 0), row.fixture),
    )[:8]

    lines: list[str] = [
        "# CSV URL to Fixture Comparison",
        "",
        "This report maps each original CSV Desmos URL to its frozen fixture state and current local USDZ sweep evidence.",
        "It does not claim live Desmos visual parity.",
        "",
        "## Sources",
        "",
        f"- CSV: `{display_path(csv_path, display_root)}`",
        f"- Frozen fixture states: `{display_path(fixture_dir, display_root)}`",
        f"- Sweep summary: `{display_path(summary_path, display_root)}`",
        f"- USDZ artifacts: `{display_path(artifact_dir, display_root)}`",
        f"- Live Desmos/browser check: {live_note}",
        "",
        "## Aggregate Evidence",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| CSV rows | {csv_count} |",
        f"| Frozen fixture states present | {frozen_count}/{csv_count} |",
        f"| Sweep reports mapped | {report_count}/{csv_count} |",
        f"| Sweep status counts | {markdown_cell(format_status_counts(status_counts))} |",
        f"| USDZ artifacts present | {usdz_count}/{csv_count} |",
        f"| Unsupported expressions | {sum_known(rows, 'unsupported_count')} |",
        f"| Classified expressions | {sum_known(rows, 'classified_count')} |",
        f"| Exported prims | {sum_known(rows, 'prim_count')} |",
        f"| Unsupported kind counts | {markdown_cell(format_kind_summary(unsupported_kind_counts, limit=8) or 'none')} |",
        "",
        "## Prioritized Remaining Rows",
        "",
    ]

    if highest_unsupported:
        lines.extend(format_priority_table(highest_unsupported, "Highest Unsupported Counts"))
        lines.append("")
    if low_prim:
        lines.extend(format_priority_table(low_prim, "Lowest Prim Counts Among Partial Rows"))
        lines.append("")

    lines.extend(
        [
            "## All CSV Rows",
            "",
            "| # | Source URL | Fixture | Frozen state | Sweep | USDZ | Unsupported | Classified | Prims | Notes |",
            "| ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.index),
                    markdown_cell(row.source_url),
                    markdown_cell(row.fixture),
                    yes_no(row.frozen_state_exists),
                    markdown_cell(row.sweep_status),
                    yes_no(row.usdz_present),
                    count_display(row.unsupported_count),
                    count_display(row.classified_count),
                    count_display(row.prim_count),
                    markdown_cell(row.notes),
                ]
            )
            + " |"
        )

    lines.append("")
    return "\n".join(lines)


def build_report(
    *,
    csv_path: Path,
    summary_path: Path,
    fixture_dir: Path,
    artifact_dir: Path,
    live_note: str,
    display_root: Path | None = None,
) -> ReportResult:
    csv_rows = load_csv_rows(csv_path)
    summary = load_summary(summary_path)
    rows, unsupported_kind_counts = build_comparison_rows(csv_rows, summary, fixture_dir, artifact_dir)
    counts = status_counter(rows)
    markdown = build_markdown_report(
        csv_path=csv_path,
        summary_path=summary_path,
        fixture_dir=fixture_dir,
        artifact_dir=artifact_dir,
        display_root=display_root,
        live_note=live_note,
        rows=rows,
        status_counts=counts,
        unsupported_kind_counts=unsupported_kind_counts,
    )
    return ReportResult(markdown=markdown, rows=rows, status_counts=counts, unsupported_kind_counts=unsupported_kind_counts)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    project_root = project_root_from_cwd()

    def root_path(value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else project_root / path

    csv_path = root_path(args.csv)
    summary_path = root_path(args.summary)
    fixture_dir = root_path(args.fixture_dir)
    artifact_dir = root_path(args.artifact_dir)
    out_path = root_path(args.out)

    result = build_report(
        csv_path=csv_path,
        summary_path=summary_path,
        fixture_dir=fixture_dir,
        artifact_dir=artifact_dir,
        display_root=project_root,
        live_note=args.live_note,
    )
    if args.expect_rows is not None and len(result.rows) != args.expect_rows:
        parser.error(f"expected {args.expect_rows} CSV rows, found {len(result.rows)}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result.markdown, encoding="utf-8")
    print(
        "wrote "
        f"{out_path} "
        f"csv_rows={len(result.rows)} "
        f"status_counts={format_status_counts(result.status_counts)} "
        f"usdz_present={sum(1 for row in result.rows if row.usdz_present)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
