# S2-01 Group B Vector Edge Assessment

- Target: `[4B] 3D Diagram - S2-01 Group B.json`
- Desmos URL: `https://www.desmos.com/3d/27v0xuv64m`
- Fix: point-defined vector expressions such as `A+t(B-A)` now classify and export as parametric `BasisCurves`.
- Before local projection: `116 prims / 27 unsupported / 143 renderable`.
- After local projection: `133 prims / 10 unsupported / 143 renderable`.
- Remaining unsupported: point-list rows such as `[A,B]` and expression `74`, `x^{2}+y^{2}<=5000z=0`.
- Visual claim: structural/local projection progress only. Live Desmos and live viewer screenshots were blocked by MCP cancellation; Tailscale route checks failed DNS resolution.
