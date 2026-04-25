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

    def test_tolerant_fixture_classification_reports_failed_definition_once(self) -> None:
        graph = GraphIR(
            source=SOURCE,
            expressions=[
                expr("1", "k=[1,...,50]"),
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
