# S2-01 Group B Visual Retry 22

- Target fixture: `[4B] 3D Diagram - S2-01 Group B.json`
- Desmos URL: `https://www.desmos.com/3d/27v0xuv64m`
- Outcome: blocked; no exporter or viewer code change was made.
- Reason: the fixture remains structurally complete (`143 prims / 0 unsupported / valid true`), but the open issue is visual and all live Desmos/viewer capture paths available to this sandbox still fail.
- Visual claim: none. The PNG files in this directory are deterministic orthographic projection evidence only, not live Desmos/viewer screenshots.

## Capture Attempts

- Playwright Desmos navigation: `user cancelled MCP tool call`.
- Chrome DevTools Desmos navigation: `user cancelled MCP tool call`.
- Tailscale root/viewer/summary route checks: `curl: (6) Could not resolve host: chq.singapura-broadnose.ts.net`.
- Direct Desmos route check: `curl: (6) Could not resolve host: www.desmos.com`.
- Local viewer server: `PermissionError: [Errno 1] Operation not permitted`.
- Playwright and Chrome DevTools `file://` viewer navigation: `user cancelled MCP tool call`.
- Headless Google Chrome and Brave `file://` viewer screenshots: process exited `-1`; no screenshots were created.

## Offline Evidence

- `S2-01_Group_B_projection.png`: target deterministic projection.
- `S2-08_Group_E_projection_guard.png`: guard deterministic projection.
- `S2-09_Group_F_projection_guard.png`: guard deterministic projection.
- `precheck/summary.json`: fixture-suite precheck for S2-01B, S2-08E, and S2-09F.
- `projection_results.json`: projection regeneration summary.
