from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _path import ROOT
from desmos2usd.converter import convert_url
from desmos2usd.desmos_state import REQUIRED_SAMPLE_URLS


class AcceptanceSampleTests(unittest.TestCase):
    def test_required_samples_export_and_validate(self) -> None:
        expected_unsupported = {
            "zaqxhna15w": 0,
            "ghnr7txz47": 0,
            "yuqwjsfvsc": 0,
            "vyp9ogyimt": 5,
            "k0fbxxwkqf": 0,
        }
        with tempfile.TemporaryDirectory() as tmp:
            for url in REQUIRED_SAMPLE_URLS:
                graph_hash = url.rstrip("/").split("/")[-1]
                output = Path(tmp) / f"{graph_hash}.usda"
                report = convert_url(url, output, project_root=ROOT, resolution=8, write_preview=True)
                self.assertTrue(output.exists(), url)
                self.assertTrue(output.with_suffix(".ppm").exists(), url)
                self.assertTrue(report.valid, report)
                self.assertEqual(report.unsupported_count, expected_unsupported[graph_hash], url)
                self.assertEqual(report.prim_count + report.unsupported_count, report.renderable_expression_count)
                self.assertEqual(report.complete, report.unsupported_count == 0)


if __name__ == "__main__":
    unittest.main()
