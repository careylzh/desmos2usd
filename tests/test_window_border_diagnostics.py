from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _path import ROOT
from desmos2usd.validate.window_border_diagnostics import (
    build_window_border_diagnostics,
    write_window_border_diagnostics_markdown,
)


class WindowBorderDiagnosticsTests(unittest.TestCase):
    def test_synthetic_duplicate_and_nested_coplanar_faces_are_measured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            usda = Path(tmp) / "sample.usda"
            usda.write_text(
                """#usda 1.0
def Xform "DesmosGraph"
{
    def Mesh "expr_0001__wide"
    {
        custom string desmos:exprId = "wide"
        custom int desmos:order = 1
        custom string desmos:latex = "y=0"
        custom string desmos:constraints = ""
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#000000"
        custom bool desmos:hidden = false
        point3f[] points = [(0, 0, 0), (2, 0, 0), (2, 0, 2), (0, 0, 2)]
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
    }

    def Mesh "expr_0002__duplicate"
    {
        custom string desmos:exprId = "duplicate"
        custom int desmos:order = 2
        custom string desmos:latex = "y=0"
        custom string desmos:constraints = ""
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#ffffff"
        custom bool desmos:hidden = false
        point3f[] points = [(0, 0, 0), (2, 0, 0), (2, 0, 2), (0, 0, 2)]
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
    }

    def Mesh "expr_0003__nested"
    {
        custom string desmos:exprId = "nested"
        custom int desmos:order = 3
        custom string desmos:latex = "y=0"
        custom string desmos:constraints = ""
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#ff0000"
        custom bool desmos:hidden = false
        point3f[] points = [(0.5, 0, 0.5), (1.5, 0, 0.5), (1.5, 0, 1.5), (0.5, 0, 1.5)]
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
    }
}
""",
                encoding="utf-8",
            )

            diagnostics = build_window_border_diagnostics(
                usda,
                target_expr_ids=("wide",),
                border_planes=(("y", 0.0),),
            )

        self.assertEqual(diagnostics["coplanar_overlap_pair_count"], 2)
        self.assertEqual(diagnostics["full_coverage_pair_count"], 1)
        self.assertEqual(diagnostics["exact_duplicate_full_pair_count"], 1)
        duplicate = diagnostics["strongest_exact_duplicate_full_pairs"][0]
        self.assertEqual(duplicate["duplicate_face_count"], 1)
        self.assertEqual(duplicate["overlap_area"], 4.0)
        nested = next(pair for pair in diagnostics["all_overlap_pairs"] if pair["prim_b"]["expr_id"] == "nested")
        self.assertEqual(nested["overlap_area"], 1.0)
        self.assertEqual(nested["coverage_of_prim_b_on_plane"], 1.0)

    def test_real_k0fbxxwkqf_strict_y_band_border_caps_are_omitted(self) -> None:
        diagnostics = build_window_border_diagnostics(
            ROOT / "artifacts/acceptance/k0fbxxwkqf.usda",
            report_path=ROOT / "artifacts/acceptance/k0fbxxwkqf.report.json",
        )

        self.assertEqual(diagnostics["graph_hash"], "k0fbxxwkqf")
        self.assertEqual(diagnostics["target_prim_count"], 11)
        self.assertEqual(diagnostics["full_coverage_pair_count"], 0)
        self.assertEqual(diagnostics["exact_duplicate_full_pair_count"], 0)
        self.assertIsNone(find_pair_or_none(diagnostics, "expr_0001__3", "expr_0003__13", "y", 20.0))
        self.assertIsNone(find_pair_or_none(diagnostics, "expr_0002__10", "expr_0003__13", "y", -20.0))
        self.assertIn("13", diagnostics["target_expr_ids_without_coplanar_face_overlap"])
        self.assertIn("46", diagnostics["target_expr_ids_without_coplanar_face_overlap"])
        self.assertIn("294", diagnostics["target_expr_ids_without_coplanar_face_overlap"])
        clipped_by_expr = {
            row["expr_id"]: [axis["axis"] for axis in row["viewport_clipped_unbounded_axes"]]
            for row in diagnostics["target_prims"]
        }
        self.assertEqual(clipped_by_expr["3"], ["z"])
        self.assertEqual(clipped_by_expr["10"], ["z"])
        # expr 13 no longer extrudes to viewport z — an inequality region whose LaTeX
        # never references z is now rendered as a flat ground plane at z=0, matching
        # how Desmos 3D treats it. Nothing is clipped because there is no z extent.
        self.assertEqual(clipped_by_expr["13"], [])
        for expr_id in ("46", "79", "80", "81", "294", "298", "312", "323"):
            self.assertEqual(clipped_by_expr[expr_id], [])
        self.assertEqual(
            diagnostics["viewport_clipped_unbounded_target_prims"],
            [
                {"prim_name": "expr_0001__3", "expr_id": "3", "order": 1, "axes": ["z"]},
                {"prim_name": "expr_0002__10", "expr_id": "10", "order": 2, "axes": ["z"]},
            ],
        )
        correlation = diagnostics["viewport_outlier_correlation"]
        self.assertEqual(correlation["total_report_outlier_count"], 11)
        self.assertEqual(correlation["target_report_outlier_count"], 11)
        self.assertEqual(correlation["broad_wall_or_floor_expr_ids"], ["3", "10", "13"])
        self.assertEqual(correlation["roof_arch_or_side_surface_expr_ids"], ["46", "79", "80", "81"])
        self.assertEqual(correlation["window_border_side_slab_expr_ids"], ["294", "298", "312", "323"])
        categories = {row["expr_id"]: row["category"] for row in correlation["rows"]}
        self.assertEqual(categories["3"], "broad_wall_or_floor")
        self.assertEqual(categories["46"], "roof_arch_or_side_surface")
        self.assertEqual(categories["294"], "window_border_side_slab")

    def test_real_k0fbxxwkqf_yz_side_view_projections(self) -> None:
        diagnostics = build_window_border_diagnostics(
            ROOT / "artifacts/acceptance/k0fbxxwkqf.usda",
            report_path=ROOT / "artifacts/acceptance/k0fbxxwkqf.report.json",
        )

        yz = diagnostics["yz_side_view_projections"]
        self.assertGreater(len(yz), 0)

        by_expr = {row["expr_id"]: row for row in yz}

        # expr 13 (y=-20..20, x=-225..225) is now rendered as a flat z=0 ground plane
        # because its LaTeX never references z. y_span stays 40, z_span collapses to 0,
        # and nothing is viewport-clipped on z.
        self.assertAlmostEqual(by_expr["13"]["y_span"], 40.0, places=1)
        self.assertAlmostEqual(by_expr["13"]["z_span"], 0.0, places=5)
        self.assertFalse(by_expr["13"]["viewport_clipped_on_z"])

        # exprs 3 and 10 are flat planes (y_span=0) so yz_area=0
        self.assertAlmostEqual(by_expr["3"]["y_span"], 0.0, places=5)
        self.assertAlmostEqual(by_expr["10"]["y_span"], 0.0, places=5)
        self.assertTrue(by_expr["3"]["viewport_clipped_on_z"])
        self.assertTrue(by_expr["10"]["viewport_clipped_on_z"])

        # roof prims (46,79,80,81) should NOT be viewport-clipped on z
        for expr_id in ("46", "79", "80", "81"):
            self.assertFalse(by_expr[expr_id]["viewport_clipped_on_z"])

    def test_real_k0fbxxwkqf_frozen_view_projections(self) -> None:
        diagnostics = build_window_border_diagnostics(
            ROOT / "artifacts/acceptance/k0fbxxwkqf.usda",
            report_path=ROOT / "artifacts/acceptance/k0fbxxwkqf.report.json",
        )

        fv = diagnostics["frozen_view_projections"]
        self.assertGreater(len(fv), 0)

        by_expr = {row["expr_id"]: row for row in fv}

        # expr 13 should rank first by screen_area in the frozen source view
        self.assertEqual(fv[0]["expr_id"], "13", "expr 13 should rank first by screen_area")

        # expr 13 is an inequality region spanning y=-20..20 and z-clipped.
        # In the frozen view the screen_u direction is approximately world Y,
        # so the screen_u_span should reflect the 40-unit y range.
        self.assertGreater(by_expr["13"]["screen_u_span"], 39.0)
        self.assertGreater(by_expr["13"]["screen_area"], 1000.0)

        # The small roof prims (46,79,80,81) should have much smaller screen_area
        for expr_id in ("46", "79", "80", "81"):
            self.assertLess(
                by_expr[expr_id]["screen_area"],
                by_expr["13"]["screen_area"],
                f"expr {expr_id} screen_area should be smaller than expr 13",
            )

        # Each row should have deterministic rotation vectors recorded
        for row in fv:
            self.assertEqual(len(row["rotation_screen_u"]), 3)
            self.assertEqual(len(row["rotation_screen_v"]), 3)

    def test_markdown_writer_names_exact_duplicate_prims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "window.md"
            diagnostics = build_window_border_diagnostics(
                ROOT / "artifacts/acceptance/k0fbxxwkqf.usda",
                report_path=ROOT / "artifacts/acceptance/k0fbxxwkqf.report.json",
                limit=2,
            )
            write_window_border_diagnostics_markdown(out, diagnostics, limit=2)
            text = out.read_text(encoding="utf-8")

        self.assertIn("full coplanar border overlap", text)
        self.assertIn("exact duplicate face grids", text)
        self.assertIn("expr_0001__3", text)
        self.assertIn("expr_0003__13", text)
        self.assertIn("target expr ids with no coplanar face-area overlap", text)
        self.assertIn("target prims viewport-clipped on otherwise unbounded axes: `3:z, 10:z`", text)
        self.assertIn("z=min+max source viewport", text)
        self.assertIn("## YZ Side-View Projections", text)
        self.assertIn("z_clipped", text)
        self.assertIn("## Frozen Source-View Projections", text)
        self.assertIn("screen_area", text)
        self.assertIn("## Viewport Outlier Correlation", text)
        self.assertIn("window-border side slab expr ids: `294, 298, 312, 323`", text)
        self.assertIn("| `294` | `window-border side slab` |", text)


def find_pair(
    diagnostics: dict,
    left_name: str,
    right_name: str,
    axis: str,
    value: float,
) -> dict:
    names = {left_name, right_name}
    for pair in diagnostics["all_overlap_pairs"]:
        if pair["plane"] == {"axis": axis, "value": value} and {
            pair["prim_a"]["prim_name"],
            pair["prim_b"]["prim_name"],
        } == names:
            return pair
    raise AssertionError(f"missing overlap pair {left_name}/{right_name} on {axis}={value}")


def find_pair_or_none(
    diagnostics: dict,
    left_name: str,
    right_name: str,
    axis: str,
    value: float,
) -> dict | None:
    try:
        return find_pair(diagnostics, left_name, right_name, axis, value)
    except AssertionError:
        return None


if __name__ == "__main__":
    unittest.main()
