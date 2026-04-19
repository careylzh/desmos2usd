from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import _path  # noqa: F401
from desmos2usd import cli


class CliTests(unittest.TestCase):
    def test_validate_usdz_requires_usdz_output(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            cli.main(["https://www.desmos.com/3d/ghnr7txz47", "-o", "out.usda", "--validate-usdz"])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("--validate-usdz requires --usdz", stderr.getvalue())

    def test_usdz_options_are_passed_to_converter(self) -> None:
        report = SimpleNamespace(output="out.usda", usdz_output="out.usdz")
        stdout = io.StringIO()
        with (
            patch.object(cli, "project_root_from_cwd", return_value=Path("/repo")),
            patch.object(cli, "convert_url", return_value=report) as convert_url,
            contextlib.redirect_stdout(stdout),
        ):
            exit_code = cli.main(
                [
                    "https://www.desmos.com/3d/ghnr7txz47",
                    "-o",
                    "out.usda",
                    "--usdz",
                    "out.usdz",
                    "--validate-usdz",
                ]
            )

        self.assertEqual(exit_code, 0)
        called_args, called_kwargs = convert_url.call_args
        self.assertEqual(called_args[0], "https://www.desmos.com/3d/ghnr7txz47")
        self.assertEqual(called_args[1], Path("out.usda"))
        self.assertEqual(called_kwargs["project_root"], Path("/repo"))
        self.assertEqual(called_kwargs["usdz_output"], Path("out.usdz"))
        self.assertEqual(called_kwargs["validate_usdz"], True)
        self.assertIn('"usdz_output": "out.usdz"', stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
