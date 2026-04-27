# S2-10 Group E Ralph Tranche: label-only math rows

- Target fixture: `[4B] 3D Diagram - S2-10 Group E.json`
- Desmos URL: `https://www.desmos.com/3d/xzhfl6m1td`
- Evidence status: browser Desmos and live viewer capture blocked; local deterministic projections only.

## Browser Capture

- Playwright Desmos navigation: `user cancelled MCP tool call`.
- Chrome DevTools Desmos navigation: `user cancelled MCP tool call`.
- Playwright live viewer navigation: `user cancelled MCP tool call`.
- Tailscale route checks for root, viewer, and summary all failed with `curl: (6) Could not resolve host: chq.singapura-broadnose.ts.net`.

No live visual parity claim is made from this environment.

## Diagnosis

The remaining ten S2-10E unsupported entries were visible Desmos expression rows containing section labels and separators, not graphable geometry:

- `------first\ pyramid\ lines------`
- `\sec ond\ pyramid\ sketch`
- `\sec ond\ pyramid\ lines`
- `third\ pyramid\ sketch`
- `third\ pyramid\ lines`
- `pyramid\ 4\ sketch`
- `pyramid\ 4\ lines\ `
- `pyramid\ 5\ sketch\ `
- `pyramid\ 5\ lines`
- `--------sph\ inx\ lines--------`

## Result

- Before: `249 prims / 10 unsupported / 259 renderable / partial`.
- After: `249 prims / 0 unsupported / 249 renderable / success`.
- Geometry projection is expected to be unchanged because the fix removes non-graphable label rows from renderable accounting rather than adding or changing geometry.

## Projection Evidence

- `S2-10_Group_E_projection_before.png`
- `S2-10_Group_E_projection_after.png`
- `S2-08_Group_E_projection_guard_after.png`
- `S2-09_Group_F_projection_guard_after.png`

