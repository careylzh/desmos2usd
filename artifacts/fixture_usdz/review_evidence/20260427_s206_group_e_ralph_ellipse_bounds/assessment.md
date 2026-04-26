# S2-06 Group E Ralph Ellipse Bounds

Target: `[4B] 3D Diagram - S2-06 Group E.json`
Desmos URL: `https://www.desmos.com/3d/cg2sd6h1ws`

## Change

Implemented a general explicit-surface domain inference path for affine chord surfaces clipped by symmetric sqrt bounds, e.g. `y=m*x+c {-sqrt(q(x))<y<sqrt(q(x))}`. The exporter now solves the implied quadratic interval for the missing domain axis instead of relying on a coarse viewport-wide sample grid that can miss tangent, sub-unit visible slivers.

No fixture names, expression ids, or one-off S2-06 constants are encoded in the fix.

## Evidence

- `S2-06_Group_E_projection_before_pass5.png` / `.ppm`: deterministic local projection from the previous pass-5 artifact.
- `S2-06_Group_E_projection_after.png` / `.ppm` / `.usda`: deterministic local projection from regenerated geometry.
- `S2-08_Group_E_projection_guard_after.png` / `.ppm` / `.usda`: guard projection.
- `S2-09_Group_F_projection_guard_after.png` / `.ppm` / `.usda`: guard projection.
- `projection_results.json`: local projection metrics.
- `capture_results.json`: browser/live viewer capture blockers.

## Metrics

- S2-06 Group E before: `679` prims, `57` unsupported, `736` classified, valid USDZ.
- S2-06 Group E after: `723` prims, `13` unsupported, `736` classified, valid USDZ, `usdchecker --arkit` return code `0`.
- S2-08 Group E guard: `87` prims, `0` unsupported, success.
- S2-09 Group F guard: `27` prims, `0` unsupported, success.
- 71-fixture summary remains `26` success, `45` partial, `0` error, `71` USDZ artifacts.

## Remaining Mismatch

Live visual parity is not claimed. MCP browser tools returned `user cancelled MCP tool call`, local headless Chrome exited `-1` without a screenshot, and the local viewer server bind failed with `PermissionError: [Errno 1] Operation not permitted`.

Remaining S2-06E unsupported families are:

- elliptical annular slab inequality regions: `169`, `177`, `183`, `191`
- two y-squared bridge surfaces: `209_18`, `209_54`
- random-point Gaussian inequality regions: `214`, `217`, `218`, `222`, `230`, `246`, `248`
