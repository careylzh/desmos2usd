# S2-07 Group F Ralph Slabs Assessment

- Target fixture: `[4B] 3D Diagram - S2-07 Group F.json`
- Desmos URL: `https://www.desmos.com/3d/jkj1z8t8pf`
- Fix: generalized leading-dot decimal implicit multiplication in the LaTeX parser, covering coefficients like `.515x`, `.5x`, and `.43(x+0.6)`.
- Baseline: `874 prims / 875 classified / 888 renderable / 14 unsupported`.
- After: `887 prims / 888 classified / 888 renderable / 1 unsupported`.
- Remaining unsupported expression: `325`, a sampled inequality region for `(x-u)^2+(y-v)^2 <= w^2` with a z slab.
- Guard fixtures: S2-08 Group E remains `87 prims / 0 unsupported`; S2-09 Group F remains `27 prims / 0 unsupported`.

## Evidence

- `S2-07_Group_F_projection_before.png`
- `S2-07_Group_F_projection_after.png`
- `S2-08_Group_E_projection_guard_after.png`
- `S2-09_Group_F_projection_guard_after.png`
- `before_metrics.json`
- `after_metrics.json`
- `capture_results.json`
- `projection_results.json`

Live Desmos and live viewer screenshots are blocked in this sandbox. See `capture_results.json` for exact tool and command failures. The visual claim for this tranche is structural/local projection progress only, not Desmos parity.
