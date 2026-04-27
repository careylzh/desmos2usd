from __future__ import annotations

import tempfile
import unittest
from math import cos, sin
from pathlib import Path

import _path  # noqa: F401
from desmos2usd.converter import export_graph
from desmos2usd.eval.context import EvalContext
from desmos2usd.ir import ExpressionIR, GraphIR, SourceInfo
from desmos2usd.parse.classify import classify_expression, classify_graph, expand_list_expression, register_definition
from desmos2usd.parse.latex_subset import LatexExpression
from desmos2usd.tessellate import tessellate
from desmos2usd.validate.fixture_usdz_suite import classify_graph_tolerant


SOURCE = SourceInfo(url="", graph_hash="fixture", state_url="", title="fixture")


def expr(expr_id: str, latex: str, *, color: str = "#c74440", hidden: bool = False) -> ExpressionIR:
    return ExpressionIR(source=SOURCE, expr_id=expr_id, order=int(expr_id) if expr_id.isdigit() else 0, latex=latex, color=color, hidden=hidden)


class StudentFixtureRegressionTests(unittest.TestCase):
    def test_segment_operator_exports_as_linear_curve(self) -> None:
        item = classify_expression(
            expr("1", r"\operatorname{segment}\left(\left(0,-8.2,0\right),\left(0,-5,122.6\right)\right)"),
            EvalContext(),
        )

        geometry = tessellate(item, EvalContext(), resolution=4)

        self.assertEqual(item.kind, "parametric_curve")
        self.assertEqual(geometry.kind, "BasisCurves")
        self.assertEqual(geometry.points[0], (0.0, -8.2, 0.0))
        self.assertEqual(geometry.points[-1], (0.0, -5.0, 122.6))

    def test_uv_tuple_exports_as_parametric_surface(self) -> None:
        item = classify_expression(expr("1", r"\left(17u-8.5,-2.5,0.4v\right)"), EvalContext())

        geometry = tessellate(item, EvalContext(), resolution=4)

        self.assertEqual(item.kind, "parametric_surface")
        self.assertEqual(geometry.kind, "Mesh")
        self.assertEqual(geometry.point_count, 16)
        self.assertEqual(geometry.face_count, 9)
        self.assertEqual(geometry.points[0], (-8.5, -2.5, 0.0))
        self.assertEqual(geometry.points[-1], (8.5, -2.5, 0.4))

    def test_single_u_tuple_exports_as_parametric_curve(self) -> None:
        item = classify_expression(expr("1", r"\left(u,0,u^{2}\right)\left\{0\le u\le2\right\}"), EvalContext())

        geometry = tessellate(item, EvalContext(), resolution=4)

        self.assertEqual(item.kind, "parametric_curve")
        self.assertEqual(item.parameter, "u")
        self.assertEqual(geometry.kind, "BasisCurves")
        self.assertEqual(geometry.points[0], (0.0, 0.0, 0.0))
        self.assertEqual(geometry.points[-1], (2.0, 0.0, 4.0))

    def test_desmos_parametric_domain_sets_curve_bounds(self) -> None:
        item = classify_expression(
            ExpressionIR(
                SOURCE,
                "1",
                0,
                r"\left(0,0,t\right)",
                raw={"parametricDomain": {"min": "0", "max": "138"}},
            ),
            EvalContext(),
        )

        geometry = tessellate(item, EvalContext(), resolution=8)

        self.assertEqual(item.kind, "parametric_curve")
        self.assertEqual(item.t_bounds, (0.0, 138.0))
        self.assertEqual(geometry.points[0], (0.0, 0.0, 0.0))
        self.assertEqual(geometry.points[-1], (0.0, 0.0, 138.0))

    def test_strict_bounded_inequality_slab_keeps_visual_caps(self) -> None:
        source = SourceInfo("", "", "", "", viewport_bounds={"x": (-10.0, 45.0), "y": (-10.0, 20.0), "z": (0.0, 2.0)})
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r"0<z<2\left\{-10<x<45\right\}\left\{-10<y<20\right\}",
            ),
            EvalContext(),
        )

        geometry = tessellate(item, EvalContext(), resolution=8)

        self.assertEqual(item.kind, "inequality_region")
        self.assertTrue(has_coplanar_face(geometry, axis=2, value=0.0))
        self.assertTrue(has_coplanar_face(geometry, axis=2, value=2.0))

    def test_double_parenthesized_vector_definitions_feed_triangles(self) -> None:
        context = EvalContext()
        self.assertTrue(register_definition(expr("1", r"a_{27}=\left(\left(6,117,15\right)\right)", hidden=True), context))
        self.assertEqual(context.vectors["a_27"], (6.0, 117.0, 15.0))

        item = classify_expression(
            expr("2", r"\operatorname{triangle}\left(\left(a_{27}\right),\left(7,117,15\right),\left(6,118,15\right)\right)"),
            context,
        )

        geometry = tessellate(item, context)
        self.assertEqual(geometry.kind, "Mesh")
        self.assertEqual(geometry.points[0], (6.0, 117.0, 15.0))

    def test_point_list_index_components_feed_triangle_meshes(self) -> None:
        graph = GraphIR(
            source=SOURCE,
            expressions=[
                expr("1", r"A=\left[(0,0,0),(1,0,0),(0,1,0)\right]"),
                expr("2", r"B=\left[(1,2,3),(1,3,2)\right]"),
                expr("3", r"\operatorname{triangle}(A[B.x],A[B.y],A[B.z])"),
            ],
            raw_state={},
        )

        classification, unsupported = classify_graph_tolerant(graph)

        self.assertEqual(unsupported, [])
        self.assertEqual([item.ir.expr_id for item in classification.classified], ["3_0", "3_1"])
        first = tessellate(classification.classified[0], classification.context)
        self.assertEqual(first.kind, "Mesh")
        self.assertEqual(first.points, [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)])

    def test_unbracketed_point_list_definition_supports_indexing(self) -> None:
        graph = GraphIR(
            source=SOURCE,
            expressions=[
                expr("1", r"G_{1}=(0,0,0),(1,0,0),(0,1,0)"),
                expr("2", r"H_{1}=\left[(1,2,3)\right]"),
                expr("3", r"\operatorname{triangle}(G_{1}[H_{1}.x],G_{1}[H_{1}.y],G_{1}[H_{1}.z])"),
            ],
            raw_state={},
        )

        classification, unsupported = classify_graph_tolerant(graph)

        self.assertEqual(unsupported, [])
        self.assertEqual(len(classification.classified), 1)
        geometry = tessellate(classification.classified[0], classification.context)
        self.assertEqual(geometry.points[-1], (0.0, 1.0, 0.0))

    def test_simple_implicit_cylinder_extrudes_to_mesh(self) -> None:
        source = SourceInfo("", "", "", "", viewport_bounds={"x": (-30.0, 0.0), "y": (-10.0, 20.0), "z": (0.0, 60.0)})
        item = classify_expression(
            ExpressionIR(source, "1", 0, r"\left(x+15\right)^{2}+\left(y-5\right)^{2}=100\left\{0<z<60\right\}"),
            EvalContext(),
        )

        geometry = tessellate(item, EvalContext(), resolution=16)

        self.assertEqual(item.kind, "implicit_surface")
        self.assertEqual(geometry.kind, "Mesh")
        self.assertGreater(geometry.face_count, 0)

    def test_unbounded_implicit_sphere_exports_closed_mesh(self) -> None:
        source = SourceInfo("", "", "", "", viewport_bounds={"x": (-12.0, 12.0), "y": (-12.0, 12.0), "z": (-12.0, 12.0)})
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r"\left(x-0.66\right)^{2}+\left(y-1.24\right)^{2}+\left(z-1.665\right)^{2}=0.003",
            ),
            EvalContext(),
        )

        geometry = tessellate(item, EvalContext(), resolution=12)
        radius = 0.003**0.5
        xs = [point[0] for point in geometry.points]
        ys = [point[1] for point in geometry.points]
        zs = [point[2] for point in geometry.points]

        self.assertEqual(item.kind, "implicit_surface")
        self.assertEqual(geometry.kind, "Mesh")
        self.assertGreater(geometry.face_count, 100)
        self.assertAlmostEqual(min(xs), 0.66 - radius, places=6)
        self.assertAlmostEqual(max(xs), 0.66 + radius, places=6)
        self.assertAlmostEqual(min(ys), 1.24 - radius, places=6)
        self.assertAlmostEqual(max(ys), 1.24 + radius, places=6)
        self.assertAlmostEqual(min(zs), 1.665 - radius, places=6)
        self.assertAlmostEqual(max(zs), 1.665 + radius, places=6)

    def test_axis_restricted_implicit_sphere_exports_surface_cap(self) -> None:
        source = SourceInfo("", "", "", "", viewport_bounds={"x": (-25.0, 25.0), "y": (-25.0, 25.0), "z": (0.0, 25.0)})
        context = EvalContext(scalars={"s_top": 0.6})
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r"\left(x-20\right)^{2}+\left(y-20\right)^{2}+\left(z-21.1\right)^{2}=s_{top}^{2}"
                r"\left\{z\ge21.1\right\}",
            ),
            context,
        )

        geometry = tessellate(item, context, resolution=12)
        zs = [point[2] for point in geometry.points]

        self.assertEqual(item.kind, "implicit_surface")
        self.assertEqual(geometry.kind, "Mesh")
        self.assertGreater(geometry.face_count, 40)
        self.assertAlmostEqual(min(zs), 21.1, places=6)
        self.assertAlmostEqual(max(zs), 21.7, places=6)
        for point in geometry.points:
            variables = {"x": point[0], "y": point[1], "z": point[2]}
            self.assertTrue(all(predicate.evaluate(context, variables, tol=1e-4) for predicate in item.predicates))

    def test_axis_aligned_ball_cap_inequality_exports_capped_mesh(self) -> None:
        source = SourceInfo("", "", "", "", viewport_bounds={"x": (-12.0, 12.0), "y": (-8.0, 8.0), "z": (0.0, 8.0)})
        context = EvalContext()
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r"\left(x-7\right)^{2}+\left(y-4\right)^{2}+\left(z-5\right)^{2}<0.5^{2}\left\{z<5\right\}",
            ),
            context,
        )

        geometry = tessellate(item, context, resolution=8)
        zs = [point[2] for point in geometry.points]

        self.assertEqual(item.kind, "inequality_region")
        self.assertEqual(geometry.kind, "Mesh")
        self.assertGreater(geometry.face_count, 100)
        self.assertAlmostEqual(min(zs), 4.5, places=6)
        self.assertLessEqual(max(zs), 5.00001)
        self.assertTrue(has_coplanar_face(geometry, axis=2, value=5.0))
        for point in geometry.points:
            variables = {"x": point[0], "y": point[1], "z": point[2]}
            self.assertTrue(all(predicate.evaluate(context, variables, tol=1e-4) for predicate in item.predicates))

    def test_variable_adjacent_trig_inequality_region_tessellates(self) -> None:
        source = SourceInfo("", "", "", "", viewport_bounds={"x": (-10.0, 10.0), "y": (-10.0, 10.0), "z": (0.0, 2.0)})
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r"\left(x-z\tan\left(5.5\right)\right)^{2}+y^{2}<10\left\{0<z<2\right\}",
            ),
            EvalContext(),
        )

        geometry = tessellate(item, EvalContext(), resolution=12)

        self.assertEqual(item.kind, "inequality_region")
        self.assertEqual(geometry.kind, "Mesh")
        self.assertGreater(geometry.face_count, 0)

    def test_modulo_z_repeated_cylinder_inequality_tessellates(self) -> None:
        source = SourceInfo("", "", "", "", viewport_bounds={"x": (-10.0, 10.0), "y": (-6.0, 6.0), "z": (0.0, 1.0)})
        context = EvalContext()
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r"\left(x-2\right)^{2}+\left(y+1\right)^{2}<0.4^{2}"
                r"\left\{0<z<1\right\}\left\{\operatorname{mod}\left(z,0.4\right)<0.1\right\}",
            ),
            context,
        )

        geometry = tessellate(item, context, resolution=8)
        z_values = [point[2] for point in geometry.points]

        self.assertEqual(item.kind, "inequality_region")
        self.assertEqual(geometry.kind, "Mesh")
        self.assertGreater(geometry.face_count, 0)
        self.assertLessEqual(max(z_values), 0.900001)
        self.assertGreater(sum(1 for value in z_values if 0.3999 <= value <= 0.5001), 0)
        for point in geometry.points:
            variables = {"x": point[0], "y": point[1], "z": point[2]}
            self.assertTrue(all(predicate.evaluate(context, variables, tol=1e-4) for predicate in item.predicates))

    def test_main_modulo_inequality_tessellates_repeated_boxes(self) -> None:
        source = SourceInfo("", "", "", "", viewport_bounds={"x": (-2.0, 2.0), "y": (-2.0, 2.0), "z": (0.0, 0.7)})
        context = EvalContext()
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r"\operatorname{mod}\left(z,0.2\right)<0.05"
                r"\left\{0<z<0.7\right\}\left\{-1<x<1\right\}\left\{-1<y<1\right\}",
            ),
            context,
        )

        geometry = tessellate(item, context, resolution=8)
        z_values = [point[2] for point in geometry.points]

        self.assertEqual(item.kind, "inequality_region")
        self.assertEqual(geometry.kind, "Mesh")
        self.assertGreater(geometry.face_count, 0)
        self.assertGreater(sum(1 for value in z_values if 0.1999 <= value <= 0.2501), 0)
        for point in geometry.points:
            variables = {"x": point[0], "y": point[1], "z": point[2]}
            self.assertTrue(all(predicate.evaluate(context, variables, tol=1e-4) for predicate in item.predicates))

    def test_degree_mode_slanted_cylinder_inequality_tessellates(self) -> None:
        source = SourceInfo(
            "",
            "",
            "",
            "",
            viewport_bounds={"x": (-40.0, 40.0), "y": (-40.0, 40.0), "z": (0.0, 120.0)},
            view_metadata={"degree_mode": True},
        )
        context = EvalContext(degree_mode=True)
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r"\left(x-z\tan\left(5.5\right)-6\right)^{2}+y^{2}<10\left\{107<z<113\right\}",
            ),
            context,
        )

        geometry = tessellate(item, context, resolution=8)
        xs = [point[0] for point in geometry.points]

        self.assertEqual(item.kind, "inequality_region")
        self.assertEqual(geometry.kind, "Mesh")
        self.assertGreater(geometry.face_count, 0)
        self.assertGreater(min(xs), -5.0)
        self.assertLess(max(xs), 25.0)

    def test_degree_mode_slanted_cylinder_equality_tessellates(self) -> None:
        source = SourceInfo(
            "",
            "",
            "",
            "",
            viewport_bounds={"x": (-40.0, 40.0), "y": (-40.0, 40.0), "z": (0.0, 120.0)},
            view_metadata={"degree_mode": True},
        )
        context = EvalContext(degree_mode=True)
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r"\left(x-z\tan\left(5.5\right)\right)^{2}+y^{2}=260\left\{20<z<80\right\}",
            ),
            context,
        )

        geometry = tessellate(item, context, resolution=8)

        self.assertEqual(item.kind, "implicit_surface")
        self.assertEqual(geometry.kind, "Mesh")
        self.assertGreater(geometry.face_count, 0)

    def test_leading_dot_decimal_implicit_plane_tessellates(self) -> None:
        source = SourceInfo("", "", "", "", viewport_bounds={"x": (-3.0, 3.0), "y": (-3.0, 3.0), "z": (0.0, 3.0)})
        context = EvalContext()
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r"2z=.515x+1.91\left\{-1.55\le y\le2.6\right\}\left\{-2\le x\le-.6\right\}",
            ),
            context,
        )

        geometry = tessellate(item, context, resolution=8)

        self.assertEqual(item.kind, "implicit_surface")
        self.assertEqual(geometry.kind, "Mesh")
        self.assertGreater(geometry.face_count, 0)

    def test_leading_dot_decimal_slab_tessellates(self) -> None:
        source = SourceInfo("", "", "", "", viewport_bounds={"x": (-12.0, 2.0), "y": (2.0, 3.0), "z": (0.0, 3.0)})
        context = EvalContext()
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r".5\le z\le1+.43(x+0.6)\left\{-10\le x\le-0.6\right\}\left\{2.55\le y\le2.6\right\}",
            ),
            context,
        )

        geometry = tessellate(item, context, resolution=8)

        self.assertEqual(item.kind, "inequality_region")
        self.assertEqual(geometry.kind, "Mesh")
        self.assertGreater(geometry.face_count, 0)

    def test_tolerant_fixture_classification_uses_graph_degree_mode(self) -> None:
        source = SourceInfo(
            "",
            "",
            "",
            "",
            viewport_bounds={"x": (-10.0, 10.0), "y": (-10.0, 10.0), "z": (0.0, 10.0)},
            view_metadata={"degree_mode": True},
        )
        graph = GraphIR(
            source=source,
            expressions=[
                ExpressionIR(
                    source,
                    "1",
                    0,
                    r"\left(x-z\tan\left(45\right)\right)^{2}+y^{2}<4\left\{0<z<2\right\}",
                )
            ],
            raw_state={},
        )

        classification, unsupported = classify_graph_tolerant(graph)

        self.assertEqual(len(unsupported), 0)
        self.assertTrue(classification.context.degree_mode)

    def test_tolerant_fixture_classification_keeps_supported_prims_after_unsupported_expr(self) -> None:
        graph = GraphIR(
            source=SOURCE,
            expressions=[
                expr("1", r"\operatorname{sphere}\left(\left(0,0,0\right),1\right)"),
                expr("2", "z=0\\left\\{-1<x<1\\right\\}\\left\\{-1<y<1\\right\\}"),
            ],
            raw_state={},
        )

        classification, unsupported = classify_graph_tolerant(graph)

        self.assertEqual(len(classification.classified), 1)
        self.assertEqual(len(unsupported), 1)
        self.assertEqual(unsupported[0].expr_id, "1")

    def test_desmos_ellipsis_list_definition_expands_fixture_repetition(self) -> None:
        graph = GraphIR(
            source=SOURCE,
            expressions=[
                expr("1", "N=4"),
                expr("2", "z_{0}=20"),
                expr("3", "h=2"),
                expr("4", "a(k)=k"),
                expr("5", "b(k)=k+1"),
                expr("6", "n=[0...N-1]"),
                expr("7", "((1-t)a(n)+tb(n),0,z_{0}+nh+th)"),
            ],
            raw_state={},
        )

        classification, unsupported = classify_graph_tolerant(graph)

        self.assertEqual(len(unsupported), 0)
        self.assertEqual([item.ir.expr_id for item in classification.classified], ["7_0", "7_1", "7_2", "7_3"])
        self.assertEqual(classification.classified[2].ir.latex, "((1-t)a(2.0)+tb(2.0),0,z_{0}+2.0h+th)")

    def test_desmos_simple_ellipsis_list_definition_expands_fixture_repetition(self) -> None:
        graph = GraphIR(
            source=SOURCE,
            expressions=[
                expr("1", "N=4"),
                expr("2", "n=[0...N-1]"),
                expr("3", "(n,0,t)"),
            ],
            raw_state={},
        )

        classification, unsupported = classify_graph_tolerant(graph)

        self.assertEqual(len(unsupported), 0)
        self.assertEqual([item.ir.expr_id for item in classification.classified], ["3_0", "3_1", "3_2", "3_3"])

    def test_desmos_stepped_ellipsis_list_definition_parses(self) -> None:
        graph = GraphIR(
            source=SOURCE,
            expressions=[
                expr("1", "k=[0.3,0.6...1.2]"),
                expr("2", "x=k\\left\\{0<y<1\\right\\}\\left\\{0<z<1\\right\\}"),
            ],
            raw_state={},
        )

        classification, unsupported = classify_graph_tolerant(graph)

        self.assertEqual(len(unsupported), 0)
        self.assertEqual([item.ir.expr_id for item in classification.classified], ["2_0", "2_1", "2_2", "2_3"])

    def test_scalar_formula_over_list_definition_expands(self) -> None:
        graph = GraphIR(
            source=SOURCE,
            expressions=[
                expr("1", "k=[0...3]"),
                expr("2", "j=2\\pi k/4"),
                expr("3", "(\\cos(j),\\sin(j),t)"),
            ],
            raw_state={},
        )

        classification, unsupported = classify_graph_tolerant(graph)

        self.assertEqual(len(unsupported), 0)
        self.assertEqual([item.ir.expr_id for item in classification.classified], ["3_0", "3_1", "3_2", "3_3"])

    def test_inline_random_list_expansion_is_seeded_and_bounded(self) -> None:
        context = EvalContext(random_seed="fixture-seed", random_list_limit=3)
        source = expr("1", r"x=\operatorname{random}\left(10\right)\left\{0<y<1\right\}")

        expanded = expand_list_expression(source, context)
        expanded_again = expand_list_expression(source, context)

        self.assertEqual([item.expr_id for item in expanded], ["1_0", "1_1", "1_2"])
        self.assertEqual([item.latex for item in expanded], [item.latex for item in expanded_again])
        self.assertNotIn("random", "".join(item.latex for item in expanded))
        self.assertTrue(all(item.raw["expandedFromRandomExpression"] == "1" for item in expanded))

    def test_random_gaussian_flat_regions_sample_in_local_bounds(self) -> None:
        source = SourceInfo(
            "",
            "",
            "",
            "",
            viewport_bounds={"x": (-500.0, 500.0), "y": (-500.0, 500.0), "z": (-500.0, 500.0)},
        )
        graph = GraphIR(
            source=source,
            expressions=[
                ExpressionIR(
                    source,
                    "1",
                    0,
                    r"e^{-\frac{(x-\operatorname{random}\left(3\right))^{2}"
                    r"+(y-\operatorname{random}\left(3\right))^{2}}{1.1}}>0.0000001",
                )
            ],
            raw_state={"randomSeed": "fixture-seed"},
        )

        classification, unsupported = classify_graph_tolerant(graph)

        self.assertEqual(unsupported, [])
        self.assertEqual([item.ir.expr_id for item in classification.classified], ["1_0", "1_1", "1_2"])
        for item in classification.classified:
            geometry = tessellate(item, classification.context, resolution=8)
            self.assertEqual(geometry.kind, "Mesh")
            self.assertGreater(geometry.face_count, 0)
            self.assertEqual({point[2] for point in geometry.points}, {0.0})

    def test_gaussian_flat_region_outside_function_restriction_exports_empty_mesh(self) -> None:
        source = SourceInfo(
            "",
            "",
            "",
            "",
            viewport_bounds={"x": (-600.0, 600.0), "y": (-600.0, 600.0), "z": (-600.0, 600.0)},
        )
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r"e^{-\frac{(x-500)^{2}+y^{2}}{1.1}}>0.0000001"
                r"\left\{-\sqrt{100000\left(1-\frac{x^{2}}{200000}\right)}<y"
                r"<\sqrt{100000\left(1-\frac{x^{2}}{200000}\right)}\right\}",
            ),
            EvalContext(),
        )

        geometry = tessellate(item, EvalContext(), resolution=8)

        self.assertEqual(item.kind, "inequality_region")
        self.assertEqual(geometry.kind, "Mesh")
        self.assertEqual(geometry.point_count, 0)
        self.assertEqual(geometry.face_count, 0)

    def test_desmos_mod_is_available_in_list_definitions(self) -> None:
        graph = GraphIR(
            source=SOURCE,
            expressions=[
                expr("1", "k=[0...3]"),
                expr("2", "j=2\\pi\\operatorname{mod}(k+1,4)/4"),
                expr("3", "(j,0,t)"),
            ],
            raw_state={},
        )

        classification, unsupported = classify_graph_tolerant(graph)

        self.assertEqual(len(unsupported), 0)
        self.assertEqual(
            [item.ir.latex for item in classification.classified],
            [
                "(1.5707963267948966,0,t)",
                "(3.141592653589793,0,t)",
                "(4.71238898038469,0,t)",
                "(0.0,0,t)",
            ],
        )

    def test_forward_point_fields_and_list_arithmetic_expand(self) -> None:
        graph = GraphIR(
            source=SOURCE,
            expressions=[
                expr("1", r"f_{1}=(h+a,k)", hidden=True),
                expr("2", r"s_{sidelength}=2a(\sqrt{2}-1)"),
                expr(
                    "3",
                    r"f_{1}.x\le x\le f_{1}.x+0.2"
                    r"\left\{f_{1}.y\le y\le f_{1}.y+0.2\right\}"
                    r"\left\{0\le z\le1\right\}",
                ),
                expr("4", "h=[20,-20]", hidden=True),
                expr("5", "k=[10,30]", hidden=True),
                expr("6", "a=2", hidden=True),
                expr("7", r"p_{pattern}=s_{sidelength}\cdot[0...2]"),
                expr("8", r"0\le x\le p_{pattern}\left\{0\le y\le1\right\}\left\{0\le z\le1\right\}"),
            ],
            raw_state={},
        )

        classification, unsupported = classify_graph_tolerant(graph)

        self.assertEqual(len(unsupported), 0)
        self.assertEqual([item.ir.expr_id for item in classification.classified], ["3_0", "3_1", "8_0", "8_1", "8_2"])
        self.assertIn("22.0\\le x\\le 22.0+0.2", classification.classified[0].ir.latex)
        self.assertEqual(classification.context.lists["p_pattern"][2], 2 * classification.context.scalars["s_sidelength"])

    def test_point_list_property_references_expand(self) -> None:
        graph = GraphIR(
            source=SOURCE,
            expressions=[
                expr("1", "w=7", hidden=True),
                expr("2", "p_{points}=[(11,w),(w,-11)]\\", hidden=True),
                expr(
                    "3",
                    r"(x-p_{points}.x)^{2}+(y-p_{points}.y)^{2}<1"
                    r"\left\{0\le z\le1\right\}",
                ),
            ],
            raw_state={},
        )

        classification, unsupported = classify_graph_tolerant(graph)

        self.assertEqual(len(unsupported), 0)
        self.assertEqual([item.ir.expr_id for item in classification.classified], ["3_0", "3_1"])
        self.assertIn("(x-11.0)^{2}+(y-7.0)^{2}", classification.classified[0].ir.latex)

    def test_identifier_containing_pi_is_not_rewritten_as_constant(self) -> None:
        context = EvalContext()
        self.assertTrue(register_definition(expr("1", r"r_{pil}=0.3", hidden=True), context))

        value = LatexExpression.parse(r"(r_{pil}-0.1)^{2}").eval(context, {})

        self.assertAlmostEqual(value, 0.04)

    def test_failed_geometric_equation_is_not_reported_as_definition(self) -> None:
        context = EvalContext()
        self.assertTrue(register_definition(expr("1", "c=1.5", hidden=True), context))

        registered = register_definition(expr("2", r"(x-s)^{2}+(y-q)^{2}+(z-17.8)^{2}=c^{2}"), context)

        self.assertFalse(registered)
        self.assertEqual(set(context.scalars), {"c"})

    def test_tolerant_fixture_classification_reports_failed_definition_once(self) -> None:
        graph = GraphIR(
            source=SOURCE,
            expressions=[
                expr("1", "k=[1,x]"),
                expr("2", "z=0\\left\\{-1<x<1\\right\\}\\left\\{-1<y<1\\right\\}"),
            ],
            raw_state={},
        )

        classification, unsupported = classify_graph_tolerant(graph)

        self.assertEqual(len(classification.classified), 1)
        self.assertEqual(len(unsupported), 1)
        self.assertEqual(unsupported[0].expr_id, "1")
        self.assertEqual(unsupported[0].kind, "definition")

    def test_inline_literal_list_bounds_expand_with_matching_restriction_alternatives(self) -> None:
        graph = GraphIR(
            source=SOURCE,
            expressions=[
                expr(
                    "1",
                    r"\left[2.7,-4.3\right]\le x\le\left[4.3,-2.7\right]"
                    r"\left\{4.2>y>3\right\}\left\{0\le z\le1,2\le z\le3\right\}",
                )
            ],
            raw_state={},
        )

        classification, unsupported = classify_graph_tolerant(graph)

        self.assertEqual(len(unsupported), 0)
        self.assertEqual([item.ir.expr_id for item in classification.classified], ["1_0", "1_1"])
        self.assertEqual(classification.classified[0].ir.latex, r"2.7\le x\le4.3\left\{4.2>y>3\right\}\left\{0\le z\le1\right\}")
        self.assertEqual(classification.classified[1].ir.latex, r"-4.3\le x\le-2.7\left\{4.2>y>3\right\}\left\{2\le z\le3\right\}")

    def test_disjoint_same_axis_comma_restriction_without_list_context_expands_as_union(self) -> None:
        graph = GraphIR(
            source=SOURCE,
            expressions=[expr("1", r"y=5.2\left\{2.7<x<4.3\right\}\left\{0\le z\le1,2\le z\le3\right\}")],
            raw_state={},
        )

        classification, unsupported = classify_graph_tolerant(graph)

        self.assertEqual(len(unsupported), 0)
        self.assertEqual([item.ir.expr_id for item in classification.classified], ["1_alt0", "1_alt1"])
        self.assertEqual(classification.classified[0].ir.latex, r"y=5.2\left\{2.7<x<4.3\right\}\left\{0\le z\le1\right\}")
        self.assertEqual(classification.classified[1].ir.latex, r"y=5.2\left\{2.7<x<4.3\right\}\left\{2\le z\le3\right\}")

    def test_overlapping_same_axis_comma_restriction_without_list_context_remains_conjunctive(self) -> None:
        graph = GraphIR(
            source=SOURCE,
            expressions=[expr("1", r"y=5.2\left\{2.7<x<4.3\right\}\left\{0\le z\le2,1\le z\le3\right\}")],
            raw_state={},
        )

        classification, unsupported = classify_graph_tolerant(graph)

        self.assertEqual(len(unsupported), 0)
        self.assertEqual([item.ir.expr_id for item in classification.classified], ["1"])
        self.assertEqual(len(classification.classified[0].predicates), 3)

    def test_mixed_axis_comma_restriction_remains_conjunctive(self) -> None:
        graph = GraphIR(
            source=SOURCE,
            expressions=[expr("1", r"z=0\left\{0\le x\le1,0\le y\le1\right\}")],
            raw_state={},
        )

        classification, unsupported = classify_graph_tolerant(graph)

        self.assertEqual(len(unsupported), 0)
        self.assertEqual([item.ir.expr_id for item in classification.classified], ["1"])
        self.assertEqual(len(classification.classified[0].predicates), 2)

    def test_list_index_references_resolve_before_literal_list_expansion(self) -> None:
        graph = GraphIR(
            source=SOURCE,
            expressions=[
                expr("1", "j=[2,-2,2,-2]"),
                expr("2", "d=[-3.4,-3.4,10.6,10.6]"),
                expr(
                    "3",
                    r"y\ge\left[j\left[3\right],j\left[4\right]\right]x+\left[d\left[3\right],d\left[4\right]\right]"
                    r"\left\{\left[0,3.5\right]\ge x\ge\left[-3.5,0\right]\right\}"
                    r"\left\{0\le z\le1,2\le z\le3\right\}",
                ),
            ],
            raw_state={},
        )

        classification, unsupported = classify_graph_tolerant(graph)

        self.assertEqual(len(unsupported), 0)
        self.assertEqual([item.ir.expr_id for item in classification.classified], ["3_0", "3_1"])
        self.assertIn(r"y\ge2.0x+10.6", classification.classified[0].ir.latex)
        self.assertIn(r"\left\{0\le z\le1\right\}", classification.classified[0].ir.latex)
        self.assertIn(r"y\ge-2.0x+10.6", classification.classified[1].ir.latex)
        self.assertIn(r"\left\{2\le z\le3\right\}", classification.classified[1].ir.latex)

    def test_single_letter_list_expansion_does_not_rewrite_braced_subscripts(self) -> None:
        graph = GraphIR(
            source=SOURCE,
            expressions=[
                expr("1", "h=[20,30]"),
                expr("2", "d_{height}=2"),
                expr("3", r"z=d_{height}x\left\{0<y<1\right\}"),
            ],
            raw_state={},
        )

        classification, unsupported = classify_graph_tolerant(graph)

        self.assertEqual(len(unsupported), 0)
        self.assertEqual([item.ir.expr_id for item in classification.classified], ["3"])
        self.assertEqual(classification.classified[0].ir.latex, r"z=d_{height}x\left\{0<y<1\right\}")

    def test_one_axis_equation_is_not_implicit_surface(self) -> None:
        with self.assertRaises(ValueError):
            classify_expression(expr("1", "x^{2}=1"), EvalContext())

    def test_one_axis_equation_with_2d_restriction_exports_flat_contour(self) -> None:
        source = SourceInfo(
            "", "", "", "", viewport_bounds={"x": (-12.0, 12.0), "y": (-12.0, 12.0), "z": (-12.0, 12.0)}
        )
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r"\operatorname{abs}(x)+\operatorname{abs}(x)=1.7\left\{1.3^{2}\le\ x^{2}+y^{2}\le1.8^{2\ }\right\}",
            ),
            EvalContext(),
        )

        geometry = tessellate(item, EvalContext(), resolution=12)

        self.assertEqual(item.kind, "implicit_surface")
        self.assertEqual(geometry.kind, "BasisCurves")
        self.assertGreater(geometry.point_count, 0)
        self.assertTrue(all(abs(point[2]) < 1e-8 for point in geometry.points))

    def test_rotated_coordinate_tilted_cylinder_uses_quadratic_profile(self) -> None:
        """S2-08 Group E: `(x*cos(theta)+z*sin(theta))^2 + y^2 = r^2 {z range}` produces an
        elliptic z-slice. It should use the analytic quadratic-profile path, not the coarse
        marching-squares fallback that made tower rings look like strips.
        """
        source = SourceInfo(
            "", "", "", "", viewport_bounds={"x": (-12.0, 12.0), "y": (-12.0, 12.0), "z": (-12.0, 12.0)}
        )
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r"(x\cos(0.07)+z\sin(0.07))^{2}+y^{2}=1.3^{2}\left\{0\le z\le2\right\}",
            ),
            EvalContext(),
        )

        self.assertEqual(item.kind, "implicit_surface")
        self.assertEqual(item.expression.identifiers, frozenset({"x", "y", "z"}))
        geometry = tessellate(item, EvalContext(), resolution=12)
        self.assertEqual(geometry.kind, "Mesh")
        self.assertGreater(geometry.face_count, 1000)
        for point in geometry.points[:: max(1, len(geometry.points) // 24)]:
            x, y, z = point
            residual = (x * cos(0.07) + z * sin(0.07)) ** 2 + y**2 - 1.3**2
            self.assertLess(abs(residual), 1e-8)

    def test_tilted_cylinder_at_constant_z_exports_closed_ring_curve(self) -> None:
        source = SourceInfo(
            "", "", "", "", viewport_bounds={"x": (-12.0, 12.0), "y": (-12.0, 12.0), "z": (-12.0, 12.0)}
        )
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r"(x\cos(0.07)+z\sin(0.07))^{2}+y^{2}=1.3^{2}\left\{z=8\right\}",
            ),
            EvalContext(),
        )

        geometry = tessellate(item, EvalContext(), resolution=12)

        self.assertEqual(item.kind, "implicit_surface")
        self.assertEqual(geometry.kind, "BasisCurves")
        self.assertEqual(len(geometry.curve_vertex_counts), 1)
        self.assertGreater(geometry.point_count, 32)
        self.assertEqual(geometry.points[0], geometry.points[-1])
        self.assertTrue(all(abs(point[2] - 8.0) < 1e-8 for point in geometry.points))

    def test_small_offset_tilted_cylinder_uses_adaptive_bbox(self) -> None:
        """S2-08 Group E: tiny tilted-cylinder shell (radius 0.06 in viewport ±12) is
        invisible to a fixed-resolution marching grid. The 3-axis fallback must adaptively
        refine its bbox before contouring.
        """
        source = SourceInfo("", "", "", "", viewport_bounds={"x": (-12.0, 12.0), "y": (-12.0, 12.0), "z": (-12.0, 12.0)})
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r"(x\cos(0.07)+z\sin(0.07)-1.36\cos(1\pi/6))^{2}+(y-1.36\sin(1\pi/6))^{2}=0.06^{2}\left\{0\le z\le8\right\}",
            ),
            EvalContext(),
        )

        self.assertEqual(item.kind, "implicit_surface")
        geometry = tessellate(item, EvalContext(), resolution=12)
        self.assertGreater(geometry.face_count, 0)

    def test_equality_predicate_yields_degenerate_axis_bound(self) -> None:
        """`z = N` with N constant should be reported by `variable_bounds` as a degenerate
        bound (low == high). Without this, downstream tessellators treat such a
        single-slice predicate as "no z bound" and fall back to viewport bounds.
        """
        from desmos2usd.parse.predicates import parse_predicate
        predicate = parse_predicate("z=8")
        bounds = predicate.variable_bounds()
        self.assertIn("z", bounds)
        low, high = bounds["z"]
        self.assertIsNotNone(low)
        self.assertIsNotNone(high)
        self.assertAlmostEqual(low.eval(EvalContext(), {}), 8.0)
        self.assertAlmostEqual(high.eval(EvalContext(), {}), 8.0)

    def test_inequality_voxel_sampler_refines_bbox_for_small_region(self) -> None:
        """`tessellate_sampled_inequality_region` must coarse-scan to find the predicate
        region before voxelizing. Without bbox refinement, a small inequality region in a
        large viewport produces zero satisfied cells.
        """
        source = SourceInfo("", "", "", "", viewport_bounds={"x": (-100.0, 100.0), "y": (-100.0, 100.0), "z": (0.0, 100.0)})
        item = classify_expression(
            ExpressionIR(source, "1", 0, r"x^{2}+y^{2}<10\left\{1<z<5\right\}"),
            EvalContext(),
        )

        self.assertEqual(item.kind, "inequality_region")
        geometry = tessellate(item, EvalContext(), resolution=12)
        self.assertGreater(geometry.face_count, 0)

    def test_near_vertical_explicit_surface_reorients_sampling_axis(self) -> None:
        """Very steep affine explicit surfaces should be sampled along their wide axis."""
        source = SourceInfo("", "", "", "", viewport_bounds={"x": (-1.0, 1.0), "y": (-400.0, 400.0), "z": (0.0, 1.0)})
        context = EvalContext()
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r"y=1000000000000x\left\{60000<y^{2}<100000\right\}\left\{0<z<1\right\}",
            ),
            context,
        )

        geometry = tessellate(item, context, resolution=8)

        self.assertEqual(item.kind, "explicit_surface")
        self.assertGreater(geometry.face_count, 0)
        used = sorted(set(geometry.face_vertex_indices))
        self.assertLess(max(abs(geometry.points[index][0]) for index in used), 1e-8)
        self.assertTrue(any(geometry.points[index][1] > 0 for index in used))
        self.assertTrue(any(geometry.points[index][1] < 0 for index in used))
        for index in used:
            point = geometry.points[index]
            variables = {"x": point[0], "y": point[1], "z": point[2]}
            self.assertAlmostEqual(point[1], 1000000000000 * point[0], places=4)
            self.assertTrue(all(predicate.evaluate(context, variables, tol=1e-4) for predicate in item.predicates))

    def test_parabolic_inequality_band_skips_circular_fast_path(self) -> None:
        """S2-05 Group E: parabolic slab bands are not circular profiles. The circular
        fast path should decline them instead of dividing by a zero quadratic axis.
        """
        source = SourceInfo("", "", "", "", viewport_bounds={"x": (-10.0, 10.0), "y": (0.0, 22.0), "z": (29.0, 33.0)})
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r"z<-0.09x^{2}+32.126\left\{-8.707<x<8.707\right\}\left\{z>-0.1x^{2}+30.775\right\}\left\{0\le y\le22\right\}",
            ),
            EvalContext(),
        )

        self.assertEqual(item.kind, "inequality_region")
        geometry = tessellate(item, EvalContext(), resolution=12)
        self.assertGreater(geometry.face_count, 0)

    def test_usda_writes_display_color_for_usdz_viewers(self) -> None:
        graph = GraphIR(
            source=SOURCE,
            expressions=[expr("1", "z=0\\left\\{-1<x<1\\right\\}\\left\\{-1<y<1\\right\\}", color="#ff0000")],
            raw_state={},
        )
        classification = classify_graph(graph)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "colored.usda"
            export_graph(graph, classification, output, resolution=4)
            text = output.read_text(encoding="utf-8")

        self.assertIn("color3f[] primvars:displayColor", text)
        self.assertIn("(1, 0, 0)", text)
        self.assertIn('interpolation = "constant"', text)

    def test_s208_2d_implicit_no_z_renders_flat_at_z0(self) -> None:
        """S2-08 Group E: ``abs(x-y)+abs(x+y)=2.4 {1.3^2 <= x^2+y^2 <= 1.8^2}`` is a 2D
        contour with no z reference. Pre-fix the marching-squares fallback extruded it
        across the full viewport ``z=[-11.91, 11.91]``, producing a tall vertical sheet
        that dominated the viewer. It must collapse to a flat shape at z=0 instead.
        """
        source = SourceInfo(
            "", "", "", "", viewport_bounds={"x": (-12.0, 12.0), "y": (-12.0, 12.0), "z": (-12.0, 12.0)}
        )
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r"\operatorname{abs}\left(x-y\right)+\operatorname{abs}\left(x+y\right)=2.4\left\{1.3^{2}\le\ x^{2}+y^{2}\le1.8^{2\ }\right\}",
            ),
            EvalContext(),
        )

        geometry = tessellate(item, EvalContext(), resolution=12)
        self.assertEqual(item.kind, "implicit_surface")
        self.assertEqual(geometry.kind, "BasisCurves")
        self.assertGreater(geometry.point_count, 0)
        z_values = [point[2] for point in geometry.points]
        self.assertLess(max(z_values) - min(z_values), 1e-2)
        self.assertLess(abs(max(z_values)), 1e-3)

    def test_s208_constant_y_with_small_x_range_renders_flat_at_z0(self) -> None:
        """S2-08 Group E: ``y=0.4 {-1.8 <= x <= -1.21}`` is a localized 2D detail (x range
        << viewport z span). Pre-fix the explicit-surface tessellator extruded it across
        ``viewport_bounds["z"]`` and produced a viewport-tall wall. It must render as a
        thin strip at z=0.
        """
        source = SourceInfo(
            "", "", "", "", viewport_bounds={"x": (-12.0, 12.0), "y": (-12.0, 12.0), "z": (-12.0, 12.0)}
        )
        item = classify_expression(
            ExpressionIR(source, "1", 0, r"y=0.4\left\{-1.8\le x\le-1.21\right\}"),
            EvalContext(),
        )

        geometry = tessellate(item, EvalContext(), resolution=12)
        self.assertEqual(item.kind, "explicit_surface")
        self.assertGreater(geometry.face_count, 0)
        z_values = [point[2] for point in geometry.points]
        self.assertLess(max(z_values) - min(z_values), 1e-2)
        x_values = [point[0] for point in geometry.points]
        # Honor the constraint range (and the boundary nudge) instead of the viewport.
        self.assertGreaterEqual(min(x_values), -1.81)
        self.assertLessEqual(max(x_values), -1.20)

    def test_explicit_surface_restriction_undefined_samples_are_outside_domain(self) -> None:
        """S2-06 Group E: a family of wall strips uses sqrt-based y restrictions.
        Samples outside the sqrt domain are outside the Desmos restriction; they should
        not abort the whole surface export.
        """
        source = SourceInfo(
            "", "", "", "", viewport_bounds={"x": (-2.0, 2.0), "y": (-2.0, 2.0), "z": (0.0, 1.0)}
        )
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r"y=0\left\{-\sqrt{1-x^{2}}<y<\sqrt{1-x^{2}}\right\}\left\{0<z<1\right\}",
            ),
            EvalContext(),
        )

        geometry = tessellate(item, EvalContext(), resolution=12)
        used_indices = set(geometry.face_vertex_indices)
        used_x_values = [geometry.points[index][0] for index in used_indices]

        self.assertEqual(item.kind, "explicit_surface")
        self.assertGreater(geometry.face_count, 0)
        self.assertGreater(min(used_x_values), -1.05)
        self.assertLess(max(used_x_values), 1.05)

    def test_explicit_surface_sqrt_restriction_infers_narrow_chord_bounds(self) -> None:
        """S2-06 Group E has tangent ellipse wall strips whose valid x interval is too
        narrow to hit with a coarse viewport-wide grid. The domain inference should solve
        the sqrt-bounded chord interval instead of exporting an unsupported empty mesh.
        """
        source = SourceInfo(
            "", "", "", "", viewport_bounds={"x": (-100.0, 100.0), "y": (-100.0, 100.0), "z": (0.0, 1.0)}
        )
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r"y=0.99+0.02x\left\{-\sqrt{1-x^{2}}<y<\sqrt{1-x^{2}}\right\}\left\{0<z<1\right\}",
            ),
            EvalContext(),
        )

        geometry = tessellate(item, EvalContext(), resolution=12)
        used_indices = set(geometry.face_vertex_indices)
        used_x_values = [geometry.points[index][0] for index in used_indices]

        self.assertEqual(item.kind, "explicit_surface")
        self.assertGreater(geometry.face_count, 0)
        self.assertGreater(min(used_x_values), -0.25)
        self.assertLess(max(used_x_values), 0.2)

    def test_annular_quadratic_inequality_extrudes_as_ellipse_ring(self) -> None:
        """S2-06 Group E uses tall elliptical ring slabs such as
        ``98000 < x^2/2 + y^2 < 100000 {35 < z < 40}``. The analytic path should emit
        the annular extrusion directly instead of missing every valid voxel cell.
        """
        source = SourceInfo(
            "", "", "", "", viewport_bounds={"x": (-500.0, 500.0), "y": (-500.0, 500.0), "z": (0.0, 200.0)}
        )
        item = classify_expression(
            ExpressionIR(
                source,
                "1",
                0,
                r"98000<\frac{x^{2}}{2}+y^{2}<100000\left\{35<z<40\right\}",
            ),
            EvalContext(),
        )

        geometry = tessellate(item, EvalContext(), resolution=12)
        used_points = [geometry.points[index] for index in set(geometry.face_vertex_indices)]
        q_values = [point[0] ** 2 / 2.0 + point[1] ** 2 for point in used_points]
        z_values = [point[2] for point in used_points]

        self.assertEqual(item.kind, "inequality_region")
        self.assertGreater(geometry.face_count, 100)
        self.assertAlmostEqual(min(q_values), 98000.0, delta=1e-3)
        self.assertAlmostEqual(max(q_values), 100000.0, delta=1e-3)
        self.assertEqual(min(z_values), 35.0)
        self.assertEqual(max(z_values), 40.0)

    def test_chained_quadratic_disk_inequality_extrudes_as_cylinder(self) -> None:
        """S2-07 Group F has a small disk chained into the z band:
        ``(x-u)^2+(y-v)^2 <= r^2 <= z <= q+t/2 {5<z<5.9}``.
        The analytic path should emit the cylinder shell directly instead of relying on
        coarse voxel cells that can miss the tiny radius.
        """
        source = SourceInfo(
            "", "", "", "", viewport_bounds={"x": (-8.0, 8.0), "y": (-8.0, 8.0), "z": (-8.0, 8.0)}
        )
        context = EvalContext(scalars={"u": -0.3, "v": 0.5, "w": 0.21, "q": 5.9, "t": 0.5})
        item = classify_expression(
            ExpressionIR(
                source,
                "325",
                0,
                r"(x-u)^{2}+(y-v)^{2}\le w^{2}q-t/2\le z\le q+t/2\left\{5<z<5.9\right\}",
            ),
            context,
        )

        geometry = tessellate(item, context, resolution=12)
        used_points = [geometry.points[index] for index in set(geometry.face_vertex_indices)]
        radial_values = [(point[0] + 0.3) ** 2 + (point[1] - 0.5) ** 2 for point in used_points]
        z_values = [point[2] for point in used_points]

        self.assertEqual(item.kind, "inequality_region")
        self.assertEqual(geometry.kind, "Mesh")
        self.assertGreater(geometry.face_count, 100)
        self.assertAlmostEqual(max(radial_values), 0.21**2 * 5.9 - 0.5 / 2.0, delta=1e-6)
        self.assertEqual(min(z_values), 5.0)
        self.assertEqual(max(z_values), 5.9)

    def test_explicit_surface_expression_undefined_samples_are_outside_domain(self) -> None:
        """An explicit function's natural domain should clip the mesh just like Desmos.
        Pre-fix, z=sqrt(1-x^2-y^2) over a larger viewport raised on the first outside
        sample and exported as unsupported.
        """
        source = SourceInfo(
            "", "", "", "", viewport_bounds={"x": (-2.0, 2.0), "y": (-2.0, 2.0), "z": (0.0, 1.0)}
        )
        item = classify_expression(
            ExpressionIR(source, "1", 0, r"z=\sqrt{1-x^{2}-y^{2}}"),
            EvalContext(),
        )

        geometry = tessellate(item, EvalContext(), resolution=16)
        used_indices = set(geometry.face_vertex_indices)
        used_points = [geometry.points[index] for index in used_indices]

        self.assertEqual(item.kind, "explicit_surface")
        self.assertGreater(geometry.face_count, 0)
        self.assertTrue(all(point[0] ** 2 + point[1] ** 2 <= 1.05 for point in used_points))

    def test_s208_disk_inequality_at_constant_z_renders_as_flat_disk(self) -> None:
        """S2-08 Group E: ``x^2+y^2 <= 4 {z=0}`` is a flat disk in the xy plane at z=0.
        Pre-fix every fallback path either rejected it (no extrusion axis) or wrote an
        empty geometry, leaving the fixture with three "did not resolve to sampled
        cells" unsupported entries. The flat-region path must produce a circular disk.
        """
        source = SourceInfo(
            "", "", "", "", viewport_bounds={"x": (-12.0, 12.0), "y": (-12.0, 12.0), "z": (-12.0, 12.0)}
        )
        item = classify_expression(
            ExpressionIR(source, "1", 0, r"x^{2}+y^{2}\le4\left\{z=0\right\}"),
            EvalContext(),
        )

        geometry = tessellate(item, EvalContext(), resolution=12)
        self.assertEqual(item.kind, "inequality_region")
        self.assertGreater(geometry.face_count, 4)
        z_values = [point[2] for point in geometry.points]
        self.assertEqual(min(z_values), 0.0)
        self.assertEqual(max(z_values), 0.0)
        x_values = [point[0] for point in geometry.points]
        y_values = [point[1] for point in geometry.points]
        # The inferred sampling window should hug the disk bounds (radius 2), not viewport.
        self.assertLess(max(x_values), 3.0)
        self.assertGreater(min(x_values), -3.0)
        self.assertLess(max(y_values), 3.0)
        self.assertGreater(min(y_values), -3.0)

    def test_s208_disk_at_z_constant_uses_predicate_value_not_zero(self) -> None:
        """S2-08 Group E: ``x^2+y^2+x <= 1.5 {z=8}`` is a flat region at z=8 (the top of
        the leaning tower). The flat-region path must read the constant value from the
        ``z=8`` predicate, not default to z=0.
        """
        source = SourceInfo(
            "", "", "", "", viewport_bounds={"x": (-12.0, 12.0), "y": (-12.0, 12.0), "z": (-12.0, 12.0)}
        )
        item = classify_expression(
            ExpressionIR(source, "1", 0, r"x^{2}+y^{2}+x\le1.5\left\{z=8\right\}"),
            EvalContext(),
        )

        geometry = tessellate(item, EvalContext(), resolution=12)
        self.assertEqual(item.kind, "inequality_region")
        self.assertGreater(geometry.face_count, 0)
        z_values = [point[2] for point in geometry.points]
        self.assertEqual(min(z_values), 8.0)
        self.assertEqual(max(z_values), 8.0)

    def test_s203_empty_affine_inequality_band_exports_empty_mesh(self) -> None:
        """S2-03 Group D includes list-expanded half-plane bands that Desmos renders as
        empty sets. They should not be reported as unsupported sampled-cell failures.
        """
        source = SourceInfo(
            "", "", "", "", viewport_bounds={"x": (-10.0, 10.0), "y": (-5.0, 15.0), "z": (-12.0, 5.0)}
        )
        item = classify_expression(
            ExpressionIR(
                source,
                "34_2_0",
                0,
                r"y\ge 2.0x+10.6\left\{5.1<y<5.2\right\}\left\{5.0\ge x\ge3.5\right\}\left\{-3.25\le z\le0.5\right\}",
                raw={"expandedFromListExpression": "34"},
            ),
            EvalContext(),
        )

        geometry = tessellate(item, EvalContext(), resolution=12)
        self.assertEqual(item.kind, "inequality_region")
        self.assertEqual(geometry.kind, "Mesh")
        self.assertEqual(geometry.point_count, 0)
        self.assertEqual(geometry.face_count, 0)

    def test_s203_nonempty_affine_inequality_band_still_renders(self) -> None:
        source = SourceInfo(
            "", "", "", "", viewport_bounds={"x": (-10.0, 10.0), "y": (-5.0, 15.0), "z": (-12.0, 5.0)}
        )
        item = classify_expression(
            ExpressionIR(
                source,
                "34_3_0",
                0,
                r"y\ge -2.0x+10.6\left\{5.1<y<5.2\right\}\left\{5.0\ge x\ge3.5\right\}\left\{-3.25\le z\le0.5\right\}",
                raw={"expandedFromListExpression": "34"},
            ),
            EvalContext(),
        )

        geometry = tessellate(item, EvalContext(), resolution=12)
        self.assertEqual(item.kind, "inequality_region")
        self.assertGreater(geometry.face_count, 0)

    def test_rotated_affine_inequality_strip_extrudes_without_sampling_miss(self) -> None:
        """S2-03 Group E has thin diagonal bands bounded by affine x/y combinations.

        A grid sampler can miss the 0.4-unit orthogonal strip entirely; affine
        half-plane clipping should build the rectangular prism directly.
        """
        source = SourceInfo(
            "", "", "", "", viewport_bounds={"x": (-30.0, 30.0), "y": (-30.0, 30.0), "z": (0.0, 3.0)}
        )
        item = classify_expression(
            ExpressionIR(
                source,
                "84_1",
                0,
                r"-1\le\frac{x-y}{\sqrt{2}}\le1\left\{3\ge z\ge2.8\right\}"
                r"\left\{-0.2\le\frac{x+y}{-\sqrt{2}}\le0.2\right\}",
            ),
            EvalContext(),
        )

        geometry = tessellate(item, EvalContext(), resolution=12)
        self.assertEqual(item.kind, "inequality_region")
        self.assertEqual(geometry.kind, "Mesh")
        self.assertGreaterEqual(geometry.face_count, 6)
        z_values = [point[2] for point in geometry.points]
        self.assertEqual(min(z_values), 2.8)
        self.assertEqual(max(z_values), 3.0)

    def test_s203_rotated_arc_cutout_retries_sampled_cells(self) -> None:
        """S2-03 Group E includes rotated arc cutouts that a coarse 3D grid misses."""
        source = SourceInfo(
            "",
            "",
            "",
            "",
            viewport_bounds={"x": (-38.3, 38.3), "y": (-38.3, 38.3), "z": (-30.0, 46.7)},
        )
        context = EvalContext(
            scalars={
                "d_height": 11.5,
                "d_length": 5.656854249492381,
                "p_2": 9.0,
                "p_3": 0.0,
                "r_arc": 2.0,
            }
        )
        item = classify_expression(
            ExpressionIR(
                source,
                "254",
                0,
                r"\left(\frac{x-y}{\sqrt{2}}-p_{3}\right)^{2}+\left(z-p_{2}\right)^{2}\ge r_{arc}^{2}"
                r"\left\{-\frac{d_{length}}{2}\le\frac{x-y}{\sqrt{2}}\le\frac{d_{length}}{2}\right\}"
                r"\left\{d_{height}+2.5\ge z\ge p_{2}\right\}"
                r"\left\{\sqrt{162}-2<\frac{x+y}{\sqrt{2}}<\sqrt{162}\right\}",
            ),
            context,
        )

        geometry = tessellate(item, context, resolution=8)

        self.assertEqual(item.kind, "inequality_region")
        self.assertEqual(geometry.kind, "Mesh")
        self.assertGreater(geometry.face_count, 0)
        z_values = [point[2] for point in geometry.points]
        self.assertGreater(max(z_values), min(z_values))


def has_coplanar_face(geometry, axis: int, value: float) -> bool:
    cursor = 0
    for count in geometry.face_vertex_counts:
        face = geometry.face_vertex_indices[cursor : cursor + count]
        cursor += count
        if face and all(abs(geometry.points[index][axis] - value) < 1e-8 for index in face):
            return True
    return False


if __name__ == "__main__":
    unittest.main()
