from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from desmos2usd.usd.package import UsdzCommandResult, package_usdz


class PackageUsdzTests(unittest.TestCase):
    def test_package_usdz_resolves_relative_output_path_before_invoking_usdzip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            usda_dir = root / "exports"
            usda_dir.mkdir()
            usda_path = usda_dir / "scene.usda"
            usda_path.write_text("#usda 1.0\n")
            relative_usdz = Path("artifacts") / "scene.usdz"

            expected = UsdzCommandResult(
                tool="usdzip",
                command=["/usr/bin/usdzip", str((root / relative_usdz).resolve()), usda_path.name],
                cwd=str(usda_dir.resolve()),
                returncode=0,
                stdout="",
                stderr="",
            )

            with patch("desmos2usd.usd.package.require_tool", return_value="/usr/bin/usdzip"), patch(
                "desmos2usd.usd.package.run_command", return_value=expected
            ) as run_command:
                result = package_usdz(usda_path, root / relative_usdz)

            self.assertEqual(result, expected)
            run_command.assert_called_once_with(expected.command, cwd=usda_dir.resolve())


if __name__ == "__main__":
    unittest.main()
