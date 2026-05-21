from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ViewerCameraTests(unittest.TestCase):
    def test_camera_module_interprets_desmos_world_rotation_rows_as_basis(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("node unavailable")

        rotation = [
            3.1045512010348404e-17,
            -1.0,
            5.277855284743943e-17,
            0.5070116874835013,
            6.123233995736766e-17,
            0.8619391792668044,
            -0.8619391792668044,
            0.0,
            0.5070116874835013,
        ]
        script = """
const camera = require("./viewer/camera.js");
const basis = camera.cameraBasisFromWorldRotation(JSON.parse(process.argv[1]));
console.log(JSON.stringify(basis));
"""
        result = subprocess.run(
            [node, "-e", script, json.dumps(rotation)],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        basis = json.loads(result.stdout)

        self.assertVectorAlmostEqual(basis["right"], rotation[0:3])
        self.assertVectorAlmostEqual(basis["up"], rotation[3:6])
        self.assertVectorAlmostEqual(basis["depth"], rotation[6:9])

    def test_viewer_loads_camera_module_before_app(self) -> None:
        html = (ROOT / "viewer" / "index.html").read_text(encoding="utf-8")
        self.assertLess(html.index("./camera.js"), html.index("./app.js"))

    def assertVectorAlmostEqual(self, actual: list[float], expected: list[float]) -> None:
        for left, right in zip(actual, expected, strict=True):
            self.assertAlmostEqual(left, right, places=12)


if __name__ == "__main__":
    unittest.main()
