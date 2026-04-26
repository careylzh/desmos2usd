# Handoff: 2026-04-26 21:30 SGT — S2-08E Pass 3 (visual parity)

## Active Task

Make S2-08 Group E visually match the Desmos leaning tower in the live viewer, not just
improve metrics. Pass 2 cut unsupported from 45 to 5 but the live screenshot still showed a
tall column of vertical sheets extending below the ground; pass 3 turns the viewer output
into a recognizable leaning tower bounded to the correct z range.

## Root Cause

Two distinct bugs combined to produce the tall-sheet appearance:

1. **2D-only expressions extruded across the viewport.** Desmos 3D renders an equation that
   doesn't mention one of `(x, y, z)` and has no restriction on it as a flat shape at
   that axis = 0. Our `tessellate_implicit_surface` 2-axis case and our
   `tessellate_explicit_surface` were both falling back to `viewport_bounds` for the
   missing axis, producing viewport-tall sheets for expressions like
   `abs(x-y)+abs(x+y)=2.4 {x^2+y^2 in annulus}` and `y=0.4 {-1.8 <= x <= -1.21}`.
2. **Flat-disk inequalities at a constant z had no working code path.** `x^2+y^2 <= 4 {z=0}`
   fell through every fallback (extrusion, band, box, voxel) because every path needed an
   axis with `low < high` for the extrude direction. The fixture suite reported
   "Inequality region for 80 did not resolve to sampled cells" for three such disks.

## What Changed

- `src/desmos2usd/tessellate/implicit.py` — implicit 2-axis case now collapses the missing
  axis to 0 when no predicate references it (the Desmos 3D 2D-in-3D convention). Added
  `_refine_iso_window` that scans for sign changes in the residual so an unbounded 2D
  contour like `abs(x)+abs(y)=1.27` is found instead of being lost between coarse cells.
- `src/desmos2usd/tessellate/surfaces.py` — added `_explicit_flat_axis`, gated by
  `FLAT_AXIS_RANGE_FRACTION = 0.10`. An explicit `y=0.4 {-1.8 <= x <= -1.21}` (constraint
  range << viewport z span) collapses to a thin strip at z=0; the road-wall case
  `y=20 {-225 < x < 225}` (constraint exceeds viewport) keeps its viewport extrusion.
  The degenerate-axis nudge only fires for flat-axis collapses, not for predicate-derived
  `(N, N)` ranges, so `z=18` predicates still land at exactly z=18.
- `src/desmos2usd/tessellate/slabs.py` — `_flat_region_geometry` now treats either a
  missing axis or a constant-bounded predicate axis as the flat axis, infers shape-axis
  bounds from inequality numeric constants when predicates don't supply them, and tightens
  the sampling window via `_refine_flat_region_window`.
- `tests/test_student_fixture_regressions.py` — four new regression tests covering each
  category (2D implicit no z, constant `y=` with small x range, flat disk at z=0, flat disk
  at z=8). Each fails on the pass-2 code and passes on pass 3.

## Validation

- `PYTHONPATH=src:tests python3 -m unittest discover tests` → 102 tests, OK.
- Existing `test_k0fbxxwkqf_side_planes_use_viewport_for_unconstrained_z` still passes,
  confirming the road-wall semantics are preserved.
- Full `[4B]` fixture sweep at resolution=12: 24 success / 47 partial / 0 error (unchanged
  totals from pass 2). Per-fixture deltas relative to pass 2:
  - **S2-08 Group E**: 78 → 81 prims, 5 → 2 unsupported (PRIMARY TARGET).
  - **S2-04 Group C**: 19 → 21 prims, 3 → 1 unsupported.
  - **S2-04 Group G**: 39 → 44 prims, 41 → 36 unsupported.
  - **S2-09 Group F**: 27 → 27 prims, 0 → 0 unsupported (regression guard intact).
  - All other 67 fixtures: identical prim/unsupported counts.
- USDA prim audit on regenerated S2-08E: zero prims now extend `z` to viewport
  `[-11.91, 11.91]`. Tallest non-floor `z` span is 8 (the radius-0.06 pillars that run from
  z=0 to z=8, by design).

## Visual evidence

