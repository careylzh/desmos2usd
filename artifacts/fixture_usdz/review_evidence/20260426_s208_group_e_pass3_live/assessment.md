# S2-08 Group E pass 3 — visual fix

## Summary

Pass 3 fixes the remaining S2-08 Group E visual mismatch from pass 2. The viewer now renders
a recognizable leaning tower of stacked rings sitting on the ground plane, instead of a
viewport-tall column of vertical sheets that extended below the ground.

The bug was that 2D-only Desmos expressions (those that reference only two of `(x, y, z)`
and have no restriction on the missing axis) were being extruded across the full
`viewport_bounds` of the missing axis, producing tall sheets that dominated every camera
angle. In addition, flat-disk inequalities like `x^2+y^2<=4 {z=0}` had no working code path
and were reported as "did not resolve to sampled cells".

## Visual evidence

* `S2-08_Group_E_desmos.png` — Desmos reference (copied from pass-2 evidence directory).
* `S2-08_Group_E_viewer_pass3.png` — Live WebGL viewer at
  `http://127.0.0.1:8765/viewer/?usda=..%2Fartifacts%2Ffixture_usdz%2F%5B4B%5D%203D%20Diagram%20-%20S2-08%20Group%20E.usda`
  after pass 3. Shows a leaning tower body bounded to its expected z range, with caps,
  pillars, and base disks visible above the ground plane.
* `S2-08_Group_E_three_projection_local.png` — local deterministic XY/XZ/YZ projection of
  the regenerated geometry. The XZ and YZ panels show the leaning tower silhouette; the XY
  panel shows the colored base disks at z=0.
* `S2-09_Group_F_viewer_regression.png` — S2-09 Group F live viewer regression check.
  Still renders the orange/red lattice tower correctly; no visible regression.

## Report metrics

* S2-08 Group E: `partial`, `81` prims, `2` unsupported (was `78` prims, `5` unsupported in
  pass 2). The 2 remaining unsupported are the `abs(x)+abs(x)` / `abs(y)+abs(y)`
  classification cases (degenerate Desmos LaTeX, mathematically equivalent to `2|x|=...`,
  not a valid 2D shape).
* S2-09 Group F: `success`, `27` prims, `0` unsupported. Unchanged from pass 2.

## Geometry sanity checks

* No remaining S2-08E prim has `z` extending beyond the legitimate tower height `[0, ~9.6]`.
  Largest non-floor `z` span is 8 (the radius-0.06 pillars that run from z=0 to z=8).
* No prim has `z=[-11.91, 11.91]` — the full-viewport sheet pattern from pass 2 is gone.
* The floor plane `z=-0.01` (expression id 175) still spans the full viewport in xy; that
  is correct — it is the explicit `z=-0.01` ground plane.

## Code changes

* `src/desmos2usd/tessellate/implicit.py` — implicit 2-axis case: when the missing axis is
  not constrained by any predicate, render flat at axis=0 instead of extruding through the
  viewport. Also added `_refine_iso_window` so an unbounded 2D contour like
  `abs(x)+abs(y)=1.27` is found by the marching-squares pass even from a viewport seed.
* `src/desmos2usd/tessellate/surfaces.py` — explicit-surface flat-axis collapse, gated by
  `FLAT_AXIS_RANGE_FRACTION = 0.10`. An explicit `y=0.4 {-1.8 <= x <= -1.21}` collapses to
  a thin strip at z=0 (small constraint range vs viewport z), while a road-wall like
  `y=20 {-225 < x < 225}` keeps its viewport-tall extrusion (constraint range exceeds the
  fraction). The degenerate-axis nudge is only applied to flat-axis collapses, not to
  predicate-derived `(N, N)` ranges, so single-slice predicates remain faithful.
* `src/desmos2usd/tessellate/slabs.py` — `_flat_region_geometry` now detects the flat axis
  from either a missing axis or a constant-bounded axis (e.g. `{z=0}` or `{z=8}`), infers
  shape-axis bounds from inequality constants when predicates do not provide them, and
  refines the sampling window via `_refine_flat_region_window` so a small disk inside a
  large viewport produces dozens of cells, not just one.
* `tests/test_student_fixture_regressions.py` — four new regression tests covering each
  category of fixed expression.

## Per-fixture summary deltas (relative to pass 2)

| fixture                              | prims     | unsupported |
| ------------------------------------ | --------- | ----------- |
| `[4B] 3D Diagram - S2-04 Group C`    | 19 → 21   | 3 → 1       |
| `[4B] 3D Diagram - S2-04 Group G`    | 39 → 44   | 41 → 36     |
| `[4B] 3D Diagram - S2-08 Group E`    | 78 → 81   | 5 → 2       |

All other 68 fixtures (including S2-09 Group F) report identical prim/unsupported counts
to pass 2. Overall summary success/partial counts unchanged: 24 success, 47 partial.

## Test status

All 102 tests in `tests/` pass. Notable: `test_k0fbxxwkqf_side_planes_use_viewport_for_unconstrained_z`
still passes, confirming the road-wall semantics are preserved.
