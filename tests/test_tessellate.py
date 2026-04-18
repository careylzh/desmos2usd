from __future__ import annotations

import unittest

from _path import ROOT
from desmos2usd.desmos_state import load_fixture_state
from desmos2usd.converter import build_explicit_surface_partition_hints, classified_expression_key
from desmos2usd.ir import graph_ir_from_state
from desmos2usd.parse.classify import classify_graph
from desmos2usd.tessellate import tessellate
from desmos2usd.validate.equations import validate_geometry


class TessellationTests(unittest.TestCase):
    def test_deterministic_geometry(self) -> None:
        graph = graph_ir_from_state(load_fixture_state("https://www.desmos.com/3d/k0fbxxwkqf", ROOT))
        result = classify_graph(graph)
        first = [tessellate(item, result.context, resolution=8).deterministic_key() for item in result.classified]
        second = [tessellate(item, result.context, resolution=8).deterministic_key() for item in result.classified]
        self.assertEqual(first, second)

    def test_k0fbxxwkqf_road_region_renders_flat_when_z_unreferenced(self) -> None:
        graph = graph_ir_from_state(load_fixture_state("https://www.desmos.com/3d/k0fbxxwkqf", ROOT))
        result = classify_graph(graph)
        item = {classified.ir.expr_id: classified for classified in result.classified}["13"]

        geometry = tessellate(item, result.context, resolution=8)
        z_values = [point[2] for point in geometry.points]

        self.assertEqual(item.ir.latex, r"20>y>-20\left\{-225<x<225\right\}")
        self.assertGreater(geometry.face_count, 0)
        # Desmos renders an inequality with no z reference as a flat ground plane at z=0,
        # not a viewport-sized 3D volume.
        self.assertEqual(min(z_values), 0.0)
        self.assertEqual(max(z_values), 0.0)

    def test_k0fbxxwkqf_road_region_omits_strict_y_boundary_caps(self) -> None:
        graph = graph_ir_from_state(load_fixture_state("https://www.desmos.com/3d/k0fbxxwkqf", ROOT))
        result = classify_graph(graph)
        item = {classified.ir.expr_id: classified for classified in result.classified}["13"]

        geometry = tessellate(item, result.context, resolution=8)

        self.assertEqual(item.ir.latex, r"20>y>-20\left\{-225<x<225\right\}")
        self.assertGreater(geometry.face_count, 0)
        self.assertEqual(count_coplanar_faces(geometry, axis="y", value=20.0), 0)
        self.assertEqual(count_coplanar_faces(geometry, axis="y", value=-20.0), 0)

    def test_k0fbxxwkqf_side_planes_use_viewport_for_unconstrained_z(self) -> None:
        graph = graph_ir_from_state(load_fixture_state("https://www.desmos.com/3d/k0fbxxwkqf", ROOT))
        result = classify_graph(graph)
        item = {classified.ir.expr_id: classified for classified in result.classified}["3"]

        geometry = tessellate(item, result.context, resolution=8)
        z_values = [point[2] for point in geometry.points]
        y_values = [point[1] for point in geometry.points]

        self.assertEqual(item.ir.latex, r"y=20\left\{-225<x<225\right\}")
        self.assertGreater(geometry.face_count, 0)
        self.assertNotEqual((min(z_values), max(z_values)), (-393.75, 393.75))
        self.assertAlmostEqual(min(z_values), graph.source.viewport_bounds["z"][0])
        self.assertAlmostEqual(max(z_values), graph.source.viewport_bounds["z"][1])
        self.assertTrue(all(abs(y - 20.0) < 1e-6 for y in y_values))

    def test_geometry_validates_supported_subset(self) -> None:
        graph = graph_ir_from_state(load_fixture_state("https://www.desmos.com/3d/yuqwjsfvsc", ROOT))
        result = classify_graph(graph)
        unsupported = []
        for item in result.classified:
            try:
                geometry = tessellate(item, result.context, resolution=8)
            except ValueError as exc:
                unsupported.append((item.ir.expr_id, str(exc)))
                continue
            report = validate_geometry(item, geometry, result.context)
            self.assertTrue(report.valid, report)
        self.assertEqual(len(unsupported), 0)

    def test_real_fixture_blocker_examples_validate(self) -> None:
        examples = {
            "zaqxhna15w": {"76", "95", "309", "500"},
            "ghnr7txz47": {"302", "434"},
            "yuqwjsfvsc": {"379", "417"},
            "vyp9ogyimt": {"461", "475", "500", "542"},
        }
        for graph_hash, expr_ids in examples.items():
            graph = graph_ir_from_state(load_fixture_state(f"https://www.desmos.com/3d/{graph_hash}", ROOT))
            result = classify_graph(graph)
            by_id = {item.ir.expr_id: item for item in result.classified}
            for expr_id in expr_ids:
                with self.subTest(graph_hash=graph_hash, expr_id=expr_id):
                    item = by_id[expr_id]
                    geometry = tessellate(item, result.context, resolution=8)
                    report = validate_geometry(item, geometry, result.context)
                    self.assertGreater(geometry.face_count, 0)
                    self.assertTrue(report.valid, report)

    def test_ghnr7txz47_non_surface_reports_do_not_fake_equation_residuals(self) -> None:
        graph = graph_ir_from_state(load_fixture_state("https://www.desmos.com/3d/ghnr7txz47", ROOT))
        result = classify_graph(graph)
        by_id = {item.ir.expr_id: item for item in result.classified}
        examples = {
            "191": (
                "inequality_region",
                r"-8\le y\le8\left\{15\le x\le25\right\}\left\{20\le z\le40\right\}",
                None,
            ),
            "166": (
                "parametric_curve",
                r"(25,8,40)+t*((15,8,40)-(25,8,40))",
                0.0,
            ),
            "940": (
                "triangle_mesh",
                r"\operatorname{triangle}((-15,8,40),(-20,0,50),(-25,8,40))",
                None,
            ),
        }

        for expr_id, (kind, latex, expected_residual) in examples.items():
            with self.subTest(expr_id=expr_id):
                item = by_id[expr_id]
                geometry = tessellate(item, result.context, resolution=8)
                report = validate_geometry(item, geometry, result.context)

                self.assertEqual(item.kind, kind)
                self.assertEqual(item.ir.latex, latex)
                self.assertTrue(report.valid, report)
                self.assertEqual(report.constraint_violation_count, 0)
                if expected_residual is None:
                    self.assertIsNone(report.max_residual)
                else:
                    self.assertIsNotNone(report.max_residual)
                    self.assertAlmostEqual(report.max_residual, expected_residual)

    def test_zaqxhna15w_explicit_surface_hints_preserve_shared_line_partition(self) -> None:
        graph = graph_ir_from_state(load_fixture_state("https://www.desmos.com/3d/zaqxhna15w", ROOT))
        result = classify_graph(graph)
        by_id = {item.ir.expr_id: item for item in result.classified}
        item = by_id["242"]
        hints = build_explicit_surface_partition_hints(result.classified, result.context, resolution=8)

        geometry = tessellate(
            item,
            result.context,
            resolution=8,
            explicit_surface_axis_samples=hints[classified_expression_key(item)],
        )
        shared_line_x_values = sorted(
            round(point[0], 8)
            for point in geometry.points
            if abs(point[1] + 90.0) < 1e-8 and abs(point[2] - 19.8) < 1e-8 and 2.0 <= point[0] <= 3.0
        )

        # The boundary-nudge sample (high - 2e-5) is included in the grid
        # alongside the exact boundary.  Filter it for the partition check.
        expected = [2.0, 2.14285714, 2.28571429, 2.42857143, 2.57142857, 2.71428571, 2.85714286, 3.0]
        filtered = [v for v in shared_line_x_values if not any(abs(v - e) < 1e-4 and v != e for e in expected)]
        self.assertEqual(filtered, expected)

    def test_zaqxhna15w_predicate_clipped_wall_reaches_exact_z_bounds(self) -> None:
        graph = graph_ir_from_state(load_fixture_state("https://www.desmos.com/3d/zaqxhna15w", ROOT))
        result = classify_graph(graph)
        item = {classified.ir.expr_id: classified for classified in result.classified}["29"]

        geometry = tessellate(item, result.context, resolution=8)
        report = validate_geometry(item, geometry, result.context)
        used_z_values = used_axis_values(geometry, axis="z")

        self.assertEqual(item.ir.latex, r"y=5\left\{2<x<3\right\}\left\{0<z<-0.01\left(y+26\right)\left(y-26\right)+7\right\}")
        self.assertTrue(report.valid, report)
        self.assertGreater(geometry.face_count, 0)
        self.assertAlmostEqual(min(used_z_values), 0.0, places=5)
        self.assertAlmostEqual(max(used_z_values), 13.51, places=5)

    def test_zaqxhna15w_predicate_clipped_truss_reaches_exact_y_bounds(self) -> None:
        graph = graph_ir_from_state(load_fixture_state("https://www.desmos.com/3d/zaqxhna15w", ROOT))
        result = classify_graph(graph)
        item = {classified.ir.expr_id: classified for classified in result.classified}["50"]

        geometry = tessellate(item, result.context, resolution=8)
        report = validate_geometry(item, geometry, result.context)
        used_y_values = used_axis_values(geometry, axis="y")

        self.assertEqual(item.ir.latex, r"z=-1.36y+6.7\left\{2<x<3\right\}\left\{0<z<-0.01\left(y+26\right)\left(y-26\right)+7\right\}")
        self.assertTrue(report.valid, report)
        self.assertGreater(geometry.face_count, 0)
        self.assertAlmostEqual(min(used_y_values), -5.006848580913449, places=5)
        self.assertAlmostEqual(max(used_y_values), 6.7 / 1.36, places=5)

    def test_zaqxhna15w_adjacent_surfaces_have_no_boundary_gap(self) -> None:
        """Adjacent explicit surfaces sharing a strict boundary must tile without
        visible gaps.  The parabolic arch (expr 18, -26<y<26) and the flat cap
        (expr 27, 26<y<32) meet at y=26.  The arch's mesh must extend close to
        y=26 so the gap is imperceptible."""
        graph = graph_ir_from_state(load_fixture_state("https://www.desmos.com/3d/zaqxhna15w", ROOT))
        result = classify_graph(graph)
        by_id = {item.ir.expr_id: item for item in result.classified}

        pairs = [
            # (surface ending at boundary, surface starting at boundary, shared y, description)
            ("18", "27", 26.0, "arch upper bound → flat cap lower bound"),
            ("25", "18", -26.0, "flat cap upper bound → arch lower bound"),
            ("1", "314", 32.0, "lower deck upper bound → right deck lower bound"),
            ("242", "25", -32.0, "left diagonal upper bound → center flat lower bound"),
        ]
        for left_id, right_id, boundary_y, desc in pairs:
            with self.subTest(desc=desc):
                left_item = by_id[left_id]
                right_item = by_id[right_id]
                left_geom = tessellate(left_item, result.context, resolution=18)
                right_geom = tessellate(right_item, result.context, resolution=18)
                left_used_y = used_axis_values(left_geom, axis="y")
                right_used_y = used_axis_values(right_geom, axis="y")
                gap = min(right_used_y) - max(left_used_y)
                self.assertLessEqual(
                    abs(gap), 0.01,
                    f"{desc}: gap of {gap:.4f} units at y={boundary_y}",
                )

    def test_zaqxhna15w_adjacent_surfaces_do_not_overlap_at_boundary(self) -> None:
        """Adjacent explicit surfaces sharing a strict boundary must NOT produce
        overlapping faces.  Overlap causes z-fighting and, when the two surfaces
        have slightly different z-values at the boundary (e.g. z=7 vs z=7.04 due
        to approximate coefficients), exposes a visible wedge-like seam."""
        graph = graph_ir_from_state(load_fixture_state("https://www.desmos.com/3d/zaqxhna15w", ROOT))
        result = classify_graph(graph)
        by_id = {item.ir.expr_id: item for item in result.classified}

        pairs = [
            ("18", "27", 26.0, "arch / flat cap at y=26"),
            ("25", "18", -26.0, "flat cap / arch at y=-26"),
            ("1", "314", 32.0, "lower deck at y=32"),
            ("242", "25", -32.0, "diagonal / center flat at y=-32"),
        ]
        for left_id, right_id, boundary_y, desc in pairs:
            with self.subTest(desc=desc):
                left_geom = tessellate(by_id[left_id], result.context, resolution=18)
                right_geom = tessellate(by_id[right_id], result.context, resolution=18)
                left_max_y = max(used_axis_values(left_geom, axis="y"))
                right_min_y = min(used_axis_values(right_geom, axis="y"))
                self.assertGreater(
                    right_min_y, left_max_y - 1e-8,
                    f"{desc}: overlap detected — left reaches {left_max_y}, "
                    f"right starts at {right_min_y}",
                )

    def test_ghnr7txz47_expr835_suppressed_when_solved_axis_outside_viewport(self) -> None:
        """Expr 835 (z=1.5x+120, x∈[62,67]) evaluates to z∈[213,220.5], entirely
        above the source viewport max z of 82.68.  The solved-axis viewport check
        must suppress its geometry to match Desmos's viewport clipping."""
        graph = graph_ir_from_state(load_fixture_state("https://www.desmos.com/3d/ghnr7txz47", ROOT))
        result = classify_graph(graph)
        item = {i.ir.expr_id: i for i in result.classified}["835"]

        geometry = tessellate(item, result.context, resolution=8)

        self.assertEqual(item.kind, "explicit_surface")
        self.assertEqual(item.axis, "z")
        self.assertEqual(geometry.face_count, 0)
        self.assertEqual(len(geometry.points), 0)

    def test_ghnr7txz47_expr800_mirror_not_suppressed(self) -> None:
        """Expr 800 (z=1.5x+120, x∈[-67,-62]) evaluates to z∈[19.5,27], within
        the source viewport.  It must NOT be suppressed."""
        graph = graph_ir_from_state(load_fixture_state("https://www.desmos.com/3d/ghnr7txz47", ROOT))
        result = classify_graph(graph)
        item = {i.ir.expr_id: i for i in result.classified}["800"]

        geometry = tessellate(item, result.context, resolution=8)

        self.assertEqual(item.kind, "explicit_surface")
        self.assertGreater(geometry.face_count, 0)
        z_values = [p[2] for p in geometry.points]
        self.assertGreaterEqual(min(z_values), 19.0)
        self.assertLessEqual(max(z_values), 28.0)


def count_coplanar_faces(geometry, axis: str, value: float) -> int:
    axis_index = {"x": 0, "y": 1, "z": 2}[axis]
    count = 0
    offset = 0
    for face_size in geometry.face_vertex_counts:
        face_indices = geometry.face_vertex_indices[offset : offset + face_size]
        offset += face_size
        if all(abs(geometry.points[index][axis_index] - value) < 1e-8 for index in face_indices):
            count += 1
    return count


def used_axis_values(geometry, axis: str) -> list[float]:
    axis_index = {"x": 0, "y": 1, "z": 2}[axis]
    return [
        geometry.points[index][axis_index]
        for index in sorted(set(geometry.face_vertex_indices))
    ]


if __name__ == "__main__":
    unittest.main()
