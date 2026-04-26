# S2-10 Group F Ralph Modulo-Region Tranche

- Fixture: `[4B] 3D Diagram - S2-10 Group F.json`
- Desmos URL: `https://www.desmos.com/3d/tejhfrm34m`
- General fix: modulo stripe inequality regions are decomposed into repeated bounded axis intervals, then emitted through the existing circular-extrusion or box/extrusion paths.
- Before: `120` prims, `47` unsupported, `167` classified.
- After: `147` prims, `20` unsupported, `167` classified, valid USDZ with `usdchecker --arkit` return code `0`.
- Guards: S2-08 Group E remains success at `87` prims / `0` unsupported; S2-09 Group F remains success at `27` prims / `0` unsupported.

## Evidence Files

- `S2-10_Group_F_projection_before.png`
- `S2-10_Group_F_projection_after.png`
- `S2-10_Group_F_projection_before.usda`
- `S2-10_Group_F_projection_after.usda`
- `S2-08_Group_E_projection_guard_after.png`
- `S2-09_Group_F_projection_guard_after.png`
- `capture_results.json`
- `projection_results.json`

## Visual Gate

Live Desmos and live viewer capture are still blocked. Chrome DevTools and Playwright both returned `user cancelled MCP tool call`; the local viewer server bind failed with `PermissionError: [Errno 1] Operation not permitted`.

No live parity claim is made. The after projection shows structural additions for the repeated modulo columns/slats, but the remaining mismatch must be checked against live Desmos once browser capture is available.

## Remaining Mismatch

The remaining S2-10F unsupported family is `20` small spherical/ball cap inequalities around `z=5`, for example `(x-7)^2+(y-4)^2+(z-5)^2<0.5^2 {z<5}`. A next bounded tranche should add a general inequality-ball/cap tessellation path rather than extending modulo-region handling.
