from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import _path  # noqa: F401
from desmos2usd.validate import fixture_usdz_suite


class FixtureUsdzSuiteTests(unittest.TestCase):
    def test_main_records_success_partial_and_error_without_aborting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_dir = root / "fixtures" / "states"
            fixtures_dir.mkdir(parents=True)
            fixtures = []
            for name in ["a.json", "b.json", "c.json"]:
                path = fixtures_dir / name
                path.write_text("{}\n", encoding="utf-8")
                fixtures.append(path)

            out_dir = root / "artifacts" / "fixture_usdz"
            fake_reports = [
                {"fixture": "a.json", "status": "success", "acceptance_success": True, "usdz_exists": True, "unsupported_count": 0},
                {"fixture": "b.json", "status": "partial", "acceptance_success": False, "usdz_exists": True, "unsupported_count": 3},
                {
                    "fixture": "c.json",
                    "status": "error",
                    "acceptance_success": False,
                    "usdz_exists": False,
                    "unsupported_count": 0,
                    "error_stage": "classify",
                },
            ]

            with patch("desmos2usd.validate.fixture_usdz_suite.project_root_from_cwd", return_value=root), patch(
                "desmos2usd.validate.fixture_usdz_suite.process_fixture", side_effect=fake_reports
            ) as process_fixture:
                with contextlib.redirect_stdout(io.StringIO()):
                    exit_code = fixture_usdz_suite.main(["--out", str(out_dir)])

            self.assertEqual(exit_code, 0)
            self.assertEqual(process_fixture.call_count, 3)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["fixture_count"], 3)
            self.assertEqual(summary["out_dir"], "artifacts/fixture_usdz")
            self.assertEqual(summary["success_count"], 1)
            self.assertEqual(summary["partial_count"], 1)
            self.assertEqual(summary["error_count"], 1)
            self.assertEqual(summary["fixtures_with_usdz_count"], 2)
            self.assertEqual(summary["unsupported_fixture_names"], ["b.json"])
            self.assertEqual(summary["error_stage_counts"], {"classify": 1})
            self.assertEqual(summary["acceptance_met"], False)

    def test_limit_truncates_fixture_processing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_dir = root / "fixtures" / "states"
            fixtures_dir.mkdir(parents=True)
            for name in ["a.json", "b.json", "c.json"]:
                (fixtures_dir / name).write_text("{}\n", encoding="utf-8")

            out_dir = root / "artifacts" / "fixture_usdz"
            with patch("desmos2usd.validate.fixture_usdz_suite.project_root_from_cwd", return_value=root), patch(
                "desmos2usd.validate.fixture_usdz_suite.process_fixture",
                return_value={"fixture": "a.json", "status": "error", "acceptance_success": False, "usdz_exists": False, "unsupported_count": 0},
            ) as process_fixture:
                with contextlib.redirect_stdout(io.StringIO()):
                    exit_code = fixture_usdz_suite.main(["--out", str(out_dir), "--limit", "2"])

            self.assertEqual(exit_code, 0)
            self.assertEqual(process_fixture.call_count, 2)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["fixture_count"], 2)

    def test_process_fixture_records_view_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures_dir = root / "fixtures" / "states"
            fixtures_dir.mkdir(parents=True)
            fixture_path = fixtures_dir / "view.json"
            fixture_path.write_text(
                json.dumps(
                    {
                        "graph": {
                            "title": "View test",
                            "viewport": {
                                "xmin": -1,
                                "xmax": 1,
                                "ymin": -2,
                                "ymax": 2,
                                "zmin": -3,
                                "zmax": 3,
                            },
                            "worldRotation3D": [1, 0, 0, 0, 1, 0, 0, 0, 1],
                            "axis3D": [0, 0, 1],
                            "threeDMode": True,
                            "showPlane3D": False,
                        },
                        "expressions": {"list": []},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            def fake_export(_graph, _classification, usda_path, resolution):
                usda_path.parent.mkdir(parents=True, exist_ok=True)
                usda_path.write_text("#usda 1.0\n", encoding="utf-8")
                return [], [], []

            def fake_package(_usda_path, usdz_path):
                usdz_path.write_bytes(b"PK")
                return SimpleNamespace(to_dict=lambda: {"returncode": 0})

            with patch("desmos2usd.validate.fixture_usdz_suite.export_graph", side_effect=fake_export), patch(
                "desmos2usd.validate.fixture_usdz_suite.package_usdz", side_effect=fake_package
            ):
                report = fixture_usdz_suite.process_fixture(
                    fixture_path=fixture_path,
                    project_root=root,
                    out_dir=root / "artifacts" / "fixture_usdz",
                    resolution=8,
                    validate_usdz=False,
                )

            self.assertEqual(report["status"], "success")
            self.assertEqual(tuple(report["view_metadata"]["world_rotation_3d"]), (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0))
            self.assertEqual(tuple(report["view_metadata"]["axis_3d"]), (0.0, 0.0, 1.0))
            self.assertEqual(report["view_metadata"]["three_d_mode"], True)
            self.assertEqual(report["view_metadata"]["show_plane_3d"], False)


if __name__ == "__main__":
    unittest.main()
