# S2-01 Group B Point-List Tranche

- Target fixture: `[4B] 3D Diagram - S2-01 Group B.json`
- Desmos URL: `https://www.desmos.com/3d/27v0xuv64m`
- Browser capture: blocked in both Playwright and Chrome DevTools with `user cancelled MCP tool call`.
- Live viewer capture: blocked in both Playwright and Chrome DevTools with `user cancelled MCP tool call`; Tailscale route verification failed with `curl: (6) Could not resolve host: chq.singapura-broadnose.ts.net`.
- Local before projection: `S2-01_Group_B_projection_before.png`
- Local after projection: `S2-01_Group_B_projection_after.png`

## Result

Static 3D vector-list rows such as `\left[A,B\right]` now export as linear `BasisCurves` when `A` and `B` are registered point/vector definitions. This removes the nine S2-01B point-list unsupported rows without fixture-specific ids or constants.

## Metrics

- Before: `133 prims / 10 unsupported / 134 classified / 143 renderable / valid true / partial`
- After: `142 prims / 1 unsupported / 143 classified / 143 renderable / valid true / partial`
- Remaining unsupported: expression `74`, `x^{2}+y^{2}<=5000z=0`, sampled-cell miss.

## Visual Scope

The local projection changes are intentionally subtle because the point-list rows overlap existing edge curves. This evidence is structural/local only; no Desmos screenshot or live viewer parity claim is made from this environment.
