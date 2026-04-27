# S2-06 Group E Ralph Steep Bridges

Captured at: 2026-04-27 10:37 +08

Target fixture: `[4B] 3D Diagram - S2-06 Group E.json`
Desmos URL: `https://www.desmos.com/3d/cg2sd6h1ws`

## Change

Added a general explicit-surface reorientation path for very steep affine surfaces. When an expression such as `y=m*x+b` has an enormous finite slope, the tessellator now solves it as `x=(y-b)/m` and samples over the wider `y,z` domain. This fixes near-vertical bridge surfaces without fixture ids or fixture constants.

## Metrics

- Before: `727 prims / 9 unsupported / 736 classified / valid true`.
- After: `729 prims / 7 unsupported / 736 classified / valid true`.
- Removed unsupported expression ids: `209_18`, `209_54`.
- Remaining unsupported expression ids: `214`, `217`, `218`, `222`, `230`, `248`, `246`.
- S2-08 Group E guard remains success: `87 prims / 0 unsupported / valid true`.
- S2-09 Group F guard remains success: `27 prims / 0 unsupported / valid true`.

## Evidence

- `S2-06_Group_E_projection_before.png` / `.ppm` / `.usda`
- `S2-06_Group_E_projection_after.png` / `.ppm` / `.usda`
- `S2-08_Group_E_projection_guard_after.png` / `.ppm` / `.usda`
- `S2-09_Group_F_projection_guard_after.png` / `.ppm` / `.usda`
- `before_metrics.json`
- `after_metrics.json`
- `capture_results.json`
- `projection_results.json`

## Capture Status

Live Desmos and viewer capture are blocked in this environment. Playwright and Chrome DevTools navigation returned `user cancelled MCP tool call`; local `http.server` failed with `PermissionError: [Errno 1] Operation not permitted`; tailnet route checks failed DNS resolution for `chq.singapura-broadnose.ts.net`.

No live visual parity claim is made. Local deterministic projections show structural progress only.

## Next Target

The remaining S2-06E mismatch is the random Gaussian floor texture family. Desmos documents `random(n)` as producing `n` random values, so exact support needs a bounded list-valued random export strategy rather than a scalar fallback.
