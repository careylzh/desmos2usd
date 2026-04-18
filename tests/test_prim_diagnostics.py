from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from _path import ROOT
from desmos2usd.validate.prim_diagnostics import (
    build_prim_diagnostics,
    parse_constant_restriction_bounds,
    parse_usda_prims,
    write_diagnostics_markdown,
)


class PrimDiagnosticsTests(unittest.TestCase):
    def test_parse_usda_prims_and_rank_viewport_outlier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            usda = tmp_path / "sample.usda"
            report = tmp_path / "sample.report.json"
            usda.write_text(
                """#usda 1.0
def Xform "DesmosGraph"
{
    def Mesh "expr_0001__near"
    {
        custom string desmos:exprId = "near"
        custom int desmos:order = 1
        custom string desmos:latex = "z=0"
        custom string desmos:constraints = ""
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#000000"
        custom bool desmos:hidden = false
        point3f[] points = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
    }

    def Mesh "expr_0002__far"
    {
        custom string desmos:exprId = "far"
        custom int desmos:order = 2
        custom string desmos:latex = "z=100"
        custom string desmos:constraints = ""
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#ffffff"
        custom bool desmos:hidden = false
        point3f[] points = [(0, 0, 100), (1, 0, 100), (1, 1, 100), (0, 1, 100)]
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
    }
}
""",
                encoding="utf-8",
            )
            report.write_text(
                json.dumps(
                    {
                        "graph_hash": "sample",
                        "geometry_diagnostics": {
                            "source_viewport_bbox": {
                                "min": [-10, -10, -10],
                                "max": [10, 10, 10],
                                "span": [20, 20, 20],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            parsed = parse_usda_prims(usda)
            diagnostics = build_prim_diagnostics(usda, report_path=report, limit=5)

        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[1].expr_id, "far")
        self.assertEqual(parsed[1].face_count, 1)
        self.assertEqual(diagnostics["viewport_outlier_count"], 1)
        self.assertEqual(diagnostics["viewport_outliers"][0]["expr_id"], "far")
        self.assertEqual(diagnostics["top_suspicious"][0]["prim_name"], "expr_0002__far")
        self.assertEqual(diagnostics["top_suspicious"][0]["viewport_overshoot"]["max"], 90.0)

    def test_parse_constant_restriction_bounds_tracks_strict_and_inclusive_sides(self) -> None:
        bounds = parse_constant_restriction_bounds(
            r"7.85\ge x\gt7.35; \left(-3\right)<y\lt 90+42; z<=6.15; 0<z<-0.01(y+26)(y-26)+7"
        )

        self.assertEqual(bounds["x"]["min"], 7.35)
        self.assertEqual(bounds["x"]["max"], 7.85)
        self.assertFalse(bounds["x"]["min_inclusive"])
        self.assertTrue(bounds["x"]["max_inclusive"])
        self.assertEqual(bounds["y"]["min"], -3.0)
        self.assertEqual(bounds["y"]["max"], 132.0)
        self.assertFalse(bounds["y"]["min_inclusive"])
        self.assertFalse(bounds["y"]["max_inclusive"])
        self.assertEqual(bounds["z"]["min"], 0.0)
        self.assertEqual(bounds["z"]["max"], 6.15)
        self.assertFalse(bounds["z"]["min_inclusive"])
        self.assertTrue(bounds["z"]["max_inclusive"])

    def test_restriction_inset_ranking_compares_bounds_to_exported_bbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            usda = Path(tmp) / "sample.usda"
            usda.write_text(
                """#usda 1.0
def Xform "DesmosGraph"
{
    def Mesh "expr_0001__inset"
    {
        custom string desmos:exprId = "inset"
        custom int desmos:order = 1
        custom string desmos:latex = "z=x"
        custom string desmos:constraints = "-3<x<3; -1\\\\le y\\\\le1; 10>z>5"
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#000000"
        custom bool desmos:hidden = false
        point3f[] points = [(-2.5, -1, 5.5), (2.75, 1, 9)]
        int[] faceVertexCounts = [2]
        int[] faceVertexIndices = [0, 1]
    }
}
""",
                encoding="utf-8",
            )
            diagnostics = build_prim_diagnostics(usda, limit=5)

        self.assertEqual(diagnostics["constant_restriction_prim_count"], 1)
        self.assertEqual(diagnostics["restriction_inset_count"], 1)
        inset_row = diagnostics["top_restriction_insets"][0]
        self.assertEqual(inset_row["expr_id"], "inset")
        self.assertEqual(inset_row["constant_restriction_bounds"]["x"]["min"], -3.0)
        self.assertFalse(inset_row["constant_restriction_bounds"]["x"]["min_inclusive"])
        self.assertEqual(inset_row["restriction_inset"]["positive_side_count"], 4)
        self.assertEqual(inset_row["restriction_inset"]["strict_positive_side_count"], 4)
        self.assertEqual(inset_row["restriction_inset"]["max_strict"], 1.0)

    def test_restriction_inset_reachability_flags_affine_equation_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            usda = Path(tmp) / "sample.usda"
            usda.write_text(
                """#usda 1.0
def Xform "DesmosGraph"
{
    def Mesh "expr_0001__limited"
    {
        custom string desmos:exprId = "limited"
        custom int desmos:order = 1
        custom string desmos:latex = "z=2y"
        custom string desmos:constraints = "0<y<2; 0<z<7"
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#000000"
        custom bool desmos:hidden = false
        point3f[] points = [(0, 0, 0), (1, 2, 4)]
        int[] faceVertexCounts = [2]
        int[] faceVertexIndices = [0, 1]
    }
}
""",
                encoding="utf-8",
            )
            diagnostics = build_prim_diagnostics(usda, limit=5)

        row = diagnostics["top_restriction_insets"][0]
        reachability = row["restriction_bound_reachability"]
        self.assertEqual(reachability["equation_limited_side_count"], 1)
        side = reachability["sides"][0]
        self.assertEqual(side["classification"], "equation_limited_by_other_restrictions")
        self.assertEqual(side["limiting_axis"], "y")
        self.assertEqual(side["limiting_side"], "max")
        self.assertEqual(side["reachable_extreme_without_compared_bound"], 4.0)
        self.assertEqual(side["gap_to_compared_bound"], 3.0)

    def test_boundary_gap_ranking_uses_internal_unmatched_mesh_edges(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            usda = Path(tmp) / "sample.usda"
            usda.write_text(
                """#usda 1.0
def Xform "DesmosGraph"
{
    def Mesh "expr_0001__open"
    {
        custom string desmos:exprId = "open"
        custom int desmos:order = 1
        custom string desmos:latex = "x=1"
        custom string desmos:constraints = ""
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#000000"
        custom bool desmos:hidden = false
        point3f[] points = [(1, 1, 1), (1, 2, 1), (1, 2, 2), (1, 1, 2)]
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
    }

    def Mesh "expr_0002__neighbor"
    {
        custom string desmos:exprId = "neighbor"
        custom int desmos:order = 2
        custom string desmos:latex = "x=1"
        custom string desmos:constraints = ""
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#ffffff"
        custom bool desmos:hidden = false
        point3f[] points = [(1, 2, 1), (1, 3, 1), (1, 3, 2), (1, 2, 2)]
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
    }

    def Mesh "expr_0003__bbox"
    {
        custom string desmos:exprId = "bbox"
        custom int desmos:order = 3
        custom string desmos:latex = "bbox helper"
        custom string desmos:constraints = ""
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#cccccc"
        custom bool desmos:hidden = false
        point3f[] points = [(0, 0, 0), (2, 4, 3)]
    }
}
""",
                encoding="utf-8",
            )
            diagnostics = build_prim_diagnostics(usda, limit=5)

        self.assertEqual(diagnostics["boundary_gap_count"], 2)
        culprit = diagnostics["top_boundary_gaps"][0]
        self.assertEqual(culprit["expr_id"], "open")
        adjacency = culprit["boundary_adjacency"]
        self.assertEqual(adjacency["boundary_edge_count"], 4)
        self.assertEqual(adjacency["exact_matched_boundary_edge_count"], 1)
        self.assertEqual(adjacency["unmatched_boundary_edge_count"], 3)
        self.assertEqual(adjacency["internal_unmatched_boundary_edge_count"], 3)
        self.assertAlmostEqual(adjacency["internal_unmatched_boundary_edge_length"], 3.0)
        self.assertEqual(adjacency["source_bound_supported_internal_unmatched_boundary_edge_count"], 0)
        self.assertEqual(adjacency["unexplained_internal_unmatched_boundary_edge_count"], 3)
        self.assertAlmostEqual(adjacency["unexplained_internal_unmatched_boundary_edge_length"], 3.0)
        self.assertAlmostEqual(adjacency["longest_internal_unmatched_boundary_edge"]["length"], 1.0)

    def test_boundary_gap_rows_split_strict_source_bound_supported_edges_from_unexplained(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            usda = Path(tmp) / "sample.usda"
            usda.write_text(
                """#usda 1.0
def Xform "DesmosGraph"
{
    def Mesh "expr_0001__bounded"
    {
        custom string desmos:exprId = "bounded"
        custom int desmos:order = 1
        custom string desmos:latex = "x=1"
        custom string desmos:constraints = "0<y<1"
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#000000"
        custom bool desmos:hidden = false
        point3f[] points = [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)]
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
    }

    def Mesh "expr_0002__bbox"
    {
        custom string desmos:exprId = "bbox"
        custom int desmos:order = 2
        custom string desmos:latex = "bbox helper"
        custom string desmos:constraints = ""
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#cccccc"
        custom bool desmos:hidden = false
        point3f[] points = [(-5, -5, -5), (5, 5, 5)]
    }
}
""",
                encoding="utf-8",
            )
            diagnostics = build_prim_diagnostics(usda, limit=5)

        bounded = diagnostics["top_boundary_gaps"][0]
        self.assertEqual(bounded["expr_id"], "bounded")
        adjacency = bounded["boundary_adjacency"]
        self.assertEqual(adjacency["internal_unmatched_boundary_edge_count"], 4)
        self.assertAlmostEqual(adjacency["internal_unmatched_boundary_edge_length"], 4.0)
        self.assertEqual(adjacency["source_bound_supported_internal_unmatched_boundary_edge_count"], 2)
        self.assertAlmostEqual(adjacency["source_bound_supported_internal_unmatched_boundary_edge_length"], 2.0)
        self.assertEqual(adjacency["unexplained_internal_unmatched_boundary_edge_count"], 2)
        self.assertAlmostEqual(adjacency["unexplained_internal_unmatched_boundary_edge_length"], 2.0)
        self.assertEqual(
            adjacency["source_bound_supported_internal_unmatched_boundary_edge_refs"],
            [
                {
                    "axis": "y",
                    "side": "high",
                    "bound": 1.0,
                    "bound_expr": "1",
                    "edge_count": 1,
                    "edge_length": 1.0,
                    "longest_edge": {
                        "length": 1.0,
                        "start": (1.0, 1.0, 0.0),
                        "end": (1.0, 1.0, 1.0),
                        "midpoint": (1.0, 1.0, 0.5),
                    },
                },
                {
                    "axis": "y",
                    "side": "low",
                    "bound": 0.0,
                    "bound_expr": "0",
                    "edge_count": 1,
                    "edge_length": 1.0,
                    "longest_edge": {
                        "length": 1.0,
                        "start": (1.0, 0.0, 0.0),
                        "end": (1.0, 0.0, 1.0),
                        "midpoint": (1.0, 0.0, 0.5),
                    },
                },
            ],
        )

    def test_boundary_gap_rows_include_near_neighbor_edge_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            usda = Path(tmp) / "sample.usda"
            usda.write_text(
                """#usda 1.0
def Xform "DesmosGraph"
{
    def Mesh "expr_0001__open"
    {
        custom string desmos:exprId = "open"
        custom int desmos:order = 1
        custom string desmos:latex = "x=1"
        custom string desmos:constraints = ""
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#000000"
        custom bool desmos:hidden = false
        point3f[] points = [(1, 0, 0), (1, 0, 2), (1, 1, 2), (1, 1, 0)]
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
    }

    def Mesh "expr_0002__near"
    {
        custom string desmos:exprId = "near"
        custom int desmos:order = 2
        custom string desmos:latex = "x=1"
        custom string desmos:constraints = ""
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#ffffff"
        custom bool desmos:hidden = false
        point3f[] points = [(1, -0.05, 0), (1, -0.05, 2), (1, -1, 2), (1, -1, 0)]
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
    }

    def Mesh "expr_0003__bbox"
    {
        custom string desmos:exprId = "bbox"
        custom int desmos:order = 3
        custom string desmos:latex = "bbox helper"
        custom string desmos:constraints = ""
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#cccccc"
        custom bool desmos:hidden = false
        point3f[] points = [(-5, -5, -5), (5, 5, 5)]
    }
}
""",
                encoding="utf-8",
            )
            diagnostics = build_prim_diagnostics(usda, limit=5, include_boundary_near_candidates=True)

        open_row = next(row for row in diagnostics["top_boundary_gaps"] if row["expr_id"] == "open")
        adjacency = open_row["boundary_adjacency"]
        self.assertGreater(adjacency["near_neighbor_candidate_count"], 0)
        candidate = adjacency["best_near_neighbor_boundary_edges"][0]
        self.assertEqual(candidate["candidate_expr_id"], "near")
        self.assertEqual(candidate["shared_planes"], [{"axis": "x", "value": 1.0}])
        self.assertAlmostEqual(candidate["midpoint_distance"], 0.05)
        self.assertAlmostEqual(candidate["endpoint_pair_distance"], 0.1)
        self.assertAlmostEqual(candidate["length_delta"], 0.0)
        self.assertEqual(candidate["source_edge"]["midpoint"], (1.0, 0.0, 1.0))
        self.assertEqual(candidate["candidate_edge"]["midpoint"], (1.0, -0.05, 1.0))
        self.assertEqual(
            adjacency["longest_internal_unmatched_boundary_edge_near_candidate"]["candidate_expr_id"],
            "near",
        )

    def test_boundary_gap_rows_split_sampled_domain_bounds_from_unexplained(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            usda = Path(tmp) / "sample.usda"
            usda.write_text(
                """#usda 1.0
def Xform "DesmosGraph"
{
    def Mesh "expr_0001__sampled"
    {
        custom string desmos:exprId = "sampled"
        custom int desmos:order = 1
        custom string desmos:latex = "y=0"
        custom string desmos:constraints = "0<x<1; 0<z<2"
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#000000"
        custom bool desmos:hidden = false
        point3f[] points = [(0, 0, 0.25), (0.5, 0, 0.25), (1, 0, 0.25), (0, 0, 1), (0.5, 0, 1), (1, 0, 1), (0, 0, 1.75), (0.5, 0, 1.75), (1, 0, 1.75)]
        int[] faceVertexCounts = [4, 4, 4, 4]
        int[] faceVertexIndices = [0, 1, 4, 3, 1, 2, 5, 4, 3, 4, 7, 6, 4, 5, 8, 7]
    }

    def Mesh "expr_0002__bbox"
    {
        custom string desmos:exprId = "bbox"
        custom int desmos:order = 2
        custom string desmos:latex = "bbox helper"
        custom string desmos:constraints = ""
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#cccccc"
        custom bool desmos:hidden = false
        point3f[] points = [(-5, -5, -5), (5, 5, 5)]
    }
}
""",
                encoding="utf-8",
            )
            diagnostics = build_prim_diagnostics(usda, limit=5)

        sampled = diagnostics["top_sampled_domain_bound_boundary_gaps"][0]
        self.assertEqual(sampled["expr_id"], "sampled")
        adjacency = sampled["boundary_adjacency"]
        self.assertEqual(adjacency["source_bound_supported_internal_unmatched_boundary_edge_count"], 4)
        self.assertAlmostEqual(adjacency["source_bound_supported_internal_unmatched_boundary_edge_length"], 3.0)
        self.assertEqual(adjacency["sampled_domain_bound_internal_unmatched_boundary_edge_count"], 4)
        self.assertAlmostEqual(adjacency["sampled_domain_bound_internal_unmatched_boundary_edge_length"], 2.0)
        self.assertEqual(adjacency["unexplained_internal_unmatched_boundary_edge_count"], 0)
        self.assertEqual(
            [
                (
                    ref["axis"],
                    ref["side"],
                    ref["sampled_value"],
                    ref["source_bound"],
                    ref["edge_count"],
                )
                for ref in adjacency["sampled_domain_bound_internal_unmatched_boundary_edge_refs"]
            ],
            [
                ("z", "high", 1.75, 2.0, 2),
                ("z", "low", 0.25, 0.0, 2),
            ],
        )

    def test_sampled_domain_bound_uses_parsed_function_bound_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            usda = Path(tmp) / "sample.usda"
            usda.write_text(
                """#usda 1.0
def Xform "DesmosGraph"
{
    def Mesh "expr_0001__sampled"
    {
        custom string desmos:exprId = "sampled"
        custom int desmos:order = 1
        custom string desmos:latex = "y=0"
        custom string desmos:constraints = "0<x<1; 0<z<y+2"
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#000000"
        custom bool desmos:hidden = false
        point3f[] points = [(0, 0, 0.25), (0.5, 0, 0.25), (1, 0, 0.25), (0, 0, 1), (0.5, 0, 1), (1, 0, 1), (0, 0, 1.75), (0.5, 0, 1.75), (1, 0, 1.75)]
        int[] faceVertexCounts = [4, 4, 4, 4]
        int[] faceVertexIndices = [0, 1, 4, 3, 1, 2, 5, 4, 3, 4, 7, 6, 4, 5, 8, 7]
    }

    def Mesh "expr_0002__bbox"
    {
        custom string desmos:exprId = "bbox"
        custom int desmos:order = 2
        custom string desmos:latex = "bbox helper"
        custom string desmos:constraints = ""
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#cccccc"
        custom bool desmos:hidden = false
        point3f[] points = [(-5, -5, -5), (5, 5, 5)]
    }
}
""",
                encoding="utf-8",
            )
            diagnostics = build_prim_diagnostics(usda, limit=5)

        sampled = diagnostics["top_sampled_domain_bound_boundary_gaps"][0]
        adjacency = sampled["boundary_adjacency"]
        self.assertEqual(adjacency["sampled_domain_bound_internal_unmatched_boundary_edge_count"], 4)
        refs = adjacency["sampled_domain_bound_internal_unmatched_boundary_edge_refs"]
        self.assertEqual(
            [
                (
                    ref["axis"],
                    ref["side"],
                    ref["support_kind"],
                    ref["support_bound_expr"],
                    ref["support_bound_identifiers"],
                    ref["edge_count"],
                )
                for ref in refs
            ],
            [
                ("z", "high", "parsed_predicate_bound", "y+2", ["y"], 2),
                ("z", "low", "parsed_constant_bound", "0", [], 2),
            ],
        )

    def test_sampled_domain_bound_rejects_axis_mentions_without_parsed_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            usda = Path(tmp) / "sample.usda"
            usda.write_text(
                """#usda 1.0
def Xform "DesmosGraph"
{
    def Mesh "expr_0001__mentioned"
    {
        custom string desmos:exprId = "mentioned"
        custom int desmos:order = 1
        custom string desmos:latex = "y=0"
        custom string desmos:constraints = "z+y<2"
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#000000"
        custom bool desmos:hidden = false
        point3f[] points = [(0, 0, 0.25), (0.5, 0, 0.25), (1, 0, 0.25), (0, 0, 1), (0.5, 0, 1), (1, 0, 1), (0, 0, 1.75), (0.5, 0, 1.75), (1, 0, 1.75)]
        int[] faceVertexCounts = [4, 4, 4, 4]
        int[] faceVertexIndices = [0, 1, 4, 3, 1, 2, 5, 4, 3, 4, 7, 6, 4, 5, 8, 7]
    }

    def Mesh "expr_0002__bbox"
    {
        custom string desmos:exprId = "bbox"
        custom int desmos:order = 2
        custom string desmos:latex = "bbox helper"
        custom string desmos:constraints = ""
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#cccccc"
        custom bool desmos:hidden = false
        point3f[] points = [(-5, -5, -5), (5, 5, 5)]
    }
}
""",
                encoding="utf-8",
            )
            diagnostics = build_prim_diagnostics(usda, limit=5)

        mentioned = diagnostics["top_boundary_gaps"][0]
        adjacency = mentioned["boundary_adjacency"]
        self.assertEqual(adjacency["sampled_domain_bound_internal_unmatched_boundary_edge_count"], 0)
        self.assertEqual(adjacency["unexplained_internal_unmatched_boundary_edge_count"], 8)

    def test_sampled_predicate_clip_classifies_domain_edges_from_explicit_axis_predicate(self) -> None:
        """When the explicit axis (z) has a predicate bound depending on a domain axis (y),
        boundary edges at the domain axis extreme sample values should be classified as
        sampled_predicate_clip rather than unexplained."""
        with tempfile.TemporaryDirectory() as tmp:
            usda = Path(tmp) / "sample.usda"
            # z = f(x) with constraints: 0 < x < 1 (constant) and 0 < z < -0.01(y+26)(y-26)+7
            # The z constraint depends on y, indirectly limiting the y domain.
            # The explicit axis is z, domain axes are x and y.
            # x has constant bounds → source_bound_support.
            # y has NO constant bounds but the z-predicate depends on y → sampled_predicate_clip.
            usda.write_text(
                """#usda 1.0
def Xform "DesmosGraph"
{
    def Mesh "expr_0001__clipped"
    {
        custom string desmos:exprId = "clipped"
        custom int desmos:order = 1
        custom string desmos:latex = "z=-1.36y+6.7"
        custom string desmos:constraints = "2<x<3; 0<z<-0.01*(y+26)*(y-26)+7"
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#000000"
        custom bool desmos:hidden = false
        point3f[] points = [(2, -3.5, 0.25), (2.5, -3.5, 0.25), (3, -3.5, 0.25), (2, 0, 0.25), (2.5, 0, 0.25), (3, 0, 0.25), (2, 3.5, 0.25), (2.5, 3.5, 0.25), (3, 3.5, 0.25)]
        int[] faceVertexCounts = [4, 4, 4, 4]
        int[] faceVertexIndices = [0, 1, 4, 3, 1, 2, 5, 4, 3, 4, 7, 6, 4, 5, 8, 7]
    }

    def Mesh "expr_0002__bbox"
    {
        custom string desmos:exprId = "bbox"
        custom int desmos:order = 2
        custom string desmos:latex = "bbox helper"
        custom string desmos:constraints = ""
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#cccccc"
        custom bool desmos:hidden = false
        point3f[] points = [(-10, -10, -10), (10, 10, 10)]
    }
}
""",
                encoding="utf-8",
            )
            diagnostics = build_prim_diagnostics(usda, limit=5)

        clipped = [row for row in diagnostics["top_boundary_gaps"] if row["expr_id"] == "clipped"][0]
        adjacency = clipped["boundary_adjacency"]
        # x edges are source-bound-supported (strict bounds 2 and 3)
        self.assertGreater(adjacency["source_bound_supported_internal_unmatched_boundary_edge_count"], 0)
        # y edges should be predicate-clip-supported, not unexplained
        self.assertGreater(adjacency["sampled_predicate_clip_internal_unmatched_boundary_edge_count"], 0)
        self.assertEqual(adjacency["unexplained_internal_unmatched_boundary_edge_count"], 0)
        # Check the refs
        refs = adjacency["sampled_predicate_clip_internal_unmatched_boundary_edge_refs"]
        self.assertTrue(len(refs) > 0)
        for ref in refs:
            self.assertEqual(ref["axis"], "y")
            self.assertEqual(ref["explicit_axis"], "z")
            self.assertIn("y", ref["depends_on"])
        # Should appear in the predicate clip gap list
        self.assertGreater(diagnostics["sampled_predicate_clip_boundary_gap_count"], 0)

    def test_real_ghnr7txz47_acceptance_artifact_has_no_viewport_outliers(self) -> None:
        """After solved-axis viewport suppression, expr 835 no longer produces
        geometry outside the viewport, so the outlier count should be 0."""
        diagnostics = build_prim_diagnostics(
            ROOT / "artifacts/acceptance/ghnr7txz47.usda",
            report_path=ROOT / "artifacts/acceptance/ghnr7txz47.report.json",
            limit=5,
        )

        self.assertEqual(diagnostics["prim_count"], 617)
        self.assertEqual(diagnostics["viewport_outlier_count"], 0)

    def test_real_zaqxhna15w_acceptance_artifact_surfaces_bound_inset_candidate(self) -> None:
        diagnostics = build_prim_diagnostics(
            ROOT / "artifacts/acceptance/zaqxhna15w.usda",
            report_path=ROOT / "artifacts/acceptance/zaqxhna15w.report.json",
            limit=5,
            include_boundary_near_candidates=True,
        )

        self.assertEqual(diagnostics["graph_hash"], "zaqxhna15w")
        self.assertEqual(diagnostics["prim_count"], 268)
        self.assertEqual(diagnostics["viewport_outlier_count"], 0)
        self.assertEqual(diagnostics["restriction_inset_count"], 4)
        self.assertEqual(diagnostics["same_line_partition_mismatch_prim_count"], 0)
        # Half-open predicate evaluation prevents overlapping boundary faces
        # (which caused wedge-like seam artifacts from z-fighting at boundaries
        # with approximate z-value mismatches).  Boundary-nudge sample points
        # keep the mesh within ~2e-5 of the domain edge so the gap is invisible.
        # The 8 unexplained gaps are from nudge-edge boundaries that the
        # diagnostics classifier doesn't attribute to a known cause; they are
        # geometrically correct (~1 unit along x at the domain boundary).
        self.assertEqual(diagnostics["boundary_gap_count"], 264)
        self.assertEqual(diagnostics["unexplained_boundary_gap_count"], 8)
        self.assertEqual(diagnostics["sampled_domain_bound_boundary_gap_count"], 264)
        self.assertEqual(diagnostics["sampled_predicate_clip_boundary_gap_count"], 120)
        self.assertEqual(diagnostics["source_bound_supported_only_boundary_gap_count"], 0)
        sampled_gap = diagnostics["top_sampled_domain_bound_boundary_gaps"][0]
        self.assertEqual(sampled_gap["prim_name"], "expr_0001__1")
        self.assertEqual(sampled_gap["expr_id"], "1")
        self.assertEqual(
            sampled_gap["boundary_adjacency"]["sampled_domain_bound_internal_unmatched_boundary_edge_count"],
            66,
        )
        self.assertAlmostEqual(
            sampled_gap["boundary_adjacency"]["sampled_domain_bound_internal_unmatched_boundary_edge_length"],
            69.99996,
            places=3,
        )
        self.assertEqual(
            sampled_gap["boundary_adjacency"]["unexplained_internal_unmatched_boundary_edge_count"],
            0,
        )
        self.assertEqual(
            [
                (ref["axis"], ref["side"], ref["edge_count"])
                for ref in sampled_gap["boundary_adjacency"][
                    "sampled_domain_bound_internal_unmatched_boundary_edge_refs"
                ]
            ],
            [("x", "high", 18), ("y", "high", 48)],
        )
        predicate_clip_gap = diagnostics["top_sampled_predicate_clip_boundary_gaps"][0]
        self.assertEqual(predicate_clip_gap["prim_name"], "expr_0103__273")
        self.assertEqual(predicate_clip_gap["expr_id"], "273")
        self.assertEqual(
            predicate_clip_gap["boundary_adjacency"]["sampled_predicate_clip_internal_unmatched_boundary_edge_count"],
            36,
        )
        self.assertEqual(
            predicate_clip_gap["boundary_adjacency"]["unexplained_internal_unmatched_boundary_edge_count"],
            0,
        )
        clip_refs = predicate_clip_gap["boundary_adjacency"]["sampled_predicate_clip_internal_unmatched_boundary_edge_refs"]
        self.assertEqual(
            [(ref["axis"], ref["side"], ref["explicit_axis"], ref["edge_count"]) for ref in clip_refs],
            [
                ("y", "high", "z", 18),
                ("y", "high", "z", 18),
                ("y", "low", "z", 18),
                ("y", "low", "z", 18),
            ],
        )
        culprit = diagnostics["top_restriction_insets"][0]
        self.assertEqual(culprit["prim_name"], "expr_0089__212")
        self.assertEqual(culprit["expr_id"], "212")
        self.assertEqual(culprit["restriction_inset"]["positive_sides"][0]["axis"], "z")
        self.assertEqual(culprit["restriction_inset"]["positive_sides"][0]["side"], "high")
        self.assertAlmostEqual(culprit["restriction_inset"]["max_strict"], 3.476)
        self.assertEqual(
            diagnostics["restriction_inset_reachability_counts"],
            {"equation_limited_by_other_restrictions": 4},
        )
        for row in diagnostics["top_restriction_insets"]:
            reachability = row["restriction_bound_reachability"]
            self.assertEqual(reachability["equation_limited_side_count"], 1)
            side = reachability["sides"][0]
            self.assertEqual(side["classification"], "equation_limited_by_other_restrictions")
            self.assertEqual(side["axis"], "z")
            self.assertEqual(side["side"], "high")
            self.assertAlmostEqual(side["reachable_extreme_without_compared_bound"], 3.524)
            self.assertAlmostEqual(side["gap_to_compared_bound"], 3.476)

    def test_same_line_partition_mismatch_identifies_overlapping_seam_with_different_segments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            usda = Path(tmp) / "sample.usda"
            usda.write_text(
                """#usda 1.0
def Xform "DesmosGraph"
{
    def Mesh "expr_0001__source"
    {
        custom string desmos:exprId = "source"
        custom int desmos:order = 1
        custom string desmos:latex = "y=0"
        custom string desmos:constraints = ""
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#000000"
        custom bool desmos:hidden = false
        point3f[] points = [(0, 0, 0), (0.5, 0, 0), (1, 0, 0), (0, 0, 1), (0.5, 0, 1), (1, 0, 1)]
        int[] faceVertexCounts = [4, 4]
        int[] faceVertexIndices = [0, 1, 4, 3, 1, 2, 5, 4]
    }

    def Mesh "expr_0002__candidate"
    {
        custom string desmos:exprId = "candidate"
        custom int desmos:order = 2
        custom string desmos:latex = "z=1"
        custom string desmos:constraints = ""
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#ffffff"
        custom bool desmos:hidden = false
        point3f[] points = [(0, -1, 1), (1, -1, 1), (1, 0, 1), (0, 0, 1)]
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
    }

    def Mesh "expr_0003__bbox"
    {
        custom string desmos:exprId = "bbox"
        custom int desmos:order = 3
        custom string desmos:latex = "bbox helper"
        custom string desmos:constraints = ""
        custom string desmos:kind = "explicit_surface"
        custom string desmos:color = "#cccccc"
        custom bool desmos:hidden = false
        point3f[] points = [(-2, -2, -2), (2, 2, 2)]
    }
}
""",
                encoding="utf-8",
            )
            diagnostics = build_prim_diagnostics(usda, limit=5, include_boundary_near_candidates=True)

        source_row = next(row for row in diagnostics["top_boundary_gaps"] if row["expr_id"] == "source")
        adjacency = source_row["boundary_adjacency"]
        self.assertEqual(adjacency["same_line_partition_mismatch_count"], 1)
        mismatch = adjacency["best_same_line_partition_mismatches"][0]
        self.assertEqual(mismatch["candidate_expr_id"], "candidate")
        self.assertEqual(
            mismatch["line_planes"],
            [{"axis": "y", "value": 0.0}, {"axis": "z", "value": 1.0}],
        )
        self.assertEqual(mismatch["varying_axis"], "x")
        self.assertEqual(mismatch["source_edges_overlapped_count"], 2)
        self.assertEqual(mismatch["candidate_edges_overlapping_source_count"], 1)
        self.assertEqual(mismatch["exact_overlapping_edge_match_count"], 0)
        self.assertAlmostEqual(mismatch["overlap_length"], 1.0)
        self.assertEqual(mismatch["source_partition_points_in_overlap"], [0.0, 0.5, 1.0])
        self.assertEqual(mismatch["candidate_partition_points_in_overlap"], [0.0, 1.0])

    def test_markdown_writer_is_human_usable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "diagnostics.md"
            diagnostics = build_prim_diagnostics(
                ROOT / "artifacts/acceptance/ghnr7txz47.usda",
                report_path=ROOT / "artifacts/acceptance/ghnr7txz47.report.json",
                limit=1,
            )
            write_diagnostics_markdown(out, diagnostics, limit=1)
            text = out.read_text(encoding="utf-8")

        self.assertIn("## Strongest Culprit", text)
        self.assertIn("## Restriction Inset Hypothesis", text)
        self.assertIn("## Boundary Gap Hypothesis", text)
        self.assertIn("expr_0214__202", text)


if __name__ == "__main__":
    unittest.main()
