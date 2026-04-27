from __future__ import annotations

import unittest
import math

from _path import ROOT
from desmos2usd.desmos_state import REQUIRED_SAMPLE_URLS, load_fixture_state
from desmos2usd.eval.context import EvalContext
from desmos2usd.ir import graph_ir_from_state
from desmos2usd.parse.classify import classify_graph
from desmos2usd.parse.latex_subset import LatexExpression
from desmos2usd.parse.predicates import parse_predicate, split_restrictions


class ParserTests(unittest.TestCase):
    def test_latex_eval(self) -> None:
        expr = LatexExpression.parse("0.16x^2+1.05")
        self.assertAlmostEqual(expr.eval(variables={"x": 2}), 1.69)

    def test_restriction_split(self) -> None:
        main, restrictions = split_restrictions("z=x^2 {-2<=x<=2}{-1<=y<=1}")
        self.assertEqual(main, "z=x^2")
        self.assertEqual(restrictions, ["-2<=x<=2", "-1<=y<=1"])

    def test_restriction_split_desmos_left_right_wrappers(self) -> None:
        main, restrictions = split_restrictions(r"z=0\left\{-3<x<3\right\}\left\{-32<y<32\right\}")
        self.assertEqual(main, "z=0")
        self.assertEqual(restrictions, ["-3<x<3", "-32<y<32"])

    def test_list_definition_parses(self) -> None:
        expr = LatexExpression.parse(r"a_{1}x^{2}+b_{1}x+c_{1}")
        self.assertEqual(expr.python, "a_1*x**(2)+b_1*x+c_1")

    def test_parameter_adjacency_is_implicit_multiplication(self) -> None:
        expr = LatexExpression.parse(r"0.05\left(4t\left(1-t\right)-1\right)")
        self.assertEqual(expr.python, "0.05*(4*t*(1-t)-1)")
        self.assertAlmostEqual(expr.eval(variables={"t": 0.5}), 0.0)

    def test_subscripted_scalar_adjacent_to_parameter_multiplies(self) -> None:
        expr = LatexExpression.parse(r"t_{p}v")
        self.assertEqual(expr.python, "t_p*v")
        self.assertAlmostEqual(expr.eval(EvalContext(scalars={"t_p": 2.0}), {"v": 3.0}), 6.0)

    def test_variable_adjacent_to_builtin_function_multiplies(self) -> None:
        expr = LatexExpression.parse(r"x-z\tan\left(5.5\right)")
        self.assertEqual(expr.python, "x-z*tan(5.5)")
        self.assertAlmostEqual(expr.eval(variables={"x": 2.0, "z": 3.0}), 2.0 - 3.0 * math.tan(5.5))

    def test_leading_dot_decimal_coefficients_multiply(self) -> None:
        expr = LatexExpression.parse(r".515x+.43\left(z+0.6\right)")
        self.assertEqual(expr.python, ".515*x+.43*(z+0.6)")
        self.assertAlmostEqual(expr.eval(variables={"x": 2.0, "z": 1.4}), 0.515 * 2.0 + 0.43 * 2.0)

    def test_degree_mode_trig_uses_degrees(self) -> None:
        expr = LatexExpression.parse(r"\tan\left(45\right)")

        self.assertAlmostEqual(expr.eval(EvalContext(degree_mode=True)), 1.0)

    def test_predicate(self) -> None:
        predicate = parse_predicate("-2<=x<=2")
        self.assertTrue(predicate.evaluate(context=EvalContext(), variables={"x": 1}))
        self.assertFalse(predicate.evaluate(context=EvalContext(), variables={"x": 3}))

    def test_required_fixtures_classify(self) -> None:
        expected_counts = {
            "zaqxhna15w": 268,
            "ghnr7txz47": 617,
            "yuqwjsfvsc": 341,
            "vyp9ogyimt": 558,
            "k0fbxxwkqf": 174,
        }
        for url in REQUIRED_SAMPLE_URLS:
            state = load_fixture_state(url, ROOT)
            graph = graph_ir_from_state(state)
            result = classify_graph(graph)
            graph_hash = url.rstrip("/").split("/")[-1]
            self.assertEqual(len(result.classified), expected_counts[graph_hash], url)

    def test_required_fixture_view_metadata_is_parsed(self) -> None:
        graph = graph_ir_from_state(load_fixture_state("https://www.desmos.com/3d/zaqxhna15w", ROOT))

        self.assertEqual(graph.source.viewport_bounds["x"], (-152.132127677567, 152.132127677567))
        self.assertEqual(graph.source.view_metadata["viewport_bounds"], graph.source.viewport_bounds)
        self.assertEqual(len(graph.source.view_metadata["world_rotation_3d"]), 9)
        self.assertAlmostEqual(graph.source.view_metadata["world_rotation_3d"][0], 0.8257596640689742)
        self.assertEqual(len(graph.source.view_metadata["axis_3d"]), 3)
        self.assertEqual(graph.source.view_metadata["show_plane_3d"], False)
        self.assertEqual(graph.source.view_metadata["three_d_mode"], True)


if __name__ == "__main__":
    unittest.main()
