# S2-03 / S2-05 View Basis Assessment

Captured at: 2026-04-26 15:39 SGT

## Change

- `viewer/app.js` now interprets `desmos:worldRotation3D` as a row-major matrix whose columns carry Desmos camera basis data.
- The viewer basis is now:
  - camera depth: negative first column
  - screen right: negative second column
  - screen up: third column
- This replaces the previous row-vector interpretation that made S2-05 look top-down/flattened and made S2-03 collapse to a front slice.

## Evidence

- Fresh Desmos screenshots copied from the main-agent recheck:
  - `S2-03_Group_B_desmos.png`
  - `S2-05_Group_D_desmos.png`
- Diagnostic local projections generated from current S2-03/S2-05 geometry with the fixed camera basis:
  - `S2-03_Group_B_local_projection_fixed_camera.png`
  - `S2-05_Group_D_local_projection_fixed_camera.png`
- Contact sheet:
  - `diagnostic_contact_sheet.png`
- Capture log:
  - `capture-results.json`

## Browser Capture Status

Local browser screenshots were not captured in this sandbox.

- Playwright MCP navigation returned `user cancelled MCP tool call`.
- Chrome DevTools MCP navigation returned `user cancelled MCP tool call`.
- `python3 -m http.server 8765 --bind 127.0.0.1` failed with `PermissionError: [Errno 1] Operation not permitted`.
- Google Chrome headless exited before producing a screenshot.
- `curl` to `chq.singapura-broadnose.ts.net` failed DNS resolution.

The diagnostic local images are not a replacement for Playwright viewer screenshots; they are geometry/camera projections used to judge whether the viewer basis fix is directionally correct.

## Visual Judgment

- S2-05 Group D: materially improved by diagnosis. The fixed-basis projection is a tall Eiffel-tower-like structure with four red legs, gray lattice, and dark top cap/spire. This addresses the flattened diamond view seen in the fresh local browser screenshot. Browser parity remains unverified.
- S2-03 Group B: materially improved by diagnosis. The fixed-basis projection restores the long blue slab/body with the rounded end visible instead of the compact front-slice frame. The diagnostic projection shows internal orange/gray geometry more strongly than the browser should because it uses translucent diagnostic fills. Browser parity remains unverified.
- S2-09 Group F: not regenerated. The same fixed basis keeps the diagnostic cylinder oriented with its top cap visible, matching the previously accepted S2-09 visual direction closely enough for a non-browser regression check, but no S2-09 artifacts were changed.

## Remaining Mismatch

- A browser-capable recapture is still required before claiming full visual parity.
- S2-03 local browser rendering may still differ in material occlusion and fit because the diagnostic renderer is not the WebGL viewer.