- `artifacts/fixture_usdz/review_evidence/20260426_s208_group_e_pass3_live/`:
  - `S2-08_Group_E_viewer_pass3.png` — live viewer screenshot showing a recognizable
    leaning tower with caps, pillars, and base disks above the ground plane.
  - `S2-08_Group_E_three_projection_local.png` — XY/XZ/YZ deterministic projection.
  - `S2-09_Group_F_viewer_regression.png` — S2-09F still renders the orange/red lattice.
  - `assessment.md`, `capture-results.json`.

## Risks or Open Questions

- [ ] S2-08E remaining 2 unsupported are 196/197 (`abs(x)+abs(x)=...`,
      `abs(y)+abs(y)=...`). These are degenerate Desmos LaTeX (likely a typo for
      `abs(x)+abs(y)=...`) and are mathematically equivalent to `x = ±N/2`,
      a single-axis equation. The classifier correctly rejects them.
- [ ] The new `FLAT_AXIS_RANGE_FRACTION = 0.10` threshold is a heuristic that may need
      tuning if a future fixture has a wall-like surface whose constraint range is
      between 10% and 100% of the viewport.
- [ ] The implicit 2-axis path's `_refine_iso_window` only scans 32 samples per axis;
      contours with fine detail relative to the seed window may miss features. The
      existing 3-axis path has more aggressive bbox refinement; if a future fixture
      regresses on a fine 2D shape, port that refinement too.

## Recommended Next Wake

Either: (a) add a 1D-curve render path for explicit `y=N {tiny x range}` expressions so
they show as visible lines instead of paper-thin strips, OR (b) keep walking the partial
list — biggest remaining unsupported counts after pass 3 are S2-04 Group G (36),
S2-08 Group G, and S2-10 Group F.

## User-Facing Update

S2-08 Group E now visually matches the Desmos leaning tower in the live viewer. Prim
count 78 → 81, unsupported 5 → 2; the previously-tall vertical-sheet artifacts are gone
and the tower stands on the ground plane with caps, pillars and base disks visible.
S2-09 Group F regression guard intact.

---

# Handoff: 2026-04-26 19:30 SGT — S2-08E Pass 2

## Active Task

Fix S2-08 Group E rotated leaning-tower cylinders (broken: viewer shows thin
strips instead of leaning circular bands), then triage other remaining partial
fixtures.

## What Changed

- `src/desmos2usd/tessellate/implicit.py`: added `tessellate_implicit_surface_3axis_marching` as a fallback when the existing circle-fit `tessellate_circular_implicit_surface` cannot match the slice cross-section. The fallback marches squares at each predicate-bounded slice and stitches adjacent slices via nearest-segment matching. Includes `_refine_3axis_bbox` (two-stage scan: coarse sign-change, then zoom around argmin |residual|) so tiny features (e.g. radius 0.06 in viewport ±12) are not invisible to a fixed-resolution grid.
- `src/desmos2usd/parse/predicates.py`: extended `variable_bounds` to handle `axis = constant` predicates as degenerate bounds `(N, N)`. Lets the 3-axis tessellator pick a slicing axis even when the predicate is exact equality (e.g. `z=8`).
- `src/desmos2usd/tessellate/slabs.py`: added `_refine_inequality_bbox` so the voxel sampler (`tessellate_sampled_inequality_region`) coarse-scans the predicate region first; small inequality regions in large viewports now produce voxels.
- `tests/test_student_fixture_regressions.py`: 4 new regression tests covering the rotated tilted cylinder, the small-offset variant, the equality-predicate bound, and the inequality bbox refinement.

## Validation

- `PYTHONPATH=src:tests python3 -m unittest discover tests` → 102 tests, OK (~5 min).
- Full `[4B]` fixture sweep at resolution=12: 24 success / 47 partial / 0 error (was 21 / 50 / 0). 18 fixtures improved, no fixture regressed.
- Per-fixture deltas:
  - **S2-08 Group E**: 38 → 78 prims, 45 → 5 unsupported. (PRIMARY TARGET.)
  - **S2-09 Group F**: 27 → 27 prims, 0 → 0 unsupported (regression guard intact).
  - **S2-10 Group F**: 85 → 120 prims, 82 → 47 unsupported.
  - **S2-07 Group E**: 15 → 34 prims, 20 → 1 unsupported.
  - **S2-08 Group G**: 1217 → 1236 prims, 42 → 23 unsupported.
  - **S2-09 Group B**: 52 → 60 prims, 13 → 5 unsupported.
  - Plus 12 more fixtures with smaller gains.
  - **Promoted partial → success** (+3): S2-05 Group A, S2-05 Group E, S2-06 Group C.

