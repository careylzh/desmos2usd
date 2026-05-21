# S2-01 Group B Visual Gate Retry

- Target fixture: `[4B] 3D Diagram - S2-01 Group B.json`
- Desmos URL: `https://www.desmos.com/3d/27v0xuv64m`
- Evidence directory: `artifacts/fixture_usdz/review_evidence/20260427_s201_group_b_ralph_visual_gate_retry/`
- Outcome: blocked, no exporter/viewer code change.

## Why This Tranche Stopped

S2-01B is already structurally complete in the tracked artifact and in a fresh offline precheck: `143 prims / 0 unsupported / 143 classified / 143 renderable / valid true`.

The reported problem is visual: Chek said the viewer still looks wrong despite metrics success. This environment still cannot capture either the live Desmos model or the live viewer:

- Playwright and Chrome DevTools both returned `user cancelled MCP tool call` for the Desmos URL.
- Playwright and Chrome DevTools both returned `user cancelled MCP tool call` for the local `file://` viewer URL.
- The Tailscale review routes for root, viewer, and summary all failed DNS resolution.
- A local `python3 -m http.server 8765 --bind 127.0.0.1` viewer server failed with `PermissionError: [Errno 1] Operation not permitted`.
- Headless Chrome against the local `file://` viewer exited `-1` without creating a screenshot.

Without a rendered Desmos reference, a rendered viewer screenshot, or fresh concrete visual feedback, another S2-01B fix would be speculative. The correct next step is Chek review or fresh mismatch detail.

## Offline Evidence

- `S2-01_Group_B_projection.png`
- `S2-01_Group_B_projection.ppm`
- `S2-01_Group_B_projection.usda`
- `S2-01_Group_B_projection.usdz`
- `S2-01_Group_B_projection.report.json`
- `S2-08_Group_E_projection_guard.png`
- `S2-08_Group_E_projection_guard.ppm`
- `S2-08_Group_E_projection_guard.usda`
- `S2-08_Group_E_projection_guard.usdz`
- `S2-08_Group_E_projection_guard.report.json`
- `S2-09_Group_F_projection_guard.png`
- `S2-09_Group_F_projection_guard.ppm`
- `S2-09_Group_F_projection_guard.usda`
- `S2-09_Group_F_projection_guard.usdz`
- `S2-09_Group_F_projection_guard.report.json`
- `precheck/summary.json`
- `projection_results.json`
- `capture_results.json`

## Metrics

- S2-01 Group B: `143 prims / 0 unsupported / valid true / success`
- S2-08 Group E guard: `87 prims / 0 unsupported / valid true / success`
- S2-09 Group F guard: `27 prims / 0 unsupported / valid true / success`

## Visual Claim

No live Desmos/viewer parity claim. The PNGs are deterministic offline projection evidence only.
