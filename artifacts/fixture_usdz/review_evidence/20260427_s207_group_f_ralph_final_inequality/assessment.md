# S2-07 Group F Ralph Final Inequality

Target fixture: `[4B] 3D Diagram - S2-07 Group F.json`
Desmos URL: `https://www.desmos.com/3d/jkj1z8t8pf`

## Structural Result

- Implemented a general chained quadratic disk extrusion path for inequalities shaped like `(x-a)^2+(y-b)^2 <= r^2 <= z <= h`, intersected with ordinary axis restrictions.
- The remaining S2-07F expression `325` now exports as a capped cylinder mesh instead of falling through to sampled voxel cells.
- No fixture IDs, fixture names, or one-off constants were added.

## Metrics

- Before: `887 prims / 888 classified / 1 unsupported / partial`.
- After: `888 prims / 888 classified / 0 unsupported / success`.
- Overall fixture summary: `71 fixtures / 30 success / 41 partial / 0 error / 71 USDZ`.
- Guards remain success: S2-08 Group E `87 prims / 0 unsupported`; S2-09 Group F `27 prims / 0 unsupported`.

## Evidence

- `S2-07_Group_F_projection_before.png` and `.ppm`: deterministic local projection before the fix.
- `S2-07_Group_F_projection_after.png` and `.ppm`: deterministic local projection after the fix.
- `S2-08_Group_E_projection_guard_after.png` and `.ppm`: deterministic guard projection.
- `S2-09_Group_F_projection_guard_after.png` and `.ppm`: deterministic guard projection.
- `before_metrics.json`, `after_metrics.json`, `capture_results.json`, and `projection_results.json`.

## Visual Gate

Live browser capture remains blocked. Playwright and Chrome DevTools navigation returned `user cancelled MCP tool call`, and Tailscale route checks failed with `curl: (6) Could not resolve host: chq.singapura-broadnose.ts.net`. This tranche does not claim live Desmos/viewer parity; it claims structural/local projection progress only.
