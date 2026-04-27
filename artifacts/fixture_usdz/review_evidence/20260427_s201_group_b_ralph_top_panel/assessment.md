# S2-01 Group B Top-Panel Tranche

- Target fixture: `[4B] 3D Diagram - S2-01 Group B.json`
- Desmos URL: `https://www.desmos.com/3d/27v0xuv64m`
- Live Desmos/viewer capture: blocked; see `capture_results.json` for exact tool and command failures.
- Local before projection: `S2-01_Group_B_projection_before.png`
- Local after projection: `S2-01_Group_B_projection_after.png`

## Result

Constant explicit panels with both domain axes bounded by constant predicates are no longer dropped solely because the solved axis is outside the saved source viewport. This restores S2-01B expression `8`, the bounded top panel `z=130 {-10<=x<=10} {-10<=y<=10}`, which previously exported as a valid but empty mesh. Nonconstant out-of-viewport surfaces still follow the existing viewport suppression path.

## Metrics

- Before this tranche: `143 prims / 0 unsupported / success`; expression `8` was empty (`0 points / 0 faces`).
- After this tranche: `143 prims / 0 unsupported / success`; expression `8` now has `196 points / 169 faces`.
- Overall fixture summary remains `71 fixtures / 50 success / 21 partial / 0 error`.
- Guards: S2-08 Group E remains `87 prims / 0 unsupported / success`; S2-09 Group F remains `27 prims / 0 unsupported / success`.

## Visual Scope

No live parity claim is made. The deterministic projection evidence shows the regenerated model includes the previously empty top panel; browser evidence remains blocked in this environment.
