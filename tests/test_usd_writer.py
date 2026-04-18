from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _path import ROOT
from desmos2usd.converter import convert_url


class UsdWriterTests(unittest.TestCase):
    def test_usda_contains_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "sample.usda"
            report = convert_url("https://www.desmos.com/3d/ghnr7txz47", output, project_root=ROOT, resolution=8)
            text = output.read_text(encoding="utf-8")
            self.assertTrue(report.valid)
            self.assertTrue(report.complete)
            self.assertEqual(report.prim_count, 617)
            self.assertEqual(report.unsupported_count, 0)
            self.assertIn("#usda 1.0", text)
            self.assertIn("custom string desmos:latex", text)
            self.assertIn("custom string desmos:constraints", text)
            self.assertIn("string desmos:viewportBounds =", text)
            self.assertEqual(report.prim_count + report.unsupported_count, report.renderable_expression_count)

            diagnostics = report.geometry_diagnostics
            self.assertEqual(diagnostics["outlier_count"], 0)
            self.assertEqual(diagnostics["outliers"], [])


if __name__ == "__main__":
    unittest.main()