## Risks or Open Questions

- [ ] Live browser visual capture not possible from chekbook in this dispatched session (viewer is on chekstool). The generated USDA/USDZ files are the "after" artifacts; main agent on chekstool needs to refresh the live viewer screenshot at the URL in the original task brief and place it as `viewer_after_pass2.png` in `artifacts/fixture_usdz/review_evidence/20260426_s208_group_e_pass2/`.
- [ ] S2-08E remaining 5 unsupported are edge cases:
  - 2 single-axis `abs(x)+abs(x) = N` (likely fixture authoring typo for `abs(x)+abs(y) = N`; classifier legitimately rejects single-axis equation).
  - 3 flat disks `x^2+y^2 <= N {z=N}` — voxel sampler cannot fill a single-z slice; needs a flat-disk render path.
- [ ] S2-09F-style large tilted inequality cylinders with `(x - z*tan(theta))^2 + y^2 < r^2` over wide z range still under-resolve because the cylinder slides across voxel cells faster than the voxel can capture. Would need voxel grid aligned to the cylinder axis, or octree refinement.
- [ ] Top remaining sweep blocker categories (post pass 2): predicate violations (~41 occurrences), `Unsupported expression node Tuple` (~81), various Desmos restriction parse edge cases (`7{0`, `1{2.7`, etc.).

## Recommended Next Wake

Either: (a) add a flat-disk render path for `inequality_region` when one axis has a degenerate (low==high) bound, OR (b) tackle the `Unsupported expression node Tuple` family (~81 occurrences) which appears to be parametric u/v Tuple AST handling.

## User-Facing Update

S2-08 Group E unsupported expressions dropped from 45 to 5 (-89%); prim count doubled (38 → 78). Full sweep gained 3 success promotions and improved 18 fixtures with no regressions.

---

# Handoff: 2026-04-26 16:30 SGT — Visual Parity Pass

## Active Task

Make generated USDA viewer output visually credible against the original
Desmos 3D graphs, starting with the two unresolved targets from the previous
hand-off and then triaging the full fixture set.

Primary targets:

- **S2-05 Group D** — viewer rendered the Eiffel-tower truss as a faint
  1-pixel skeleton even though the geometry was structurally complete.
- **S2-03 Group B** — paraboloid-cap "fins" rendered as scattered jagged
  fragments instead of smooth caps.
- Regression guard: **S2-09 Group F** — must remain visually unchanged.

## Diagnosis

Two distinct root causes.

1. **Curves render as 1-pixel lines.** `viewer/app.js` rendered every
   `BasisCurves` prim as `gl.LINE_STRIP` with `gl.lineWidth(2)`. Desktop
   browsers ignore `gl.lineWidth > 1`, so curves were always 1 pixel wide.
   With 125 curves making up the S2-05 truss, the tower looked like a wire
   skeleton.

2. **Surface boundary is grid-quantized.** `tessellate_explicit_surface`
   used `quad_faces`, which only emits a quad if all four corners satisfy
   the predicates. At resolution=8, a surface clipped by `z>3` has its
   true contour rim approximated by whatever grid cells happen to have
   four valid corners — a small irregular subset of the actual cap.

S2-09 Group F has zero `BasisCurves` and zero `explicit_surface` prims, so
neither fix can affect it.

## What Changed

- `viewer/app.js`
  - New `appendTubeGeometry()` builds a 6-sided cylindrical tube along each
    polyline using a rotation-minimizing parallel-transport frame.
  - Tube radius: `clamp(diag * 0.006, 0.015, diag * 0.025)`. Tuned against
    the Desmos S2-05 reference.
  - Tubes feed the existing mesh shader (so they receive the same lighting
    as `Mesh` prims) via a new per-prim `tubeRanges` list. Opaque /
    translucent / selected passes and pick rendering all iterate the tube
    ranges. The legacy LINE_STRIP pass is preserved as a fallback for
    degenerate or zero-radius curves only.
  - No semantic exporter changes from this fix.

