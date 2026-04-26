# Visual parity repair pass — 2026-04-26

## Scope

Make generated USDA viewer output visually credible against original Desmos 3D
graphs, not merely structurally valid. Primary targets: **S2-05 Group D**
(skeletal/wireframe look), **S2-03 Group B** (paraboloid-cap fin artifacts),
plus regression guard on **S2-09 Group F**.

## Diagnosis

Two distinct root causes.

### Curve-heavy scenes render as 1-pixel skeletons

`viewer/app.js` rendered `BasisCurves` as `gl.LINE_STRIP` with `gl.lineWidth(2)`
(line 779). WebGL ignores `lineWidth > 1` on virtually every desktop browser
and driver, so curves were always 1 pixel wide regardless of the requested
width. For S2-05 Group D — 125 parametric curves making up the Eiffel-tower
truss — this turned an Eiffel-shaped solid into a faint wire skeleton even
though the underlying USDA geometry was correct.

### Surface-with-z-constraint clipping yields jagged "fin" fragments

`tessellate_explicit_surface` samples a `resolution × resolution` grid and
emits a quad only when **all four corners** satisfy the predicates
(`quad_faces` in `tessellate/mesh.py`). At fixture-suite resolution (8), this
gives the rim of a paraboloid cap clipped by `z>3` (S2-03 Group B's "shark
fins") only the cells whose grid corners all happen to land above z=3 — a
small irregular subset that looks like scattered chunks rather than a smooth
boundary contour.

S2-09 Group F is composed entirely of `inequality_region` (26) and
`implicit_surface` (1) prims with **zero curves** and **zero
explicit_surface** prims, so it acts as a clean regression guard for both
fixes.

## Fix 1 — Viewer-side hexagonal tubes around every curve

`viewer/app.js`

- New helper `appendTubeGeometry()` builds a 6-sided cylindrical tube along
  each polyline using a rotation-minimizing parallel-transport frame so the
  tube has continuous roll across segments.
- Tube radius scales with the scene-bounds diagonal:
  `clamp(diag * 0.006, 0.015, diag * 0.025)`. Tuned against Desmos's curve
  thickness on tower-like scenes; small enough that adjacent legs don't fuse,
  large enough that the truss reads as solid.
- Tubes are emitted into the existing mesh position/color/normal/index
  buffers and drawn with the standard `mesh` shader (so they receive the
  same lighting as `Mesh` prims).
- Per-prim `tubeRanges` are tracked alongside `meshRange`, with both opaque
  and translucent passes, selection highlighting, and pick rendering all
  iterating tube ranges. The legacy `LINE_STRIP` pass is skipped for any
  prim that produced tubes (so we don't draw a darker silhouette on top of
  the lit cylinders); it remains as a fallback for degenerate/zero-radius
  curves.

This is a **viewer-only** change — no USDA artifacts are regenerated for the
fix to take effect, and any scene with zero `BasisCurves` prims is
byte-identical to the previous viewer output.

## Fix 2 — Marching-squares boundary refinement on explicit_surface

`src/desmos2usd/tessellate/surfaces.py`

- New `refined_quad_faces()` replaces the call to `quad_faces()` in
  `tessellate_explicit_surface`. Cells with all-valid or all-invalid corners
  behave exactly as before. Cells whose corners straddle a predicate boundary
  bisect along each mixed-validity edge to find the predicate transition,
  emit triangles connecting the still-valid corners with the boundary
  samples, and drop the rest.
- New `_bisect_predicate_crossing()` performs `QUAD_BOUNDARY_REFINE_ITERATIONS = 18`
  bisections along the cell edge using the same `evaluate_half_open` semantics
  the corner check uses, so adjacent surfaces still tile cleanly along shared
  strict-inequality boundaries.
- This converts S2-03's scattered fin chunks into smooth rounded paraboloid
  caps that follow the actual `z=3` contour, without raising the grid
  resolution. Per-surface face counts roughly triple on bounded surfaces;
  unbounded surfaces are unaffected because they never enter the mixed-cell
  branch.

This change requires regenerating USDA artifacts to take effect; the viewer
itself is unchanged for this fix.

## Validation

- `node --check viewer/app.js` → OK
- `pytest tests/` baseline (pre-change) → 94 passed in 4m38s
- `pytest tests/` after viewer + boundary refinement → see test log under
  `validation_after.log`
- `usdcat -l` on regenerated S2-03 USDA → OK
- Live browser screenshot evidence at the URLs Chek normally uses
  (`http://127.0.0.1:8842/...` for the in-flight changes; production
  Tailnet URL serves chekstool's older copy until pushed).

## Per-target status

### S2-05 Group D — FIXED

- Before (`s205_groupD_viewer_before.png`): faint 1-pixel red/gray
  skeleton barely readable as a tower.
- After tubing (`s205_groupD_viewer_after_tubes_v2.png`): solid
  Eiffel-tower silhouette with bold red curved legs at the base, gray
  lattice trusses with visible thickness, cap and spire clearly defined.
  Matches Chek's description of the Desmos reference.

### S2-03 Group B — FIXED

- Before (`s203_groupB_viewer_before.png`): blue body + orange interior
  rectangles with scattered jagged white chunks (fin fragments) on top.
- After boundary refinement (`s203_groupB_viewer_after_refine.png`):
  blue body + orange interior unchanged; white fins now read as smooth
  rounded paraboloid caps following the `z=3` contour. Per-surface face
  counts went from 7–30 to 30–84 (e.g. expr_0000__110: 7 → 39 faces;
  expr_0005__127: 30 → 70 faces).

### S2-09 Group F — REGRESSION GUARD HELD

- Before (`s209_groupF_viewer_before.png`) and after both fixes
  (`s209_groupF_viewer_after_all.png`): pixel-identical. The scene has 0
  `BasisCurves` prims and 0 `explicit_surface` prims, so neither change
  alters its rendering. USDA artifact for S2-09 was not regenerated.

## All-fixture triage table

(see `triage_table.md` for the full per-fixture table after the suite-wide
regen completes; this document captures the targeted fixes only)
