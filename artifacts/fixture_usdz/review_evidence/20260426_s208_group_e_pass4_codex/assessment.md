# S2-08 Group E pass 4 — element fidelity repair

## Summary

Pass 4 targets the element-shape mismatch in the Leaning Tower of Pisa fixture. The main
problem was that most tilted tower cylinders and horizontal bands were not using the analytic
cylinder path. They fell back to coarse 3-axis marching, producing roughly 20 faces per shell
and visibly strip-like/merged tower elements.

The exporter now fits axis-aligned quadratic profiles, so tilted cylinders with elliptic
z-slices are emitted as dense analytic meshes. Constant-z tilted rings are emitted as closed
curve rings, and flat implicit base contours are emitted as curve segments instead of empty
or four-quad meshes.

## Visual Evidence

* `S2-08_Group_E_desmos.png` — Desmos reference copied from pass-3 evidence.
* `S2-08_Group_E_viewer_pass3.png` — pass-3 live viewer baseline.
* `S2-08_Group_E_three_projection_local.png` — pass-3 deterministic projection baseline.
* `S2-08_Group_E_projection_pass4.png` — pass-4 deterministic local projection.
* `S2-09_Group_F_projection_regression_pass4.png` — S2-09F deterministic regression projection.

Live browser capture was not available in this sandbox: `python3 -m http.server` failed to bind
to localhost with `PermissionError: Operation not permitted`, and the browser MCP calls were
cancelled by the environment. Main should capture the live viewer screenshot for final review.

## S2-08E Report Deltas

* Status: `partial` -> `success`.
* Prims: `81` -> `83`.
* Unsupported: `2` -> `0`.
* USDA geometry: `62` meshes, `21` curve prims.
* Main lower shell expression `63`: `60` faces -> `1104` faces.
* One-level shells/bands that had `20` to `22` faces now use `1104` faces.
* Constant-z rings such as expressions `83` and `95` now export as closed `BasisCurves`
  with `49` points instead of coarse flat meshes.
* Previously unsupported base contours `196` and `197` now export as flat curve segments.

## S2-09F Regression

S2-09 Group F remains `success`: `27` prims, `0` unsupported, valid and complete. Its committed
artifacts were not changed.

## Remaining Review Target

The tower elements are geometrically denser and less merged, but ccwork should still review the
live viewer for color/layer readability. The main gray cylindrical tower surfaces are still opaque
viewer meshes, so some smaller colored posts and rings can be visually busy depending on camera
angle.
