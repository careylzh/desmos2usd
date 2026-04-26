# S2-08 Group E pass 2: rotated tilted-cylinder shells

Date: 2026-04-26
Branch: fix/student-fixture-usdz-export
Base before pass-2: 1e2517e ("Add corrected Desmos links and S2-08E probe evidence")

## Problem

S2-08 Group E uses tilted-cylinder shells of the form

```
(x*cos(0.07) + z*sin(0.07))^2 + y^2 = r^2  {z range}
```

and small offset variants

```
(x*cos(0.07) + z*sin(0.07) - 1.36*cos(k*pi/6))^2 + (y - 1.36*sin(k*pi/6))^2 = 0.06^2  {0 <= z <= 8}
```

Both have a 3-axis residual when classified as `implicit_surface`. Pass-1 added
`tessellate_circular_implicit_surface` (cylinders.py) which fits a circle to each
slice. The fit fails for these expressions because the cross-section is a slight
ellipse (squashed by `cos(0.07) ≈ 0.995`), so its boundary tolerance check rejects
the fit. Result before pass-2: 38 prims, 45 unsupported (40 of "implicit surface
requires a supported bounded three-axis form").

The tiny `0.06`-radius variants additionally have the issue that with viewport
±12 and a fixed marching grid, the cell width is far larger than the feature, so
even a marching-squares contour at that resolution sees no sign change.

## Fix

1. **3-axis marching-squares fallback** (`tessellate_implicit_surface_3axis_marching`
   in `tessellate/implicit.py`). Used when `tessellate_circular_implicit_surface`
   returns None or zero faces. Picks the shortest constant-bounded axis as the
   slicing axis, marches squares at each slice, and stitches adjacent slices via
   nearest-segment matching (works for convex contours that don't change topology
   between slices — fine for tilted cylinder shells).

2. **Adaptive bbox refinement** (`_refine_3axis_bbox`). Two stages: a coarse
   sign-change scan; if nothing found, zoom around the argmin |residual| and
   rescan at higher density. Lets the marching grid resolve features that are
   tiny relative to the viewport.

3. **`=` predicate variable_bounds** (`parse/predicates.py`). `z = N` with
   constant N now reports a degenerate bound `(N, N)` so the 3-axis tessellator
   can pick z as the slicing axis even when the predicate is exact equality.

4. **Inequality voxel-sampler bbox refinement**
   (`_refine_inequality_bbox` in `tessellate/slabs.py`). Same coarse-scan idea
   for the inequality fallback path so small inequality regions inside large
   viewports produce voxels.

## Result

| Fixture       | Before (chektien base 1e2517e) | After pass-2 |
|---------------|--------------------------------|--------------|
| S2-08 Group E | 38 prims, 45 unsupported       | 78 prims, 5 unsupported |
| S2-09 Group F | 27 prims, 0 unsupported (success) | 27 prims, 0 unsupported (success) — regression guard intact |

Remaining S2-08E unsupported (5 of 83):

- 2 `classification: not a supported renderable geometry form` for
  `abs(x)+abs(x)=1.7` and `abs(y)+abs(y)=1.7` — these simplify to `2|x|=1.7`
  i.e. a single-axis equation (a pair of planes), which the implicit handler
  legitimately rejects. Likely an authoring typo for `abs(x)+abs(y)=1.7`.
- 3 `inequality_region did not resolve to sampled cells` for flat disks
  `x^2+y^2 <= 4 {z=0}`, `x^2+y^2+0.5 <= 4 {z=0}`,
  `x^2+y^2+x <= 1.5 {z=8}` — voxel sampling fundamentally cannot produce a
  filled box at a single-z slice; needs a flat-disk render path. Not addressed
  this pass.

## Tests

Added in `tests/test_student_fixture_regressions.py`:

- `test_rotated_coordinate_tilted_cylinder_falls_back_to_marching_squares`
- `test_small_offset_tilted_cylinder_uses_adaptive_bbox`
- `test_equality_predicate_yields_degenerate_axis_bound`
- `test_inequality_voxel_sampler_refines_bbox_for_small_region`

All 98 existing tests still pass.

## Visual evidence

Browser capture not available from chekbook in this dispatched session (the
viewer is served from chekstool). The previous probe evidence in
`../20260426_s208_group_e_probe/` (Desmos vs viewer screenshots before pass-2)
remains the canonical "before" snapshot; the current `*.usda`/`*.usdz` files in
`artifacts/fixture_usdz/[4B] 3D Diagram - S2-08 Group E.{usda,usdz}` are the
"after" outputs. Main agent on chekstool should refresh the live viewer
screenshot at the URL noted in the original task brief and place it as
`viewer_after_pass2.png` next to this note.
