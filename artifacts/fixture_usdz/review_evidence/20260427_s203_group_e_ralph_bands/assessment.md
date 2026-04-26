# S2-03 Group E Ralph Bands Tranche

- Target: `[4B] 3D Diagram - S2-03 Group E.json`
- Desmos URL: `https://www.desmos.com/3d/sqkhp7wnx6`
- Scope: structural exporter fix only. Live Desmos and live viewer screenshots are blocked in this sandbox, so this evidence does not claim visual parity.

## Browser / Viewer Capture

- `mcp__playwright.browser_navigate https://www.desmos.com/3d/sqkhp7wnx6` returned `user cancelled MCP tool call`.
- `mcp__chrome_devtools.new_page https://www.desmos.com/3d/sqkhp7wnx6` returned `user cancelled MCP tool call`.
- Local Chrome headless screenshot exited with code `-1` and created no screenshot.
- Local viewer server failed: `python3 -m http.server 8765 --bind 127.0.0.1` raised `PermissionError: [Errno 1] Operation not permitted`.

## Structural Result

- S2-03 Group E improved from `393` prims / `71` unsupported to `447` prims / `17` unsupported.
- The fixed family is the rotated affine x/y half-plane strip set, including expressions `84`-`103`, plus the affine bridge strips `259`, `260`, `265`, `267`, `272`, `273`, `274`, and `275`.
- S2-08 Group E guard remains `87` prims / `0` unsupported.
- S2-09 Group F guard remains `27` prims / `0` unsupported.

## Evidence Files

- `S2-03_Group_E_projection_after.png`
- `S2-03_Group_E_projection_after.ppm`
- `S2-03_Group_E_projection_after.usda`
- `S2-08_Group_E_projection_guard_after.png`
- `S2-08_Group_E_projection_guard_after.ppm`
- `S2-08_Group_E_projection_guard_after.usda`
- `S2-09_Group_F_projection_guard_after.png`
- `S2-09_Group_F_projection_guard_after.ppm`
- `S2-09_Group_F_projection_guard_after.usda`
- `capture_results.json`

## Remaining Unsupported

- Spherical implicit cap family: `363_0`-`363_3`, `300_0`-`300_3`, and `189`.
- Non-affine arc/cutout inequality family: `254`, `257`, `261`, `263`, `268`, `269`, `270`, and `271`.
