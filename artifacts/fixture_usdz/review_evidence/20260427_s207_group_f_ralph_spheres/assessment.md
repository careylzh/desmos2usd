# S2-07 Group F Ralph Sphere Tranche

- Target fixture: `[4B] 3D Diagram - S2-07 Group F.json`
- Desmos URL: `https://www.desmos.com/3d/jkj1z8t8pf`
- Evidence directory: `artifacts/fixture_usdz/review_evidence/20260427_s207_group_f_ralph_spheres/`
- Live visual gate status: blocked. Chrome DevTools and Playwright navigation both returned `user cancelled MCP tool call`; local viewer server bind returned `PermissionError: [Errno 1] Operation not permitted`.

## Structural Result

- Implemented a general axis-aligned ellipsoid tessellation path for three-axis implicit equalities with no constant-bounded slice axis.
- This resolves the repeated tiny implicit sphere family in S2-07F without fixture IDs or fixture constants.
- S2-07F improved from `835 prims / 53 unsupported` to `874 prims / 14 unsupported`.
- S2-08 Group E remains `87 prims / 0 unsupported`.
- S2-09 Group F remains `27 prims / 0 unsupported`.

## Evidence Files

- `S2-07_Group_F_projection_before.png`
- `S2-07_Group_F_projection_before.ppm`
- `S2-07_Group_F_projection_after.png`
- `S2-07_Group_F_projection_after.ppm`
- `S2-07_Group_F_projection_after.usda`
- `S2-08_Group_E_projection_guard_after.png`
- `S2-08_Group_E_projection_guard_after.ppm`
- `S2-08_Group_E_projection_guard_after.usda`
- `S2-09_Group_F_projection_guard_after.png`
- `S2-09_Group_F_projection_guard_after.ppm`
- `S2-09_Group_F_projection_guard_after.usda`
- `projection_results.json`
- `capture_results.json`

## Remaining Mismatch

- No live Desmos/viewer parity claim was made.
- Remaining S2-07F unsupported items are 13 classification/parser misses and one sampled inequality region (`325`).
- Next exact S2-07F target: parser support for implicit multiplication in forms such as `2z=.515x+1.91` and chained slab inequalities with affine function bounds, or inequality-region support for expression `325`.
