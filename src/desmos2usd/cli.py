from __future__ import annotations

import argparse
import json
from pathlib import Path

from desmos2usd.converter import convert_url
from desmos2usd.desmos_state import project_root_from_cwd


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert a public Desmos 3D URL to USDA")
    parser.add_argument("url", help="Public Desmos 3D share URL")
    parser.add_argument("-o", "--output", required=True, help="Output .usda path")
    parser.add_argument("--refresh", action="store_true", help="Fetch live Desmos state instead of using a frozen fixture")
    parser.add_argument("--resolution", type=int, default=18, help="Base tessellation resolution")
    parser.add_argument("--report", help="Optional JSON report path")
    parser.add_argument("--preview", action="store_true", help="Write a deterministic orthographic PPM preview beside the USDA")
    parser.add_argument("--usdz", help="Optional output .usdz path packaged from the generated USDA")
    parser.add_argument("--validate-usdz", action="store_true", help="Run usdchecker --arkit on --usdz and fail if invalid")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.validate_usdz and not args.usdz:
        parser.error("--validate-usdz requires --usdz")
    root = project_root_from_cwd()
    report = convert_url(
        args.url,
        Path(args.output),
        project_root=root,
        refresh=args.refresh,
        resolution=args.resolution,
        write_preview=args.preview,
        usdz_output=Path(args.usdz) if args.usdz else None,
        validate_usdz=args.validate_usdz,
    )
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report.__dict__, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report.__dict__, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
