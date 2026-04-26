from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _path import ROOT
from desmos2usd.converter import convert_url
from desmos2usd.ir import GraphIR, SourceInfo
from desmos2usd.usd.package import package_usdz, validate_usdz_arkit
from desmos2usd.usd.writer import write_usda


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
            self.assertIn('defaultPrim = "DesmosGraph"', text)
            self.assertIn("metersPerUnit = 1", text)
            self.assertIn("custom string desmos:latex", text)
            self.assertIn("custom string desmos:constraints", text)
            self.assertIn('string "desmos:viewportBounds" =', text)
            self.assertIn('string "desmos:worldRotation3D" =', text)
            self.assertIn('string "desmos:axis3D" =', text)
            self.assertIn('string "desmos:threeDMode" = "true"', text)
            self.assertIsNone(report.usdz_output)
            self.assertIsNone(report.usdz_package)
            self.assertIsNone(report.usdz_validation)
            self.assertEqual(report.prim_count + report.unsupported_count, report.renderable_expression_count)
            self.assertIn("world_rotation_3d", report.view_metadata)
            self.assertIn("axis_3d", report.view_metadata)

            diagnostics = report.geometry_diagnostics
            self.assertEqual(diagnostics["outlier_count"], 0)
            self.assertEqual(diagnostics["outliers"], [])

    @unittest.skipUnless(shutil.which("usdcat"), "usdcat unavailable")
    def test_usda_loads_with_usdcat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "minimal.usda"
            write_usda(output, minimal_graph(), [])
            result = subprocess.run(["usdcat", "-l", str(output)], check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("OK", result.stdout)

    @unittest.skipUnless(
        shutil.which("usdzip") and shutil.which("usdchecker"),
        "usdzip and usdchecker unavailable",
    )
    def test_usdz_package_validates_with_arkit_checker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "minimal.usda"
            usdz_output = Path(tmp) / "minimal.usdz"
            write_usda(output, minimal_graph(), [])

            package_result = package_usdz(output, usdz_output)
            validation_result = validate_usdz_arkit(usdz_output)

            self.assertTrue(usdz_output.exists())
            self.assertEqual(package_result.returncode, 0)
            self.assertEqual(validation_result.returncode, 0)
            self.assertIn("Success", validation_result.stdout)
            self.assertFalse((Path(tmp) / "(A Document Being Saved By usdzip)").exists())


def minimal_graph() -> GraphIR:
    return GraphIR(
        source=SourceInfo(
            url="https://www.desmos.com/3d/minimal",
            graph_hash="minimal",
            state_url="https://www.desmos.com/calculator_api/minimal",
            title="Minimal",
            viewport_bounds={"x": (-1.0, 1.0), "y": (-1.0, 1.0), "z": (-1.0, 1.0)},
        ),
        expressions=[],
        raw_state={},
    )


if __name__ == "__main__":
    unittest.main()
