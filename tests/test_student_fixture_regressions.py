from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _path  # noqa: F401
from desmos2usd.converter import export_graph
from desmos2usd.eval.context import EvalContext
from desmos2usd.ir import ExpressionIR, GraphIR, SourceInfo
from desmos2usd.parse.classify import classify_expression, classify_graph, register_definition
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

    def test_one_axis_equation_is_not_implicit_surface(self) -> None:
        with self.assertRaises(ValueError):
            classify_expression(expr("1", "x^{2}=1"), EvalContext())

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


if __name__ == "__main__":
    unittest.main()
