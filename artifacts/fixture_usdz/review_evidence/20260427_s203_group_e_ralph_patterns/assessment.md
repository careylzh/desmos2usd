# S2-03 Group E Ralph Pattern Definitions

Target: `[4B] 3D Diagram - S2-03 Group E.json`
Desmos URL: `https://www.desmos.com/3d/sqkhp7wnx6`

Browser capture status: blocked. Playwright navigation and Chrome DevTools `new_page` both returned `user cancelled MCP tool call`, so this tranche does not claim live Desmos/viewer visual parity.

Evidence files:
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

Structural result:
- S2-03 Group E improved from `111 prims / 85 unsupported / 190 classified` to `393 prims / 71 unsupported / 464 classified`.
- S2-08 Group E guard remains success at `87 prims / 0 unsupported`.
- S2-09 Group F guard remains success at `27 prims / 0 unsupported`.

Remaining S2-03E mismatch:
- The largest remaining family is the generated rotated thin diagonal bands from expressions `84`-`103`, which classify after point-field expansion but still fail sampled-cell resolution.
- Remaining unsupported also includes unbounded sphere-like implicit surfaces (`189`, `300_*`, `363_*`) and diagonal bridge strips (`259`, `260`, `265`, `267`, `272`, `273`, `274`, `275`).
