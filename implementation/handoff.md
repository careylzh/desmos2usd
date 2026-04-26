# Handoff: 2026-04-27 06:55 SGT - S2-07F unbounded sphere tranche

## Current Branch State
- Repo: `/Users/chek/repos/desmos2usd-carey`
- Branch: `fix/student-fixture-usdz-export`
- Push target: `chektien:fix/student-fixture-usdz-export`
- Previous HEAD before this tranche: `2b3ecae Improve S2-07F point-list triangle export`

## Completed This Tranche
- Targeted fixture: `[4B] 3D Diagram - S2-07 Group F.json`
- Desmos URL: `https://www.desmos.com/3d/jkj1z8t8pf`
- Implemented one general exporter fix:
  - three-axis implicit equalities now try a fitted axis-aligned ellipsoid path when the existing circular-extrusion path cannot handle the expression
  - the fitter validates no cross terms, consistent quadratic signs, finite center/radii, and sampled boundary residuals before emitting a closed mesh
  - predicates are respected by rejecting the ellipsoid fast path if any generated vertex violates an existing predicate
- No fixture-specific expression ids, fixture names, or one-off constants were added.
- Added regression coverage for an unbounded tiny implicit sphere.
- Regenerated tracked artifacts for S2-07F plus S2-08E/S2-09F guards and rebuilt the 71-fixture `artifacts/fixture_usdz/summary.json` from reports.

## Evidence
- Evidence directory: `artifacts/fixture_usdz/review_evidence/20260427_s207_group_f_ralph_spheres/`
- Files:
  - `S2-07_Group_F_projection_before.png`
  - `S2-07_Group_F_projection_before.ppm`
  - `S2-07_Group_F_projection_after.png`
  - `S2-07_Group_F_projection_after.ppm`
  - `S2-07_Group_F_projection_after.usda`
  - `S2-08_Group_E_projection_guard_after.png`
  - `S2-08_Group_E_projection_guard_after.ppm`
  - `S2-08_Group_E_projection_guard_after.usda`
  - `S2-09_Group_F_projection_guard_after.png`
  - `S2-09_Group_F_projection_guard_after.ppm`
  - `S2-09_Group_F_projection_guard_after.usda`
  - `projection_results.json`
  - `capture_results.json`
  - `assessment.md`
- Browser/live viewer blockers:
  - Chrome DevTools navigation to Desmos returned `user cancelled MCP tool call`.
  - Playwright navigation to Desmos returned `user cancelled MCP tool call`.
  - Local viewer server bind failed with `PermissionError: [Errno 1] Operation not permitted`.
- Visual claim: no live Desmos/viewer parity claim. This tranche has deterministic local projection evidence only.

## Metrics
- Overall fixture summary remains 71 fixtures, 26 success, 45 partial, 0 error, 71 USDZ, acceptance still not met.
- S2-07 Group F before: `835 prims / 53 unsupported / 875 classified / 888 renderable`.
- S2-07 Group F after: `874 prims / 14 unsupported / 875 classified / 888 renderable / valid true / usdchecker returncode 0`.
- S2-08 Group E guard remains success: `87 prims / 0 unsupported / valid true / usdchecker returncode 0`.
- S2-09 Group F guard remains success: `27 prims / 0 unsupported / valid true / usdchecker returncode 0`.

## Validation
- Focused unbounded sphere regression passed.
- Full `tests.test_student_fixture_regressions`: `Ran 50 tests in 0.568s OK`.
- Visual/fixture unit tests: `tests.test_visual_preview tests.test_fixture_usdz_suite` ran `5` tests OK.
- Full unittest discovery with `PYTHONPATH=src:tests python3 -m unittest discover -s tests`: `Ran 124 tests in 135.452s OK`.
- Report-vs-USDA consistency checked:
  - S2-07F report prim_count `874`, USDA `Mesh` + `BasisCurves` defs `874`, unsupported `14`
  - S2-08E report prim_count `87`, USDA defs `87`, unsupported `0`
  - S2-09F report prim_count `27`, USDA defs `27`, unsupported `0`
- `git diff --check`: passed.

## Commit / Push
- Commit/push blocked before staging.
- Exact blocker: `git add -u` failed with `fatal: Unable to create '/Users/chek/repos/desmos2usd-carey/.git/index.lock': Operation not permitted`.
- Worktree is ready for the main environment to stage tracked changes, force-add the ignored evidence directory, commit, and push to `chektien:fix/student-fixture-usdz-export`.
- Required staging commands:
  - `git add -u`
  - `git add -f artifacts/fixture_usdz/review_evidence/20260427_s207_group_f_ralph_spheres/`

## Remaining Mismatch / Next Wake Instructions
1. Do not claim visual parity until live Desmos reference screenshots and live viewer screenshots can be captured.
2. S2-07F remaining unsupported families:
   - parser/classifier misses for implicit multiplication in equations such as `2z=.515x+1.91` and `.5x+3.76 <= z <= .8x+4.13`
   - chained affine z-slab inequalities such as `.5 <= z <= 1+.43(x+0.6)`
   - sampled inequality region `325`
3. Next highest-impact partial after this tranche remains S2-10 Group F (`https://www.desmos.com/3d/tejhfrm34m`) unless the orchestrator wants another bounded S2-07F classification/parser pass.
4. Preserve S2-08 Group E and S2-09 Group F as regression guards.
