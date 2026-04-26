# S2-03 / S2-05 Domain And Slab Assessment

Captured at: 2026-04-26 SGT

## Before Evidence

- `artifacts/fixture_usdz/review_evidence/20260426_s203_s205_current_check/S2-03_Group_B_desmos.png`
- `artifacts/fixture_usdz/review_evidence/20260426_s203_s205_current_check/S2-03_Group_B_local.png`
- `artifacts/fixture_usdz/review_evidence/20260426_s203_s205_current_check/S2-05_Group_D_desmos.png`
- `artifacts/fixture_usdz/review_evidence/20260426_s203_s205_current_check/S2-05_Group_D_local.png`
- `artifacts/fixture_usdz/review_evidence/20260426_s203_s205_current_check/capture-results.json`

## What Changed

- S2-03 Group B: bounded 3D inequality bands now keep visual caps even when the band uses strict inequalities. Expr `123` (`0<z<2 {-10<y<20} {-10<x<45}`) changed from side-only wall geometry to a filled capped slab: `12` faces -> `30` faces.
- S2-05 Group D: parametric curves now use Desmos' stored `parametricDomain` when the LaTeX itself does not contain an explicit `{...}` parameter bound. Red outer curves `e1` through `e4` now sample `t=0..138` instead of the fallback `0..1`; arch curves `e23` through `e26` now sample `0..pi`.
- S2-09 Group F was not regenerated or changed in this pass.

## After Artifact Checks

- `artifacts/fixture_usdz/[4B] 3D Diagram - S2-03 Group B.usda`
  - status: `success`
  - prims: `12`
  - unsupported: `0`
  - expr `123`: `32` points, `30` faces, valid
- `artifacts/fixture_usdz/[4B] 3D Diagram - S2-05 Group D.usda`
  - status: `success`
  - prims: `150`
  - unsupported: `0`
  - curve `e1`: first point `(40, 40, 0)`, last point approximately `(7.215, 7.215, 138)`

## Screenshot Capture Status

After-change screenshot capture did not complete in this sandbox.

- Playwright/Chrome failed before navigation for all four target pages with `browserType.launch: Target page, context or browser has been closed`; the launch log shows Chrome exiting with `SIGABRT` and `kill EPERM`.
- Chrome DevTools MCP navigation to the local viewer returned `user cancelled MCP tool call`.
- Playwright MCP navigation to the local viewer returned `user cancelled MCP tool call`.
- The failure log is recorded in `artifacts/fixture_usdz/review_evidence/20260426_s203_s205_after_domain_caps/capture-results.json`.

No after-change browser screenshots were produced in this evidence directory.

## Visual Judgment

- S2-03 Group B: structurally improved. The missing filled blue slab body is now represented by capped mesh faces. Browser visual parity remains unverified because capture failed.
- S2-05 Group D: structurally improved. The red outer legs and base arches now have the correct parameter extents instead of collapsing to tiny fragments. Browser visual parity remains unverified because capture failed.
- Remaining risk: the latest browser screenshot evidence before this change also showed local viewer camera/framing differences. This pass did not change viewer camera code, so a browser-capable recapture is still required to confirm final visual parity.
