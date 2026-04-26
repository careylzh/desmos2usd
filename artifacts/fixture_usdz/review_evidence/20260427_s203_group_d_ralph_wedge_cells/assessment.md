# S2-03 Group D Ralph Wedge Cells

- Target fixture: `[4B] 3D Diagram - S2-03 Group D.json`
- Desmos URL: `https://www.desmos.com/3d/zvasa1wcgo`
- Fix target: remaining 12 affine half-plane band expansions that were exported as unsupported sampled-cell failures.

## Capture Status

Live Desmos and live viewer screenshots are blocked in this environment:

- Playwright navigation to the Desmos URL returned `user cancelled MCP tool call`.
- Chrome DevTools `new_page` for the Desmos URL returned `user cancelled MCP tool call`.
- Local headless Chrome smoke screenshot exited with return code `-1` and no stdout/stderr.
- Direct Desmos state fetch failed DNS with `nodename nor servname provided, or not known`.

Visual parity is therefore not claimed. Local projection evidence was generated from the regenerated USDA artifacts:

- `S2-03_Group_D_projection_after.png`
- `S2-08_Group_E_projection_guard_after.png`
- `S2-09_Group_F_projection_guard_after.png`

## Result

- S2-03 Group D: `573 prims / 12 unsupported / 585 classified` before; `585 prims / 0 unsupported / 585 classified` after.
- The 12 former unsupported entries are now validated zero-face Mesh prims because their affine band constraints are analytically empty.
- S2-08 Group E guard remains `83 prims / 0 unsupported`.
- S2-09 Group F guard remains `27 prims / 0 unsupported`.
