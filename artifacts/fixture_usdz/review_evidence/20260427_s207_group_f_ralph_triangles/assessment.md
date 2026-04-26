# S2-07 Group F Ralph Triangles Tranche

- Target fixture: `[4B] 3D Diagram - S2-07 Group F.json`
- Desmos URL: `https://www.desmos.com/3d/jkj1z8t8pf`
- Fix assessed: general point-list indexing for triangle meshes, including `A[B.x]` and subscripted point lists such as `G_{1}[H_{1}.x]`.

## Evidence

- `S2-07_Group_F_projection_after.png` and `.ppm`: deterministic XY/XZ/YZ projection after the fix.
- `S2-07_Group_F_projection_after.usda`: evidence USDA generated from the same fixed classifier/export path.
- `S2-08_Group_E_projection_guard_after.png` and `.ppm`: guard projection.
- `S2-09_Group_F_projection_guard_after.png` and `.ppm`: guard projection.
- `projection_results.json`: projection-generation counts.
- `capture_results.json`: failed live browser/viewer capture attempts and exact blocker details.

## Metrics

- S2-07F before: `36 prims / 69 unsupported / 37 classified`.
- S2-07F after: `835 prims / 53 unsupported / 875 classified / valid true / usdchecker returncode 0`.
- Triangle mesh exports after: `799` triangle prims.
- S2-08E guard remains success: `87 prims / 0 unsupported / valid true / usdchecker returncode 0`.
- S2-09F guard remains success: `27 prims / 0 unsupported / valid true / usdchecker returncode 0`.

## Visual Status

Live Desmos and live viewer capture are blocked in this environment. This tranche does not claim live visual parity. The structural projection shows the previously missing truss/point-list triangle geometry now exported, and the remaining S2-07F mismatch is still partial due to unresolved affine parser cases, sphere-like 3-axis implicit surfaces, and expression `325`.
