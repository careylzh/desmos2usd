# S2-03 Group E Ralph Top Sphere Caps

Structural result: predicate-clipped axis-aligned implicit ellipsoids now export as valid mesh caps instead of falling through to the 3-axis marching fallback that requires a constant-bounded axis.

## Metrics
- Before: `460 prims / 464 classified / 4 unsupported / partial`.
- After: `464 prims / 464 classified / 0 unsupported / success`.
- Added cap prims: `363_0`, `363_1`, `363_2`, `363_3`; each validates as `64 faces / 65 points`.
- Overall fixture summary: `71 fixtures / 29 success / 42 partial / 0 error / 71 USDZ`.
- Guards remain success: S2-08 Group E `87 prims / 0 unsupported`; S2-09 Group F `27 prims / 0 unsupported`.

## Evidence
- `S2-03_Group_E_projection_before.png` and `.ppm`: deterministic local projection from the pre-fix USDA.
- `S2-03_Group_E_projection_after.png` and `.ppm`: deterministic local projection from the regenerated USDA.
- `S2-08_Group_E_projection_guard_after.png` and `.ppm`: deterministic guard projection.
- `S2-09_Group_F_projection_guard_after.png` and `.ppm`: deterministic guard projection.
- `before_metrics.json`, `after_metrics.json`, `capture_results.json`, and `projection_results.json`.

## Visual Gate
Live browser capture remains blocked. Playwright and Chrome DevTools navigation calls returned `user cancelled MCP tool call`, and Tailscale route checks failed with `curl: (6) Could not resolve host: chq.singapura-broadnose.ts.net`. This tranche does not claim live Desmos/viewer parity; it claims structural/local projection progress only.
