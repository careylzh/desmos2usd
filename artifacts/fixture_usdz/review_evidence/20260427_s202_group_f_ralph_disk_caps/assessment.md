# S2-02 Group F Ralph Disk-Cap Tranche

- Target fixture: `[4B] 3D Diagram - S2-02 Group F.json`
- Desmos URL: `https://www.desmos.com/3d/1zpiejy9c9`
- General fix: constant explicit surfaces with circular/quadratic domain predicates now export as analytic flat triangle-fan disks instead of relying on viewport grid sampling.
- Before local export: `159` prims, `47` unsupported (`72_*`: 9, `90_*`: 21, `98_*`: 17).
- After local/exported artifact: `197` prims, `9` unsupported (`72_*`: 9).
- Guard projections: S2-08 Group E remains `87` prims / `0` unsupported; S2-09 Group F remains `27` prims / `0` unsupported.
- Browser/live-viewer blocker: Chrome DevTools and Playwright Desmos navigation returned `user cancelled MCP tool call`; Chrome file-viewer navigation returned `user cancelled MCP tool call`; local HTTP server binding failed with `PermissionError: [Errno 1] Operation not permitted`.
- Route verification blocker: root, viewer, and summary Tailscale curls all failed with `curl: (6) Could not resolve host: chq.singapura-broadnose.ts.net`.
- Visual claim: structural/local projection progress only; no live Desmos parity claim.
- Remaining mismatch: the nine `72_*` malformed chained inequalities, e.g. `(y-0.2)^2 <= 0.00250 <= z <= 13.2-0.03 <= x <= 2.03`, still need interpretation.