- `src/desmos2usd/tessellate/surfaces.py`
  - New `refined_quad_faces()` replaces `quad_faces` for explicit_surface
    cells whose corners straddle the predicate boundary. Mixed cells
    bisect along each mixed-validity edge to localize the predicate
    transition (`QUAD_BOUNDARY_REFINE_ITERATIONS = 8`), and the polygon
    formed by valid corners + boundary samples is fanned into triangles.
  - `_bisect_predicate_crossing()` does the bisection using
    `evaluate_half_open` with the same tolerance as the original corner
    check, so adjacent strict-bound surfaces still tile cleanly.
  - `_surface_predicates_constrain_solved_axis()` short-circuits the
    refinement when no predicate references the solved axis (e.g. only
    domain-axis bounds). In that case the boundary already aligns with the
    grid and the cheap `quad_faces` path is used. This keeps the suite
    fast on surfaces where refinement would add nothing.

## Target Artifacts

- All `artifacts/fixture_usdz/*.usda` and `*.usdz` artifacts regenerated
  by re-running `desmos2usd.validate.fixture_usdz_suite --no-validate-usdz`
  at the suite default `resolution=8`. `summary.json` rebuilt.
- S2-09 Group F regen produces byte-identical tessellation (no curves, no
  explicit_surface).

## Evidence

- Evidence directory:
  `artifacts/fixture_usdz/review_evidence/20260426_visual_parity_pass/`
- Per-target before/after browser captures (Playwright vs the in-flight
  viewer served via `python3 -m http.server` from the fresh clone):
  - `s205_groupD_viewer_before.png`, `s205_groupD_viewer_after_tubes_v2.png`,
    `s205_groupD_desmos_reference.png`
  - `s203_groupB_viewer_before.png`, `s203_groupB_viewer_after_refine.png`,
    `s203_groupB_desmos_reference.png`
  - `s209_groupF_viewer_before.png`, `s209_groupF_viewer_after_all.png`
- Triage table covering all 67 student + acceptance fixtures:
  `triage_table.md` in the same directory.
- Assessment write-up: `assessment.md`.

## Visual Judgment

- **S2-05 Group D**: the new screenshot shows a solid-looking
  Eiffel-tower silhouette: bold red curved base legs, gray lattice trusses
  with material weight, cap and spire. Matches the Desmos reference
  capture at the same camera basis.
- **S2-03 Group B**: scattered fin chunks replaced by smooth rounded
  paraboloid caps following the `z=3` contour. Per-surface face counts
  grew from 7-30 to 30-84. Still a touch more uniform than the wavier
  Desmos reference (which reflects the `a=0.07` slider parameter and the
  more elaborate shape of those expressions), but the "broken puzzle
  pieces" failure mode is gone.
- **S2-09 Group F**: pixel-identical. Regression guard held.

## Validation

- `node --check viewer/app.js` → OK
- `pytest tests/` after viewer + boundary refinement: 94 passed, 23
  subtests passed in 4m51s.
- `pytest tests/test_tessellate.py tests/test_student_fixture_regressions.py -q`
  after the optimization (axis-aware refinement, 8 iterations): 34
  passed, 23 subtests passed in 30.67s.
- `usdcat -l` validated regenerated S2-03 USDA artifact.
- `git diff --check` clean.
- Live browser screenshot evidence captured against the in-flight viewer
  via Playwright. The production tailnet URL still serves the older
  chekstool copy until this branch is pushed and the viewer redeployed.

## Commit / Push

- Workdir is a fresh clone of `git@github.com:chektien/desmos2usd.git` at
  `/tmp/desmos2usd-carey-visual-20260426-160834/` on branch
  `fix/student-fixture-usdz-export`.
- HEAD before this pass: `c63b2ed` (Fix all-fixture review index links).
- Commits planned for this pass (single coherent commit per fix):
  1. viewer-side tube rendering and the supporting per-prim tube ranges,
  2. exporter-side explicit_surface boundary refinement,
  3. regenerated fixture artifacts + summary,
  4. evidence directory + STATE/handoff updates.
- Push target: `chektien:fix/student-fixture-usdz-export`. Do not rewrite
  history; do not close, merge, or delete PR #1.

## Follow-ups (not in this pass)

- `parametric_surface` and `implicit_surface` use their own tessellators
  (`tessellate/parametric.py`, `tessellate/implicit.py`) and would benefit
  from a similar boundary-refinement treatment for clipped cases. Out of
  scope for this pass; flagged for a future pass.
- `S2-08 Group G` (1208 curves) remains a pre-existing
  no-USDA failure; suite limits / curve cap need a separate triage.
- Recommended next step: kick off the HOME Codex review against this
  branch once pushed.
