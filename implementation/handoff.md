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
    transition (`QUAD_BOUNDARY_REFINE_ITERATIONS = 12`), and the polygon
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
  after the optimization (axis-aware refinement, 12 iterations): 34
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
