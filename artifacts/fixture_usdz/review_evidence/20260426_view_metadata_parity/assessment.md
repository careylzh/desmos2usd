# View Metadata Parity Assessment

Captured at: 2026-04-26 12:31 SGT

## Code and Artifact Change

- The viewer now parses quoted `customLayerData` keys, including `desmos:viewportBounds`.
- Generated USDA now includes `desmos:worldRotation3D`, `desmos:axis3D`, and available Desmos view flags.
- The viewer initializes its camera from `worldRotation3D` when available, preserving Desmos' saved screen-right, screen-up, and depth basis instead of using only a guessed yaw/pitch.
- The three target USDA/report/USDZ artifacts were regenerated with view metadata:
  - `artifacts/fixture_usdz/[4B] 3D Diagram - S2-03 Group B.usda`
  - `artifacts/fixture_usdz/[4B] 3D Diagram - S2-05 Group D.usda`
  - `artifacts/fixture_usdz/[4B] 3D Diagram - S2-09 Group F.usda`

## Screenshot Evidence Status

The previous Playwright evidence remains at:

- `artifacts/fixture_usdz/review_evidence/20260426_playwright_parity/all_three_comparison.png`
- `artifacts/fixture_usdz/review_evidence/20260426_playwright_parity/capture-results.json`

That before-change comparison shows the local viewer using a materially different camera/framing for all three fixtures.

After-change screenshot capture did not complete in this sandbox:

- Starting a local `python3 -m http.server` failed with `PermissionError: [Errno 1] Operation not permitted`.
- `curl` to the existing tailnet viewer route and Desmos failed DNS resolution with `curl: (6) Could not resolve host`.
- Playwright/Chromium launch failed before navigation with `bootstrap_check_in org.chromium.Chromium.MachPortRendezvousServer: Permission denied (1100)` and SIGTRAP/SIGABRT.
- MCP browser calls were immediately cancelled before navigation.

No after-change screenshots were captured, so this run does not prove screenshot parity.

## Per-Fixture Judgment

- S2-03 Group B: camera metadata is now present and consumed by the viewer. Visual parity remains unverified after change.
- S2-05 Group D: camera metadata is now present and consumed by the viewer. Visual parity remains unverified after change.
- S2-09 Group F: camera metadata is now present and consumed by the viewer, including `degreeMode=true`. Visual parity remains unverified after change.

## Next Step

Run the same Playwright capture outside this sandbox or from the existing browser-capable orchestration environment and compare the new local screenshots against the saved Desmos screenshots before touching exporter geometry.
