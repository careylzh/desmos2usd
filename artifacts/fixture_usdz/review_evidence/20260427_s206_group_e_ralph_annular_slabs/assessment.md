# S2-06 Group E Ralph Annular Slabs

Target: `[4B] 3D Diagram - S2-06 Group E.json`
Desmos URL: `https://www.desmos.com/3d/cg2sd6h1ws`

## Change

Implemented a general analytic exporter path for axis-aligned annular quadratic slabs, e.g. `low < x^2/2 + y^2 < high {z0 < z < z1}`. The exporter fits the inner and outer ellipse profiles and emits a closed annular extrusion mesh instead of relying on voxel sampling.

No fixture names, expression ids, or S2-06 constants are encoded in the fix.

## Evidence

- `S2-06_Group_E_projection_before.png` / `.ppm` / `.usda`: previous local projection baseline.
- `S2-06_Group_E_projection_after.png` / `.ppm` / `.usda`: regenerated local projection after this tranche.
- `S2-08_Group_E_projection_guard_after.png` / `.ppm` / `.usda`: guard projection.
- `S2-09_Group_F_projection_guard_after.png` / `.ppm` / `.usda`: guard projection.
- `before_metrics.json`
- `after_metrics.json`
- `projection_results.json`
- `capture_results.json`

## Metrics

- S2-06 Group E before: `723` prims, `13` unsupported, `736` classified/renderable, valid USDZ.
- S2-06 Group E after: `727` prims, `9` unsupported, `736` classified/renderable, valid USDZ, `usdchecker --arkit` return code `0`.
- S2-08 Group E guard remains success: `87` prims, `0` unsupported, valid USDZ, `usdchecker --arkit` return code `0`.
- S2-09 Group F guard remains success: `27` prims, `0` unsupported, valid USDZ, `usdchecker --arkit` return code `0`.
- Full summary remains `71` fixtures, `27` success, `44` partial, `0` error, `71` USDZ artifacts.

## Remaining Mismatch

Live visual parity is not claimed. Playwright and Chrome DevTools browser capture returned `user cancelled MCP tool call`; the Tailscale root, viewer, and summary routes failed DNS resolution from this environment.

Remaining S2-06E unsupported families:

- y-squared bridge surfaces: `209_18`, `209_54`
- random-point Gaussian inequality regions: `214`, `217`, `218`, `222`, `230`, `246`, `248`
