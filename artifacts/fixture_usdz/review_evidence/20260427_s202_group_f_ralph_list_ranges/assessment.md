# S2-02 Group F Ralph Tranche

- Target: `[4B] 3D Diagram - S2-02 Group F.json`
- Desmos: https://www.desmos.com/3d/1zpiejy9c9
- Fix: one-axis quadratic inequality bands such as `(z-0.3)^2 <= 0.0025` now tessellate as thin slabs using the existing band mesh path.
- Fresh local before evidence at resolution 8: `95 prims / 111 unsupported / valid true`.
- Tracked after artifact at resolution 12: `159 prims / 47 unsupported / valid true / usdchecker returncode 0`.
- The 64 repeated guide-band slabs from expressions `3_*` and `71_*` are now exported.
- Remaining unsupported: 9 malformed chained `72_*` inequalities and 38 constant-z circular explicit disk caps from `90_*` and `98_*`.
- Browser capture blocker: both Playwright and Chrome DevTools returned `user cancelled MCP tool call` for Desmos navigation; Playwright returned the same for the live viewer link.
- Tailscale route blocker: root, viewer, and summary routes failed DNS lookup with `curl: (6) Could not resolve host: chq.singapura-broadnose.ts.net`.
- Visual claim: structural/local projection progress only, not live Desmos/viewer parity.
