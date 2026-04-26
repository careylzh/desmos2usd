from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401
from desmos2usd.validate import csv_fixture_report


class CsvFixtureReportTests(unittest.TestCase):
    def test_build_report_maps_csv_rows_to_summary_and_missing_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "urls.csv"
            csv_path.write_text(
                "file_name,url\n"
                "[4B] 3D Diagram - S2-01 Group A.docx,https://www.desmos.com/3d/cvggvbbe73\n"
                "[4B] 3D Diagram - S2-01 Group B.docx,https://www.desmos.com/3d/27v0xuv64m\n",
                encoding="utf-8",
            )
            fixture_dir = root / "fixtures" / "states"
            fixture_dir.mkdir(parents=True)
            (fixture_dir / "[4B] 3D Diagram - S2-01 Group A.json").write_text("{}\n", encoding="utf-8")
            artifact_dir = root / "artifacts" / "fixture_usdz"
            artifact_dir.mkdir(parents=True)
            (artifact_dir / "[4B] 3D Diagram - S2-01 Group A.usdz").write_text("placeholder\n", encoding="utf-8")
            summary_path = artifact_dir / "summary.json"
            summary_path.write_text(
                json.dumps(
                    {
                        "reports": [
                            {
                                "fixture": "[4B] 3D Diagram - S2-01 Group A.json",
                                "status": "success",
                                "usdz_exists": True,
                                "unsupported_count": 0,
                                "classified_expression_count": 4,
                                "prim_count": 3,
                                "unsupported": [],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = csv_fixture_report.build_report(
                csv_path=csv_path,
                summary_path=summary_path,
                fixture_dir=fixture_dir,
                artifact_dir=artifact_dir,
                live_note="curl failed",
            )

            self.assertEqual(len(result.rows), 2)
            self.assertEqual(result.status_counts["success"], 1)
            self.assertEqual(result.status_counts["missing-report"], 1)
            self.assertIn("| CSV rows | 2 |", result.markdown)
            self.assertIn("Frozen fixture states present | 1/2", result.markdown)
            self.assertIn("structural success; live visual parity unverified", result.markdown)
            self.assertIn("missing frozen fixture state; missing sweep report", result.markdown)


if __name__ == "__main__":
    unittest.main()
