# S2-04 Group G Ralph Tranche - Desmos sphere support

- Target: S2-04 Group G
- Desmos URL: https://www.desmos.com/3d/ratctlkc9i
- Change: added general classification support for `\operatorname{sphere}(center, radius)` by lowering it to an implicit axis-aligned sphere residual and reusing the existing ellipsoid tessellator.
- Scope: no fixture names, expression ids, or one-off numeric constants were added.

## Evidence

- Live Desmos screenshot capture failed: Chrome DevTools and Playwright both returned `user cancelled MCP tool call`.
- Live viewer capture failed: Chrome DevTools returned `user cancelled MCP tool call`.
- Tailscale route checks failed for root, viewer, and summary with `curl: (6) Could not resolve host: chq.singapura-broadnose.ts.net`.
- Visual claim: structural/local projection progress only; no live parity claim.

## Local Projection Files

- `S2-04_Group_G_projection_before.png`
- `S2-04_Group_G_projection_before.ppm`
- `S2-04_Group_G_projection_before.usda`
- `S2-04_Group_G_report_before.json`
- `S2-04_Group_G_projection_after.png`
- `S2-04_Group_G_projection_after.ppm`
- `S2-04_Group_G_projection_after.usda`
- `S2-04_Group_G_report_after.json`
- `S2-04_Group_G_tracked_report_after.json`
- `S2-08_Group_E_projection_guard_after.png`
- `S2-09_Group_F_projection_guard_after.png`

## Metrics

- Latest tracked summary at tranche start: `44 prims / 36 unsupported / 56 classified`.
- Fresh pre-edit local export from current code: `70 prims / 36 unsupported / 82 classified / valid true`.
- After tracked regeneration: `91 prims / 15 unsupported / 103 classified / valid true / usdchecker --arkit 0`.
- Fixed family: 21 `\operatorname{sphere}` expressions now classify/export.
- Remaining S2-04G unsupported: 3 color definitions (`hsv`/`okhsv`), 4 `x/\infty = ...` implicit helper planes, 8 `z/\infty +/- constant` explicit helper planes.
- Guards: S2-08 Group E remains `87 prims / 0 unsupported`; S2-09 Group F remains `27 prims / 0 unsupported`.
