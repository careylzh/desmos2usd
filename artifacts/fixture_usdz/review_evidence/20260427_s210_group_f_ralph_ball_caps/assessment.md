# S2-10 Group F Ralph Ball-Cap Tranche

- Fixture: `[4B] 3D Diagram - S2-10 Group F.json`
- Desmos URL: `https://www.desmos.com/3d/tejhfrm34m`
- General fix: axis-aligned ellipsoid inequality regions now emit clipped surface meshes and constant-axis cap faces when the main inequality fits an ellipsoid interior.
- Before: `147` prims, `20` unsupported, `167` classified.
- After: `167` prims, `0` unsupported, `167` classified, valid USDZ with `usdchecker --arkit` return code `0`.
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

Live Desmos and live viewer capture are still blocked. Chrome DevTools and Playwright returned `user cancelled MCP tool call`; the local viewer server bind failed with `PermissionError: [Errno 1] Operation not permitted`.

No live parity claim is made. The after projection shows the lower ball-cap regions now present structurally, but live Desmos/viewer comparison still needs to be captured once browser serving is available.

## Remaining Mismatch

S2-10 Group F is structurally complete in the exporter report after this tranche. The next exact target should be live visual parity capture for S2-10F, or the highest-priority remaining partial fixture in `implementation/STATE.md` if browser capture remains blocked.
