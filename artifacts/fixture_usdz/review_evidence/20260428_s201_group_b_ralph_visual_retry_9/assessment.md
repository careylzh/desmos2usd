# S2-01 Group B visual retry 9 assessment

- Target fixture: `[4B] 3D Diagram - S2-01 Group B.json`
- Desmos URL: `https://www.desmos.com/3d/27v0xuv64m`
- Outcome: blocked, no exporter/viewer code change.
- Reason: tracked and regenerated metrics remain structurally complete (`143 prims / 0 unsupported / valid true`), but Chek's report is a visual mismatch. Live Desmos and live viewer capture are still unavailable in this sandbox, so a code change would be speculative.

## Evidence

- `capture_results.json` records all failed live-capture routes.
- `S2-01_Group_B_projection.png` is deterministic offline projection evidence only.
- `S2-08_Group_E_projection_guard.png` and `S2-09_Group_F_projection_guard.png` preserve the required guards.
- `projection_results.json` and `precheck/summary.json` both report 3/3 success with zero unsupported expressions.

## Visual claim

No visual parity claim is made from this tranche. The direct viewer must be checked against the Desmos URL by Chek or by a future environment with browser capture working.
